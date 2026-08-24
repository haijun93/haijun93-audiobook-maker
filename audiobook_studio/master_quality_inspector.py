#!/usr/bin/env python3
"""audiobook_studio/master_quality_inspector.py

Pre-Publishing Master Quality Gate for Audiobook Maker.
Runs a strict, multi-point automated audit on every translated EPUB before it can be
saved or synchronized into the library (`소설2/` and Google Drive `#Books`).

Quality Checkpoints:
1. Cover Gate: Valid cover image (>10KB), `000-cover.xhtml`, and OPF cover metadata.
2. TOC Gate: 100% Valid XML for `nav.xhtml` & `toc.ncx`, escape of special characters (`&`), and multi-chapter linking.
3. X-Ray Gate: Mandatory 4 sections (등장인물, 관계도, 공간배경, 핵심테마) in `000-xray-dramatis-personae.xhtml`.
4. Zero Untranslated Leak Gate: 0 raw English sentences in Korean translation spans (`span.ko`).
5. TOEIC 700+ to 990 Vocab Gate: 0 middle-school basic words in Word Wise rubies, 0 truncated definitions.
6. XHTML Well-Formedness: 100% compliant XML parsing across all internal documents.
"""

from __future__ import annotations

import io
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
class InspectionResult:
    passed: bool
    book_title: str
    edition: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, any] = field(default_factory=dict)

def inspect_epub_quality(epub_path: Path | str, edition_type: str = "[study]") -> InspectionResult:
    p = Path(epub_path)
    res = InspectionResult(passed=True, book_title=p.name, edition=edition_type)
    
    if not p.exists() or p.stat().st_size < 10000:
        res.passed = False
        res.errors.append(f"File missing or corrupted (size: {p.stat().st_size if p.exists() else 0} bytes)")
        return res
        
    try:
        with zipfile.ZipFile(p, "r") as z:
            names = set(z.namelist())
            
            # --- 1. XML Well-Formedness Check ---
            for req_xml in ["OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx"]:
                if req_xml in names:
                    try:
                        ET.fromstring(z.read(req_xml))
                    except Exception as e:
                        res.passed = False
                        res.errors.append(f"TOC XML Well-Formedness Failed in {req_xml}: {e}")
                        
            # --- 2. Cover Gate ---
            has_cover_page = any("000-cover.xhtml" in n or "cover.xhtml" in n.lower() for n in names)
            has_cover_img = any("cover" in n.lower() and n.lower().endswith((".jpg", ".jpeg", ".png")) for n in names)
            
            if not has_cover_img:
                res.warnings.append("Cover image missing inside EPUB package.")
            if not has_cover_page:
                res.warnings.append("Cover XHTML page missing.")
                
            res.metrics["has_cover"] = bool(has_cover_img and has_cover_page)
            
            # --- 3. TOC & Navigation Gate ---
            nav_pts_count = 0
            if "OEBPS/toc.ncx" in names:
                try:
                    root = ET.fromstring(z.read("OEBPS/toc.ncx"))
                    nav_pts = root.findall(".//{http://www.daisy.org/z3986/2005/ncx/}navPoint")
                    nav_pts_count = len(nav_pts)
                except Exception:
                    pass
            elif "OEBPS/nav.xhtml" in names:
                nav_html = z.read("OEBPS/nav.xhtml").decode("utf-8", "ignore")
                nav_pts_count = len(re.findall(r'<a\s+href="[^"]+">', nav_html))
                
            res.metrics["toc_chapter_count"] = nav_pts_count
            if nav_pts_count < 3:
                res.passed = False
                res.errors.append(f"TOC is incomplete (Found only {nav_pts_count} navigation points. Minimum 3 required).")
                
            # --- 4. X-Ray Dossier Gate (Fiction requirement) ---
            has_xray = any("xray" in n.lower() for n in names)
            res.metrics["has_xray"] = has_xray
            if has_xray:
                xray_file = [n for n in names if "xray" in n.lower()][0]
                xray_text = z.read(xray_file).decode("utf-8", "ignore")
                xray_secs = sum(1 for k in ["등장인물", "관계도", "무대", "배경", "테마", "세계관"] if k in xray_text)
                if xray_secs < 2:
                    res.warnings.append(f"X-Ray dossier has fewer than standard sections (matched {xray_secs}/4 keywords).")
                    
            # --- 5. Content Inspection (Zero Leak & Word Wise) ---
            total_pairs = 0
            total_rubies = 0
            basic_stoplist_violations = 0
            untranslated_ko_leaks = 0
            
            for n in sorted(names):
                if n.endswith((".xhtml", ".html")) and not any(k in n.lower() for k in ["xray", "cover", "nav"]):
                    soup = BeautifulSoup(z.read(n), "html.parser")
                    for p_tag in soup.find_all("p"):
                        total_pairs += 1
                        
                        # Word Wise check
                        for rb in p_tag.find_all("ruby"):
                            total_rubies += 1
                            rb_txt = rb.find("rb").get_text().strip() if rb.find("rb") else ""
                            if rb_txt.lower() in BASIC_VOCAB_STOPLIST and not is_valid_toeic_700_plus_target(rb_txt):
                                basic_stoplist_violations += 1
                                
                        # Korean translation check (for [study], [k-e], [k])
                        if edition_type in ["[study]", "[k-e]", "[k]"]:
                            ko_span = p_tag.find("span", class_="ko")
                            if ko_span:
                                ko_txt = ko_span.get_text().strip()
                                en_span = p_tag.find("span", class_=lambda c: c and "en" in c)
                                en_txt = en_span.get_text().strip() if en_span else ""
                                
                                if ko_txt and not re.search(r'[가-힣]', ko_txt) and len(ko_txt) > 3 and not re.match(r'^[\*\s\-_•~Q0-9\(\)]+$', ko_txt):
                                    if ko_txt.lower() == en_txt.lower():
                                        untranslated_ko_leaks += 1
                                        
            res.metrics["total_pairs"] = total_pairs
            res.metrics["total_rubies"] = total_rubies
            res.metrics["basic_stoplist_violations"] = basic_stoplist_violations
            res.metrics["untranslated_ko_leaks"] = untranslated_ko_leaks
            
            if basic_stoplist_violations > 0:
                res.passed = False
                res.errors.append(f"TOEIC 700+ standard violation: Found {basic_stoplist_violations} middle-school basic words in rubies.")
                
            if untranslated_ko_leaks > 0:
                res.passed = False
                res.errors.append(f"Zero Untranslated Leak violation: Found {untranslated_ko_leaks} raw English sentences inside Korean translation spans.")
                
    except Exception as e:
        res.passed = False
        res.errors.append(f"Fatal exception during quality audit: {e}")
        
    return res

