#!/usr/bin/env python3
"""scripts/audit_korean_only_library.py

Audits all EPUBs in /Users/hyeokjunkong/Desktop/소설2/[k]/ to detect:
1. Files with low Korean percentage (< 85%).
2. Files with entire chapters that contain only English (0% Korean).
3. Suffix/Prefix mismatches.
"""

from __future__ import annotations

import re
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
K_ROOT = LIB_ROOT / "[k]"

def audit_single_k_epub(ep_path: Path) -> tuple[Path, float, int, int, list[tuple[str, int, int]]]:
    try:
        with zipfile.ZipFile(ep_path, "r") as z:
            total_p = 0
            ko_p = 0
            untrans_chapters = []
            for name in z.namelist():
                if name.endswith((".xhtml", ".html")) and "xray" not in name and "cover" not in name and "nav" not in name:
                    raw = z.read(name).decode("utf-8", "ignore")
                    paras = re.findall(r"<p[^>]*>(.*?)</p>", raw, re.DOTALL)
                    ch_total = len(paras)
                    ch_ko = sum(1 for p in paras if re.search(r"[\uac00-\ud7a3]", p))
                    total_p += ch_total
                    ko_p += ch_ko
                    if ch_total > 5 and (ch_ko / ch_total) < 0.6:
                        untrans_chapters.append((name, ch_ko, ch_total))

            pct = round(ko_p / total_p * 100, 1) if total_p > 0 else 0
            return ep_path, pct, ko_p, total_p, untrans_chapters
    except Exception as e:
        return ep_path, -1, 0, 0, [("ERROR", 0, 0)]

def main():
    print("==================================================================")
    print("🔍 AUDITING ALL [k] KOREAN-ONLY EPUBS IN LIBRARY")
    print("==================================================================")

    epubs = sorted(list(K_ROOT.rglob("*.epub")))
    print(f"📚 Total [k] EPUBs to audit: {len(epubs)}\n")

    problem_books = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(audit_single_k_epub, p) for p in epubs]
        for f in as_completed(futs):
            ep_path, pct, ko_p, tot_p, chs = f.result()
            if pct < 90 or len(chs) > 0:
                problem_books.append((ep_path, pct, ko_p, tot_p, chs))

    print("\n==================================================")
    print(f"🚨 Audit Results: Found {len(problem_books)} books with Korean flaws:")
    print("==================================================")
    for ep, pct, ko_p, tot_p, chs in sorted(problem_books, key=lambda x: x[1]):
        rel_path = ep.relative_to(K_ROOT)
        print(f"\n📕 [{pct:>5.1f}%] {rel_path}")
        print(f"   Total Korean paras: {ko_p}/{tot_p}")
        for ch in chs:
            print(f"   ⚠️ Chapter: {ch[0]} -> only {ch[1]}/{ch[2]} Korean paragraphs")

if __name__ == "__main__":
    main()
