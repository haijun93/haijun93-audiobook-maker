#!/usr/bin/env python3
"""scripts/audit_all_screen_adaptations_in_library.py

Scans all 586+ books in `/Users/hyeokjunkong/Desktop/소설2/[k]` and detects all Screen Adaptations
(Movies, TV Series, Netflix, HBO, Prime Video, Hulu, Disney+, Apple TV+).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
K_ROOT = LIB_ROOT / "[k]"

# Comprehensive Database of Screen Adaptations (Title/Author keywords -> Adaptation Info)
SCREEN_ADAPTATION_DB = [
    # Mega Franchises & Classics
    {
        "keywords": ["three-body", "three body", "dark forest", "death's end", "remembrance of earth"],
        "author": "Cixin Liu",
        "work": "삼체 (The Three-Body Problem)",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 시리즈 (2024), 텐센트 드라마 (2023)",
        "details": "베네딕트 웡, 에이사 곤살레스 주연 넷플릭스 SF 대작"
    },
    {
        "keywords": ["harry potter", "philosopher's stone", "chamber of secrets", "prisoner of azkaban", "goblet of fire", "order of the phoenix", "half-blood prince", "deathly hallows"],
        "author": "J.K. Rowling",
        "work": "해리 포터 (Harry Potter) 전 시리즈",
        "media_type": "영화 & HBO 시리즈",
        "platform": "워너 브라더스 8부작 영화 (2001~2011), HBO 신규 오리지널 TV 시리즈 제작 중",
        "details": "다니엘 래드클리프, 엠마 왓슨 주연 세기의 판타지 블록버스터"
    },
    {
        "keywords": ["lord of the rings", "hobbit", "fellowship", "two towers", "return of the king"],
        "author": "J.R.R. Tolkien",
        "work": "반지의 제왕 / 호빗",
        "media_type": "영화 & 드라마",
        "platform": "피터 잭슨 3부작 영화 (아카데미 11관왕), 프라임 비디오 '힘의 반지' (2022~)",
        "details": "일라이저 우드, 이언 맥켈런 주연 판타지 영화의 정점"
    },
    {
        "keywords": ["hunger games", "catching fire", "mockingjay", "ballad of songbirds", "sunrise on the reaping"],
        "author": "Suzanne Collins",
        "work": "헝거 게임 (The Hunger Games) 시리즈",
        "media_type": "영화",
        "platform": "라이온스게이트 4부작 영화 (2012~2015) & 프리퀄 (2023)",
        "details": "제니퍼 로렌스 주연 전 세계 디스토피아 신드롬"
    },
    {
        "keywords": ["divergent", "insurgent", "allegiant"],
        "author": "Veronica Roth",
        "work": "다이버전트 (Divergent) 3부작",
        "media_type": "영화",
        "platform": "라이온스게이트 3부작 영화 (2014~2016)",
        "details": "셰일린 우들리, 테오 제임스 주연 SF 액션"
    },
    {
        "keywords": ["dune", "messiah", "children of dune"],
        "author": "Frank Herbert",
        "work": "듄 (Dune)",
        "media_type": "영화 & 드라마",
        "platform": "드니 빌뇌브 감독 영화 '듄 파트 1 & 2' (2021~2024), Max 드라마 '듄: 예언'",
        "details": "티모시 샬라메, 젠데이아 주연 SF 걸작"
    },
    {
        "keywords": ["foundation"],
        "author": "Isaac Asimov",
        "work": "파운데이션 (Foundation)",
        "media_type": "TV 시리즈",
        "platform": "Apple TV+ 오리지널 시리즈 (2021~)",
        "details": "리 페이스, 자레드 해리스 주연 애플 대표 SF 대하 드라마"
    },
    {
        "keywords": ["silo", "wool", "shift", "dust"],
        "author": "Hugh Howey",
        "work": "사일로 (Silo) 3부작",
        "media_type": "TV 시리즈",
        "platform": "Apple TV+ 오리지널 시리즈 (2023~)",
        "details": "레베카 페르구손 주연 디스토피아 미스터리 스릴러"
    },
    {
        "keywords": ["outlander", "dragonfly in amber"],
        "author": "Diana Gabaldon",
        "work": "아웃랜더 (Outlander)",
        "media_type": "TV 시리즈",
        "platform": "Starz & Netflix 7시즌 드라마 (2014~)",
        "details": "카트리나 밸프, 샘 휴언 주연 시공간 타임슬립 로맨스 대작"
    },
    {
        "keywords": ["the witcher", "last wish", "sword of destiny", "blood of elves"],
        "author": "Andrzej Sapkowski",
        "work": "위쳐 (The Witcher)",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 시리즈 (2019~)",
        "details": "헨리 카빌 주연 글로벌 다크 판타지 드라마"
    },
    
    # Thriller, Mystery, Crime Adaptations
    {
        "keywords": ["crawdads sing"],
        "author": "Delia Owens",
        "work": "가재가 노래하는 곳 (Where the Crawdads Sing)",
        "media_type": "영화",
        "platform": "소니 픽처스 영화 (2022) / Netflix 스트리밍",
        "details": "데이지 에드거존스 주연, 리즈 위더스푼 제작 감성 미스터리"
    },
    {
        "keywords": ["the help"],
        "author": "Kathryn Stockett",
        "work": "헬프 (The Help)",
        "media_type": "영화",
        "platform": "드림웍스 영화 (2011)",
        "details": "엠마 스톤, 비올라 데이비스, 옥타비아 스펜서(아카데미 여우조연상) 주연 명작"
    },
    {
        "keywords": ["gone girl"],
        "author": "Gillian Flynn",
        "work": "나를 찾아줘 (Gone Girl)",
        "media_type": "영화",
        "platform": "데이빗 핀처 감독 20세기 폭스 영화 (2014)",
        "details": "벤 애플렉, 로자먼드 파이크 주연 심리 스릴러 걸작"
    },
    {
        "keywords": ["sharp objects"],
        "author": "Gillian Flynn",
        "work": "몸을 긋는 소녀 (Sharp Objects)",
        "media_type": "TV 시리즈",
        "platform": "HBO 미니시리즈 (2018)",
        "details": "에이미 아담스 주연 HBO 명품 스릴러"
    },
    {
        "keywords": ["dark places"],
        "author": "Gillian Flynn",
        "work": "다크 플레이스 (Dark Places)",
        "media_type": "영화",
        "platform": "영화 (2015)",
        "details": "샤를리즈 테론 주연 미스터리 범죄 영화"
    },
    {
        "keywords": ["silence of the lambs", "red dragon", "hannibal"],
        "author": "Thomas Harris",
        "work": "양들의 침묵 / 한니발 / 레드 드래곤",
        "media_type": "영화 & 드라마",
        "platform": "조나단 드미 영화 (아카데미 5관왕), NBC 드라마 '한니발'",
        "details": "안소니 홉킨스, 조디 포스터, 매즈 미켈슨 주연 스릴러의 전설"
    },
    {
        "keywords": ["girl with the dragon tattoo", "played with fire", "hornet's nest", "millennium"],
        "author": "Stieg Larsson",
        "work": "밀레니엄 (The Girl with the Dragon Tattoo) 3부작",
        "media_type": "영화",
        "platform": "스웨덴 3부작 영화 & 데이빗 핀처 할리우드 영화 (2011)",
        "details": "루니 마라, 다니엘 크레이그, 누미 라파스 주연 북유럽 스릴러 정점"
    },
    {
        "keywords": ["you series", "hidden bodies", "you love me", "for you and only you", "you caroline kepnes"],
        "author": "Caroline Kepnes",
        "work": "너의 모든 것 (YOU) 1~4부",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 시리즈 (2018~)",
        "details": "펜 배글리 주연 넷플릭스 글로벌 1위 심리 범죄 드라마"
    },
    {
        "keywords": ["the shining girls", "shining girls"],
        "author": "Lauren Beukes",
        "work": "샤이닝 걸스 (The Shining Girls)",
        "media_type": "TV 시리즈",
        "platform": "Apple TV+ 오리지널 시리즈 (2022)",
        "details": "엘리자베스 모스 주연 타임 트래블 연쇄살인 스릴러"
    },
    {
        "keywords": ["presumed innocent"],
        "author": "Scott Turow",
        "work": "무죄추정 (Presumed Innocent)",
        "media_type": "영화 & TV 시리즈",
        "platform": "해리슨 포드 영화 (1990) & 제이크 질렌할 Apple TV+ 드라마 (2024)",
        "details": "법정 스릴러의 바이블"
    },
    {
        "keywords": ["black bird", "in with the devil"],
        "author": "James Keene",
        "work": "블랙 버드 (Black Bird)",
        "media_type": "TV 시리즈",
        "platform": "Apple TV+ 오리지널 미니시리즈 (2022)",
        "details": "태런 에저턴, 폴 월터 하우저 주연 실화 교도소 심리극"
    },
    {
        "keywords": ["the last thing he told me"],
        "author": "Laura Dave",
        "work": "그가 나에게 말하지 않은 마지막 것",
        "media_type": "TV 시리즈",
        "platform": "Apple TV+ 오리지널 시리즈 (2023~)",
        "details": "제니퍼 가너 주연, 리즈 위더스푼 제작 미스터리 드라마"
    },
    {
        "keywords": ["pachinko"],
        "author": "Min Jin Lee",
        "work": "파친코 (Pachinko)",
        "media_type": "TV 시리즈",
        "platform": "Apple TV+ 오리지널 글로벌 대하 드라마 (2022~)",
        "details": "윤여정, 이민호, 김민하 주연 전 세계 찬사를 받은 명작"
    },
    {
        "keywords": ["the lincoln lawyer"],
        "author": "Michael Connelly",
        "work": "링컨 차를 타는 변호사 (The Lincoln Lawyer)",
        "media_type": "영화 & TV 시리즈",
        "platform": "매튜 맥커너히 영화 (2011) & Netflix 오리지널 드라마 (2022~)",
        "details": "미키 할러 변호사의 법정 활극"
    },
    {
        "keywords": ["bosch", "harry bosch"],
        "author": "Michael Connelly",
        "work": "형사 해리 보슈 (Bosch) 시리즈",
        "media_type": "TV 시리즈",
        "platform": "Amazon Prime Video 7시즌 드라마 & '보슈 레거시'",
        "details": "타이터스 웰리버 주연 정통 하드보일드 수사물"
    },
    {
        "keywords": ["jack reacher", "killing floor", "one shot", "die trying"],
        "author": "Lee Child",
        "work": "잭 리처 (Jack Reacher) 시리즈",
        "media_type": "영화 & TV 시리즈",
        "platform": "톰 크루즈 주연 영화 (2012) & Amazon Prime Video 드라마 '리처' (2022~)",
        "details": "앨런 리치슨 주연 프라임 비디오 최고 흥행 액션 스릴러"
    },
    {
        "keywords": ["the night agent"],
        "author": "Matthew Quirk",
        "work": "나이트 에이전트 (The Night Agent)",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 시리즈 (2023~)",
        "details": "가브리엘 바쏘 주연 넷플릭스 역대 시청 순위 Top 10 첩보 스릴러"
    },
    {
        "keywords": ["behind her eyes"],
        "author": "Sarah Pinborough",
        "work": "비하인드 허 아이즈 (Behind Her Eyes)",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 미니시리즈 (2021)",
        "details": "충격적인 반전의 심리 스릴러 드라마"
    },
    {
        "keywords": ["anatomy of a scandal"],
        "author": "Sarah Vaughan",
        "work": "아나토미 오브 스캔들 (Anatomy of a Scandal)",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 미니시리즈 (2022)",
        "details": "시에나 밀러, 루퍼트 프렌드 주연 정치/법정 스캔들 드라마"
    },
    {
        "keywords": ["shutter island"],
        "author": "Dennis Lehane",
        "work": "셔터 아일랜드 (Shutter Island)",
        "media_type": "영화",
        "platform": "마틴 스코세이지 감독 영화 (2010)",
        "details": "레오나르도 디카프리오, 마크 러팔로 주연 미스터리 명작"
    },
    {
        "keywords": ["mystic river"],
        "author": "Dennis Lehane",
        "work": "미스틱 리버 (Mystic River)",
        "media_type": "영화",
        "platform": "클린트 이스트우드 감독 영화 (2003)",
        "details": "숀 펜(남우주연상), 팀 로빈스(남우조연상) 아카데미 2관왕 걸작"
    },
    {
        "keywords": ["bird box", "malorie"],
        "author": "Josh Malerman",
        "work": "버드 박스 (Bird Box)",
        "media_type": "영화",
        "platform": "Netflix 오리지널 영화 (2018)",
        "details": "산드라 블록 주연 넷플릭스 메가 히트 호러 스릴러"
    },
    
    # Contemporary, Literary & Bestseller Adaptations
    {
        "keywords": ["the martian", "project hail mary"],
        "author": "Andy Weir",
        "work": "마션 / 프로젝트 헤일메리",
        "media_type": "영화",
        "platform": "리들리 스콧 감독 '마션' (2015), 라이언 고슬링 주연 '프로젝트 헤일메리' (2026 개봉 예정)",
        "details": "맷 데이먼 주연 하드 SF 최고 흥행작"
    },
    {
        "keywords": ["a man called ove", "anxious people"],
        "author": "Fredrik Backman",
        "work": "오베라는 남자 (A Man Called Ove / 오토라는 남자)",
        "media_type": "영화 & 드라마",
        "platform": "스웨덴 영화 (2015) & 톰 행크스 주연 영화 '오토라는 남자' (2022)",
        "details": "전 세계를 울린 감동의 휴먼 코미디 드라마"
    },
    {
        "keywords": ["the kite runner", "a thousand splendid suns"],
        "author": "Khaled Hosseini",
        "work": "연을 쫓는 아이 / 천 개의 찬란한 태양",
        "media_type": "영화 & 연극",
        "platform": "마크 포스터 감독 영화 '연을 쫓는 아이' (2007)",
        "details": "골든글로브 및 아카데미 노미네이트 대하 서사"
    },
    {
        "keywords": ["the book thief"],
        "author": "Markus Zusak",
        "work": "책도둑 (The Book Thief)",
        "media_type": "영화",
        "platform": "20세기 폭스 영화 (2013)",
        "details": "제프리 러쉬, 에밀리 왓슨 주연 제2차 세계대전 감동 휴먼 드라마"
    },
    {
        "keywords": ["memoirs of a geisha"],
        "author": "Arthur Golden",
        "work": "게이샤의 추억 (Memoirs of a Geisha)",
        "media_type": "영화",
        "platform": "롭 마샬 감독 콜롬비아 픽처스 영화 (2005)",
        "details": "장쯔이, 와타나베 켄, 양자경 주연 아카데미 3관왕"
    },
    {
        "keywords": ["perfume", "patrick suskind", "patrick süskind"],
        "author": "Patrick Süskind",
        "work": "향수 (Perfume: The Story of a Murderer)",
        "media_type": "영화 & 드라마",
        "platform": "톰 티크베어 감독 영화 (2006) & Netflix 오리지널 시리즈 (2018)",
        "details": "벤 위쇼, 더스틴 호프만 주연 감각적 영상미의 극치"
    },
    {
        "keywords": ["all the light we cannot see"],
        "author": "Anthony Doerr",
        "work": "우리가 볼 수 없는 모든 빛",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 미니시리즈 (2023)",
        "details": "숀 레비 감독, 마크 러팔로 주연 퓰리처상 수상작 원작"
    },
    {
        "keywords": ["the sympathizer"],
        "author": "Viet Thanh Nguyen",
        "work": "동조자 (The Sympathizer)",
        "media_type": "TV 시리즈",
        "platform": "박찬욱 감독 연출 HBO 오리지널 시리즈 (2024)",
        "details": "로버트 다우니 주니어, 호아 쉬안데 주연 퓰리처상 원작"
    },
    {
        "keywords": ["normal people", "conversations with friends"],
        "author": "Sally Rooney",
        "work": "노멀 피플 (Normal People)",
        "media_type": "TV 시리즈",
        "platform": "BBC & Hulu 12부작 드라마 (2020)",
        "details": "폴 메스칼, 데이지 에드거존스 주연 Z세대 대표 청춘 로맨스"
    },
    {
        "keywords": ["one day"],
        "author": "David Nicholls",
        "work": "원 데이 (One Day)",
        "media_type": "영화 & TV 시리즈",
        "platform": "앤 해서웨이 영화 (2011) & Netflix 오리지널 시리즈 (2024)",
        "details": "전 세계를 사로잡은 20년의 엇갈린 러브 스토리"
    },
    {
        "keywords": ["me before you"],
        "author": "Jojo Moyes",
        "work": "미 비포 유 (Me Before You)",
        "media_type": "영화",
        "platform": "워너 브라더스 영화 (2016)",
        "details": "에밀리아 클라크, 샘 클라플린 주연 감동 로맨스"
    },
    {
        "keywords": ["thirteen reasons why", "13 reasons why"],
        "author": "Jay Asher",
        "work": "루머의 루머의 루머 (13 Reasons Why)",
        "media_type": "TV 시리즈",
        "platform": "Netflix 4시즌 오리지널 드라마 (2017~2020)",
        "details": "셀레나 고메즈 제작 넷플릭스 하이틴 신드롬"
    },
    {
        "keywords": ["we were liars"],
        "author": "E. Lockhart",
        "work": "우리가 거짓말쟁이였을 때 (We Were Liars)",
        "media_type": "TV 시리즈",
        "platform": "Amazon Prime Video 신규 오리지널 시리즈 (제작 중)",
        "details": "줄리 플렉 제작 프라임 비디오 기대작"
    },
    {
        "keywords": ["the big short", "moneyball"],
        "author": "Michael Lewis",
        "work": "빅쇼트 / 머니볼",
        "media_type": "영화",
        "platform": "아담 맥케이 감독 '빅쇼트' (2015) & 브래드 피트 '머니볼' (2011)",
        "details": "크리스찬 베일, 라이언 고슬링, 브래드 피트 주연 금융/스포츠 실화 명작"
    },
    {
        "keywords": ["killers of the flower moon"],
        "author": "David Grann",
        "work": "플라워 킬링 문 (Killers of the Flower Moon)",
        "media_type": "영화",
        "platform": "마틴 스코세이지 감독 Apple Original Film / 파라마운트 (2023)",
        "details": "레오나르도 디카프리오, 로버트 드니로 주연 아카데미 10개 부문 노미네이트"
    },
    {
        "keywords": ["red, white & royal blue", "red white and royal blue"],
        "author": "Casey McQuiston",
        "work": "빨강, 하양, 로열 블루",
        "media_type": "영화",
        "platform": "Amazon Prime Video 오리지널 영화 (2023)",
        "details": "테일러 자카르 페레즈, 니콜라스 골리친 주연 글로벌 1위 로맨스"
    },
    {
        "keywords": ["the idea of you"],
        "author": "Robinne Lee",
        "work": "디 아이디어 오브 유 (The Idea of You)",
        "media_type": "영화",
        "platform": "Amazon Prime Video 오리지널 영화 (2024)",
        "details": "앤 해서웨이, 니콜라스 골리친 주연 인기 로맨틱 코미디"
    },
    {
        "keywords": ["it ends with us"],
        "author": "Colleen Hoover",
        "work": "우리가 끝이야 (It Ends with Us)",
        "media_type": "영화",
        "platform": "소니 픽처스 영화 (2024 글로벌 흥행 3억 달러 돌파)",
        "details": "블레이크 라이블리 주연 로맨스 영화"
    },
    {
        "keywords": ["daisy jones & the six", "daisy jones and the six"],
        "author": "Taylor Jenkins Reid",
        "work": "데이지 존스 앤 더 식스",
        "media_type": "TV 시리즈",
        "platform": "Amazon Prime Video 오리지널 드라마 (2023)",
        "details": "라일리 코프, 샘 클라플린 주연 에미상 수상 록밴드 드라마"
    },
    {
        "keywords": ["the seven husbands of evelyn hugo", "evelyn hugo"],
        "author": "Taylor Jenkins Reid",
        "work": "에블린 휴고의 일곱 남편",
        "media_type": "영화",
        "platform": "Netflix 오리지널 장편 영화 (제작 중)",
        "details": "리즈 차일드레스 각본 넷플릭스 기대작"
    },
    {
        "keywords": ["crazy rich asians"],
        "author": "Kevin Kwan",
        "work": "크레이지 리치 아시안 (Crazy Rich Asians)",
        "media_type": "영화",
        "platform": "워너 브라더스 영화 (2018)",
        "details": "콘스탄스 우, 헨리 골딩, 양자경 주연 글로벌 메가 히트작"
    },
    {
        "keywords": ["maid"],
        "author": "Stephanie Land",
        "work": "조용한 희망 (Maid)",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 미니시리즈 (2021)",
        "details": "마가렛 퀄리 주연 에미상 노미네이트 감동 드라마"
    },
    {
        "keywords": ["queen's gambit", "queens gambit"],
        "author": "Walter Tevis",
        "work": "퀸스 갬빗 (The Queen's Gambit)",
        "media_type": "TV 시리즈",
        "platform": "Netflix 오리지널 미니시리즈 (2020)",
        "details": "안야 테일러조이 주연 넷플릭스 역대 최고 시청 기록 체스 드라마"
    }
]

def scan_all_library_for_adaptations():
    all_books = list(K_ROOT.rglob("*.epub"))
    print(f"==================================================================")
    print(f"🔍 SCANNING ALL {len(all_books):,} BOOKS IN LIBRARY FOR SCREEN ADAPTATIONS")
    print(f"==================================================================")
    
    found_adaptations = []
    
    for epub_p in sorted(all_books, key=lambda x: x.name):
        fname_lower = epub_p.name.lower()
        parent_lower = str(epub_p.parent).lower()
        full_str = f"{parent_lower}/{fname_lower}"
        
        matched_info = None
        for item in SCREEN_ADAPTATION_DB:
            if any(kw in full_str for kw in item["keywords"]):
                matched_info = item
                break
                
        if matched_info:
            found_adaptations.append({
                "filename": epub_p.name,
                "current_location": str(epub_p.parent.relative_to(LIB_ROOT)),
                "work": matched_info["work"],
                "author": matched_info["author"],
                "media_type": matched_info["media_type"],
                "platform": matched_info["platform"],
                "details": matched_info["details"]
            })
            
    print(f"\n🎉 Identified {len(found_adaptations)} Screen Adaptation Novels in Library!\n")
    
    out_file = Path("data/library_screen_adaptations_audit.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(found_adaptations, indent=2, ensure_ascii=False))
    
    return found_adaptations

if __name__ == "__main__":
    scan_all_library_for_adaptations()
