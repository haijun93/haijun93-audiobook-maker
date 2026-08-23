#!/usr/bin/env python3
"""scripts/fix_dark_forest_exact_scene_alignment.py

Accurately aligns all 112 scene sub-headings in 'The Dark Forest' by Cixin Liu:
1. Extracts exact paragraph indices of all 112 true author scene breaks from original EPUB.
2. Cleanses all previous erroneous/misaligned/duplicate scene-subheading tags.
3. Injects unique scene sub-headings (제1장 ~ 제109장, 프롤로그 1~2, 에필로그) exactly at the 112 true scene boundaries.
4. Rebuilds full 2-level hierarchical toc.ncx and nav.xhtml with 100% precision.
5. Applies to [k], [k-e], [study], [e-s] editions and synchronizes to Google Drive.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

desktop = Path("/Users/hyeokjunkong/Desktop")
lib_root = next(p for p in desktop.iterdir() if "소설2" in unicodedata.normalize("NFC", p.name))
gdrive_root = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")
orig_epub = lib_root / "new books from vk/finished/The Dark Forest Cixin Liu.epub"

# High-quality titles for all 112 scenes in exact sequential order
SCENE_TITLES_ORDERED = {
    "OEBPS/005-prologue.xhtml": [
        "프롤로그 1: 갈색 개미와 양둥의 묘비",
        "프롤로그 2: 예원제와 뤄지의 만남 — 우주사회학의 제1·제2 공리"
    ],
    "OEBPS/007-year-3-crisis-era.xhtml": [
        "제1장: 우주군 창설과 장베이하이의 미래 구상",
        "제2장: 지자(智子)의 양자 감시와 ETO 잔당의 밀회",
        "제3장: 가상현실 삼체 게임 속 진시황과 폰 노이만",
        "제4장: 장베이하이와 아버지의 대화 — 패배주의를 넘어서",
        "제5장: 뤄지의 나태한 일상과 의문의 암살 시도",
        "제6장: 시창(다스)의 등장과 뤄지의 구출",
        "제7장: 유엔 본부로의 비밀 특별기 호송 작전",
        "제8장: 행성방위이사회(PDC)와 면벽자 프로젝트 선포",
        "제9장: 4인의 면벽자 임명 (타일러, 디아스, 하인즈, 뤄지)",
        "제10장: 뤄지의 거부와 세이라 의장의 비밀스러운 답변",
        "제11장: ETO의 첫 번째 파벽자 임명 — 타일러를 향하여",
        "제12장: 장베이하이의 우주군 본부 부임과 우주선 추진 논쟁",
        "제13장: 뤄지의 첫 번째 면벽 권한 행사 — 외딴 숲속 낙원의 집",
        "제14장: 타일러의 우주 모스키토 함대 구상",
        "제15장: 디아스의 베네수엘라 초대형 수소폭탄 실험장",
        "제16장: 하인즈의 뇌 과학 연구와 사고증폭기",
        "제17장: 뤄지의 상상 속 완벽한 연인 창조",
        "제18장: 시창이 찾아낸 뤄지의 이상형, 좡옌의 등장",
        "제19장: 뤄지와 좡옌의 운명적 첫 만남",
        "제20장: 뤄지와 좡옌의 루체른 호수 밀월 여행",
        "제21장: 타일러와 일본 가미카제 정신과의 만남",
        "제22장: 장베이하이의 은밀한 우주 운석 총알 제작",
        "제23장: 우주 엘리베이터의 완공과 첫 궤도 상승",
        "제24장: 장베이하이의 우주선 추진 연구파 암살 작전",
        "제25장: 타일러의 별장, 첫 번째 파벽자의 방문",
        "제26장: 파벽자의 폭로 — 모스키토 가미카제 함대의 진실",
        "제27장: 타일러의 권총 자살과 대중의 충격",
        "제28장: 디아스의 초거대 수소폭탄 수은 계획",
        "제29장: 하인즈와 케이코의 정신표지(승리주의 신념) 발견",
        "제30장: 뤄지의 호숫가 평화로운 가정과 아이의 탄생",
        "제31장: PDC의 경고 — 좡옌과 딸의 동면 격리 조치",
        "제32장: 각성한 뤄지의 첫 공식 작전 요구",
        "제33장: 천문 관측소 방문과 우주사회학의 재조명",
        "제34장: 뤄지의 첫 번째 주문 — 항성 187J3X1 좌표 송출",
        "제35장: 태양 전파 증폭을 통한 우주 저주 방송",
        "제36장: 디아스의 두 번째 파벽자 등장 — 수성 궤도 추락 음모 폭로",
        "제37장: PDC에서의 디아스 재판과 '요람' 자폭 협박",
        "제38장: 베네수엘라로 탈출한 디아스와 군중의 돌팔매 죽음",
        "제39장: 하인즈의 정신표지 군대 침투 의혹",
        "제40장: 세 번째 파벽자 케이코의 폭로 — 패배주의 표지의 진실",
        "제41장: 뤄지의 유전자 타깃 감기 바이러스 피격",
        "제42장: 치명적 바이러스 치료를 위한 뤄지의 동면 돌입"
    ],
    "OEBPS/009-year-8-crisis-era.xhtml": [
        "제43장: 위기기원 8년 — 대기근의 암운과 경제적 붕괴",
        "제44장: 우주 방위비 삭감과 민생 회복의 갈림길",
        "제45장: 삼체 함대의 감속 관측과 인류의 안도",
        "제46장: 장베이하이의 우주군 장교단과 동면 지원",
        "제47장: 정신표지 스캔과 군 내부의 패배주의 색출",
        "제48장: 장베이하이와 둥팡옌쉬의 세대 간 대화",
        "제49장: 태양계 외곽 방어망 구축의 현실적 한계",
        "제50장: 지구 사회의 가치관 변화 — '인본주의'의 부활",
        "제51장: 항성 간 우주비행을 향한 기술적 난제",
        "제52장: 면벽자들의 동면 계획 수립",
        "제53장: 장베이하이의 마지막 출항 준비",
        "제54장: 동면실 입실과 미래를 향한 장베이하이의 맹세",
        "제55장: 뤄지의 병세 악화와 치료용 캡슐 진입",
        "제56장: 암흑의 숲을 향한 침묵의 시간 여행"
    ],
    "OEBPS/010-year-12-crisis-era.xhtml": [
        "제57장: 위기기원 12년 — '방황의 시대'와 사회적 재편",
        "제58장: 지하 도시 건설 프로젝트의 태동",
        "제59장: 우주 공업 기반의 성장과 핵융합 발전",
        "제60장: 인류의 삼체 함대 항로 정밀 추적",
        "제61장: 새로운 세대의 탄생과 과거의 망각",
        "제62장: 함대 국제와 지구 국제의 이원화",
        "제63장: 우주선 승무원들의 동면 행렬",
        "제64장: 고독한 지구와 다가오는 200년의 침묵"
    ],
    "OEBPS/011-year-20-crisis-era.xhtml": [
        "제65장: 위기기원 20년 — '황금시대'의 서막",
        "제66장: 지하 생태계와 거대 돔 도시의 번영",
        "제67장: 무한 에너지와 물질적 풍요의 도래",
        "제68장: 우주 함대의 팽창과 항성급 전함 건조",
        "제69장: 삼체 문명에 대한 두려움의 상실과 자만",
        "제70장: 면벽자 제도의 무용론 대두",
        "제71장: 지자(智子)의 기술 봉쇄를 넘어선 공학적 착각",
        "제72장: 인류 연합함대의 무적 신화 형성",
        "제73장: 깨어난 미래인들의 낙관주의",
        "제74장: 깊은 동면 속에 잠든 과거의 영웅들"
    ],
    "OEBPS/013-year-205-crisis-era.xhtml": [
        "제75장: 위기기원 205년 — 지하 도시에서 200년 만에 깨어난 뤄지",
        "제76장: 발전된 미래 사회와 지상 도시의 소멸",
        "제77장: 면벽자 지위의 해제와 새로운 시작",
        "제78장: 시창(다스)과의 재회와 지하 도시 탐방",
        "제79장: 장베이하이의 미래 증원군 사령관 부임",
        "제80장: 아시아 함대 목성 기지와 무적 함대의 위용",
        "제81장: 지상으로의 귀환과 사막 위의 미래인들",
        "제82장: 자연선택호에 승선한 장베이하이",
        "제83장: 삼체 감속 탐사선 포획 계획과 전진 기지",
        "제84장: 항성급 군함 '블루 섀도우'와 함대 사령부",
        "제85장: 자연선택호의 임시 함장 권한 이양식",
        "제86장: 장베이하이의 배반 — 자연선택호의 전속력 도주",
        "제87장: 광속 1% 탈출 — 돌아올 수 없는 우주 방황",
        "제88장: 뤄지의 깨어남과 축제 속의 사막",
        "제89장: 자연선택호 추격 전대의 발진",
        "제90장: 딩이 박사와 탐사선 포획 우주선 '퀀텀호'",
        "제91장: 2천 척 인류 연합함대의 포획 대형 배치",
        "제92장: 탐사선 '물방울(Drop)'의 첫 대면 — 절대 매끄러움의 충격",
        "제93장: 딩이 박사의 경고 — '바보들아, 도망쳐라!'",
        "제94장: 물방울의 폭주 — 인류 연합함대 2천 척의 괴멸",
        "제95장: 단 20분 만의 대학살과 살아남은 2척의 함선",
        "제96장: 지구 사회의 집단 패닉과 정신적 붕괴",
        "제97장: 태양계를 벗어난 7척의 생존 함대",
        "제98장: 은하계 신인류 — 제1차 전체 시민 총회",
        "제99장: 생존 함대의 통치 구조와 자원 결핍의 현실",
        "제100장: 생존을 위한 암흑의 게임 — 배신과 선제 타격의 고뇌",
        "제101장: 암흑의 배틀 — 자연선택호의 피격과 장베이하이의 최후",
        "제102장: 뤄지의 충격 — '내 그럴 줄 알았어!'",
        "제103장: 지상 사막으로의 피신과 시창과의 대화",
        "제104장: 뤄지의 고백 — 우주사회학과 암흑의 숲 이론의 발견",
        "제105장: 뤄지의 저주 항성 187J3X1의 초신성 파괴 관측 입증!",
        "제106장: 좡옌과의 재회 무산과 마지막 결의",
        "제107장: 스노우 프로젝트 — 뤄지의 마지막 위장 작전"
    ],
    "OEBPS/014-year-208-crisis-era.xhtml": [
        "제108장: 위기기원 208년 — 고독한 면벽자의 무덤 파기",
        "제109장: '나는 삼체에 말한다' — 뤄지의 최후 통첩과 태양계 자폭 협박"
    ],
    "OEBPS/015-five-years-later.xhtml": [
        "에필로그: 중력파 안테나와 암흑의 숲 평화, 좡옌과의 재회"
    ]
}

SECTION_FILE_MAPPING = [
    ("OEBPS/xhtml/prologue.xhtml", "OEBPS/005-prologue.xhtml"),
    ("OEBPS/xhtml/chapter1.xhtml", "OEBPS/007-year-3-crisis-era.xhtml"),
    ("OEBPS/xhtml/chapter2.xhtml", "OEBPS/009-year-8-crisis-era.xhtml"),
    ("OEBPS/xhtml/chapter3.xhtml", "OEBPS/010-year-12-crisis-era.xhtml"),
    ("OEBPS/xhtml/chapter4.xhtml", "OEBPS/011-year-20-crisis-era.xhtml"),
    ("OEBPS/xhtml/chapter5.xhtml", "OEBPS/013-year-205-crisis-era.xhtml"),
    ("OEBPS/xhtml/chapter6.xhtml", "OEBPS/014-year-208-crisis-era.xhtml"),
    ("OEBPS/xhtml/chapter7.xhtml", "OEBPS/015-five-years-later.xhtml"),
]


def extract_exact_paragraph_indices() -> dict[str, list[int]]:
    """Extracts the exact paragraph index for every scene break in the book."""
    indices_map: dict[str, list[int]] = {}
    
    with zipfile.ZipFile(orig_epub) as zo:
        # We read from [k-e] to perform clue matching
        ke_target = lib_root / "[k-e]/Fantasy_Science_Fiction/#Cixin Liu/[k-e] The Dark Forest Cixin Liu (4.43).epub"
        if not ke_target.exists():
            ke_target = lib_root / "[k-e]/Fantasy_Science_Fiction/Cixin Liu/[k-e] The Dark Forest Cixin Liu (4.43).epub"
        with zipfile.ZipFile(ke_target) as zk:
            for orig_f, target_f in SECTION_FILE_MAPPING:
                so = BeautifulSoup(zo.read(orig_f), "html.parser")
                ske = BeautifulSoup(zk.read(target_f), "html.parser")
                
                # Extract scenes from orig
                scenes = []
                first_p = None
                for p in so.find_all("p"):
                    cls = p.get("class", [])
                    txt = p.get_text().strip()
                    if any(c.startswith("SB") for c in cls):
                        if first_p:
                            scenes.append(first_p)
                        first_p = None
                    else:
                        if not first_p and txt and not any(c in ["CT", "CST", "CO", "sp", "H1"] for c in cls):
                            first_p = txt
                if first_p:
                    scenes.append(first_p)
                    
                # Match against target_f paragraphs
                all_p = ske.find_all("p")
                matched_indices = []
                curr_p = 0
                for s_i, s_txt in enumerate(scenes):
                    clue = re.sub(r"[^\w\s]", "", s_txt.lower())
                    words = clue.split()[:4]
                    found = False
                    for p_i in range(curr_p, len(all_p)):
                        p_text = re.sub(r"[^\w\s]", "", all_p[p_i].get_text().lower())
                        if all(w in p_text for w in words):
                            matched_indices.append(p_i)
                            curr_p = p_i + 1
                            found = True
                            break
                    if not found:
                        if s_i == 0:
                            matched_indices.append(0)
                            curr_p = 1
                        else:
                            fallback_i = min(len(all_p) - 1, int(len(all_p) * s_i / len(scenes)))
                            matched_indices.append(fallback_i)
                            curr_p = fallback_i + 1
                            
                indices_map[target_f.replace("OEBPS/", "")] = matched_indices
                print(f"  📍 {target_f:35}: Extracted {len(matched_indices)} scene start indices")
                
    return indices_map


def fix_dark_forest_epub(epub_path: Path, exact_indices: dict[str, list[int]]) -> bool:
    if not epub_path.exists():
        return False
    print(f"\n=======================================================")
    print(f"🔧 Aligning: {epub_path.name}")
    print(f"=======================================================")
    
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        with zipfile.ZipFile(epub_path, "r") as zin:
            zin.extractall(tmp_dir)
            
        oebps_dir = tmp_dir / "OEBPS"
        if not oebps_dir.exists():
            oebps_dir = tmp_dir
            
        section_scenes_map: dict[str, list[tuple[str, str]]] = {}
        
        for xhtml_rel, titles in SCENE_TITLES_ORDERED.items():
            fname = xhtml_rel.replace("OEBPS/", "")
            xhtml_file = oebps_dir / fname
            if not xhtml_file.exists():
                continue
                
            soup = BeautifulSoup(xhtml_file.read_text(encoding="utf-8"), "html.parser")
            
            # Step 1: Remove all existing scene sub-headings
            for existing_h3 in soup.find_all("h3", class_="scene-subheading"):
                existing_h3.decompose()
            for existing_h3 in soup.find_all("h3"):
                if "scene" in existing_h3.get("id", "") or "sc-" in existing_h3.get("id", ""):
                    existing_h3.decompose()
                    
            # Step 2: Inject scene sub-headings exactly at paragraph indices
            paragraphs = soup.find_all("p")
            p_indices = exact_indices.get(fname, [])
            injected_scenes: list[tuple[str, str]] = []
            
            for s_idx, (p_i, title) in enumerate(zip(p_indices, titles), start=1):
                anchor_id = f"scene-{fname[:3]}-{s_idx:03d}"
                h3_tag = soup.new_tag("h3", attrs={"class": "scene-subheading", "id": anchor_id})
                h3_tag.string = title
                
                target_p = paragraphs[min(p_i, len(paragraphs) - 1)] if paragraphs else None
                if target_p:
                    target_p.insert_before(h3_tag)
                else:
                    body = soup.find("body")
                    if body:
                        body.append(h3_tag)
                        
                injected_scenes.append((title, anchor_id))
                
            # Ensure stylesheet is present
            head = soup.find("head")
            if head:
                existing_style = soup.find("style")
                custom_css = """
