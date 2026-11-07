"""Restore a private dump into a new local PG18 cluster and rehearse migrations.

Never connects to DATABASE_URL or Neon. Does not run application tests on real
copied users. Private local cluster remains stopped for inspection afterward.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2 import sql
from neon_preflight import ROOT, verify_backup

EXPECTED = {
    ('usuarios', '0005_email_case_unique'), ('usuarios', '0006_wishlist'),
    ('usuarios', '0007_promotions_checkout'), ('productos', '0002_stock_movements'),
    ('productos', '0003_verified_reviews'), ('carrito', '0003_promotions_checkout'),
    ('carrito', '0004_legacy_coupons'), ('carrito', '0005_promotion_constraints'),
}


def schema(conn):
    """Compare all public tables, columns/defaults, constraints and indexes."""
    with conn.cursor() as cur:
        cur.execute("SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default,"
                    "character_maximum_length,numeric_precision,numeric_scale,is_identity,identity_generation "
                    "FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position")
        columns = cur.fetchall()
        cur.execute("SELECT c.relname,k.conname,k.contype,pg_get_constraintdef(k.oid),k.convalidated "
                    "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1,2")
        constraints = cur.fetchall()
        cur.execute("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2")
        indexes = cur.fetchall()
        cur.execute("SELECT sequencename,data_type,start_value,min_value,max_value,increment_by,cycle,cache_size "
                    "FROM pg_sequences WHERE schemaname='public' ORDER BY 1")
        sequences = cur.fetchall()
        cur.execute("SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2")
        triggers = cur.fetchall()
        cur.execute("SELECT tablename,policyname,permissive,roles,cmd,qual,with_check "
                    "FROM pg_policies WHERE schemaname='public' ORDER BY 1,2")
        policies = cur.fetchall()
        cur.execute("SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY 1")
        row_security = cur.fetchall()
    return {'columns': columns, 'constraints': constraints, 'indexes': indexes,
            'sequences': sequences, 'triggers': triggers, 'policies': policies, 'row_security': row_security}


def fingerprints(conn, selected=None, metadata_ids=None):
    """Hash original column values for every public table, without emitting rows."""
    if selected is None:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name,column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name <> 'django_migrations' "
                        "ORDER BY table_name,ordinal_position")
            selected = {}
            for table, column in cur.fetchall():
                selected.setdefault(table, []).append(column)
    result = {}
    for table, columns in selected.items():
        condition = sql.SQL(' WHERE id = ANY(%s)') if metadata_ids is not None and table in metadata_ids else sql.SQL('')
        query = sql.SQL('SELECT row_to_json(r)::text FROM (SELECT {} FROM public.{}{}) r ORDER BY row_to_json(r)::text COLLATE "C"').format(
            sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(table), condition)
        digest = hashlib.sha256()
        count = 0
        conn.ensure_connection()
        with conn.connection.cursor(name='fingerprint_' + secrets.token_hex(5), withhold=True) as cur:
            cur.itersize = 1000
            if metadata_ids is not None and table in metadata_ids:
                cur.execute(query, [metadata_ids[table]])
            else:
                cur.execute(query)
            for (row,) in cur:
                encoded = row.encode('utf-8')
                digest.update(len(encoded).to_bytes(8, 'big'))
                digest.update(encoded)
                count += 1
        result[table] = {'count': count, 'sha256': digest.hexdigest()}
    return selected, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup', type=Path)
    parser.add_argument('--pg-bin', type=Path, default=Path(r'C:\Program Files\PostgreSQL\18\bin'))
    args = parser.parse_args()
    verify_backup(args.backup)
    work = ROOT / '.private' / ('rehearsal-' + secrets.token_hex(8))
    work.mkdir(parents=True)
    cluster = work / 'pgdata'
    password = secrets.token_urlsafe(32)
    pwfile = work / 'init-password'
    pwfile.write_text(password, encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('PG')}
    env.update(PGHOST='127.0.0.1', PGUSER='monolith_rehearsal', PGPASSWORD=password,
               PGSSLMODE='disable', PGCONNECT_TIMEOUT='2')
    process = None
    log = None

    def run(name, arguments):
        result = subprocess.run([str(args.pg_bin / (name + '.exe')), *arguments], env=env,
                                capture_output=True, timeout=300)
        if result.returncode:
            raise RuntimeError(name + ' failed (private details suppressed)')

    def connect(database):
        return psycopg2.connect(host='127.0.0.1', port=env['PGPORT'], user=env['PGUSER'],
                                password=password, dbname=database, connect_timeout=2, sslmode='disable')

    try:
        run('initdb', ['-D', str(cluster), '--username=monolith_rehearsal', '--auth=scram-sha-256',
                        '--pwfile=' + str(pwfile), '--encoding=UTF8', '--locale=C'])
        pwfile.unlink()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            env['PGPORT'] = str(listener.getsockname()[1])
        log = (work / 'postgres.log').open('wb')
        process = subprocess.Popen([str(args.pg_bin / 'postgres.exe'), '-D', str(cluster),
                                    '-h', '127.0.0.1', '-p', env['PGPORT']],
                                   stdout=log, stderr=log, env=env,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for attempt in range(60):
            try:
                conn = connect('postgres')
                break
            except psycopg2.OperationalError:
                if process.poll() is not None:
                    raise RuntimeError('Private PostgreSQL failed to start') from None
                time.sleep(0.25)
        else:
            raise RuntimeError('Private PostgreSQL startup timed out')
        conn.autocommit = True
        with conn.cursor() as cur:
            for database in ('rehearsal_copy', 'rehearsal_expected'):
                cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        conn.close()
        run('pg_restore', ['--no-password', '--no-owner', '--no-privileges', '--exit-on-error',
                           '--single-transaction', '--dbname=rehearsal_copy', str(args.backup.resolve())])
        print('PASS: full archive restoration into a newly initialized local cluster')

        # Configure Django before setup. No application settings or production URL are used.
        sys.path.insert(0, str(ROOT))
        from django.conf import settings
        config = {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'rehearsal_copy',
                  'USER': env['PGUSER'], 'PASSWORD': password, 'HOST': '127.0.0.1', 'PORT': env['PGPORT']}
        settings.configure(SECRET_KEY='isolated-rehearsal-only', USE_TZ=True,
                           DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
                           INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes',
                                           'django.contrib.admin', 'django.contrib.sessions',
                                           'rest_framework.authtoken',
                                           'usuarios', 'productos', 'carrito'],
                           AUTH_USER_MODEL='usuarios.Usuario', DATABASES={
                               'default': config, 'expected': {**config, 'NAME': 'rehearsal_expected'}},
                           EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
        import django
        django.setup()
        from django.db import connections
        from django.db.migrations.executor import MigrationExecutor
        source = connections['default']
        expected = connections['expected']
        executor = MigrationExecutor(source)
        executor.loader.check_consistent_history(source)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if any(backwards for _, backwards in plan) or {(m.app_label, m.name) for m, _ in plan} != EXPECTED:
            raise RuntimeError('Pending migration plan is not exactly the expected eight forward migrations')
        applied = set(executor.loader.applied_migrations)
        graph = executor.loader.graph
        targets = [node for node in applied if node in graph.node_map and
                   not any(child.key in applied for child in graph.node_map[node].children)]
        MigrationExecutor(expected).migrate(targets)
        before_schema = schema(source)
        if before_schema != schema(expected):
            raise RuntimeError('Restored public schema differs from the recorded Django migration state; manual review required')
        print('PASS: restored public columns, defaults, constraints and indexes match migration history')
        columns, before = fingerprints(source)
        # The production command also emits post_migrate, creating new Django
        # content types/permissions. Verify every original metadata row while
        # allowing those additive framework records.
        metadata_ids = {}
        with source.cursor() as cur:
            for table in ('django_content_type', 'auth_permission'):
                cur.execute(sql.SQL('SELECT id FROM public.{} ORDER BY id').format(sql.Identifier(table)))
                metadata_ids[table] = [row[0] for row in cur.fetchall()]
        from django.core.management import call_command
        call_command('migrate', interactive=False, verbosity=0)
        source.commit()
        _, after = fingerprints(source, columns, metadata_ids=metadata_ids)
        if before != after:
            raise RuntimeError('Existing table rows changed; preservation check failed')
        MigrationExecutor(expected).migrate(MigrationExecutor(expected).loader.graph.leaf_nodes())
        if schema(source) != schema(expected):
            raise RuntimeError('Migrated schema differs from a clean current Django migration schema')
        if MigrationExecutor(source).migration_plan(MigrationExecutor(source).loader.graph.leaf_nodes()):
            raise RuntimeError('Migrations remain pending')
        call_command('makemigrations', check=True, dry_run=True, verbosity=0)
        print('PASS: complete manage.py migrate lifecycle, including post_migrate; schema and models match')
        print('PASS: every original public table retains its row count and original-column SHA256')
        metadata_additions = {}
        with source.cursor() as cur:
            for table, ids in metadata_ids.items():
                cur.execute(sql.SQL('SELECT COUNT(*) FROM public.{}').format(sql.Identifier(table)))
                metadata_additions[table] = cur.fetchone()[0] - len(ids)
        print('Framework metadata rows added (original rows preserved):', json.dumps(metadata_additions))
        # No row data or secrets in this private technical manifest.
        result = {'backup_sha256': __import__('neon_preflight').file_digest(args.backup.resolve()),
                  'synthetic': json.loads(args.backup.resolve().with_suffix('.manifest.json').read_text(encoding='utf-8')).get('synthetic', False),
                  'created_utc': datetime.now(timezone.utc).isoformat(),
                  'migration_sha256': {f'{app}/{name}': __import__('neon_preflight').file_digest(
                      ROOT / app / 'migrations' / (name + '.py')) for app, name in sorted(EXPECTED)},
                  'migrations': sorted(EXPECTED), 'original_tables': before,
                  'schema_matches': True, 'rows_preserved': True,
                  'management_lifecycle_verified': True, 'metadata_additions': metadata_additions,
                  'scope': 'public columns/defaults/constraints/indexes/sequence definitions/triggers/RLS; not global roles, grants or extensions'}
        (work / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('Private rehearsal verification saved under .private; production remains unchanged.')
        connections.close_all()
    finally:
        pwfile.unlink(missing_ok=True)
        if process is not None and process.poll() is None:
            try:
                run('pg_ctl', ['-D', str(cluster), '-m', 'fast', '-w', 'stop'])
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=30)
        if log:
            log.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Rehearsal stopped:', type(exc).__name__, '(database/provider details suppressed)')
        sys.exit(1)
