#!/usr/bin/env python3
"""Master Korean Fiction X-Ray Generator & Injector for Entire Library.

Targets Fiction / Novels only across all editions:
- 소설2/[k]/
- 소설2/[k-e]/
- 소설2/[study]/
- 소설2/[e-s]/
- 소설2/[xteink]/[study]/
- 소설2/[xteink]/[e-s]/

Dossier Sections (100% Authentic Korean):
1. 👥 주요 등장인물 소개 (인물명, 역할, 성격, 행동 동기)
2. 🔗 인물 관계도 및 핵심 갈등 구조 (주인공, 적대자, 조력자, 심리적 역학)
3. 🗺️ 주요 무대 및 공간적 배경 (핵심 장소, 공간의 상징성)
4. 🔍 핵심 테마 및 주요 용어 해설 (세계관, 복선, 중심 메시지)

Position:
- Table of Contents top entry (nav.xhtml <ol> top <li>, toc.ncx top <navPoint>).
"""

from __future__ import annotations

import html
import os
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_studio.epub_xray_policy import purge_xray_from_epub

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

# Master database of fiction masterpieces, series, and authors
FICTION_DOSSIERS = {
    "housemaid": {
        "title": "하우스메이드 (The Housemaid)",
        "characters": [
            ("밀리 캘러웨이 (Millie Calloway)", "주인공 / 입주 가정부", "가석방 상태에서 윈체스터 가문의 가정부로 취업한 20대 여성. 어두운 과거를 숨기고 평범한 삶을 꿈꾸지만, 저택에 도사린 기괴한 비밀과 통제에 맞서 생존의 사투를 벌인다."),
            ("니나 윈체스터 (Nina Winchester)", "여주인 / 안주인", "완벽하고 우아해 보이지만 극심한 감정 기복과 거짓말로 밀리를 심리적으로 코너에 몰아넣는 여주인. 딸 세실리아와 남편 앤드루를 향해 이해할 수 없는 집착과 불안을 보인다."),
            ("앤드루 윈체스터 (Andrew Winchester)", "남주인 / 니나의 남편", "부유하고 매력적이며 누구에게나 다정한 완벽한 이상형. 아내 니나의 변덕과 학대로 고통받는 것처럼 보이며 밀리에게 깊은 연민과 호감을 표시한다."),
            ("세실리아 윈체스터 (Cecelia)", "윈체스터 부부의 딸", "부모의 왜곡된 관계 속에서 자라 공격적이고 변덕스러운 성격을 보이지만, 저택의 공포스러운 진실을 은연중에 암시하는 인물."),
            ("엔조 (Enzo)", "이탈리아인 정원사", "저택의 비밀을 오랜 시간 지켜본 과묵한 정원사. 밀리에게 위험을 직감하고 끊임없이 경고를 던지는 미스터리한 조력자.")
        ],
        "relationships": [
            "• 밀리 ↔ 앤드루: 연민과 호감으로 시작되지만, 숨겨진 진실이 밝혀지며 경악스러운 반전을 맞이하는 관계",
            "• 밀리 ↔ 니나: 고용주와 피고용인의 숨 막히는 심리적 갑을 관계이자 가해자와 피해자의 경계가 뒤바뀌는 대립",
            "• 니나 ↔ 앤드루: 겉으로는 상류층 잉꼬부부이지만, 이면에 치명적인 통제와 복수가 도사린 파괴적 관계",
            "• 엔조 → 밀리: 저택의 끔찍한 과거를 알고 있는 자의 침묵과 결정적인 탈출 경고"
        ],
        "locations": [
            ("윈체스터 저택 3층 다락방 침실", "밀리가 머무는 좁은 방. 밖에서만 잠글 수 있는 자물쇠와 문고리가 달린 폐쇄된 공포의 공간."),
            ("롱아일랜드 호화 저택", "외관은 우아하고 평화롭지만, 도망칠 수 없는 완벽한 심리적 감옥 역할을 하는 주 무대.")
        ],
        "themes": [
            ("가스라이팅과 완벽한 심리 조작", "누가 피해자이고 누가 가해자인지 끊임없이 의심하게 만드는 정교한 서스펜스."),
            ("사회적 약자의 생존과 복수", "취약한 처지의 여성이 권력과 부를 쥔 자들의 잔혹한 게임을 뒤엎는 통쾌한 반전.")
        ]
    },
    "dark notes": {
        "title": "다크 노츠 (Dark Notes)",
        "characters": [
            ("에머리 샌더스 (Emery Saunders)", "주인공 / 고등학생 피아니스트", "가난과 가정 폭력 속에서도 음악적 천재성을 잃지 않는 18세 졸업반 학생. 생존을 위해 클럽에서 일하며 명문 르모인 아카데미 졸업을 향해 분투한다."),
            ("캠든 맥클랜드 (Camden MacFarland)", "피아노 거장 / 르모인 음악 교사", "전설적인 천재 피아니스트였으나 뼈아픈 과거로 인해 은둔하고 있는 엄격하고 냉혹한 스승. 에머리의 재능을 발견하고 집착과 열정에 휩싸인다."),
            ("제이슨 (Jason)", "에머리의 삼촌 / 법적 보호자", "도박 빚과 알코올 중독으로 에머리를 착취하고 위험에 빠뜨리는 파괴적인 인물.")
        ],
        "relationships": [
            "• 에머리 ↔ 캠든: 금지된 사제 관계이자 예술적 영혼의 교감, 어둠과 구원이 공존하는 강렬한 열정",
            "• 에머리 ↔ 제이슨: 생존을 위협하는 가정 내 착취와 학대, 탈출해야만 하는 족쇄",
            "• 캠든 ↔ 과거의 트라우마: 음악을 버리게 만든 죄책감과 에머리를 통해 마주하는 속죄"
        ],
        "locations": [
            ("르모인 아카데미 (Le Moyne Academy)", "뉴올리언스의 명문 예술 학교. 상류층의 위선과 에머리의 순수한 음악적 재능이 충돌하는 공간."),
            ("캠든의 저택 피아노실", "세상과 단절된 채 두 주인공이 음악과 본능으로 부딪히는 은밀한 성역.")
        ],
        "themes": [
            ("음악을 통한 영혼의 구원", "클래식 음악의 격정적인 선율 속에 녹아든 상처의 치유와 예술적 승화."),
            ("금기와 속박의 극복", "사회적 금기와 나이, 신분의 한계를 뛰어넘는 처절하고 매혹적인 다크 로맨스.")
        ]
    },
    "silent patient": {
        "title": "사일런트 페이션트 (The Silent Patient)",
        "characters": [
            ("앨리샤 베렌슨 (Alicia Berenson)", "주인공 / 유명 화가", "남편을 총으로 살해한 뒤 단 한 마디의 말도 하지 않고 침묵을 지키는 비운의 천재 화가."),
            ("테오 파버 (Theo Faber)", "범죄 심리치료사", "앨리샤의 침묵 뒤에 숨겨진 진실을 밝혀내기 위해 그로브 정신병원에 자원한 야심 찬 심리치료사."),
            ("가브리엘 베렌슨 (Gabriel Berenson)", "앨리샤의 남편 / 패션 사진작가", "완벽해 보였으나 자택에서 앨리샤의 총에 맞아 살해당한 인물.")
        ],
        "relationships": [
            "• 테오 ↔ 앨리샤: 침묵하는 환자와 집착하는 치료사의 위험하고 치밀한 심리적 탐색전",
            "• 앨리샤 ↔ 가브리엘: 겉으로는 완벽했던 부부 이면에 숨겨진 배신과 비극",
            "• 테오 ↔ 아내 캐시: 테오의 내면을 갉아먹는 불륜의 의혹과 고통"
        ],
        "locations": [
            ("더 그로브 (The Grove)", "런던의 보안 정신병원. 앨리샤가 수감되어 침묵을 지키는 폐쇄된 공간."),
            ("알케스티스 자화상 앞", "그리스 비극 알케스티스를 모티프로 앨리샤가 남긴 유일한 단서인 그림.")
        ],
        "themes": [
            ("침묵 뒤에 감춰진 트라우마", "언어로 표현할 수 없는 극도의 상처와 배신이 낳은 침묵의 무게."),
            ("신뢰할 수 없는 화자와 반전", "치료사의 시선과 화가의 일기가 교차하며 완성되는 충격적인 서스펜스.")
        ]
    }
}

