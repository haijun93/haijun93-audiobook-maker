#!/usr/bin/env python3
"""scripts/unify_cixin_liu_deaths_end_terms.py

1. Systematically standardizes all inconsistent terminology, character names, and era titles
   across all editions of Cixin Liu's Death's End (Three Body 3) in `/Users/hyeokjunkong/Desktop/소설2/`.
2. Preserves HTML structure and tags.
3. Reports before-and-after frequency statistics.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

# Terminology & Character Replacement Rules for Death's End
# Format: (Target Canonical Term, [List of inconsistent variations to replace])
TERM_REPLACEMENTS = [
    # 1. Sophon -> 지자 (智子)
    ("지자", ["소폰", "지폰", "소포논"]),

    # 2. Swordholder -> 검잡이 (執劍人)
    ("검잡이", ["집검인", "소드홀더", "소드 홀더"]),

    # 3. Droplet -> 물방울 (水滴)
    ("물방울", ["수적(水滴)", "드롭릿"]),

    # 4. Dark Forest -> 암흑의 숲 (黑暗森林)
    ("암흑의 숲", ["어두운 숲", "다크 포레스트", "다크포레스트"]),

    # 5. Deterrence Era -> 억제 시대 (威懾紀元)
    ("억제 시대", ["위협 시대", "디터런스 시대"]),
    ("억제 후 시대", ["위협 후 시대", "포스트 디터런스 시대"]),

    # 6. Two-Vector Foil -> 이방향박편 / 2차원 박편 (二向箔)
    ("2차원 박편", ["투벡터 포일", "투 벡터 포일", "투-벡터 포일", "이향박"]),

    # 7. Character Names
    ("관이판", ["관일범", "관이반"]),
    ("뤄지", ["루오지", "뤄 지"]),
    ("토머스 웨이드", ["토마스 웨이드", "토마스웨이드", "토머스웨이드"]),
    ("아이 AA", ["아이AA", "아이 에이에이"]),
    ("윈톈밍", ["윈티엔밍", "윈티안밍", "윤천명"]),
    ("비윈펑", ["비윈젠", "필운봉"]),
    ("장베이하이", ["장북해"]),
    ("가수", ["싱어(Singer)", "노래하는 자"]),
]

def replace_terms_in_html(html_text: str, is_korean_only: bool = False) -> tuple[str, dict[str, int]]:
    counts = {}
    soup = BeautifulSoup(html_text, "html.parser")

    # Only replace text inside text nodes, avoid touching tags and attributes
    for node in soup.find_all(text=True):
        if node.parent.name in ["script", "style"]:
            continue
        original_text = str(node)
        new_text = original_text

        for canonical, variants in TERM_REPLACEMENTS:
            for var in variants:
                if var in new_text:
                    c = new_text.count(var)
                    counts[f"{var} -> {canonical}"] = counts.get(f"{var} -> {canonical}", 0) + c
                    new_text = new_text.replace(var, canonical)

        # Special context check for Ding Yi (물리학자 정의 -> 딩이)
        # "정의 박사", "물리학자 정의", "정의가", "정의는", "정의에게" where it refers to Ding Yi
        ding_yi_patterns = [
            (r"(?<!\w)정의(?= 박사| 교수| 물리학자| 학자)", "딩이"),
            (r"(?<=[^\w]딩이 )정의(?=[^\w])", "딩이"),
            (r"(?<=[,\.\s])정의(?=는 물리학|는 기초과학|의 이론|와 함께|가 말했다|가 물었다|는 고개를|는 웃으며)", "딩이")
        ]
        for pat, rep in ding_yi_patterns:
            matches = len(re.findall(pat, new_text))
            if matches > 0:
                counts[f"정의(Ding Yi) -> {rep}"] = counts.get(f"정의(Ding Yi) -> {rep}", 0) + matches
                new_text = re.sub(pat, rep, new_text)

        if new_text != original_text:
            node.replace_with(new_text)

    return str(soup), counts

def process_single_epub(epub_path: Path):
    print(f"\n⚡ Standardizing terminology in: {epub_path.name}")
    print(f"   📁 Location: {epub_path.parent.relative_to(LIB_ROOT)}")

    total_modifications = {}
    temp_zip_buf = io.BytesIO()

    with zipfile.ZipFile(epub_path, "r") as src_zip:
        with zipfile.ZipFile(temp_zip_buf, "w", zipfile.ZIP_DEFLATED) as dst_zip:
            for item in src_zip.infolist():
                content = src_zip.read(item.filename)
                if item.filename.endswith((".xhtml", ".html", ".htm")):
                    try:
                        html_str = content.decode("utf-8")
                        new_html, mod_counts = replace_terms_in_html(html_str)
                        for k, v in mod_counts.items():
                            total_modifications[k] = total_modifications.get(k, 0) + v
                        dst_zip.writestr(item, new_html.encode("utf-8"))
                    except Exception:
                        dst_zip.writestr(item, content)
                else:
                    dst_zip.writestr(item, content)

    if total_modifications:
        epub_path.write_bytes(temp_zip_buf.getvalue())
        print(f"   ✅ Successfully unified {sum(total_modifications.values()):,} terminology instances:")
        for k, v in sorted(total_modifications.items(), key=lambda x: x[1], reverse=True):
            print(f"      • {k}: {v:,} changes")
    else:
        print("   ✨ Already fully standardized (0 changes needed).")

def main():
    print("==================================================================")
    print("🌟 THREE BODY 3 (DEATH'S END) TERMINOLOGY STANDARDIZATION ENGINE")
    print("==================================================================")

    # Target all editions of Death's End
    target_files = []
    for ed in ["[k]", "[k-e]", "[study]", "[xteink]/[study]", "[xteink]/[e-s]"]:
        dir_p = LIB_ROOT / ed / "Fantasy_Science_Fiction" / "#Cixin Liu"
        if dir_p.exists():
            for f in dir_p.glob("*Death*.epub"):
                target_files.append(f)
            for f in dir_p.glob("*death*.epub"):
                if f not in target_files:
                    target_files.append(f)

    print(f"📚 Found {len(target_files)} target EPUBs across all library editions.\n")
    for epub_file in target_files:
        process_single_epub(epub_file)

    print("\n==================================================================")
    print("🎉 ALL TERMINOLOGY & CHARACTER NAMES SUCCESSFULLY UNIFIED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
