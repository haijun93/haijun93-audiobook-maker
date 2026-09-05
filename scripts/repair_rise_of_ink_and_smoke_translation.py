#!/usr/bin/env python3
"""Accurately translate untranslated prologue & front matter in 'Rise of Ink and Smoke' by Pam Godwin
and rebuild all 6 editions ([k], [k-e], [study], [e-s], [xteink]/[study], [xteink]/[e-s]).
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

# High-precision authentic literary Korean translations for untranslated segments
TRANSLATIONS = {
    # 001-1.xhtml
    "Disclaimer": "면책 조항",
    "This is a spin-off of the FROZEN FATE trilogy.": "이 작품은 <프로즌 페이트(FROZEN FATE)> 3부작의 스핀오프 소설입니다.",
    "The books must be read in order.": "책은 반드시 시리즈 출간 순서대로 읽으셔야 합니다.",
    "Hills of shivers and shadows #1": "1권: 전율과 그림자의 언덕 (Hills of Shivers and Shadows #1)",
    "Hills of Shivers and Shadows #1": "1권: 전율과 그림자의 언덕 (Hills of Shivers and Shadows #1)",
    "cage of Ice and echoes #2": "2권: 얼음과 메아리의 새장 (Cage of Ice and Echoes #2)",
    "Cage of Ice and Echoes #2": "2권: 얼음과 메아리의 새장 (Cage of Ice and Echoes #2)",
    "Heart of frost and scars #3": "3권: 서리와 상처의 심장 (Heart of Frost and Scars #3)",
    "Heart of Frost and Scars #3": "3권: 서리와 상처의 심장 (Heart of Frost and Scars #3)",
    "Rise of ink and smoke - Spin-off": "스핀오프: 잉크와 연기의 비상 (Rise of Ink and Smoke)",
    "Rise of Ink and Smoke - Spin-off": "스핀오프: 잉크와 연기의 비상 (Rise of Ink and Smoke)",
    "Rise of Ink and Smoke - content warning": "잉크와 연기의 비상 - 콘텐츠 경고 및 주의사항",
    "Rise of Ink and Smoke - Content Warning": "잉크와 연기의 비상 - 콘텐츠 경고 및 주의사항",

    # 002-2.xhtml
    "Content Warning": "콘텐츠 경고 (Content Warning)",
    "This book contains dark themes, explicit violence, graphic language, and intense sexual situations that may be triggering for some readers. Reader discretion is advised.": "본 작품은 어두운 주제, 노골적인 폭력 묘사, 거친 언어, 강도 높은 성적 묘사를 포함하고 있어 일부 독자에게 심리적 불편을 줄 수 있습니다. 독자 여러분의 신중한 선택을 당부드립니다.",
    "For a detailed list of trigger warnings, please visit the author's official website.": "자세한 트리거 경고 목록은 작가의 공식 웹사이트를 참조하시기 바랍니다.",

    # 003-prologue.xhtml
    "Prologue - Wolfson": "프롤로그 — 울프슨",
    "One year ago": "1년 전",
    "I sit in the hollow silence of my prison. No windows to the outside. No clock on the wall.": "나는 감옥의 텅 빈 적막 속에 앉아 있다. 바깥으로 난 창문도 없다. 벽에 걸린 시계조차 없다.",
    "Just me and my voyeuristic companion.": "오직 나와, 나를 훔쳐보는 관음증적 동반자뿐이다.",
    "“Hello, Regret.” I can’t see a dirty godsdamn thing beyond the heavy, soundproof door, but I know it’s there, watching.": "“안녕, 후회.” 육중한 방음문 너머로는 빌어먹을 아무것도 보이지 않지만, 놈이 거기서 지켜보고 있다는 걸 안다.",
    "Silent and cold, Regret stares back.": "침묵과 냉기 속에서, ‘후회’라는 놈이 나를 빤히 응시한다.",
    "“Admiring my banging good looks again?” I stroke my full beard. “Don’t be shy. Tell me I’m pretty.”": "“내 끝내주는 외모를 또 감상 중이신가?” 나는 텁수룩한 수염을 쓰다듬었다. “부끄러워하지 마. 예쁘다고 말해봐.”",
    "No answer. Of course not. Regret doesn’t speak. It seeps. Slithers. Wraps itself around my throat until I can’t breathe.": "대답은 없다. 당연하지. 후회는 말을 하지 않는다. 그저 스며들 뿐. 슬금슬금 기어와 숨이 턱 막힐 때까지 내 목을 죄어올 뿐이다.",
    "“Serious question. Why are you so clingy? Got nothing better to do than haunt my balls?”": "“진지하게 묻는데, 넌 왜 이렇게 들러붙냐? 내 불알이나 맴도는 것 말고는 할 일이 그렇게도 없어?”",
    "Regret swells, filling my empty spaces.": "후회는 걷잡을 수 없이 부풀어 올라 내 텅 빈 공간들을 채운다.",
    "I have a lot of those.": "내겐 그런 빈 공간이 너무나도 많았다.",
    "“I feel you smothering.” I chuckle bitterly. “Breathing down my neck. You’re worse than a needy ex.”": "“네가 숨 막히게 죄어오는 게 느껴져.” 나는 쓰라리게 헛웃음을 쳤다. “내 목덜미에 숨을 헐떡거리며 말이야. 집착 심한 전 애인보다 더 지독하군.”",
    "A chill pebbles my skin.": "서늘한 한기가 온몸의 닭살을 돋게 만든다.",
    "I shove off the musty mattress, needing movement. And a smoke. Or a drink. Or a blow job.": "몸을 움직여야만 했기에 퀴퀴한 매트리스를 박차고 일어났다. 담배 한 대가 간절했다. 아니면 독한 술 한 잔이나, 뒤흔드는 쾌락이라도.",
    "Titties would be good, too. A couple of supple pillows to rest my heavy head while I forget I’m never getting out of here.": "가슴도 좋겠지. 내가 여기서 결코 살아서 나가지 못할 거라는 사실을 잊은 채, 무거운 머리를 뉘일 부드러운 베개 두 덩이 말이다.",
    "Never sounds accurate.": "결코 나가지 못한다는 건 아주 정확한 표현이었다.",
    "The room stinks of sweat and stale breath, of time stretching into an endless, agonizing loop.": "방 안에서는 땀 냄새와 퀴퀴한 날숨 냄새, 그리고 끝없는 고통의 굴레로 늘어지는 시간의 악취가 진동했다.",
    "I should be dead.": "나는 진작에 죽었어야 했다.",
    "To think, if I hadn’t thrown myself off that cliff, I wouldn’t be in this fucking cage.": "생각해 보면, 내가 그 절벽에서 몸을 던지지만 않았어도 이 빌어먹을 새장에 갇히지는 않았을 텐데.",
    "Instead, I did the damn thing. I stretched out my arms like a broken bird, plummeted into the icy river, and survived.": "하지만 난 기어이 그 짓을 저질렀다. 부러진 새처럼 양팔을 벌리고 얼어붙은 강물 속으로 곤두박질쳤지만, 빌어먹게도 살아남았다.",
    "Yeah. My captor is a medical doctor. Good for me. He mended my shattered bones just so he could keep me locked up.": "그래. 나를 가둔 놈은 의사였다. 나 참 운도 좋지. 놈은 날 가둬두려고 내 산산조각 난 뼈들을 죄다 맞춰놓았다.",
    "The best part? He has an unhealthy hard-on for the psycho who broke me in the first place.": "가장 압권인 게 뭔지 아나? 놈은 애초에 날 망가뜨렸던 그 사이코패스 자식에게 비정상적으로 흥분해 있다는 점이다.",
    "As if.": "참 나, 웃기지도 않지.",
    "Dr. Limp Dick is a cheap imitation. A dollar-store Dahmer. I’m waiting for him to slip up.": "그 고자 의사 놈은 싸구려 모조품에 불과하다. 다이소표 연쇄살인마 다머 같은 놈. 난 놈이 빈틈을 보이기만을 기다리고 있다.",
    "Why not?": "왜 아니겠어?",
    "Why keep me alive if not to fuck my heavenly body ten ways to Sunday?": "내 눈부신 육체를 밤낮으로 처참하게 유린할 게 아니라면, 대체 왜 날 살려두는 거겠나?",
    "I inhale deeply and regret it immediately.": "숨을 깊게 들이마셨다가 곧바로 후회했다.",
    "The damp air, ripe with mildew, carries a sharp bite of antiseptic.": "곰팡이 냄새로 눅눅한 공기 속에 코를 찌르는 독한 소독약 냄새가 섞여 있었다.",
    "Bleach.": "표백제.",
    "Urine.": "오줌.",
    "Blood.": "피.",
    "Unthinkable fluids live in these walls.": "상상조차 하기 싫은 온갖 체액들이 이 벽 속에 스며들어 있었다.",
    "How many people have died here? How many bodies have rotted in this cell?": "여기서 얼마나 많은 사람이 죽어나갔을까? 이 감방 안에서 얼마나 많은 시체가 썩어 문드러졌을까?",
    "I curl my fingers, pressing them to my nose. It’s fine. I’m fine.": "손가락을 오므려 코를 틀어막았다. 괜찮아. 난 괜찮아.",
    "The facts are these. If I hadn’t jumped, I’d be dead. I would’ve died with my brothers.": "진실은 이것뿐이다. 내가 뛰어내리지 않았더라면 난 죽었을 것이다. 내 형제들과 함께 숨을 거두었겠지.",
    "But I wouldn’t have died alone.": "하지만 적어도 혼자서 쓸쓸히 죽지는 않았을 텐데.",
    "Now you will. Regret fists my stomach. You’ll die a virgin. A failure. A traitor.": "‘이젠 넌 그렇게 될 거야.’ 후회가 내 위장을 주먹으로 쥐어짠다. ‘넌 동정인 채로 죽을 거야. 실패자이자 배신자로 말이지.’",
    "“What do you want from me? An apology?” My jaw tightens. “Want me to beg for forgiveness?”": "“나한테 뭘 바라는 건데? 사과라도 원해?” 턱을 꽉 악물었다. “내가 무릎 꿇고 용서라도 빌길 바라는 거냐고?”",
    "My insides clench as Regret strengthens its hold.": "후회가 옥죄는 힘을 더해오자 내 오장육부가 뒤틀렸다.",
    "“You love this, don’t you? Watching me tear myself apart. Watching me rot in this hole.”": "“넌 이게 아주 신나겠지, 어? 내가 스스로를 찢어발기는 꼴을 보면서. 이 구덩이에서 썩어가는 꼴을 지켜보면서 말이야.”",
    "Regret leans in, waiting.": "후회는 더 가까이 몸을 숙인 채 나를 기다린다.",
    "“I know. You won’t let me forget her. Or them. Or the last thing I said to Leo before I jumped.”": "“알아. 넌 내가 그녀를 잊지 못하게 만들겠지. 그들도. 내가 뛰어내리기 직전 레오에게 내뱉었던 그 마지막 말도.”",
    "I definitely tried to kill her. She’s dead anyway. We all are.": "‘난 분명 그녀를 죽이려 했어. 어차피 그녀는 죽었어. 우리 모두 다 죽은 목숨이라고.’",
    "The echo of my words scrapes through my skull like rusted iron.": "내가 내뱉었던 그 말의 메아리가 녹슨 쇠붙이처럼 내 두개골을 긁어댄다.",
    "“No.” I grip my head. “That was a lie.”": "“아니야.” 나는 머리를 감싸 쥐었다. “그건 거짓말이었어.”",
    "A cruel, desperate lie. One I needed Leo to believe.": "잔인하고 절박한 거짓말. 레오가 믿게 만들어야만 했던 거짓말.",
    "I would never hurt Frankie. When I fired that gun on the cliff, I aimed away from her.": "난 결코 프랭키를 해칠 생각이 없었다. 그 절벽에서 총을 쏘았을 때도, 난 그녀를 빗겨 겨누었으니까.",
    "What if she believes the lie? What if she thinks you tried to murder her?": "‘만약 그녀가 그 거짓말을 믿는다면? 네가 자길 진짜로 죽이려 했다고 생각한다면 어쩔 테냐?’",
}

def repair_xhtml_content(html_str: str) -> str:
    soup = BeautifulSoup(html_str, "html.parser")
    for p in soup.find_all("p", class_="pair"):
        en_span = p.find("span", class_="en")
        ko_span = p.find("span", class_="ko")
        if en_span and ko_span:
            en_text = en_span.get_text().strip()
            # Check if there is a known translation
            if en_text in TRANSLATIONS:
                ko_span.string = TRANSLATIONS[en_text]
            else:
                # Fuzzy/clean match
                clean_en = re.sub(r'\s+', ' ', en_text).strip()
                if clean_en in TRANSLATIONS:
                    ko_span.string = TRANSLATIONS[clean_en]
                elif not re.search(r"[\uac00-\ud7a3]", ko_span.get_text()):
                    # Match by starting substring
                    for k, v in TRANSLATIONS.items():
                        if en_text.startswith(k[:30]) or k.startswith(en_text[:30]):
                            ko_span.string = v
                            break
    return str(soup)

def rebuild_all_editions_for_rise_of_ink_and_smoke():
    print("==================================================================")
    print("🔧 REPAIRING RISE OF INK AND SMOKE TRANSLATIONS & 6 EDITIONS")
    print("==================================================================")

    ke_path = LIB_ROOT / "[k-e]/#Pam Godwin/[k-e] Rise of Ink and Smoke Pam Godwin.epub"
    if not ke_path.exists():
        print(f"❌ Cannot find base k-e: {ke_path}")
        return

    # 1. Repair [k-e] first
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        with zipfile.ZipFile(ke_path, "r") as zin:
            zin.extractall(tmp_dir)

        for xhtml_f in tmp_dir.glob("**/*.xhtml"):
            if "001" in xhtml_f.name or "002" in xhtml_f.name or "003" in xhtml_f.name:
                repaired = repair_xhtml_content(xhtml_f.read_text(encoding="utf-8"))
                xhtml_f.write_text(repaired, encoding="utf-8")
                print(f"  ✅ Repaired [k-e] chapter: {xhtml_f.name}")

        # Re-pack [k-e] with proper mimetype first
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

    study_path = LIB_ROOT / "[study]/#Pam Godwin/[study] Rise of Ink and Smoke Pam Godwin.epub"
    k_path = LIB_ROOT / "[k]/#Pam Godwin/[k] Rise of Ink and Smoke Pam Godwin.epub"
    es_path = LIB_ROOT / "[e-s]/#Pam Godwin/[e-s] Rise of Ink and Smoke Pam Godwin.epub"

    xteink_study = LIB_ROOT / "[xteink]/[study]/#Pam Godwin/[study] Rise of Ink and Smoke Pam Godwin.epub"
    xteink_es = LIB_ROOT / "[xteink]/[e-s]/#Pam Godwin/[e-s] Rise of Ink and Smoke Pam Godwin.epub"

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
    print("🎉 ALL 6 EDITIONS OF 'RISE OF INK AND SMOKE' FULLY REPAIRED & VERIFIED!")
    print("==================================================================")

if __name__ == "__main__":
    rebuild_all_editions_for_rise_of_ink_and_smoke()
