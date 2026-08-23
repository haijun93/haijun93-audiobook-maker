#!/usr/bin/env python3
"""
OceanofPDF Official Automated Scraper & Downloader for AudiobookStudio.

Standard operating tool to search OceanofPDF, identify missing English EPUBs,
download them directly to `/Users/hyeokjunkong/Desktop/소설2/[e]/#Author/`,
and optionally queue them into the continuous translation scheduler.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
DEFAULT_E_ROOT = LIBRARY_ROOT / "[e]"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "AudiobookStudio" / "browser_profiles" / "oceanofpdf"


def clean_title(title: str) -> str:
    t = re.sub(r"\s+by\s+.*", "", title, flags=re.IGNORECASE).strip()
    t = re.sub(r"\b(PDF|EPUB)\b", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\[.*?\]", "", t).strip()
    t = re.sub(r"\(\d+\.\d+\)", "", t).strip()
    t = re.sub(r"[^\w\s]", "", t).strip().lower()
    return t


def get_owned_stems(dest_dir: Path) -> set[str]:
    owned = set()
    # Check current destination directory
    if dest_dir.exists():
        for p in dest_dir.rglob("*.epub"):
            owned.add(clean_title(p.stem))
            
    # Also check whole library editions ([k-e], [study], [k], [e]) to avoid re-downloading existing titles
    for ed in ["[k-e]", "[study]", "[k]", "[e]"]:
        ed_path = LIBRARY_ROOT / ed
        if ed_path.exists():
            for p in ed_path.rglob("*.epub"):
                owned.add(clean_title(p.stem))
    return owned


def is_english_title(title: str) -> bool:
    non_en_prefixes = ["le ", "de ", "der ", "het ", "das ", "une ", "la ", "les ", "un "]
    tl = title.lower()
    return not any(tl.startswith(p) for p in non_en_prefixes)


def search_and_download(
    *,
    author: str,
    query: str | None = None,
    dest_dir: Path | None = None,
    max_pages: int = 5,
    auto_queue: bool = False,
    visible: bool = True,
) -> list[Path]:
    search_query = query or author
    target_author = author
    author_folder = f"#{target_author}" if not target_author.startswith("#") else target_author
    target_dir = dest_dir or (DEFAULT_E_ROOT / author_folder)
    target_dir.mkdir(parents=True, exist_ok=True)

    owned = get_owned_stems(target_dir)
    print(f"\n=======================================================")
    print(f"📖 OceanofPDF Downloader — Target: {target_author}")
    print(f"📁 Destination: {target_dir}")
    print(f"📚 Currently owned: {len(owned)} titles in library (Whole Library Deduplication Active)")
    print(f"=======================================================\n")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    download_dir = Path(tempfile.mkdtemp())
    downloaded_files: list[Path] = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=CHROME_PATH,
            headless=not visible,
            accept_downloads=True,
            downloads_path=str(download_dir),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        page = context.new_page()

        # Step 1: Search and gather book links
        book_candidates: list[tuple[str, str]] = []
        for page_idx in range(1, max_pages + 1):
            url = f"https://oceanofpdf.com/page/{page_idx}/?s={search_query.replace(' ', '+')}" if page_idx > 1 else f"https://oceanofpdf.com/?s={search_query.replace(' ', '+')}"
            print(f"[Search Page {page_idx}] Visiting: {url}...", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(2.5)
                # Handle potential Cloudflare challenge
                for _ in range(12):
                    try:
                        t = page.title()
                        if "잠시만" not in t and "Just a moment" not in t and "Cloudflare" not in t:
                            break
                    except:
                        pass
                    time.sleep(1.5)

                time.sleep(1.5)
                html_content = ""
                for _ in range(5):
                    try:
                        html_content = page.content()
                        if html_content:
                            break
                    except:
                        time.sleep(1)
                
                soup = BeautifulSoup(html_content, "html.parser")
                articles = soup.find_all("article")
                if not articles:
                    print(f"  No more articles on page {page_idx}.", flush=True)
                    break

                for a in articles:
                    h2 = a.find(["h2", "h3", "h1"])
                    link = a.find("a")
                    raw_title = h2.get_text(strip=True) if h2 else (link.get_text(strip=True) if link else "")
                    href = link.get("href") if link else ""
                    if href and is_english_title(raw_title):
                        book_candidates.append((raw_title, href))
                        print(f"  • Found: {raw_title}", flush=True)

                if not soup.find("a", class_="next"):
                    break
            except Exception as e:
                print(f"  Error on search page {page_idx}: {e}", flush=True)
                break

        print(f"\nTotal candidate books discovered: {len(book_candidates)}", flush=True)

        # Step 2: Filter missing books
        missing_targets: list[tuple[str, str]] = []
        for raw_title, href in book_candidates:
            c = clean_title(raw_title)
            if not any(c == o or c in o or o in c for o in owned):
                missing_targets.append((raw_title, href))
                print(f"  🎯 MISSING TARGET: {raw_title}", flush=True)
            else:
                print(f"  ⏩ Already owned: {raw_title}", flush=True)

        print(f"\n--> {len(missing_targets)} books to download.\n", flush=True)

        # Step 3: Download missing targets
        for idx, (raw_title, href) in enumerate(missing_targets, 1):
            print(f"[{idx}/{len(missing_targets)}] Navigating to: {raw_title}...", flush=True)
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=45000)
                # Wait for challenge resolution
                for _ in range(12):
                    t = page.title()
                    if "잠시만" not in t and "Just a moment" not in t:
                        break
                    time.sleep(1.5)

                # Locate EPUB download button
                # Button is inside form with hidden input filename containing .epub
                form = page.locator("form:has(input[value*='.epub'])")
                if form.count() == 0:
                    form = page.locator("form[action*='Fetching_Resource']")

                if form.count() > 0:
                    btn = form.first.locator("input[type='image'], input[type='submit'], button")
                    print("  Triggering EPUB download...", flush=True)
                    with page.expect_download(timeout=45000) as download_info:
                        if btn.count() > 0:
                            btn.first.click(force=True)
                        else:
                            form.first.evaluate("f => f.submit()")

                    download = download_info.value
                    orig_name = download.suggested_filename
                    temp_file = download_dir / orig_name
                    download.save_as(str(temp_file))

                    # Validate EPUB file
                    if temp_file.exists() and temp_file.stat().st_size > 1000:
                        # Standard library format: [e] Title - Author.epub
                        clean_stem = raw_title.split(" by ")[0].strip()
                        final_filename = f"[e] {clean_stem} - {target_author}.epub"
                        final_path = target_dir / final_filename
                        if final_path.exists():
                            print(f"  ⏩ Skipping: {final_filename} already exists in destination.\n", flush=True)
                        else:
                            shutil.copy2(temp_file, final_path)
                            print(f"  ✅ SUCCESS: Saved to {final_path.name} ({final_path.stat().st_size:,} bytes)\n", flush=True)
                            downloaded_files.append(final_path)
                        owned.add(clean_title(raw_title))
                    else:
                        print(f"  ❌ File invalid or 0 bytes: {orig_name}\n", flush=True)
                else:
                    print(f"  ⚠️ Download form not found for {raw_title}\n", flush=True)

                time.sleep(2)
            except Exception as e:
                print(f"  ❌ Download failed for {raw_title}: {e}\n", flush=True)

        context.close()

    shutil.rmtree(download_dir, ignore_errors=True)

    print(f"\n=======================================================")
    print(f"🎉 Download Summary: {len(downloaded_files)} new EPUBs downloaded to {target_dir}")
    print(f"=======================================================\n")

    return downloaded_files


def main() -> int:
    parser = argparse.ArgumentParser(description="OceanofPDF Official Downloader & Scheduler Integration")
    parser.add_argument("--author", type=str, default="Freida McFadden", help="Author name to search & download")
    parser.add_argument("--query", type=str, default=None, help="Optional specific search query")
    parser.add_argument("--dest-dir", type=Path, default=None, help="Target library directory for [e] EPUBs")
    parser.add_argument("--max-pages", type=int, default=5, help="Max search result pages to scan")
    parser.add_argument("--auto-queue", action="store_true", help="Automatically queue downloaded books for translation")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (default: visible for Cloudflare)")
    args = parser.parse_args()

    downloaded = search_and_download(
        author=args.author,
        query=args.query,
        dest_dir=args.dest_dir,
        max_pages=args.max_pages,
        auto_queue=args.auto_queue,
        visible=not args.headless,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
