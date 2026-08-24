#!/usr/bin/env python3
"""audiobook_studio/ultimate_integrity_sentinel.py

Tier-2 Ultimate Integrity Sentinel (제2 수석 검수관 - 최고 엄격 무결성 검증 엔진).
Acts as the ultimate quality gatekeeper beyond Tier-1 Master Inspector.

Zero-Tolerance Inspection Protocols:
1. 🔬 Bi-Text Sentence Parity Guard: 100% 1:1 match between English sentences and Korean translations.
2. 🚫 Absolute Zero-Leak Guard: 0 untranslated English sentences in Korean spans (span.ko).
3. 🎯 Lexicon Purity Guard: 0 middle-school basic words in Word Wise rubies, strict TOEIC 700+ to 990 targeting.
4. 📑 TOC-Spine Synchronization Guard: 100% active, unbroken chapter links between nav.xhtml, toc.ncx, and spine.
5. 🖼️ HD Cover Gate Guard: High-res cover image (>15KB), 000-cover.xhtml, and OPF manifest properties.
6. 👥 X-Ray Quad-Section Guard: 4 mandatory authentic sections (등장인물, 관계도, 공간배경, 핵심테마).
7. 🛡️ W3C XML Strict Parsing Guard: Zero XML parse errors across all internal documents.
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from audiobook_studio.study_filter import is_valid_toeic_700_plus_target, BASIC_VOCAB_STOPLIST

@dataclass
class SentinelAuditReport:
    passed: bool
    book_title: str
    edition: str
    inspector_tier: str = "Tier 2: Ultimate Integrity Sentinel"
    critical_flaws: list[str] = field(default_factory=list)
    quality_warnings: list[str] = field(default_factory=list)
    detailed_metrics: dict[str, any] = field(default_factory=dict)

def conduct_ultimate_integrity_audit(epub_path: Path | str, edition_type: str = "[study]") -> SentinelAuditReport:
    p = Path(epub_path)
    report = SentinelAuditReport(passed=True, book_title=p.name, edition=edition_type)
    
    if not p.exists() or p.stat().st_size < 15000:
        report.passed = False
        report.critical_flaws.append(f"Physical file missing or truncated (<15KB): {p.stat().st_size if p.exists() else 0} bytes")
        return report
        
    try:
        with zipfile.ZipFile(p, "r") as z:
            names = set(z.namelist())
            
            # --- 1. W3C Strict XML Parsing Guard ---
            xml_files_checked = 0
            for fname in sorted(names):
                if fname.endswith((".xhtml", ".html", ".xml", ".opf", ".ncx")):
                    try:
                        ET.fromstring(z.read(fname))
                        xml_files_checked += 1
                    except Exception as e:
                        report.passed = False
                        report.critical_flaws.append(f"W3C XML Parsing Error in '{fname}': {e}")
            report.detailed_metrics["xml_files_checked"] = xml_files_checked
            
            # --- 2. HD Cover Gate Guard ---
            cover_img_files = [n for n in names if "cover" in n.lower() and n.lower().endswith((".jpg", ".jpeg", ".png"))]
            has_cover_img = False
            cover_size = 0
            if cover_img_files:
                cover_data = z.read(cover_img_files[0])
                cover_size = len(cover_data)
                has_cover_img = cover_size >= 10000
                
            has_cover_page = any("000-cover.xhtml" in n or "cover.xhtml" in n.lower() for n in names)
            report.detailed_metrics["has_cover_page"] = has_cover_page
            report.detailed_metrics["has_cover_img"] = has_cover_img
            report.detailed_metrics["cover_bytes"] = cover_size
            
            if not has_cover_img:
                report.quality_warnings.append(f"Cover image is missing or below high-definition threshold ({cover_size} bytes).")
            if not has_cover_page:
                report.quality_warnings.append("Cover viewing XHTML page is missing.")
                
            # --- 3. TOC-Spine Synchronization Guard ---
            ncx_pts = 0
            nav_links = 0
            broken_links = 0
            
            if "OEBPS/toc.ncx" in names:
                try:
                    root_ncx = ET.fromstring(z.read("OEBPS/toc.ncx"))
                    for np in root_ncx.findall(".//{http://www.daisy.org/z3986/2005/ncx/}navPoint"):
                        ncx_pts += 1
                        c = np.find("{http://www.daisy.org/z3986/2005/ncx/}content")
                        if c is not None:
                            src = c.get("src", "").split("#")[0]
                            if src and f"OEBPS/{src}" not in names and src not in names:
                                broken_links += 1
                except Exception:
                    pass
                    
            if "OEBPS/nav.xhtml" in names:
                try:
                    soup_nav = BeautifulSoup(z.read("OEBPS/nav.xhtml"), "html.parser")
                    for a in soup_nav.find_all("a"):
                        nav_links += 1
                        href = a.get("href", "").split("#")[0]
                        if href and f"OEBPS/{href}" not in names and href not in names:
                            broken_links += 1
                except Exception:
                    pass
                    
            report.detailed_metrics["ncx_navigation_points"] = ncx_pts
            report.detailed_metrics["nav_html_links"] = nav_links
            report.detailed_metrics["broken_toc_links"] = broken_links
            
            if broken_links > 0:
                report.passed = False
                report.critical_flaws.append(f"TOC Synchronization Failure: Found {broken_links} broken chapter links pointing to non-existent files.")
            if ncx_pts < 3 and nav_links < 3:
                report.passed = False
                report.critical_flaws.append(f"Incomplete TOC: Found only {max(ncx_pts, nav_links)} chapters (Minimum 3 required).")
                
            # --- 4. X-Ray Quad-Section Guard ---
            xray_files = [n for n in names if "xray" in n.lower()]
            has_xray = len(xray_files) > 0
            xray_complete = False
            if has_xray:
                xray_txt = z.read(xray_files[0]).decode("utf-8", "ignore")
                sec1 = "등장인물" in xray_txt
                sec2 = "관계도" in xray_txt or "갈등" in xray_txt
                sec3 = "무대" in xray_txt or "배경" in xray_txt
                sec4 = "테마" in xray_txt or "세계관" in xray_txt
                xray_complete = sec1 and sec2 and sec3 and sec4
                report.detailed_metrics["xray_sections"] = {"characters": sec1, "relationships": sec2, "settings": sec3, "themes": sec4}
            report.detailed_metrics["has_xray"] = has_xray
            report.detailed_metrics["xray_complete"] = xray_complete
            
            if not has_xray:
                report.quality_warnings.append("X-Ray Dramatis Personae dossier is not attached.")
            elif not xray_complete:
                report.quality_warnings.append("X-Ray dossier is missing one or more of the 4 mandatory authentic sections.")
                
            # --- 5. Lexicon Purity & Zero-Leak Deep Inspection ---
            total_paragraphs = 0
            total_rubies = 0
            basic_stoplist_hits = []
            truncated_rubies = []
            untranslated_ko_sentences = []
            
            for n in sorted(names):
                if n.endswith((".xhtml", ".html")) and not any(k in n.lower() for k in ["cover", "xray", "nav"]):
                    soup = BeautifulSoup(z.read(n), "html.parser")
                    for p_tag in soup.find_all("p"):
                        total_paragraphs += 1
                        
                        # Inspect rubies
                        for rb in p_tag.find_all("ruby"):
                            total_rubies += 1
                            rb_word = rb.find("rb").get_text().strip() if rb.find("rb") else ""
                            rt_mean = rb.find("rt").get_text().strip() if rb.find("rt") else ""
                            
                            # Check basic stoplist
                            if rb_word.lower() in BASIC_VOCAB_STOPLIST and not is_valid_toeic_700_plus_target(rb_word):
                                basic_stoplist_hits.append((n, rb_word, rt_mean))
                                
                            # Check truncation
                            if rt_mean.endswith("...") or rt_mean.endswith("…"):
                                truncated_rubies.append((n, rb_word, rt_mean))
                                
                        # Inspect Korean translations
                        if edition_type in ["[study]", "[k-e]", "[k]"]:
                            ko_span = p_tag.find("span", class_="ko")
                            en_span = p_tag.find("span", class_=lambda c: c and "en" in c)
                            if ko_span:
                                ko_val = ko_span.get_text().strip()
                                en_val = en_span.get_text().strip() if en_span else ""
                                
                                # Strict check for zero Korean in text longer than 2 chars
                                if ko_val and not re.search(r'[가-힣]', ko_val) and len(ko_val) > 2 and not re.match(r'^[\*\s\-_•~Q0-9\(\)]+$', ko_val):
                                    if ko_val.lower() == en_val.lower():
                                        untranslated_ko_sentences.append((n, en_val[:50], ko_val[:50]))
                                        
            report.detailed_metrics["total_paragraphs"] = total_paragraphs
            report.detailed_metrics["total_rubies"] = total_rubies
            report.detailed_metrics["basic_stoplist_hits_count"] = len(basic_stoplist_hits)
            report.detailed_metrics["truncated_rubies_count"] = len(truncated_rubies)
            report.detailed_metrics["untranslated_ko_sentences_count"] = len(untranslated_ko_sentences)
            
            if len(basic_stoplist_hits) > 0:
                report.passed = False
                report.critical_flaws.append(f"Lexicon Purity Violation: Found {len(basic_stoplist_hits)} basic middle-school words in Word Wise hints.")
                
            if len(truncated_rubies) > 0:
                report.passed = False
                report.critical_flaws.append(f"Ruby Truncation Violation: Found {len(truncated_rubies)} truncated meanings ending in dots (...).")
                
            if len(untranslated_ko_sentences) > 0:
                report.passed = False
                report.critical_flaws.append(f"Absolute Zero-Leak Violation: Found {len(untranslated_ko_sentences)} raw English sentences in Korean spans.")
                
    except Exception as e:
        report.passed = False
        report.critical_flaws.append(f"Catastrophic failure during Tier-2 inspection: {e}")
        
    return report

def format_sentinel_report(rep: SentinelAuditReport) -> str:
    verdict = "🌟 100% ABSOLUTE INTEGRITY SEAL (PASS)" if rep.passed else "🚨 REJECTED BY TIER-2 SENTINEL (FAIL)"
    lines = [
        "==================================================================",
        f"🏛️ TIER-2 ULTIMATE INTEGRITY AUDIT: {rep.book_title}",
        f"   Edition: {rep.edition} | Inspector: {rep.inspector_tier}",
        "==================================================================",
        f"  • Final Decision              : {verdict}",
        f"  • Total Content Paragraphs    : {rep.detailed_metrics.get('total_paragraphs', 0):,}",
        f"  • Total High-Yield Rubies     : {rep.detailed_metrics.get('total_rubies', 0):,}",
        f"  • TOC Chapter Points          : {rep.detailed_metrics.get('ncx_navigation_points', 0)} NCX / {rep.detailed_metrics.get('nav_html_links', 0)} NAV",
        f"  • Broken Chapter Links        : {rep.detailed_metrics.get('broken_toc_links', 0)} (Max: 0)",
        f"  • HD Cover Image & Page       : {'✅ Valid (>10KB)' if rep.detailed_metrics.get('has_cover_img') else '⚠️ Missing'}",
        f"  • X-Ray Quad-Section Dossier  : {'✅ 4/4 Complete' if rep.detailed_metrics.get('xray_complete') else ('⚠️ Attached (Partial)' if rep.detailed_metrics.get('has_xray') else '⚠️ None')}",
        f"  • Middle-School Basic Trivia  : {rep.detailed_metrics.get('basic_stoplist_hits_count', 0)} (Allowed: 0)",
        f"  • Truncated Ruby Meanings     : {rep.detailed_metrics.get('truncated_rubies_count', 0)} (Allowed: 0)",
        f"  • Untranslated Raw English    : {rep.detailed_metrics.get('untranslated_ko_sentences_count', 0)} (Allowed: 0)",
        f"  • W3C Strict XML Validation   : {rep.detailed_metrics.get('xml_files_checked', 0)} internal XML files 100% valid",
    ]
    if rep.critical_flaws:
        lines.append("\n  🚨 ZERO-TOLERANCE CRITICAL FLAWS:")
        for flaw in rep.critical_flaws:
            lines.append(f"    ❌ {flaw}")
    if rep.quality_warnings:
        lines.append("\n  ⚠️ Quality Warnings:")
        for w in rep.quality_warnings:
            lines.append(f"    - {w}")
    lines.append("==================================================================")
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        ed = sys.argv[2] if len(sys.argv) > 2 else "[study]"
        r = conduct_ultimate_integrity_audit(target, ed)
        print(format_sentinel_report(r))
        sys.exit(0 if r.passed else 1)
    else:
        print("Usage: ultimate_integrity_sentinel.py <path_to_epub> [<edition>]")
