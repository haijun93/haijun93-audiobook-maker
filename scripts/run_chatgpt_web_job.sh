#!/bin/zsh

set -u

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 <input-file> <output-file> [work-dir]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INPUT_FILE="$1"
OUTPUT_FILE="$2"
WORK_DIR="${3:-${OUTPUT_FILE%.*}_work}"
VOICE="${VOICE:-cove}"
MAX_CHARS="${MAX_CHARS:-1800}"
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-600}"
RETRY_SLEEP_SEC="${RETRY_SLEEP_SEC:-15}"
SHUTDOWN_ON_SUCCESS="${SHUTDOWN_ON_SUCCESS:-0}"
CHATGPT_WEB_VISIBLE="${CHATGPT_WEB_VISIBLE:-0}"
CHATGPT_WEB_READING_INSTRUCTIONS_FILE="${CHATGPT_WEB_READING_INSTRUCTIONS_FILE:-}"

VISIBLE_ARGS=()
if [[ "${CHATGPT_WEB_VISIBLE}" == "1" ]]; then
  VISIBLE_ARGS+=(--chatgpt-web-visible)
fi

EXTRA_ARGS=()
if [[ -n "${CHATGPT_WEB_READING_INSTRUCTIONS_FILE}" ]]; then
  if [[ ! -f "${CHATGPT_WEB_READING_INSTRUCTIONS_FILE}" ]]; then
    echo "missing reading instructions file: ${CHATGPT_WEB_READING_INSTRUCTIONS_FILE}" >&2
    exit 1
  fi
  CHATGPT_WEB_READING_INSTRUCTIONS="$(<"${CHATGPT_WEB_READING_INSTRUCTIONS_FILE}")"
  EXTRA_ARGS+=(--chatgpt-web-reading-instructions "${CHATGPT_WEB_READING_INSTRUCTIONS}")
fi

cd "${ROOT_DIR}" || exit 1

while true; do
  date "+%Y-%m-%d %H:%M:%S start/resume"
  python3 audiobook_maker.py \
    --provider chatgpt_web \
    --input-file "${INPUT_FILE}" \
    --output-file "${OUTPUT_FILE}" \
    --work-dir "${WORK_DIR}" \
    --keep-workdir \
    --voice "${VOICE}" \
    --max-chars-per-chunk "${MAX_CHARS}" \
    --request-timeout-sec "${REQUEST_TIMEOUT_SEC}" \
    "${EXTRA_ARGS[@]}" \
    "${VISIBLE_ARGS[@]}"
  exit_code=$?
  date "+%Y-%m-%d %H:%M:%S exit ${exit_code}"
  if [[ "${exit_code}" == "0" ]]; then
    break
  fi
  sleep "${RETRY_SLEEP_SEC}"
done

if [[ "${SHUTDOWN_ON_SUCCESS}" == "1" ]]; then
  osascript -e 'tell application "System Events" to shut down'
fi
