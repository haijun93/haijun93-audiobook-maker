#!/usr/bin/env python3
"""scripts/scan_korean_original_books.py

Scans all EPUBs in [e] and [k-e] to detect any pure Korean original books
that are NOT English-to-Korean translations.
"""

from __future__ import annotations

import os
import re
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")


def inspect_epub_language(epub_path: Path):
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            total_hangul = 0
            total_latin = 0
            sample_text = ""
            for name in z.namelist():
                if name.endswith((".xhtml", ".html", ".htm")):
                    data = z.read(name).decode("utf-8", errors="ignore")
                    h_cnt = len(re.findall(r"[가-힣]", data))
                    l_cnt = len(re.findall(r"[a-zA-Z]", data))
                    total_hangul += h_cnt
                    total_latin += l_cnt
                    if h_cnt > 30 and not sample_text:
                        clean = re.sub(r"<[^>]+>", " ", data)
                        sample_text = " ".join(clean.split())[:150]
                    if total_hangul > 2000:
                        break
            # If Korean text dominates or is substantial in original source
            if total_hangul > 200 and total_hangul > total_latin * 0.25:
                return {
                    "path": epub_path,
                    "rel_path": str(epub_path.relative_to(LIB_ROOT)),
                    "hangul": total_hangul,
                    "latin": total_latin,
                    "sample": sample_text,
                }
    except Exception:
        pass
    return None


def main():
    print("==================================================================")
    print("🔎 SCANNING ENTIRE LIBRARY FOR KOREAN ORIGINAL WORKS")
    print("==================================================================")

    e_files = [
        p for p in (LIB_ROOT / "[e]").rglob("*.epub")
        if not any(x.startswith(".") for x in p.parts) and "[backup_data]" not in str(p)
    ]
    print(f"Total [e] original EPUBs to inspect: {len(e_files)}")

    results = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        for res in executor.map(inspect_epub_language, e_files):
            if res:
                results.append(res)

    print(f"\n==================================================================")
    print(f"Discovered {len(results)} Korean original / non-English works in [e]:")
    print("==================================================================")
    for idx, r in enumerate(results, 1):
        print(f"{idx:2d}. 📖 {r['rel_path']}")
        print(f"    • 한글: {r['hangul']:,}자 | 영문: {r['latin']:,}자")
        print(f"    • 내용 샘플: {r['sample']}")
        print()


if __name__ == "__main__":
    main()
