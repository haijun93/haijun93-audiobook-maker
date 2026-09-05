#!/usr/bin/env python3
"""scripts/handle_non_english_books.py

Scans for non-English source books, skips translation, searches and downloads
the official English edition from OceanofPDF, places it in the standard genre
directory in `소설2/[e]/`, updates the scheduler config, and purges non-standard
`non-english`, `finished`, and misplaced `[e]` subdirectories across all library editions.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
CONFIG_PATH = ROOT / ".work" / "continuous_scheduler" / "config.json"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "AudiobookStudio" / "browser_profiles" / "oceanofpdf"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

try:
    from webui.book_organizer import (
        guess_genre_online,
        guess_average_rating,
        extract_metadata_from_epub,
        clean_metadata_field,
        sanitize_filename_part,
        sanitize_folder_name,
        build_organized_filename,
    )
except ImportError:
    pass

# Language identifiers & keywords indicating non-English editions
NON_ENGLISH_KEYWORDS = [
    "german edition", "french edition", "czech edition", "turkish edition",
    "italian edition", "indonesian edition", "spanish edition", "russian edition",
    "portuguese edition", "polish edition", "dutch edition", "swedish edition",
    "japanese edition", "chinese edition", "deutsche ausgabe", "edition francaise",
    "edicion en espanol", "edizione italiana", "tome 1", "tome 2", "tome 3",
    "fenixuv rad", "princ dvoji krve", "ve zumruduanka", "sepuluh anak negro",
    "die hyperion gesange", "kameni mudrcu", "tajemna komnata", "vezen z azkabanu",
    "ohnivy pohar", "relikvie smrti"
]

NON_ENGLISH_LANG_CODES = {
    "de", "ger", "fr", "fra", "fre", "cs", "ces", "cze", "tr", "tur",
    "it", "ita", "id", "ind", "es", "spa", "ru", "rus", "pt", "por",
    "pl", "pol", "nl", "dut", "nld", "sv", "swe", "ja", "jpn", "zh", "zho", "chi"
}


def is_non_english_epub(epub_path: Path) -> tuple[bool, str]:
    """Inspects metadata, filename, and inner text sample to determine if EPUB is non-English."""
    fname_lower = epub_path.name.lower()

    # 1. Path check
    if "non-english" in str(epub_path).lower():
        return True, "Path contains 'non-english'"

    # 2. Filename keyword check
    for kw in NON_ENGLISH_KEYWORDS:
        if kw in fname_lower:
            return True, f"Filename contains keyword '{kw}'"

    # 3. EPUB Metadata & Text Analysis
    if not epub_path.is_file() or epub_path.stat().st_size < 100:
        return False, "Not a valid file"

    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            # Check OPF dc:language
            opf_names = [n for n in z.namelist() if n.lower().endswith(".opf")]
            if opf_names:
                opf_data = z.read(opf_names[0]).decode("utf-8", errors="replace")
                lang_match = re.search(r"<dc:language\b[^>]*>(.*?)</dc:language>", opf_data, re.IGNORECASE)
                if lang_match:
                    lang = lang_match.group(1).strip().lower()
                    lang_base = re.split(r"[-_]", lang)[0]
                    if lang_base in NON_ENGLISH_LANG_CODES:
                        return True, f"OPF dc:language='{lang}'"

            # Check inner sample text
            html_names = [n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")) and not n.lower().endswith(("toc.xhtml", "nav.xhtml"))]
            if html_names:
                sample_text = ""
                for h_name in html_names[:3]:
                    txt = z.read(h_name).decode("utf-8", errors="replace")
                    txt = re.sub(r"<[^>]+>", " ", txt)
                    sample_text += " " + txt
                    if len(sample_text) > 3000:
                        break

                # Check for prominent non-English stopwords
                words = re.findall(r"\b[a-zA-Z가-힣\u00C0-\u017F]+\b", sample_text.lower())
                if len(words) > 100:
                    de_words = sum(1 for w in words if w in {"der", "die", "das", "und", "ist", "nicht", "ein", "eine", "sie", "er"})
                    fr_words = sum(1 for w in words if w in {"le", "la", "les", "des", "est", "une", "dans", "pour", "avec", "sur"})
                    cs_words = sum(1 for w in words if w in {"se", "na", "že", "do", "byl", "byla", "jsem", "jste", "pro", "ale"})
                    it_words = sum(1 for w in words if w in {"il", "la", "le", "dei", "con", "per", "sono", "una", "che", "non"})
                    es_words = sum(1 for w in words if w in {"el", "la", "los", "las", "un", "una", "del", "que", "por", "para"})

                    max_foreign = max(de_words, fr_words, cs_words, it_words, es_words)
                    ratio = max_foreign / max(1, len(words[:500]))
                    if ratio > 0.05:
                        return True, f"Body text high foreign stopword ratio ({ratio:.1%})"
    except Exception:
        pass

    return False, "English or unidentified"


def sanitize_title_for_search(raw_title: str) -> tuple[str, str]:
    """Cleans foreign edition markers and extracts (cleaned_title, author)."""
    t = raw_title
    t = re.sub(r"^\[(k-e|k|study|e-s|e)\]\s*", "", t)
    t = re.sub(r"\(\d+\.\d+\)", "", t)
    t = re.sub(r"\(\d+\)", "", t)

    # Remove foreign edition markers
    for kw in NON_ENGLISH_KEYWORDS:
        t = re.sub(re.escape(kw), "", t, flags=re.IGNORECASE)

    t = re.sub(r"(?i)\b(german|french|czech|turkish|italian|indonesian|spanish|russian)\s+edition\b", "", t)
    t = re.sub(r"(?i)\b(tome\s*\d+|partie\s*\d+|band\s*\d+)\b", "", t)

    # Specific known title mappings
    title_overrides = {
        "die hyperion gesange": ("The Hyperion Cantos", "Dan Simmons"),
        "harry potter fenixuv rad": ("Harry Potter and the Order of the Phoenix", "J.K. Rowling"),
        "harry potter princ dvoji krve": ("Harry Potter and the Half-Blood Prince", "J.K. Rowling"),
        "harry potter ve zumruduanka yoldasligi": ("Harry Potter and the Order of the Phoenix", "J.K. Rowling"),
        "sepuluh anak negro": ("And Then There Were None", "Agatha Christie"),
        "outlander tome 2": ("Dragonfly in Amber", "Diana Gabaldon"),
        "the time-block planner": ("The Time-Block Planner", "Cal Newport"),
        "the help": ("The Help", "Kathryn Stockett"),
        "divine rivals": ("Divine Rivals", "Rebecca Ross"),
        "becoming": ("Becoming", "Michelle Obama"),
    }

    t_lower = t.lower()
    for key, (canon_title, canon_author) in title_overrides.items():
        if key in t_lower:
            return canon_title, canon_author

    if " - " in t:
        parts = t.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()

    return t.strip(), ""


def download_english_edition_from_oceanofpdf(title: str, author: str) -> Path | None:
    """Searches OceanofPDF using Playwright and downloads the authentic English EPUB."""
    from playwright.sync_api import sync_playwright

    search_query = f"{title} {author}".strip()
    print(f"  🔍 Searching OceanofPDF for English Edition: '{search_query}'...")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    download_dir = Path(tempfile.mkdtemp(prefix="ocean_dl_"))
    downloaded_file: Path | None = None

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                executable_path=CHROME_PATH,
                headless=True,
                accept_downloads=True,
                downloads_path=str(download_dir),
                args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
            )
            page = context.new_page()
            page.set_default_timeout(30000)

            search_url = f"https://oceanofpdf.com/?s={search_query.replace(' ', '+')}"
            page.goto(search_url, wait_until="domcontentloaded")
            time.sleep(3)

            articles = page.query_selector_all("article.post")
            if not articles:
                print(f"  ⚠️ No results found on OceanofPDF for '{search_query}'")
                context.close()
                return None

            first_link = None
            for art in articles[:4]:
                a_tag = art.query_selector("h2.title a, h2 a, a.entry-title-link")
                if a_tag:
                    txt = (a_tag.text_content() or "").lower()
                    href = a_tag.get_attribute("href")
                    first_link = href
                    print(f"  📖 Found OceanofPDF result: {txt}")
                    break

            if not first_link:
                context.close()
                return None

            page.goto(first_link, wait_until="domcontentloaded")
            time.sleep(3)

            epub_btn = page.query_selector("form[action*='oceanofpdf'] input[value*='EPUB'], a[href*='EPUB'], input[type='submit'][value*='EPUB']")
            if not epub_btn:
                epub_btn = page.query_selector("input[type='submit']")

            if not epub_btn:
                print("  ⚠️ EPUB download button not found on detail page")
                context.close()
                return None

            print("  ⬇️ Triggering EPUB download from OceanofPDF...")
            with page.expect_download(timeout=60000) as dl_info:
                epub_btn.click()
            download = dl_info.value

            target_path = download_dir / download.suggested_filename
            download.save_as(str(target_path))

            if target_path.exists() and target_path.stat().st_size > 1000:
                print(f"  ✅ Successfully downloaded: {target_path.name} ({target_path.stat().st_size:,} bytes)")
                downloaded_file = target_path
            context.close()
    except Exception as e:
        print(f"  ❌ OceanofPDF download exception: {e}")

    return downloaded_file


def relocate_to_standard_e_library(epub_path: Path, canon_title: str, canon_author: str) -> Path:
    """Classifies and places the downloaded English EPUB into 소설2/[e]/[Genre]/#[Author]/."""
    meta = extract_metadata_from_epub(epub_path)
    title = canon_title or meta.get("title") or epub_path.stem
    author = canon_author or meta.get("author") or "General Authors"

    genre = guess_genre_online(epub_path.name, {"title": title, "author": author})
    rating = guess_average_rating({"title": title, "author": author})

    genre_dir = LIB_ROOT / "[e]" / sanitize_folder_name(genre)
    author_folder = f"#{sanitize_folder_name(author)}" if not author.startswith("#") else sanitize_folder_name(author)
    dest_dir = genre_dir / author_folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    clean_t = sanitize_filename_part(clean_metadata_field(title))
    clean_a = sanitize_filename_part(clean_metadata_field(author))
    stem = f"[e] {clean_t} - {clean_a}"
    if rating:
        stem += f" ({rating:.2f})"
    dest_epub = dest_dir / f"{stem}.epub"

    shutil.copy2(epub_path, dest_epub)
    print(f"  📁 Placed English Original: {dest_epub.relative_to(LIB_ROOT)}")
    return dest_epub


