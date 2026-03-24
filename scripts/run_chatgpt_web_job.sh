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
VOICE="${VOICE:-cove}"
MAX_CHARS="${MAX_CHARS:-1800}"
REQUEST_TIMEOUT_SEC="${REQUEST_TIMEOUT_SEC:-600}"
RETRY_SLEEP_SEC="${RETRY_SLEEP_SEC:-15}"
SHUTDOWN_ON_SUCCESS="${SHUTDOWN_ON_SUCCESS:-0}"
CHATGPT_WEB_VISIBLE="${CHATGPT_WEB_VISIBLE:-0}"
CHATGPT_WEB_READING_INSTRUCTIONS_FILE="${CHATGPT_WEB_READING_INSTRUCTIONS_FILE:-}"
WATCHDOG_STALL_SEC="${WATCHDOG_STALL_SEC:-120}"
WATCHDOG_POLL_SEC="${WATCHDOG_POLL_SEC:-15}"
WATCHDOG_KILL_GRACE_SEC="${WATCHDOG_KILL_GRACE_SEC:-10}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
AUDIOBOOK_MAKER_SCRIPT="${AUDIOBOOK_MAKER_SCRIPT:-audiobook_maker.py}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-${WORK_DIR}/chatgpt_web_job_heartbeat.json}"
PARTIAL_OUTPUT_FILE="${OUTPUT_FILE%.*}.partial.${OUTPUT_FILE##*.}"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log_line() {
  print -r -- "$(timestamp) $*"
}

file_mtime_epoch() {
  local path="$1"
  if [[ ! -e "${path}" ]]; then
    print 0
    return
  fi
  stat -f "%m" "${path}" 2>/dev/null || print 0
}

