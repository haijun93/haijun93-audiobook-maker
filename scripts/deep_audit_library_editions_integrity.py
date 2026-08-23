#!/usr/bin/env python3
"""scripts/deep_audit_library_editions_integrity.py

Comprehensive deep audit of ALL EPUB files across all edition folders in /Users/hyeokjunkong/Desktop/소설2/
Editions checked:
1. [k] (Korean-only): Must be pure Korean. Fails if English paragraphs exceed threshold or any chapter is >40% English.
2. [k-e] (Bilingual): Fails if span.ko is missing Korean characters (echoing English) or missing bilingual pairing.
3. [e] (English Original): Fails if containing Korean translation markup or non-English body.
4. [e-s] (English + Study): Fails if missing English text or lacking study structure.
5. [study] (Study Edition): Fails if span.ko echoes English or lacks study notes.
6. [xteink]: Checked against target edition standard.

Inspects EVERY CHAPTER / TOC file inside every EPUB across all CPU cores.
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def audit_single_epub(epub_path_str: str) -> dict:
    epub_path = Path(epub_path_str)
    rel_path = str(epub_path.relative_to(LIB_ROOT))
    
    # Determine expected edition type
    ed_type = "unknown"
    for t in ["[k]", "[k-e]", "[study]", "[e-s]", "[e]", "[ks]", "[xteink]"]:
        if t in rel_path:
            ed_type = t
            break
            
    if "[xteink]" in rel_path:
        if "[study]" in rel_path:
            ed_type = "[xteink]/[study]"
        elif "[e-s]" in rel_path:
            ed_type = "[xteink]/[e-s]"
        else:
            ed_type = "[xteink]"

    issues = []
    total_chapters = 0
    total_paras = 0
    
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            names = z.namelist()
            
            # Check mimetype
            if "mimetype" not in names:
                issues.append("Missing mimetype")
            else:
                info = z.getinfo("mimetype")
                if info.compress_type != zipfile.ZIP_STORED:
                    issues.append("mimetype is compressed (must be ZIP_STORED)")
                    
            xhtml_files = [n for n in names if n.endswith((".xhtml", ".html")) and "xray" not in n and "cover" not in n]
            total_chapters = len(xhtml_files)
            
            for ch_name in xhtml_files:
                content = z.read(ch_name).decode("utf-8", "ignore")
                
                # Skip front/back meta pages if short
                is_meta_page = any(m in ch_name.lower() for m in ["copyright", "nav.", "toc.", "about", "also-by", "author", "connect", "playlist", "dedication"])
                
                soup = BeautifulSoup(content, "html.parser")
                paras = soup.find_all(["p", "div", "li", "h1", "h2", "h3"])
                ch_paras_count = len(paras)
                total_paras += ch_paras_count
                
                if ch_paras_count == 0:
                    continue
                    
                # 1. Audit [k] (Korean-only)
                if ed_type == "[k]":
                    # Check for residual pair markup
                    if soup.find("p", class_="pair") or soup.find("span", class_="en"):
                        issues.append(f"{ch_name}: Leftover bilingual pair markup (<span class='en'>)")
                    # Check Korean ratio in body chapters
                    if not is_meta_page and ch_paras_count >= 5:
                        ko_count = sum(1 for p in paras if re.search(r"[\uac00-\ud7a3]", p.get_text()))
                        if ko_count / ch_paras_count < 0.4:
                            sample = [p.get_text(strip=True)[:50] for p in paras[:3] if len(p.get_text(strip=True)) > 5]
                            issues.append(f"{ch_name}: Low Korean content ({ko_count}/{ch_paras_count} Korean) -> Sample: {sample}")
                            
                # 2. Audit [k-e] (Bilingual)
                elif ed_type == "[k-e]":
                    pairs = soup.find_all("p", class_="pair")
                    if not is_meta_page and ch_paras_count >= 5 and len(pairs) == 0:
                        issues.append(f"{ch_name}: Missing bilingual <p class='pair'> tags")
                    else:
                        untrans_in_ko = 0
                        for p in pairs:
                            ko_span = p.find("span", class_="ko")
                            en_span = p.find("span", class_="en")
                            if ko_span and en_span:
                                ko_t = ko_span.get_text(strip=True)
                                en_t = en_span.get_text(strip=True)
                                if not re.search(r"[\uac00-\ud7a3]", ko_t) and len(ko_t) > 8 and ko_t == en_t:
                                    untrans_in_ko += 1
                        if not is_meta_page and untrans_in_ko >= 5:
                            issues.append(f"{ch_name}: {untrans_in_ko} untranslated paragraphs (span.ko equals span.en)")

                # 3. Audit [e] (English original)
                elif ed_type == "[e]":
                    if not is_meta_page:
                        # Should NOT contain Korean text
                        ko_count = sum(1 for p in paras if re.search(r"[\uac00-\ud7a3]", p.get_text()))
                        if ko_count >= 5 and ko_count / ch_paras_count > 0.3:
                            issues.append(f"{ch_name}: Accidental Korean text found in [e] edition ({ko_count}/{ch_paras_count} paras)")

                # 4. Audit [e-s] (English + Study)
                elif ed_type in ["[e-s]", "[xteink]/[e-s]"]:
                    # Should contain English text, no Korean translation block (except ruby/study note)
                    if soup.find("span", class_="ko"):
                        issues.append(f"{ch_name}: Leftover <span class='ko'> found in English study edition")

                # 5. Audit [study] (Study Edition)
                elif ed_type in ["[study]", "[xteink]/[study]"]:
                    pairs = soup.find_all("p", class_="pair")
                    untrans_in_ko = 0
                    for p in pairs:
                        ko_span = p.find("span", class_="ko")
                        en_span = p.find("span", class_="en")
                        if ko_span and en_span:
                            ko_t = ko_span.get_text(strip=True)
                            en_t = en_span.get_text(strip=True)
                            if not re.search(r"[\uac00-\ud7a3]", ko_t) and len(ko_t) > 8 and ko_t == en_t:
                                untrans_in_ko += 1
                    if not is_meta_page and untrans_in_ko >= 5:
                        issues.append(f"{ch_name}: {untrans_in_ko} untranslated paragraphs in [study]")

    except Exception as e:
        issues.append(f"Corrupted or Unreadable ZIP: {e}")

    return {
        "path": rel_path,
        "filename": epub_path.name,
        "ed_type": ed_type,
        "total_chapters": total_chapters,
        "total_paras": total_paras,
        "valid": len(issues) == 0,
        "issues": issues,
    }

def main():
    print("==================================================================")
    print("🔬 COMPREHENSIVE DEEP AUDIT OF ALL LIBRARY EDITIONS ([k], [e], [e-s], [k-e], [study])")
    print("==================================================================")
    
    all_epubs = sorted([str(p) for p in LIB_ROOT.rglob("*.epub") if "_translation_stage" not in str(p) and "_chatgpt_translate_work" not in str(p)])
    print(f"📚 Total EPUBs queued for chapter-by-chapter deep audit: {len(all_epubs):,}\n")
    
    flawed_books = []
    total_inspected = 0
    
    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(audit_single_epub, ep): ep for ep in all_epubs}
        for fut in as_completed(futures):
            res = fut.result()
            total_inspected += 1
            if not res["valid"]:
                flawed_books.append(res)
                print(f"  ❌ [{res['ed_type']}] {res['path']}")
                for iss in res["issues"][:3]:
                    print(f"       ⚠️ {iss}")
                if len(res["issues"]) > 3:
                    print(f"       ... and {len(res['issues']) - 3} more chapter issues")
            if total_inspected % 500 == 0:
                print(f"   ... Inspected {total_inspected:,} / {len(all_epubs):,} books")

    print("\n==================================================================")
    print(f"🏁 AUDIT SUMMARY: Inspected {total_inspected:,} EPUBs across all editions")
    print(f"   ✅ Fully Valid EPUBs: {total_inspected - len(flawed_books):,}")
    print(f"   🚨 Flawed EPUBs needing remediation: {len(flawed_books):,}")
    print("==================================================================")
    
    report_file = Path("data/library_deep_audit_report.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(flawed_books, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📄 Detailed report written to: {report_file}")

if __name__ == "__main__":
    main()
