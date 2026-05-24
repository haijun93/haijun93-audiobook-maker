#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_STEMS = [
    "사회보험법_OX_통합본_2026최종검수",
    "노동법_OX_통합본_2026최종검수",
    "민법_OX_통합본_2026최종검수",
    "경영학_OX_통합본_2026최종검수",
]


@dataclass
class Job:
    stem: str
    input_file: Path
    output_file: Path
    work_dir: Path
    heartbeat_file: Path


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def count_files(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.glob(pattern))


def is_pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def child_pids(pid: int) -> list[int]:
    try:
        proc = subprocess.run(
            ["pgrep", "-P", str(pid)],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    pids: list[int] = []
    for raw in proc.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            pids.append(int(raw))
        except ValueError:
            continue
    return pids


def process_tree(root_pid: int) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []

    def walk(pid: int) -> None:
        if pid in seen:
            return
        seen.add(pid)
        ordered.append(pid)
        for child in child_pids(pid):
            walk(child)

    walk(root_pid)
    return ordered


def kill_tree(root_pid: int, grace_sec: int) -> None:
    pids = process_tree(root_pid)
    if not pids:
        return
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + grace_sec
    while time.time() < deadline:
        if not any(is_pid_alive(pid) for pid in pids):
            return
        time.sleep(1)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def build_jobs(input_dir: Path, output_dir: Path, stems: list[str]) -> list[Job]:
    jobs: list[Job] = []
    for stem in stems:
        work_dir = output_dir / f"{stem}_audiobook_chatgpt_web_cove_work"
        jobs.append(
            Job(
                stem=stem,
                input_file=input_dir / f"{stem}.docx",
                output_file=output_dir / f"{stem}_audiobook_chatgpt_web_cove.m4a",
                work_dir=work_dir,
                heartbeat_file=work_dir / "chatgpt_web_job_heartbeat.json",
            )
        )
    return jobs


def first_incomplete_job(jobs: list[Job]) -> Job | None:
    for job in jobs:
        if not job.output_file.exists():
            return job
    return None


def job_status(job: Job, now_epoch: int) -> dict[str, Any]:
    heartbeat = read_json(job.heartbeat_file)
    heartbeat_epoch = int(float(heartbeat.get("timestamp", 0) or 0))
    heartbeat_age = None
    if heartbeat_epoch > 0:
        heartbeat_age = max(0, now_epoch - heartbeat_epoch)
    return {
        "stem": job.stem,
        "input_file": str(job.input_file),
        "output_file": str(job.output_file),
        "output_exists": job.output_file.exists(),
        "work_dir": str(job.work_dir),
        "heartbeat_file": str(job.heartbeat_file),
        "audio_count": count_files(job.work_dir, "*.mp3"),
        "response_count": count_files(job.work_dir, "*_response.txt"),
        "prompt_count": count_files(job.work_dir, "*_prompt.txt"),
        "heartbeat_age_sec": heartbeat_age,
        "heartbeat": heartbeat,
    }


def semantic_marker(status: dict[str, Any]) -> tuple[str, int, str, str, str, Any]:
    heartbeat = status.get("heartbeat") or {}
    return (
        status["stem"],
        int(status.get("audio_count", 0) or 0),
        str(heartbeat.get("label") or "?"),
        str(heartbeat.get("section_prefix") or "?"),
        str(heartbeat.get("stage") or "?"),
        heartbeat.get("attempt") or 0,
    )


def launch_batch(
    batch_script: Path,
    root_dir: Path,
    log_path: Path,
    env_overrides: dict[str, str],
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.update(env_overrides)
    log_handle = log_path.open("a", encoding="utf-8", buffering=1)
    return subprocess.Popen(
        ["/bin/zsh", str(batch_script)],
        cwd=str(root_dir),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def write_status_file(
    status_path: Path,
    batch_pid: int | None,
    jobs: list[dict[str, Any]],
    active_stem: str | None,
    last_progress_iso: str,
) -> None:
    payload = {
        "timestamp": time.time(),
        "iso_time": now_iso(),
        "batch_pid": batch_pid,
        "batch_alive": is_pid_alive(batch_pid),
        "active_stem": active_stem,
        "last_progress_time": last_progress_iso,
        "jobs": jobs,
    }
    status_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-dir", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument(
        "--input-dir",
        default="/Users/hyeokjunkong/Desktop/1차 시험/#STD/#Here",
    )
    parser.add_argument(
        "--output-dir",
        default="/Users/hyeokjunkong/Desktop/1차 시험/#STD/오디오북",
    )
    parser.add_argument(
        "--batch-script",
        default=str(Path(__file__).resolve().with_name("run_chatgpt_web_ox_batch.sh")),
    )
    parser.add_argument("--batch-pid", type=int, default=0)
    parser.add_argument("--poll-sec", type=int, default=60)
    parser.add_argument("--stalled-sec", type=int, default=1800)
    parser.add_argument("--kill-grace-sec", type=int, default=15)
    parser.add_argument("--progress-log-sec", type=int, default=300)
    parser.add_argument(
        "--log-file",
        default="/Users/hyeokjunkong/Desktop/1차 시험/#STD/오디오북/ox_audiobook_batch_supervisor.log",
    )
    parser.add_argument(
        "--status-file",
        default="/Users/hyeokjunkong/Desktop/1차 시험/#STD/오디오북/ox_audiobook_batch_status.json",
    )
    parser.add_argument(
        "--stems",
        nargs="*",
        default=DEFAULT_STEMS,
    )
    parser.add_argument("--watchdog-stall-sec", type=int, default=1200)
    parser.add_argument("--watchdog-semantic-stall-sec", type=int, default=900)
    parser.add_argument("--watchdog-poll-sec", type=int, default=15)
    parser.add_argument("--watchdog-log-interval-sec", type=int, default=300)
    parser.add_argument("--max-chars", type=int, default=1800)
    parser.add_argument("--request-timeout-sec", type=int, default=600)
    parser.add_argument("--retry-sleep-sec", type=int, default=20)
    parser.add_argument("--chatgpt-web-max-attempts", type=int, default=8)
    args = parser.parse_args()

    root_dir = Path(args.root_dir)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    batch_script = Path(args.batch_script)
    log_path = Path(args.log_file)
    status_path = Path(args.status_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)

    jobs = build_jobs(input_dir, output_dir, args.stems)
    batch_pid: int | None = args.batch_pid or None
    launched_proc: subprocess.Popen[str] | None = None
    last_marker: tuple[str, int, str, str, str, Any] | None = None
    last_progress_epoch = time.time()
    last_progress_iso = now_iso()
    last_log_epoch = 0.0

    def log(message: str) -> None:
        line = f"{now_iso()} [supervisor] {message}"
        print(line)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{line}\n")

    log("start")
    log(f"batch_pid={batch_pid or 0} stems={', '.join(args.stems)}")

    while True:
        now_epoch = int(time.time())
        incomplete_job = first_incomplete_job(jobs)
        status_rows = [job_status(job, now_epoch) for job in jobs]
        active_stem = incomplete_job.stem if incomplete_job else None
        active_status = next((row for row in status_rows if row["stem"] == active_stem), None)

        if incomplete_job is None:
            write_status_file(status_path, batch_pid, status_rows, None, last_progress_iso)
            log("all jobs completed")
            return 0

        marker = semantic_marker(active_status) if active_status else None
        if marker != last_marker:
            last_marker = marker
            last_progress_epoch = time.time()
            last_progress_iso = now_iso()
            if active_status:
                heartbeat = active_status["heartbeat"] or {}
                log(
                    "progress "
                    f"stem={active_status['stem']} mp3={active_status['audio_count']} "
                    f"label={heartbeat.get('label', '?')} section={heartbeat.get('section_prefix', '?')} "
                    f"attempt={heartbeat.get('attempt', 0)} stage={heartbeat.get('stage', '?')}"
                )

        batch_alive = is_pid_alive(batch_pid)
        if batch_alive and args.stalled_sec > 0 and time.time() - last_progress_epoch >= args.stalled_sec:
            log(
                "semantic stall detected "
                f"for {args.stalled_sec}s on {active_stem}; restarting batch pid {batch_pid}"
            )
            kill_tree(batch_pid, args.kill_grace_sec)
            batch_pid = None
            batch_alive = False
            last_progress_epoch = time.time()
            last_progress_iso = now_iso()

        if not batch_alive:
            env_overrides = {
                "MAX_CHARS": str(args.max_chars),
                "REQUEST_TIMEOUT_SEC": str(args.request_timeout_sec),
                "RETRY_SLEEP_SEC": str(args.retry_sleep_sec),
                "CHATGPT_WEB_MAX_ATTEMPTS": str(args.chatgpt_web_max_attempts),
                "WATCHDOG_STALL_SEC": str(args.watchdog_stall_sec),
                "WATCHDOG_SEMANTIC_STALL_SEC": str(args.watchdog_semantic_stall_sec),
                "WATCHDOG_POLL_SEC": str(args.watchdog_poll_sec),
                "WATCHDOG_LOG_INTERVAL_SEC": str(args.watchdog_log_interval_sec),
            }
            launched_proc = launch_batch(batch_script, root_dir, log_path, env_overrides)
            batch_pid = launched_proc.pid
            last_progress_epoch = time.time()
            last_progress_iso = now_iso()
            log(f"launched batch pid={batch_pid}")
            time.sleep(5)
            continue

        if args.progress_log_sec > 0 and time.time() - last_log_epoch >= args.progress_log_sec:
            last_log_epoch = time.time()
            if active_status:
                heartbeat = active_status["heartbeat"] or {}
                log(
                    "heartbeat "
                    f"stem={active_status['stem']} mp3={active_status['audio_count']} "
                    f"label={heartbeat.get('label', '?')} section={heartbeat.get('section_prefix', '?')} "
                    f"attempt={heartbeat.get('attempt', 0)} stage={heartbeat.get('stage', '?')} "
                    f"age={active_status.get('heartbeat_age_sec')}"
                )

        write_status_file(status_path, batch_pid, status_rows, active_stem, last_progress_iso)
        time.sleep(max(5, args.poll_sec))


if __name__ == "__main__":
    sys.exit(main())
