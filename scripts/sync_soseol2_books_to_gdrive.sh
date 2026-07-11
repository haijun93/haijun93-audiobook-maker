#!/bin/zsh
set -euo pipefail

SOURCE_ROOT="/Users/hyeokjunkong/Desktop/소설2"
DEST_ROOT="/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books"
LOG_DIR="/Users/hyeokjunkong/Library/Logs/soseol2"
LOG_FILE="${LOG_DIR}/gdrive_books_sync.log"
LOCK_DIR="${LOG_DIR}/gdrive_books_sync.lock"

mkdir -p "$LOG_DIR"

log() {
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "SKIP another sync is already running"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

if [[ ! -d "$SOURCE_ROOT" ]]; then
  log "ERROR missing source root: $SOURCE_ROOT"
  exit 1
fi

mkdir -p "$DEST_ROOT"
log "START sync to $DEST_ROOT"

for folder in "[s]" "[k]" "[k-e]"; do
  source_dir="${SOURCE_ROOT}/${folder}"
  dest_dir="${DEST_ROOT}/${folder}"
  if [[ ! -d "$source_dir" ]]; then
    log "SKIP missing source folder: $source_dir"
    continue
  fi

  mkdir -p "$dest_dir"
  log "SYNC ${folder}"
  /usr/bin/rsync -a --delete --delete-excluded --human-readable \
    --exclude '.DS_Store' \
    "${source_dir}/" \
    "${dest_dir}/" >> "$LOG_FILE" 2>&1
done

log "DONE sync"
