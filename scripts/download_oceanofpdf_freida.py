#!/usr/bin/env python3
"""
OceanofPDF automated search & downloader for missing Freida McFadden books.
Uses persistent Playwright with real Chrome to cleanly bypass Cloudflare,
downloads missing EPUBs directly into `/소설2/[e]/#Freida McFadden/`,
and queues them into the continuous translation scheduler.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
DEST_DIR = LIBRARY_ROOT / "[e]" / "#Freida McFadden"
DEST_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def get_owned_titles() -> set[str]:
    owned = set()
    if DEST_DIR.exists():
        for p in DEST_DIR.glob("*.epub"):
            stem = p.stem.replace("[e] ", "").strip()
            # remove rating suffixes like (4.08)
            clean = re.sub(r"\(\d+\.\d+\)", "", stem)
            clean = re.sub(r"[^\w\s]", "", clean).strip().lower()
            owned.add(clean)
    return owned


def normalize_title(title: str) -> str:
    # e.g., "The Ex by Freida McFadden" -> "the ex"
    t = re.sub(r"\s+by\s+Freida\s+McFadden.*", "", title, flags=re.IGNORECASE).strip()
    t = re.sub(r"\b(PDF|EPUB)\b", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"[^\w\s]", "", t).strip().lower()
    return t


def is_english_book(title: str, url: str) -> bool:
    # filter out non-english translations like 'Le diner', 'De vriend', 'Der Insasse'
    non_english = ["le diner", "de vriend", "der ", "het ", "das ", "une ", "la "]
    title_lower = title.lower()
    for ne in non_english:
        if title_lower.startswith(ne):
            return False
    return True


def run_downloader() -> list[Path]:
    owned = get_owned_titles()
    print(f"=== Currently Owned Freida McFadden Books ({len(owned)} titles) ===")

    temp_profile = tempfile.mkdtemp()
    download_dir = Path(tempfile.mkdtemp())

    downloaded_files: list[Path] = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=temp_profile,
            executable_path=CHROME_PATH,
            headless=False,
            accept_downloads=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        page = context.new_page()

        # 1. Search oceanofpdf for Freida McFadden across pages
        book_links: list[tuple[str, str]] = []
        page_num = 1

        while page_num <= 5:
            search_url = f"https://oceanofpdf.com/page/{page_num}/?s=Freida+McFadden" if page_num > 1 else "https://oceanofpdf.com/?s=Freida+McFadden"
            print(f"\n[Page {page_num}] Fetching {search_url}...")
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(5)

                soup = BeautifulSoup(page.content(), "html.parser")
                articles = soup.find_all("article")
                if not articles:
                    print(f"No more articles found on page {page_num}.")
                    break

                for a in articles:
                    h2 = a.find(["h2", "h3", "h1"])
                    link = a.find("a")
                    raw_title = h2.get_text(strip=True) if h2 else (link.get_text(strip=True) if link else "")
                    href = link.get("href") if link else ""
                    if href and is_english_book(raw_title, href):
                        book_links.append((raw_title, href))
                        print(f"  Found: {raw_title} -> {href}")

                next_link = soup.find("a", class_="next")
                if not next_link:
                    break
                page_num += 1
            except Exception as e:
                print(f"Error on page {page_num}:", e)
                break

        print(f"\nTotal Candidate Book Links Found: {len(book_links)}")

        # 2. Filter missing books
        missing_books = []
        for raw_title, href in book_links:
            clean = normalize_title(raw_title)
            # check against owned
            is_owned = any(clean == o or clean in o or o in clean for o in owned)
            if not is_owned:
                missing_books.append((raw_title, href))
                print(f"🎯 NEW TARGET TO DOWNLOAD: {raw_title}")
            else:
                print(f"⏩ Already owned: {raw_title}")

        print(f"\n=== Found {len(missing_books)} missing books to download ===")

        # 3. Download each missing book
        for raw_title, href in missing_books:
            print(f"\n--> Navigating to {raw_title} ({href})...")
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=45000)
                time.sleep(4)

                # Look for EPUB download button / form
                # OceanofPDF uses forms with submit buttons for 'Download EPUB' or 'Download [EPUB]'
                epub_btn = page.locator("form[action*='epub'] input[type='submit'], button:has-text('EPUB'), a:has-text('Download EPUB'), input[value*='EPUB']")
                
                if epub_btn.count() == 0:
                    # fallback search
                    epub_btn = page.get_by_role("button", name=re.compile("EPUB", re.I))

                if epub_btn.count() == 0:
                    epub_btn = page.locator("input[value*='EPUB']")

                if epub_btn.count() > 0:
                    print("Found EPUB download trigger! Triggering download...")
                    with page.expect_download(timeout=60000) as download_info:
                        epub_btn.first.click()
                    
                    download = download_info.value
                    orig_filename = download.suggested_filename
                    temp_dest = download_dir / orig_filename
                    download.save_as(str(temp_dest))
                    print(f"✅ Downloaded: {orig_filename} ({temp_dest.stat().st_size:,} bytes)")

                    # Format standard name: [e] Title - Freida McFadden.epub
                    clean_name = orig_filename
                    if not clean_name.lower().startswith("[e]"):
                        clean_name = f"[e] {clean_name}"

                    target_file = DEST_DIR / clean_name
                    shutil.copy2(temp_dest, target_file)
                    print(f"📁 Saved to Library: {target_file}")
                    downloaded_files.append(target_file)
                    owned.add(normalize_title(raw_title))
                else:
                    print(f"⚠️ EPUB download button not found for {raw_title}")

                time.sleep(3)
            except Exception as e:
                print(f"❌ Failed to download {raw_title}: {e}")

        context.close()

    shutil.rmtree(temp_profile, ignore_errors=True)
    shutil.rmtree(download_dir, ignore_errors=True)

    print(f"\n🎉 Successfully downloaded {len(downloaded_files)} new Freida McFadden EPUBs!")
    return downloaded_files


if __name__ == "__main__":
    downloaded = run_downloader()
    print("Downloaded paths:", downloaded)