current_progress_epoch() {
  local newest=0
  local path
  local mtime
  local -a candidates

  candidates=(
    "${HEARTBEAT_FILE}"
    "${OUTPUT_FILE}"
    "${PARTIAL_OUTPUT_FILE}"
    "${WORK_DIR}"/*.mp3(N)
    "${WORK_DIR}"/*.partial.*(N)
    "${WORK_DIR}"/*_response.txt(N)
    "${WORK_DIR}"/*_chatgpt_web.json(N)
    "${WORK_DIR}"/ffmpeg_concat.log(N)
  )

  for path in "${candidates[@]}"; do
    [[ -e "${path}" ]] || continue
    mtime="$(file_mtime_epoch "${path}")"
    if (( mtime > newest )); then
      newest="${mtime}"
    fi
  done

  print "${newest}"
}

collect_descendants() {
  local parent_pid="$1"
  local child_pid
  local -a child_pids

  child_pids=(${(f)"$(pgrep -P "${parent_pid}" 2>/dev/null || true)"})
  for child_pid in "${child_pids[@]}"; do
    [[ -n "${child_pid}" ]] || continue
    print -r -- "${child_pid}"
    collect_descendants "${child_pid}"
  done
}

terminate_process_tree() {
  local root_pid="$1"
  local signal_name="${2:-TERM}"
  local pid
  local -a raw_pids
  local -a unique_pids
  typeset -A seen_pids

  raw_pids=("${root_pid}" ${(f)"$(collect_descendants "${root_pid}")"})
  for pid in "${raw_pids[@]}"; do
    [[ -n "${pid}" ]] || continue
    if [[ -n "${seen_pids[$pid]-}" ]]; then
      continue
    fi
    seen_pids[$pid]=1
    unique_pids+=("${pid}")
  done

  if (( ${#unique_pids[@]} > 0 )); then
    kill "-${signal_name}" "${unique_pids[@]}" 2>/dev/null || true
  fi
}

kill_process_tree() {
  local root_pid="$1"

  terminate_process_tree "${root_pid}" TERM
  sleep "${WATCHDOG_KILL_GRACE_SEC}"
  if kill -0 "${root_pid}" 2>/dev/null; then
    terminate_process_tree "${root_pid}" KILL
  fi
}

log_heartbeat_snapshot() {
  if [[ ! -f "${HEARTBEAT_FILE}" ]]; then
    return
  fi
  local snapshot
  snapshot="$(tr '\n' ' ' < "${HEARTBEAT_FILE}" | cut -c1-600)"
  log_line "watchdog heartbeat: ${snapshot}"
}

reset_wrapper_heartbeat() {
  local now_epoch
  local now_text

  mkdir -p "${WORK_DIR}"
  now_epoch="$(date +%s)"
  now_text="$(timestamp)"
  cat > "${HEARTBEAT_FILE}" <<EOF
{
  "timestamp": ${now_epoch},
  "iso_time": "${now_text}",
  "pid": $$,
  "stage": "wrapper_start",
  "detail": "watchdog wrapper initialized"
}
EOF
}

monitor_child_progress() {
  local child_pid="$1"
  local last_progress_epoch
  local observed_epoch
  local now_epoch

  if (( WATCHDOG_STALL_SEC <= 0 )); then
    while kill -0 "${child_pid}" 2>/dev/null; do
      sleep "${WATCHDOG_POLL_SEC}"
    done
    return 0
  fi

  last_progress_epoch="$(current_progress_epoch)"
  if (( last_progress_epoch <= 0 )); then
    last_progress_epoch="$(date +%s)"
  fi

  while kill -0 "${child_pid}" 2>/dev/null; do
    observed_epoch="$(current_progress_epoch)"
    if (( observed_epoch > last_progress_epoch )); then
      last_progress_epoch="${observed_epoch}"
    fi

    now_epoch="$(date +%s)"
    if (( now_epoch - last_progress_epoch >= WATCHDOG_STALL_SEC )); then
      log_line "watchdog: no progress for ${WATCHDOG_STALL_SEC}s; restarting pid ${child_pid}"
      log_heartbeat_snapshot
      kill_process_tree "${child_pid}"
      return 124
    fi

    sleep "${WATCHDOG_POLL_SEC}"
  done

  return 0
}

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

child_pid=""
cleanup() {
  if [[ -n "${child_pid}" ]] && kill -0 "${child_pid}" 2>/dev/null; then
    kill_process_tree "${child_pid}"
  fi
}
trap cleanup EXIT INT TERM

cd "${ROOT_DIR}" || exit 1
mkdir -p "${WORK_DIR}"

while true; do
  reset_wrapper_heartbeat
  log_line "start/resume"
  log_line "watchdog: stall=${WATCHDOG_STALL_SEC}s poll=${WATCHDOG_POLL_SEC}s heartbeat=${HEARTBEAT_FILE}"

  "${PYTHON_BIN}" -u "${AUDIOBOOK_MAKER_SCRIPT}" \
    --provider chatgpt_web \
    --input-file "${INPUT_FILE}" \
    --output-file "${OUTPUT_FILE}" \
    --work-dir "${WORK_DIR}" \
    --keep-workdir \
    --voice "${VOICE}" \
    --max-chars-per-chunk "${MAX_CHARS}" \
    --request-timeout-sec "${REQUEST_TIMEOUT_SEC}" \
    --heartbeat-file "${HEARTBEAT_FILE}" \
    "${EXTRA_ARGS[@]}" \
    "${VISIBLE_ARGS[@]}" &
  child_pid=$!

  monitor_child_progress "${child_pid}"
  monitor_status=$?
  wait "${child_pid}"
  exit_code=$?
  child_pid=""

  if [[ "${monitor_status}" == "124" ]]; then
    exit_code=124
  fi

  log_line "exit ${exit_code}"
  if [[ "${exit_code}" == "0" ]]; then
    break
  fi
  sleep "${RETRY_SLEEP_SEC}"
done

if [[ "${SHUTDOWN_ON_SUCCESS}" == "1" ]]; then
  osascript -e 'tell application "System Events" to shut down'
fi
