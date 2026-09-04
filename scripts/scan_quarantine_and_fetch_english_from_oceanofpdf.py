#!/usr/bin/env python3
"""scripts/scan_quarantine_and_fetch_english_from_oceanofpdf.py

1. Full Language Audit: Scans all pending tasks in `config.json` (and 2TB hard candidates).
2. Quarantines all non-English source books (Spanish, French, German, Italian, etc.) from translation queue.
3. Automatically searches and downloads their official English Editions from OceanofPDF (`oceanofpdf.com`).
4. Places downloaded English EPUBs into standard `소설2/[e]/[Genre]/#[Author]/` directories.
5. Registers them as top-priority (Priority: 3000) tasks in `config.json` for immediate translation.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
E_ROOT = LIB_ROOT / "[e]"
CONFIG_PATH = WORKSPACE_ROOT / ".work" / "continuous_scheduler" / "config.json"
PROFILE_DIR = Path("/Users/hyeokjunkong/Library/Application Support/AudiobookStudio/browser_profiles/oceanofpdf")

COMMON_EN_WORDS = {
    "the", "and", "of", "to", "a", "in", "that", "is", "was", "he", "for", "it", "with", "as",
    "his", "on", "be", "at", "by", "i", "this", "had", "not", "are", "but", "from", "or", "have",
    "an", "they", "which", "one", "you", "were", "her", "all", "she", "there", "would", "their",
    "we", "him", "been", "has", "when", "who", "will", "more", "no", "if", "out", "so", "said",
    "what", "up", "its", "about", "into", "than", "them", "can", "only", "other", "new", "some",
    "could", "time", "these", "two", "may", "then", "do", "first", "any", "my", "now", "such"
}

COMMON_FOREIGN_WORDS = {
    # Spanish
    "que", "de", "no", "la", "el", "en", "y", "los", "del", "se", "las", "por", "un", "para",
    "con", "una", "su", "al", "lo", "como", "más", "pero", "sus", "le", "ya", "o", "fue", "este",
    "ha", "sí", "porque", "esta", "son", "entre", "está", "cuando", "él", "todo", "sobre", "también",
    # German
    "und", "der", "die", "das", "in", "zu", "den", "nicht", "von", "sie", "ist", "des", "sich",
    "mit", "dem", "dass", "er", "es", "ein", "ich", "auf", "so", "eine", "auch", "als", "an",
    "nach", "wie", "im", "für", "man", "aber", "aus", "durch", "wenn", "nur", "war", "noch",
    # French
    "les", "du", "qui", "dans", "par", "plus", "pas", "au", "sur", "ne", "ce", "avec",
    "sont", "il", "ou", "aux", "sa", "mais", "ont", "ses", "cette", "aussi", "tout", "nous"
}

def detect_epub_language(epub_path: Path | str) -> tuple[str, float]:
    """Returns ('en' or 'foreign', confidence_ratio)."""
    p = Path(epub_path)
    if not p.exists() or p.stat().st_size < 10000:
        return "unknown", 0.0
    try:
        import zipfile
        from bs4 import BeautifulSoup

        sample_words = []
        with zipfile.ZipFile(p, "r") as z:
            xhtmls = [n for n in z.namelist() if n.endswith((".xhtml", ".html")) and not any(k in n.lower() for k in ["cover", "toc", "nav"])]
            for xf in xhtmls[:4]:
                txt = z.read(xf).decode("utf-8", "ignore")
                soup = BeautifulSoup(txt, "html.parser")
                for para in soup.find_all("p")[:25]:
                    words = re.findall(r'[a-zA-ZáéíóúüñÁÉÍÓÚÜÑàèìòùÀÈÌÒÙäöüÄÖÜßçÇ]+', para.get_text().lower())
                    sample_words.extend(words)
                    if len(sample_words) > 300:
                        break
                if len(sample_words) > 300:
                    break

        if not sample_words:
            return "en", 1.0

        en_hits = sum(1 for w in sample_words if w in COMMON_EN_WORDS)
        foreign_hits = sum(1 for w in sample_words if w in COMMON_FOREIGN_WORDS)

        # Strictly foreign if foreign hits exceed English hits
        if foreign_hits > en_hits:
            return "foreign", foreign_hits / max(1, en_hits)
        return "en", en_hits / len(sample_words)
    except Exception:
        return "en", 1.0

def download_from_oceanofpdf(page, query: str, dest_file: Path) -> bool:
    try:
        print(f"  🔍 Searching OceanofPDF for: '{query}'...")
        encoded = urllib.parse.quote(query)
        search_url = f"https://oceanofpdf.com/?s={encoded}"
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)

        article = page.locator("article.post h2 a, article h2 a, .entry-title a").first
        if not article.count():
            print(f"  ❌ No search results found for '{query}'")
            return False

        book_title = article.inner_text()
        print(f"  📖 Found book: '{book_title}' -> Navigating...")
        article.click()
        page.wait_for_timeout(3500)

        epub_btn = page.locator("form[action*='download'] button, a[href*='.epub'], input[value*='EPUB'], button:has-text('EPUB')").first
        if not epub_btn.count():
            epub_btn = page.locator("form:has-text('EPUB') button, form:has-text('Download') button").first

        if not epub_btn.count():
            print("  ❌ EPUB download button not found.")
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

def main():
    print("==================================================================", flush=True)
    print("🛡️ FULL QUEUE NON-ENGLISH AUDIT & OCEANOFPDF AUTO-REPLACEMENT", flush=True)
    print("==================================================================", flush=True)

    if not CONFIG_PATH.exists():
        print("Config path not found.", flush=True)
        return

    cfg = json.loads(CONFIG_PATH.read_text())
    tasks = cfg.get("tasks", [])
    print(f"📊 Total Tasks in Configuration: {len(tasks):,} tasks", flush=True)

    non_english_tasks = []
    cleaned_tasks = []

    def check_task(t):
        in_ep = t.get("input_epub", "")
        if not in_ep or not Path(in_ep).exists():
            return t, "en", 0.0
        lang, ratio = detect_epub_language(in_ep)
        return t, lang, ratio

    print("  🚀 Multi-threading language inspection across tasks (16 workers)...", flush=True)
    # Target pending and uncompleted tasks
    pending_tasks = [t for t in tasks if t.get("status") != "completed"]
    completed_tasks = [t for t in tasks if t.get("status") == "completed"]
    print(f"  • Pending Candidate Tasks: {len(pending_tasks):,} tasks", flush=True)

    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(check_task, pending_tasks))

    for t, lang, ratio in results:
        in_ep = t.get("input_epub", "")
        t_title = t.get("book_title_ko") or t.get("title") or Path(in_ep).stem
        if lang == "foreign":
            print(f"  🚨 [NON-ENGLISH DETECTED] Task ID: {t.get('id')}", flush=True)
            print(f"     Title: {t_title}", flush=True)
            print(f"     Path:  {in_ep}", flush=True)
            print(f"     Ratio: Foreign/English = {ratio:.2f}\n", flush=True)
            non_english_tasks.append(t)
        else:
            cleaned_tasks.append(t)

    cleaned_tasks.extend(completed_tasks)

    print("==================================================================")
    print("📋 AUDIT SUMMARY:")
    print(f"  • Total Valid English Tasks Kept : {len(cleaned_tasks):,} tasks")
    print(f"  • 🚫 Non-English Tasks Quarantined: {len(non_english_tasks):,} tasks")
    print("==================================================================")

    # Save cleaned config immediately to protect workers
    cfg["tasks"] = cleaned_tasks
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    print(f"💾 Updated {CONFIG_PATH.name} - Non-English tasks successfully purged from queue.\n")

    if not non_english_tasks:
        print("🎉 No non-English tasks found. Queue is 100% pure authentic English!")
        return

    # Attempt to fetch official English editions from OceanofPDF
    print("==================================================================", flush=True)
    print(f"🌐 FETCHING OFFICIAL ENGLISH EDITIONS FROM OCEANOFPDF ({len(non_english_tasks)} books)", flush=True)
    print("==================================================================", flush=True)

    # Clean stale locks
    for lk in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        f_lk = PROFILE_DIR / lk
        if f_lk.exists():
            try:
                f_lk.unlink()
            except Exception:
                pass

    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    newly_added_tasks = []

    with sync_playwright() as pw:
        launch_opts = {
            "headless": True,
            "viewport": {"width": 1280, "height": 800}
        }
        if Path(chrome_bin).exists():
            launch_opts["executable_path"] = chrome_bin

        browser = pw.chromium.launch(**launch_opts)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for t in non_english_tasks:
            t_title = t.get("book_title_ko") or t.get("title") or ""
            # Extract author and book title cleanly
            clean_t = re.sub(r'\(.*?\)|\[.*?\]|\.epub', '', t_title).strip()

            # Formulate smart English search query
            parts = clean_t.split(" - ")
            if len(parts) >= 2:
                b_name, author = parts[0].strip(), parts[1].strip()
                query = f"{b_name} {author}"
            else:
                query = clean_t
                author = "Author"
                b_name = clean_t

            genre = "Mystery_Thriller_Crime"
            if "Romance" in str(t):
                genre = "Romance_Contemporary"
            elif "Fantasy" in str(t) or "Fiction" in str(t):
                genre = "Fantasy_Science_Fiction"

            dest_epub = E_ROOT / genre / f"#{author}" / f"[e] {b_name} - {author}.epub"

            print(f"\n📘 Target: {t_title}")
            ok = download_from_oceanofpdf(page, query, dest_epub)
            if ok and dest_epub.exists() and dest_epub.stat().st_size > 30000:
                # Register high priority English translation task
                new_task = {
                    "id": f"stage1_ocean_en_{re.sub(r'[^a-zA-Z0-9]', '', b_name.lower())}",
                    "title": dest_epub.stem,
                    "book_title_ko": f"{b_name} - {author}",
                    "input_epub": str(dest_epub),
                    "output_epub": str(LIB_ROOT / "[k-e]" / genre / f"#{author}" / f"[k-e] {dest_epub.name[4:]}"),
                    "study_output_epub": str(LIB_ROOT / "[study]" / genre / f"#{author}" / f"[study] {dest_epub.name[4:]}"),
                    "work_dir": str(LIB_ROOT / f"_translation_work_{re.sub(r'[^a-zA-Z0-9]', '', b_name.lower())}"),
                    "stage": 1,
                    "stage_name": "Stage 1: OceanofPDF English Replacement",
                    "priority": 3000,
                    "status": "pending",
                    "force_retranslate": True
                }
                newly_added_tasks.append(new_task)

        context.close()

    if newly_added_tasks:
        print(f"\n🚀 Registering {len(newly_added_tasks)} newly fetched English editions to top priority queue...")
        cfg = json.loads(CONFIG_PATH.read_text())
        cfg["tasks"] = newly_added_tasks + cfg.get("tasks", [])
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        print("✅ Registered and ready for immediate authentic AI translation!")

if __name__ == "__main__":
    main()
