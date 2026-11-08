#!/bin/sh
set -eu
umask 077
stamp=$(date -u +%Y%m%dT%H%M%SZ)
case "$PGDATABASE" in
  *-pooler.*) echo 'Backup requires a direct Neon connection.' >&2; exit 1 ;;
esac
export PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=0'
database="/backups/neon-$stamp.dump"
media="/backups/media-$stamp.tar.gz"
trap 'rm -f "$database.part" "$media.part"' EXIT
pg_dump --format=custom --no-owner --no-acl --file="$database.part"
pg_restore --list "$database.part" >/dev/null
tar -czf "$media.part" -C /media .
mv "$database.part" "$database"
mv "$media.part" "$media"
cd /backups
sha256sum "neon-$stamp.dump" "media-$stamp.tar.gz" >"$stamp.sha256"
echo "Backup completed: $stamp (archive listing checked; restore not tested)."
