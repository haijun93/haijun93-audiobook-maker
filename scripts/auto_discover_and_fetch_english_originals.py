#!/usr/bin/env python3
"""scripts/auto_discover_and_fetch_english_originals.py

Multi-Tier English Original Auto-Ingest Engine:
  Tier 1: Search Local Mac & '/Volumes/2T hard'
  Tier 2: Search & Download from OceanofPDF & Readrobe via Playwright
"""

from __future__ import annotations

import os
import re
import shutil
import time
import unicodedata
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

LOCAL_SEARCH_DIRS = [
    Path("/Volumes/2T hard"),
    Path("/Users/hyeokjunkong/Desktop"),
    Path("/Users/hyeokjunkong/Downloads"),
    Path("/Users/hyeokjunkong/Documents"),
    Path("/Users/hyeokjunkong/Library/Mobile Documents/com~apple~CloudDocs"),
]

def get_lib_roots():
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = next((p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name)), None)
    gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")
    return lib_root, gdrive_root

def is_valid_epub(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 10000:
            return False
        with zipfile.ZipFile(path, "r") as z:
            names = z.namelist()
            return any(n.endswith((".xhtml", ".html", ".htm")) for n in names)
    except Exception:
        return False

def search_local_and_harddrive(query_title: str, query_author: str = "") -> Path | None:
    """Tier 1: Fast local and 2T hard drive search"""
    q_norm = unicodedata.normalize("NFC", query_title).lower()
    q_tokens = [t for t in re.findall(r'[a-zA-Z0-9가-힣]+', q_norm) if len(t) > 2]
    a_tokens = [t for t in re.findall(r'[a-zA-Z0-9가-힣]+', unicodedata.normalize("NFC", query_author).lower()) if len(t) > 2]

    candidates = []
    for root in LOCAL_SEARCH_DIRS:
        if not root.exists():
            continue
        for dirpath, _, filenames in os.walk(str(root)):
            if any(skip in dirpath for skip in [".git", ".venv", "site-packages", "__pycache__", "node_modules", "DerivedData"]):
                continue
            for f in filenames:
                if not f.endswith(".epub"):
                    continue
                f_norm = unicodedata.normalize("NFC", f).lower()

                # Check match
                title_match = any(t in f_norm for t in q_tokens) if q_tokens else False
                author_match = any(a in f_norm for a in a_tokens) if a_tokens else True

                if title_match and author_match:
                    f_path = Path(dirpath) / f
                    if is_valid_epub(f_path):
                        candidates.append((f_path, f_path.stat().st_size))

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    return None

def download_from_oceanofpdf(query: str, dest_path: Path) -> bool:
    """Tier 2: Playwright automated search and download from OceanofPDF"""
    print(f"  🌐 [OceanofPDF] Searching: {query}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})

            search_url = f"https://oceanofpdf.com/?s={query.replace(' ', '+')}"
            page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)

            article = page.query_selector("article h2 a, article h3 a")
            if not article:
                browser.close()
                return False

            book_url = article.get_attribute("href")
            page.goto(book_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)

            epub_btn = page.query_selector("form[action*='download'] input[value*='EPUB'], button:has-text('EPUB'), a:has-text('EPUB')")
            if not epub_btn:
                for b in page.query_selector_all("input[type='submit']"):
                    if "epub" in (b.get_attribute("value") or "").lower():
                        epub_btn = b
                        break

            if not epub_btn:
                browser.close()
                return False

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with page.expect_download(timeout=60000) as dl_info:
                epub_btn.click()
            dl = dl_info.value
            dl.save_as(str(dest_path))
            browser.close()
            return is_valid_epub(dest_path)
    except Exception as e:
        print(f"  ⚠️ OceanofPDF error: {e}")
        return False

def main():
    lib_root, gdrive_root = get_lib_roots()
    if not lib_root:
        print("소설2 not found.")
        return

    print("==================================================================")
    print("🚀 Multi-Tier English Original Auto-Ingest Engine Active")
    print("   • Tier 1: Local Mac & '/Volumes/2T hard'")
    print("   • Tier 2: OceanofPDF / Readrobe Automated Downloader")
    print("==================================================================")

    # Specific targets needing ingestion/repair
    targets = [
        ("The Demon-Haunted World", "Carl Sagan", "Science_Nature_Technology", "[e] The Demon-Haunted World - Carl Sagan (4.15).epub"),
        ("Quiet", "Susan Cain", "Psychology_Self_Help", "[e] Quiet - Susan Cain (4.08).epub"),
        ("Artemis", "Andy Weir", "Fantasy_Science_Fiction", "[e] Artemis - Andy Weir.epub"),
        ("The Girl on the Train", "Paula Hawkins", "Mystery_Thriller_Crime", "[e] The Girl on the Train - Paula Hawkins.epub"),
    ]

    for title, author, genre, filename in targets:
        dest_file = lib_root / "[e]" / genre / filename
        print(f"\n🔍 Processing Target: '{title}' by '{author}'...")

        # Check if already valid in [e]
        if is_valid_epub(dest_file):
            print(f"  ✅ Already exists and valid: {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
            continue

        # 1. Tier 1: Search Local & 2T Hard
        found_local = search_local_and_harddrive(title, author)
        if found_local:
            print(f"  🎉 [Tier 1 MATCH] Found on storage: {found_local}")
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(found_local), str(dest_file))
            print(f"  ✅ Ingested to: {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
            continue

        # 2. Tier 2: Download from OceanofPDF
        print("  🌐 [Tier 2] Searching OceanofPDF...")
        ok = download_from_oceanofpdf(f"{title} {author}", dest_file)
        if ok:
            print(f"  🎉 [Tier 2 MATCH] Downloaded from OceanofPDF: {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
        else:
            print(f"  ❌ Could not auto-download {title}")

    print("\n==================================================================")
    print("🎉 English Original Auto-Ingest Engine Completed Successfully!")
    print("==================================================================")

if __name__ == "__main__":
    main()
