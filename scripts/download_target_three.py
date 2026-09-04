#!/usr/bin/env python3
"""scripts/download_target_three.py

Direct targeted downloader for:
1. The Alchemist - Paulo Coelho
2. Eleven Minutes - Paulo Coelho
3. Perfume: The Story of a Murderer - Patrick Süskind
"""

import time
import shutil
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
E_ROOT = LIB_ROOT / "[e]"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

TARGETS = [
    {
        "title": "The Alchemist",
        "author": "Paulo Coelho",
        "url": "https://oceanofpdf.com/authors/paulo-coelho/pdf-epub-the-alchemist-download/",
        "dest_dir": E_ROOT / "#Paulo Coelho",
        "final_filename": "[e] The Alchemist - Paulo Coelho.epub"
    },
    {
        "title": "Eleven Minutes",
        "author": "Paulo Coelho",
        "url": "https://oceanofpdf.com/authors/paulo-coelho/pdf-epub-eleven-minutes-download/",
        "dest_dir": E_ROOT / "#Paulo Coelho",
        "final_filename": "[e] Eleven Minutes - Paulo Coelho.epub"
    },
    {
        "title": "Perfume: The Story of a Murderer",
        "author": "Patrick Süskind",
        "url": "https://oceanofpdf.com/authors/patrick-suskind/pdf-epub-perfume-the-story-of-a-murderer-download/",
        "dest_dir": E_ROOT / "#Patrick Süskind",
        "final_filename": "[e] Perfume The Story of a Murderer - Patrick Süskind.epub"
    }
]

def download_one_target(page, target, download_dir):
    print("\n=======================================================")
    print(f"📖 Downloading: {target['title']} ({target['author']})")
    print(f"🔗 URL: {target['url']}")
    target['dest_dir'].mkdir(parents=True, exist_ok=True)

    try:
        page.goto(target['url'], wait_until="domcontentloaded", timeout=45000)
        time.sleep(3)

        # Handle cloudflare if any
        for _ in range(10):
            t = page.title()
            if "Just a moment" not in t and "잠시만" not in t:
                break
            time.sleep(1.5)

        time.sleep(2)

        # Find the EPUB form or button
        forms = page.locator("form")
        epub_form = None
        for i in range(forms.count()):
            f = forms.nth(i)
            html = f.inner_html()
            if ".epub" in html.lower() or "epub" in html.lower():
                epub_form = f
                break

        if not epub_form and forms.count() > 0:
            epub_form = forms.first

        if not epub_form:
            print("  ❌ No download form found!")
            return False

        btn = epub_form.locator("input[type='image'], input[type='submit'], button")
        print("  🚀 Triggering EPUB download stream...")

        with page.expect_download(timeout=60000) as download_info:
            if btn.count() > 0:
                btn.first.click(force=True)
            else:
                epub_form.evaluate("f => f.submit()")

        download = download_info.value
        temp_file = download_dir / download.suggested_filename
        download.save_as(str(temp_file))

        if temp_file.exists() and temp_file.stat().st_size > 1000:
            dest_file = target['dest_dir'] / target['final_filename']
            shutil.copy2(temp_file, dest_file)
            print(f"  ✅ SUCCESS: Saved {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
            return True
        else:
            print("  ❌ Downloaded file invalid or empty.")
            return False
    except Exception as e:
        print(f"  ❌ Error downloading {target['title']}: {e}")
        return False

def main():
    profile_dir = Path(tempfile.mkdtemp())
    download_dir = Path(tempfile.mkdtemp())

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            executable_path=CHROME_PATH,
            headless=True,
            accept_downloads=True,
            downloads_path=str(download_dir),
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()

        for t in TARGETS:
            download_one_target(page, t, download_dir)
            time.sleep(3)

        context.close()

if __name__ == "__main__":
    main()
