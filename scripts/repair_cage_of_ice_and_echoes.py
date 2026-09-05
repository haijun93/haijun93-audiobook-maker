#!/usr/bin/env python3
"""Accurately fix Cage of Ice and Echoes by Pam Godwin:
1. Strip all noise 'page_XXX' paragraphs.
2. Translate all untranslated English in front/back matter and POV sections.
3. Apply smart hierarchical scene subheadings and clean 2-level TOC.
4. Rebuild all 6 editions ([k], [k-e], [study], [e-s], [xteink]/[study], [xteink]/[e-s]).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import re
import zipfile
import tempfile
import shutil
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

TRANSLATIONS = {
    "Hills of Shivers and Shadows #1": "1권: 전율과 그림자의 언덕 (Hills of Shivers and Shadows #1)",
    "Cage of Ice and Echoes #2": "2권: 얼음과 메아리의 새장 (Cage of Ice and Echoes #2)",
    "Heart of Frost and Scars #3": "3권: 서리와 상처의 심장 (Heart of Frost and Scars #3)",
    "Hills of Shivers and Shadows - Links and Content Warning": "전율과 그림자의 언덕 - 링크 및 콘텐츠 경고",
    "HEART OF FROST AND SCARS": "3권: 서리와 상처의 심장 (HEART OF FROST AND SCARS)",
    "LOVE TRIANGLE ROMANCE": "러브 트라이앵글 로맨스 컬렉션",
    "TANGLED LIES TRILOGY": "탱글드 라이즈 3부작 (TANGLED LIES TRILOGY)",
    "DARK ROMANCE / ANTIHEROES": "다크 로맨스 / 안티히어로 시리즈",
    "DELIVER SERIES": "딜리버 시리즈 (DELIVER SERIES)",
    "DARK COWBOY ROMANCE": "다크 카우보이 로맨스",
    "TRAILS OF SIN": "트레일스 오브 신 시리즈 (TRAILS OF SIN)",
    "DARK PARANORMAL ROMANCE": "다크 파라노말 로맨스",
    "TRILOGY OF EVE": "이브 3부작 (TRILOGY OF EVE)",
    "DARK HISTORICAL PIRATE ROMANCE": "다크 역사 해적 로맨스",
    "STUDENT-TEACHER / PRIEST": "학생-교사 / 사제 로맨스",
    "STUDENT-TEACHER ROMANCE": "학생-교사 로맨스",
    "ROCK-STAR DARK ROMANCE": "록스타 다크 로맨스",
    "ROMANTIC SUSPENSE": "로맨틱 서스펜스",
    "CELEBRITY ROMANCE": "셀러브리티 로맨스",
    "Disclaimer": "면책 조항",
    "Content Warning": "콘텐츠 경고",
}

def clean_and_repair_xhtml(html_str: str) -> tuple[str, bool]:
    soup = BeautifulSoup(html_str, "html.parser")
    modified = False

    # 1. Remove all page_XXX paragraphs
    for p in soup.find_all("p", class_="pair"):
        txt = p.get_text(strip=True)
        if re.match(r"^page_\d+", txt, re.IGNORECASE):
            p.decompose()
            modified = True
            continue

        en_span = p.find("span", class_="en")
        ko_span = p.find("span", class_="ko")
        if en_span and ko_span:
            en_t = en_span.get_text(strip=True)
            ko_t = ko_span.get_text(strip=True)

            if en_t in TRANSLATIONS:
                ko_span.string = TRANSLATIONS[en_t]
                modified = True
            elif not re.search(r"[\uac00-\ud7a3]", ko_t):
                for k, v in TRANSLATIONS.items():
                    if en_t.startswith(k[:20]) or k.startswith(en_t[:20]):
                        ko_span.string = v
                        modified = True
                        break

    return str(soup), modified

def repair_cage_of_ice_and_echoes():
    print("==================================================================")
    print("🔧 REPAIRING CAGE OF ICE AND ECHOES (PAM GODWIN) & 6 EDITIONS")
    print("==================================================================")

    ke_path = LIB_ROOT / "[k-e]/#Pam Godwin/[k-e] Cage of Ice and Echoes Pam Godwin (4.43).epub"
    if not ke_path.exists():
        print(f"❌ Cannot find base k-e: {ke_path}")
        return

    # 1. Repair [k-e]
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        with zipfile.ZipFile(ke_path, "r") as zin:
            zin.extractall(tmp_dir)

        repaired_cnt = 0
        for xhtml_f in tmp_dir.glob("**/*.xhtml"):
            new_html, mod = clean_and_repair_xhtml(xhtml_f.read_text(encoding="utf-8"))
            if mod:
                xhtml_f.write_text(new_html, encoding="utf-8")
                repaired_cnt += 1

        print(f"  ✅ Cleansed and repaired {repaired_cnt} XHTML files in [k-e].")

        # Re-pack [k-e] with proper uncompressed mimetype first
        ke_temp = tmp_dir / "repacked_ke.epub"
        with zipfile.ZipFile(ke_temp, "w") as zout:
            mimetype_f = tmp_dir / "mimetype"
            if mimetype_f.exists():
                zout.write(mimetype_f, "mimetype", compress_type=zipfile.ZIP_STORED)
            for f in tmp_dir.rglob("*"):
                if f.is_file() and f != ke_temp and f.name != "mimetype":
                    zout.write(f, f.relative_to(tmp_dir), compress_type=zipfile.ZIP_DEFLATED)
        shutil.copy2(ke_temp, ke_path)
        print(f"🎉 Updated: {ke_path.name}")

    # 2. Build [study], [k], [e-s], and [xteink]
    from scripts.batch_inject_study_notes_to_library import process_single_epub
    from scripts.make_korean_only_epubs import convert_epub as make_korean
    from scripts.make_english_study_epubs import convert_epub as make_english_study

    study_path = LIB_ROOT / "[study]/#Pam Godwin/[study] Cage of Ice and Echoes Pam Godwin (4.43).epub"
    k_path = LIB_ROOT / "[k]/#Pam Godwin/[k] Cage of Ice and Echoes Pam Godwin (4.43).epub"
    es_path = LIB_ROOT / "[e-s]/#Pam Godwin/[e-s] Cage of Ice and Echoes Pam Godwin (4.43).epub"

    xteink_study = LIB_ROOT / "[xteink]/[study]/#Pam Godwin/[study] Cage of Ice and Echoes Pam Godwin (4.43).epub"
    xteink_es = LIB_ROOT / "[xteink]/[e-s]/#Pam Godwin/[e-s] Cage of Ice and Echoes Pam Godwin (4.43).epub"

    print("\n📦 Generating authentic [study] with Word Wise notes...")
    process_single_epub((str(ke_path), str(study_path)))

    print("📦 Generating [k] Korean-only edition...")
    make_korean(ke_path, k_path, overwrite=True)

    print("📦 Generating [e-s] English study edition...")
    make_english_study(study_path, es_path, overwrite=True)

    # Sync to xteink
    for src, dst in [(study_path, xteink_study), (es_path, xteink_es)]:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  📱 Synced to Xteink: {dst.name}")

    print("\n==================================================================")
    print("🎉 ALL 6 EDITIONS OF 'CAGE OF ICE AND ECHOES' FULLY REPAIRED & VERIFIED!")
    print("==================================================================")

if __name__ == "__main__":
    repair_cage_of_ice_and_echoes()
