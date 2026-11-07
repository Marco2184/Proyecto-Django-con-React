"""Read-only audit or private pg_dump. Never migrates or restores a database.

Run from the project root using .venv/Scripts/python.exe.
Credentials are read locally and never printed or passed as command arguments.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import psycopg2
from psycopg2.extensions import parse_dsn
from decouple import Config, RepositoryEnv

ROOT = Path(__file__).resolve().parents[1]


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_backup(path):
    path = path.resolve()
    directory = (ROOT / '.private' / 'backups').resolve()
    if path.parent != directory or path.suffix != '.dump':
        raise ValueError('Backup must be a .dump in .private/backups')
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('file') != path.name or manifest.get('bytes') != path.stat().st_size
            or manifest.get('sha256') != file_digest(path) or manifest.get('toc_checked') is not True):
        raise ValueError('Backup integrity verification failed')
    print('Backup filename, size and SHA256 match the manifest; original TOC check recorded.')
    print('Full restoration is not verified by this command.')


def configured(name):
    if os.environ.get(name):
        return os.environ[name]
    # compose.yaml interpolates DATABASE_URL from the root .env, overriding env_file.
    filenames = ('.env', '.env.docker') if name == 'DATABASE_URL' else ('.env.docker', '.env')
    for filename in filenames:
        path = ROOT / filename
        if path.exists():
            value = Config(RepositoryEnv(str(path)))(name, default='')
            if value:
                return value
    return ''


def direct_parameters():
    value = configured('DATABASE_URL_DIRECT')
    if not value:
        raise ValueError('Missing DATABASE_URL_DIRECT')
    params = parse_dsn(value)
    host = params.get('host', '').lower()
    if (not host.endswith('.neon.tech') or '-pooler' in host or ',' in host
            or 'hostaddr' in params or 'service' in params):
        raise ValueError('Expected one direct Neon hostname without pooler or host override')
    source = configured('DATABASE_URL')
    if not source:
        raise ValueError('DATABASE_URL required to confirm backup source identity')
    original = parse_dsn(source)
    # Compare identifiers only; never construct a direct URL by replacing a host.
    if (original.get('dbname') != params.get('dbname') or
            original.get('port', '5432') != params.get('port', '5432') or
            original.get('host', '').lower().replace('-pooler.', '.') != host):
        raise ValueError('Direct source differs from the configured application database')
    return params


def audit(conn):
    with conn.cursor() as cur:
        cur.execute('SHOW transaction_read_only')
        assert cur.fetchone()[0] == 'on'
        cur.execute('SHOW server_version')
        print('PostgreSQL:', cur.fetchone()[0])
        cur.execute('SELECT app,name FROM django_migrations ORDER BY app,name')
        applied = set(cur.fetchall())
        expected = {
            'usuarios': ['0005_email_case_unique', '0006_wishlist', '0007_promotions_checkout'],
            'productos': ['0002_stock_movements', '0003_verified_reviews'],
            'carrito': ['0003_promotions_checkout', '0004_legacy_coupons', '0005_promotion_constraints'],
        }
        for app, names in expected.items():
            for name in names:
                print(f'{app}.{name}:', 'applied' if (app, name) in applied else 'pending')
        cur.execute('SELECT COUNT(*) FROM (SELECT lower(email) FROM usuarios_usuario '
                    'GROUP BY lower(email) HAVING COUNT(*) > 1) duplicates')
        collisions = cur.fetchone()[0]
        print('Case-insensitive email collision groups (including blank):', collisions)
        # Detect manually created tables/columns before their migrations were recorded.
        checks = [
            ('usuarios', '0006_wishlist', 'usuarios_wishlistitem'),
            ('usuarios', '0006_wishlist', 'usuarios_pricenotification'),
            ('productos', '0002_stock_movements', 'productos_stockmovement'),
            ('productos', '0003_verified_reviews', 'productos_review'),
            ('carrito', '0003_promotions_checkout', 'carrito_promotion'),
            ('carrito', '0003_promotions_checkout', 'carrito_couponuse'),
        ]
        conflicts = []
        for app, migration, table in checks:
            cur.execute('SELECT to_regclass(%s)', [f'public.{table}'])
            exists = cur.fetchone()[0] is not None
            if exists != ((app, migration) in applied):
                conflicts.append(table)
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
                    "AND table_name='usuarios_pedido' AND column_name IN "
                    "('checkout_hash','checkout_key','checkout_response')")
        columns = {r[0] for r in cur.fetchall()}
        if (('usuarios', '0007_promotions_checkout') in applied and len(columns) != 3) or (
                ('usuarios', '0007_promotions_checkout') not in applied and columns):
            conflicts.append('usuarios_pedido checkout columns')
        print('Schema/record conflicts:', json.dumps(conflicts))
        cur.execute('SELECT COUNT(*) FROM pg_stat_activity WHERE datname=current_database() '
                    "AND wait_event_type='Lock'")
        print('Visible sessions waiting for locks:', cur.fetchone()[0])
        print('Preflight only; full schema comparison and isolated restore rehearsal still required.')
        return not collisions and not conflicts


def backup(params):
    if '-pooler' in params.get('host', ''):
        raise ValueError('Backup requires DATABASE_URL_DIRECT with an unpooled host')
    binary = shutil.which('pg_dump')
    if not binary:
        candidate = Path(r'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe')
        binary = str(candidate) if candidate.exists() else None
    if not binary:
        raise ValueError('Install PostgreSQL client tools (pg_dump and pg_restore)')
    restore = str(Path(binary).with_name('pg_restore.exe' if os.name == 'nt' else 'pg_restore'))
    directory = ROOT / '.private' / 'backups'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (datetime.now(timezone.utc).strftime('neon-%Y%m%dT%H%M%S%fZ') + '.dump')
    partial = target.with_suffix('.part')
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('PG')}
    mapping = {'host': 'PGHOST', 'port': 'PGPORT', 'user': 'PGUSER',
               'password': 'PGPASSWORD', 'dbname': 'PGDATABASE', 'channel_binding': 'PGCHANNELBINDING'}
    for key, variable in mapping.items():
        if key in params:
            env[variable] = params[key]
    env.update(PGSSLMODE='require', PGCONNECT_TIMEOUT='8',
               PGOPTIONS='-c default_transaction_read_only=on')
    try:
        result = subprocess.run([binary, '--no-password', '--format=custom', '--no-owner', '--no-privileges',
                                 '--lock-wait-timeout=10s', '--file', str(partial)],
                                env=env, capture_output=True, timeout=600)
        if result.returncode:
            raise RuntimeError('pg_dump failed; no verified backup created (details suppressed)')
        listing = subprocess.run([restore, '--list', str(partial)], capture_output=True, timeout=60)
        if listing.returncode:
            raise RuntimeError('Archive table-of-contents validation failed')
        digest = file_digest(partial)
        partial.rename(target)
        manifest = {'file': target.name, 'bytes': target.stat().st_size, 'sha256': digest,
                    'toc_checked': True, 'restore_rehearsed': False,
                    'created_utc': datetime.now(timezone.utc).isoformat()}
        target.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print('Private backup created; SHA256 and TOC verified. Restore rehearsal remains pending.')
    finally:
        partial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--backup', action='store_true', help='Read-only private custom-format backup')
    mode.add_argument('--verify-backup', type=Path, help='Verify an existing local dump against its manifest; no connection')
    mode.add_argument('--check-direct', action='store_true', help='Validate direct connection configuration without connecting')
    args = parser.parse_args()
    try:
        if args.verify_backup:
            verify_backup(args.verify_backup)
            return 0
        if args.check_direct:
            direct_parameters()
            print('PASS: direct Neon host without pooler; endpoint and database match DATABASE_URL. No connection made.')
            return 0
        dsn = configured('DATABASE_URL_DIRECT') if args.backup else configured('DATABASE_URL')
        if not dsn:
            raise ValueError('Missing DATABASE_URL_DIRECT' if args.backup else 'Missing DATABASE_URL')
        params = direct_parameters() if args.backup else parse_dsn(dsn)
        params.update(sslmode='require', connect_timeout='8',
                      options='-c default_transaction_read_only=on -c statement_timeout=15000')
        with psycopg2.connect(**params) as conn:
            conn.set_session(readonly=True)
            if args.backup:
                backup(params)
            else:
                return 0 if audit(conn) else 2
        return 0
    except (OSError, ValueError, RuntimeError, psycopg2.Error, subprocess.SubprocessError) as exc:
        print('Operation blocked:', type(exc).__name__, '(connection/provider details suppressed)')
        # Print only fixed diagnostics, never raw provider responses or DSNs.
        if isinstance(exc, psycopg2.OperationalError) and '10013' in str(exc):
            print('Windows socket error 10013: network access denied in this session.')
        direct_mode = args.backup or args.check_direct
        if not args.verify_backup and not configured('DATABASE_URL_DIRECT' if direct_mode else 'DATABASE_URL'):
            print('Missing variable:', 'DATABASE_URL_DIRECT' if direct_mode else 'DATABASE_URL')
        return 1


if __name__ == '__main__':
    sys.exit(main())
