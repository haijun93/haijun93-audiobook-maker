#!/bin/zsh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}" || exit 1

VOICE="${VOICE:-cove}" \
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-600}" \
CHATGPT_WEB_VISIBLE="${CHATGPT_WEB_VISIBLE:-0}" \
SHUTDOWN_ON_SUCCESS=1 \
"${SCRIPT_DIR}/run_chatgpt_web_job.sh" \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/YOU - A Novel(Kor).txt" \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a" \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work"
