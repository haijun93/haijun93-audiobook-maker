#!/usr/bin/env python3
"""scripts/resolve_foreign_titles_to_english_and_download.py

Resolves foreign language book titles into their canonical English titles,
downloads the authentic English EPUB from OceanofPDF (`oceanofpdf.com`),
places them into standard `소설2/[e]/[Genre]/#[Author]/` directories,
and registers them as top-priority translation tasks.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
E_ROOT = LIB_ROOT / "[e]"
CONFIG_PATH = WORKSPACE_ROOT / ".work" / "continuous_scheduler" / "config.json"

CANONICAL_ENGLISH_MAP = [
    {
        "foreign_title": "La vérité sur l'affaire Harry Quebert",
        "author": "Joël Dicker",
        "english_query": "The Truth About the Harry Quebert Affair Joel Dicker",
        "target_name": "[e] The Truth About the Harry Quebert Affair - Joel Dicker (4.06).epub",
        "genre": "Mystery_Thriller_Crime",
        "author_folder": "#Joel Dicker"
    },
    {
        "foreign_title": "Il Trono di Spade 3",
        "author": "George R.R. Martin",
        "english_query": "A Storm of Swords George R.R. Martin",
        "target_name": "[e] A Storm of Swords - George R.R. Martin (4.55).epub",
        "genre": "Fantasy_Science_Fiction",
        "author_folder": "#George R.R. Martin"
    },
    {
        "foreign_title": "Elemente und Ursprünge totaler Herrschaft",
        "author": "Hannah Arendt",
        "english_query": "The Origins of Totalitarianism Hannah Arendt",
        "target_name": "[e] The Origins of Totalitarianism - Hannah Arendt (4.30).epub",
        "genre": "Nonfiction_History_Politics",
        "author_folder": "#Hannah Arendt"
    },
    {
        "foreign_title": "La désobéissance civile",
        "author": "Henry David Thoreau",
        "english_query": "Civil Disobedience Henry David Thoreau",
        "target_name": "[e] Civil Disobedience - Henry David Thoreau (3.90).epub",
        "genre": "Nonfiction_History_Politics",
        "author_folder": "#Henry David Thoreau"
    },
    {
        "foreign_title": "Las Venas Abiertas De América Latina",
        "author": "Eduardo Galeano",
        "english_query": "Open Veins of Latin America Eduardo Galeano",
        "target_name": "[e] Open Veins of Latin America - Eduardo Galeano (4.50).epub",
        "genre": "Nonfiction_History_Politics",
        "author_folder": "#Eduardo Galeano"
    },
    {
        "foreign_title": "El Psicoanalista",
        "author": "John Katzenbach",
        "english_query": "The Analyst John Katzenbach",
        "target_name": "[e] The Analyst - John Katzenbach (4.11).epub",
        "genre": "Mystery_Thriller_Crime",
        "author_folder": "#John Katzenbach"
    },
    {
        "foreign_title": "Discours sur les sciences et les arts",
        "author": "Jean-Jacques Rousseau",
        "english_query": "Discourse on the Sciences and the Arts Jean-Jacques Rousseau",
        "target_name": "[e] Discourse on the Sciences and the Arts - Jean-Jacques Rousseau (3.60).epub",
        "genre": "Nonfiction_History_Politics",
        "author_folder": "#Jean-Jacques Rousseau"
    }
]

def download_english_epub(page, item: dict) -> bool:
    dest_dir = E_ROOT / item["genre"] / item["author_folder"]
    dest_file = dest_dir / item["target_name"]

    if dest_file.exists() and dest_file.stat().st_size > 30000:
        print(f"  ✅ English edition already exists: {dest_file.name}")
        return True

    query = item["english_query"]
    print(f"  🔍 Searching OceanofPDF for: '{query}'...")
    try:
        encoded = urllib.parse.quote(query)
        search_url = f"https://oceanofpdf.com/?s={encoded}"
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)

        article = page.locator("article.post h2 a, article h2 a, .entry-title a").first
        if not article.count():
            print(f"  ❌ No results on OceanofPDF for '{query}'")
            return False

        book_title = article.inner_text()
        print(f"  📖 Found English book: '{book_title}' -> Navigating...")
        article.click()
        page.wait_for_timeout(3500)

        epub_btn = page.locator("form[action*='download'] button, a[href*='.epub'], input[value*='EPUB'], button:has-text('EPUB')").first
        if not epub_btn.count():
            epub_btn = page.locator("form:has-text('EPUB') button, form:has-text('Download') button").first

        if not epub_btn.count():
            print("  ❌ EPUB download button not found.")
            return False

        print("  ⬇️ Downloading English EPUB...")
        with page.expect_download(timeout=60000) as download_info:
            epub_btn.click()

        download = download_info.value
        dest_dir.mkdir(parents=True, exist_ok=True)
        download.save_as(str(dest_file))
        print(f"  🎉 Successfully Downloaded & Placed: {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        print(f"  ❌ Error downloading: {e}")
        return False

def main():
    print("==================================================================")
    print("🌐 CANONICAL ENGLISH TITLE RESOLVER & OCEANOFPDF DOWNLOADER")
    print("==================================================================")

    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    launch_opts = {"headless": True}
    if Path(chrome_bin).exists():
        launch_opts["executable_path"] = chrome_bin

    new_tasks = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_opts)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for item in CANONICAL_ENGLISH_MAP:
            print(f"\n📘 Foreign: '{item['foreign_title']}' ({item['author']}) ➔ English: '{item['english_query']}'")
            ok = download_english_epub(page, item)

            dest_file = E_ROOT / item["genre"] / item["author_folder"] / item["target_name"]
            if ok and dest_file.exists():
                b_name = item["target_name"].replace("[e] ", "").replace(".epub", "")
                t_id = f"stage1_ocean_en_{re.sub(r'[^a-zA-Z0-9]', '', b_name.lower())}"

                new_tasks.append({
                    "id": t_id,
                    "title": dest_file.stem,
                    "book_title_ko": b_name,
                    "input_epub": str(dest_file),
                    "output_epub": str(LIB_ROOT / "[k-e]" / item["genre"] / item["author_folder"] / f"[k-e] {dest_file.name[4:]}"),
                    "study_output_epub": str(LIB_ROOT / "[study]" / item["genre"] / item["author_folder"] / f"[study] {dest_file.name[4:]}"),
                    "work_dir": str(LIB_ROOT / f"_translation_work_{re.sub(r'[^a-zA-Z0-9]', '', b_name.lower())}"),
                    "stage": 1,
                    "stage_name": "Stage 1: OceanofPDF English Replacement",
                    "priority": 3000,
                    "status": "pending",
                    "force_retranslate": True
                })

        browser.close()

    if new_tasks and CONFIG_PATH.exists():
        print(f"\n🚀 Registering {len(new_tasks)} authentic English editions into top priority translation queue...")
        cfg = json.loads(CONFIG_PATH.read_text())
        existing_ids = {t.get("id") for t in cfg.get("tasks", [])}
        add_tasks = [t for t in new_tasks if t["id"] not in existing_ids]
        cfg["tasks"] = add_tasks + cfg.get("tasks", [])
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        print(f"✅ Successfully registered {len(add_tasks)} tasks to Priority 3000 in config.json!")

if __name__ == "__main__":
    main()
