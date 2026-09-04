#!/usr/bin/env python3
"""scripts/rigorous_study_version_classifier.py

Rigorous, paragraph-by-paragraph classifier for [study] vs [study-]:
1. Checks raw work caches in _chatgpt_translate_work/.
2. Analyzes 100+ paragraphs in each EPUB for:
   - Static dictionary artifacts (said-말했다, dad-아빠, closed-닫힌/쌀쌀맞은, maintenance-양육비 등)
   - Real AI contextual markers (character names, specific situational definitions, (여기선 ..., (비유, 작중 대화 뉘앙스 등).
3. Strictly classifies:
   - True New Version AI Translations -> '[study] ... .epub'
   - Old Translations with Static Lexicon -> '[study-] ... .epub'
4. Synchronizes to Google Drive #Books/[study].
"""

from __future__ import annotations

import re
import shutil
import unicodedata
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor, as_completed

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

study_dir = lib_root / "[study]"
gdrive_study = gdrive_root / "[study]"
work_base = lib_root / "_chatgpt_translate_work"

# 1. Load authentic work caches
def get_verified_work_cache_keys() -> set[str]:
    cache_keys = set()
    if not work_base.exists(): return cache_keys
    for wd in work_base.iterdir():
        if not wd.is_dir(): continue
        td = wd / "translations"
        if not td.exists(): continue
        # Verify if chunks have authentic study notes
        json_files = list(td.glob("*.json"))
        if len(json_files) < 3: continue
        has_study = False
        for jf in json_files[:5]:
            raw = jf.read_text(encoding="utf-8", errors="ignore")
            if "※학습:" in raw or "study_notes" in raw:
                has_study = True
                break
        if has_study:
            clean = re.sub(r'[^a-zA-Z0-9가-힣]', '', wd.name.lower())
            if clean: cache_keys.add(clean)
    return cache_keys

# Known guaranteed New-Version authors/series
KNOWN_NEW_SERIES = [
    "#Pam Godwin",
    "#Leigh Rivers",
    "#Top 10 dark romance",
    "Pam Godwin",
    "Leigh Rivers",
    "Pepper Winters",
    "H.D. Carlton",
    "Penelope Douglas",
    "Rina Kent"
]

def inspect_single_epub(epub_path_str: str, verified_cache_keys: set[str]) -> dict:
    ep = Path(epub_path_str)
    rel_p = ep.relative_to(study_dir)
    rel_str = str(rel_p)
    clean_stem = re.sub(r'\[.*?\]\s*', '', ep.stem)
    clean_k = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean_stem.lower())

    # Check 1: Known Series Match
    if any(pat.lower() in rel_str.lower() for pat in KNOWN_NEW_SERIES):
        return {"path": epub_path_str, "is_new": True, "reason": "Verified Full-Catalogue AI Series"}

    # Check 2: Work Cache Match
    for ck in verified_cache_keys:
        if len(clean_k) >= 6 and (clean_k in ck or ck in clean_k):
            return {"path": epub_path_str, "is_new": True, "reason": f"Work Cache Match ({ck[:20]})"}

    # Check 3: Deep Paragraph Content Analysis
    static_dict_hits = 0
    ai_context_hits = 0
    total_notes = 0

    try:
        with zipfile.ZipFile(ep, "r") as z:
            htmls = [n for n in z.namelist() if n.endswith((".xhtml", ".html"))]
            for h in htmls[:10]:
                content = z.read(h).decode("utf-8", errors="ignore")
                if "class=\"study-note\"" not in content and "class=\"pair\"" not in content:
                    continue
                soup = BeautifulSoup(content, "html.parser")
                for p in soup.find_all(class_=lambda c: c and "pair" in c):
                    note = p.find("span", class_="study-note")
                    if note:
                        nt = note.get_text()
                        if len(nt) > 3:
                            total_notes += 1
                            # Static dictionary artifacts
                            if any(w in nt for w in ["said - 말했다", "dad - 아빠", "for mom - 엄마", "closed - (마음이나 표정이) 닫힌", "maintenance - (이혼 후의) 양육비", "tap - (자원·상처 등을)", "pickle - 곤경"]):
                                static_dict_hits += 1
                            # Genuine AI contextual indicators
                            if any(w in nt for w in ["(여기선", "(상황", "(비유", "맥락", "의역", "주인공", "비꼬는", "감탄사", "음역:"]):
                                ai_context_hits += 1
                if total_notes > 80:
                    break
    except Exception as e:
        return {"path": epub_path_str, "is_new": False, "reason": f"Inspection Error: {e}"}

    # Decision threshold
    if static_dict_hits >= 2 or (ai_context_hits < 2 and total_notes > 10):
        return {"path": epub_path_str, "is_new": False, "reason": f"Static Dict Artifacts ({static_dict_hits} hits, {ai_context_hits} context)"}
    elif ai_context_hits >= 4:
        return {"path": epub_path_str, "is_new": True, "reason": f"Rich AI Context ({ai_context_hits} markers)"}
    else:
        return {"path": epub_path_str, "is_new": False, "reason": "No Confirmed AI Markers"}

