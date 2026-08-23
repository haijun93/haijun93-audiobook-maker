#!/usr/bin/env python3
"""scripts/audit_study_folder_and_wordwise.py

Audits all EPUB files inside /Users/hyeokjunkong/Desktop/소설2/[study]/ to detect:
1. Misnamed files (files starting with [k-e], [k], [e], etc. instead of [study]).
2. Files missing Word Wise / Study notes (<span class="study-note"> or <ruby>).
3. Ratio of study notes across chapters.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor, as_completed

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
STUDY_ROOT = LIB_ROOT / "[study]"

def audit_single_study_epub(ep_path: Path) -> dict:
    fname = ep_path.name
    rel_path = str(ep_path.relative_to(STUDY_ROOT))
    
    issues = []
    
    # 1. Check filename prefix
    if not fname.startswith("[study]"):
        issues.append(f"Misnamed file in [study] folder: starts with '{fname.split()[0]}'")

    # 2. Check study notes / Word Wise presence
    total_paras = 0
    study_notes_count = 0
    total_chapters = 0
    
    try:
        with zipfile.ZipFile(ep_path, "r") as z:
            xhtml_files = [n for n in z.namelist() if n.endswith((".xhtml", ".html")) and "xray" not in n and "cover" not in n and "nav" not in n]
            total_chapters = len(xhtml_files)
            
            for ch in xhtml_files:
                raw = z.read(ch).decode("utf-8", "ignore")
                soup = BeautifulSoup(raw, "html.parser")
                
                # Check for study notes
                notes = soup.find_all(["span", "rt"], class_=lambda c: c and ("study-note" in c or "wordwise-hint" in c))
                study_notes_count += len(notes)
                
                # Also check ruby tags
                rubies = soup.find_all("ruby")
                study_notes_count += len(rubies)
                
                paras = soup.find_all("p", class_=lambda c: c and "pair" in c)
                total_paras += len(paras)

        if total_paras > 10 and study_notes_count == 0:
            issues.append(f"Missing Word Wise: 0 study notes found across {total_paras} paragraphs in {total_chapters} chapters")
        elif total_paras > 50 and (study_notes_count / total_paras) < 0.05:
            issues.append(f"Extremely low study notes: only {study_notes_count} notes in {total_paras} paragraphs")
            
    except Exception as e:
        issues.append(f"ZIP error: {e}")

    return {
        "path": rel_path,
        "filename": fname,
        "total_paras": total_paras,
        "study_notes_count": study_notes_count,
        "total_chapters": total_chapters,
        "valid": len(issues) == 0,
        "issues": issues,
    }

def main():
    print("==================================================================")
    print("🔬 AUDITING ALL EPUBS IN 소설2/[study] FOR WORD WISE & NAMING INTEGRITY")
    print("==================================================================")
    
    epubs = sorted(list(STUDY_ROOT.rglob("*.epub")))
    print(f"📚 Total EPUBs in [study] folder to audit: {len(epubs)}\n")
    
    problem_books = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(audit_single_study_epub, p) for p in epubs]
        for f in as_completed(futs):
            res = f.result()
            if not res["valid"]:
                problem_books.append(res)
                print(f"  ❌ {res['path']}")
                for iss in res["issues"]:
                    print(f"       ⚠️ {iss}")

    print("\n==================================================================")
    print(f"🏁 AUDIT RESULTS: Found {len(problem_books)} flawed books out of {len(epubs)} total in [study]:")
    print("==================================================================")
    
    # Categorize
    misnamed = [b for b in problem_books if any("Misnamed" in i for i in b["issues"])]
    missing_ww = [b for b in problem_books if any("Missing Word Wise" in i or "Extremely low" in i for i in b["issues"])]
    
    print(f"  • Misnamed files (e.g. [k-e] inside [study]): {len(misnamed)}")
    print(f"  • Files missing Word Wise study notes: {len(missing_ww)}")

if __name__ == "__main__":
    main()
