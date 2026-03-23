#!/bin/zsh

set -u

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <input-file> [<input-file> ...]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

VOICE="${VOICE:-cove}"
SHUTDOWN_ON_SUCCESS="${SHUTDOWN_ON_SUCCESS:-0}"

derive_paths() {
  local input_file="$1"
  local input_dir="${input_file:h}"
  local input_stem="${input_file:t:r}"
  local output_dir
  local output_file
  local work_dir

  if [[ "${input_dir:t}" == "audiobooks" ]]; then
    output_dir="${input_dir}"
  else
    output_dir="${input_dir}/audiobooks"
  fi

  output_file="${output_dir}/${input_stem}_audiobook_chatgpt_web_${VOICE}.m4a"
  work_dir="${output_file:r}_work"

  printf '%s\n%s\n' "${output_file}" "${work_dir}"
}

cd "${ROOT_DIR}" || exit 1

task_index=0
task_total=$#

for input_file in "$@"; do
  task_index=$((task_index + 1))
  if [[ ! -f "${input_file}" ]]; then
    echo "[${task_index}/${task_total}] missing input file: ${input_file}" >&2
    exit 1
  fi

  derived_paths=("${(@f)$(derive_paths "${input_file}")}")
  output_file="${derived_paths[1]}"
  work_dir="${derived_paths[2]}"

  echo "[${task_index}/${task_total}] queue start"
  echo "input: ${input_file}"
  echo "output: ${output_file}"
  echo "work: ${work_dir}"

  SHUTDOWN_ON_SUCCESS=0 \
  VOICE="${VOICE}" \
  "${SCRIPT_DIR}/run_chatgpt_web_job.sh" \
    "${input_file}" \
    "${output_file}" \
    "${work_dir}" || exit $?

  echo "[${task_index}/${task_total}] queue complete"
done

if [[ "${SHUTDOWN_ON_SUCCESS}" == "1" ]]; then
  osascript -e 'tell application "System Events" to shut down'
fi