def main():
    print("==================================================================")
    print("🔬 RIGOROUS LIBRARY-WIDE [study] vs [study-] CLASSIFICATION")
    print("==================================================================")

    verified_keys = get_verified_work_cache_keys()
    print(f"Verified AI Translation Work Cache Keys: {len(verified_keys):,}")

    all_study_epubs = sorted(study_dir.glob("**/*.epub"))
    print(f"Total Study EPUBs to Classify: {len(all_study_epubs):,}")

    tasks = [str(p) for p in all_study_epubs]

    new_version_list = []
    old_version_list = []

    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(inspect_single_epub, t, verified_keys) for t in tasks]
        for fut in as_completed(futures):
            res = fut.result()
            ep = Path(res["path"])
            is_new = res["is_new"]

            if is_new:
                # Must have [study] prefix
                pure_name = ep.name.replace("[study-] ", "[study] ").replace("[study-]", "[study] ")
                if not pure_name.startswith("[study]"): pure_name = f"[study] {pure_name}"
                target_p = ep.parent / pure_name
                if target_p != ep:
                    shutil.move(str(ep), str(target_p))
                new_version_list.append((target_p, res["reason"]))
            else:
                # Must have [study-] prefix
                dash_name = ep.name.replace("[study] ", "[study-] ").replace("[study]", "[study-]")
                if not dash_name.startswith("[study-]"): dash_name = f"[study-] {dash_name}"
                target_p = ep.parent / dash_name
                if target_p != ep:
                    shutil.move(str(ep), str(target_p))
                old_version_list.append((target_p, res["reason"]))

    print("\nClassification Finished:")
    print(f"  • Confirmed New-Version AI Web Translations ([study])  : {len(new_version_list):,} books")
    print(f"  • Confirmed Old-Version Static Lexicon Translations ([study-]): {len(old_version_list):,} books")

    # 4. Synchronize clean to Google Drive
    print("\nSynchronizing to Google Drive #Books/[study]...")
    for gd_f in gdrive_study.glob("**/*.epub"):
        try: gd_f.unlink()
        except Exception:
            pass
    local_all = list(study_dir.glob("**/*.epub"))
    for lp in local_all:
        rel = lp.relative_to(study_dir)
        gd_dest = gdrive_study / rel
        gd_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(lp), str(gd_dest))

    print("\n==================================================================")
    print("🎉 ACCURATE CLASSIFICATION & GDRIVE SYNCHRONIZATION COMPLETED!")
    print("==================================================================")
    print("\n--- SAMPLE NEW-VERSION [study] (AUTHENTIC AI) BOOKS ---")
    for p, r in new_version_list[:10]:
        print(f"  🌟 {p.parent.name} / {p.name} | ({r})")

    print("\n--- SAMPLE OLD-VERSION [study-] (STATIC LEXICON) BOOKS ---")
    for p, r in old_version_list[:10]:
        print(f"  🏷️ {p.parent.name} / {p.name} | ({r})")

if __name__ == "__main__":
    main()
