#!/usr/bin/env python3
"""Single book test for Claude Web X-Ray Harvester with screenshots."""

import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import browser_cookie3

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "AudiobookStudio" / "browser_profiles" / "claude"
SCREENSHOT_DIR = Path("data/claude_harvest_screenshots")
CACHE_DIR = Path("data/fiction_xray_cache")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def get_claude_cookies():
    cj = browser_cookie3.chrome()
    claude_cookies = []
    for c in cj:
        if "claude.ai" in c.domain:
            claude_cookies.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain if c.domain.startswith(".") else f".{c.domain}",
                "path": c.path or "/",
                "secure": bool(c.secure),
                "httpOnly": bool(c.has_nonstandard_attr("HttpOnly")),
            })
    return claude_cookies

def test_harvest_book(title: str, author: str):
    print(f"\n🧪 Testing Claude Web X-Ray for: '{title}' by {author}...")
    cookies = get_claude_cookies()
    print(f"🔑 Loaded {len(cookies)} cookies from Chrome.")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=CHROME_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        if cookies:
            browser.add_cookies(cookies)

        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        print("🌐 Navigating to https://claude.ai/new ...")
        page.goto("https://claude.ai/new", wait_until="domcontentloaded", timeout=45000)
        time.sleep(3)

        # Take screenshot of new chat page
        page.screenshot(path=str(SCREENSHOT_DIR / "01_new_chat.png"))

        prompt = f"""다음 소설에 대한 킨들 X-Ray(등장인물 도감 및 해설)을 100% 한국어로 작성해줘:
- 소설 제목: {title}
- 작가: {author}

반드시 소설의 실제 줄거리와 인물을 바탕으로 다음 4가지 항목을 JSON으로만 작성해줘:
```json
{{
  "title": "{title}",
  "author": "{author}",
  "characters": [
    ["인물명 (원어명)", "역할/신분", "소설 속 실제 성격, 배경, 행동 동기, 서사적 비중 상세 설명"]
  ],
  "relationships": [
    "• 인물A ↔ 인물B: 실제 핵심 대립/협력/애증 관계 및 심리적 갈등 상세 설명"
  ],
  "locations": [
    ["핵심 무대/장소명", "소설 속 실제 공간적 의미, 분위기 및 사건 전개 배경 상세 설명"]
  ],
  "themes": [
    ["핵심 주제", "소설을 관통하는 중심 메시지 및 주제 의식"],
    ["핵심 용어/복선", "세계관 이해에 필수적인 핵심 개념 또는 주요 복선"]
  ]
}}
```
"""
        editor = page.locator("div.ProseMirror, div[contenteditable=\"true\"]").first
        if editor.count() == 0:
            print("❌ Could not find editor ProseMirror!")
            page.screenshot(path=str(SCREENSHOT_DIR / "error_no_editor.png"))
            browser.close()
            return None

        editor.click()
        page.keyboard.insert_text(prompt)
        time.sleep(1)

        page.screenshot(path=str(SCREENSHOT_DIR / "02_prompt_typed.png"))

        send_btn = page.locator("button[aria-label=\"메시지 보내기\"], button[aria-label*=\"Send\"], button.bg-accent-main-000").first
        if send_btn.count() == 0 or send_btn.is_disabled():
            print("❌ Send button not clickable!")
            page.screenshot(path=str(SCREENSHOT_DIR / "error_send_disabled.png"))
            browser.close()
            return None

        send_btn.click()
        print("🚀 Clicked Send button! Waiting for generation...")

        # Wait for generation to complete
        start_t = time.time()
        completed = False
        parsed_json = None

        while time.time() - start_t < 70:
            time.sleep(3)
            # Check if stop button is gone
            stop_btn = page.locator("button[aria-label*=\"중지\"], button[aria-label*=\"Stop\"]")
            is_generating = stop_btn.count() > 0 and stop_btn.is_visible()

            # Check assistant messages
            assistant_msgs = page.locator("[data-message-author-role=\"assistant\"], .font-claude-message, pre code")
            if assistant_msgs.count() > 0:
                txt = assistant_msgs.last.inner_text()
                if "{" in txt and "}" in txt and "characters" in txt:
                    m = re.search(r"```json\s*(\{.*?\})\s*```", txt, flags=re.DOTALL) or re.search(r"(\{.*\})", txt, flags=re.DOTALL)
                    if m:
                        try:
                            data = json.loads(m.group(1))
                            if "characters" in data and len(data["characters"]) >= 2:
                                parsed_json = data
                                if not is_generating:
                                    completed = True
                                    break
                        except Exception:
                            pass

            if completed:
                break

        page.screenshot(path=str(SCREENSHOT_DIR / "03_response_received.png"))
        browser.close()

        if parsed_json:
            print(f"🎉 SUCCESS! Received valid dossier with {len(parsed_json.get('characters', []))} characters:")
            for c in parsed_json.get("characters", [])[:4]:
                print(f"   👤 {c[0]} ({c[1]}): {c[2][:40]}...")
            return parsed_json
        else:
            print("❌ Failed to parse valid JSON dossier.")
            return None

if __name__ == "__main__":
    # Test with Sea of Ruin by Pam Godwin
    test_harvest_book("Sea of Ruin", "Pam Godwin")
