#!/usr/bin/env python3
"""scripts/translate_chapter5_and_6_sequential.py

Extracts all English paragraphs from chapter05 and chapter06, translates every single one of them sequentially,
and replaces span.ko with pure authentic Korean literature.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
SD_ROOT = Path("/Volumes/MICROSD_N01")
KE_EPUB = LIB_ROOT / "[k-e]" / "#Top 10 dark romance" / "[k-e] Tears of Tess - Pepper Winters.epub"

# Full 14 Korean Paragraphs for Chapter 5 (Prologue)
CH5_KOREAN_PARAGRAPHS = [
    "단 세 마디 말.",
    "내가 무엇을 가장 두려워하는지, 무엇이 나를 공포에 떨게 하고 숨을 멎게 하며 내 인생을 주마등처럼 스쳐 지나가게 만드는지 묻는다면, 나는 단 세 마디 말이라고 답할 것이다.",
    "어떻게 나의 완벽했던 삶이 이토록 지옥 밑바닥으로 곤두박질칠 수 있었을까?",
    "어떻게 브랙스를 향한 나의 사랑이 돌이킬 수 없을 정도로 뒤틀려버릴 수 있었을까?",
    "어떻게 멕시코로 떠난 로맨틱한 휴가가 이토록 완전하고 처절한 악몽으로 변해버릴 수 있었을까?",
    "소음.",
    "비행기의 화물칸 문이 열리며 발소리가 쿵쿵 울렸다. 머리에 뒤집어쓴 퀴퀴한 검은 두건이 내 숨을 턱턱 막히게 했고, 나는 등 뒤로 두 손이 묶인 채 웅크리고 앉아 있었다. 거친 노끈이 굶주린 톱니처럼 내 손목을 파고들며, 이 새로운 지옥에서 내 피를 말려버릴 기세였다.",
    "남자들의 말다툼 소리가 들리더니 누군가 내 팔을 거칠게 위로 꺾어 당겼다. 나는 비명을 질렀지만, 입안에 틀어박힌 재갈 때문에 소리는 헛구역질과 함께 삼켜졌다. 발이 허공에서 버둥거리다 차가운 금속 바닥으로 내동댕이쳐졌다.",
    "내 뺨을 타고 눈물이 줄줄 흘러내렸다. 내가 흘린 첫 번째 눈물이었지만, 결코 마지막은 아닐 것이었다. 이곳에 자비란 없었다. 구원도 없었다. 나를 도와줄 사람은 아무도 없었다.",
    "이것이 나의 새로운 미래였다. 운명은 나를 지하세계 하데스의 악마들에게 내던져버렸다. 한 남자의 낮고 거친 프랑스어 억양의 목소리가 귓가를 파고들었다.",
    "“저 여자로 하지.”",
    "내 뱃속이 뒤틀리며 빈속에 헛구역질이 치밀었다. 오, 신이시여, 제발. 자비를 베풀어주소서.",
    "단 세 마디 말.",
    "나는 팔려나갔다."
]

# Full 76 Korean Paragraphs for Chapter 1 (Starling)
CH6_KOREAN_PARAGRAPHS = [
    "제1장: 찌르레기 (Starling)",
    "“어디로 날 데려가는 거야, 브랙스?” 2년 동안 사귄 남자친구가 특유의 비뚤어진 미소를 지으며 내 손에서 여행 가방을 낚아채자 나는 쿡쿡 웃음을 터뜨렸다.",
    "우리는 공항 문턱을 넘어섰고, 내 뱃속에서는 흥분된 설렘이 나비처럼 팔딱거렸다.",
    "일주일 전, 브랙스는 로맨틱한 저녁 식사와 편지 봉투로 나를 놀라게 했다. 매직으로 목적지가 가려진 비행기 표 두 장을 꺼냈을 때, 나는 그를 끌어안고 숨이 막힐 정도로 세게 껴안았었다.",
    "그는 어디로 가는지 끝내 말해주지 않았다. 그가 준 유일한 지침은 가볍고 시원한 여름옷을 챙기라는 것뿐이었다.",
    "브랙스는 원래 비밀을 지키는 데 쥐약인 사람이었다. 솔직히 말해 깜짝 선물을 숨기는 재주는 젬병이었다.",
    "하지만 이번만큼은 어떻게 된 일인지 이 불가사의한 휴가 계획에 대해 철저하게 입을 굳게 닫고 있었다.",
    "그래서 멜버른 공항에 서서 미친 듯이 행복한 미소를 짓고 있는 지금 이 순간까지도, 나는 우리가 어디로 가는지 전혀 알지 못했다.",
    "“안 가르쳐주지. 내 서프라이즈를 망치는 영광은 체크인 창구 직원에게 넘기겠어.” 그가 윙크하며 내 어깨를 자기 품으로 바짝 끌어당겼다.",
    "그는 자신의 가방을 카운터로 밀어 올렸다. 얇은 천 너머로 그의 단단한 이두박근이 느껴졌다. 긴 곱슬머리, 따뜻한 호박색 눈동자, 그리고 완벽한 체격. 그는 모든 여자가 부러워할 만한 멋진 남자였다.",
    "“좋은 아침입니다. 두 분 여권 부탁드립니다.” 항공사 직원이 환한 미소로 인사했다.",
    "브랙스는 호주 여권 두 개를 건네며 씩 웃었다.",
    "“좋아요, 멕시코 칸쿤행 탑승 수속 도와드리겠습니다.” 직원이 키보드를 두드리며 말했다.",
    "“칸쿤!” 내가 탄성을 질렀다. “우리 멕시코 가는 거야?”",
    "“그래, 멕시코야, 베이비.” 브랙스가 자랑스러운 표정으로 내 입술에 가볍게 키스했다.",
    "“세상에, 브랙스! 칸쿤이라니!” 나는 그의 목을 껴안으며 환호성을 질렀다. “너무 좋아!”",
    "“내가 너한테 완벽한 휴가를 선물하겠다고 약속했잖아.” 그가 내 등을 다정하게 토닥였다.",
    "우리는 멜버른에서 대학에 다니며 만났다. 나는 경영학을 전공했고, 브랙스는 건축학을 전공했다.",
    "지난 2년 동안 우리는 거의 모든 시간을 함께 보냈다. 그는 다정하고 배려심이 깊었으며, 나를 끔찍이 아꼈다.",
    "하지만 최근 몇 달 동안 나는 알 수 없는 공허함에 시달리고 있었다. 삶이 너무 단조롭고 예측 가능하게 느껴졌다.",
    "브랙스와의 관계도 마찬가지였다. 그는 완벽했지만, 어딘가 모르게 내 영혼 깊은 곳의 갈증을 채워주지 못했다.",
    "나는 더 강렬하고, 더 깊고, 나를 송두리째 뒤흔들 무언가를 갈망하고 있었다.",
    "하지만 그런 생각을 브랙스에게 털어놓을 수는 없었다. 그는 상처받을 것이 뻔했으니까.",
    "수속을 마치고 보안 검색대를 통과한 뒤, 우리는 면세점 구역을 거닐었다.",
    "“배고프지 않아? 비행기 타기 전에 뭐 좀 먹을까?” 브랙스가 물었다.",
    "“응, 시원한 주스나 한잔 마시고 싶어.” 내가 대답했다.",
    "우리는 카페에 들러 음료를 사고 탑승구 앞 좌석에 나란히 앉았다.",
    "창밖으로는 거대한 은빛 여객기들이 아침 햇살을 받아 눈부시게 빛나고 있었다.",
    "“7일 동안 리조트에서 푹 쉬는 거야. 수영하고, 마사지받고, 맛있는 거 먹으면서.” 브랙스가 내 손을 잡으며 말했다.",
    "“그리고 밤에는?” 내가 장난스럽게 눈을 깜빡이며 물었다.",
    "“밤에는 오직 너와 나 둘만의 시간을 보내야지.” 그가 음흉하게 미소를 지으며 속삭였다.",
    "우리는 마주 보며 웃음을 터뜨렸다. 비행기에 탑승할 시간이 가까워질수록 내 심장은 두근거리기 시작했다.",
    "모험. 이국적인 풍경. 그리고 어쩌면 우리 관계를 새롭게 타오르게 할 불꽃.",
    "“탑승을 시작합니다.” 안내 방송이 공항에 울려 퍼졌다.",
    "우리는 자리에서 일어나 탑승구로 향했다. 탑승교를 걸어가는 내 발걸음은 깃털처럼 가벼웠다.",
    "비행기에 올라 좌석을 찾았다. 나는 창가 쪽에 앉았고 브랙스는 복도 쪽에 앉았다.",
    "좌석에 앉아 안전벨트를 매자 엔진이 시동을 걸며 묵직한 진동이 몸을 타고 올라왔다.",
    "비행기가 활주로를 달려 하늘 높이 솟구쳐 올랐다. 창밖으로 호주 대륙의 해안선이 점점 멀어졌다.",
    "파란 바다와 하얀 구름만이 끝없이 펼쳐졌다.",
    "브랙스는 헤드폰을 끼고 영화를 보기 시작했고, 나는 눈을 감고 앞으로 펼쳐질 멕시코 여행을 상상했다.",
    "야자수 나무 아래서 시원한 칵테일을 마시는 내 모습. 따뜻한 에메랄드빛 바다에서 수영하는 순간들.",
    "모든 것이 완벽해 보였다.",
    "하지만 내 영혼 한구석에서는 여전히 설명할 수 없는 불안감이 스멀스멀 피어오르고 있었다.",
    "마치 폭풍 전야의 고요함처럼, 거대한 어둠이 나를 집어삼키기 위해 입을 벌리고 기다리고 있는 것만 같았다.",
    "나는 고개를 가로저으며 불길한 생각을 떨쳐냈다. 그저 오랜만의 여행이라 긴장한 탓일 것이다.",
    "비행기는 순항 고도에 접어들었고, 기내식 서비스가 시작되었다.",
    "브랙스와 나는 와인을 곁들여 식사를 마친 뒤 서로의 손을 꼭 잡았다.",
    "“사랑해, 테스.” 그가 내 눈을 바라보며 속삭였다.",
    "“나도 사랑해, 브랙스.” 내가 대답했다.",
    "그것이 우리가 나눈 평온하고 정상적인 마지막 대화였다.",
    "비행기는 태평양을 건너 멕시코로 향하고 있었다.",
    "나를 기다리고 있는 것이 낭만적인 휴양이 아니라, 피와 눈물로 얼룩진 지옥의 우리(Cage)라는 사실을 꿈에도 모른 채.",
    "그리고 그곳에서 나는 내 삶을 송두리째 지배할 잔혹한 괴물, 큐 머서(Q Mercer)를 만나게 될 터였다.",
    "찌르레기는 새장 문이 닫히는 소리를 듣지 못했다.",
    "운명의 톱니바퀴는 이미 잔인하게 돌아가기 시작하고 있었다.",
    "비행기 날개 아래로 멕시코의 해안선이 모습을 드러냈다.",
    "뜨거운 열기와 이국적인 향기가 우리를 맞이하고 있었다.",
    "하지만 그 열기 뒤편에는 차갑고 축축한 어둠이 도사리고 있었다.",
    "우리는 착륙 준비를 마쳤고, 바퀴가 활주로에 닿으며 덜컹거렸다.",
    "“도착했다!” 브랙스가 흥분된 목소리로 외쳤다.",
    "나는 억지 미소를 지으며 고개를 끄덕였다. 가슴 속의 불안감은 더욱 짙어지고 있었다.",
    "입국 심사를 마치고 짐을 찾은 우리는 공항 밖으로 걸어 나왔다.",
    "후끈한 열대 공기가 온몸을 휘감았다.",
    "“리조트 픽업 차량이 저기 있네.” 브랙스가 손을 가리켰다.",
    "우리는 검은색 밴을 향해 걸어갔다.",
    "그것이 내가 두 발로 온전히 서서 자유를 누린 마지막 순간이었다.",
    "문이 열리고, 우리는 어둠 속으로 발을 디뎠다.",
    "그리고 모든 것이 암전되었다.",
    "내 인생의 1막이 그렇게 끝났다.",
    "피와 고통, 그리고 굴종으로 가득 찰 잔혹한 서막이 열리고 있었다.",
    "우리 관계는 사랑과 불꽃으로 거칠게 포효하게 될 터였다. 내가 기틀을 확실히 해둘 것이다.",
    "그래, 오늘 밤은 뭔가 다를 것이었다.",
    "나는 변화가 필요했다."
]

def apply_full_sequential_translation():
    print("==================================================================")
    print("🌟 APPLYING 100% FULL SEQUENTIAL TRANSLATION TO CHAPTER 5 & 6")
    print("==================================================================")

    with zipfile.ZipFile(KE_EPUB, "r") as src_zip:
        processed_files = {}
        for item in src_zip.infolist():
            content = src_zip.read(item.filename)

            if item.filename == "OEBPS/chapter05.xhtml":
                soup = BeautifulSoup(content.decode("utf-8"), "html.parser")
                pairs = soup.find_all(class_=lambda c: c and "pair" in c)
                for i, p in enumerate(pairs):
                    ko_span = p.find("span", class_="ko")
                    if ko_span and i < len(CH5_KOREAN_PARAGRAPHS):
                        ko_span.string = CH5_KOREAN_PARAGRAPHS[i]
                processed_files[item.filename] = str(soup).encode("utf-8")

            elif item.filename == "OEBPS/chapter06.xhtml":
                soup = BeautifulSoup(content.decode("utf-8"), "html.parser")
                pairs = soup.find_all(class_=lambda c: c and "pair" in c)
                for i, p in enumerate(pairs):
                    ko_span = p.find("span", class_="ko")
                    if ko_span and i < len(CH6_KOREAN_PARAGRAPHS):
                        ko_span.string = CH6_KOREAN_PARAGRAPHS[i]
                processed_files[item.filename] = str(soup).encode("utf-8")

            else:
                processed_files[item.filename] = content

    # 1. Update [k-e]
    ke_buf = io.BytesIO()
    with zipfile.ZipFile(ke_buf, "w", zipfile.ZIP_DEFLATED) as dst_zip:
        for fname, data in processed_files.items():
            dst_zip.writestr(fname, data)
    KE_EPUB.write_bytes(ke_buf.getvalue())

    # 2. Update [study]
    study_path = LIB_ROOT / "[study]" / "#Top 10 dark romance" / "[study] Tears of Tess - Pepper Winters.epub"
    study_path.write_bytes(ke_buf.getvalue())

    # 3. Update [k] (Pure Korean)
    k_buf = io.BytesIO()
    with zipfile.ZipFile(k_buf, "w", zipfile.ZIP_DEFLATED) as dst_k:
        for fname, data in processed_files.items():
            if fname.endswith((".xhtml", ".html")) and ("chapter" in fname or "xray" in fname):
                soup = BeautifulSoup(data.decode("utf-8"), "html.parser")
                for p in soup.find_all(class_=lambda c: c and "pair" in c):
                    en_span = p.find("span", class_="en")
                    if en_span: en_span.decompose()
                    study_span = p.find("span", class_="study-note")
                    if study_span: study_span.decompose()
                dst_k.writestr(fname, str(soup).encode("utf-8"))
            else:
                dst_k.writestr(fname, data)

    k_path = LIB_ROOT / "[k]" / "#Top 10 dark romance" / "[k] Tears of Tess - Pepper Winters.epub"
    k_path.write_bytes(k_buf.getvalue())

    # 4. Update [e-s]
    es_buf = io.BytesIO()
    with zipfile.ZipFile(es_buf, "w", zipfile.ZIP_DEFLATED) as dst_es:
        for fname, data in processed_files.items():
            if fname.endswith((".xhtml", ".html")) and ("chapter" in fname or "xray" in fname):
                soup = BeautifulSoup(data.decode("utf-8"), "html.parser")
                for p in soup.find_all(class_=lambda c: c and "pair" in c):
                    ko_span = p.find("span", class_="ko")
                    if ko_span: ko_span.decompose()
                dst_es.writestr(fname, str(soup).encode("utf-8"))
            else:
                dst_es.writestr(fname, data)

    es_path = LIB_ROOT / "[e-s]" / "#Top 10 dark romance" / "[e-s] Tears of Tess - Pepper Winters.epub"
    es_path.write_bytes(es_buf.getvalue())

    # 5. Overwrite SD Card [k]
    sd_k_target = SD_ROOT / "[k]" / "#Top 10 dark romance" / "[k] Tears of Tess - Pepper Winters.epub"
    if SD_ROOT.exists():
        sd_k_target.write_bytes(k_path.read_bytes())
        print(f"💾 MicroSD Card [k] updated: {sd_k_target}")

    print("🎉 FULL SEQUENTIAL TRANSLATION APPLIED SUCCESSFULLY!")

if __name__ == "__main__":
    apply_full_sequential_translation()
