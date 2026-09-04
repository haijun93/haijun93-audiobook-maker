#!/usr/bin/env python3
"""scripts/run_latest_master_inspector_team.py

Executes full-library 3-Tier Master Inspector Team cross-verification using the latest master rules:
1. Tier 1: Master Quality Inspector (Structure, TOC, Covers, XML)
2. Tier 2: Ultimate Integrity Sentinel (7 Zero-Tolerance Integrity Gates: Lexicon Purity without basic words like 'fate', Zero Untranslated Leaks, Zero Emojis in TOC/X-Ray, Zero Truncation, W3C Strict XML)
3. Tier 3: Visual Screen Sentinel (Playwright 800x1200 Screen Capture & Render Gate: Zero Broken Images, Zero Collapsed Covers, Adequate Line-Height)

Automatically performs instant self-healing for any recoverable defects and outputs the comprehensive master audit report.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.master_inspector_team import run_master_inspector_team
from scripts.purge_all_basic_rubies_from_library import process_single_epub

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def audit_single_epub_latest(args: tuple[str, str]) -> dict:
    ep_path_str, ed_name = args
    ep = Path(ep_path_str)

    start_t = time.time()
    try:
        # 1. Instant Auto-Healing for basic rubies
        process_single_epub((str(ep), ed_name))

        # 2. 3-Tier Master Inspector Team
        team_report = run_master_inspector_team(ep, edition_type=ed_name)
        flaws = []
        if not team_report.t1_report.passed:
            flaws.extend(team_report.t1_report.errors)
        if not team_report.t2_report.passed:
            flaws.extend(team_report.t2_report.critical_flaws)
        if not team_report.t3_report.passed:
            flaws.extend(team_report.t3_report.visual_flaws)

        return {
            "path": str(ep),
            "name": ep.name,
            "edition": ed_name,
            "passed": team_report.unanimous_seal,
            "t1_pass": team_report.t1_report.passed,
            "t2_pass": team_report.t2_report.passed,
            "t3_pass": team_report.t3_report.passed,
            "defects": flaws,
            "elapsed": time.time() - start_t
        }
    except Exception as e:
        return {
            "path": str(ep),
            "name": ep.name,
            "edition": ed_name,
            "passed": False,
            "t1_pass": False,
            "t2_pass": False,
            "t3_pass": False,
            "defects": [str(e)],
            "elapsed": time.time() - start_t
        }

def main():
    print("==================================================================")
    print("🏛️ LATEST MASTER 3-TIER INSPECTOR TEAM: FULL LIBRARY AUDIT")
    print("   • Tier 1: Master Quality Inspector (Structure & Layout)")
    print("   • Tier 2: Ultimate Integrity Sentinel (7 Zero-Tolerance Gates)")
    print("   • Tier 3: Visual Screen Sentinel (Playwright Screen Capture)")
    print("   • Latest Rules: Zero Emojis, Strict TOEIC 700+ Vocab, Pure AI X-Ray")
    print("==================================================================")

    editions = ["[study]", "[e-s]", "[k-e]", "[k]", "[ks]", "[xteink]/[study_x]", "[xteink]/[e-s_x]"]
    all_targets = []

    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            for p in ed_dir.rglob("*.epub"):
                if p.stat().st_size > 15000:
                    all_targets.append((str(p), ed))

    print(f"📚 Total Books Queued for Latest 3-Tier Verification: {len(all_targets):,} books (16 workers)...\n", flush=True)

    start_time = time.time()
    results = []

    with ProcessPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(audit_single_epub_latest, t) for t in all_targets]
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            if len(results) % 500 == 0:
                pass_count = sum(1 for r in results if r["passed"])
                print(f"  ... Inspected {len(results):,} / {len(all_targets):,} books (Pass Rate: {(pass_count/len(results))*100:.1f}%) ...", flush=True)

    elapsed = time.time() - start_time
    total_books = len(results)
    total_pass = sum(1 for r in results if r["passed"])
    total_t1 = sum(1 for r in results if r["t1_pass"])
    total_t2 = sum(1 for r in results if r["t2_pass"])
    total_t3 = sum(1 for r in results if r["t3_pass"])

    print("\n==================================================================")
    print("📊 LATEST 3-TIER MASTER INSPECTOR TEAM: FINAL AUDIT REPORT")
    print(f"   Elapsed Time: {elapsed:.1f}s")
    print("==================================================================")
    print(f"  • Total Books Inspected         : {total_books:,} books")
    print(f"  • 🌟 3-Tier Digital Seal Granted: {total_pass:,} books ({(total_pass/total_books)*100:.1f}%)")
    print(f"  • 🚨 Team Rejections (Defects)  : {total_books - total_pass:,} books")
    print("------------------------------------------------------------------")
    print("  Edition              |  Total | Tier 1 | Tier 2 | 📸 Tier 3 | 🌟 Team Pass")
    print("------------------------------------------------------------------")

    for ed in editions:
        ed_res = [r for r in results if r["edition"] == ed]
        if not ed_res:
            continue
        tot = len(ed_res)
        t1 = sum(1 for r in ed_res if r["t1_pass"])
        t2 = sum(1 for r in ed_res if r["t2_pass"])
        t3 = sum(1 for r in ed_res if r["t3_pass"])
        tp = sum(1 for r in ed_res if r["passed"])
        print(f"  {ed:20} | {tot:6,d} | {t1:6,d} | {t2:6,d} | {t3:10,d} | {tp:12,d}")

    print("==================================================================")

    # Save JSON report
    report_path = Path("data/latest_master_3tier_audit_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_books": total_books,
        "team_pass": total_pass,
        "team_pass_ratio": f"{(total_pass/total_books)*100:.2f}%",
        "results": results
    }, indent=2, ensure_ascii=False))
    print(f"💾 Full Inspection Log Saved: {report_path}")

if __name__ == "__main__":
    main()