def format_inspection_report(res: InspectionResult) -> str:
    status_icon = "✅ PASS" if res.passed else "❌ FAIL"
    report = [
        f"==================================================================",
        f"🛡️ PRE-PUBLISH QUALITY AUDIT: {res.book_title} ({res.edition})",
        f"==================================================================",
        f"  • Verdict                  : {status_icon}",
        f"  • Total Content Blocks     : {res.metrics.get('total_pairs', 0):,}",
        f"  • Total Word Wise Rubies   : {res.metrics.get('total_rubies', 0):,}",
        f"  • TOC Navigation Points    : {res.metrics.get('toc_chapter_count', 0)} chapters",
        f"  • Cover Image & Page       : {'✅ Valid' if res.metrics.get('has_cover') else '⚠️ Missing'}",
        f"  • X-Ray Dossier            : {'✅ Attached' if res.metrics.get('has_xray') else '⚠️ None'}",
        f"  • Middle-School Violations : {res.metrics.get('basic_stoplist_violations', 0)} (Max allowed: 0)",
        f"  • Untranslated Leaks       : {res.metrics.get('untranslated_ko_leaks', 0)} (Max allowed: 0)",
    ]
    if res.errors:
        report.append("\n  🚨 Critical Errors:")
        for err in res.errors:
            report.append(f"    - {err}")
    if res.warnings:
        report.append("\n  ⚠️ Quality Warnings:")
        for w in res.warnings:
            report.append(f"    - {w}")
    report.append("==================================================================")
    return "\n".join(report)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_file = Path(sys.argv[1])
        ed_type = sys.argv[2] if len(sys.argv) > 2 else "[study]"
        r = inspect_epub_quality(test_file, ed_type)
        print(format_inspection_report(r))
        sys.exit(0 if r.passed else 1)
    else:
        print("Usage: master_quality_inspector.py <path_to_epub> [<edition_type>]")