def purge_non_standard_folders():
    """Purges misplaced `non-english`, `finished`, and `[e]` subfolders across all editions."""
    print("\n==================================================================")
    print("🧹 PURGING NON-STANDARD FOLDERS ACROSS ALL LIBRARY EDITIONS")
    print("==================================================================")

    editions = [
        LIB_ROOT / "[k]",
        LIB_ROOT / "[k-e]",
        LIB_ROOT / "[study]",
        LIB_ROOT / "[e-s]",
        LIB_ROOT / "[xteink]" / "[study_x]",
        LIB_ROOT / "[xteink]" / "[e-s_x]",
    ]

    targets = ["non-english", "finished", "[e]"]

    for ed in editions:
        if not ed.exists():
            continue
        for t in targets:
            sub = ed / t
            if sub.exists():
                files = list(sub.glob("*.epub"))
                if files:
                    print(f"  ⚠️ Deleting {len(files)} non-standard files in {sub.relative_to(LIB_ROOT)}:")
                    for f in files:
                        print(f"     - {f.name}")
                        try:
                            f.unlink()
                        except Exception as e:
                            print(f"       ❌ Failed to delete {f.name}: {e}")
                try:
                    sub.rmdir()
                    print(f"  🗑️ Removed empty directory: {sub.relative_to(LIB_ROOT)}")
                except Exception:
                    shutil.rmtree(sub, ignore_errors=True)
                    print(f"  🗑️ Force-removed directory tree: {sub.relative_to(LIB_ROOT)}")

    print("✅ Successfully purged non-standard folder remnants.")


