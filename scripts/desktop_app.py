#!/usr/bin/env python3
"""
Audiobook Studio - Native macOS Desktop GUI App (Standalone WebKit Window)
크롬 브라우저 창이 아닌 순수 macOS 전용 독립형 GUI 윈도우로 실행
"""

import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
import webview

ROOT = Path(__file__).resolve().parents[1]
PYTHON_BIN = ROOT / ".venv311" / "bin" / "python"
SCHEDULER_CONFIG = ROOT / ".work" / "continuous_scheduler" / "config.json"
SCHEDULER_STATE_DIR = ROOT / ".work" / "continuous_scheduler"
WEB_URL = "http://127.0.0.1:7870/"


def is_web_server_running() -> bool:
    try:
        req = urllib.request.Request(WEB_URL, headers={"User-Agent": "DesktopGUI/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_scheduler_running() -> bool:
    try:
        res = subprocess.run(["pgrep", "-f", "run_continuous_translation_scheduler"],
                             capture_output=True, text=True)
        return res.returncode == 0 and bool(res.stdout.strip())
    except Exception:
        return False


def ensure_backend_services():
    # 1. Start web app if not running
    if not is_web_server_running():
        (ROOT / ".webui").mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [str(PYTHON_BIN), str(ROOT / "web_app.py"), "--port", "7870"],
            cwd=str(ROOT),
            stdout=open(ROOT / ".work" / "web_app.stdout.log", "a"),
            stderr=open(ROOT / ".work" / "web_app.stderr.log", "a"),
        )
        
    # 2. Start scheduler if not running
    if not is_scheduler_running():
        (ROOT / ".work" / "continuous_scheduler").mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [
                str(PYTHON_BIN), "-m", "scripts.run_continuous_translation_scheduler",
                "run", "--config", str(SCHEDULER_CONFIG), "--state-dir", str(SCHEDULER_STATE_DIR),
            ],
            cwd=str(ROOT),
            stdout=open(SCHEDULER_STATE_DIR / "scheduler.stdout.log", "a"),
            stderr=open(SCHEDULER_STATE_DIR / "scheduler.stderr.log", "a"),
        )
        
    # Wait until web server responds
    for _ in range(30):
        if is_web_server_running():
            break
        time.sleep(0.2)


class DesktopAppAPI:
    """JS Bridge for Native Buttons"""
    def start_tasks(self):
        ensure_backend_services()
        return {"status": "started", "message": "작업이 개시되었습니다."}

    def stop_tasks(self):
        subprocess.run(["pkill", "-15", "-f", "run_continuous_translation_scheduler"], check=False)
        subprocess.run(["pkill", "-15", "-f", "translate_epub"], check=False)
        return {"status": "stopped", "message": "작업이 중단되었습니다."}

    def refresh_audit(self):
        subprocess.Popen([str(PYTHON_BIN), str(ROOT / "scripts" / "check_accounts_and_report.py")], cwd=str(ROOT))
        return {"status": "refreshed", "message": "새로고침을 시작했습니다."}

    def quit_app(self):
        sys.exit(0)


def main():
    ensure_backend_services()
    api = DesktopAppAPI()
    
    # Create native Cocoa/WebKit window (always on top enabled for unobstructed monitoring)
    window = webview.create_window(
        title="Audiobook Studio - 통합 관리 대시보드 (Native GUI)",
        url=WEB_URL,
        js_api=api,
        width=1240,
        height=820,
        min_size=(880, 580),
        on_top=True,
        text_select=True,
    )
    
    webview.start(debug=False)


if __name__ == "__main__":
    main()
