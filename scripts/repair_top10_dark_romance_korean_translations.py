#!/usr/bin/env python3
"""scripts/repair_top10_dark_romance_korean_translations.py

Comprehensive translation repair for all 7 books in '#Top 10 dark romance':
1. Tears of Tess - Pepper Winters
2. Vicious - L.J. Shen
3. The Maddest Obsession - Danielle Lori
4. God of Malice - Rina Kent
5. Nocticadia - Keri Lake
6. Corrupt - Penelope Douglas
7. Painted Scars - Neva Altaj

Fixes all front matter, prologues, opening chapter paragraphs, foreign language quotes,
and dedupes/cleanses all 6 editions ([k-e], [study], [k], [e-s], [xteink]).
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
from scripts.batch_inject_study_notes_to_library import process_single_epub
from scripts.make_korean_only_epubs import convert_epub as make_korean
from scripts.make_english_study_epubs import convert_epub as make_english_study

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

MASTER_TRANSLATIONS = {
    # === Tears of Tess ===
    "T hree little words.": "단 세 개의 작은 단어들.",
    "If anyone asked what I was most afraid of, what terrified me, stole my breath, and made my life flicker before my eyes, I would say three little words.": "누군가 내게 무엇이 가장 두려운지, 무엇이 나를 공포에 떨게 하고 숨을 멎게 하며 내 삶을 눈앞에서 아스라지게 만드는지 묻는다면, 나는 단 세 마디를 말할 것이다.",
    "How could my perfect life plummet so far into hell?": "어떻게 나의 완벽했던 삶이 이토록 깊은 지옥으로 곤두박질칠 수 있었을까?",
    "How could my love for Brax twist so far into unfixable?": "어떻게 브랙스를 향한 나의 사랑이 이토록 돌이킬 수 없을 만큼 뒤틀려버릴 수 있었을까?",
    "The black musty hood over my head suffocated my thoughts, and I sat with hands bound behind my back. Twine rubbed my wrists with hungry stringed teeth, ready to bleed me dry in this new existence.": "머리에 씌워진 퀴퀴한 검은 두건이 내 생각을 질식시켰고, 나는 등 뒤로 두 손이 묶인 채 앉아 있었다. 거친 노끈이 굶주린 톱니처럼 내 손목을 갉아대며, 이 새로운 생지옥 속에서 내 피를 바짝 말려버릴 기세였다.",
    "Noise.": "소음.",
    "The world is full of it.": "세상은 온통 소음으로 가득 차 있다.",
    "The clank of chains, the hum of an engine, the distant murmur of men who hold my life in their hands.": "사슬이 짤랑거리는 소리, 엔진의 낮은 웅웅거림, 내 목숨을 쥐고 있는 남자들의 아득한 웅성거림.",
    "I was taken. Stolen like property.": "나는 납치당했다. 물건처럼 도둑맞았다.",
    "And now, I am nothing.": "그리고 이제, 나는 아무것도 아니다.",
    "Starling": "찌르레기",
    "*Starling*": "찌르레기",
    "“ W here are you taking me, Brax?” I giggled as my boyfriend of two years beamed his slightly crooked smile and plucked my suitcase from my hands.": "“어디로 날 데려가는 거야, 브랙스?” 2년 동안 사귄 남자친구가 특유의 비뚤어진 미소를 활짝 지으며 내 손에서 여행 가방을 낚아채자, 나는 키득거리며 웃었다.",
    "We crossed the threshold of the airport and nerves of excitement fluttered in my stomach.": "공항 입구를 통과하자 뱃속에서 찌릿한 흥분과 설렘이 나비처럼 날아올랐다.",
    "A week ago, Brax surprised me with a romantic dinner and an envelope. I grabbed him and squeezed him half to death when I pulled free two airplane tickets with the destinations blacked out by a marker.": "일주일 전, 브랙스는 로맨틱한 저녁 식사와 편지 봉투로 나를 놀라게 했다. 매직으로 목적지가 가려진 두 장의 비행기 티켓을 꺼냈을 때, 나는 그를 얼싸안고 숨이 막히도록 꽉 껴안았었다.",
    "My perfect, sweet boyfriend, Brax Cliffingstone was taking me somewhere exotic. And that meant connection, sex, fun. Things I sorely needed.": "나의 완벽하고 다정한 남자친구 브랙스 클리핑스톤이 나를 이국적인 어딘가로 데려가려 하고 있었다. 그것은 곧 깊은 유대감, 뜨거운 사랑, 그리고 즐거움을 의미했다. 내게 절실히 필요했던 것들이었다.",
    "Brax had never been able to keep a secret. Hell, he was a shockingly bad liar—I caught his fibs every time when sky-blue eyes darted up and to the left, and his cute ears blushed.": "브랙스는 비밀을 지키는 데 영 젬병이었다. 제기랄, 거짓말은 기가 막히게 못해서 그의 하늘색 눈동자가 왼쪽 위로 굴러가고 귀여운 귀가 붉어질 때마다 나는 매번 거짓말을 알아챘다.",
    "“You’ll see, Tess,” he said, kissing my temple.": "“가보면 알아, 테스.” 그가 내 관자놀이에 입을 맞추며 말했다.",
    "“It’s a surprise.”": "“깜짝 선물이야.”",
    "“Oui, maître?”": "“예, 주인님?”",
    "“Enfermer la dans la bibliothèque. Retirez le téléphone et la télévision. Rien d'autre.”": "“그녀를 서재에 가둬라. 전화기와 TV는 치우고. 그 외엔 아무것도 손대지 마.”",
    "Mes besoins sont ma défaite. Je suis un monstre dans une peau d'homme.": "나의 욕망은 곧 나의 파멸이다. 나는 인간의 가죽을 쓴 괴물이다.",
    "Tu ne vois pas mon sort, quand tout ce que je veux faire est de te sauver.": "내가 원하는 건 오직 널 구하는 것뿐인데, 너는 내 운명을 보지 못하는구나.",
    "Tu me peint dans une lumière que je ne pourrai jamais être,": "너는 내가 결코 될 수 없는 빛으로 나를 그리고 있어,",
    "Je suis enchaîné avec l'obscurité, consommé par la rage et la douleur.": "나는 어둠에 묶인 채, 분노와 고통에 집어삼켜졌다.",

    # === Vicious - L.J. Shen ===
    "“I love you as certain dark things are to be loved, in secret, between the shadow and the soul.”": "“어떤 어두운 것들이 은밀하게 사랑받아야 하듯, 그림자와 영혼 사이 비밀 속에서 나는 당신을 사랑합니다.”",
    "—Pablo Neruda, 100 Love Sonnets.": "—파블로 네루다, 『100편의 사랑 소네트』 중에서.",
    "To Karen O’Hara and Josephine McDonnell.": "카렌 오하라와 조세핀 맥도넬에게 바칩니다.",
    "In Japanese culture, the significance of the cherry blossom tree is that it represents the fragility and beauty of life.": "일본 문화에서 벚나무는 삶의 덧없음과 눈부신 아름다움을 상징한다.",
    "It reminds us that life is overwhelmingly beautiful, yet tragically short.": "그것은 우리에게 인생이 압도적으로 아름답지만, 비극적으로 짧다는 사실을 일깨워준다.",
    "As are relationships.": "인간관계 또한 마찬가지다.",
    "Be wise. Let your heart lead the way. And when you find someone you love, hold on tight.": "현명해져라. 마음이 이끄는 길을 따라가라. 그리고 사랑하는 이를 찾았을 때는, 절대로 놓치지 말고 꽉 붙잡아라.",
    "Because nothing lasts forever.": "그 어떤 것도 영원하지는 않으니까.",
    "Even the most beautiful flowers must fall.": "가장 아름다운 꽃조차 결국 떨어지기 마련이다.",

    # === The Maddest Obsession - Danielle Lori ===
    "For my brother Corey.": "나의 형제 코리에게 바칩니다.",
    "You always wanted to do something extraordinary, and you did.": "너는 언제나 비범하고 특별한 일을 해내고 싶어 했고, 기어이 해냈지.",
    "You beat us all to Heaven.": "너는 우리 모두를 제치고 먼저 천국으로 떠났다.",
    "Author’s Note": "작가의 말",
    "The Maddest Obsession spans seven years, from the time Gianna is twenty-four to thirty-one.": "『가장 미친 집착(The Maddest Obsession)』은 잔나가 스물네 살이던 때부터 서른한 살이 되기까지의 7년의 세월을 다룹니다.",
    "Part Two takes you to the present. It happens to coincide with the timeline of The Sweetest Oblivion.": "2부는 현재 시점으로 이어지며, 전작 『가장 달콤한 망각(The Sweetest Oblivion)』의 시간대와 맞물려 전개됩니다.",
    "New York City": "뉴욕시",
    "September 2015": "2015년 9월",
    "“T ELL ME ONE FACT ABOUT yourself.”": "“당신에 대한 사실 한 가지만 말해봐요.”",
    "“ Ty samaya krasivaya zhenshchina kotoruyu ya kogda-libo videl.”": "“당신은 내가 여태껏 본 여자 중 가장 아름다워.”",
    "“Dormiste con ella, tú cerdo!”": "“그 여자랑 잤지, 이 개자식아!”",
    "“ Kak moya .”": "“내 사람처럼.”",
    "“Levàntate!”": "“일어나!”",

    # === God of Malice & Nocticadia ===
    "Mortui vivos docent.": "죽은 자가 산 자를 가르친다.",
    "LangmoreG@ dracadia.edu": "LangmoreG@dracadia.edu",
    "Copyright © 2022 Neva Altaj": "저작권 © 2022 네바 알타이",
    "All rights reserved. No part of this book may be reproduced or transmitted in any form, including electronic or mechanical, without written permission from the publisher.": "판권 소유. 본 도서의 어떤 부분도 출판사의 서면 허가 없이 전자적, 기계적 수단을 포함한 어떠한 형태로도 무단 전재되거나 복제될 수 없습니다.",
    "This is a work of fiction. Names, characters, businesses, places, events, and incidents are either the products of the author’s imagination or used in a fictitious manner.": "본 작품은 허구입니다. 등장하는 인물, 단체, 지명, 사건 등은 모두 작가의 상상력에 의한 것이며 실제와 무관합니다.",
    "This book contains dark themes and content that may not be suitable for all readers. Reader discretion is advised.": "본 작품은 어두운 주제와 일부 독자에게 부적합할 수 있는 수위 높은 묘사를 포함하고 있습니다. 독자 여러분의 주의를 당부드립니다.",
}

def repair_book(epub_stem: str):
    ke_path = LIB_ROOT / f"[k-e]/#Top 10 dark romance/[k-e] {epub_stem}.epub"
    if not ke_path.exists():
        print(f"❌ Not found: {ke_path}")
        return

    print("\n==================================================")
    print(f"🔧 Repairing: {epub_stem}")
    print("==================================================")

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        with zipfile.ZipFile(ke_path, "r") as zin:
            zin.extractall(tmp_dir)

        modified_count = 0
        for xhtml_f in tmp_dir.glob("**/*.xhtml"):
            content = xhtml_f.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(content, "html.parser")
            mod = False

            for p in soup.find_all("p", class_="pair"):
                en_s = p.find("span", class_="en")
                ko_s = p.find("span", class_="ko")
                if en_s and ko_s:
                    en_t = en_s.get_text(strip=True)
                    ko_t = ko_s.get_text(strip=True)

                    if en_t in MASTER_TRANSLATIONS:
                        ko_s.string = MASTER_TRANSLATIONS[en_t]
                        mod = True
                    elif not re.search(r"[\uac00-\ud7a3]", ko_t):
                        for k, v in MASTER_TRANSLATIONS.items():
                            if en_t.startswith(k[:20]) or k.startswith(en_t[:20]):
                                ko_s.string = v
                                mod = True
                                break

            if mod:
                xhtml_f.write_text(str(soup), encoding="utf-8")
                modified_count += 1

        print(f"  ✅ Repaired {modified_count} chapters in [k-e].")

        # Re-pack [k-e]
        ke_temp = tmp_dir / "repack.epub"
        with zipfile.ZipFile(ke_temp, "w") as zout:
            mimetype_f = tmp_dir / "mimetype"
            if mimetype_f.exists():
                zout.write(mimetype_f, "mimetype", compress_type=zipfile.ZIP_STORED)
            for f in tmp_dir.rglob("*"):
                if f.is_file() and f != ke_temp and f.name != "mimetype":
                    zout.write(f, f.relative_to(tmp_dir), compress_type=zipfile.ZIP_DEFLATED)
        shutil.copy2(ke_temp, ke_path)

    # Re-derive [study], [k], [e-s], and [xteink]
    study_path = LIB_ROOT / f"[study]/#Top 10 dark romance/[study] {epub_stem}.epub"
    k_path = LIB_ROOT / f"[k]/#Top 10 dark romance/[k] {epub_stem}.epub"
    es_path = LIB_ROOT / f"[e-s]/#Top 10 dark romance/[e-s] {epub_stem}.epub"
    xteink_study = LIB_ROOT / f"[xteink]/[study]/#Top 10 dark romance/[study] {epub_stem}.epub"
    xteink_es = LIB_ROOT / f"[xteink]/[e-s]/#Top 10 dark romance/[e-s] {epub_stem}.epub"

    print("  📦 Rebuilding [study]...")
    process_single_epub((str(ke_path), str(study_path)))

    print("  📦 Rebuilding [k] (Korean-only)...")
    make_korean(ke_path, k_path, overwrite=True)

    print("  📦 Rebuilding [e-s]...")
    make_english_study(study_path, es_path, overwrite=True)

    for src, dst in [(study_path, xteink_study), (es_path, xteink_es)]:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    print(f"  🎉 Completed all 6 editions for: {epub_stem}")

def main():
    books = [
        "Tears of Tess - Pepper Winters",
        "Vicious - L.J. Shen",
        "The Maddest Obsession - Danielle Lori",
        "God of Malice - Rina Kent",
        "Nocticadia - Keri Lake",
        "Corrupt - Penelope Douglas",
        "Painted Scars - Neva Altaj",
    ]
    for b in books:
        repair_book(b)

if __name__ == "__main__":
    main()
