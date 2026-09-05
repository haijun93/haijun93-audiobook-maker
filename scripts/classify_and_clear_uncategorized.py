#!/usr/bin/env python3
"""scripts/classify_and_clear_uncategorized.py

Classifies all books in `Uncategorized` across all editions into their canonical genre directories:
1. Divine Rivals / Ruthless Vows (Rebecca Ross) -> Romance_Contemporary/#Rebecca Ross/
2. Five Star Summer (Ella Monroe) -> Romance_Contemporary/#Ella Monroe/
3. The Five Star Weekend (Elin Hilderbrand) -> Romance_Contemporary/#Elin Hilderbrand/
4. Mad Mabel (Sally Hepworth) -> Mystery_Thriller_Crime/#Sally Hepworth/
5. Gödel, Escher, Bach (Douglas R. Hofstadter) -> Science_Nature_Technology/#Douglas R. Hofstadter/
6. The Selfish Gene (Richard Dawkins) -> Science_Nature_Technology/#Richard Dawkins/
7. Hyperion Cantos / Hyperion Tales (Dan Simmons) -> Fantasy_Science_Fiction/#Dan Simmons/
8. Pam Godwin books -> #Pam Godwin/

Then completely deletes all `Uncategorized` directories across all library editions and Google Drive.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

UNCATEGORIZED_BOOK_RULES = [
    {
        "keywords": ["divine rivals", "ruthless vows"],
        "target_rel": "Romance_Contemporary/#Rebecca Ross",
        "clean_title": "Divine Rivals - Rebecca Ross (4.24)",
    },
    {
        "keywords": ["five star summer", "ella monroe"],
        "target_rel": "Romance_Contemporary/#Ella Monroe",
        "clean_title": "Five Star Summer - Ella Monroe",
    },
    {
        "keywords": ["five star weekend", "five-star weekend", "elin hilderbrand"],
        "target_rel": "Romance_Contemporary/#Elin Hilderbrand",
        "clean_title": "The Five-Star Weekend - Elin Hilderbrand (4.01)",
    },
    {
        "keywords": ["mad mabel", "sally hepworth"],
        "target_rel": "Mystery_Thriller_Crime/#Sally Hepworth",
        "clean_title": "Mad Mabel - Sally Hepworth",
    },
    {
        "keywords": ["godel, escher, bach", "hofstadter"],
        "target_rel": "Science_Nature_Technology/#Douglas R Hofstadter",
        "clean_title": "Godel, Escher, Bach-An Eternal Golden Braid - Douglas R. Hofstadter (4.30)",
    },
    {
        "keywords": ["selfish gene", "richard dawkins"],
        "target_rel": "Science_Nature_Technology/#Richard Dawkins",
        "clean_title": "The Selfish Gene - Richard Dawkins (4.15)",
    },
    {
        "keywords": ["hyperion"],
        "target_rel": "Fantasy_Science_Fiction/#Dan Simmons",
        "clean_title": "", # Preserve stem
    },
    {
        "keywords": ["pam godwin", "godwin, pam", "unshackle", "dead of eve", "dominate"],
        "target_rel": "#Pam Godwin",
        "clean_title": "", # Preserve stem
    }
]


def match_rule(fname: str) -> dict | None:
    fn_lower = fname.lower()
    for rule in UNCATEGORIZED_BOOK_RULES:
        if any(kw in fn_lower for kw in rule["keywords"]):
            return rule
    return None


def clean_book_filename(fname: str, prefix: str, clean_override: str) -> str:
    if clean_override and not "hyperion" in fname.lower() and not "godwin" in fname.lower():
        return f"{prefix} {clean_override}.epub"
    s = fname
    s = re.sub(r"^(\[(k-e|k|study|e-s|e)\]\s*)+", "", s)
    s = re.sub(r"^\[e\]\s*", "", s)
    return f"{prefix} {s.strip()}"


def process_edition_uncategorized(ed_root: Path, prefix: str):
    uncat_dir = ed_root / "Uncategorized"
    if not uncat_dir.exists():
        return

    print(f"\n📂 Processing {ed_root.relative_to(LIB_ROOT)}/Uncategorized...")
    for epub_file in list(uncat_dir.rglob("*.epub")):
        rule = match_rule(epub_file.name)
        if not rule:
            # Fallback to general fiction
            target_rel = "Literary_General_Fiction/#General Authors"
            clean_t = ""
        else:
            target_rel = rule["target_rel"]
            clean_t = rule.get("clean_title", "")

        dest_dir = ed_root / target_rel
        dest_dir.mkdir(parents=True, exist_ok=True)

        new_name = clean_book_filename(epub_file.name, prefix, clean_t)
        dest_file = dest_dir / new_name

        print(f"  📦 Moving: {epub_file.name} -> {target_rel}/{new_name}")
        if not dest_file.exists() or dest_file.stat().st_size != epub_file.stat().st_size:
            shutil.move(str(epub_file), str(dest_file))
        else:
            epub_file.unlink()

    # Remove subfolders & uncat folder
    shutil.rmtree(uncat_dir, ignore_errors=True)
    print(f"  🗑️ Deleted Uncategorized directory: {ed_root.relative_to(LIB_ROOT)}/Uncategorized")


def main():
    print("==================================================================")
    print("🌟 CLASSIFYING ALL UNCATEGORIZED BOOKS & PURGING FOLDERS")
    print("==================================================================")

    editions = [
        (LIB_ROOT / "[k]", "[k]"),
        (LIB_ROOT / "[k-e]", "[k-e]"),
        (LIB_ROOT / "[study]", "[study]"),
        (LIB_ROOT / "[e-s]", "[e-s]"),
        (LIB_ROOT / "[e]", "[e]"),
        (LIB_ROOT / "[xteink]" / "[study]", "[study]"),
        (LIB_ROOT / "[xteink]" / "[e-s]", "[e-s]"),
    ]

    for ed_root, prefix in editions:
        process_edition_uncategorized(ed_root, prefix)

    # GDrive Purge
    if GDRIVE_ROOT.exists():
        print("\n☁️ Synchronizing with Google Drive #Books...")
        for ed_rel in ["[k]", "[k-e]", "[study]", "[e-s]", "[e]", "[xteink]/[study]", "[xteink]/[e-s]"]:
            g_uncat = GDRIVE_ROOT / ed_rel / "Uncategorized"
            if g_uncat.exists():
                shutil.rmtree(g_uncat, ignore_errors=True)
                print(f"  ☁️ Deleted GDrive folder: {ed_rel}/Uncategorized")

    print("\n==================================================================")
    print("🎉 ALL UNCATEGORIZED BOOKS SUCCESSFULLY CLASSIFIED & FOLDERS ELIMINATED!")
    print("==================================================================")


if __name__ == "__main__":
    main()
