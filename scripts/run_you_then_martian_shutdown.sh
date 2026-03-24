#!/bin/zsh

set -eu
setopt pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

YOU_INPUT="/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/YOU - A Novel(Kor).txt"
MARTIAN_INPUT="/Users/hyeokjunkong/Desktop/소설/The Martian/The_Martian_by_Andy_Weir_ko_chatgpt.txt"

VOICE="${VOICE:-cove}"
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-600}"
CHATGPT_WEB_VISIBLE="${CHATGPT_WEB_VISIBLE:-0}"
SHUTDOWN_ON_SUCCESS="${SHUTDOWN_ON_SUCCESS:-1}"

cd "${SCRIPT_DIR}/.."

export VOICE
export REQUEST_TIMEOUT_SEC
export CHATGPT_WEB_VISIBLE
export SHUTDOWN_ON_SUCCESS

"${SCRIPT_DIR}/run_chatgpt_web_batch.sh" \
  "${YOU_INPUT}" \
  "${MARTIAN_INPUT}"
