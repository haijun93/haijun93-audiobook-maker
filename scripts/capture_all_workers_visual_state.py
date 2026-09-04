#!/usr/bin/env python3
"""Capture live status and the latest Playwright screen for all four workers.

The translation worker already captures its active browser page after each
request/retry.  This monitor deliberately discovers the running processes and
their ``--work-dir`` values instead of using stale book-specific directories.
That makes the evidence useful after the supervisor rotates a worker to a new
book.  It is a one-shot snapshot by default; ``--watch`` can be used for
continuous polling.
"""

from __future__ import annotations

import json
import argparse
import shutil
import subprocess
import time
from pathlib import Path

import psutil

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = WORKSPACE_ROOT / ".work" / "continuous_scheduler" / "screenshots"
STATUS_FILE = WORKSPACE_ROOT / ".work" / "visual_audits" / "latest_worker_capture.json"
WORK_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2/_chatgpt_translate_work")

WORKERS = [
    {
        "id": "main",
        "name": "워커 1 (Gemini 1)",
        "account": "haijun93@gmail.com (Chrome Profile 1)",
        "profile_dir": "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio/browser_profiles/gemini",
    },
    {
        "id": "account2",
        "name": "워커 2 (Gemini 2)",
        "account": "haijun2be@gmail.com (Chrome Profile 2)",
        "profile_dir": "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio-account2/browser_profiles/gemini",
    },
    {
        "id": "account3",
        "name": "워커 3 (Gemini 3)",
        "account": "ngaytot9@gmail.com (Chrome Profile 18)",
        "profile_dir": "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio-account3/browser_profiles/gemini",
    },
    {
        "id": "chatgpt",
        "name": "워커 4 (ChatGPT)",
        "account": "haijun93@gmail.com (ChatGPT Profile 1)",
        "profile_dir": "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles/chatgpt",
    },
]


def _value_after(args: list[str], flag: str) -> str:
    try:
        return args[args.index(flag) + 1]
    except (ValueError, IndexError):
        return ""

def _running_workers() -> dict[str, dict]:
    """Return the live translation process for each account.

    Environment access can be denied on macOS, so command-line profile paths
    are used as a fallback for account identification.
    """
    workers: dict[str, dict] = {}
    for proc in psutil.process_iter(["pid", "cmdline", "status", "create_time", "environ"]):
        try:
            args = proc.info.get("cmdline") or []
            if not any("translate_epub_with_chatgpt_web_to_study_epub.py" in arg for arg in args):
                continue
            command = " ".join(args)
            env = proc.info.get("environ") or {}
            profile = f"{env.get('AUDIOBOOK_WEB_PROFILE_DIR', '')} {command}"
            account_id = "main"
            if "AudiobookStudio-account2" in profile:
                account_id = "account2"
            elif "AudiobookStudio-account3" in profile:
                account_id = "account3"
            elif "AudiobookStudio-chatgpt" in profile:
                account_id = "chatgpt"

            work_dir = _value_after(args, "--work-dir")
            title = _value_after(args, "--book-title-ko") or Path(_value_after(args, "--input-epub")).stem
            current = workers.get(account_id)
            if current is None or proc.info.get("create_time", 0) > current.get("create_time", 0):
                workers[account_id] = {
                    "pid": proc.info["pid"],
                    "task_id": env.get("AUDIOBOOK_TASK_ID", ""),
                    "book": title,
                    "work_dir": work_dir,
                    "process_status": proc.info.get("status", "unknown"),
                    "create_time": proc.info.get("create_time", 0),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, OSError):
            continue
    return workers


def _read_heartbeat(work_dir: Path) -> dict:
    try:
        return json.loads((work_dir / "heartbeat.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _capture_desktop_screen() -> str | None:
    """Capture the visible macOS display as a fallback visual checkpoint."""
    destination = ARTIFACT_DIR / "desktop_latest.png"
    try:
        subprocess.run(
            ["/usr/sbin/screencapture", "-x", "-m", str(destination)],
            check=True,
            timeout=10,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return str(destination) if destination.exists() and destination.stat().st_size > 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def capture_snapshot() -> dict:
    """Capture current worker metadata and copy each available live screenshot."""
    print("==================================================================")
    print("📸 REAL-TIME VISUAL SCREENSHOT MONITORING FOR WORKERS 1, 2, 3, 4")
    print("==================================================================")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    desktop_screenshot = _capture_desktop_screen()
    live = _running_workers()
    accounts = {}

    for worker in WORKERS:
        account_id = worker["id"]
        process = live.get(account_id)
        work_dir = Path(process["work_dir"]) if process and process.get("work_dir") else None
        heartbeat = _read_heartbeat(work_dir) if work_dir else {}
        screenshot = work_dir / "latest_screenshot.png" if work_dir else None
        copied = None
        if screenshot and screenshot.exists() and screenshot.stat().st_size > 0:
            copied_path = ARTIFACT_DIR / f"{account_id}_latest.png"
            try:
                shutil.copy2(screenshot, copied_path)
                copied = str(copied_path)
            except OSError:
                copied = None

        hb_timestamp = float(heartbeat.get("timestamp", 0) or 0)
        age = round(max(0.0, time.time() - hb_timestamp), 1) if hb_timestamp else None
        chunks = 0
        if work_dir and (work_dir / "translations").exists():
            chunks = len(list((work_dir / "translations").glob("chunk_*.json")))
        accounts[account_id] = {
            "name": worker["name"],
            "provider": "chatgpt" if account_id == "chatgpt" else "gemini",
            "pid": process.get("pid") if process else None,
            "book": process.get("book") if process else None,
            "task_id": process.get("task_id") if process else None,
            "work_dir": str(work_dir) if work_dir else None,
            "process_status": process.get("process_status") if process else "idle",
            "stage": heartbeat.get("stage", "idle" if not process else "heartbeat_missing"),
            "label": heartbeat.get("label"),
            "detail": str(heartbeat.get("detail", ""))[:500],
            "heartbeat_age_seconds": age,
            "chunks_done": chunks,
            "screenshot": copied,
            "screenshot_age_seconds": round(max(0.0, time.time() - screenshot.stat().st_mtime), 1) if screenshot and screenshot.exists() else None,
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        state = accounts[account_id]
        visual = "screen captured" if copied else "screen not yet captured"
        print(f"[{worker['name']}] pid={state['pid']} stage={state['stage']} chunks={chunks} {visual}")

    report = {
        "timestamp": time.time(),
        "desktop_screenshot": desktop_screenshot,
        "accounts": accounts,
    }
    STATUS_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="poll continuously")
    parser.add_argument("--interval", type=float, default=60.0, help="poll interval in seconds")
    parser.add_argument("--rounds", type=int, default=0, help="stop after N rounds; 0 means one-shot or until interrupted")
    args = parser.parse_args()

    rounds = args.rounds if args.rounds > 0 else (10**9 if args.watch else 1)
    for round_no in range(rounds):
        capture_snapshot()
        if round_no + 1 < rounds:
            time.sleep(max(1.0, args.interval))

    print("\n==================================================================")
    print("✅ VISUAL MONITORING CAPTURE COMPLETE")
    print("==================================================================")

if __name__ == "__main__":
    main()
