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

ANALYSIS_MODE="${ANALYSIS_MODE:-basic}"
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-900}"
MAX_CHARS="${MAX_CHARS:-6000}"
CHATGPT_WEB_VISIBLE="${CHATGPT_WEB_VISIBLE:-0}"
CLAUDE_WEB_VISIBLE="${CLAUDE_WEB_VISIBLE:-0}"
GEMINI_WEB_VISIBLE="${GEMINI_WEB_VISIBLE:-0}"
CHATGPT_WEB_MAX_ATTEMPTS="${CHATGPT_WEB_MAX_ATTEMPTS:-8}"
CLAUDE_WEB_MAX_ATTEMPTS="${CLAUDE_WEB_MAX_ATTEMPTS:-5}"
GEMINI_WEB_MAX_ATTEMPTS="${GEMINI_WEB_MAX_ATTEMPTS:-3}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-${WORK_DIR}/multi_web_document_analysis_heartbeat.json}"
ANALYSIS_INSTRUCTIONS_FILE="${ANALYSIS_INSTRUCTIONS_FILE:-}"
FINAL_FORMAT="${FINAL_FORMAT:-markdown}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APPLY_RESULTS_AFTER_ANALYSIS="${APPLY_RESULTS_AFTER_ANALYSIS:-}"
NO_PDF_AFTER_APPLY="${NO_PDF_AFTER_APPLY:-0}"
APPLY_SECTION_TITLE="${APPLY_SECTION_TITLE:-문서심화분석 반영}"

mkdir -p "${WORK_DIR}"

if [[ -z "${APPLY_RESULTS_AFTER_ANALYSIS}" ]]; then
  if [[ "${ANALYSIS_MODE}" == "deep" && "${INPUT_FILE:e:l}" == "docx" ]]; then
    APPLY_RESULTS_AFTER_ANALYSIS="1"
  else
    APPLY_RESULTS_AFTER_ANALYSIS="0"
  fi
fi

ARGS=(
  "${ROOT_DIR}/scripts/analyze_document_with_web_services.py"
  --input-file "${INPUT_FILE}"
  --output-file "${OUTPUT_FILE}"
  --work-dir "${WORK_DIR}"
  --analysis-mode "${ANALYSIS_MODE}"
  --request-timeout-sec "${REQUEST_TIMEOUT_SEC}"
  --max-chars-per-chunk "${MAX_CHARS}"
  --chatgpt-web-max-attempts "${CHATGPT_WEB_MAX_ATTEMPTS}"
  --claude-web-max-attempts "${CLAUDE_WEB_MAX_ATTEMPTS}"
  --gemini-web-max-attempts "${GEMINI_WEB_MAX_ATTEMPTS}"
  --heartbeat-file "${HEARTBEAT_FILE}"
  --final-format "${FINAL_FORMAT}"
)

if [[ "${APPLY_RESULTS_AFTER_ANALYSIS}" == "1" ]]; then
  ARGS+=(--apply-results-to-docx-pdf --apply-section-title "${APPLY_SECTION_TITLE}")
  if [[ "${NO_PDF_AFTER_APPLY}" == "1" ]]; then
    ARGS+=(--no-pdf-after-apply)
  fi
fi

if [[ "${CHATGPT_WEB_VISIBLE}" == "1" ]]; then
  ARGS+=(--chatgpt-web-visible)
fi
if [[ "${CLAUDE_WEB_VISIBLE}" == "1" ]]; then
  ARGS+=(--claude-web-visible)
fi
if [[ "${GEMINI_WEB_VISIBLE}" == "1" ]]; then
  ARGS+=(--gemini-web-visible)
fi
if [[ -n "${ANALYSIS_INSTRUCTIONS_FILE}" ]]; then
  ARGS+=(--analysis-instructions-file "${ANALYSIS_INSTRUCTIONS_FILE}")
fi

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" "${ARGS[@]}"
