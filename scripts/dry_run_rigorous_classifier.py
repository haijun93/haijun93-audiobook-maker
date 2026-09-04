#!/usr/bin/env python3
"""scripts/dry_run_rigorous_classifier.py
Audits the exact count of True New-Version vs Old-Version Static Lexicon books
without modifying any filenames.
"""

import zipfile
import re
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor

lib_root = Path("/Users/hyeokjunkong/Desktop/소설2")
study_dir = lib_root / "[study]"
work_base = lib_root / "_chatgpt_translate_work"

def get_verified_work_cache_keys() -> set[str]:
    cache_keys = set()
    if not work_base.exists(): return cache_keys
    for wd in work_base.iterdir():
        if not wd.is_dir(): continue
        td = wd / "translations"
        if not td.exists(): continue
        json_files = list(td.glob("*.json"))
        if len(json_files) < 3: continue
        has_study = False
        for jf in json_files[:5]:
            raw = jf.read_text(encoding="utf-8", errors="ignore")
            if "※학습:" in raw or "study_notes" in raw or "span class=\"study-note\"" in raw:
                has_study = True
                break
        if has_study:
            clean = re.sub(r'[^a-zA-Z0-9가-힣]', '', wd.name.lower())
            if clean: cache_keys.add(clean)
    return cache_keys

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
        return {"path": str(rel_p), "is_new": True, "reason": "Verified Full-Catalogue AI Series"}

    # Check 2: Work Cache Match
    for ck in verified_cache_keys:
        if len(clean_k) >= 6 and (clean_k in ck or ck in clean_k):
            return {"path": str(rel_p), "is_new": True, "reason": f"Work Cache Match ({ck[:20]})"}

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
                            if any(w in nt for w in ["said - 말했다", "dad - 아빠", "for mom - 엄마", "closed - (마음이나 표정이) 닫힌", "maintenance - (이혼 후의) 양육비", "tap - (자원·상처 등을)", "pickle - 곤경"]):
                                static_dict_hits += 1
                            if any(w in nt for w in ["(여기선", "(상황", "(비유", "맥락", "의역", "주인공", "비꼬는", "감탄사", "음역:"]):
                                ai_context_hits += 1
                if total_notes > 80:
                    break
    except Exception as e:
        return {"path": str(rel_p), "is_new": False, "reason": f"Inspection Error: {e}"}

    if static_dict_hits >= 2 or (ai_context_hits < 2 and total_notes > 10):
        return {"path": str(rel_p), "is_new": False, "reason": f"Static Dict Artifacts ({static_dict_hits} hits, {ai_context_hits} context)"}
    elif ai_context_hits >= 4:
        return {"path": str(rel_p), "is_new": True, "reason": f"Rich AI Context ({ai_context_hits} markers)"}
    else:
        return {"path": str(rel_p), "is_new": False, "reason": "No Confirmed AI Markers"}

def main():
    verified_keys = get_verified_work_cache_keys()
    all_study_epubs = sorted([p for p in study_dir.glob("**/*.epub") if not p.name.startswith("._")])
    tasks = [str(p) for p in all_study_epubs]

    new_version_list = []
    old_version_list = []

    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(inspect_single_epub, t, verified_keys) for t in tasks]
        for fut in futures:
            res = fut.result()
            if res["is_new"]:
                new_version_list.append(res)
            else:
                old_version_list.append(res)

    print("==================================================================")
    print("📊 서재 내 도서 원천 번역 이력 및 정적 사전 아티팩트 정밀 전수 검사")
    print("==================================================================")
    print(f"• 서재 내 [study] 총 도서 수                          : {len(all_study_epubs)} 권")
    print(f"• 🌟 검증된 신버전 AI 웹 완역 도서 ([study])           : {len(new_version_list)} 권")
    print(f"• 🏷️ 구버전 정적 사전 주입 도서 ([study-] 재번역 대상)  : {len(old_version_list)} 권")
    print("==================================================================\n")

    print("--- 🏷️ [구버전 정적 사전 주입 도서 샘플 30선 - 재번역 대상] ---")
    for idx, r in enumerate(old_version_list[:30], 1):
        print(f"{idx:2}. {r['path']} | ({r['reason']})")

if __name__ == "__main__":
    main()
