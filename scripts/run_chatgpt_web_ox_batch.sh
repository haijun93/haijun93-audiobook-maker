#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INPUT_DIR="${INPUT_DIR:-/Users/hyeokjunkong/Desktop/1차 시험/#STD/#Here}"
OUTPUT_DIR="${OUTPUT_DIR:-/Users/hyeokjunkong/Desktop/1차 시험/#STD/오디오북}"

MAX_CHARS="${MAX_CHARS:-1800}"
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-600}"
WATCHDOG_STALL_SEC="${WATCHDOG_STALL_SEC:-600}"
WATCHDOG_SEMANTIC_STALL_SEC="${WATCHDOG_SEMANTIC_STALL_SEC:-900}"
WATCHDOG_POLL_SEC="${WATCHDOG_POLL_SEC:-15}"
WATCHDOG_LOG_INTERVAL_SEC="${WATCHDOG_LOG_INTERVAL_SEC:-300}"
RETRY_SLEEP_SEC="${RETRY_SLEEP_SEC:-20}"
CHATGPT_WEB_MAX_ATTEMPTS="${CHATGPT_WEB_MAX_ATTEMPTS:-8}"

run_one() {
  local stem="$1"
  local input_file="${INPUT_DIR}/${stem}.docx"
  local output_file="${OUTPUT_DIR}/${stem}_audiobook_chatgpt_web_cove.m4a"
  local work_dir="${OUTPUT_DIR}/${stem}_audiobook_chatgpt_web_cove_work"

  if [[ ! -f "${input_file}" ]]; then
    echo "missing input: ${input_file}" >&2
    return 1
  fi

  echo "===== $(date '+%Y-%m-%d %H:%M:%S') start: ${stem} ====="
  (
    cd "${ROOT_DIR}"
    export MAX_CHARS REQUEST_TIMEOUT_SEC WATCHDOG_STALL_SEC WATCHDOG_SEMANTIC_STALL_SEC WATCHDOG_POLL_SEC WATCHDOG_LOG_INTERVAL_SEC RETRY_SLEEP_SEC CHATGPT_WEB_MAX_ATTEMPTS
    ./scripts/run_chatgpt_web_job.sh "${input_file}" "${output_file}" "${work_dir}"
  )
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') done: ${stem} ====="
}

run_one "사회보험법_OX_통합본_2026최종검수"
run_one "노동법_OX_통합본_2026최종검수"
run_one "민법_OX_통합본_2026최종검수"
run_one "경영학_OX_통합본_2026최종검수"
