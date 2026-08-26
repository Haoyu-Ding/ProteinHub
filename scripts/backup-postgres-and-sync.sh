#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${PROTEINHUB_ENV_FILE:-/etc/proteinhub.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

BACKUP_OUTPUT="$("$SCRIPT_DIR/backup-postgres.sh")"
printf '%s\n' "$BACKUP_OUTPUT"
BACKUP_FILE="$(printf '%s\n' "$BACKUP_OUTPUT" | tail -n 1)"

if [[ -z "${PROTEINHUB_REMOTE_BACKUP_TARGET:-}" ]]; then
  echo "PROTEINHUB_REMOTE_BACKUP_TARGET is not set; skipping remote backup sync."
  exit 0
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required for remote backup sync." >&2
  exit 1
fi

if [[ -n "${PROTEINHUB_REMOTE_BACKUP_SSH_KEY:-}" ]]; then
  if [[ ! -f "$PROTEINHUB_REMOTE_BACKUP_SSH_KEY" ]]; then
    echo "Remote backup SSH key not found: $PROTEINHUB_REMOTE_BACKUP_SSH_KEY" >&2
    exit 1
  fi
  RSYNC_SSH_COMMAND="ssh -i $PROTEINHUB_REMOTE_BACKUP_SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes"
else
  RSYNC_SSH_COMMAND="${PROTEINHUB_REMOTE_BACKUP_SSH_COMMAND:-ssh -o BatchMode=yes}"
fi

rsync -av -e "$RSYNC_SSH_COMMAND" "$BACKUP_FILE" "$PROTEINHUB_REMOTE_BACKUP_TARGET"
echo "Synced $BACKUP_FILE to $PROTEINHUB_REMOTE_BACKUP_TARGET"
