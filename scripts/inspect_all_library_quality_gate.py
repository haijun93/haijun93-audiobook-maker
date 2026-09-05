#!/usr/bin/env python3
"""scripts/inspect_all_library_quality_gate.py

Executes Master Quality Gate inspection across ALL [study] EPUBs in `소설2/[study]`.
Generates a comprehensive audit report of:
1. Cover images & cover pages
2. 100% Valid XML TOC & chapter links
3. X-Ray Dossier attachments
4. Zero untranslated leaks in Korean spans
5. TOEIC 700+ to 990 target vocabulary compliance (Zero basic middle-school trivia)
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.master_quality_inspector import inspect_epub_quality

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
STUDY_DIR = LIB_ROOT / "[study]"

def inspect_single(ep_path_str: str) -> dict:
    p = Path(ep_path_str)
    res = inspect_epub_quality(p, "[study]")
    return {
        "path": str(p),
        "name": p.name,
        "passed": res.passed,
        "errors": res.errors,
        "warnings": res.warnings,
        "metrics": res.metrics
    }

def main():
    print("==================================================================")
    print("🛡️ MASTER PRE-PUBLISHING QUALITY GATE: FULL LIBRARY INSPECTION")
    print("==================================================================")

    epubs = [str(p) for p in STUDY_DIR.rglob("*.epub") if p.stat().st_size > 10000]
    print(f"📚 Inspecting {len(epubs):,} [study] EPUBs across the library (12 workers)...\n")

    start_t = time.time()
    passed_count = 0
    failed_count = 0

    total_rubies = 0
    total_leaks = 0
    total_basic_viol = 0

    failed_items = []

    with ProcessPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(inspect_single, p) for p in epubs]
        for fut in as_completed(futures):
            r = fut.result()
            m = r.get("metrics", {})
            total_rubies += m.get("total_rubies", 0)
            total_leaks += m.get("untranslated_ko_leaks", 0)
            total_basic_viol += m.get("basic_stoplist_violations", 0)

            if r["passed"]:
                passed_count += 1
            else:
                failed_count += 1
                failed_items.append(r)

    elapsed = time.time() - start_t

    print("\n==================================================================")
    print(f"📊 QUALITY GATE FINAL RESULTS (Elapsed: {elapsed:.1f}s)")
    print("==================================================================")
    print(f"  • Total Books Inspected   : {len(epubs):,} books")
    print(f"  • Quality Gate PASS (🟢)  : {passed_count:,} books ({(passed_count/len(epubs))*100:.1f}%)")
    print(f"  • Quality Gate FAIL (🚨)  : {failed_count:,} books")
    print(f"  • Total High-Yield Rubies : {total_rubies:,} TOEIC 700+ annotations")
    print(f"  • Middle-School Violations: {total_basic_viol:,} basic trivia words")
    print(f"  • Untranslated KO Leaks   : {total_leaks:,} untranslated sentences")
    print("==================================================================")

    if failed_items:
        print("\n🚨 Summary of Failed Items:")
        for item in failed_items[:10]:
            print(f"  ❌ {item['name'][:50]}")
            for err in item["errors"]:
                print(f"      -> {err}")

if __name__ == "__main__":
    main()
