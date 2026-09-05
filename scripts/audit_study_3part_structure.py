#!/usr/bin/env python3
"""scripts/audit_study_3part_structure.py

Audits all [study] EPUBs to detect:
1. 'EN + EN' errors (where the <span class="ko"> contains English instead of Korean)
2. Missing Korean translation spans
3. Missing TOEIC 700+ Study notes (<span class="study-note">)
4. Non-pair or corrupted EPUB structures
"""

import re
import unicodedata
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor, as_completed

def is_korean(text: str) -> bool:
    if not text: return False
    ko = len(re.findall(r'[가-힣]', text))
    en = len(re.findall(r'[a-zA-Z]', text))
    return ko > 0 and (ko >= en * 0.3 or ko >= 5)

def is_english(text: str) -> bool:
    if not text: return False
    en = len(re.findall(r'[a-zA-Z]', text))
    ko = len(re.findall(r'[가-힣]', text))
    return en > 8 and ko == 0

def audit_single_epub(ep_path_str: str, study_dir_str: str):
    ep = Path(ep_path_str)
    study_dir = Path(study_dir_str)
    book_total_paras = 0
    en_en_errors = 0
    missing_ko = 0
    missing_study = 0
    sample_en_en = []

    try:
        with zipfile.ZipFile(ep, "r") as z:
            for name in z.namelist():
                if not (name.endswith(".xhtml") or name.endswith(".html")):
                    continue
                content = z.read(name).decode("utf-8", errors="ignore")
                if "class=\"pair\"" not in content and "class='pair'" not in content and "<p class=\"pair\"" not in content:
                    continue

                soup = BeautifulSoup(content, "html.parser")
                pairs = soup.find_all(class_=lambda c: c and "pair" in c)

                for p in pairs:
                    book_total_paras += 1
                    en_span = p.find("span", class_="en")
                    ko_span = p.find("span", class_="ko")
                    study_span = p.find("span", class_="study-note")

                    en_txt = en_span.get_text(strip=True) if en_span else ""
                    ko_txt = ko_span.get_text(strip=True) if ko_span else ""
                    study_txt = study_span.get_text(strip=True) if study_span else ""

                    if not ko_span or not ko_txt:
                        missing_ko += 1
                    elif is_english(ko_txt) and len(ko_txt) > 15:
                        en_en_errors += 1
                        if len(sample_en_en) < 2:
                            sample_en_en.append(f"EN: {en_txt[:40]}... | KO(error): {ko_txt[:40]}...")

                    if not study_span or not study_txt:
                        if len(en_txt) > 25:
                            missing_study += 1

        return {
            "name": ep.name,
            "rel": str(ep.relative_to(study_dir)),
            "path": str(ep),
            "total_paras": book_total_paras,
            "en_en_errors": en_en_errors,
            "missing_ko": missing_ko,
            "missing_study": missing_study,
            "samples": sample_en_en,
            "error": None
        }
    except Exception as e:
        return {
            "name": ep.name,
            "rel": str(ep.relative_to(study_dir)),
            "path": str(ep),
            "total_paras": 0,
            "en_en_errors": 0,
            "missing_ko": 0,
            "missing_study": 0,
            "samples": [],
            "error": str(e)
        }

def main():
    desktop = Path("/Users/hyeokjunkong/Desktop")
    lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
    study_dir = lib_root / "[study]"

    epubs = sorted(study_dir.glob("**/*.epub"))
    print(f"Auditing {len(epubs)} [study] EPUBs across 8 processes...")

    tasks = [(str(ep), str(study_dir)) for ep in epubs]
    results = []

    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(audit_single_epub, t[0], t[1]) for t in tasks]
        for fut in as_completed(futures):
            results.append(fut.result())

    en_en_list = [r for r in results if r["en_en_errors"] > 0]
    missing_ko_list = [r for r in results if r["missing_ko"] > 0]
    missing_study_list = [r for r in results if r["missing_study"] > 0]
    zero_para_list = [r for r in results if r["total_paras"] == 0]

    print("\n==================================================================")
    print("📊 FULL [study] 3-PART STRUCTURE AUDIT REPORT (514+ Books)")
    print(f"   • Total Books Audited           : {len(results):,}")
    print(f"   • Books with 'EN + EN' Errors   : {len(en_en_list):,}")
    print(f"   • Books with Missing KO Spans   : {len(missing_ko_list):,}")
    print(f"   • Books with Missing Study Notes: {len(missing_study_list):,}")
    print(f"   • Books with 0 Pair Paragraphs  : {len(zero_para_list):,}")
    print("==================================================================")

    if en_en_list:
        en_en_list.sort(key=lambda x: x["en_en_errors"], reverse=True)
        print(f"\n🚨 ALL {len(en_en_list)} BOOKS WITH 'EN + EN' (English in Korean span) ERRORS:")
        for b in en_en_list:
            print(f"  • {b['rel']}")
            print(f"     -> EN+EN Error Count: {b['en_en_errors']:,} / Total: {b['total_paras']:,}")
            for s in b["samples"]:
                print(f"        Sample: {s}")

    if zero_para_list:
        print(f"\n⚠️ ALL {len(zero_para_list)} BOOKS WITH 0 PAIR PARAGRAPHS:")
        for b in zero_para_list:
            print(f"  • {b['rel']}")

if __name__ == "__main__":
    main()
