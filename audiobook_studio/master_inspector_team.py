#!/usr/bin/env python3
"""audiobook_studio/master_inspector_team.py

3-Tier Master Inspector Team Orchestrator:
- Inspector 1: Tier 1 Master Quality Inspector & Auto-Healer
- Inspector 2: Tier 2 Ultimate Integrity Sentinel (Senior Master Inspector)
- Inspector 3: Tier 3 Visual Screen Sentinel (Playwright Screen Capture & Render Inspector)

Ensures that every EPUB published into the library achieves 100.0% unanimous approval across all 3 tiers.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.master_quality_inspector import inspect_epub_quality, InspectionResult  # noqa: E402
from audiobook_studio.ultimate_integrity_sentinel import conduct_ultimate_integrity_audit, SentinelAuditReport  # noqa: E402
from audiobook_studio.visual_screen_sentinel import inspect_epub_visually, VisualAuditReport  # noqa: E402

@dataclass
class MasterTeamAuditReport:
    passed: bool
    book_title: str
    edition: str
    t1_report: InspectionResult
    t2_report: SentinelAuditReport
    t3_report: VisualAuditReport
    unanimous_seal: bool = False

def run_master_inspector_team(epub_path: Path | str, edition_type: str = "[study]") -> MasterTeamAuditReport:
    p = Path(epub_path)

    # 1. Tier-1 Master Quality Inspector
    t1 = inspect_epub_quality(p, edition_type)

    # 2. Tier-2 Ultimate Integrity Sentinel
    t2 = conduct_ultimate_integrity_audit(p, edition_type)

    # 3. Tier-3 Visual Screen Sentinel (10-20 pages screen capture audit)
    t3 = inspect_epub_visually(p, edition_type, min_pages=10, max_pages=20)

    unanimous = t1.passed and t2.passed and t3.passed

    return MasterTeamAuditReport(
        passed=unanimous,
        book_title=p.name,
        edition=edition_type,
        t1_report=t1,
        t2_report=t2,
        t3_report=t3,
        unanimous_seal=unanimous
    )

def format_team_report(rep: MasterTeamAuditReport) -> str:
    verdict = "🌟 3-TIER MASTER DIGITAL SEAL GRANTED (100% UNANIMOUS PASS)" if rep.unanimous_seal else "🚨 REJECTED BY INSPECTOR TEAM (FAIL)"
    lines = [
        "==================================================================",
        f"🏛️ 3-TIER MASTER INSPECTOR TEAM AUDIT: {rep.book_title}",
        f"   Edition: {rep.edition} | Team: Tier 1 + Tier 2 + Tier 3",
        "==================================================================",
        f"  • Overall Decision            : {verdict}",
        f"  • 🛡️ Inspector 1 (Master)     : {'✅ PASS' if rep.t1_report.passed else '❌ FAIL'}",
        f"  • 🏛️ Inspector 2 (Sentinel)   : {'✅ PASS' if rep.t2_report.passed else '❌ FAIL'}",
        f"  • 📸 Inspector 3 (Visual Screen): {'✅ PASS' if rep.t3_report.passed else '❌ FAIL'} ({rep.t3_report.pages_captured} pages rendered)",
        f"  • Total Content Paragraphs    : {rep.t2_report.detailed_metrics.get('total_paragraphs', 0):,}",
        f"  • Total High-Yield Rubies     : {rep.t2_report.detailed_metrics.get('total_rubies', 0):,}",
        f"  • TOC Chapter Points          : {rep.t2_report.detailed_metrics.get('ncx_navigation_points', 0)} NCX",
        f"  • Broken Chapter Links        : {rep.t2_report.detailed_metrics.get('broken_toc_links', 0)} (Max: 0)",
        f"  • Visual Cover Render         : {'✅ Valid' if rep.t3_report.metrics.get('has_valid_cover_render') else '⚠️ Collapsed'}",
        f"  • Untranslated Raw English    : {rep.t2_report.detailed_metrics.get('untranslated_ko_sentences_count', 0)} (Max: 0)",
        f"  • Middle-School Basic Trivia  : {rep.t2_report.detailed_metrics.get('basic_stoplist_hits_count', 0)} (Max: 0)",
        f"  • W3C Strict XML Validation   : {rep.t2_report.detailed_metrics.get('xml_files_checked', 0)} internal files 100% valid",
    ]
    if not rep.unanimous_seal:
        lines.append("\n  🚨 DEFECTS DETECTED BY TEAM:")
        for err in rep.t1_report.errors:
            lines.append(f"    [Tier 1 Error] {err}")
        for flaw in rep.t2_report.critical_flaws:
            lines.append(f"    [Tier 2 Flaw]  {flaw}")
        for v_flaw in rep.t3_report.visual_flaws:
            lines.append(f"    [Tier 3 Visual] {v_flaw}")
    lines.append("==================================================================")
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        ed = sys.argv[2] if len(sys.argv) > 2 else "[study]"
        r = run_master_inspector_team(target, ed)
        print(format_team_report(r))
        sys.exit(0 if r.passed else 1)
    else:
        print("Usage: master_inspector_team.py <path_to_epub> [<edition>]")
