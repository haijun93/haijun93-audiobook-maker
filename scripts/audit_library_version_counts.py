#!/usr/bin/env python3
"""scripts/audit_library_version_counts.py

Performs a rigorous, full-depth audit across the entire library to categorize
every single book into New-Version (AI Translation + AI Study Notes) vs
Old-Version (pre-August legacy / dictionary-free simple bilingual without authentic AI study notes).
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
STUDY_ROOT = LIB_ROOT / "[study]"
KE_ROOT = LIB_ROOT / "[k-e]"
K_ROOT = LIB_ROOT / "[k]"
ES_ROOT = LIB_ROOT / "[e-s]"
E_ROOT = LIB_ROOT / "[e]"

BACKUP_STUDY = LIB_ROOT / "[backup_data] 20260807" / "[study]"
WORK_ROOT = LIB_ROOT / "_chatgpt_translate_work"
STAGE_ROOT = LIB_ROOT / "_translation_stage" / "pam_general_translation"
TOP10_STUDY = STUDY_ROOT / "#Top 10 dark romance"


def clean_title(name: str) -> str:
    name = re.sub(r"^\[(study|k-e|k|e-s|e|s)\]\s*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\.epub$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\(\s*\d+\.\d+\s*\)", "", name)  # remove ratings like (4.20)
    name = re.sub(r"[\(\[\{].*?[\)\]\}]", "", name)
    name = re.sub(r"[^a-zA-Z0-9가-힣]", " ", name)
    return " ".join(name.lower().split())


def inspect_study_epub_for_authentic_notes(epub_path: Path) -> bool:
    if not epub_path.exists():
        return False
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            html_files = [n for n in z.namelist() if n.endswith((".xhtml", ".html", ".htm"))]
            found_notes = 0
            for name in html_files:
                if any(x in name.lower() for x in ["01", "02", "03", "chapter", "text", "sec", "part"]):
                    data = z.read(name).decode("utf-8", errors="ignore")
                    notes = re.findall(r"<span class=\"study-note\"[^>]*>(.*?)</span>", data)
                    found_notes += len(notes)
                    if found_notes >= 3:
                        return True
            return found_notes >= 3
    except Exception:
        return False


def main():
    print("==================================================================")
    print("🔎 FULL LIBRARY DEEP AUDIT: NEW-VERSION VS OLD-VERSION")
    print("==================================================================")

    # 1. Collect all books in library
    all_books = {}  # clean_key -> dict of edition paths

    for ed_name, ed_root in [("study", STUDY_ROOT), ("ke", KE_ROOT), ("k", K_ROOT), ("es", ES_ROOT)]:
        if not ed_root.exists():
            continue
        for p in ed_root.rglob("*.epub"):
            if any(x.startswith(".") for x in p.parts) or "[backup_data]" in str(p):
                continue
            key = clean_title(p.name)
            if not key:
                continue
            if key not in all_books:
                all_books[key] = {
                    "raw_name": p.stem,
                    "parent_rel": p.parent.relative_to(ed_root),
                    "study": None,
                    "ke": None,
                    "k": None,
                    "es": None,
                }
            all_books[key][ed_name] = p

    print(f"Total Unique Library Titles Discovered: {len(all_books)}")

    # 2. Known verified sources
    backup_study_keys = {clean_title(p.name) for p in BACKUP_STUDY.rglob("*.epub") if not any(x.startswith(".") for x in p.parts)}
    stage_keys = {clean_title(p.name) for p in STAGE_ROOT.rglob("*.epub") if not any(x.startswith(".") for x in p.parts)}
    top10_keys = {clean_title(p.name) for p in TOP10_STUDY.rglob("*.epub") if not any(x.startswith(".") for x in p.parts)}

    new_version_list = []
    old_version_list = []

    for key, info in sorted(all_books.items()):
        is_new = False
        reason = ""

        if key in backup_study_keys:
            is_new = True
            reason = "20260807 Backup [study] (179권 정본)"
        elif key in stage_keys:
            is_new = True
            reason = "_translation_stage Pam Godwin 완역본"
        elif key in top10_keys:
            is_new = True
            reason = "VK Top 10 Dark Romance 신버전 완역본"
        else:
            # Check if study epub exists and has genuine AI study notes
            study_p = info.get("study")
            if study_p and inspect_study_epub_for_authentic_notes(study_p):
                is_new = True
                reason = "Verified Authentic AI LLM Study Notes"

        display_name = re.sub(r"^\[(study|k-e|k|e-s|e|s)\]\s*", "", info["raw_name"]).strip()
        genre = str(info["parent_rel"])

        if is_new:
            new_version_list.append((genre, display_name, reason))
        else:
            old_version_list.append((genre, display_name))

    print("\n==================================================================")
    print(f"  🌟 신버전 번역본 (New Versions) : {len(new_version_list)} 권 ({len(new_version_list)/len(all_books)*100:.1f}%)")
    print(f"  📦 구버전 번역본 (Old Versions) : {len(old_version_list)} 권 ({len(old_version_list)/len(all_books)*100:.1f}%)")
    print(f"  📚 서재 내 번역본 총계          : {len(all_books)} 권")
    print("==================================================================")

    # Group old version books by genre
    old_by_genre = defaultdict(list)
    for g, name in old_version_list:
        old_by_genre[g].append(name)

    print("\n[구버전 번역본 장르별 분포]")
    for g, b_list in sorted(old_by_genre.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  • {g:35s}: {len(b_list):3d} 권")

    # Output detailed JSON report for inspection
    report_data = {
        "total_books": len(all_books),
        "new_version_count": len(new_version_list),
        "old_version_count": len(old_version_list),
        "old_version_by_genre": {g: sorted(l) for g, l in sorted(old_by_genre.items())},
    }
    Path("data/library_version_audit_report.json").write_text(json.dumps(report_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
