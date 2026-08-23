#!/usr/bin/env python3
"""scripts/audit_cixin_liu_deaths_end_terms.py

Audits terminology, characters, and concepts across all EPUB files of Death's End in `소설2/[k]` and other editions.
"""

from __future__ import annotations

import zipfile
import re
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
K_ROOT = LIB_ROOT / "[k]" / "Fantasy_Science_Fiction" / "#Cixin Liu"

TARGET_TERMS = [
    # Concepts & Tech
    ("소폰", "지폰", "지자", "소포논", "스마트 입자"),
    ("검잡이", "집검인", "칼잡이", "소드홀더"),
    ("면벽자", "월페이서"),
    ("파벽자", "월브레이커"),
    ("수적", "물방울", "드롭릿"),
    ("계단 프로젝트", "계단 계획", "스테어케이스 프로젝트"),
    ("암흑의 숲", "다크 포레스트", "어두운 숲"),
    ("이방향박편", "이차원박편", "2차원 포일", "이향박", "투벡터 포일"),
    ("곡률 추진", "곡률 항법", "곡률 드라이브"),
    ("의심의 사슬", "의심의 연쇄"),
    ("기술 폭발", "기술의 비약"),
    ("소우주", "미니 우주", "포켓 유니버스"),
    ("억제 시대", "위협 시대", "디터런스 시대"),
    ("벙커 시대", "차폐 시대", "엄체 시대"),
    ("방송 시대", "브로드캐스트 시대"),
    ("은하 시대", "갤럭시 시대"),
    
    # Characters
    ("청신", "쳉신", "챙신", "정신"),
    ("윈톈밍", "윤천명", "윈티엔밍", "윈티안밍"),
    ("토머스 웨이드", "토마스 웨이드", "토마스웨이드", "토머스웨이드"),
    ("아이 AA", "아이AA", "아이 에이에이", "에이 에이"),
    ("관이판", "관일범", "관이반"),
    ("뤄지", "루오지", "나집"),
    ("딩이", "정의", "딩 이"),
    ("차오빈", "카오빈", "조빈"),
    ("비윈펑", "비윈젠", "필운봉"),
    ("장베이하이", "장북해"),
    ("가수", "노래하는 자", "싱어")
]

def audit_epub(epub_path: Path):
    print(f"\n==================================================================")
    print(f"📖 Auditing EPUB: {epub_path.name}")
    print(f"==================================================================")
    
    if not epub_path.exists():
        print("  ❌ File does not exist.")
        return
        
    full_text = []
    with zipfile.ZipFile(epub_path, "r") as z:
        for name in z.namelist():
            if name.endswith((".xhtml", ".html", ".htm")):
                soup = BeautifulSoup(z.read(name), "html.parser")
                full_text.append(soup.get_text())
                
    content = " ".join(full_text)
    print(f"  • Total text length: {len(content):,} characters")
    
    term_counts = {}
    for group in TARGET_TERMS:
        group_counts = {}
        for term in group:
            cnt = len(re.findall(re.escape(term), content))
            if cnt > 0:
                group_counts[term] = cnt
        if group_counts:
            term_counts[" / ".join(group)] = group_counts
            
    for grp_name, counts in term_counts.items():
        print(f"  🔍 [{grp_name}]")
        for term, c in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            print(f"     - '{term}': {c:,} occurrences")

def main():
    target_epubs = list(K_ROOT.glob("*Death*.epub")) + list(K_ROOT.glob("*death*.epub"))
    for ep in target_epubs:
        audit_epub(ep)

if __name__ == "__main__":
    main()
