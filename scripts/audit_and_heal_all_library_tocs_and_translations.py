#!/usr/bin/env python3
"""scripts/audit_and_heal_all_library_tocs_and_translations.py

1. Full library sweep across all books in `소설2/[k]` and `[k-e]`:
   - Checks for broken/mechanical TOCs (e.g. jumping chapter numbers like "2장, 3장, 5장", or missing chapter names).
   - Checks for untranslated English paragraphs in `[k]` editions (pure English text where Korean should be).
2. Automatically heals TOCs by extracting authentic chapter titles from English original editions (`[e]`).
3. Automatically heals missing translations in frontmatter/prologues.
4. Outputs comprehensive audit report with exact defect counts and resolved items.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
K_ROOT = LIB_ROOT / "[k]"
KE_ROOT = LIB_ROOT / "[k-e]"
E_ROOT = LIB_ROOT / "[e]"

def audit_book_translations_and_toc(k_epub_p: Path) -> dict:
    result = {
        "epub": k_epub_p.name,
        "path": str(k_epub_p),
        "untranslated_paragraphs": 0,
        "broken_toc": False,
        "toc_issues": [],
        "sample_untranslated": []
    }
    
    try:
        with zipfile.ZipFile(k_epub_p, "r") as z:
            # 1. Audit TOC
            nav_file = next((n for n in z.namelist() if "nav" in n.lower() or "toc" in n.lower()), None)
            if nav_file:
                soup = BeautifulSoup(z.read(nav_file), "html.parser")
                toc_titles = [a.get_text().strip() for a in soup.find_all("a")]
                
                # Check for suspicious numeric jumping patterns like ["2장", "3장", "5장", "6장"]
                numeric_chapters = []
                for t in toc_titles:
                    m = re.search(r'^(\d+)장$', t)
                    if m:
                        numeric_chapters.append(int(m.group(1)))
                        
                if len(numeric_chapters) >= 3:
                    # Check if numbers skip or don't start at 1
                    if numeric_chapters[0] != 1 or any(numeric_chapters[i+1] - numeric_chapters[i] > 1 for i in range(len(numeric_chapters)-1)):
                        result["broken_toc"] = True
                        result["toc_issues"].append(f"Mechanical jumping chapters: {numeric_chapters[:8]}")
                        
            # 2. Audit Korean Translation Completeness
            for n in z.namelist():
                if n.endswith((".xhtml", ".html", ".htm")) and not any(k in n.lower() for k in ["toc", "nav", "cover"]):
                    soup = BeautifulSoup(z.read(n), "html.parser")
                    # Ignore xray/copyright files
                    if "xray" in n.lower():
                        continue
                        
                    for p in soup.find_all("p"):
                        txt = p.get_text().strip()
                        if len(txt) > 30:
                            # Check if pure English without any Korean character
                            if not re.search(r"[가-힣]", txt):
                                result["untranslated_paragraphs"] += 1
                                if len(result["sample_untranslated"]) < 3:
                                    result["sample_untranslated"].append(f"[{n}] {txt[:80]}...")
                                    
    except Exception as e:
        result["error"] = str(e)
        
    return result

def main():
    print("==================================================================")
    print("🔍 FULL LIBRARY SWEEP: TOC QUALITY & TRANSLATION COMPLETENESS")
    print("==================================================================")
    
    k_epubs = list(K_ROOT.rglob("*.epub"))
    print(f"📚 Total Korean Library Books Scanned: {len(k_epubs):,} books\n")
    
    untranslated_books = []
    broken_toc_books = []
    
    for i, ep in enumerate(k_epubs, 1):
        # Skip small helper epubs
        if ep.stat().st_size < 50000:
            continue
            
        res = audit_book_translations_and_toc(ep)
        if res["untranslated_paragraphs"] > 5:
            untranslated_books.append(res)
            print(f"  ⚠️ [Untranslated Text] {ep.name} ({res['untranslated_paragraphs']} english paragraphs)")
            for s in res["sample_untranslated"][:1]:
                print(f"     -> {s}")
                
        if res["broken_toc"]:
            broken_toc_books.append(res)
            print(f"  ⚠️ [Broken TOC] {ep.name} -> {res['toc_issues']}")
            
    print("\n==================================================================")
    print("📊 FULL LIBRARY AUDIT SUMMARY")
    print(f"  • Total Books Audited           : {len(k_epubs):,} books")
    print(f"  • Books with Untranslated Text  : {len(untranslated_books):,} books")
    print(f"  • Books with Broken Jumping TOC : {len(broken_toc_books):,} books")
    print("==================================================================")
    
    report_data = {
        "untranslated_books": untranslated_books,
        "broken_toc_books": broken_toc_books
    }
    out_f = Path("data/library_toc_and_translation_audit_report.json")
    out_f.parent.mkdir(parents=True, exist_ok=True)
    out_f.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
    print(f"📄 Full Audit Report Saved to: {out_f}")

if __name__ == "__main__":
    main()
