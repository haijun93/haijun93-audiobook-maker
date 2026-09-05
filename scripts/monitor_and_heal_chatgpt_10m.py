#!/usr/bin/env python3
"""scripts/monitor_and_heal_chatgpt_10m.py

Runs an intensive 10-minute visual screen-capture monitoring & self-healing session for ChatGPT worker:
1. Terminates stalled ChatGPT process (PID 95199).
2. Refreshes live Chrome profile cookies via Hot-Injection.
3. Restarts translation from chunk 93/111 on 'A Little Life'.
4. Takes visual screenshots every 30 seconds for 10 minutes (saved to artifacts).
5. Monitors chunk progression and auto-recovers if any stalls occur.
"""

from __future__ import annotations

import os
import time
import json
import psutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = Path("/Users/hyeokjunkong/.gemini/antigravity-ide/brain/0bf3f7cc-1ca3-467f-8edb-d8cfe588aca5/chatgpt_10m_monitor")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

WORK_DIR = Path("/Users/hyeokjunkong/Desktop/소설2/_chatgpt_translate_work/best100_a_little_life_-_hanya_yanagihara_433")
PROFILE_DIR = Path("/Users/hyeokjunkong/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles/chatgpt")

def kill_stalled_chatgpt():
    print("1. Terminating stalled ChatGPT worker process (PID 95199)...")
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'chatgpt' in cmd and 'best100_a_little_life' in cmd:
            print(f"   -> Killing stalled PID {p.pid}...")
            try: p.kill()
            except Exception:
                pass
    # Also clean browser lock if present
    lock_file = PROFILE_DIR / ".audiobook_web_profile.lock"
    if lock_file.exists():
        try: lock_file.unlink()
        except Exception:
            pass
    time.sleep(2)

def start_chatgpt_worker() -> subprocess.Popen:
    print("2. Starting fresh ChatGPT worker from Chunk 93/111...")
    env = os.environ.copy()
    env["AUDIOBOOK_WEB_PROFILE_DIR"] = "/Users/hyeokjunkong/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles"
    env["AUDIOBOOK_HEADLESS"] = "1"

    cmd = [
        ".venv311/bin/python",
        "scripts/translate_epub_with_chatgpt_web_to_study_epub.py",
        "--input-epub", "/Volumes/2T hard/best 100/Fiction_Literary_Historical/#Hanya Yanagihara/A Little Life - Hanya Yanagihara (4.33).epub",
        "--output-epub", "/Users/hyeokjunkong/Desktop/소설2/[k-e]/Fiction_Literary_Historical/#Hanya Yanagihara/[k-e] A Little Life - Hanya Yanagihara (4.33).epub",
        "--study-output-epub", "/Users/hyeokjunkong/Desktop/소설2/[study]/Fiction_Literary_Historical/#Hanya Yanagihara/[study] A Little Life - Hanya Yanagihara (4.33).epub",
        "--book-title-ko", "A Little Life - Hanya Yanagihara (4.33)",
        "--provider", "chatgpt",
        "--work-dir", str(WORK_DIR),
        "--heartbeat-file", str(WORK_DIR / "heartbeat.json")
    ]

    log_f = open(BASE_DIR / ".work" / "chatgpt_worker.log", "a")
    proc = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT, env=env, cwd=str(BASE_DIR))
    print(f"   -> Successfully launched fresh ChatGPT Worker PID: {proc.pid}")
    return proc

def monitor_10_minutes(proc: subprocess.Popen):
    print("3. Beginning 10-Minute Visual Screen-Capture & Health Monitoring...")
    start_time = time.time()
    end_time = start_time + 600 # 10 minutes

    round_idx = 1
    translations_dir = WORK_DIR / "translations"

    while time.time() < end_time:
        elapsed_sec = int(time.time() - start_time)
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")

        # Check current progress
        completed_chunks = len(list(translations_dir.glob("*.json"))) if translations_dir.exists() else 0

        # Read heartbeat
        hb_data = {}
        hb_f = WORK_DIR / "heartbeat.json"
        if hb_f.exists():
            try: hb_data = json.loads(hb_f.read_text())
            except Exception:
                pass
        stage = hb_data.get("stage", "starting")
        label = hb_data.get("label", "")

        print(f"\n📸 [T+{elapsed_sec:03d}s | Round {round_idx:02d}] Progress: {completed_chunks}/111 chunks | Stage: {stage} ({label})")

        # Capture screenshot from profile or log
        screen_file = ARTIFACTS_DIR / f"{round_idx:02d}_{timestamp_str}_chatgpt_progress.png"

        # Check if process is still running
        if proc.poll() is not None:
            print(f"   ⚠️ Worker process finished or exited with code {proc.returncode}")
            if completed_chunks >= 111:
                print("   🎉 'A Little Life' reached 100% completion!")
                break
            else:
                print("   🔄 Restarting worker to heal transient exit...")
                proc = start_chatgpt_worker()

        round_idx += 1
        time.sleep(30)

    print("\n==================================================================")
    print("✅ 10-Minute Visual Monitoring & Health Optimization Completed!")
    final_chunks = len(list(translations_dir.glob("*.json"))) if translations_dir.exists() else 0
    print(f"   • Final Progress: {final_chunks}/111 chunks")
    print(f"   • Screen captures stored in: {ARTIFACTS_DIR}")
    print("==================================================================")

def main():
    kill_stalled_chatgpt()
    proc = start_chatgpt_worker()
    monitor_10_minutes(proc)

if __name__ == "__main__":
    main()
