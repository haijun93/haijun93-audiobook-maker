#!/usr/bin/env python3
"""scripts/count_pending_translations.py"""

import os
import re
import unicodedata
import zipfile
from pathlib import Path

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
hard_drive = Path("/Volumes/2T hard")

# 1. Gather all completed books in library [k-e]
ke_epubs = list((lib_root / "[k-e]").glob("**/*.epub"))
completed_keys = set()
for p in ke_epubs:
    clean_stem = re.sub(r'^\[k-e\]\s*', '', p.stem)
    clean_stem = re.sub(r'\(.*?\)', '', clean_stem)
    key = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean_stem.lower())
    if key:
        completed_keys.add(key)

print(f"Total Completed Books in Library [k-e]: {len(ke_epubs):,} (Unique titles: {len(completed_keys):,})")

# 2. Scan Candidate Source Directories
source_dirs = [
    ("Best 100 Master Collection", hard_drive / "best 100"),
    ("Best 100 Account2 Pool", hard_drive / "best 100 - account2"),
    ("English Books Collection", hard_drive / "English Books Collection"),
    ("External 2T Novel Pool", hard_drive / "소설"),
    ("Local [e] Original Edition", lib_root / "[e]"),
]

def is_valid_source_epub(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 30000 and path.name.endswith(".epub")

all_untranslated_books = {}
collection_stats = {}

for coll_name, sdir in source_dirs:
    if not sdir.exists():
        continue
    coll_total = 0
    coll_untranslated = 0
    
    for dirpath, _, filenames in os.walk(str(sdir)):
        if any(skip in dirpath for skip in [".git", ".venv", "_work", "site-packages", "__pycache__", "4account_"]):
            continue
        for f in filenames:
            if not f.endswith(".epub"):
                continue
            if f.startswith(("[k]", "[k-e]", "[study]")):
                continue
                
            f_path = Path(dirpath) / f
            if not is_valid_source_epub(f_path):
                continue
                
            coll_total += 1
            clean_stem = re.sub(r'^\[e\]\s*', '', f_path.stem)
            clean_stem = re.sub(r'\(.*?\)', '', clean_stem)
            key = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean_stem.lower())
            
            # Check if key is completed
            is_completed = False
            for ck in completed_keys:
                if key and ck and (key == ck or (len(key) > 8 and key in ck) or (len(ck) > 8 and ck in key)):
                    is_completed = True
                    break
                    
            if not is_completed:
                coll_untranslated += 1
                if key not in all_untranslated_books:
                    all_untranslated_books[key] = {
                        "name": f_path.name,
                        "path": str(f_path),
                        "collection": coll_name,
                        "size": f_path.stat().st_size,
                        "rel": str(f_path.relative_to(sdir))
                    }
                    
    collection_stats[coll_name] = {
        "total": coll_total,
        "untranslated": coll_untranslated
    }

print("\n==================================================================")
print("📊 DETAILED BREAKDOWN OF PENDING TRANSLATION SOURCES")
print("==================================================================")
for cname, st in collection_stats.items():
    print(f"  📁 {cname:30s}: Total {st['total']:4d} EPUBs | Pending Translation: {st['untranslated']:4d} books")

active_translating = [
    ("ChatGPT", "A Little Life - Hanya Yanagihara (4.33)", "92/111 chunks (82.9%)"),
    ("Gemini 1", "World Without End - Ken Follett (4.33)", "Active In Progress"),
    ("Gemini 2", "The Pillars of the Earth - Ken Follett (4.33)", "Active In Progress"),
    ("Gemini 3", "The Book Thief - Markus Zusak (4.39)", "Active In Progress")
]

print("\n==================================================================")
print(f"🎯 SUMMARY OF PENDING TRANSLATION TASKS")
print(f"   • Total Unique Master Originals Awaiting Translation : {len(all_untranslated_books):,} books")
print(f"   • Currently Active in 4 AI LLM Workers              : {len(active_translating):,} books")
print(f"   • Queued in Supervisor for Next Auto-Assignment     : {len(all_untranslated_books) - len(active_translating):,} books")
print("==================================================================")

print("\n--- ⚡ TOP PRIORITY UPCOMING BOOKS IN TRANSLATION QUEUE ---")
for i, (k, b) in enumerate(list(all_untranslated_books.items())[:15], 1):
    print(f"{i:2d}. [{b['collection']}] {b['name']} ({b['size']:,} bytes)")