def is_fiction_book(p: Path) -> bool:
    p_str = str(p).lower()
    non_fiction_keywords = [
        "nonfiction", "business", "biography", "memoir", "economics", "history_politics",
        "walter isaacson", "carl sagan", "richard dawkins", "malcolm gladwell", "susan cain",
        "angela duckworth", "steve jobs", "matthew mcconaughey", "jennette mccurdy",
        "jeannette walls", "tara westover", "paul kalanithi", "viktor frankl", "eric schmidt",
        "steven johnson", "sandel", "kahneman", "yuval noah harari"
    ]
    if any(k in p_str for k in non_fiction_keywords):
        return False
    return True

def extract_fiction_dossier(epub_path: Path, title: str, author: str) -> dict:
    clean_t = re.sub(r"^\[(study|e-s|ks|kindle|k|k-e|xteink)\]\s*", "", title)
    clean_t_lower = clean_t.lower()

    # Check masterpiece dossiers
    for k, v in FICTION_DOSSIERS.items():
        if k in clean_t_lower:
            return v

    # Dynamic NLP extraction from fiction chapters
    names = []
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            ch_names = [n for n in z.namelist() if n.endswith((".xhtml", ".html")) and ("ch" in n.lower() or "00" in n or "part" in n.lower())]
            sample_text = ""
            for ch in ch_names[:6]:
                sample_text += z.read(ch).decode("utf-8", errors="replace") + " "
                if len(sample_text) > 60000:
                    break
            # Recurring character names
            found = re.findall(r"\b([A-Z][a-z]{2,15}(?:\s+[A-Z][a-z]{2,15})?)\b", sample_text)
            counts = {}
            ignore = {"The", "This", "That", "When", "There", "What", "Then", "Chapter", "With", "From", "Into", "About", "After", "Before", "Could", "Would", "Should", "They", "Their", "Where", "While", "Suddenly"}
            for n in found:
                if n not in ignore and len(n) > 2 and not n.isdigit():
                    counts[n] = counts.get(n, 0) + 1
            sorted_n = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            names = [n for n, c in sorted_n[:6] if c >= 3]
    except Exception:
        pass

    p1 = names[0] if len(names) > 0 else "주인공 (Protagonist)"
    p2 = names[1] if len(names) > 1 else "핵심 상대역 (Key Character)"
    p3 = names[2] if len(names) > 2 else "주요 조력자 (Supporting Lead)"
    p4 = names[3] if len(names) > 3 else "주변 인물군 (Supporting Cast)"

    return {
        "title": clean_t,
        "characters": [
            (f"{p1}", "주인공 / 서사의 중심", "작품의 사건과 갈등을 이끌어가는 핵심 주역. 내면의 결핍과 목표를 향해 나아가며 극적인 선택의 기로에 선다."),
            (f"{p2}", "핵심 상대역 / 대립·조력자", "주인공과 가장 긴밀하게 얽히며 서사의 긴장감과 반전을 촉발하는 핵심 인물."),
            (f"{p3}", "주요 조력자 / 관찰자", "주인공의 결정을 지지하거나 사건의 결정적 단서를 제공하는 주요 인물."),
            (f"{p4}", "주변 인물군", "작품의 배경과 긴장감을 풍성하게 구성하는 조연 인물진.")
        ],
        "relationships": [
            f"• {p1} ↔ {p2}: 서로의 운명을 뒤바꾸는 치밀한 심리적 상호작용 및 갈등 구조",
            f"• {p1} ↔ {p3}: 위기의 순간 조력과 신뢰를 형성하는 핵심 파트너십",
            "• 서사적 긴장감: 숨겨진 비밀과 복선이 풀려나며 변화하는 인물 간 역학 관계"
        ],
        "locations": [
            ("주요 공간적 배경", "인물들의 감정과 갈등이 극대화되는 핵심 무대이자 사건의 중심지."),
            ("은밀한 대립의 공간", "진실이 밝혀지고 결정적인 선택이 이루어지는 상징적 장소.")
        ],
        "themes": [
            ("인간 본성과 심리적 갈등", "극한의 상황에서 드러나는 인물들의 심리와 생존 본능."),
            ("운명의 극복과 선택", "스스로의 한계를 깨뜨리고 진실을 향해 나아가는 주제 의식.")
        ]
    }

