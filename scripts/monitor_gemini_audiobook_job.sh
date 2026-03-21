#!/bin/zsh
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <input-file> <output-file> [session-name] [max-chars-per-chunk] [key-file] [check-interval-sec] [watchdog-log] [job-log]" >&2
  exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"
SESSION_NAME="${3:-phm_audiobook}"
PROVIDER="${PROVIDER:-gemini_web}"
MAX_CHARS="${4:-}"
KEY_FILE="${5:-/tmp/phm_gemini_keys_comma.txt}"
CHECK_INTERVAL_SEC="${6:-60}"
WATCHDOG_LOG="${7:-/tmp/${SESSION_NAME}_watchdog.log}"
JOB_LOG="${8:-/tmp/${SESSION_NAME}.log}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNNER_SCRIPT="$ROOT_DIR/scripts/run_gemini_audiobook_job.sh"

if [[ -z "$MAX_CHARS" ]]; then
  if [[ "$PROVIDER" == "gemini_web" ]]; then
    MAX_CHARS="900"
  else
    MAX_CHARS="12000"
  fi
fi

timestamp() {
  date '+%Y-%m-%d %H:%M:%S %Z'
}

log_line() {
  local message="$1"
  print -r -- "[$(timestamp)] $message" | tee -a "$WATCHDOG_LOG" >&2
}

session_count() {
  local listing
  listing="$(screen -ls 2>/dev/null || true)"
  print -r -- "$listing" | rg -c "[[:space:]][0-9]+\\.${SESSION_NAME}[[:space:]]" || true
}

session_running() {
  [[ "$(session_count)" -gt 0 ]]
}

work_dir_for_output() {
  python3 - "$OUTPUT_FILE" <<'PY'
from pathlib import Path
import sys
output = Path(sys.argv[1]).expanduser()
print(output.with_name(f"{output.stem}_work"))
PY
}

audio_count() {
  local work_dir
  work_dir="$(work_dir_for_output)"
  python3 - "$work_dir" "$PROVIDER" <<'PY'
from pathlib import Path
import sys
work = Path(sys.argv[1])
provider = sys.argv[2]
pattern = "*.ogg" if provider == "gemini_web" else "*.wav"
if not work.exists():
    print(0)
else:
    print(sum(1 for path in work.glob(pattern) if path.is_file()))
PY
}

start_job() {
  if session_running; then
    log_line "session already active; skipping restart"
    return 0
  fi
  if [[ "$PROVIDER" == "gemini" && ! -f "$KEY_FILE" ]]; then
    log_line "key file missing: $KEY_FILE"
    return 1
  fi
  mkdir -p "$(dirname "$WATCHDOG_LOG")" "$(dirname "$JOB_LOG")"
  : >> "$WATCHDOG_LOG"
  : >> "$JOB_LOG"
  local launch_cmd
  launch_cmd="cd ${(q)ROOT_DIR} && PROVIDER=${(q)PROVIDER} ${(q)RUNNER_SCRIPT} ${(q)INPUT_FILE} ${(q)OUTPUT_FILE} ${(q)MAX_CHARS} ${(q)KEY_FILE} >> ${(q)JOB_LOG} 2>&1"
  log_line "starting session ${SESSION_NAME} (provider=${PROVIDER}, audio_count=$(audio_count))"
  screen -dmS "$SESSION_NAME" zsh -lc "$launch_cmd"
}

if [[ ! -f "$RUNNER_SCRIPT" ]]; then
  echo "missing runner script: $RUNNER_SCRIPT" >&2
  exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "missing input file: $INPUT_FILE" >&2
  exit 1
fi

mkdir -p "$(dirname "$WATCHDOG_LOG")"
: >> "$WATCHDOG_LOG"

log_line "watchdog started for session ${SESSION_NAME} (provider=${PROVIDER})"

while true; do
  if [[ -s "$OUTPUT_FILE" ]]; then
    log_line "output detected, watchdog exiting: $OUTPUT_FILE"
    exit 0
  fi

  current_audio_count="$(audio_count)"
  current_session_count="$(session_count)"

  if [[ "$current_session_count" -gt 0 ]]; then
    if [[ "$current_session_count" -gt 1 ]]; then
      log_line "warning: duplicate sessions detected ($current_session_count)"
    fi
    log_line "session active (sessions=$current_session_count, audio_count=$current_audio_count)"
  else
    log_line "session not running; attempting restart (audio_count=$current_audio_count)"
    if start_job; then
      :
    fi
  fi

  sleep "$CHECK_INTERVAL_SEC"
done