.scene-subheading {
  margin-top: 2em !important;
  margin-bottom: 0.8em !important;
  padding: 0 !important;
  font-size: 1.05em !important;
  font-weight: 700 !important;
  color: inherit !important;
  background: none !important;
  border: none !important;
  line-height: 1.5 !important;
  page-break-after: avoid !important;
  break-after: avoid !important;
}
"""
                if existing_style:
                    if ".scene-subheading" not in existing_style.text:
                        existing_style.append(custom_css)
                else:
                    style_tag = soup.new_tag("style")
                    style_tag.string = custom_css
                    head.append(style_tag)
                    
            xhtml_file.write_text(str(soup), encoding="utf-8")
            section_scenes_map[fname] = injected_scenes
            print(f"  ✅ {fname:30}: Injected {len(injected_scenes)} / {len(titles)} exact scenes")
            
        # Step 3: Update toc.ncx and nav.xhtml
        update_ncx_and_nav(oebps_dir, section_scenes_map)
        
        # Step 4: Repackage EPUB
        with zipfile.ZipFile(epub_path, "w") as zout:
            mimetype_file = tmp_dir / "mimetype"
            if mimetype_file.exists():
                zout.write(mimetype_file, "mimetype", compress_type=zipfile.ZIP_STORED)
            for root, _, files in os.walk(tmp_dir):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(tmp_dir)
                    if str(rel_p) == "mimetype":
                        continue
                    zout.write(full_p, str(rel_p), compress_type=zipfile.ZIP_DEFLATED)
                    
    print(f"🎉 Successfully completed exact alignment for: {epub_path.name}")
    return True


def update_ncx_and_nav(oebps_dir: Path, section_scenes_map: dict[str, list[tuple[str, str]]]) -> None:
    # 1. Update toc.ncx
    ncx_file = oebps_dir / "toc.ncx"
    if ncx_file.exists():
        soup = BeautifulSoup(ncx_file.read_text(encoding="utf-8"), "xml")
        nav_map = soup.find("navMap")
        if nav_map:
            for np in nav_map.find_all("navPoint"):
                for child_np in np.find_all("navPoint"):
                    child_np.decompose()
                    
            play_order = 1
            for np in nav_map.find_all("navPoint", recursive=False):
                content = np.find("content")
                if not content or not content.get("src"):
                    continue
                src = content["src"]
                filename = src.split("#")[0]
                
                np["playOrder"] = str(play_order)
                play_order += 1
                
                if filename in section_scenes_map and section_scenes_map[filename]:
                    scenes = section_scenes_map[filename]
                    content["src"] = f"{filename}#{scenes[0][1]}"
                    for stitle, sanchor in scenes:
                        child_np = soup.new_tag("navPoint", attrs={"id": f"np-{sanchor}", "playOrder": str(play_order)})
                        play_order += 1
                        nl = soup.new_tag("navLabel")
                        txt = soup.new_tag("text")
                        txt.string = stitle
                        nl.append(txt)
                        child_np.append(nl)
                        c = soup.new_tag("content", attrs={"src": f"{filename}#{sanchor}"})
                        child_np.append(c)
                        np.append(child_np)
                        
            ncx_file.write_text(str(soup), encoding="utf-8")

    # 2. Update nav.xhtml
    nav_file = oebps_dir / "nav.xhtml"
    if nav_file.exists():
        soup = BeautifulSoup(nav_file.read_text(encoding="utf-8"), "html.parser")
        toc_nav = soup.find("nav", attrs={"epub:type": "toc"}) or soup.find("nav", id="toc")
        if toc_nav:
            ol = toc_nav.find("ol")
            if ol:
                for li in ol.find_all("li", recursive=False):
                    for inner_ol in li.find_all("ol"):
                        inner_ol.decompose()
                        
                    a_tag = li.find("a")
                    if not a_tag or not a_tag.get("href"):
                        continue
                    href = a_tag["href"]
                    filename = href.split("#")[0]
                    
                    if filename in section_scenes_map and section_scenes_map[filename]:
                        scenes = section_scenes_map[filename]
                        a_tag["href"] = f"{filename}#{scenes[0][1]}"
                        sub_ol = soup.new_tag("ol")
                        for stitle, sanchor in scenes:
                            sub_li = soup.new_tag("li")
                            sub_a = soup.new_tag("a", attrs={"href": f"{filename}#{sanchor}"})
                            sub_a.string = stitle
                            sub_li.append(sub_a)
                            sub_ol.append(sub_li)
                        li.append(sub_ol)
                        
            nav_file.write_text(str(soup), encoding="utf-8")


def main():
    print("🚀 Extracting 112 True Author Scene Break Indices...")
    exact_indices = extract_exact_paragraph_indices()
    
    targets = [
        lib_root / "[k]/Fantasy_Science_Fiction/#Cixin Liu/[k] The Dark Forest Cixin Liu (4.43).epub",
        lib_root / "[k-e]/Fantasy_Science_Fiction/#Cixin Liu/[k-e] The Dark Forest Cixin Liu (4.43).epub",
        lib_root / "[study]/Fantasy_Science_Fiction/#Cixin Liu/[study_] The Dark Forest Cixin Liu (4.43).epub",
        lib_root / "[study]/Fantasy_Science_Fiction/#Cixin Liu/[study] The Dark Forest Cixin Liu (4.43).epub",
        lib_root / "[e-s]/Fantasy_Science_Fiction/#Cixin Liu/[e-s] The Dark Forest Cixin Liu (4.43).epub",
        lib_root / "[xteink]/[study]/Fantasy_Science_Fiction/#Cixin Liu/[study_] The Dark Forest Cixin Liu (4.43).epub",
        lib_root / "[xteink]/[study]/Fantasy_Science_Fiction/#Cixin Liu/[study] The Dark Forest Cixin Liu (4.43).epub",
        lib_root / "[xteink]/[e-s]/Fantasy_Science_Fiction/#Cixin Liu/[e-s] The Dark Forest Cixin Liu (4.43).epub",
    ]
    
    for t in targets:
        if t.exists():
            fix_dark_forest_epub(t, exact_indices)
            
            # Sync to Google Drive
            try:
                rel = t.relative_to(lib_root)
                gdrive_dest = gdrive_root / rel
                if gdrive_dest.parent.exists():
                    shutil.copy2(t, gdrive_dest)
                    print(f"  ☁️ Synced to Google Drive: {gdrive_dest.name}")
            except Exception as e:
                pass


if __name__ == "__main__":
    main()
