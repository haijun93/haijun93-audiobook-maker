#!/usr/bin/env python3
"""Download all 10 authentic English EPUBs from OceanofPDF."""

from __future__ import annotations

import re
import time
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DEST_DIR = Path("/Users/hyeokjunkong/Desktop/소설2/new books from vk")
PROFILE_DIR = Path("/tmp/oceanofpdf_en_master_profile")

TARGET_BOOKS = [
    {
        "author": "Pepper Winters",
        "title": "Tears of Tess",
        "url": "https://oceanofpdf.com/authors/pepper-winters/pdf-epub-tears-of-tess-monsters-in-the-dark-1-download/",
        "out": "Tears of Tess - Pepper Winters.epub"
    },
    {
        "author": "Rina Kent",
        "title": "God of Malice",
        "url": "https://oceanofpdf.com/authors/rina-kent/pdf-epub-god-of-malice-legacy-of-gods-1-download/",
        "out": "God of Malice - Rina Kent.epub"
    },
    {
        "author": "Keri Lake",
        "title": "Nocticadia",
        "url": "https://oceanofpdf.com/authors/keri-lake/pdf-epub-nocticadia-download/",
        "out": "Nocticadia - Keri Lake.epub"
    },
    {
        "author": "H.D. Carlton",
        "title": "Haunting Adeline",
        "url": "https://oceanofpdf.com/authors/h-d-carlton/pdf-epub-haunting-adeline-download-71743508826/",
        "out": "Haunting Adeline - H.D. Carlton.epub"
    },
    {
        "author": "Penelope Douglas",
        "title": "Corrupt",
        "url": "https://oceanofpdf.com/authors/penelope-douglas/pdf-epub-corrupt-devils-night-1-download/",
        "out": "Corrupt - Penelope Douglas.epub"
    },
    {
        "author": "C.J. Roberts",
        "title": "Captive in the Dark",
        "url": "https://oceanofpdf.com/authors/c-j-roberts/pdf-epub-captive-in-the-dark-download/",
        "search": "Captive in the Dark CJ Roberts",
        "out": "Captive in the Dark - C.J. Roberts.epub"
    },
    {
        "author": "Danielle Lori",
        "title": "The Maddest Obsession",
        "url": "https://oceanofpdf.com/authors/danielle-lori/pdf-epub-the-maddest-obsession-made-2-download/",
        "out": "The Maddest Obsession - Danielle Lori.epub"
    },
    {
        "author": "Cora Reilly",
        "title": "Bound by Honor",
        "url": "https://oceanofpdf.com/authors/cora-reilly/pdf-epub-bound-by-honor-born-in-blood-mafia-chronicles-1-download/",
        "out": "Bound by Honor - Cora Reilly.epub"
    },
    {
        "author": "Neva Altaj",
        "title": "Painted Scars",
        "url": "https://oceanofpdf.com/authors/neva-altaj/pdf-epub-painted-scars-perfectly-imperfect-1-download/",
        "out": "Painted Scars - Neva Altaj.epub"
    },
    {
        "author": "L.J. Shen",
        "title": "Vicious",
        "url": "https://oceanofpdf.com/authors/l-j-shen/pdf-epub-vicious-sinners-of-saint-1-download/",
        "search": "Vicious Sinners of Saint LJ Shen",
        "out": "Vicious - L.J. Shen.epub"
    },
]


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


