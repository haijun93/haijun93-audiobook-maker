#!/usr/bin/env python3
"""scripts/relocate_and_purge_all_nonstandard_folders.py

1. Relocates all valid Korean [k] books and other editions from `[e]`, `finished`, `non-english`
   into their proper canonical genre & author directories.
2. Purges the flawed non-English [k-e], [study], [e-s], [xteink] editions.
3. Completely deletes `[e]`, `finished`, and `non-english` directories across ALL library editions
   ([k], [k-e], [study], [e-s], [xteink]/[study], [xteink]/[e-s]).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

# Mapping of book title keywords to canonical genre & author folder
CANONICAL_TARGETS = [
    {
        "pattern": "hyperion",
        "genre": "Fantasy_Science_Fiction",
        "author_folder": "#Dan Simmons",
        "clean_title": "The Hyperion Cantos 4 Book Bundle - Dan Simmons (4.26)"
    },
    {
        "pattern": "daring greatly",
        "genre": "Psychology_Self_Help",
        "author_folder": "#Brené Brown",
        "clean_title": "Daring Greatly - Brené Brown (4.28)"
    },
    {
        "pattern": "meditation",
        "genre": "Classics",
        "author_folder": "#Marcus Aurelius",
        "clean_title": "Meditations - Marcus Aurelius (4.15)"
    },
    {
        "pattern": "mindset",
        "genre": "Psychology_Self_Help",
        "author_folder": "#Carol S. Dweck",
        "clean_title": "Mindset The New Psychology of Success - Carol S. Dweck (4.09)"
    },
    {
        "pattern": "time-block",
        "genre": "Business_Economics",
        "author_folder": "#Cal Newport",
        "clean_title": "The Time-Block Planner - Cal Newport (4.15)"
    },
    {
        "pattern": "the help",
        "genre": "Historical_Fiction",
        "author_folder": "#Kathryn Stockett",
        "clean_title": "The Help - Kathryn Stockett (4.47)"
    },
    {
        "pattern": "divine rivals",
        "genre": "Romance_Contemporary",
        "author_folder": "#Rebecca Ross",
        "clean_title": "Divine Rivals - Rebecca Ross (4.24)"
    },
    {
        "pattern": "sepuluh anak negro",
        "genre": "Mystery_Thriller_Crime",
        "author_folder": "#Agatha Christie",
        "clean_title": "And Then There Were None - Agatha Christie (4.28)"
    },
    {
        "pattern": "harry potter",
        "genre": "Fantasy_Science_Fiction",
        "author_folder": "#J.K. Rowling",
        "clean_title": "" # Keep base title
    },
    {
        "pattern": "outlander",
        "genre": "Historical_Fiction",
        "author_folder": "#Diana Gabaldon",
        "clean_title": "Outlander Dragonfly in Amber - Diana Gabaldon (4.26)"
    },
    {
        "pattern": "becoming",
        "genre": "Biography_Memoir",
        "author_folder": "#Michelle Obama",
        "clean_title": "Becoming - Michelle Obama (4.48)"
    },
    {
        "pattern": "alex leto",
        "genre": "Romance_Contemporary",
        "author_folder": "#Emily Henry",
        "clean_title": "People We Meet on Vacation - Emily Henry (4.15)"
    },
    {
        "pattern": "knihomolove",
        "genre": "Romance_Contemporary",
        "author_folder": "#Emily Henry",
        "clean_title": "Book Lovers - Emily Henry (4.15)"
    }
]

def clean_korean_filename(fname: str, target_clean: str) -> str:
    if target_clean:
        return f"[k] {target_clean}.epub"
    s = fname
    s = re.sub(r"^\[(k-e|k|study|e-s|e)\]\s*", "", s)
    s = re.sub(r"^\[e\]\s*", "", s)
    s = re.sub(r"(?i)\s*(czech|german|french|turkish|italian|indonesian)\s+edition", "", s)
    s = re.sub(r"\s+\(2\)", "", s)
    return f"[k] {s.strip()}"

def find_target_dir(fname: str) -> tuple[str, str, str]:
    fn_lower = fname.lower()
    for item in CANONICAL_TARGETS:
        if item["pattern"] in fn_lower:
            return item["genre"], item["author_folder"], item["clean_title"]
    return "Literary_General_Fiction", "#General Authors", ""

def relocate_and_purge():
    print("==================================================================")
    print("🚀 RELOCATING VALID [k] BOOKS & PURGING ALL NON-STANDARD FOLDERS")
    print("==================================================================")

    # 1. Relocate [k] Korean translations to standard genre folders
    k_root = LIB_ROOT / "[k]"
    for sub_name in ["[e]", "finished", "non-english"]:
        sub_dir = k_root / sub_name
        if sub_dir.exists():
            print(f"\n📂 Processing [k]/{sub_name}:")
            for epub_file in list(sub_dir.glob("*.epub")):
                genre, author_dir, clean_title = find_target_dir(epub_file.name)
                dest_dir = k_root / genre / author_dir
                dest_dir.mkdir(parents=True, exist_ok=True)

                new_fname = clean_korean_filename(epub_file.name, clean_title)
                dest_file = dest_dir / new_fname

                print(f"  📦 Moving [k]: {epub_file.name} -> {genre}/{author_dir}/{new_fname}")
                if not dest_file.exists() or dest_file.stat().st_size != epub_file.stat().st_size:
                    shutil.move(str(epub_file), str(dest_file))
                else:
                    epub_file.unlink()

    # 2. Relocate valid [k-e] / [study] / [e-s] books from `finished` and `[e]` if they are in English
    for edition_root in [LIB_ROOT / "[k-e]", LIB_ROOT / "[study]", LIB_ROOT / "[e-s]"]:
        if not edition_root.exists():
            continue
        ed_prefix = f"[{edition_root.name}]"
        for sub_name in ["[e]", "finished"]:
            sub_dir = edition_root / sub_name
            if sub_dir.exists():
                for epub_file in list(sub_dir.glob("*.epub")):
                    genre, author_dir, clean_title = find_target_dir(epub_file.name)
                    dest_dir = edition_root / genre / author_dir
                    dest_dir.mkdir(parents=True, exist_ok=True)

                    clean_name = re.sub(r"^\[(k-e|k|study|e-s|e)\]\s*", "", epub_file.name)
                    clean_name = re.sub(r"^\[e\]\s*", "", clean_name)
                    new_fname = f"{ed_prefix} {clean_name}"
                    dest_file = dest_dir / new_fname

                    print(f"  📦 Moving {edition_root.name}: {epub_file.name} -> {genre}/{author_dir}/{new_fname}")
                    if not dest_file.exists() or dest_file.stat().st_size != epub_file.stat().st_size:
                        shutil.move(str(epub_file), str(dest_file))
                    else:
                        epub_file.unlink()

    # 3. Purge flawed non-English [k-e], [study], [e-s], [xteink] editions
    for ed_path in [
        LIB_ROOT / "[k-e]" / "non-english",
        LIB_ROOT / "[study]" / "non-english",
        LIB_ROOT / "[e-s]" / "non-english",
        LIB_ROOT / "[xteink]" / "[study]" / "non-english",
        LIB_ROOT / "[xteink]" / "[e-s]" / "non-english",
    ]:
        if ed_path.exists():
            print(f"  🗑️ Purging flawed non-English edition files in {ed_path.relative_to(LIB_ROOT)}...")
            shutil.rmtree(ed_path, ignore_errors=True)

    # 4. Remove all empty `[e]`, `finished`, `non-english` directories across all edition roots
    all_edition_roots = [
        LIB_ROOT / "[k]",
        LIB_ROOT / "[k-e]",
        LIB_ROOT / "[study]",
        LIB_ROOT / "[e-s]",
        LIB_ROOT / "[xteink]" / "[study]",
        LIB_ROOT / "[xteink]" / "[e-s]",
    ]

    for ed in all_edition_roots:
        for sub_name in ["[e]", "finished", "non-english"]:
            target_p = ed / sub_name
            if target_p.exists():
                shutil.rmtree(target_p, ignore_errors=True)
                print(f"  ✨ Completely deleted: {target_p.relative_to(LIB_ROOT)}")

    # 5. Clean Google Drive #Books
    if GDRIVE_ROOT.exists():
        print("\n☁️ Synchronizing with Google Drive #Books...")
        for ed_name in ["[k]", "[k-e]", "[study]", "[e-s]", "[xteink]/[study]", "[xteink]/[e-s]"]:
            for sub_name in ["[e]", "finished", "non-english"]:
                g_target = GDRIVE_ROOT / ed_name / sub_name
                if g_target.exists():
                    shutil.rmtree(g_target, ignore_errors=True)
                    print(f"  ☁️ Deleted GDrive folder: {ed_name}/{sub_name}")

    print("\n==================================================================")
    print("🎉 ALL NON-STANDARD SUBFOLDERS SUCCESSFULLY ELIMINATED!")
    print("==================================================================")

if __name__ == "__main__":
    relocate_and_purge()