def process_all_non_english():
    print("==================================================================")
    print("🚀 AUDITING & REPLACING NON-ENGLISH SOURCE BOOKS WITH ENGLISH ORIGINALS")
    print("==================================================================")

    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text())
        tasks = cfg.get("tasks", [])
        updated_tasks = []
        replaced_count = 0
        skipped_count = 0

        for task in tasks:
            in_path = Path(task.get("input_epub", ""))
            title = task.get("title", "")

            is_non_en, reason = is_non_english_epub(in_path)
            if not is_non_en and any(kw in title.lower() for kw in NON_ENGLISH_KEYWORDS):
                is_non_en = True
                reason = "Title matches non-English keyword"

            if is_non_en:
                print(f"\n⚠️ Detected Non-English Task: {title}")
                print(f"   Reason: {reason}")

                canon_title, canon_author = sanitize_title_for_search(title)
                print(f"   Target English Edition: '{canon_title}' by '{canon_author}'")

                existing_e = list((LIB_ROOT / "[e]").rglob(f"*{canon_title}*.epub")) if canon_title else []
                dl_file = None
                if existing_e:
                    dl_file = existing_e[0]
                    print(f"   ✨ Found existing English original in library: {dl_file.relative_to(LIB_ROOT)}")
                else:
                    dl_file = download_english_edition_from_oceanofpdf(canon_title, canon_author)
                    if dl_file:
                        dl_file = relocate_to_standard_e_library(dl_file, canon_title, canon_author)

                if dl_file and dl_file.exists():
                    genre = guess_genre_online(dl_file.name, {"title": canon_title, "author": canon_author})
                    author_folder = f"#{sanitize_folder_name(canon_author)}" if not canon_author.startswith("#") else sanitize_folder_name(canon_author)

                    target_ke = LIB_ROOT / "[k-e]" / sanitize_folder_name(genre) / author_folder / f"[k-e] {dl_file.name.replace('[e] ', '')}"
                    target_study = LIB_ROOT / "[study]" / sanitize_folder_name(genre) / author_folder / f"[study] {dl_file.name.replace('[e] ', '')}"

                    task["input_epub"] = str(dl_file)
                    task["output_epub"] = str(target_ke)
                    task["study_output_epub"] = str(target_study)
                    task["title"] = dl_file.name
                    task["book_title_ko"] = f"{canon_title} - {canon_author}"
                    task["priority"] = 1500
                    task["status"] = "pending"

                    print(f"   🔄 Successfully updated task to English original: {dl_file.name}")
                    updated_tasks.append(task)
                    replaced_count += 1
                else:
                    print("   ⏭️ Skipping non-English task (English original not found yet)")
                    skipped_count += 1
            else:
                updated_tasks.append(task)

        cfg["tasks"] = updated_tasks
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n📦 Config updated: {replaced_count} tasks converted to English originals, {skipped_count} skipped.")

    purge_non_standard_folders()


if __name__ == "__main__":
    process_all_non_english()