def download_target_book(page, item: dict) -> bool:
    author = item["author"]
    title = item["title"]
    out_name = item["out"]
    target_url = item.get("url")
    save_path = DEST_DIR / out_name

    print("\n==================================================", flush=True)
    print(f"[*] Processing: {title} by {author}", flush=True)

    # If file exists and > 500KB and does not contain Dutch/Spanish/Italian in EPUB content
    if save_path.exists() and save_path.stat().st_size > 100000:
        # Check if already verified english
        if item.get("verified_en"):
            print(f"[+] Already verified: {save_path.name} ({save_path.stat().st_size / 1024 / 1024:.2f} MB)", flush=True)
            return True

    # If URL given, navigate directly
    if target_url:
        print(f"[*] Navigating to direct URL: {target_url}", flush=True)
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            solve_turnstile(page)
            time.sleep(2)
        except Exception as e:
            print(f"[-] Direct navigation failed: {e}", flush=True)
            target_url = None

    # If direct navigation failed or 404, search
    if not target_url or "404" in page.title() or "Not Found" in page.title() or "잠시만" in page.title():
        search_query = item.get("search") or f"{title} {author}"
        search_url = f"https://oceanofpdf.com/?s={search_query.replace(' ', '+')}"
        print(f"[*] Searching: {search_url}", flush=True)
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            solve_turnstile(page)
            time.sleep(2)

            soup = BeautifulSoup(page.content(), "html.parser")
            articles = soup.select("article h2 a")
            target_link = None
            for a in articles:
                t_text = a.text.strip()
                href = a.get("href")
                # Filter out non-English editions
                if any(lang in t_text.lower() for lang in ["spanish", "french", "german", "italian", "dutch", "buch", "edicion"]):
                    continue
                if title.lower() in t_text.lower():
                    target_link = href
                    break
            if not target_link and articles:
                target_link = articles[0].get("href")

            if target_link:
                print(f"[+] Selected English article: {target_link}", flush=True)
                page.goto(target_link, wait_until="domcontentloaded", timeout=45000)
                solve_turnstile(page)
                time.sleep(2)
        except Exception as e:
            print(f"[-] Search failed: {e}", flush=True)
            return False

    # Find EPUB form
    soup = BeautifulSoup(page.content(), "html.parser")
    epub_form = None
    for f in soup.find_all("form"):
        fn_input = f.find("input", {"name": "filename"})
        if fn_input and ".epub" in str(fn_input.get("value", "")).lower():
            # Ensure not non-english edition
            val = str(fn_input.get("value", "")).lower()
            if not any(lang in val for lang in ["spanish", "french", "german", "italian", "dutch"]):
                epub_form = f
                break

    if not epub_form:
        # Fallback to any epub form
        for f in soup.find_all("form"):
            fn_input = f.find("input", {"name": "filename"})
            if fn_input and ".epub" in str(fn_input.get("value", "")).lower():
                epub_form = f
                break

    if not epub_form:
        print(f"[-] No EPUB form found on: {page.url}", flush=True)
        return False

    form_data = {}
    for inp in epub_form.find_all("input"):
        name = inp.get("name")
        val = inp.get("value")
        if name and val is not None:
            form_data[name] = val

    action_url = epub_form.get("action") or "https://oceanofpdf.com/Fetching_Resource.php"
    print(f"[+] Fetching EPUB for: {form_data.get('filename')}...", flush=True)

    try:
        resp = page.request.post(action_url, form=form_data, headers={"Referer": page.url})
        if resp.status != 200:
            print(f"[-] POST failed with HTTP {resp.status}", flush=True)
            return False

        fetch_html = resp.text()
        direct_url = None
        m = re.search(r'url=(https://fs\d*\.oceanofpdf\.com/[^"\s]+)', fetch_html)
        if m:
            direct_url = m.group(1).replace("&amp;", "&")
        else:
            m2 = re.search(r'(https://fs\d*\.oceanofpdf\.com/[^"\s\']+\.epub[^"\s\']*)', fetch_html)
            if m2:
                direct_url = m2.group(1).replace("&amp;", "&")

        if not direct_url:
            print("[-] Could not find direct URL in response", flush=True)
            return False

        print(f"[+] Downloading from direct link: {direct_url}", flush=True)
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
            print(f"[-] Corrupt/too small download: {len(epub_bytes)} bytes", flush=True)
            return False

        save_path.write_bytes(epub_bytes)
        print(f"[SUCCESS] Downloaded and verified: {save_path.name} ({len(epub_bytes) / 1024 / 1024:.2f} MB)", flush=True)
        return True

    except Exception as e:
        print(f"[-] Download error: {e}", flush=True)
        return False


def main() -> int:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    print("==================================================", flush=True)
    print(f"[*] Downloading 10 Dark Romance EPUBs to {DEST_DIR}", flush=True)
    print("==================================================", flush=True)

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

        for item in TARGET_BOOKS:
            ok = download_target_book(page, item)
            if ok:
                success_count += 1
            time.sleep(2)

        ctx.close()

    print("\n==================================================", flush=True)
    print(f"[FINAL SUMMARY] Successfully downloaded {success_count}/{len(TARGET_BOOKS)} EPUBs to {DEST_DIR}", flush=True)
    return 0 if success_count == len(TARGET_BOOKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
