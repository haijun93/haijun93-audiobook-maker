#!/bin/zsh

set -u
setopt pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 <input-file> <output-file> [work-dir]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INPUT_FILE="$1"
OUTPUT_FILE="$2"
WORK_DIR="${3:-${OUTPUT_FILE%.*}_work}"

CHATGPT_WEB_VISIBLE="${CHATGPT_WEB_VISIBLE:-0}"
CHATGPT_WEB_MAX_ATTEMPTS="${CHATGPT_WEB_MAX_ATTEMPTS:-8}"
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-900}"
MAX_CHARS="${MAX_CHARS:-6000}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-${WORK_DIR}/chatgpt_web_document_analysis_heartbeat.json}"
ANALYSIS_INSTRUCTIONS_FILE="${ANALYSIS_INSTRUCTIONS_FILE:-}"
FINAL_FORMAT="${FINAL_FORMAT:-markdown}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "${WORK_DIR}"

ARGS=(
  "${ROOT_DIR}/scripts/analyze_document_with_chatgpt_web.py"
  --input-file "${INPUT_FILE}"
  --output-file "${OUTPUT_FILE}"
  --work-dir "${WORK_DIR}"
  --request-timeout-sec "${REQUEST_TIMEOUT_SEC}"
  --max-chars-per-chunk "${MAX_CHARS}"
  --chatgpt-web-max-attempts "${CHATGPT_WEB_MAX_ATTEMPTS}"
  --heartbeat-file "${HEARTBEAT_FILE}"
  --final-format "${FINAL_FORMAT}"
)

if [[ "${CHATGPT_WEB_VISIBLE}" == "1" ]]; then
  ARGS+=(--chatgpt-web-visible)
fi

if [[ -n "${ANALYSIS_INSTRUCTIONS_FILE}" ]]; then
  ARGS+=(--analysis-instructions-file "${ANALYSIS_INSTRUCTIONS_FILE}")
fi

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" "${ARGS[@]}"
