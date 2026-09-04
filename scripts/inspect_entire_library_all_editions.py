#!/usr/bin/env python3
"""scripts/inspect_entire_library_all_editions.py

Executes Comprehensive Master Quality Gate Audit across ALL 4,000+ EPUBs in `소설2/`
including:
- `[study]`
- `[e-s]`
- `[k-e]`
- `[k]`
- `[xteink]/[study]`
- `[xteink]/[e-s]`

Checks:
1. Cover Image & 000-cover.xhtml
2. 100% Valid XML TOC & Chapter Navigation Points
3. X-Ray Dossier Completeness
4. Zero Untranslated English Leaks
5. TOEIC 700+ to 990 Target Vocabulary Compliance (Zero Basic Middle-School Trivia)
6. XML Well-Formedness across all internal files
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

def inspect_single_wrapper(args_tuple: tuple[str, str]) -> dict:
    ep_path_str, edition_name = args_tuple
    p = Path(ep_path_str)
    res = inspect_epub_quality(p, edition_name)
    return {
        "path": str(p),
        "name": p.name,
        "edition": edition_name,
        "passed": res.passed,
        "errors": res.errors,
        "warnings": res.warnings,
        "metrics": res.metrics
    }

def main():
    print("==================================================================")
    print("🛡️ MASTER QUALITY GATE: FULL ALL-EDITION LIBRARY INSPECTION")
    print("==================================================================")

    target_tasks = []
    editions = ["[study]", "[e-s]", "[k-e]", "[k]", "[xteink]/[study]", "[xteink]/[e-s]"]

    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            files = [str(p) for p in ed_dir.rglob("*.epub") if p.stat().st_size > 10000]
            print(f"  📂 {ed:<20}: {len(files):>5,} books queued")
            for f in files:
                target_tasks.append((f, ed))

    print(f"\n🚀 Total EPUBs queued for inspection: {len(target_tasks):,} books across 6 editions (16 workers)...\n")

    start_t = time.time()
    edition_stats = {ed: {"total": 0, "passed": 0, "failed": 0, "rubies": 0, "leaks": 0, "basic_viol": 0} for ed in editions}
    total_passed = 0
    total_failed = 0
    failed_samples = []

    with ProcessPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(inspect_single_wrapper, t) for t in target_tasks]
        for fut in as_completed(futures):
            r = fut.result()
            ed = r["edition"]
            m = r.get("metrics", {})

            edition_stats[ed]["total"] += 1
            edition_stats[ed]["rubies"] += m.get("total_rubies", 0)
            edition_stats[ed]["leaks"] += m.get("untranslated_ko_leaks", 0)
            edition_stats[ed]["basic_viol"] += m.get("basic_stoplist_violations", 0)

            if r["passed"]:
                total_passed += 1
                edition_stats[ed]["passed"] += 1
            else:
                total_failed += 1
                edition_stats[ed]["failed"] += 1
                if len(failed_samples) < 15:
                    failed_samples.append(r)

    elapsed = time.time() - start_t

    print("\n==================================================================")
    print(f"📊 FULL LIBRARY QUALITY AUDIT SUMMARY (Elapsed: {elapsed:.1f}s)")
    print("==================================================================")
    print(f"  • Grand Total Books Inspected : {len(target_tasks):,} books")
    print(f"  • Total Quality Gate PASS (🟢) : {total_passed:,} books ({(total_passed/len(target_tasks))*100:.1f}%)")
    print(f"  • Total Quality Gate FAIL (🚨) : {total_failed:,} books")
    print("------------------------------------------------------------------")
    print(f"  {'Edition':<20} | {'Total':>7} | {'Passed':>7} | {'Failed':>7} | {'Rubies':>10} | {'Leaks':>6}")
    print("------------------------------------------------------------------")
    for ed, s in edition_stats.items():
        print(f"  {ed:<20} | {s['total']:>7,} | {s['passed']:>7,} | {s['failed']:>7,} | {s['rubies']:>10,} | {s['leaks']:>6,}")
    print("==================================================================")

    if failed_samples:
        print("\n🚨 Representative Quality Gate Issue Samples:")
        for item in failed_samples[:8]:
            print(f"  ❌ [{item['edition']}] {item['name'][:50]}")
            for err in item["errors"]:
                print(f"      -> {err}")

if __name__ == "__main__":
    main()
