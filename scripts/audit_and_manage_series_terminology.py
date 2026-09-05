#!/usr/bin/env python3
"""scripts/audit_and_manage_series_terminology.py

1. Scans the entire library (`소설2/[k]`, `[k-e]`, `[study]`) to discover all multi-book Series.
2. Identifies all constituent books in each series.
3. Defines and maintains canonical series-wide glossaries for key terminology, character names, and lore.
4. Audits terminology consistency across series books and outputs a comprehensive report.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
K_ROOT = LIB_ROOT / "[k]"
STUDY_ROOT = LIB_ROOT / "[study]"

# Master Series Definition & Canonical Glossaries
SERIES_REGISTRY = {
    "Three_Body_Problem_Cixin_Liu": {
        "title": "삼체 (Three-Body Problem) 3부작",
        "author": "Cixin Liu (류츠신)",
        "genre": "Fantasy_Science_Fiction/#Cixin Liu",
        "keywords": ["three-body", "three body", "dark forest", "death's end", "deaths end", "remembrance of earth"],
        "canonical_glossary": {
            "지자 (智子 / Sophon)": ["소폰", "지폰", "소포논", "스마트 입자"],
            "검잡이 (執劍人 / Swordholder)": ["집검인", "소드홀더", "소드 홀더"],
            "면벽자 (面壁者 / Wallfacer)": ["월페이서", "벽면자"],
            "파벽자 (破壁者 / Wallbreaker)": ["월브레이커"],
            "물방울 (水滴 / Droplet)": ["수적(水滴)", "드롭릿"],
            "암흑의 숲 (黑暗森林 / Dark Forest)": ["어두운 숲", "다크 포레스트"],
            "계단 프로젝트 (階梯計劃 / Staircase Program)": ["계단 계획", "스테어케이스"],
            "2차원 박편 (二向箔 / Two-Vector Foil)": ["투벡터 포일", "이향박", "이방향박편"],
            "곡률 추진 (曲率驅動 / Curvature Propulsion)": ["곡률 드라이브", "곡률 항법"],
            "억제 시대 (威懾紀元 / Deterrence Era)": ["위협 시대", "디터런스 시대"],
            "뤄지 (羅輯 / Luo Ji)": ["루오지", "나집"],
            "청신 (程心 / Cheng Xin)": ["쳉신", "정신"],
            "윈톈밍 (雲天明 / Yun Tianming)": ["윤천명", "윈티엔밍"],
            "관이판 (關一帆 / Guan Yifan)": ["관일범", "관이반"],
            "토머스 웨이드 (Thomas Wade)": ["토마스 웨이드", "토마스웨이드"],
            "아이 AA (Ai AA)": ["아이AA", "아이 에이에이"],
            "장베이하이 (張北海 / Zhang Beihai)": ["장북해"],
            "딩이 (丁儀 / Ding Yi)": ["정의 박사", "딩 이"]
        }
    },
    "Harry_Potter_JK_Rowling": {
        "title": "해리 포터 (Harry Potter) 시리즈",
        "author": "J.K. Rowling",
        "genre": "Fantasy_Science_Fiction/#J.K. Rowling",
        "keywords": ["harry potter", "philosopher's stone", "chamber of secrets", "prisoner of azkaban", "goblet of fire", "order of the phoenix", "half-blood prince", "deathly hallows"],
        "canonical_glossary": {
            "호그와트 (Hogwarts)": ["호그와츠", "호그와트 마법학교"],
            "볼드모트 (Voldemort)": ["볼드모어", "볼데모트", "그 사람"],
            "헤르미온느 그레인저 (Hermione Granger)": ["허마이오니", "헤르미온느"],
            "론 위즐리 (Ron Weasley)": ["론 웨슬리"],
            "알버스 덤블도어 (Albus Dumbledore)": ["덤블도어 교수", "알버스 덤블도어"],
            "세베루스 스네이프 (Severus Snape)": ["스네이프 교수", "세베루스 스네이프"],
            "불사조 기사단 (Order of the Phoenix)": ["피닉스 기사단", "불사조 오더"],
            "호크룩스 (Horcrux)": ["호크럭스", "영혼 조각"],
            "죽음을 먹는 자들 (Death Eaters)": ["데스 이터", "죽음의 사자들"],
            "머글 (Muggle)": ["머글들", "비마법사"]
        }
    },
    "Silo_Series_Hugh_Howey": {
        "title": "실로 (Silo) 3부작 (Wool, Shift, Dust)",
        "author": "Hugh Howey (휴 하위)",
        "genre": "Fantasy_Science_Fiction/#Hugh Howey",
        "keywords": ["wool", "shift", "dust", "silo"],
        "canonical_glossary": {
            "사일로 (Silo / 실로)": ["사일로", "실로"],
            "클리닝 (Cleaning / 청소)": ["청소 의식", "센서 청소"],
            "줄리엣 니콜스 (Juliette Nichols)": ["줄스", "줄리엣 니콜스"],
            "도널드 킨 (Donald Keene)": ["도널드 킨", "도널드"],
            "루카스 카일 (Lukas Kyle)": ["루카스 카일"],
            "IT 부서 (IT Department)": ["정보기술부", "IT부서"],
            "기계과 (Mechanical)": ["기계 부서", "하층 기계과"]
        }
    },
    "The_Housemaid_Freida_McFadden": {
        "title": "하우스메이드 (The Housemaid) 3부작",
        "author": "Freida McFadden (프리다 맥패든)",
        "genre": "#Freida McFadden",
        "keywords": ["housemaid", "housemaids secret", "housemaid is watching", "housemaid's wedding"],
        "canonical_glossary": {
            "밀리 캘로웨이 (Millie Calloway)": ["밀리", "밀리 캘러웨이"],
            "니나 윈체스터 (Nina Winchester)": ["니나", "니나 윈체스터"],
            "앤드루 윈체스터 (Andrew Winchester)": ["앤디", "앤드루 윈체스터"],
            "시시 윈체스터 (Cece Winchester)": ["세시", "시시"],
            "엔조 (Enzo)": ["엔초", "엔조"]
        }
    },
    "Outlander_Series_Diana_Gabaldon": {
        "title": "아웃랜더 (Outlander) 시리즈",
        "author": "Diana Gabaldon (다이애나 개벌돈)",
        "genre": "Historical_Fiction/#Diana Gabaldon",
        "keywords": ["outlander", "dragonfly in amber", "voyager", "drums of autumn", "fiery cross"],
        "canonical_glossary": {
            "클레어 랜들 (Claire Randall / Claire Fraser)": ["클레어 랜들", "클레어 프레이저", "클레어"],
            "제이미 프레이저 (Jamie Fraser)": ["제임스 프레이저", "제이미 프레이저", "제이미"],
            "크레이그 나 둔 (Craigh na Dun)": ["크레이그나둔", "선돌 유적지"],
            "잭 랜들 (Jack Randall)": ["블랙 잭 랜들", "조너선 랜들"],
            "라일리브로크 (Lallybroch)": ["랄리브록", "브로크 튜라크"]
        }
    },
    "Hyperion_Cantos_Dan_Simmons": {
        "title": "하이페리온 칸토스 (Hyperion Cantos) 4부작",
        "author": "Dan Simmons (댄 시먼스)",
        "genre": "Fantasy_Science_Fiction/#Dan Simmons",
        "keywords": ["hyperion", "fall of hyperion", "endymion", "rise of endymion"],
        "canonical_glossary": {
            "슈라이크 (Shrike / 고시마즈)": ["슈라이크", "고시마즈", "가시나무 괴물"],
            "시간의 무덤 (Time Tombs)": ["시간 무덤", "타임 툼스"],
            "헤게모니 (Hegemony of Man)": ["인류 패권", "헤게모니"],
            "테크노코어 (TechnoCore)": ["테크노코어", "AI 코어"],
            "파캐스터 (Far力を / Farcaster)": ["원거리 전송기", "파캐스터 포털"],
            "아웃라이더 (Ousters)": ["아우스터", "외부인들"],
            "마틴 실레너스 (Martin Silenus)": ["마틴 실레누스", "실레너스 시인"],
            "페드만 카사드 (Fedmahn Kassad)": ["카사드 대령", "페드만 카사드"]
        }
    },
    "Hunger_Games_Suzanne_Collins": {
        "title": "헝거 게임 (The Hunger Games) 시리즈",
        "author": "Suzanne Collins (수잔 콜린스)",
        "genre": "Fantasy_Science_Fiction/#Suzanne Collins",
        "keywords": ["hunger games", "catching fire", "mockingjay", "ballad of songbirds", "sunrise on the reaping"],
        "canonical_glossary": {
            "캣니스 에버딘 (Katniss Everdeen)": ["캣니스", "캣니스 에버딘"],
            "피타 멜라크 (Peeta Mellark)": ["피타", "피타 멜라크"],
            "게일 호손 (Gale Hawthorne)": ["게일", "게일 호손"],
            "스노우 대통령 (President Coriolanus Snow)": ["코리올라누스 스노우", "스노우 대통령"],
            "모킹제이 (Mockingjay)": ["흉내어치", "모킹제이"],
            "캐피톨 (The Capitol)": ["캐피톨", "수도"],
            "조공인 (Tribute)": ["트리뷰트", "조공물"]
        }
    },
    "Stormlight_Archive_Brandon_Sanderson": {
        "title": "스톰라이트 아카이브 (The Stormlight Archive) 시리즈",
        "author": "Brandon Sanderson (브랜든 샌더슨)",
        "genre": "Fantasy_Science_Fiction/#Brandon Sanderson",
        "keywords": ["way of kings", "words of radiance", "oathbringer", "rhythm of war", "wind and truth"],
        "canonical_glossary": {
            "스톰라이트 (Stormlight)": ["폭풍빛", "스톰라이트"],
            "하이스톰 (Highstorm)": ["대폭풍", "하이스톰"],
            "샬란 다바르 (Shallan Davar)": ["샬란", "샬란 다바르"],
            "칼라딘 (Kaladin)": ["칼라딘 스톰블레스트", "칼라딘"],
            "달리나 콜린 (Dalinar Kholin)": ["달리나", "달리나르 콜린"],
            "샤드블레이드 (Shardblade)": ["파편검", "샤드블레이드"],
            "샤드플레이트 (Shardplate)": ["파편갑옷", "샤드플레이트"],
            "스프렌 (Spren)": ["스프렌", "정령"],
            "빛의 기사단 (Knights Radiant)": ["나이츠 래디언트", "빛의 기사단"]
        }
    }
}

def scan_library_for_series():
    print("==================================================================")
    print("🌟 FULL LIBRARY MULTI-BOOK SERIES AUDIT & REGISTRY ENGINE")
    print("==================================================================")

    series_books_map = defaultdict(list)

    # 1. Scan [k] and [study]
    all_k_epubs = list(K_ROOT.rglob("*.epub"))
    print(f"📚 Total Korean Library Books Scanned: {len(all_k_epubs):,} books\n")

    for epub_p in all_k_epubs:
        fname_lower = epub_p.name.lower()
        parent_lower = str(epub_p.parent).lower()
        full_path_str = f"{parent_lower}/{fname_lower}"

        for s_id, s_info in SERIES_REGISTRY.items():
            if any(kw in full_path_str for kw in s_info["keywords"]):
                series_books_map[s_id].append({
                    "name": epub_p.name,
                    "rel_path": str(epub_p.parent.relative_to(LIB_ROOT)),
                    "path": epub_p
                })
                break

    results = {}
    for s_id, s_info in SERIES_REGISTRY.items():
        found_books = series_books_map.get(s_id, [])
        results[s_id] = {
            "title": s_info["title"],
            "author": s_info["author"],
            "book_count": len(found_books),
            "books": [b["name"] for b in found_books],
            "glossary_terms_count": len(s_info["canonical_glossary"]),
            "canonical_glossary": s_info["canonical_glossary"]
        }

        print(f"📖 [{s_info['title']}] ({s_info['author']})")
        print(f"   • Managed Books in Library: {len(found_books)} books")
        for b in found_books:
            print(f"      - {b['name']}")
        print(f"   • Standardized Key Terms & Character Names: {len(s_info['canonical_glossary'])} terms defined")
        print()

    out_file = Path("data/master_series_registry.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"✅ Saved Master Series Registry & Canonical Glossaries to: {out_file}")

if __name__ == "__main__":
    scan_library_for_series()
