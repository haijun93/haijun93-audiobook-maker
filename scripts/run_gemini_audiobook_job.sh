#!/bin/zsh
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <input-file> <output-file> [max-chars-per-chunk] [key-file]" >&2
  exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"
MAX_CHARS="${3:-12000}"
KEY_FILE="${4:-/tmp/phm_gemini_keys_comma.txt}"

if [[ ! -f "$KEY_FILE" ]]; then
  echo "missing key file: $KEY_FILE" >&2
  exit 1
fi

ROOT_DIR="/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker"
export GEMINI_API_KEY="$(<"$KEY_FILE")"

cd "$ROOT_DIR"
python3 audiobook_maker.py \
  --provider gemini \
  --input-file "$INPUT_FILE" \
  --output-file "$OUTPUT_FILE" \
  --max-chars-per-chunk "$MAX_CHARS" \
  --keep-workdir
