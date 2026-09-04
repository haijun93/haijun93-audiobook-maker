#!/usr/bin/env python3
"""scripts/run_3tier_master_inspector_full_library.py

Executes the 3-Tier Master Inspector Team across ALL EPUBs in `소설2/`:
1. Inspector 1: Tier 1 Master Quality Inspector (Structure, XML, Cover, TOC, Vocab Filter)
2. Inspector 2: Tier 2 Ultimate Integrity Sentinel (Senior Inspector - 7 Zero-Tolerance Protocols)
3. Inspector 3: Tier 3 Visual Screen Sentinel (Playwright Chromium Screen Capture - 10 to 20 pages)

Produces a comprehensive, real-time 3-Tier Master Integrity Audit Report across all editions:
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

from audiobook_studio.master_inspector_team import run_master_inspector_team

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def audit_single_book_3tier(args: tuple[str, str]) -> dict:
    path_str, ed_name = args
    p = Path(path_str)

    rep = run_master_inspector_team(p, ed_name)

    return {
        "path": str(p),
        "name": p.name,
        "edition": ed_name,
        "passed": rep.unanimous_seal,
        "t1_pass": rep.t1_report.passed,
        "t2_pass": rep.t2_report.passed,
        "t3_pass": rep.t3_report.passed,
        "pages_rendered": rep.t3_report.pages_captured,
        "rubies": rep.t2_report.detailed_metrics.get("total_rubies", 0),
        "paras": rep.t2_report.detailed_metrics.get("total_paragraphs", 0),
        "t1_errors": rep.t1_report.errors,
        "t2_flaws": rep.t2_report.critical_flaws,
        "t3_flaws": rep.t3_report.visual_flaws,
    }

def main():
    print("==================================================================")
    print("🏛️ 3-TIER MASTER INSPECTOR TEAM: FULL ALL-EDITION AUDIT INITIATED")
    print("   • Inspector 1: Tier 1 Master Quality Inspector")
    print("   • Inspector 2: Tier 2 Ultimate Integrity Sentinel")
    print("   • Inspector 3: Tier 3 Visual Screen Sentinel (Playwright Screen Capture)")
    print("==================================================================")

    target_tasks = []
    editions = ["[study]", "[e-s]", "[k-e]", "[k]", "[xteink]/[study]", "[xteink]/[e-s]"]

    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            files = [str(p) for p in ed_dir.rglob("*.epub") if p.stat().st_size > 15000]
            print(f"  📂 {ed:<20}: {len(files):>5,} valid EPUBs queued")
            for f in files:
                target_tasks.append((f, ed))

    print(f"\n🚀 Total Books Queued for 3-Tier Visual Cross-Inspection: {len(target_tasks):,} books (8 workers)...\n")

    start_t = time.time()
    edition_stats = {ed: {"total": 0, "t1_pass": 0, "t2_pass": 0, "t3_pass": 0, "team_pass": 0, "pages": 0, "rubies": 0} for ed in editions}
    total_team_passed = 0
    total_failed = 0
    flaw_samples = []

    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(audit_single_book_3tier, t) for t in target_tasks]
        for fut in as_completed(futures):
            r = fut.result()
            ed = r["edition"]

            edition_stats[ed]["total"] += 1
            edition_stats[ed]["rubies"] += r["rubies"]
            edition_stats[ed]["pages"] += r["pages_rendered"]

            if r["t1_pass"]:
                edition_stats[ed]["t1_pass"] += 1
            if r["t2_pass"]:
                edition_stats[ed]["t2_pass"] += 1
            if r["t3_pass"]:
                edition_stats[ed]["t3_pass"] += 1

            if r["passed"]:
                total_team_passed += 1
                edition_stats[ed]["team_pass"] += 1
            else:
                total_failed += 1
                if len(flaw_samples) < 10:
                    flaw_samples.append(r)

    elapsed = time.time() - start_t

    print("\n==================================================================")
    print(f"📊 3-TIER MASTER INSPECTOR TEAM: FINAL AUDIT REPORT (Elapsed: {elapsed:.1f}s)")
    print("==================================================================")
    print(f"  • Total Books Inspected         : {len(target_tasks):,} books")
    print(f"  • 🌟 3-Tier Digital Seal Granted: {total_team_passed:,} books ({(total_team_passed/len(target_tasks))*100:.1f}%)")
    print(f"  • 🚨 Team Rejections (Defects)  : {total_failed:,} books")
    print("------------------------------------------------------------------")
    print(f"  {'Edition':<20} | {'Total':>6} | {'Tier 1':>6} | {'Tier 2':>6} | {'📸 Tier 3':>8} | {'🌟 Team Pass':>11}")
    print("------------------------------------------------------------------")
    for ed, s in edition_stats.items():
        print(f"  {ed:<20} | {s['total']:>6,} | {s['t1_pass']:>6,} | {s['t2_pass']:>6,} | {s['t3_pass']:>8,} | {s['team_pass']:>11,}")
    print("==================================================================")

    if flaw_samples:
        print("\n🚨 Representative Rejected Items for Review:")
        for item in flaw_samples[:5]:
            print(f"  ❌ [{item['edition']}] {item['name'][:50]}")
            if item["t1_errors"]:
                print(f"      -> [Tier 1 Errors] {item['t1_errors']}")
            if item["t2_flaws"]:
                print(f"      -> [Tier 2 Flaws]  {item['t2_flaws']}")
            if item["t3_flaws"]:
                print(f"      -> [Tier 3 Flaws]  {item['t3_flaws']}")

if __name__ == "__main__":
    main()
