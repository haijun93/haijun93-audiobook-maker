#!/bin/zsh
set -euo pipefail

SYNC_SCRIPT="/Users/hyeokjunkong/Library/Scripts/sync_soseol2_books_to_gdrive.sh"
LOG_DIR="/Users/hyeokjunkong/Library/Logs/soseol2"
LOOP_LOG="${LOG_DIR}/gdrive_books_sync_loop.log"
INTERVAL_SECONDS=43200

mkdir -p "$LOG_DIR"

while true; do
  {
    print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] LOOP start sync"
    /bin/zsh "$SYNC_SCRIPT"
    sync_status=$?
    print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] LOOP sync exit=${sync_status}; sleeping ${INTERVAL_SECONDS}s"
  } >> "$LOOP_LOG" 2>&1
  sleep "$INTERVAL_SECONDS"
done
