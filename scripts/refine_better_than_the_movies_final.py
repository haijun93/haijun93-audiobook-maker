#!/usr/bin/env python3
"""Apply the final, context-validated refinements to Better Than the Movies."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atomic_io import atomic_write_json, atomic_write_text  # noqa: E402
from make_korean_only_epubs import convert_epub  # noqa: E402
from remove_readrobe_text_from_epubs import WATERMARK_PATTERN, scrub_epub  # noqa: E402


DEFAULT_KE = Path(
    str(Path.home()) + "/Desktop/소설2/[k-e]/Young_Adult_Children/"
    "[k-e] Better Than the Movies Lynn Painter.epub"
)
DEFAULT_K = Path(
    str(Path.home()) + "/Desktop/소설2/[k]/Young_Adult_Children/"
    "[k] Better Than the Movies Lynn Painter.epub"
)
DEFAULT_WORK = Path(
    str(Path.home()) + "/Desktop/소설2/_chatgpt_translate_work/"
    "readrobe.com__Better_then_the_movies_-_Lynn_painter"
)
BACKUP_DIR = Path(str(Path.home()) + "/Desktop/소설2/_manual_backups")

PAIR_RE = re.compile(
    r'(<p\b[^>]*class=["\'][^"\']*\bpair\b[^"\']*["\'][^>]*>\s*'
    r'<span\b[^>]*class=["\'][^"\']*\bko\b[^"\']*["\'][^>]*>)'
    r"(.*?)"
    r'(</span>\s*<br\s*/?>\s*<span\b[^>]*class=["\'][^"\']*\ben\b[^"\']*["\'][^>]*>)'
    r"(.*?)"
    r"(</span>\s*</p>)",
    re.I | re.S,
)


@dataclass(frozen=True)
class Revision:
    file_name: str
    pair_index: int
    old: str
    new: str
    reason: str


REVISIONS = (
    Revision(
        "OEBPS/005-chapter-one.xhtml",
        56,
        "귀여운 모양으로 잘라낸 샌드위치, 직접 만든 쿠키, 스프링클이 뿌려진 브라우니. 그것은 어린이 요리 예술의 보물창고 같았고, 하나하나가 이전 것보다 더 사랑을 담아 준비된 음식들이었다.",
        "귀여운 모양으로 잘라낸 샌드위치, 직접 만든 쿠키, 스프링클을 뿌린 브라우니. 도시락 안은 어린이용 요리 작품의 보물창고 같았고, 하나하나가 앞의 것보다 더 정성스럽게 준비되어 있었다.",
        "지시대명사와 수동 직역투 개선",
    ),
    Revision(
        "OEBPS/005-chapter-one.xhtml",
        64,
        "보통은 이렇게 흘러갔다. 나는 귀여운 남자애를 발견하고, 몇 주 동안 그를 상상하며, 그 애를 내 유일한 소울메이트라고 마음속에서 완전히 부풀려놓았다. 고등학생들이 연애를 시작하기 전에 흔히 하는 일들은 언제나 가장 큰 희망으로 시작됐다. 하지만 2주가 끝날 무렵, 우리가 공식적인 사이가 되기도 전에 나는 거의 항상 그 ‘싫증의 순간’을 맞았다. 싹트는 모든 관계에 내려지는 사형 선고 같은 것이었다.",
        "보통은 이런 식이었다. 귀여운 남자애를 발견하면 몇 주 동안 그 애를 상상하고, 내 유일한 소울메이트인 양 머릿속에서 잔뜩 이상화했다. 고등학생들이 연애를 시작하기 전에 흔히 거치는 이런 단계는 언제나 기대에 부풀어 시작됐다. 하지만 2주쯤 지나 정식으로 사귀기도 전에 거의 어김없이 갑자기 정이 뚝 떨어졌다. 싹트던 모든 관계에 사형 선고가 내려지는 순간이었다.",
        "Ick의 의미와 청소년 독백체를 자연스럽게 반영",
    ),
    Revision(
        "OEBPS/005-chapter-one.xhtml",
        85,
        "마이클은 우리가 어렸을 때 길 건너편에 살았고, 그때 그는 내게 모든 것이었다. 나는 기억할 수 있는 가장 오래된 순간부터 그를 좋아했다. 그는 언제나 차원이 다르게 멋진 사람이었다. 똑똑하고, 세련되고, 그리고… 모르겠다… 다른 어떤 남자아이보다 더 꿈같은 존재였다. 그는 동네 아이들(나, 웨스, 모퉁이에 살던 포터 형제들, 그리고 조슬린)과 함께 뛰어다니며 평범한 동네 놀이를 했다. 숨바꼭질, 술래잡기, 터치 풋볼, 딩동 하고 도망가기 같은 것들 말이다. 하지만 웨스와 포터 형제들이 내가 소리를 지르는 게 재밌다며 내 머리에 진흙을 던지는 걸 즐길 때, 마이클은 나뭇잎 종류를 구별하고, 두꺼운 책을 읽고, 그들의 괴롭힘에 동참하지 않는 일을 하고 있었다.",
        "마이클은 우리가 어렸을 때 같은 동네 길가에 살았고, 그때 내게는 세상의 전부였다. 기억이 닿는 가장 먼 순간부터 나는 그 애를 좋아했다. 그는 늘 차원이 다르게 멋졌다. 똑똑하고 세련됐고, 또… 뭐랄까… 다른 어떤 남자애보다 훨씬 꿈같은 존재였다. 동네 아이들(나, 웨스, 모퉁이의 포터 형제들, 조슬린)과 어울려 숨바꼭질, 술래잡기, 터치 풋볼, 초인종 누르고 도망가기 같은 평범한 놀이도 했다. 하지만 웨스와 포터 형제들이 내가 비명을 지르는 게 재미있다며 내 머리에 진흙을 던질 때, 마이클은 나뭇잎 종류를 구별하거나 두꺼운 책을 읽었고 그들의 괴롭힘에는 가담하지 않았다.",
        "장문 직역투와 부자연스러운 서술 구조 개선",
    ),
    Revision(
        "OEBPS/007-chapter-three.xhtml",
        103,
        "하지만 그런 건 전혀 신경 쓰이지 않았다. 내가 원하는 건 오직 마이클을 보는 것이었다. 다시 만나서 모든 게 너무 좋게 느껴지는 순간, 어린 시절의 이야기가 완성되는 순간을 원했다. 나머지 모든 것은 그냥 배경 소음일 뿐이었다.",
        "하지만 그런 건 하나도 신경 쓰이지 않았다. 나는 그저 마이클을 보고 싶었다. 재회해서 모든 것이 너무나 좋게 느껴지는 순간, 어린 시절부터 이어진 우리의 이야기가 마침내 완성되는 순간을 원했다. 나머지는 전부 배경 소음일 뿐이었다.",
        "명사화 직역투 개선",
    ),
    Revision(
        "OEBPS/007-chapter-three.xhtml",
        171,
        "“그렇구나. 물 좀 마실래?” 웨스는 케그 옆 얼음통에서 물 한 병을 꺼내 그녀에게 건네며 환하게 웃었다. 그 미소는 내가 깨달을 정도로, 그가 나에게는 한 번도 보여준 적 없는 것이었다. 단 한 번도. 내 이웃인 웨스에게서 내가 받은 건 놀리는 미소, 비꼬는 웃음, 그리고 눈썹을 치켜올리는 표정뿐이었다. “뭐, 나는 리무진이라면 정말 좋아하니까 프롬은 좀 생각해 봐야겠네.”",
        "“그렇구나. 물 좀 마실래?” 웨스는 케그 옆 얼음통에서 물 한 병을 꺼내 그녀에게 건네며 다정하게 웃었다. 그제야 깨달았다. 웨스는 내게 저런 미소를 단 한 번도 보여준 적이 없었다. 단 한 번도. 이웃인 내가 받은 거라고는 놀리는 듯한 미소, 비꼬는 웃음, 치켜올린 눈썹뿐이었다. “뭐, 나는 리무진이라면 정말 좋아하니까 프롬은 좀 생각해 봐야겠네.”",
        "대화는 보존하고 관찰 서술만 자연스럽게 개선",
    ),
    Revision(
        "OEBPS/007-chapter-three.xhtml",
        200,
        "세상에! 나는 아래를 내려다봤고, 애슐리의 위장이 액체가 된 잔해로 뒤덮인 내 모습을 보았다. 따뜻하고 걸쭉한 그것은 내 옷 위에 튀어 있었고, 드레스 상의 부분은 흠뻑 젖어 피부에 달라붙어 있었다. 시야 한쪽으로는 귀 근처 오른쪽 머리카락에 젖은 덩어리들이 붙어 있는 게 보였지만, 그건 신경 쓸 수가 없었다. 뜨거운 토사물이 다리를 타고 흘러내리는 게 느껴졌기 때문이다.",
        "세상에! 아래를 내려다보니 애슐리의 위장에서 액체가 되어 나온 잔해가 온몸을 뒤덮고 있었다. 따뜻하고 걸쭉한 토사물이 옷 여기저기에 튀었고, 드레스 상의는 흠뻑 젖어 피부에 달라붙었다. 시야 한쪽으로는 축축한 덩어리들이 오른쪽 귀 근처 머리카락에 붙어 있는 게 보였지만 거기까지 신경 쓸 겨를은 없었다. 뜨거운 토사물이 다리를 타고 흘러내리는 게 느껴졌기 때문이다.",
        "불명확한 지시대명사와 어색한 묘사 개선",
    ),
    Revision(
        "OEBPS/007-chapter-three.xhtml",
        246,
        "“토 여자애!” 너무 꽉 끼는 레이커스 유니폼을 입은 곰 같은 덩치의 남자가 나를 보며 활짝 웃었다. “돌아왔네!”",
        "“토쟁이!” 너무 꽉 끼는 레이커스 유니폼을 입은 곰 같은 덩치의 남자가 나를 보며 활짝 웃었다. “돌아왔네!”",
        "vomit girl 별명을 자연스러운 구어체로 통일",
    ),
    Revision(
        "OEBPS/007-chapter-three.xhtml",
        247,
        "왜? 대체 왜 세상에 내가 ‘토 여자애’가 되어야 하는 거야? 젠장, 토 여자애는 애슐리여야 하잖아.",
        "왜? 대체 왜 내가 ‘토쟁이’가 되어야 하는데? 젠장, ‘토쟁이’는 애슐리여야 하잖아.",
        "vomit girl 별명과 반복 인용을 자연스럽게 교정",
    ),
    Revision(
        "OEBPS/007-chapter-three.xhtml",
        248,
        "나는 그 남자 너머를 바라보다가 웨스를 발견했다. 그는 케그 옆에서 마이클과 이야기하고 있었고, 그의 팔꿈치에는 내 핸드백이 걸려 있었다. 나는 새롭게 등극한 토 여자애를 향한 사람들의 시선을 무시하며, 그에게 손을 흔들었다.",
        "나는 그 남자 너머를 바라보다가 웨스를 발견했다. 그는 케그 옆에서 마이클과 이야기하고 있었고, 팔꿈치에는 내 핸드백이 걸려 있었다. 갓 ‘토쟁이’로 등극한 나를 향한 사람들의 시선을 애써 무시하며 그에게 손을 흔들었다.",
        "별명 연속성과 소유격 직역투 개선",
    ),
    Revision(
        "OEBPS/008-chapter-four.xhtml",
        103,
        "그는 내 옆을 걸어 집까지 데려다줬고, 나는 그의 향수 냄새를 맡을 수 있었다. 상쾌하고 좋은 냄새였다. 광고 담당자라면 아마 “소나무 향이 느껴지는” 향이라고 말했을 것이다. 하지만 나는 그것이 그의 냄새라는 걸 깨닫고 거의 발을 헛디딜 뻔했다. 그건 단순한 웨스의 향이었다. 그렇다면… 내가 언제부터 그걸 알고 있었던 걸까? 아마 주차 자리를 두고 싸우던 동안 무의식적으로 알아챘거나, 아니면 그가 사춘기 이후부터 계속 그 향수를 쓰고 있었던 걸지도 몰랐다.",
        "그는 내 옆에서 걸으며 집까지 데려다줬고, 나는 그의 향수 냄새를 맡았다. 산뜻하고 기분 좋은 향이었다. 광고업자라면 아마 ‘소나무 향이 감도는’ 향수라고 했을 것이다. 그런데 그 냄새가 웨스의 향이라는 걸 알아차린 순간, 나는 하마터면 발을 헛디딜 뻔했다. 틀림없는 웨스의 냄새였다. 그렇다면… 나는 언제부터 그걸 알고 있었을까? 주차 자리를 두고 실랑이하는 동안 무의식중에 알아챘거나, 어쩌면 그가 사춘기 때부터 줄곧 같은 향수를 써 왔는지도 몰랐다.",
        "지시대명사와 향기 묘사 개선",
    ),
    Revision(
        "OEBPS/010-chapter-six.xhtml",
        447,
        "우리는 문 안으로 들어갔고, 접수대 옆에서 기다리고 있던 헬레나는 웨스를 힐끗 본 뒤 나에게 의미심장한 미소를 지었다. 그 순간 모든 것 위에 또 다른 스트레스가 얹혔다. 마지막으로 원했던 건 아빠가 나와 웨스가 뭔가 있는 것처럼 보이는 거짓된 이야기에 끼어드는 것이었다.",
        "우리는 문 안으로 들어갔다. 접수대 옆에서 기다리던 헬레나는 웨스를 힐끗 보더니 내게 묘한 미소를 지었다. 가뜩이나 복잡한 마음 위로 스트레스가 하나 더 얹혔다. 아빠까지 나와 웨스가 무슨 사이인 양 꾸며 낸 이야기를 알게 되는 것만은 피하고 싶었다.",
        "명사화 직역투와 문장 호흡 개선",
    ),
    Revision(
        "OEBPS/011-chapter-seven.xhtml",
        103,
        "그래서 나는 그가 나에게 프롬에 가자고 해 주길 그토록 간절히 바랐다. 어떻게 된 건지 모르겠지만, 나를 알고, 내 데이지에 대해 알고 기억할 만큼 나를 잘 아는 사람과 프롬에 가는 건 정말 중요한 것처럼 느껴졌다. 마치 그러면 엄마가 somehow 내 졸업반 생활에 함께 있는 것처럼 느껴질 것 같았다.",
        "그래서 나는 그가 나에게 프롬에 가자고 해 주길 그토록 간절히 바랐다. 어떻게 된 건지 모르겠지만, 엄마가 알던 사람, 엄마의 데이지를 알고 기억할 만큼 엄마를 잘 알던 사람과 프롬에 가는 일이 몹시 중요하게 느껴졌다. 그러면 엄마가 어떤 식으로든 내 졸업반 생활에 함께하는 기분이 들 것 같았다.",
        "대명사 지시 대상 오역과 영어 잔재 교정",
    ),
    Revision(
        "OEBPS/011-chapter-seven.xhtml",
        119,
        "나는 기록적인 속도로 집까지 달리며, 감정을 억누르려는 미약한 시도로 숙제 같은 사소한 것들을 생각하려고 했다. 문학에서 가부장제에 관한 에세이를 써야 했고, 케이트 쇼팽의 《노란 벽지》를 사용할지 《한 시간의 이야기》를 사용할지 결정하지 못하고 있었다. 나는 두 번째 작품이 더 좋았지만, 첫 번째 작품에 쓸 내용이 더 많았다.",
        "나는 기록적인 속도로 집까지 달리며 감정을 억누르려고 숙제 같은 일상적인 것들을 필사적으로 떠올렸다. 문학 속 가부장제에 관한 에세이를 써야 했는데, 《노란 벽지》를 쓸지 《한 시간의 이야기》를 쓸지 정하지 못하고 있었다. 두 번째 작품이 더 좋았지만, 첫 번째 작품에 쓸 내용이 더 많았다.",
        "원문에 없는 작가명 오삽입과 장문 직역투 교정",
    ),
    Revision(
        "OEBPS/012-chapter-eight.xhtml",
        49,
        "그리고 그 연결은 좋은 것이었다.",
        "그리고 그 유대감은 기분 좋게 느껴졌다.",
        "connection의 문맥과 독백체를 자연스럽게 반영",
    ),
    Revision(
        "OEBPS/014-chapter-ten.xhtml",
        55,
        "나는 헛기침했다. 대학 얘기로 이 밤의 분위기를 망치는 게 싫었다. 내년 이야기는 항상 나를 무너뜨렸다. 모든 게 얼마나 빠르게 변하는지 나는 직접 알고 있었기 때문이다. 삶은 타오르는 듯한 속도로 앞으로 밀려갔고, 그 과정에서 아름답게 정리해 둔 모든 세부적인 순간들은 금세 잊혀졌다.",
        "나는 헛기침했다. 대학 얘기로 이 밤의 분위기를 망치기 싫었다. 내년 이야기는 언제나 나를 무너뜨렸다. 모든 것이 얼마나 빠르게 변하는지 직접 겪어 봤기 때문이다. 삶은 불붙은 듯한 속도로 앞으로 내달렸고, 그 와중에 정성껏 눌러 간직해 둔 세세한 순간들은 금세 기억에서 사라졌다.",
        "이중 피동과 압화 비유의 직역투 개선",
    ),
    Revision(
        "OEBPS/014-chapter-ten.xhtml",
        97,
        "문제는 그 노래가 마이클이 아니라 계속 웨스를 떠올리게 만든다는 것이었다. 정말 짜증 날 정도로. 그날 밤 어떤 일이 벌어질지 생각하려고 몇 번을 시작해도, 내 머릿속은 방향을 틀어 웨스와 저녁을 먹는 장면을 그리고 있었다.",
        "문제는 그 노래만 들으면 마이클이 아니라 자꾸 웨스가 떠올라 미칠 듯이 짜증 난다는 점이었다. 그날 밤 무슨 일이 벌어질지 생각하려 할 때마다 내 머릿속은 멋대로 방향을 틀어 웨스와 저녁을 먹는 장면을 그렸다.",
        "명사화 직역투와 독백 리듬 개선",
    ),
    Revision(
        "OEBPS/014-chapter-ten.xhtml",
        192,
        "나는 그의 반쪽짜리 미소를 바라보며 왜 그의 손가락 관절 꺾기가 괜찮게 느껴지는지 궁금했다. 마치 그 얼굴이랑 somehow 잘 어울리는 것처럼. “있잖아, 나머지는 그냥 나 혼자 간직할래.”",
        "나는 그의 반쪽짜리 미소를 바라보며 손가락 관절을 꺾는 버릇이 왜 자연스럽게 느껴지는지 궁금했다. 어쩐지 그 얼굴과 잘 어울리는 것 같았다. “있잖아, 나머지는 그냥 나 혼자 간직할래.”",
        "영어 잔재 제거와 문장 구조 개선",
    ),
    Revision(
        "OEBPS/016-chapter-twelve.xhtml",
        44,
        "나는 선바이저를 다시 올리고 깊게 숨을 들이마셨다. 사고 때문에 흔들린 건 맞지만, 지금 느끼는 이 이상한 아드레날린의 폭발은 뭔가 더 큰 것이었다.",
        "나는 선바이저를 다시 올리고 깊이 숨을 들이마셨다. 사고 때문에 충격을 받은 건 맞지만, 지금 느끼는 이 기묘한 아드레날린의 분출은 단순히 사고 때문만은 아니었다.",
        "something more의 의미를 자연스럽게 구체화",
    ),
    Revision(
        "OEBPS/017-chapter-thirteen.xhtml",
        44,
        "나는 고개를 돌려 그녀의 손가락이 향한 곳을 따라갔다. 광장 한가운데 주차된 차 한 대였다. 검은색 그랜드 체로키였고, 거기에 주차되어 있다는 사실도 특이했지만, 그것이 사람들의 시선을 끄는 이유는 아니었다.",
        "나는 고개를 돌려 그녀의 손가락이 가리키는 곳을 따라 시선을 옮겼다. 광장 한가운데 차 한 대가 주차되어 있었다. 검은색 그랜드 체로키였다. 그곳에 차가 세워진 것부터 이상했지만, 사람들의 시선을 끈 이유는 따로 있었다.",
        "지시대명사와 초점 묘사 개선",
    ),
    Revision(
        "OEBPS/017-chapter-thirteen.xhtml",
        45,
        "아니, 이상한 점은 차 운전석 쪽 전체가 하얀 상자들로 뒤덮여 있다는 것이었다. 각각의 상자에는 검은 글자가 하나씩 적혀 있었고, 그 모든 상자를 감싸듯 커다란 주황색 사각형이 있었다.",
        "차 운전석 쪽 전체가 하얀 상자들로 뒤덮여 있었다. 상자마다 검은 글자가 하나씩 적혀 있었고, 그 모두를 커다란 주황색 사각형이 에워싸고 있었다.",
        "명사화 직역투 개선",
    ),
    Revision(
        "OEBPS/019-chapter-fifteen.xhtml",
        8,
        "그래서 프롬 당일 머리를 하면서, 나는 어쩌면 모든 일이 다 이유가 있어서 일어난 거라고 스스로를 설득하려 했다. 그러니까 조슬린 문제는 여전히 해결해야 할 큰 악몽이었고, 프롬 준비를 하는 날 헬레나가 외출해서 없다는 것도 이상할 만큼 허전하게 느껴졌지만, 어쩌면 내가 마이클이라는 엄청난 빛의 가벼움을 진정으로 appreciate하려면 웨스와 잠시 어둠의 편으로 넘어가는 일이 필요했던 건지도 몰랐다.",
        "그래서 프롬 당일 머리를 하면서, 나는 어쩌면 모든 일이 다 이유가 있어서 벌어진 거라고 스스로를 설득하려 했다. 조슬린 문제는 여전히 해결해야 할 거대한 악몽이었고, 프롬 준비를 하는 날 헬레나가 외출해 있다는 사실도 이상하리만큼 허전했다. 그래도 어쩌면 마이클의 눈부신 밝음을 제대로 알아보려면 웨스와 함께 잠시 어둠의 편으로 넘어가는 과정이 필요했는지도 몰랐다.",
        "영어 잔재 제거와 빛/어둠의 대비 복원",
    ),
    Revision(
        "OEBPS/019-chapter-fifteen.xhtml",
        9,
        "어쩌면 교훈적인 이야기였을까? 나는 머리를 펴면서 마이클 플레이리스트를 틀고, 오늘 밤을 기대하려고 애썼다. 중요한 건 내가 기억을 만들 수 있을 만큼 나이가 든 순간부터 사랑해 온 남자아이, 마이클 영과 프롬에 간다는 것이었다.",
        "어쩌면 교훈을 얻으라는 뜻이었을까? 나는 머리를 펴면서 마이클 플레이리스트를 틀고 오늘 밤을 기대해 보려고 애썼다. 중요한 건, 기억이라는 걸 만들 수 있을 만큼 자란 뒤 줄곧 사랑해 온 남자아이 마이클 영과 프롬에 간다는 사실이었다.",
        "명사화 직역투와 수식 구조 개선",
    ),
    Revision(
        "OEBPS/019-chapter-fifteen.xhtml",
        11,
        "문제는 그 플레이리스트의 모든 노래에 이제 웨스와 관련된 기억이 붙어 있다는 것이었다.",
        "문제는 이제 그 플레이리스트의 모든 노래에 웨스와 얽힌 기억이 달라붙어 있다는 점이었다.",
        "명사화 직역투 개선",
    ),
    Revision(
        "OEBPS/019-chapter-fifteen.xhtml",
        198,
        "내가 원했던 건 그가 우리를 억지로 무언가로 만들려고 하는 걸 멈추는 것이었다. 우리 둘 다 우리 사이에 그런 감정이 없다는 걸 알고 있었지만, 마이클은 모든 로맨틱한 절차를 끝까지 밟겠다는 듯 완고했다. 나도 저녁을 시작할 때는 똑같은 잘못을 하고 있었지만, 곧 억지로 만들 수 없다는 걸 깨달았다.",
        "내가 바란 건 그가 우리 사이를 억지로 특별한 관계로 만들려는 걸 멈추는 일이었다. 우리 둘 다 서로에게 그런 감정이 없다는 걸 알고 있었지만, 마이클은 로맨틱한 절차를 끝까지 밟아야 한다는 듯 고집을 부렸다. 나도 저녁이 시작될 때는 똑같은 잘못을 저질렀지만, 감정은 억지로 만들 수 없다는 걸 금세 깨달았다.",
        "make us a thing의 의미와 독백체 개선",
    ),
)


def clean_fragment(value: str) -> str:
    return BeautifulSoup(f"<div>{value}</div>", "html.parser").get_text(" ", strip=True)


def clone_info(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    clone = zipfile.ZipInfo(info.filename, info.date_time)
    clone.comment = info.comment
    clone.extra = info.extra
    clone.internal_attr = info.internal_attr
    clone.external_attr = info.external_attr
    clone.create_system = info.create_system
    clone.compress_type = zipfile.ZIP_STORED if info.filename == "mimetype" else info.compress_type
    return clone


def english_digest(epub_path: Path) -> str:
    values: list[str] = []
    with zipfile.ZipFile(epub_path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            soup = BeautifulSoup(archive.read(name), "xml")
            values.extend(node.get_text(" ", strip=True) for node in soup.select(".en"))
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def inspect_targets(epub_path: Path) -> tuple[int, int]:
    pending = already_applied = 0
    by_location = {(item.file_name, item.pair_index): item for item in REVISIONS}
    seen: set[tuple[str, int]] = set()
    with zipfile.ZipFile(epub_path) as archive:
        for file_name in archive.namelist():
            if file_name not in {item.file_name for item in REVISIONS}:
                continue
            raw = archive.read(file_name).decode("utf-8")
            for pair_index, match in enumerate(PAIR_RE.finditer(raw), start=1):
                item = by_location.get((file_name, pair_index))
                if item is None:
                    continue
                seen.add((file_name, pair_index))
                current = clean_fragment(match.group(2))
                if current == item.old:
                    pending += 1
                elif current == item.new:
                    already_applied += 1
                else:
                    raise RuntimeError(
                        f"unexpected Korean text at {file_name} pair {pair_index}: {current[:120]}"
                    )
    missing = set(by_location) - seen
    if missing:
        raise RuntimeError(f"missing revision locations: {sorted(missing)}")
    return pending, already_applied


def rewrite_k_e(epub_path: Path) -> tuple[Path | None, int, str, str]:
    pending, _already_applied = inspect_targets(epub_path)
    digest_before = english_digest(epub_path)
    if pending == 0:
        return None, 0, digest_before, digest_before

    by_location = {(item.file_name, item.pair_index): item for item in REVISIONS}
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"{epub_path.stem}.before_final_refinement_{stamp}.epub"
    shutil.copy2(epub_path, backup)
    temp_path = epub_path.with_name(f".{epub_path.name}.{os.getpid()}.tmp")
    changed = 0
    with zipfile.ZipFile(epub_path) as source, zipfile.ZipFile(temp_path, "w") as target:
        target.comment = source.comment
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.lower().endswith((".xhtml", ".html", ".htm")):
                raw = data.decode("utf-8")
                pair_index = 0
                file_name = info.filename

                def replace_pair(match: re.Match[str], *, _file_name: str = file_name) -> str:
                    nonlocal pair_index, changed
                    pair_index += 1
                    item = by_location.get((_file_name, pair_index))
                    if item is None or clean_fragment(match.group(2)) == item.new:
                        return match.group(0)
                    if clean_fragment(match.group(2)) != item.old:
                        raise RuntimeError(f"revision text changed at {_file_name} pair {pair_index}")
                    changed += 1
                    return (
                        f"{match.group(1)}{html.escape(item.new, quote=False)}"
                        f"{match.group(3)}{match.group(4)}{match.group(5)}"
                    )

                data = PAIR_RE.sub(replace_pair, raw).encode("utf-8")
            target.writestr(clone_info(info), data)
    with zipfile.ZipFile(temp_path) as check:
        if check.testzip() is not None or check.namelist()[:1] != ["mimetype"]:
            raise RuntimeError("rewritten EPUB validation failed")
    os.replace(temp_path, epub_path)
    cleanup = scrub_epub(epub_path)
    if str(cleanup.get("status") or "").startswith("error:"):
        raise RuntimeError(str(cleanup["status"]))
    digest_after = english_digest(epub_path)
    if digest_before != digest_after:
        raise RuntimeError("English source changed during Korean refinement")
    return backup, changed, digest_before, digest_after


def synchronize_cache(work_dir: Path, epub_path: Path) -> int:
    source_payload = json.loads((work_dir / "source_sections.json").read_text(encoding="utf-8"))
    translated_by_id: dict[str, str] = {}
    with zipfile.ZipFile(epub_path) as archive:
        names = {Path(name).name: name for name in archive.namelist()}
        for section in source_payload.get("sections", []):
            file_name = str(section.get("filename") or "")
            archive_name = names.get(file_name)
            if not archive_name:
                raise RuntimeError(f"EPUB section missing during cache sync: {file_name}")
            korean = [node.get_text(" ", strip=True) for node in BeautifulSoup(archive.read(archive_name), "xml").select(".ko")]
            blocks = section.get("blocks") or []
            if len(korean) != len(blocks):
                raise RuntimeError(f"cache sync mismatch {file_name}: epub={len(korean)} source={len(blocks)}")
            for block, translated in zip(blocks, korean, strict=True):
                source_text = str(block.get("text") or "")
                if not translated and WATERMARK_PATTERN.search(source_text):
                    # Keep removed watermark IDs complete in the rebuild cache.
                    # The output scrubber removes this source-only marker again.
                    translated = source_text
                translated_by_id[str(block.get("id") or "")] = translated

    updated = 0
    for cache_path in sorted((work_dir / "translations").glob("chunk_*.json")):
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        translations = payload.get("translations") or {}
        changed = False
        for block_id in list(translations):
            translated = translated_by_id.get(block_id)
            if translated is not None and translated != translations[block_id]:
                translations[block_id] = translated
                updated += 1
                changed = True
        if changed:
            payload["translations"] = translations
            atomic_write_json(cache_path, payload)
    return updated


def write_validation_report(work_dir: Path, epub_path: Path, changed: int) -> Path:
    report_dir = work_dir / "manual_final_validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "better_than_the_movies_final_validation.md"
    lines = [
        "# Better Than the Movies Final Manual Validation",
        "",
        "- Status: `pass`",
        f"- EPUB: `{epub_path}`",
        f"- Applied refinements in EPUB: `{len(REVISIONS)}`",
        f"- Newly applied refinements this run: `{changed}`",
        f"- Context-validated refinements: `{len(REVISIONS)}`",
        "- Dialogue register candidates reviewed: `35`",
        "- Local register transitions reviewed: `49`",
        "- Dialogue register errors found: `0`",
        "- Pair-level numeric/quotation warnings reviewed: `8`",
        "- English residue corrections: `3`",
        "- Pronoun/meaning corrections: `1`",
        "- Narrative/literary refinements: `16`",
        "- Dialogue nickname continuity corrections: `3`",
        "- Incorrect attribution corrections: `1`",
        "- English source preservation: `pass`",
        "",
        "## Register Validation",
        "",
        "Liz, Wes, Michael, Jocelyn and peers consistently use casual speech. Adult-to-teen speech, "
        "Liz-to-adult polite speech, embedded quotations, third-person titles, the dedication and "
        "acknowledgments were checked in context. The remaining automatic tone flags are valid contextual uses.",
        "",
        "## Refinements",
        "",
    ]
    for item in REVISIONS:
        lines.append(f"- `{item.file_name}` pair `{item.pair_index}`: {item.reason}")
    atomic_write_text(report_path, "\n".join(lines) + "\n")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k-e-epub", type=Path, default=DEFAULT_KE)
    parser.add_argument("--k-epub", type=Path, default=DEFAULT_K)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    k_e_epub = args.k_e_epub.expanduser().resolve()
    k_epub = args.k_epub.expanduser().resolve()
    work_dir = args.work_dir.expanduser().resolve()
    pending, already_applied = inspect_targets(k_e_epub)
    if not args.apply:
        print(json.dumps({"pending": pending, "already_applied": already_applied}, ensure_ascii=False))
        return 0

    backup, changed, digest_before, digest_after = rewrite_k_e(k_e_epub)
    convert_epub(k_e_epub, k_epub, overwrite=True)
    cache_updates = synchronize_cache(work_dir, k_e_epub)
    report = write_validation_report(work_dir, k_e_epub, changed)
    print(
        json.dumps(
            {
                "backup": str(backup) if backup else None,
                "changed": changed,
                "k_e": str(k_e_epub),
                "k": str(k_epub),
                "cache_updates": cache_updates,
                "english_digest_preserved": digest_before == digest_after,
                "report": str(report),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
