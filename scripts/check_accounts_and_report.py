#!/usr/bin/env python3
"""30-minute account login status and batch progress reporter."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webui.storage import atomic_write_json
import audiobook_maker


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".work" / "continuous_scheduler"
CONFIG_FILE = STATE_DIR / "config.json"
STATE_FILE = STATE_DIR / "state.json"
REPORT_OUTPUT_FILE = STATE_DIR / "account_login_health.json"


def check_account_login_health(account_id: str, provider: str, profile_dir: Path, is_active_running: bool = False) -> dict[str, Any]:
    """Check whether the persistent browser profile has an active login session."""
    if is_active_running:
        return {
            "logged_in": True,
            "status": "active_translating",
            "message": "실시간 번역 작업 정상 수행 중",
            "checked_at": time.time(),
        }

    if provider == "gemini":
        gemini_dir = profile_dir / "gemini" if not str(profile_dir).endswith("gemini") else profile_dir
        if not gemini_dir.is_dir():
            return {"logged_in": False, "reason": "profile_dir_missing", "checked_at": time.time()}
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(gemini_dir),
                    headless=True,
                    channel="chrome",
                    args=["--password-store=basic"],
                )
                page = context.new_page()
                page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(3500)
                
                # Check guest login button
                btn_text = audiobook_maker.GEMINI_WEB_GUEST_MODE_LOGIN_BUTTON_TEXT
                buttons = page.get_by_text(btn_text, exact=True)
                guest_detected = any(buttons.nth(i).is_visible() for i in range(buttons.count()))
                
                if guest_detected:
                    cookie_file = audiobook_maker.WEB_ACCOUNT_BOOTSTRAP_COOKIE_FILES.get(account_id)
                    if cookie_file and cookie_file.is_file():
                        try:
                            import browser_cookie3
                            cookies = audiobook_maker.load_gemini_web_cookies(browser_cookie3, cookie_file=str(cookie_file))
                            if cookies:
                                context.add_cookies(cookies)
                                page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=25000)
                                page.wait_for_timeout(3500)
                                buttons = page.get_by_text(btn_text, exact=True)
                                guest_detected = any(buttons.nth(i).is_visible() for i in range(buttons.count()))
                        except Exception:
                            pass
                
                has_prompt = page.locator('rich-textarea, div[contenteditable="true"]').count() > 0
                has_account = "haijun" in page.content() or "ngaytot9" in page.content() or not guest_detected
                
                context.close()
                return {
                    "logged_in": not guest_detected and has_prompt,
                    "guest_detected": guest_detected,
                    "has_prompt": has_prompt,
                    "checked_at": time.time(),
                }
        except Exception as exc:
            return {"logged_in": False, "error": str(exc), "checked_at": time.time()}
            
    elif provider == "chatgpt":
        chatgpt_dir = profile_dir / "chatgpt" if not str(profile_dir).endswith("chatgpt") else profile_dir
        if not chatgpt_dir.is_dir():
            return {"logged_in": False, "reason": "profile_dir_missing", "checked_at": time.time()}
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(chatgpt_dir),
                    headless=True,
                    channel="chrome",
                    args=["--password-store=basic"],
                )
                page = context.new_page()
                page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(3500)
                
                has_prompt = page.locator('#prompt-textarea, div[contenteditable="true"]').count() > 0
                has_login_btn = page.locator('button[data-testid="login-button"]').count() > 0
                
                context.close()
                return {
                    "logged_in": has_prompt and not has_login_btn,
                    "has_prompt": has_prompt,
                    "checked_at": time.time(),
                }
        except Exception as exc:
            return {"logged_in": False, "error": str(exc), "checked_at": time.time()}
            
    return {"logged_in": True, "provider": provider, "checked_at": time.time()}


def generate_status_and_health_report() -> dict[str, Any]:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.is_file() else {}
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.is_file() else {}
    
    accounts = config.get("accounts", [])
    account_health: dict[str, Any] = {}
    active_accounts = {
        aid for aid, astate in state.get("accounts", {}).items()
        if astate.get("status") in ("running", "external", "active") and astate.get("pid")
    }
    
    for acc in accounts:
        aid = acc["id"]
        prov = acc["provider"]
        prof = Path(acc["profile_dir"])
        is_active = aid in active_accounts
        print(f"Checking login health for {aid} ({prov}, active={is_active})...")
        health = check_account_login_health(aid, prov, prof, is_active_running=is_active)
        account_health[aid] = {
            "label": acc.get("label", aid),
            "provider": prov,
            "profile_dir": str(prof),
            **health,
        }
    
    # Task progress summary
    tasks_summary: list[dict[str, Any]] = []
    task_states = state.get("tasks", {})
    for tspec in config.get("tasks", []):
        tid = tspec["id"]
        tstate = task_states.get(tid, {})
        work_dir = Path(tspec.get("work_dir", ""))
        heartbeat_file = work_dir / "heartbeat.json"
        
        hb = {}
        if heartbeat_file.is_file():
            try:
                hb = json.loads(heartbeat_file.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        completed = hb.get("completed_chunks", hb.get("completed", 0))
        total = hb.get("total_chunks", hb.get("total", 0))
        pct = round((completed / total * 100), 1) if total > 0 else 0.0
        
        tasks_summary.append({
            "id": tid,
            "title": tspec.get("title", tid),
            "status": tstate.get("status", "unknown"),
            "account_id": tstate.get("account_id"),
            "completed": completed,
            "total": total,
            "progress_percent": pct,
            "last_error": tstate.get("error"),
        })
        
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "account_health": account_health,
        "tasks": tasks_summary,
    }
    
    atomic_write_json(REPORT_OUTPUT_FILE, report)
    return report


if __name__ == "__main__":
    report = generate_status_and_health_report()
    print("\n=== 30-MINUTE ACCOUNT & BATCH HEALTH REPORT ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
