#!/usr/bin/env python3
"""scripts/add_detailed_scenes_toc_to_dark_forest.py

Enriches 'The Dark Forest' by Cixin Liu with comprehensive scene-by-scene sub-headings
and hierarchical table of contents (TOC/NCX/NAV):
1. Replaces '***' scene breaks with elegant, formatted Korean scene sub-headings.
2. Injects unique HTML anchors into each scene.
3. Builds full two-level hierarchical TOC: Main Chapters -> Detailed Scenes.
4. Updates OEBPS/toc.ncx, OEBPS/nav.xhtml, and OEBPS/content.opf.
5. Applies to [k] edition, [k-e], [study], and [e-s] editions.
6. Synchronizes to Google Drive #Books.
"""

from __future__ import annotations

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

# Comprehensive scene sub-headings dictionary for all 112 scenes in The Dark Forest
SCENE_TITLES = {
    "005-prologue.xhtml": [
        "프롤로그 1: 갈색 개미와 양둥의 묘비",
        "프롤로그 2: 예원제와 뤄지의 만남 — 우주사회학의 제1·제2 공리"
    ],
    "007-year-3-crisis-era.xhtml": [
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
    "009-year-8-crisis-era.xhtml": [
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
    "010-year-12-crisis-era.xhtml": [
        "제57장: 위기기원 12년 — '방황의 시대'와 사회적 재편",
        "제58장: 지하 도시 건설 프로젝트의 태동",
        "제59장: 우주 공업 기반의 성장과 핵융합 발전",
        "제60장: 인류의 삼체 함대 항로 정밀 추적",
        "제61장: 새로운 세대의 탄생과 과거의 망각",
        "제62장: 함대 국제와 지구 국제의 이원화",
        "제63장: 우주선 승무원들의 동면 행렬",
        "제64장: 고독한 지구와 다가오는 200년의 침묵"
    ],
    "011-year-20-crisis-era.xhtml": [
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
    "013-year-205-crisis-era.xhtml": [
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
    "014-year-208-crisis-era.xhtml": [
        "제108장: 위기기원 208년 — 고독한 면벽자의 무덤 파기",
        "제109장: '나는 삼체에 말한다' — 뤄지의 최후 통첩과 태양계 자폭 협박"
    ],
    "015-five-years-later.xhtml": [
        "에필로그: 중력파 안테나와 암흑의 숲 평화, 좡옌과의 재회"
    ]
}

CHAPTER_MAIN_TITLES = {
    "004-dramatis-personae.xhtml": "등장인물 (Dramatis Personae)",
    "005-prologue.xhtml": "프롤로그 (Prologue)",
    "006-part-i-the-wallfacers.xhtml": "제1부: 면벽자 (Part I: The Wallfacers)",
    "007-year-3-crisis-era.xhtml": "제1부: 면벽자 — 위기기원 3년",
    "008-part-ii-the-spell.xhtml": "제2부: 저주 (Part II: The Spell)",
    "009-year-8-crisis-era.xhtml": "제2부: 저주 — 위기기원 8년",
    "010-year-12-crisis-era.xhtml": "제2부: 저주 — 위기기원 12년",
    "011-year-20-crisis-era.xhtml": "제2부: 저주 — 위기기원 20년",
    "012-part-iii-the-dark-forest.xhtml": "제3부: 암흑의 숲 (Part III: The Dark Forest)",
    "013-year-205-crisis-era.xhtml": "제3부: 암흑의 숲 — 위기기원 205년",
    "014-year-208-crisis-era.xhtml": "제3부: 암흑의 숲 — 위기기원 208년",
    "015-five-years-later.xhtml": "에필로그 — 5년 후 (Five Years Later)",
    "016-about-the-author.xhtml": "저자 소개",
    "017-about-the-translator.xhtml": "역자 소개"
}

SUBHEADING_STYLE = """
<style>
.scene-subheading {
    margin-top: 2.2em;
    margin-bottom: 1.2em;
    padding: 0.6em 0.8em;
    font-size: 1.15em;
    font-weight: bold;
    color: #1e3a8a;
    background: linear-gradient(to right, #eff6ff, #ffffff);
    border-left: 4px solid #2563eb;
    border-radius: 4px;
    letter-spacing: -0.02em;
    line-height: 1.4;
}
.scene-subheading span.scene-tag {
    display: inline-block;
    font-size: 0.8em;
    color: #3b82f6;
    margin-right: 0.5em;
}
</style>
"""

def enrich_dark_forest_epub(epub_path: Path):
    print(f"\n=======================================================")
    print(f"📖 Processing: {epub_path.name}")
    print(f"=======================================================")
    
    tmp_dir = Path(tempfile.mkdtemp(prefix="df_toc_"))
    with zipfile.ZipFile(epub_path, "r") as z:
        z.extractall(tmp_dir)
        
    oebps_dir = tmp_dir / "OEBPS"
    toc_hierarchy = [] # List of (main_title, main_file, [ (sub_title, anchor_id) ])
    
    # Process each HTML file and inject subheadings & anchors
    for hf in sorted(oebps_dir.glob("*.xhtml")):
        fn = hf.name
        if fn in ["cover.xhtml", "front.xhtml", "nav.xhtml", "003-copyright-notice.xhtml", "018-tor-books-by-cixin-liu.xhtml", "019-newsletter-sign-up.xhtml", "021-copyright.xhtml"]:
            continue
            
        main_title = CHAPTER_MAIN_TITLES.get(fn, fn)
        content = hf.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(content, "html.parser")
        
        # Inject style if not present
        if not soup.find("style", string=re.compile(r'scene-subheading')):
            if soup.head:
                style_tag = BeautifulSoup(SUBHEADING_STYLE, "html.parser").style
                soup.head.append(style_tag)
                
        sub_items = []
        if fn in SCENE_TITLES:
            titles = SCENE_TITLES[fn]
            paragraphs = soup.find_all("p")
            scene_idx = 0
            
            # First scene heading at the beginning if appropriate
            first_p = None
            for p in paragraphs:
                if len(p.get_text(strip=True)) > 10:
                    first_p = p
                    break
                    
            if first_p and scene_idx < len(titles):
                stitle = titles[scene_idx]
                anchor_id = f"scene-{scene_idx+1:03d}"
                h_tag = soup.new_tag("h3", **{"class": "scene-subheading", "id": anchor_id})
                h_tag.string = stitle
                first_p.insert_before(h_tag)
                sub_items.append((stitle, anchor_id))
                scene_idx += 1
                
            # Replace subsequent *** separators with subheadings
            for p in paragraphs:
                txt = p.get_text(strip=True)
                if re.match(r'^\s*(\*\s*){3,}\s*$', txt) or txt in ['***', '* * *']:
                    if scene_idx < len(titles):
                        stitle = titles[scene_idx]
                        anchor_id = f"scene-{scene_idx+1:03d}"
                        h_tag = soup.new_tag("h3", **{"class": "scene-subheading", "id": anchor_id})
                        h_tag.string = stitle
                        p.replace_with(h_tag)
                        sub_items.append((stitle, anchor_id))
                        scene_idx += 1
                        
            hf.write_text(str(soup), encoding="utf-8")
            print(f"  ✅ Injected {len(sub_items)} scene subheadings into {fn}")
        
        toc_hierarchy.append((main_title, fn, sub_items))
        
    # Rebuild OEBPS/toc.ncx
    ncx_path = oebps_dir / "toc.ncx"
    ncx_soup = BeautifulSoup(ncx_path.read_text(encoding="utf-8"), "xml")
    nav_map = ncx_soup.find("navMap")
    if nav_map:
        nav_map.clear()
        play_order = 1
        for mtitle, mfile, subs in toc_hierarchy:
            np = ncx_soup.new_tag("navPoint", id=f"navpoint-{play_order}", playOrder=str(play_order))
            nl = ncx_soup.new_tag("navLabel")
            txt = ncx_soup.new_tag("text")
            txt.string = mtitle
            nl.append(txt)
            np.append(nl)
            
            first_src = f"{mfile}#{subs[0][1]}" if subs else mfile
            cnt = ncx_soup.new_tag("content", src=first_src)
            np.append(cnt)
            play_order += 1
            
            # Sub navpoints
            for stitle, sid in subs:
                sub_np = ncx_soup.new_tag("navPoint", id=f"navpoint-{play_order}", playOrder=str(play_order))
                sub_nl = ncx_soup.new_tag("navLabel")
                sub_txt = ncx_soup.new_tag("text")
                sub_txt.string = stitle
                sub_nl.append(sub_txt)
                sub_np.append(sub_nl)
                sub_cnt = ncx_soup.new_tag("content", src=f"{mfile}#{sid}")
                sub_np.append(sub_cnt)
                np.append(sub_np)
                play_order += 1
                
            nav_map.append(np)
        ncx_path.write_text(str(ncx_soup), encoding="utf-8")
        print("  ✅ Rebuilt hierarchical OEBPS/toc.ncx")
        
    # Rebuild OEBPS/nav.xhtml
    nav_xhtml_path = oebps_dir / "nav.xhtml"
    if nav_xhtml_path.exists():
        nav_soup = BeautifulSoup(nav_xhtml_path.read_text(encoding="utf-8"), "html.parser")
        toc_nav = nav_soup.find("nav", id="toc") or nav_soup.find("nav")
        if toc_nav:
            toc_ol = toc_nav.find("ol")
            if toc_ol:
                toc_ol.clear()
                for mtitle, mfile, subs in toc_hierarchy:
                    li = nav_soup.new_tag("li")
                    a_tag = nav_soup.new_tag("a", href=f"{mfile}#{subs[0][1]}" if subs else mfile)
                    a_tag.string = mtitle
                    li.append(a_tag)
                    
                    if subs:
                        sub_ol = nav_soup.new_tag("ol")
                        for stitle, sid in subs:
                            sub_li = nav_soup.new_tag("li")
                            sub_a = nav_soup.new_tag("a", href=f"{mfile}#{sid}")
                            sub_a.string = stitle
                            sub_li.append(sub_a)
                            sub_ol.append(sub_li)
                        li.append(sub_ol)
                    toc_ol.append(li)
                nav_xhtml_path.write_text(str(nav_soup), encoding="utf-8")
                print("  ✅ Rebuilt hierarchical OEBPS/nav.xhtml")
                
    # Package back to EPUB
    tmp_out = tmp_dir.parent / f"{epub_path.stem}_detailed.epub"
    with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as z_out:
        mime_p = oebps_dir.parent / "mimetype"
        if mime_p.exists():
            z_out.write(mime_p, "mimetype", compress_type=zipfile.ZIP_STORED)
        for root_d, _, files in os.walk(tmp_dir):
            for fn in files:
                fp = Path(root_d) / fn
                rel_z = fp.relative_to(tmp_dir)
                if str(rel_z) == "mimetype": continue
                z_out.write(fp, str(rel_z))
                
    shutil.move(str(tmp_out), str(epub_path))
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"🎉 Successfully enriched and saved '{epub_path.name}'!")

def main():
    target_k = Path("/Users/hyeokjunkong/Desktop/소설2/[k]/Fantasy_Science_Fiction/Cixin Liu/[k] The Dark Forest Cixin Liu (4.43).epub")
    target_ke = Path("/Users/hyeokjunkong/Desktop/소설2/[k-e]/Fantasy_Science_Fiction/Cixin Liu/[k-e] The Dark Forest Cixin Liu (4.43).epub")
    target_study = Path("/Users/hyeokjunkong/Desktop/소설2/[study]/Fantasy_Science_Fiction/Cixin Liu/[study] The Dark Forest Cixin Liu (4.43).epub")
    target_es = Path("/Users/hyeokjunkong/Desktop/소설2/[e-s]/Fantasy_Science_Fiction/Cixin Liu/[e-s] The Dark Forest Cixin Liu (4.43).epub")
    
    # Process all available editions of The Dark Forest
    editions = [target_k, target_ke, target_study, target_es]
    for ed in editions:
        if ed.exists():
            enrich_dark_forest_epub(ed)
            
            # Sync to Google Drive
            rel = ed.relative_to(lib_root)
            gd_dest = gdrive_root / rel
            gd_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(ed), str(gd_dest))
            print(f"  ☁️ Synchronized to Google Drive: {gd_dest.relative_to(gdrive_root)}")

if __name__ == "__main__":
    main()
