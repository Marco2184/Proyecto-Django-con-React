#!/bin/sh
set -eu
umask 077
stamp=$(date -u +%Y%m%dT%H%M%SZ)
case "${PGDATABASE:-}" in
  postgres://*|postgresql://*) ;;
  *) echo 'Backup requires the direct Neon connection URI in PGDATABASE.' >&2; exit 1 ;;
esac
case "$PGDATABASE" in
  *-pooler.*) echo 'Backup requires a direct Neon connection.' >&2; exit 1 ;;
esac
export PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=0'
if [ ! -d /media ]; then
  echo 'Media directory is missing. Check the backup volume mount.' >&2
  exit 1
fi
first_media_file=$(find /media -type f -print -quit)
media_status=empty
if [ -n "$first_media_file" ]; then
  media_status=present
fi
database="/backups/neon-$stamp.dump"
media="/backups/media-$stamp.tar.gz"
trap 'rm -f "$database.part" "$media.part"' EXIT
# libpq does not expand an environment-default dbname as a connection URI.
# Pass it explicitly; never enable shell tracing or print provider error bodies.
if ! pg_dump --dbname="$PGDATABASE" --no-password --format=custom --no-owner --no-acl --file="$database.part" 2>/dev/null; then
  echo 'PostgreSQL backup failed. Check the direct URL, TLS, permissions and pg_dump version; credentials suppressed.' >&2
  exit 1
fi
pg_restore --list "$database.part" >/dev/null
tar -czf "$media.part" -C /media .
tar -tzf "$media.part" >/dev/null
mv "$database.part" "$database"
mv "$media.part" "$media"
cd /backups
sha256sum "neon-$stamp.dump" "media-$stamp.tar.gz" >"$stamp.sha256"
printf '# media_status=%s\n' "$media_status" >>"$stamp.sha256"
echo "Backup completed: $stamp; media_status=$media_status (archive listings checked; restore not tested)."
