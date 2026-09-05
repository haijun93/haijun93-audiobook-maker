#!/usr/bin/env python3
"""
Download remaining missing Freida McFadden EPUBs from OceanofPDF.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DEST_DIR = Path("/Users/hyeokjunkong/Desktop/소설2/[e]/#Freida McFadden")
DEST_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "AudiobookStudio" / "browser_profiles" / "oceanofpdf"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

TARGET_BOOKS = [
    ("The Locked Door", "https://oceanofpdf.com/authors/freida-mcfadden/pdf-epub-the-locked-door-download-92354255011/"),
    ("Ward D", "https://oceanofpdf.com/authors/freida-mcfadden/pdf-epub-ward-d-download-21834217648/"),
    ("The Surrogate Mother", "https://oceanofpdf.com/authors/freida-mcfadden/pdf-epub-the-surrogate-mother-download-40016554350/"),
    ("The Wife Upstairs", "https://oceanofpdf.com/authors/freida-mcfadden/pdf-epub-the-wife-upstairs-by-freida-mcfadden-download-89953622003/"),
    ("The Devil You Know", "https://oceanofpdf.com/?s=Freida+McFadden+The+Devil+You+Know"),
]


def extract_epub_metadata(epub_path: Path) -> tuple[str | None, str | None]:
    try:
        with zipfile.ZipFile(epub_path, 'r') as z:
            names = z.namelist()
            opf_files = [n for n in names if n.endswith('.opf')]
            if opf_files:
                soup = BeautifulSoup(z.read(opf_files[0]), 'xml')
                title_tag = soup.find(['dc:title', 'title'])
                creator_tag = soup.find(['dc:creator', 'creator'])
                return (
                    title_tag.get_text(strip=True) if title_tag else None,
                    creator_tag.get_text(strip=True) if creator_tag else None,
                )
    except Exception:
        pass
    return None, None


def main() -> int:
    download_staging = Path(tempfile.mkdtemp())
    print("=== Downloading Remaining Freida McFadden Books ===")
    print(f"Destination: {DEST_DIR}")
    print(f"Download staging: {download_staging}\n")

    downloaded_count = 0

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=CHROME_PATH,
            headless=False,
            accept_downloads=True,
            downloads_path=str(download_staging),
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()

        for title, url in TARGET_BOOKS:
            # Check if already in DEST_DIR
            existing = list(DEST_DIR.glob(f"*{title}*.epub"))
            if existing:
                print(f"⏩ Already exists: {existing[0].name}")
                continue

            print("\n==================================================")
            print(f"📖 Processing: {title} ({url})")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)

                # Wait for Cloudflare challenge
                for _ in range(12):
                    t = page.title()
                    if "잠시만" not in t and "Just a moment" not in t:
                        break
                    time.sleep(1.5)

                # If search page, click first article
                if "?s=" in url:
                    articles = page.locator("article").all()
                    if not articles:
                        print(f"  ❌ No search results found for {title}")
                        continue
                    first_link = articles[0].locator("a").first
                    detail_href = first_link.get_attribute("href")
                    print(f"  Found post: {detail_href}")
                    page.goto(detail_href, wait_until="domcontentloaded", timeout=45000)
                    for _ in range(10):
                        t = page.title()
                        if "잠시만" not in t and "Just a moment" not in t:
                            break
                        time.sleep(1.5)

                # Snapshot before click
                before_files = set(download_staging.iterdir())

                # Find EPUB form button
                form = page.locator("form:has(input[value*='.epub'])")
                if form.count() == 0:
                    form = page.locator("form[action*='Fetching_Resource']")

                if form.count() > 0:
                    btn = form.first.locator("input[type='image'], input[type='submit'], button")
                    print("  Triggering EPUB download...", flush=True)

                    download_obj = None
                    try:
                        with page.expect_download(timeout=25000) as download_info:
                            if btn.count() > 0:
                                btn.first.click(force=True)
                            else:
                                form.first.evaluate("f => f.submit()")
                        download_obj = download_info.value
                    except Exception as e:
                        print(f"  Note: expect_download event wait ended ({e}). Checking staging folder...")

                    time.sleep(5)

                    # Check for new files in staging
                    after_files = set(download_staging.iterdir()) - before_files
                    new_file: Path | None = None

                    if download_obj:
                        suggested = download_obj.suggested_filename
                        target_temp = download_staging / suggested
                        download_obj.save_as(str(target_temp))
                        new_file = target_temp
                    elif after_files:
                        new_file = list(after_files)[0]

                    if new_file and new_file.exists() and new_file.stat().st_size > 1000:
                        # Verify epub
                        meta_title, _ = extract_epub_metadata(new_file)
                        clean_name = meta_title or title
                        clean_name = re.sub(r"\s+by\s+.*", "", clean_name, flags=re.IGNORECASE).strip()
                        clean_name = re.sub(r"\[.*?\]", "", clean_name).strip()

                        final_name = f"[e] {clean_name} - Freida McFadden.epub"
                        final_path = DEST_DIR / final_name
                        shutil.copy2(new_file, final_path)
                        print(f"  🎉 SUCCESS: Saved {final_path.name} ({final_path.stat().st_size:,} bytes)")
                        downloaded_count += 1
                    else:
                        print(f"  ❌ No file downloaded for {title}")
                else:
                    print(f"  ⚠️ EPUB download form not found for {title}")

                time.sleep(2)
            except Exception as e:
                print(f"  ❌ Error processing {title}: {e}")

        context.close()

    shutil.rmtree(download_staging, ignore_errors=True)
    print("\n==================================================")
    print(f"Finished! Total {downloaded_count} new EPUBs downloaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