def generate_full_korean_xray_xhtml(title: str, author: str, dossier: dict) -> str:
    clean_t = re.sub(r"^\[(study|e-s|ks|kindle|k|k-e|xteink)\]\s*", "", title)
    clean_t = re.sub(r"\s*\([^)]*\)$", "", clean_t).strip()

    char_cards_html = ""
    for name, role, desc in dossier["characters"]:
        char_cards_html += f'''  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{html.escape(name)}</span> <span class="xray-entity-role">{html.escape(role)}</span></div>
    <div class="xray-entity-desc">{html.escape(desc)}</div>
  </div>\n'''

    rel_items_html = ""
    for rel in dossier["relationships"]:
        rel_items_html += f'    <li style="margin-bottom: 0.5em; line-height: 1.6;">{html.escape(rel)}</li>\n'

    loc_cards_html = ""
    for loc_name, loc_desc in dossier["locations"]:
        loc_cards_html += f'''  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{html.escape(loc_name)}</span> <span class="xray-entity-role">주요 무대</span></div>
    <div class="xray-entity-desc">{html.escape(loc_desc)}</div>
  </div>\n'''

    theme_cards_html = ""
    for th_name, th_desc in dossier["themes"]:
        theme_cards_html += f'''  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{html.escape(th_name)}</span> <span class="xray-entity-role">핵심 테마</span></div>
    <div class="xray-entity-desc">{html.escape(th_desc)}</div>
  </div>\n'''

    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>⚡ X-Ray: {html.escape(clean_t)}</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
  <style type="text/css">
    .xray-section {{ margin: 0 4%; padding-bottom: 3em; font-family: "Bookerly_KR", "Amazon Ember", sans-serif; }}
    .xray-header {{ text-align: center; margin: 1.5em 0 2em; border-bottom: 2px solid #0284c7; padding-bottom: 1em; }}
    .xray-header h1 {{ font-size: 1.55em; color: #0f172a; margin: 0 0 0.4em; }}
    .xray-header p {{ font-size: 0.9em; color: #64748b; margin: 0; }}
    .xray-box {{ background: rgba(2, 132, 199, 0.04); border: 1px solid rgba(2, 132, 199, 0.2); border-radius: 8px; padding: 1.2em; margin-bottom: 1.8em; }}
    .xray-box-title {{ font-size: 1.15em; font-weight: bold; color: #0284c7; margin-bottom: 0.8em; display: flex; align-items: center; }}
    .xray-entity-card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0.9em 1em; margin-bottom: 0.8em; box-shadow: 0 1px 3px rgba(0,0,0,0.03); }}
    .xray-entity-name {{ font-size: 1.05em; font-weight: bold; color: #1e293b; }}
    .xray-entity-role {{ font-size: 0.78em; color: #0284c7; background: #e0f2fe; padding: 2px 7px; border-radius: 12px; margin-left: 6px; font-weight: 600; }}
    .xray-entity-desc {{ font-size: 0.92em; color: #475569; margin-top: 0.4em; line-height: 1.6; word-break: keep-all; }}
  </style>
</head>
<body>
<section class="xray-section">
  <div class="xray-header">
    <h1>⚡ X-Ray: 등장인물 및 용어 도감</h1>
    <p><strong>{html.escape(clean_t)}</strong> by <em>{html.escape(author)}</em></p>
  </div>

  <div class="xray-box">
    <div class="xray-box-title">👥 주요 등장인물 소개 (Major Characters)</div>
{char_cards_html}  </div>

  <div class="xray-box">
    <div class="xray-box-title">🔗 인물 관계도 및 핵심 갈등 (Relationships &amp; Dynamics)</div>
    <ul style="padding-left: 1.2em; margin: 0; color: #334155; font-size: 0.92em;">
{rel_items_html}    </ul>
  </div>

  <div class="xray-box">
    <div class="xray-box-title">🗺️ 주요 무대 및 공간적 배경 (Key Locations)</div>
{loc_cards_html}  </div>

  <div class="xray-box">
    <div class="xray-box-title">🔍 핵심 테마 및 세계관 해설 (Themes &amp; Terminology)</div>
{theme_cards_html}  </div>
</section>
</body>
</html>
'''

def inject_xray_to_single_epub(epub_path: Path) -> bool:
    # Historical entry point retained for compatibility. The library no longer
    # permits any X-Ray dossier, so callers now get deterministic cleanup rather
    # than a new injection.
    return purge_xray_from_epub(epub_path)
    # Legacy dossier-generation code below is intentionally unreachable.
    author = epub_path.parent.name.lstrip("#")
    book_title = epub_path.stem
    dossier = extract_fiction_dossier(epub_path, book_title, author)
    xray_xhtml = generate_full_korean_xray_xhtml(book_title, author, dossier)

    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
            fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=epub_path.parent)
            os.close(fd)
            tmp_file = Path(tmp_path_str)

            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment

                # Write mimetype
                if "mimetype" in in_names:
                    zout.writestr(zipfile.ZipInfo("mimetype"), zin.read("mimetype"), compress_type=zipfile.ZIP_STORED)

                xray_path = "OEBPS/000-xray-dramatis-personae.xhtml" if any(n.startswith("OEBPS/") for n in in_names) else "000-xray-dramatis-personae.xhtml"
                zout.writestr(xray_path, xray_xhtml.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)

                for name in in_names:
                    if name == "mimetype" or name == xray_path:
                        continue
                    data = zin.read(name)

                    # Update nav.xhtml
                    if name.endswith("nav.xhtml"):
                        nav_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in nav_str:
                            xray_li = '<li><a href="000-xray-dramatis-personae.xhtml">⚡ X-Ray: 등장인물 및 용어 도감</a></li>\n      '
                            nav_str = re.sub(r"(<ol[^>]*>)", rf"\1\n      {xray_li}", nav_str, count=1)
                        data = nav_str.encode("utf-8")

                    # Update toc.ncx
                    elif name.endswith("toc.ncx"):
                        ncx_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in ncx_str:
                            xray_navpoint = '<navPoint id="navpoint-xray" playOrder="1">\n    <navLabel><text>⚡ X-Ray: 등장인물 및 용어 도감</text></navLabel>\n    <content src="000-xray-dramatis-personae.xhtml"/>\n  </navPoint>\n  '
                            ncx_str = re.sub(r"(<navMap[^>]*>)", rf"\1\n  {xray_navpoint}", ncx_str, count=1)
                        data = ncx_str.encode("utf-8")

                    # Update .opf
                    elif name.endswith(".opf"):
                        opf_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in opf_str:
                            item_tag = '<item id="xray-dir" href="000-xray-dramatis-personae.xhtml" media-type="application/xhtml+xml"/>\n'
                            itemref_tag = '<itemref idref="xray-dir"/>\n'
                            opf_str = re.sub(r"(<manifest[^>]*>)", rf"\1\n    {item_tag}", opf_str, count=1)
                            opf_str = re.sub(r"(<spine[^>]*>)", rf"\1\n    {itemref_tag}", opf_str, count=1)
                        data = opf_str.encode("utf-8")

                    zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

        tmp_file.replace(epub_path)
        return True
    except Exception:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return False

def inject_all_fiction_library():
    t0 = time.time()
    print("==================================================================")
    print("🌟 INJECTING KOREAN X-RAY DOSSIERS TO ALL FICTION NOVELS")
    print("==================================================================")

    target_dirs = [
        LIB_ROOT / "[k]",
        LIB_ROOT / "[k-e]",
        LIB_ROOT / "[study]",
        LIB_ROOT / "[e-s]",
        LIB_ROOT / "[xteink]" / "[study]",
        LIB_ROOT / "[xteink]" / "[e-s]",
    ]

    all_fiction_epubs = []
    for d in target_dirs:
        if d.exists():
            files = [p for p in d.rglob("*.epub") if is_fiction_book(p)]
            print(f"📁 {d.name} ({len(files):,} fiction novels)")
            all_fiction_epubs.extend(files)

    print(f"\n📚 Total Fiction Novels to Process: {len(all_fiction_epubs):,} across all editions\n")

    success_count = 0
    for idx, epub_p in enumerate(all_fiction_epubs, 1):
        if inject_xray_to_single_epub(epub_p):
            success_count += 1
        if idx % 200 == 0 or idx == len(all_fiction_epubs):
            print(f"   -> Progress: {idx:,} / {len(all_fiction_epubs):,} ({success_count:,} dossiers injected)")

    elapsed = time.time() - t0
    print("\n==================================================================")
    print(f"🎉 COMPLETED in {elapsed:.1f}s! Successfully injected Korean X-Ray into {success_count:,} Fiction Novels!")
    print("==================================================================")

if __name__ == "__main__":
    inject_all_fiction_library()
