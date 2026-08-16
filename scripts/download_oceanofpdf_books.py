#!/usr/bin/env python3
"""Automated EPUB downloader from OceanofPDF for top dark romance authors."""

from __future__ import annotations

import re
import sys
import time
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DEST_DIR = Path("/Users/hyeokjunkong/Desktop/소설2/new books from vk")
PROFILE_DIR = Path("/tmp/oceanofpdf_downloader_profile")

BOOKS_TO_DOWNLOAD = [
    ("Pepper Winters", "Tears of Tess"),
    ("Rina Kent", "God of Malice"),
    ("Keri Lake", "Nocticadia"),
    ("H.D. Carlton", "Haunting Adeline"),
    ("Penelope Douglas", "Corrupt"),
    ("C.J. Roberts", "Captive in the Dark"),
    ("Danielle Lori", "The Maddest Obsession"),
    ("Cora Reilly", "Bound by Honor"),
    ("Neva Altaj", "Painted Scars"),
    ("L.J. Shen", "Vicious"),
]


def clean_filename(title: str, author: str) -> str:
    name = f"{title} - {author}.epub"
    return re.sub(r'[\\/*?:"<>|]', "", name)


def solve_turnstile(page, max_wait_sec: int = 15) -> bool:
    for _ in range(max_wait_sec):
        title = page.title()
        if "잠시만" not in title and "Just a moment" not in title and len(title) > 0:
            return True
        for f in page.frames:
            if "challenges.cloudflare.com" in f.url or "turnstile" in f.url:
                try:
                    cb = f.query_selector('input[type="checkbox"], .ctp-checkbox-label, #challenge-stage')
                    if cb:
                        cb.click()
                except Exception:
                    pass
        time.sleep(1)
    return "잠시만" not in page.title()


def download_book(page, author: str, title: str) -> bool:
    print(f"\n==================================================", flush=True)
    print(f"[*] Processing: {title} by {author}", flush=True)
    
    final_name = clean_filename(title, author)
    save_path = DEST_DIR / final_name
    
    # Check if already exists in DEST_DIR and size > 50KB
    if save_path.exists() and save_path.stat().st_size > 50000:
        print(f"[+] Already downloaded: {save_path.name} ({save_path.stat().st_size / 1024 / 1024:.2f} MB)", flush=True)
        return True

    search_query = f"{title} {author}"
    search_url = f"https://oceanofpdf.com/?s={search_query.replace(' ', '+')}"
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        solve_turnstile(page)
        time.sleep(2)
    except Exception as e:
        print(f"[-] Search navigation error: {e}", flush=True)
        return False

    # Find article links
    articles = page.query_selector_all("article h2 a")
    if not articles:
        print(f"[-] No search results found for {title} by {author}", flush=True)
        return False

    # Pick best match
    target_link = None
    target_text = ""
    for a in articles:
        text = a.inner_text().strip()
        href = a.get_attribute("href")
        if title.lower() in text.lower():
            target_link = href
            target_text = text
            break
    if not target_link:
        target_link = articles[0].get_attribute("href")
        target_text = articles[0].inner_text().strip()

    print(f"[+] Found article: {target_text} -> {target_link}", flush=True)

    try:
        page.goto(target_link, wait_until="domcontentloaded", timeout=45000)
        solve_turnstile(page)
        time.sleep(2)
    except Exception as e:
        print(f"[-] Article navigation error: {e}", flush=True)
        return False

    # Parse HTML for the EPUB download form
    soup = BeautifulSoup(page.content(), "html.parser")
    epub_form = None
    for f in soup.find_all("form"):
        fn_input = f.find("input", {"name": "filename"})
        if fn_input and ".epub" in str(fn_input.get("value", "")).lower():
            epub_form = f
            break

    if not epub_form:
        print(f"[-] Could not find EPUB form on article page: {target_link}", flush=True)
        return False

    form_data = {}
    for inp in epub_form.find_all("input"):
        name = inp.get("name")
        val = inp.get("value")
        if name and val is not None:
            form_data[name] = val

    action_url = epub_form.get("action") or "https://oceanofpdf.com/Fetching_Resource.php"
    print(f"[+] Submitting resource fetch request for {form_data.get('filename')}...", flush=True)

    try:
        resp = page.request.post(action_url, form=form_data, headers={"Referer": page.url})
        if resp.status != 200:
            print(f"[-] POST failed with HTTP {resp.status}", flush=True)
            return False
        
        fetch_html = resp.text()
        
        # Look for meta refresh or fs direct link
        direct_url = None
        m = re.search(r'url=(https://fs\d*\.oceanofpdf\.com/[^"\s]+)', fetch_html)
        if m:
            direct_url = m.group(1).replace("&amp;", "&")
        else:
            m2 = re.search(r'(https://fs\d*\.oceanofpdf\.com/[^"\s\']+\.epub[^"\s\']*)', fetch_html)
            if m2:
                direct_url = m2.group(1).replace("&amp;", "&")

        if not direct_url:
            print(f"[-] Could not extract direct download URL from fetch response", flush=True)
            return False

        print(f"[+] Direct download URL: {direct_url}", flush=True)
        print(f"[*] Downloading binary EPUB...", flush=True)
        
        req = urllib.request.Request(
            direct_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://oceanofpdf.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            epub_bytes = response.read()

        if len(epub_bytes) < 10000:
            print(f"[-] Downloaded data too small ({len(epub_bytes)} bytes), possibly corrupt", flush=True)
            return False

        save_path.write_bytes(epub_bytes)
        print(f"[SUCCESS] Downloaded and verified: {save_path.name} ({len(epub_bytes) / 1024 / 1024:.2f} MB)", flush=True)
        return True

    except Exception as e:
        print(f"[-] Download failed with error: {e}", flush=True)
        return False


def main() -> int:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Target download directory: {DEST_DIR}", flush=True)
    print(f"Total books to download: {len(BOOKS_TO_DOWNLOAD)}", flush=True)

    success_count = 0
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--password-store=basic",
            ],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for author, title in BOOKS_TO_DOWNLOAD:
            ok = download_book(page, author, title)
            if ok:
                success_count += 1
            time.sleep(2)

        ctx.close()

    print(f"\n==================================================", flush=True)
    print(f"[SUMMARY] Successfully downloaded {success_count}/{len(BOOKS_TO_DOWNLOAD)} EPUBs to {DEST_DIR}", flush=True)
    return 0 if success_count == len(BOOKS_TO_DOWNLOAD) else 1


if __name__ == "__main__":
    raise SystemExit(main())
