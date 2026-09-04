#!/usr/bin/env python3
"""scripts/download_netflix_originals.py

Searches OceanofPDF and downloads major Netflix Original adaptation novels
directly to `/Users/hyeokjunkong/Desktop/소설2/new books from vk/`.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
VK_DIR = Path("/Users/hyeokjunkong/Desktop/소설2/new books from vk")
VK_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "AudiobookStudio" / "browser_profiles" / "oceanofpdf"

NETFLIX_TARGETS = [
    {"query": "Three Body Problem", "title": "The Three-Body Problem", "author": "Cixin Liu"},
    {"query": "Duke and I", "title": "The Duke and I", "author": "Julia Quinn"},
    {"query": "Queens Gambit", "title": "The Queen's Gambit", "author": "Walter Tevis"},
    {"query": "Lincoln Lawyer", "title": "The Lincoln Lawyer", "author": "Michael Connelly"},
    {"query": "One Day Nicholls", "title": "One Day", "author": "David Nicholls"},
    {"query": "Fool Me Once", "title": "Fool Me Once", "author": "Harlan Coben"},
    {"query": "All the Light We Cannot See", "title": "All the Light We Cannot See", "author": "Anthony Doerr"},
    {"query": "Behind Her Eyes Pinborough", "title": "Behind Her Eyes", "author": "Sarah Pinborough"},
    {"query": "Shadow and Bone", "title": "Shadow and Bone", "author": "Leigh Bardugo"},
    {"query": "The Last Wish Sapkowski", "title": "The Last Wish", "author": "Andrzej Sapkowski"},
]

def main():
    print("==================================================================")
    print("🎬 NETFLIX ORIGINAL NOVELS AUTO-DOWNLOADER (OceanofPDF)")
    print(f"📁 Destination: {VK_DIR}")
    print("==================================================================\n", flush=True)

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    download_dir = Path(tempfile.mkdtemp())
    downloaded = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=CHROME_PATH,
            headless=False,
            accept_downloads=True,
            downloads_path=str(download_dir),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        page = context.new_page()

        for idx, target in enumerate(NETFLIX_TARGETS, 1):
            q = target["query"]
            t_name = target["title"]
            a_name = target["author"]

            # Check if file already exists in VK dir or finished
            existing = list(VK_DIR.glob(f"*{t_name.replace(' ', '_')}*.epub")) + list((VK_DIR / "finished").glob(f"*{t_name.replace(' ', '_')}*.epub"))
            if existing:
                print(f"[{idx:02d}/{len(NETFLIX_TARGETS):02d}] ⏩ Skipping (already exists): {t_name} - {a_name}", flush=True)
                continue

            print(f"[{idx:02d}/{len(NETFLIX_TARGETS):02d}] 🔍 Searching OceanofPDF: '{q}'...", flush=True)
            search_url = f"https://oceanofpdf.com/?s={q.replace(' ', '+')}"

            try:
                page.goto(search_url, timeout=45000, wait_until="domcontentloaded")
                time.sleep(2.5)

                # Cloudflare bypass loop
                for _ in range(10):
                    try:
                        title_text = page.title()
                        if "잠시만" not in title_text and "Just a moment" not in title_text and "Cloudflare" not in title_text:
                            break
                    except Exception:
                        pass
                    time.sleep(1.5)

                soup = BeautifulSoup(page.content(), "html.parser")
                articles = soup.find_all("article")

                target_url = None
                target_title = None

                for art in articles:
                    link_el = art.find("a", href=True)
                    title_el = art.find(["h2", "h3", "h1"]) or link_el
                    if not link_el or not title_el:
                        continue

                    found_title = title_el.get_text(strip=True)
                    href = link_el["href"]
                    target_url = href
                    target_title = found_title
                    break

                if not target_url:
                    print("   ⚠️ No matching search results found on OceanofPDF.", flush=True)
                    continue

                print(f"   📖 Found: {target_title}", flush=True)
                print(f"   🌐 Opening book page: {target_url}...", flush=True)
                page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2.0)

                # Locate EPUB download button using official AudiobookStudio selector
                form = page.locator("form:has(input[value*='.epub'])")
                if form.count() == 0:
                    form = page.locator("form[action*='Fetching_Resource']")

                if form.count() > 0:
                    btn = form.first.locator("input[type='image'], input[type='submit'], button")
                    print("   ⬇️ Triggering EPUB download...", flush=True)
                    with page.expect_download(timeout=60000) as download_info:
                        if btn.count() > 0:
                            btn.first.click(force=True)
                        else:
                            form.first.evaluate("f => f.submit()")

                    download = download_info.value
                    orig_name = download.suggested_filename
                    temp_file = download_dir / orig_name
                    download.save_as(str(temp_file))

                    if temp_file.exists() and temp_file.stat().st_size > 5000:
                        dest_file = VK_DIR / orig_name
                        shutil.copy2(temp_file, dest_file)
                        print(f"   ✅ SUCCESS: Downloaded and saved to vk folder: {dest_file.name} ({dest_file.stat().st_size:,} bytes)\n", flush=True)
                        downloaded.append(dest_file)
                    else:
                        print("   ❌ Downloaded file invalid or too small.\n", flush=True)
                else:
                    print("   ⚠️ EPUB download form not found on page.\n", flush=True)

                time.sleep(2.0)
            except Exception as e:
                print(f"   ❌ Failed to download {t_name}: {e}\n", flush=True)

        context.close()

    shutil.rmtree(download_dir, ignore_errors=True)
    print("==================================================================")
    print(f"🎉 DOWNLOAD COMPLETE: {len(downloaded)} Netflix Original EPUBs added to vk folder!")
    print("==================================================================")

if __name__ == "__main__":
    main()
