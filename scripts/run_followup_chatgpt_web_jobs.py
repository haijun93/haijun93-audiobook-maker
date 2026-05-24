#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Job:
    input_file: str
    output_file: str
    work_dir: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wait for one audiobook job to finish, then run follow-up ChatGPT web jobs sequentially.",
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--wait-input-file", required=True)
    parser.add_argument("--wait-output-file", type=Path, required=True)
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--poll-sec", type=int, default=60)
    parser.add_argument(
        "--job",
        action="append",
        nargs=3,
        metavar=("INPUT_FILE", "OUTPUT_FILE", "WORK_DIR"),
        default=[],
        help="Follow-up job triple to run after the wait target completes.",
    )
    return parser


def log_line(log_file: Path, message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def command_output() -> str:
    return subprocess.run(
        ["ps", "-Ao", "command"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout


def target_still_running(wait_input_file: str) -> bool:
    ps_output = command_output()
    return wait_input_file in ps_output and "run_chatgpt_web_job.sh" in ps_output


def wait_for_completion(wait_input_file: str, wait_output_file: Path, log_file: Path, poll_sec: int) -> None:
    log_line(log_file, "queue started")
    while True:
        if wait_output_file.exists() and not target_still_running(wait_input_file):
            log_line(log_file, f"detected completion: {wait_output_file}")
            return
        time.sleep(poll_sec)


def run_job(repo_root: Path, job: Job, log_file: Path) -> None:
    log_line(log_file, f"starting follow-up job: {job.input_file}")
    subprocess.run(
        [
            "./scripts/run_chatgpt_web_job.sh",
            job.input_file,
            job.output_file,
            job.work_dir,
        ],
        cwd=repo_root,
        check=True,
    )
    log_line(log_file, f"completed follow-up job: {job.output_file}")


def main() -> int:
    args = build_parser().parse_args()
    jobs = [Job(*job) for job in args.job]
    wait_for_completion(args.wait_input_file, args.wait_output_file, args.log_file, args.poll_sec)
    for job in jobs:
        run_job(args.repo_root, job, args.log_file)
    log_line(args.log_file, "all follow-up jobs completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
