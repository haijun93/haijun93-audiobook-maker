#!/usr/bin/env python3
"""Launch a visible Chrome window for Account 2 login."""
from pathlib import Path
from playwright.sync_api import sync_playwright

profile_dir = Path.home() / "Library" / "Application Support" / "AudiobookStudio-account2" / "browser_profiles"

print(f"Opening visible Chrome for Gemini Account 2 at:\n{profile_dir}")
print("Please log into Google Gemini (gemini.google.com) in the opened browser window.")

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        channel="chrome",
        args=["--password-store=basic"],
    )
    page = context.new_page()
    page.goto("https://gemini.google.com/app")
    print("Browser is open. Log in and close the browser window when done.")
    try:
        page.wait_for_timeout(300000)  # 5 minutes
    except Exception:
        pass
    context.close()
