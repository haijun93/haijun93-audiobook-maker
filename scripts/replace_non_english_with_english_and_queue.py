#!/usr/bin/env python3
"""scripts/replace_non_english_with_english_and_queue.py

1. Identifies all canonical English titles for previous non-English works.
2. Checks whether their English EPUBs already exist in `소설2/[e]/` or if they need to be fetched via OceanofPDF.
3. Automatically downloads any missing English EPUBs from OceanofPDF.
4. Places them into canonical `소설2/[e]/[Genre]/#[Author]/` paths.
5. Registers them as high-priority translation tasks in `config.json` so workers will produce authentic 4-editions ([k], [k-e], [study], [e-s]).
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
E_ROOT = LIB_ROOT / "[e]"
CONFIG_PATH = Path(__file__).resolve().parents[1] / ".work" / "continuous_scheduler" / "config.json"
PROFILE_DIR = Path("/Users/hyeokjunkong/Library/Application Support/AudiobookStudio/browser_profiles/oceanofpdf")

TARGET_REPLACEMENTS = [
    {
        "search_query": "And Then There Were None Agatha Christie",
        "author": "Agatha Christie",
        "genre": "Mystery_Thriller_Crime",
        "author_folder": "#Agatha Christie",
        "target_english_title": "[e] And Then There Were None - Agatha Christie (4.28).epub",
        "book_title_ko": "그리고 아무도 없었다 - 애거서 크리스티 (4.28)",
        "priority": 3000
    },
    {
        "search_query": "Harry Potter and the Half Blood Prince JK Rowling",
        "author": "J.K. Rowling",
        "genre": "Fantasy_Science_Fiction",
        "author_folder": "#J.K. Rowling",
        "target_english_title": "[e] Harry Potter and the Half-Blood Prince - J.K. Rowling (4.63).epub",
        "book_title_ko": "해리 포터와 혼혈 왕자 - J.K. 롤링 (4.63)",
        "priority": 3000
    },
    {
        "search_query": "Harry Potter and the Order of the Phoenix JK Rowling",
        "author": "J.K. Rowling",
        "genre": "Fantasy_Science_Fiction",
        "author_folder": "#J.K. Rowling",
        "target_english_title": "[e] Harry Potter and the Order of the Phoenix - J.K. Rowling (4.63).epub",
        "book_title_ko": "해리 포터와 불사조 기사단 - J.K. 롤링 (4.63)",
        "priority": 3000
    },
    {
        "search_query": "People We Meet on Vacation Emily Henry",
        "author": "Emily Henry",
        "genre": "Romance_Contemporary",
        "author_folder": "#Emily Henry",
        "target_english_title": "[e] People We Meet on Vacation - Emily Henry (4.15).epub",
        "book_title_ko": "우리가 휴가 중에 만난 사람들 - 에밀리 헨리 (4.15)",
        "priority": 3000
    },
    {
        "search_query": "Book Lovers Emily Henry",
        "author": "Emily Henry",
        "genre": "Romance_Contemporary",
        "author_folder": "#Emily Henry",
        "target_english_title": "[e] Book Lovers - Emily Henry (4.15).epub",
        "book_title_ko": "북 러버스 - 에밀리 헨리 (4.15)",
        "priority": 3000
    },
    {
        "search_query": "Divine Rivals Rebecca Ross",
        "author": "Rebecca Ross",
        "genre": "Romance_Contemporary",
        "author_folder": "#Rebecca Ross",
        "target_english_title": "[e] Divine Rivals - Rebecca Ross (4.24).epub",
        "book_title_ko": "디바인 라이벌스 - 레베카 로스 (4.24)",
        "priority": 3000
    },
    {
        "search_query": "Dragonfly in Amber Diana Gabaldon",
        "author": "Diana Gabaldon",
        "genre": "Historical_Fiction",
        "author_folder": "#Diana Gabaldon",
        "target_english_title": "[e] Dragonfly in Amber - Diana Gabaldon (4.26).epub",
        "book_title_ko": "호박 속의 잠자리 (아웃랜더 2부) - 다이애나 개벌돈 (4.26)",
        "priority": 3000
    },
    {
        "search_query": "Hyperion Dan Simmons",
        "author": "Dan Simmons",
        "genre": "Fantasy_Science_Fiction",
        "author_folder": "#Dan Simmons",
        "target_english_title": "[e] The Hyperion Cantos 4-Book Bundle - Dan Simmons (4.26).epub",
        "book_title_ko": "하이페리온 칸토스 4부작 합본 - 댄 시먼스 (4.26)",
        "priority": 3000
    },
    {
        "search_query": "Becoming Michelle Obama",
        "author": "Michelle Obama",
        "genre": "Biography_Memoir",
        "author_folder": "#Michelle Obama",
        "target_english_title": "[e] Becoming - Michelle Obama (4.48).epub",
        "book_title_ko": "비커밍 - 미셸 오바마 (4.48)",
        "priority": 3000
    },
    {
        "search_query": "Allegiant Veronica Roth",
        "author": "Veronica Roth",
        "genre": "Young_Adult_Children",
        "author_folder": "#Veronica Roth",
        "target_english_title": "[e] Allegiant (Divergent Book 3) - Veronica Roth (4.15).epub",
        "book_title_ko": "얼리전트 (다이버전트 3부) - 베로니카 로스 (4.15)",
        "priority": 3000
    },
    {
        "search_query": "Insurgent Veronica Roth",
        "author": "Veronica Roth",
        "genre": "Young_Adult_Children",
        "author_folder": "#Veronica Roth",
        "target_english_title": "[e] Insurgent (Divergent Book 2) - Veronica Roth (4.15).epub",
        "book_title_ko": "인서전트 (다이버전트 2부) - 베로니카 로스 (4.15)",
        "priority": 3000
    },
    {
        "search_query": "Divergent Veronica Roth",
        "author": "Veronica Roth",
        "genre": "Young_Adult_Children",
        "author_folder": "#Veronica Roth",
        "target_english_title": "[e] Divergent (Divergent Book 1) - Veronica Roth (4.15).epub",
        "book_title_ko": "다이버전트 (다이버전트 1부) - 베로니카 로스 (4.15)",
        "priority": 3000
    },
    {
        "search_query": "Voracious Leigh Rivers",
        "author": "Leigh Rivers",
        "genre": "#Leigh Rivers",
        "author_folder": "",
        "target_english_title": "[e] Voracious - Leigh Rivers.epub",
        "book_title_ko": "보레이셔스 - 리 리버스",
        "priority": 3000
    }
]

def find_existing_english_file(target: dict) -> Path | None:
    # 1. Search in target folder
    if target["author_folder"]:
        dest_dir = E_ROOT / target["genre"] / target["author_folder"]
    else:
        dest_dir = E_ROOT / target["genre"]

    if dest_dir.exists():
        exact = dest_dir / target["target_english_title"]
        if exact.exists() and exact.stat().st_size > 50000:
            return exact

    # 2. Search entire [e] for query keywords
    kw = target["search_query"].split()[0].lower()
    for f in E_ROOT.rglob("*.epub"):
        if kw in f.name.lower():
            if target["author"].lower().split()[-1] in f.name.lower():
                return f
    return None

def download_from_oceanofpdf(page, query: str, dest_file: Path) -> bool:
    try:
        print(f"  🔍 Searching OceanofPDF for: '{query}'...")
        encoded = urllib.parse.quote(query)
        search_url = f"https://oceanofpdf.com/?s={encoded}"
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # Click first article link
        article = page.locator("article.post h2 a, article h2 a, .entry-title a").first
        if not article.count():
            print(f"  ❌ No search results found for '{query}'")
            return False

        book_title = article.inner_text()
        print(f"  📖 Found book: '{book_title}' -> Navigating...")
        article.click()
        page.wait_for_timeout(4000)

        # Look for EPUB download button
        epub_btn = page.locator("form[action*='download'] button, a[href*='.epub'], input[value*='EPUB'], button:has-text('EPUB')").first
        if not epub_btn.count():
            # Try finding any form with epub
            epub_btn = page.locator("form:has-text('EPUB') button, form:has-text('Download') button").first

        if not epub_btn.count():
            print("  ❌ EPUB download button not found on book page.")
            return False

        print("  ⬇️ Triggering EPUB download...")
        with page.expect_download(timeout=60000) as download_info:
            epub_btn.click()

        download = download_info.value
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        download.save_as(str(dest_file))
        print(f"  ✅ Downloaded successfully to: {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        print(f"  ❌ Error downloading '{query}': {e}")
        return False

def register_task_in_config(target: dict, english_epub: Path):
    if not CONFIG_PATH.exists():
        return

    cfg = json.loads(CONFIG_PATH.read_text())
    tasks = cfg.get("tasks", [])

    tid = f"stage1_replace_non_en_{re.sub(r'[^a-zA-Z0-9]', '', target['target_english_title'].lower())}"

    # Check if already in queue
    for t in tasks:
        if t.get("id") == tid:
            print(f"  ℹ️ Task '{tid}' is already queued.")
            return

    if target["author_folder"]:
        rel_genre = f"{target['genre']}/{target['author_folder']}"
    else:
        rel_genre = target["genre"]

    clean_stem = english_epub.name.replace("[e] ", "").replace(".epub", "")
    tid_clean = re.sub(r'[^a-zA-Z0-9_]', '', tid)

    new_task = {
        "id": tid,
        "input_epub": str(english_epub),
        "output_epub": str(LIB_ROOT / "[k-e]" / rel_genre / f"[k-e] {clean_stem}.epub"),
        "study_output_epub": str(LIB_ROOT / "[study]" / rel_genre / f"[study] {clean_stem}.epub"),
        "work_dir": str(LIB_ROOT / f"_translation_work_{tid_clean}"),
        "book_title_ko": target["book_title_ko"],
        "stage": 1,
        "priority": target["priority"],
        "max_chars_per_chunk": 6000,
        "request_timeout_sec": 1200,
        "web_max_attempts": 3,
        "chunks_per_conversation": 10,
        "inter_request_delay_sec": 8.0,
        "force_retranslate": True
    }

    # Prepend to top of queue
    tasks.insert(0, new_task)
    cfg["tasks"] = tasks
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    print(f"  🚀 Queued high-priority retranslation task: '{new_task['book_title_ko']}' (Priority {new_task['priority']})")

def main():
    print("==================================================================")
    print("🌟 NON-ENGLISH REPLACEMENT & HIGH-PRIORITY RE-TRANSLATION PIPELINE")
    print("==================================================================")

    missing_targets = []
    for item in TARGET_REPLACEMENTS:
        existing = find_existing_english_file(item)
        if existing:
            print(f"✅ Found English edition on disk: {existing.name}")
            register_task_in_config(item, existing)
        else:
            print(f"⬇️ Needs OceanofPDF download: '{item['search_query']}'")
            missing_targets.append(item)

    if missing_targets:
        print(f"\n🌐 Launching Playwright to download {len(missing_targets)} missing English books from OceanofPDF...")
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=True,
                channel="chrome",
                args=["--password-store=basic"]
            )
            page = context.new_page()

            for item in missing_targets:
                if item["author_folder"]:
                    dest_file = E_ROOT / item["genre"] / item["author_folder"] / item["target_english_title"]
                else:
                    dest_file = E_ROOT / item["genre"] / item["target_english_title"]

                if download_from_oceanofpdf(page, item["search_query"], dest_file):
                    register_task_in_config(item, dest_file)
                time.sleep(3)

            context.close()

    print("\n==================================================================")
    print("🎉 ALL ENGLISH EDITIONS ACQUIRED & QUEUED FOR MASTER TRANSLATION!")
    print("==================================================================")

if __name__ == "__main__":
    main()
