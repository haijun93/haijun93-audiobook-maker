#!/usr/bin/env python3
"""Run and manage the durable multi-account translation scheduler."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
from pathlib import Path

from scripts.atomic_io import atomic_output_path
from webui.continuous_scheduler import (
    ContinuousTranslationScheduler,
    SchedulerConfigurationError,
    load_json_object,
    validate_config,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / ".work" / "continuous_scheduler" / "config.json"
DEFAULT_STATE_DIR = ROOT / ".work" / "continuous_scheduler"
DEFAULT_LABEL = "com.haijun.audiobook.continuous-translation"


def install_launch_agent(*, config: Path, state_dir: Path, label: str) -> Path:
    python = Path(os.sys.executable).absolute()
    launch_agents = Path.home() / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents / f"{label}.plist"
    payload = {
        "Label": label,
        "ProgramArguments": [
            str(python),
            "-m",
            "scripts.run_continuous_translation_scheduler",
            "run",
            "--config",
            str(config.resolve()),
            "--state-dir",
            str(state_dir.resolve()),
        ],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "ThrottleInterval": 10,
        "StandardOutPath": str(state_dir / "scheduler.stdout.log"),
        "StandardErrorPath": str(state_dir / "scheduler.stderr.log"),
        "EnvironmentVariables": {
            "PATH": f"{python.parent}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "PYTHONUNBUFFERED": "1",
        },
    }
    with atomic_output_path(plist_path) as temporary:
        with temporary.open("wb") as handle:
            plistlib.dump(payload, handle, sort_keys=True)

    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(plist_path)], capture_output=True, check=False)
    result = subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "launchctl bootstrap failed")
    subprocess.run(["launchctl", "enable", f"{domain}/{label}"], check=False)
    return plist_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the scheduler until it receives SIGTERM")
    run_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    run_parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)

    validate_parser = subparsers.add_parser("validate", help="validate a scheduler config")
    validate_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)

    status_parser = subparsers.add_parser("status", help="print the latest scheduler status")
    status_parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)

    install_parser = subparsers.add_parser("install-launch-agent", help="install and start a macOS LaunchAgent")
    install_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    install_parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    install_parser.add_argument("--label", default=DEFAULT_LABEL)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "run":
        ContinuousTranslationScheduler(args.config, state_dir=args.state_dir).run()
        return 0
    if args.command == "validate":
        payload = load_json_object(args.config.expanduser().resolve())
        validate_config(payload)
        print(f"OK: {args.config}")
        return 0
    if args.command == "status":
        payload = load_json_object(args.state_dir.expanduser().resolve() / "status.json")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload else 1
    if args.command == "install-launch-agent":
        payload = load_json_object(args.config.expanduser().resolve())
        validate_config(payload)
        plist_path = install_launch_agent(
            config=args.config.expanduser().resolve(),
            state_dir=args.state_dir.expanduser().resolve(),
            label=args.label,
        )
        print(f"Installed and started: {plist_path}")
        return 0
    raise SchedulerConfigurationError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
