#!/bin/zsh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BOOK_DIR="${BOOK_DIR:-${HOME}/Desktop/소설/YOU - A Novel(Kor)}"

cd "${ROOT_DIR}" || exit 1

VOICE="${VOICE:-cove}" \
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-600}" \
CHATGPT_WEB_VISIBLE="${CHATGPT_WEB_VISIBLE:-0}" \
SHUTDOWN_ON_SUCCESS=1 \
"${SCRIPT_DIR}/run_chatgpt_web_job.sh" \
  "${BOOK_DIR}/YOU - A Novel(Kor).txt" \
  "${BOOK_DIR}/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a" \
  "${BOOK_DIR}/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work"
