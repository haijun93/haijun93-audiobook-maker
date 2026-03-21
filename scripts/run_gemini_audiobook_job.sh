#!/bin/zsh
set -euo pipefail

if [[ $# -lt 2 || $# -gt 4 ]]; then
  echo "usage: $0 <input-file> <output-file> [max-chars-per-chunk] [key-file]" >&2
  echo "default provider is gemini_web. set PROVIDER=gemini to use the API fallback." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INPUT_FILE="$1"
OUTPUT_FILE="$2"
PROVIDER="${PROVIDER:-gemini_web}"
KEY_FILE="${4:-/tmp/phm_gemini_keys_comma.txt}"
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-600}"
GEMINI_WEB_VISIBLE="${GEMINI_WEB_VISIBLE:-0}"

if [[ "${PROVIDER}" == "gemini_web" ]]; then
  MAX_CHARS="${3:-900}"
elif [[ "${PROVIDER}" == "gemini" ]]; then
  MAX_CHARS="${3:-12000}"
else
  echo "unsupported PROVIDER: ${PROVIDER} (expected gemini_web or gemini)" >&2
  exit 1
fi

VISIBLE_ARGS=()
if [[ "${GEMINI_WEB_VISIBLE}" == "1" && "${PROVIDER}" == "gemini_web" ]]; then
  VISIBLE_ARGS+=(--gemini-web-visible)
fi

if [[ "${PROVIDER}" == "gemini" ]]; then
  if [[ ! -f "$KEY_FILE" ]]; then
    echo "missing key file: $KEY_FILE" >&2
    exit 1
  fi
  export GEMINI_API_KEY="$(<"$KEY_FILE")"
fi

cd "$ROOT_DIR"
python3 audiobook_maker.py \
  --provider "$PROVIDER" \
  --input-file "$INPUT_FILE" \
  --output-file "$OUTPUT_FILE" \
  --max-chars-per-chunk "$MAX_CHARS" \
  --request-timeout-sec "$REQUEST_TIMEOUT_SEC" \
  --keep-workdir \
  "${VISIBLE_ARGS[@]}"
