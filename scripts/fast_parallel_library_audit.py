#!/usr/bin/env python3
"""scripts/fast_parallel_library_audit.py

Fast parallel audit of all books in `소설2/[k]` for:
1. Mechanical jumping TOCs (e.g. 2장, 3장, 5장).
2. Untranslated English paragraphs (>5 untranslated paragraphs).
"""

from __future__ import annotations

import json
import re
import warnings
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
K_ROOT = LIB_ROOT / "[k]"

def audit_single_epub(epub_path_str: str) -> dict:
    ep = Path(epub_path_str)
    res = {
        "name": ep.name,
        "path": str(ep),
        "untranslated_count": 0,
        "broken_toc": False,
        "toc_issue": "",
        "samples": []
    }
    
    try:
        with zipfile.ZipFile(ep, "r") as z:
            # 1. Audit TOC
            nav_file = next((n for n in z.namelist() if "nav" in n.lower() or "toc" in n.lower()), None)
            if nav_file:
                soup = BeautifulSoup(z.read(nav_file), "html.parser")
                toc_titles = [a.get_text().strip() for a in soup.find_all("a")]
                nums = []
                for t in toc_titles:
                    m = re.search(r'^(\d+)장$', t)
                    if m:
                        nums.append(int(m.group(1)))
                if len(nums) >= 3:
                    if nums[0] != 1 or any(nums[i+1] - nums[i] > 1 for i in range(len(nums)-1)):
                        res["broken_toc"] = True
                        res["toc_issue"] = f"Jumping chapter numbers: {nums[:8]}"
                        
            # 2. Audit Korean translation
            for n in z.namelist():
                if n.endswith((".xhtml", ".html", ".htm")) and not any(k in n.lower() for k in ["toc", "nav", "cover", "xray"]):
                    soup = BeautifulSoup(z.read(n), "html.parser")
                    for p in soup.find_all("p"):
                        txt = p.get_text().strip()
                        if len(txt) > 30 and not re.search(r"[가-힣]", txt):
                            res["untranslated_count"] += 1
                            if len(res["samples"]) < 2:
                                res["samples"].append(f"[{n}] {txt[:70]}...")
                                
    except Exception as e:
        res["error"] = str(e)
        
    return res

def main():
    print("==================================================================")
    print("⚡ FAST PARALLEL AUDIT ACROSS FULL [k] LIBRARY")
    print("==================================================================")
    
    epubs = [str(p) for p in K_ROOT.rglob("*.epub") if p.stat().st_size > 50000]
    print(f"📚 Auditing {len(epubs):,} books in parallel (12 workers)...")
    
    untranslated_list = []
    broken_toc_list = []
    
    with ProcessPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(audit_single_epub, ep) for ep in epubs]
        for fut in as_completed(futures):
            r = fut.result()
            if r.get("untranslated_count", 0) > 5:
                untranslated_list.append(r)
                print(f"  ⚠️ [Untranslated] {r['name']} ({r['untranslated_count']} english paras)")
            if r.get("broken_toc"):
                broken_toc_list.append(r)
                print(f"  ⚠️ [Broken TOC] {r['name']} -> {r['toc_issue']}")
                
    print("\n==================================================================")
    print("📊 FAST AUDIT SUMMARY")
    print(f"  • Total Books Audited           : {len(epubs):,} books")
    print(f"  • Books with Untranslated Text  : {len(untranslated_list):,} books")
    print(f"  • Books with Broken Jumping TOC : {len(broken_toc_list):,} books")
    print("==================================================================")
    
    report = {
        "untranslated_books": untranslated_list,
        "broken_toc_books": broken_toc_list
    }
    out_p = Path("data/library_fast_audit_report.json")
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"✅ Report saved to: {out_p}")

if __name__ == "__main__":
    main()
