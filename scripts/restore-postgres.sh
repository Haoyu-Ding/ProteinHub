#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/proteinhub_YYYYmmdd_HHMMSS.dump" >&2
  exit 2
fi

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 2
fi

ENV_FILE="${PROTEINHUB_ENV_FILE:-/etc/proteinhub.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${PROTEINHUB_DATABASE_URL:?PROTEINHUB_DATABASE_URL is required}"

echo "This will restore $BACKUP_FILE into the configured ProteinHub database."
echo "Stop the ProteinHub service before restoring."
read -r -p "Type RESTORE to continue: " CONFIRMATION
if [[ "$CONFIRMATION" != "RESTORE" ]]; then
  echo "Restore cancelled."
  exit 1
fi

pg_restore --clean --if-exists --no-owner --dbname="$PROTEINHUB_DATABASE_URL" "$BACKUP_FILE"
echo "Restore complete."
