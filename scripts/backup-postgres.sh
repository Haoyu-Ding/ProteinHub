#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${PROTEINHUB_ENV_FILE:-/etc/proteinhub.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${PROTEINHUB_DATABASE_URL:?PROTEINHUB_DATABASE_URL is required}"

BACKUP_DIR="${PROTEINHUB_BACKUP_DIR:-/var/backups/proteinhub}"
RETENTION_DAYS="${PROTEINHUB_BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_FILE="$BACKUP_DIR/proteinhub_$TIMESTAMP.dump"

mkdir -p "$BACKUP_DIR"
pg_dump --format=custom --file="$OUTPUT_FILE" "$PROTEINHUB_DATABASE_URL"

find "$BACKUP_DIR" -type f -name "proteinhub_*.dump" -mtime +"$RETENTION_DAYS" -print -delete
echo "$OUTPUT_FILE"
