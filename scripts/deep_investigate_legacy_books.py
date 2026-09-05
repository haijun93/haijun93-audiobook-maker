#!/usr/bin/env python3
"""scripts/deep_investigate_legacy_books.py
Investigates the exact translation origin, timestamp, engine signature, 
and translation quality characteristics of all books in the library.
"""

import zipfile
import re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime

lib_root = Path("/Users/hyeokjunkong/Desktop/소설2")
study_dir = lib_root / "[study]"
ke_dir = lib_root / "[k-e]"

books = []

# Scan all [k-e] and [study] books
for ep in sorted(ke_dir.rglob("*.epub")):
    if ep.name.startswith("._"):
        continue
    rel = ep.relative_to(ke_dir)
    mtime = datetime.fromtimestamp(ep.stat().st_mtime)

    # Analyze EPUB internals
    try:
        with zipfile.ZipFile(ep) as z:
            namelist = z.namelist()
            # Read content.opf
            opf_name = [n for n in namelist if n.endswith(".opf")]
            opf_content = ""
            creator = ""
            date = ""
            if opf_name:
                opf_content = z.read(opf_name[0]).decode("utf-8", "ignore")

            # Sample first chapter
            chap_files = [n for n in namelist if n.endswith((".xhtml", ".html")) and "nav" not in n.lower() and "cover" not in n.lower()]
            sample_ko = ""
            total_pairs = 0
            has_study_notes = False
            has_ruby = False
            has_deep_l_markers = False

            for c in chap_files[:3]:
                raw = z.read(c).decode("utf-8", "ignore")
                if "class=\"study-note\"" in raw or "class='study-note'" in raw:
                    has_study_notes = True
                if "<ruby>" in raw:
                    has_ruby = True
                if "deepl" in raw.lower() or "google" in raw.lower():
                    has_deep_l_markers = True

                soup = BeautifulSoup(raw, "html.parser")
                pairs = soup.find_all("p", class_="pair")
                total_pairs += len(pairs)
                if not sample_ko:
                    for p in pairs:
                        ko = p.find("span", class_="ko")
                        if ko and len(ko.get_text(strip=True)) > 20:
                            sample_ko = ko.get_text(strip=True)
                            break

            books.append({
                "path": str(rel),
                "mtime": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                "size_kb": round(ep.stat().st_size / 1024, 1),
                "pairs": total_pairs,
                "has_study_notes": has_study_notes,
                "has_ruby": has_ruby,
                "sample_ko": sample_ko[:80],
                "opf_snippet": opf_content[:300].replace("\n", " ")
            })
    except Exception as exc:
        books.append({
            "path": str(rel),
            "error": str(exc)
        })

print(f"Total examined [k-e] books: {len(books)}")

# Group by date / directory / patterns
by_folder = {}
for b in books:
    folder = b["path"].split("/")[0] if "/" in b["path"] else "root"
    by_folder.setdefault(folder, []).append(b)

print("\n=== BREAKDOWN BY SUBFOLDER IN [k-e] ===")
for folder, b_list in sorted(by_folder.items()):
    print(f"📁 {folder:35}: {len(b_list)} books")

# Check work directory matches in _chatgpt_translate_work
work_dir = Path("/Users/hyeokjunkong/Desktop/소설2/_chatgpt_translate_work")
work_dirs_list = [d.name for d in work_dir.glob("*") if d.is_dir()]
print(f"\nTotal work directories in _chatgpt_translate_work: {len(work_dirs_list)}")

# Find books that DO NOT have a modern work_dir in _chatgpt_translate_work
unmatched_in_work_dir = []
matched_in_work_dir = []

for b in books:
    b_name = Path(b["path"]).stem.lower()
    clean_stem = re.sub(r"[^a-z0-9]", "", b_name.replace("ke", "").replace("study", ""))

    found = False
    for wd in work_dirs_list:
        wd_clean = re.sub(r"[^a-z0-9]", "", wd.lower())
        if clean_stem in wd_clean or wd_clean in clean_stem:
            found = True
            break
    if found:
        matched_in_work_dir.append(b)
    else:
        unmatched_in_work_dir.append(b)

print("\n📊 TRANSLATION ORIGIN ANALYSIS:")
print(f"  • Matched with New AI Work Dirs (_chatgpt_translate_work) : {len(matched_in_work_dir)} books")
print(f"  • UNMATCHED (Originating from Legacy/External batch)      : {len(unmatched_in_work_dir)} books ⚠️")

print("\n--- SAMPLE OF THE ~200 LEGACY/UNMATCHED BOOKS ---")
for idx, b in enumerate(unmatched_in_work_dir[:35], 1):
    print(f"{idx:2}. [{b.get('mtime')}] {b['path']}")
    print(f"    Sample: \"{b.get('sample_ko')}\"")
