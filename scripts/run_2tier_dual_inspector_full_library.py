#!/usr/bin/env python3
"""scripts/run_2tier_dual_inspector_full_library.py

Executes the 2-Tier Master Dual Inspector across ALL 4,095+ EPUBs in `소설2/`:
1. Tier 1: Master Quality Inspector (Structure, XML, Cover, TOC, Vocab Filter)
2. Tier 2: Ultimate Integrity Sentinel (Senior Inspector - 7 Zero-Tolerance Protocols)

Produces a comprehensive, real-time Dual Audit Integrity Report across all editions:
- `[study]`
- `[e-s]`
- `[k-e]`
- `[k]`
- `[xteink]/[study]`
- `[xteink]/[e-s]`
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
from audiobook_studio.ultimate_integrity_sentinel import conduct_ultimate_integrity_audit

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def dual_inspect_single_book(args: tuple[str, str]) -> dict:
    path_str, ed_name = args
    p = Path(path_str)

    # 1. Tier-1 Master Inspector
    t1_res = inspect_epub_quality(p, ed_name)

    # 2. Tier-2 Ultimate Sentinel
    t2_res = conduct_ultimate_integrity_audit(p, ed_name)

    both_passed = t1_res.passed and t2_res.passed

    return {
        "path": str(p),
        "name": p.name,
        "edition": ed_name,
        "t1_passed": t1_res.passed,
        "t2_passed": t2_res.passed,
        "both_passed": both_passed,
        "t1_errors": t1_res.errors,
        "t2_flaws": t2_res.critical_flaws,
        "rubies": t2_res.detailed_metrics.get("total_rubies", 0),
        "paragraphs": t2_res.detailed_metrics.get("total_paragraphs", 0),
        "broken_links": t2_res.detailed_metrics.get("broken_toc_links", 0),
        "xml_valid_count": t2_res.detailed_metrics.get("xml_files_checked", 0),
    }

def main():
    print("==================================================================")
    print("🏛️ 2-TIER MASTER DUAL INSPECTOR: FULL ALL-EDITION AUDIT INITIATED")
    print("   Tier 1: Master Quality Inspector & Auto-Healer")
    print("   Tier 2: Ultimate Integrity Sentinel (Senior Master Inspector)")
    print("==================================================================")

    target_tasks = []
    editions = ["[study]", "[e-s]", "[k-e]", "[k]", "[xteink]/[study_x]", "[xteink]/[e-s_x]"]

    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            files = [str(p) for p in ed_dir.rglob("*.epub") if p.stat().st_size > 15000]
            print(f"  📂 {ed:<20}: {len(files):>5,} valid EPUBs queued")
            for f in files:
                target_tasks.append((f, ed))

    print(f"\n🚀 Total Books Queued for 2-Tier Cross-Inspection: {len(target_tasks):,} books (16 workers)...\n")

    start_t = time.time()
    edition_stats = {ed: {"total": 0, "t1_pass": 0, "t2_pass": 0, "dual_pass": 0, "rubies": 0, "paras": 0} for ed in editions}
    total_dual_passed = 0
    total_failed = 0
    flaw_samples = []

    with ProcessPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(dual_inspect_single_book, t) for t in target_tasks]
        for fut in as_completed(futures):
            r = fut.result()
            ed = r["edition"]

            edition_stats[ed]["total"] += 1
            edition_stats[ed]["rubies"] += r["rubies"]
            edition_stats[ed]["paras"] += r["paragraphs"]

            if r["t1_passed"]:
                edition_stats[ed]["t1_pass"] += 1
            if r["t2_passed"]:
                edition_stats[ed]["t2_pass"] += 1

            if r["both_passed"]:
                total_dual_passed += 1
                edition_stats[ed]["dual_pass"] += 1
            else:
                total_failed += 1
                if len(flaw_samples) < 10:
                    flaw_samples.append(r)

    elapsed = time.time() - start_t

    print("\n==================================================================")
    print(f"📊 2-TIER MASTER DUAL INSPECTION: FINAL INTEGRITY REPORT (Elapsed: {elapsed:.1f}s)")
    print("==================================================================")
    print(f"  • Total Books Inspected         : {len(target_tasks):,} books")
    print(f"  • 🌟 2-Tier Digital Seal Granted: {total_dual_passed:,} books ({(total_dual_passed/len(target_tasks))*100:.1f}%)")
    print(f"  • 🚨 Dual-Inspector Rejections   : {total_failed:,} books")
    print("------------------------------------------------------------------")
    print(f"  {'Edition':<20} | {'Total':>6} | {'Tier 1':>6} | {'Tier 2':>6} | {'🌟 Dual Pass':>11} | {'Rubies':>10}")
    print("------------------------------------------------------------------")
    for ed, s in edition_stats.items():
        print(f"  {ed:<20} | {s['total']:>6,} | {s['t1_pass']:>6,} | {s['t2_pass']:>6,} | {s['dual_pass']:>11,} | {s['rubies']:>10,}")
    print("==================================================================")

    if flaw_samples:
        print("\n🚨 Representative Rejected Items for Review:")
        for item in flaw_samples[:5]:
            print(f"  ❌ [{item['edition']}] {item['name'][:50]}")
            if item["t1_errors"]:
                print(f"      -> [Tier 1 Errors] {item['t1_errors']}")
            if item["t2_flaws"]:
                print(f"      -> [Tier 2 Flaws]  {item['t2_flaws']}")

if __name__ == "__main__":
    main()
