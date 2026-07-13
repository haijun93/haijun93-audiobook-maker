#!/usr/bin/env python3
"""Review and refine Lessons in Sin dialogue register with Gemini Web."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audiobook_maker import (  # noqa: E402
    CHATGPT_WEB_CHROME_PATH,
    GEMINI_WEB_CHROME_PATH,
    chatgpt_web_launch_args,
    load_gemini_web_cookies,
    load_gemini_web_modules,
)
from atomic_io import atomic_write_json, atomic_write_text  # noqa: E402
from final_epub_tone_review import classify_dialogue, extract_dialogues  # noqa: E402
from make_korean_only_epubs import convert_epub  # noqa: E402
from remove_readrobe_text_from_epubs import WATERMARK_PATTERN, scrub_epub  # noqa: E402
from translate_epub_with_chatgpt_web_to_study_epub import request_web_translation  # noqa: E402


DEFAULT_KE = Path(
    str(Path.home()) + "/Desktop/소설2/[k-e]/Romance_Dark_Romance/Pam Godwin/"
    "[k-e] Lessons in Sin Pam Godwin.epub"
)
DEFAULT_K = Path(
    str(Path.home()) + "/Desktop/소설2/[k]/Romance_Dark_Romance/Pam Godwin/"
    "[k] Lessons in Sin Pam Godwin.epub"
)
DEFAULT_WORK = Path(
    str(Path.home()) + "/Desktop/소설2/_chatgpt_translate_work/"
    "readrobe.com__Lessons_in_Sin_-_Pam_Godwin/honorific_refinement"
)
BACKUP_DIR = Path(str(Path.home()) + "/Desktop/소설2/_manual_backups")
MANUAL_OVERRIDES = {
    "D00274": (
        "“여기서 기다려. 내가 처리할게.” 나는 옆에 있던 여자아이에게 말했다. “캐리. 같이 가자.”"
    ),
    "D00095": (
        "“오, 좋은 생각이네요. 제 생체 강화 팔로 철창을 구부려서 치우면 되겠네요. "
        "망할 창문을 열려고 손톱을 다 부러뜨린 다음에요.”"
    ),
    "D00114": (
        "“와. 진짜 어둡네요.” 나는 입술을 깨물었다. “봐요, 나쁜 여자애들을 벌주는 일이 신부님 직업이라는 건 "
        "알아요. 하지만 솔직히 말할게요. 천국은 나한테 맞는 곳이 아니에요. 그러니까 오지가 초대 명단에 못 오른다면, "
        "거기가 얼마나 재미있는 곳이겠어요? 거기 누가 있는데요? 가르마도 반듯하고, 춤도 촌스럽고, 작년에 산 청바지를 "
        "입은 답답한 모범생들 무리? 틱톡 엄마들 같잖아요. 해시태그 올드톡. 하품 나오네요.”"
    ),
    "D00155": "“아. 그렇군요. 신부님들은 거짓말하지 않으시니까요?”",
    "D00391": "“그럼 오늘 아침에는 참여하지 않았다는 뜻이군.”",
    "D00373": (
        "“네가 저지른 위반 사항을 다시 하나씩 말하지는 않겠다.” 그는 손가락으로 책상을 두드렸다. 톡. 톡. 톡. "
        "그리고 손을 멈췄다. “총 87분의 벌을 받게 됐다.”"
    ),
    "D00376": (
        "“잘 들어, 콘스탄틴 양.” 그는 책상에서 몸을 떼고 벽에 걸린 거대한 십자가 앞으로 걸어갔다. "
        "“불평하거나 대충 하지 말고 네가 받아야 할 속죄를 수행해. 제대로 하지 않으면 시간은 처음부터 다시 계산되고, "
        "마지막에 더 많은 시간이 추가될 거다.”"
    ),
    "D00383": "“세상에, 이게 뭐예요? 설마 발 페티시 같은 거 있으신 거예요?”",
    "D00416": (
        "“성 요한의 말이 옳았어. 교만이 천사를 악마로 만들었다면, 겸손은 악마를 천사로 만들 수 있지.” "
        "그의 엄지가 내 아랫입술 곡선을 스치듯 지나갔고, 그의 시선은 그 움직임을 따라갔다. 그러고는 손을 거두고 "
        "문 쪽으로 걸어갔다. “내일 아침 미사에서 보자.”"
    ),
    "D00452": "“제가 신부님을 보면 보이는 건 자만심에 찬 위선자뿐이에요. 그러니까…”",
    "D00477": (
        "“제가 똑똑하지 않다는 말이 듣고 싶으신 거라면, 아니에요.” 그녀는 책상 옆을 걸으며 손끝으로 책상 가장자리를 "
        "따라 훑었다. “전 그냥 기억력이 좋아요. 듣거나 읽으면 나중에 다시 떠올릴 수 있어요. 그냥 암기일 뿐이에요. "
        "특별한 건 아니라고요.”"
    ),
    "D00530": (
        "“신부님 말이 맞아요.” 그녀는 이마를 손으로 치며 신음했다. “제가 바보예요. 생각을 못 했어요. 그리고… 아! "
        "변명할 여지가 없어요. 제가 한 말은 모욕적이고 무지했어요. 미안해요.” 그녀는 허리를 곧게 펴고 내 눈을 바라봤다. "
        "믿을 수 없을 만큼, 눈부시게 부끄러워하는 모습이었다. “예수님 발에 키스하든, 바닥을 닦든, 신부님이 정하는 대로 "
        "할게요. 저항 안 해요. 저는 완전한 멍청이예요.”"
    ),
    "D00669": (
        "“신부님은 빙산만큼이나 불꽃이 없는데요. 내가 말하려는 건 이거겠죠…” 나는 그의 사타구니 쪽으로 시선을 "
        "보냈다. “내가 남극을 가지고 노는 중이라고요?”"
    ),
    "D00680": (
        "“알았어요, 잠깐만요. 이건 좀 충격적인데요.” 나는 그가 자리에서 일어나 다가오는 기척을 느끼며 빠르게 "
        "신명기 22장 20절을 펼쳤다. “그러나 그 혐의가 사실이고 젊은 여자의 처녀성을 증명할 수 없다면, 그녀를 "
        "아버지 집 문으로 데려가고 그 성읍의 남자들이 그녀를 돌로 쳐 죽일 것이다.” 나는 책을 덮고 불길한 검은 "
        "표지를 바라봤다. “현대의 자유로운 여성들이 성경을 읽기 어렵게 만드는 게 바로 이런 이야기예요.”"
    ),
    "D00767": (
        "“안타깝네요. 내 방을 엉망으로 만든 사람이 누군지 알아요. 그리고 신부님이 그 애를 벌할 때…” "
        "그녀가 신음 같은 소리를 냈다. “이거 말하기 정말 힘드네요.”"
    ),
    "D00770": (
        "“—어떤 방식으로든 만지지 않았으면 해요. 무엇보다 오늘 나한테 했던 것처럼 그 애와 함께하지 않았으면 "
        "좋겠어요.” 그녀는 내 가슴 위에 턱을 올렸고, 시선은 한 번도 내게서 떨어지지 않았다. “내가 이런 걸 "
        "요구할 자격이 없다는 거 알아요. 소리 내서 말하니 너무 사소하고, 부적절하게 질투하는 것처럼 들려요. "
        "맹세할게요, 매그너스. 더 이상 어떤 행동도 하지 않을 거예요. 아마 포옹 정도는 빼고요.” 그녀는 내게 "
        "두 팔을 더 단단히 감았다. “이건 좋아요. 하지만 다시는 속옷도 안 입고 수업에 오거나, 같이 자려고 하거나, "
        "그런 짓은 안 할게요.”"
    ),
    "D00774": (
        "“내가 하려는 말은…” 그녀가 눈을 깜빡이고 숨을 들이마셨다. 배에 힘이 들어갔다. “네바다는 신부님에게 "
        "완전히 빠져 있어요. 그리고 오늘 밤 그 애가 나한테 한 짓에 대한 보상으로 신부님이 그 애 치마를 올리고—”"
    ),
    "D00775": (
        "“그만해.” 나는 낮게 중얼거리며 그녀의 도톰한 입술이 말없이 버티려 애쓰듯 오므라졌다가 다시 풀리는 모습을 "
        "지켜보았다. “나는 학생 세 명에게만 체벌 도구를 사용한 적이 있어. 그리고 세 경우 모두 아무것도 느끼지 "
        "못했어. 분노도, 좌절도, 직업적인 범위를 벗어난 관심도 없었어.”"
    ),
    "D00795": (
        "“스릴 있는 종류의 두려움이에요. 가짜 귀신의 집이 내 심장 박동을 올리고, 몸 안에 아드레날린을 쏟아붓고, "
        "살아 있다는 느낌을 주는 것처럼요. 나를 놀라게 하려고 튀어나오는 것들이 날 죽이지 않을 거라는 건 알아요. "
        "하지만 정말 심장이 뛰게 하잖아요. 신부님도 그래요.” 그녀는 창밖을 바라보며 중얼거렸다. “난 그 밀어붙이고, "
        "당기고, 긴장되고, 무서운 느낌이 좋아요. 관계 안에서도 그런 걸 원해요. 그래야 피가 계속 돌잖아요.”"
    ),
    "D00796": "“넌 네가 원하는 게 뭔지 알기에는 너무 어려.”",
    "D00800": (
        "“신부님은 나를 교회에 가게 만들 수는 있어요. 하지만 나는 절대 신부님의 신앙이 지닌 신비를 함께 나누지는 않을 "
        "거예요.” 그녀가 조용히 말했다. “나한테 터커와 키스하지 말라고 명령할 수는 있어요. 하지만 신부님이 원하든 "
        "원하지 않든 나는 섹스를 할 거예요. 그리고 내가 신부님을 무서워해야 한다고 말할 수도 있겠죠. 하지만 나는 "
        "안 무서워요. 신부님이 원하는 방식으로는요.” 그녀는 철창에서 손을 놓고 뒤로 걸어갔다. “다시는 키스하지 "
        "않을게요. 신부님이 원망하는 그런 사람이 되고 싶지 않아요. 서약을 깨게 된다면, 누구를 위해서가 아니라 "
        "신부님 자신을 위해서 해야 해요.” 그녀는 고개를 살짝 기울였다. “잘 자요, 매그너스.”"
    ),
    "D00842": (
        "“하고 있어.” 그가 내 팔을 따라 손을 천천히 움직였다. “널 볼 때마다, 그리고 네가 내 시야에 없는 모든 "
        "순간마다.” 그의 손가락이 내 엉덩이를 감싸 쥐고, 나를 그의 몸 가까이 끌어당겼다. “계속 이 일을 생각하고 있어.”"
    ),
    "D00792": "“오늘 밤 네가 한 말 중 가장 현명하군.”",
    "D01114": "“오늘 네가 받을 교정이 뭔지 물어봐.” 나는 책상에서 일어났다.",
    "D01020": (
        "“그 아이가 처음은 아니죠? 여기 무료로 다니는 다른 사람들도 있을 것 같아요. 신부님이 돕는 다른 학생들도요.”"
    ),
    "D01038": (
        "“한 달 전에…” 나는 변기 뚜껑 위에 앉아, 그가 내 속옷을 씻는 모습의 능숙함과 다정함에 놀라며 말했다. "
        "“내가 신부님을 사디스트라고 했을 때, 도움을 받았다고 했잖아요. 여기 와서 신부가 되었고, 9년 동안 "
        "금욕했다고 했잖아요. 그 부분에 대해 궁금한 게 많아요. 물어보기가 두려웠어요. 대답하지 않을까 봐. 아니면 "
        "어쩌면, 대답할까 봐 두려웠는지도 몰라요.”"
    ),
    "D01062": (
        "“내 가슴은, 그러니까…” 그녀는 자신의 가슴을 내려다보다가 스스로 웃었다. 눈에는 장난기가 빛났다. "
        "“얘들이 뭔지에 대해서는 위원회가 있어요.”"
    ),
    "D01238": "“거기에는 나 혼자였고, 여기에는 신부님 혼자잖아요. 나는 아무것도 기대하지 않아요. 그냥…”",
    "D01243": "“손으로 그러지 마요.” 심장이 세차게 뛰었다. “매그너스 때문에 미치겠어요.”",
    "D01252": (
        "“매그너스, 이 빌어먹을 인간.” 나는 등을 활처럼 휘며 반은 으르렁거리고 반은 웃었다. “빨리 해줘요.”"
    ),
    "D01264": (
        "“완전 원시인이네요.” 나는 그의 허벅지 위로 다리를 걸치며, 그가 내 몸을 다루는 모습을 바라보는 걸 즐겼다. "
        "“나 또 하고 싶어요. 물론 신부님이 못 한다면 말고요. 나이 든 남자들은 회복하는 데 얼마나 걸려요? 비아그라 "
        "필요해요?”"
    ),
    "D01386": "“아멜리아가 마지막으로…? 그게 마지막으로 섹스한 때예요?”",
    "D01388": (
        "“그러니 지금까지 계속 금욕해온 게 당연하네요.” 그녀가 중얼거렸다. “이건 받아들이기 정말 끔찍한 일이에요. "
        "게다가 이미 감정적으로 꽉 막혀 있잖아요. 설령 아멜리아를 아꼈다고 해도, 그녀를 위해 흘릴 눈물 두 방울조차 "
        "남아 있지 않았을 거예요.”"
    ),
    "D01401": (
        "“신부님은 내가 배우고 대학에 가도록 격려해 줘요. 다른 사람들에게 숨기는 비밀을 나한테는 믿고 "
        "털어놓잖아요. 내가 주머니쥐 때문에 울 때 날 안아 줘요. 내가 피를 흘렸을 때 어두운 곳에서 체육관 바닥을 "
        "닦아 줬어요. 둘만 있을 때는 내가 굴욕을 느끼길 바라지만, 다른 사람들 앞에서는 절대 나를 모욕하지 않아요. "
        "나를 일으켜 세워 줘요. 나를 보호해 줘요. 언제나 내 편이 되어 주는 사람이에요.” 그녀는 내 뺨 위로 입술을 "
        "스치듯 가져갔다. “그러니까 아니에요. 난 신부님이 무섭지 않아요. 말로 표현할 수 없을 만큼 소중하게 "
        "생각해요.”"
    ),
    "D01410": "“해줘요.” 그녀는 허리를 움직이며 내 입을 향해 다가왔고, 자신의 혀로 나를 유혹했다.",
    "D01418": (
        "“어떻게 이렇게 좋을 수 있어요?” 그녀가 내게 몸을 밀착하며 말했다. “이렇게 가득 차고 너무 자극적인데도, "
        "아직 더 원해요. 매그너스, 마약 같아요. 그게 무서워해야 할 일이겠죠?”"
    ),
    "D01428": (
        "“그랬어요.” 그녀가 몸에 힘을 주며 말했다. 그 순간 내 숨이 멎을 만큼 강하게 조여 왔다. "
        "“하지만 지금은 아니에요. 젠장, 매그너스. 너무 벅차요. 너무 커요.”"
    ),
    "D01437": "“좋은 의미로 표현할 수 없는 거야?”",
    "D01451": (
        "“순수한 기쁨이 뭔지 알아요? 내 실크 베갯잇이에요. 얼굴이 저 끔찍한 면 베개에 눌려 있으니, "
        "그렇게 어둡고 무섭게 화난 표정을 짓는 것도 당연하죠.”"
    ),
    "D01509": "“누가 나를 감시했는지, 왜 그랬는지 알기 전까지 아무 말도 안 할 거야.”",
    "D01626": (
        "“그냥 말해.” 나는 무릎 위에서 주먹을 꽉 쥐었다. “내가— 뭐라고 생각하는지 말하면 되잖아. "
        "계속 나를 그런 식으로 쳐다보는 걸 멈출 수 있다면…”"
    ),
    "D01628": "맙소사. 나는 6개월 동안 빌어먹을 만큼 비참했어. “이제야 알아차린 거야?”",
    "D01635": "“정말 여기 있는 거예요?” 내가 속삭였다.",
    "D01637": "“날 위해 크게 포효해 주세요.” 나는 웃음 섞인 울음으로 말했다.",
    "D01738": (
        "“매그너스.” 나는 몸을 움직이며 그의 단단한 몸을 붙잡고 그를 받아들이려 했다. "
        "“이 못된 인간. 날 가져요. 제발, 전부 다 주세요.”"
    ),
    "D01739": (
        "“안녕, 잘생긴 사람. 다람쥐를 봤어.” 그녀의 시선은 기어 다니던 관목 쪽으로 다시 향했다. "
        "놓아주기 싫다는 듯했다."
    ),
    "D01743": (
        "“왜 안 해? 다들 기다리고 있잖아.” 그녀는 주변의 서식지를 가리키며 자신이 돌보는 동물들을 뜻했다."
    ),
    "D01747": "“교회에서 나랑 하자는 거야?” 나는 벨트를 풀어냈다.",
}
PAIR_RE = re.compile(
    r'(<p\b[^>]*class=["\'][^"\']*\bpair\b[^"\']*["\'][^>]*>\s*'
    r'<span\b[^>]*class=["\'][^"\']*\bko\b[^"\']*["\'][^>]*>)'
    r'(.*?)'
    r'(</span>\s*<br\s*/?>\s*<span\b[^>]*class=["\'][^"\']*\ben\b[^"\']*["\'][^>]*>)'
    r'(.*?)'
    r'(</span>\s*</p>)',
    re.I | re.S,
)
RESPONSE_RE = re.compile(r"\[\[\[BEGIN:(D\d{5})\]\]\]\s*(.*?)\s*\[\[\[END:\1\]\]\]", re.S)


@dataclass
class DialoguePair:
    id: str
    file_name: str
    pair_index: int
    pov: str
    korean: str
    english: str


def clean_fragment(value: str) -> str:
    return BeautifulSoup(f"<div>{value}</div>", "html.parser").get_text(" ", strip=True)


def extract_dialogue_pairs(epub_path: Path) -> list[DialoguePair]:
    pairs: list[DialoguePair] = []
    next_id = 1
    with zipfile.ZipFile(epub_path) as archive:
        for file_name in archive.namelist():
            if not file_name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            raw = archive.read(file_name).decode("utf-8")
            soup = BeautifulSoup(raw, "xml")
            headings = [node.get_text(" ", strip=True).upper() for node in soup.select("h2 .en")]
            pov = next(("TINSLEY" for value in headings if "TINSLEY" in value), "")
            if not pov:
                pov = next(("MAGNUS" for value in headings if "MAGNUS" in value), "")
            for pair_index, match in enumerate(PAIR_RE.finditer(raw), start=1):
                korean = clean_fragment(match.group(2))
                english = clean_fragment(match.group(4))
                if not re.search(r"[“”\"]", korean + english):
                    continue
                pairs.append(
                    DialoguePair(
                        id=f"D{next_id:05d}",
                        file_name=file_name,
                        pair_index=pair_index,
                        pov=pov or "UNKNOWN",
                        korean=korean,
                        english=english,
                    )
                )
                next_id += 1
    return pairs


def build_batches(pairs: list[DialoguePair], max_chars: int) -> list[list[DialoguePair]]:
    batches: list[list[DialoguePair]] = []
    current: list[DialoguePair] = []
    current_chars = 0
    current_file = ""
    for pair in pairs:
        rendered_chars = len(pair.korean) + len(pair.english) + 100
        if current and current_chars + rendered_chars > max_chars and pair.file_name != current_file:
            batches.append(current)
            current = []
            current_chars = 0
        elif current and current_chars + rendered_chars > max_chars * 3 // 2:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(pair)
        current_chars += rendered_chars
        current_file = pair.file_name
    if current:
        batches.append(current)
    return batches


def review_prompt(batch: list[DialoguePair], pass_index: int, focus: str = "") -> str:
    entries = "\n\n".join(
        f"ID: {pair.id}\nCHAPTER_POV: {pair.pov}\nKOREAN: {pair.korean}\nENGLISH: {pair.english}"
        for pair in batch
    )
    pass_note = (
        "1차 교정입니다. 관계와 화자 방향을 영어 원문으로 판별해 잘못된 한국어 높임을 수정하세요."
        if pass_index == 1
        else "독립적인 2차 검수입니다. 1차 결과에 남은 화자 오인, 높임 방향 오류, 한 대사 안의 말투 혼합만 수정하세요."
    )
    if focus == "tinsley_to_magnus":
        pass_note = (
            "집중 최종 검수입니다. 학생/신부 관계에 있는 틴슬리가 매그너스에게 말하는 대사인데 반말 종결이 하나라도 "
            "남은 문단만 찾아, 문단 안의 해당 대사를 모두 자연스러운 해요체 존댓말로 고치세요. 결혼 뒤 에필로그의 "
            "부부간 사적 대화와 다른 화자 방향은 절대 수정하지 마세요."
        )
    return f"""소설 Lessons in Sin의 한국어 대화체를 검수합니다. {pass_note}

필수 관계 규칙:
1. 틴슬리 -> 파더 매그너스: 학생과 신부·교직자 관계가 유지되는 동안 자연스러운 해요체 존댓말을 사용합니다. 반항, 분노, 연애와 친밀한 장면에서도 종결 높임은 유지합니다. 초기에는 '신부님/파더 매그너스', 가까워진 뒤에는 '매그너스'라고 부를 수 있지만 동사는 존댓말이어야 합니다. 불필요한 '당신'은 가능하면 생략합니다. 매그너스가 성직을 떠난 뒤 결혼한 에필로그의 부부간 사적 대화에서는 친밀한 반말을 허용합니다.
2. 매그너스 -> 틴슬리: 나이 많은 신부/교직자가 학생에게 말하므로 절제되고 권위적인 반말을 사용합니다. 공식적인 공지나 다른 성인에게 하는 말은 원래 격식을 유지합니다.
3. 다른 학생 -> 신부/교직자: 존댓말. 신부/교직자 -> 학생: 자연스러운 지도자 반말.
4. 틴슬리 -> 어머니, 형제자매, 친구와 또래 학생: 반말. 매그너스 <-> 어린 시절 친구 크리산토: 사적인 장면은 반말.
5. 영어 원문의 의미, 감정 강도, 욕설, 이름, 사건과 서술문은 바꾸지 마세요. 대화 밖의 1인칭 서술은 '~다'체를 유지하세요.
6. 영어의 you만 보고 기계적으로 바꾸지 말고 CHAPTER_POV, 대화 태그(I said, she asked, he replied), 앞뒤 대사를 사용해 화자와 청자를 판별하세요.

수정이 필요한 ID만 아래 형식으로 출력하세요. 문단 전체 한국어를 출력하고 설명, 목록, 코드펜스는 쓰지 마세요. 수정이 없으면 NO_CHANGES만 출력하세요.
[[[BEGIN:D00001]]]
수정된 한국어 문단 전체
[[[END:D00001]]]

검수 자료:
{entries}
"""


def parse_response(response: str, allowed_ids: set[str]) -> dict[str, str]:
    revisions: dict[str, str] = {}
    for match in RESPONSE_RE.finditer(response):
        dialogue_id = match.group(1)
        if dialogue_id not in allowed_ids:
            continue
        value = match.group(2).strip()
        if value and re.search(r"[가-힣]", value):
            revisions[dialogue_id] = value
    return revisions


def run_review_pass(
    *,
    context,
    timeout_error_cls,
    args,
    pairs: list[DialoguePair],
    work_dir: Path,
    pass_index: int,
    max_chars: int,
    focus: str = "",
) -> dict[str, str]:
    batches = build_batches(pairs, max_chars)
    revisions: dict[str, str] = {}
    pass_dir = work_dir / (f"pass_{pass_index}_{focus}" if focus else f"pass_{pass_index}")
    pass_dir.mkdir(parents=True, exist_ok=True)

    def request_piece(piece: list[DialoguePair], batch_index: int, suffix: str = "", depth: int = 0) -> dict[str, str]:
        stem = f"batch_{batch_index:03d}{suffix}"
        response_path = pass_dir / f"{stem}_response.txt"
        if response_path.exists():
            return parse_response(response_path.read_text(encoding="utf-8"), {pair.id for pair in piece})
        prompt = review_prompt(piece, pass_index, focus)
        atomic_write_text(pass_dir / f"{stem}_prompt.txt", prompt)
        try:
            _conversation_id, response = request_web_translation(
                context=context,
                timeout_error_cls=timeout_error_cls,
                args=args,
                prompt=prompt,
                heartbeat=None,
                label=f"Lessons honorific pass {pass_index} {batch_index}/{len(batches)}{suffix}",
                prefix=f"lessons_pass_{pass_index}_{batch_index:03d}{suffix}",
            )
        except Exception:
            if len(piece) <= 8 or depth >= 4:
                if pass_index >= 3:
                    atomic_write_json(
                        pass_dir / f"{stem}_skipped.json",
                        {
                            "reason": "Gemini 1095 after two completed review passes",
                            "dialogue_ids": [pair.id for pair in piece],
                        },
                    )
                    return {}
                raise
            midpoint = len(piece) // 2
            left = request_piece(piece[:midpoint], batch_index, f"{suffix}_a", depth + 1)
            right = request_piece(piece[midpoint:], batch_index, f"{suffix}_b", depth + 1)
            return {**left, **right}
        atomic_write_text(response_path, response)
        return parse_response(response, {pair.id for pair in piece})

    for batch_index, batch in enumerate(batches, start=1):
        cache_path = pass_dir / f"batch_{batch_index:03d}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            revisions.update(payload.get("revisions") or {})
            print(f"PASS {pass_index} {batch_index}/{len(batches)} cached changes={len(payload.get('revisions') or {})}", flush=True)
            continue
        parsed = request_piece(batch, batch_index)
        payload = {
            "pass_index": pass_index,
            "batch_index": batch_index,
            "dialogue_ids": [pair.id for pair in batch],
            "revisions": parsed,
        }
        atomic_write_json(cache_path, payload)
        revisions.update(parsed)
        print(f"PASS {pass_index} {batch_index}/{len(batches)} changes={len(parsed)}", flush=True)
        time.sleep(3)
    return revisions


def apply_revisions_to_pairs(pairs: list[DialoguePair], revisions: dict[str, str]) -> list[DialoguePair]:
    return [
        DialoguePair(**{**asdict(pair), "korean": revisions.get(pair.id, pair.korean)})
        for pair in pairs
    ]


def rewrite_k_e_epub(epub_path: Path, pairs: list[DialoguePair], revisions: dict[str, str]) -> Path:
    by_location = {(pair.file_name, pair.pair_index): revisions[pair.id] for pair in pairs if pair.id in revisions}
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"{epub_path.stem}.before_lessons_honorifics_{stamp}.epub"
    shutil.copy2(epub_path, backup)
    temp_path = epub_path.with_name(f".{epub_path.name}.{stamp}.tmp")
    with zipfile.ZipFile(epub_path) as source, zipfile.ZipFile(temp_path, "w") as target:
        target.comment = source.comment
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.lower().endswith((".xhtml", ".html", ".htm")):
                text = data.decode("utf-8")
                pair_index = 0
                file_name = info.filename

                def replace_pair(match: re.Match[str], *, _file_name: str = file_name) -> str:
                    nonlocal pair_index
                    pair_index += 1
                    revised = by_location.get((_file_name, pair_index))
                    if revised is None:
                        return match.group(0)
                    return f"{match.group(1)}{html.escape(revised, quote=False)}{match.group(3)}{match.group(4)}{match.group(5)}"

                data = PAIR_RE.sub(replace_pair, text).encode("utf-8")
            clone = zipfile.ZipInfo(info.filename, info.date_time)
            clone.comment = info.comment
            clone.extra = info.extra
            clone.internal_attr = info.internal_attr
            clone.external_attr = info.external_attr
            clone.create_system = info.create_system
            clone.compress_type = zipfile.ZIP_STORED if info.filename == "mimetype" else info.compress_type
            target.writestr(clone, data)
    with zipfile.ZipFile(temp_path) as check:
        if check.testzip() is not None or check.namelist()[:1] != ["mimetype"]:
            raise RuntimeError("rewritten EPUB validation failed")
    temp_path.replace(epub_path)
    cleanup = scrub_epub(epub_path)
    if str(cleanup.get("status") or "").startswith("error:"):
        raise RuntimeError(str(cleanup["status"]))
    return backup


def update_translation_cache(work_dir: Path, pairs: list[DialoguePair], revisions: dict[str, str]) -> int:
    source_path = work_dir.parent / "source_sections.json"
    if not source_path.exists():
        return 0
    source_payload = json.loads(source_path.read_text(encoding="utf-8"))
    blocks_by_file: dict[str, dict[str, list[str]]] = {}
    for section in source_payload.get("sections", []):
        by_text: dict[str, list[str]] = {}
        for block in section.get("blocks", []):
            text = re.sub(r"\s+", " ", str(block.get("text") or "")).strip()
            by_text.setdefault(text, []).append(str(block.get("id") or ""))
        blocks_by_file[str(section.get("filename") or "")] = by_text

    used: set[str] = set()
    revisions_by_block: dict[str, str] = {}
    for pair in pairs:
        candidates = blocks_by_file.get(Path(pair.file_name).name, {}).get(
            re.sub(r"\s+", " ", pair.english).strip(),
            [],
        )
        block_id = next((candidate for candidate in candidates if candidate and candidate not in used), "")
        if not block_id:
            continue
        used.add(block_id)
        if pair.id in revisions:
            revisions_by_block[block_id] = revisions[pair.id]

    updated = 0
    translations_dir = work_dir.parent / "translations"
    for cache_path in sorted(translations_dir.glob("chunk_[0-9][0-9][0-9][0-9].json")):
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        translations = payload.get("translations") or {}
        changed = False
        for block_id, revised in revisions_by_block.items():
            if block_id in translations and translations[block_id] != revised:
                translations[block_id] = revised
                updated += 1
                changed = True
        if changed:
            payload["translations"] = translations
            atomic_write_json(cache_path, payload)
    return updated


def synchronize_full_translation_cache(work_dir: Path, epub_path: Path) -> int:
    source_path = work_dir.parent / "source_sections.json"
    source_payload = json.loads(source_path.read_text(encoding="utf-8"))
    translations_by_block: dict[str, str] = {}
    with zipfile.ZipFile(epub_path) as archive:
        for section in source_payload.get("sections", []):
            file_name = str(section.get("filename") or "")
            archive_name = next(
                (name for name in archive.namelist() if Path(name).name == file_name),
                "",
            )
            if not archive_name:
                raise RuntimeError(f"EPUB section missing during cache sync: {file_name}")
            soup = BeautifulSoup(archive.read(archive_name), "xml")
            korean = [node.get_text(" ", strip=True) for node in soup.select(".ko")]
            blocks = section.get("blocks", [])
            if len(korean) != len(blocks):
                raise RuntimeError(
                    f"cache sync count mismatch {file_name}: epub={len(korean)} source={len(blocks)}"
                )
            for block, translated in zip(blocks, korean, strict=True):
                if not translated:
                    source_text = str(block.get("text") or "")
                    if WATERMARK_PATTERN.search(source_text):
                        translated = source_text
                    else:
                        continue
                translations_by_block[str(block.get("id") or "")] = translated

    updated = 0
    translations_dir = work_dir.parent / "translations"
    for cache_path in sorted(translations_dir.glob("chunk_[0-9][0-9][0-9][0-9].json")):
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        translations = payload.get("translations") or {}
        changed = False
        for block_id in list(translations):
            translated = translations_by_block.get(block_id)
            if translated is not None and translations[block_id] != translated:
                translations[block_id] = translated
                updated += 1
                changed = True
        if changed:
            payload["translations"] = translations
            atomic_write_json(cache_path, payload)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k-e-epub", type=Path, default=DEFAULT_KE)
    parser.add_argument("--k-epub", type=Path, default=DEFAULT_K)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--max-prompt-chars", type=int, default=18000)
    parser.add_argument("--passes", type=int, choices=(2, 3), default=2)
    parser.add_argument("--focused-tinsley-pass", action="store_true")
    parser.add_argument("--focused-pass-index", type=int, default=5)
    parser.add_argument("--apply", action="store_true")
    parsed = parser.parse_args()

    k_e_epub = parsed.k_e_epub.expanduser().resolve()
    k_epub = parsed.k_epub.expanduser().resolve()
    work_dir = parsed.work_dir.expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    original_pairs = extract_dialogue_pairs(k_e_epub)
    gemini_args = SimpleNamespace(
        web_provider="gemini",
        web_max_attempts=1,
        request_timeout_sec=900,
        gemini_web_chrome_path=GEMINI_WEB_CHROME_PATH,
        chatgpt_web_chrome_path=CHATGPT_WEB_CHROME_PATH,
        web_visible=False,
    )

    browser_cookie3, sync_playwright, timeout_error_cls = load_gemini_web_modules()
    cookies = load_gemini_web_cookies(browser_cookie3)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            executable_path=str(Path(GEMINI_WEB_CHROME_PATH).expanduser()),
            args=chatgpt_web_launch_args(visible=False),
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1200})
        context.add_cookies(cookies)
        try:
            pass_1 = run_review_pass(
                context=context,
                timeout_error_cls=timeout_error_cls,
                args=gemini_args,
                pairs=original_pairs,
                work_dir=work_dir,
                pass_index=1,
                max_chars=max(6000, parsed.max_prompt_chars),
            )
            pass_1_pairs = apply_revisions_to_pairs(original_pairs, pass_1)
            pass_2 = run_review_pass(
                context=context,
                timeout_error_cls=timeout_error_cls,
                args=gemini_args,
                pairs=pass_1_pairs,
                work_dir=work_dir,
                pass_index=2,
                max_chars=max(6000, parsed.max_prompt_chars),
            )
            pass_3: dict[str, str] = {}
            if parsed.passes >= 3:
                pass_2_pairs = apply_revisions_to_pairs(pass_1_pairs, pass_2)
                pass_3 = run_review_pass(
                    context=context,
                    timeout_error_cls=timeout_error_cls,
                    args=gemini_args,
                    pairs=pass_2_pairs,
                    work_dir=work_dir,
                    pass_index=3,
                    max_chars=max(6000, parsed.max_prompt_chars),
                )
            focused: dict[str, str] = {}
            if parsed.focused_tinsley_pass:
                focused_pairs = [
                    pair
                    for pair in original_pairs
                    if any(classify_dialogue(dialogue) in {"casual", "mixed"} for dialogue in extract_dialogues(pair.korean))
                ]
                focused = run_review_pass(
                    context=context,
                    timeout_error_cls=timeout_error_cls,
                    args=gemini_args,
                    pairs=focused_pairs,
                    work_dir=work_dir,
                    pass_index=parsed.focused_pass_index,
                    max_chars=max(6000, parsed.max_prompt_chars),
                    focus="tinsley_to_magnus",
                )
        finally:
            context.close()
            browser.close()

    if not pass_3:
        for cache_path in sorted((work_dir / "pass_3").glob("batch_[0-9][0-9][0-9].json")):
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            pass_3.update(payload.get("revisions") or {})
    # A focused rerun starts from the already-refined EPUB. Do not let stale
    # broad-pass caches overwrite newer corrections in that file.
    if parsed.focused_tinsley_pass:
        merged = {**focused, **MANUAL_OVERRIDES}
    else:
        merged = {**pass_1, **pass_2, **pass_3, **MANUAL_OVERRIDES}
    original_by_id = {pair.id: pair.korean for pair in original_pairs}
    merged = {
        dialogue_id: value
        for dialogue_id, value in merged.items()
        if value != original_by_id.get(dialogue_id)
    }
    report = {
        "dialogue_pairs": len(original_pairs),
        "pass_1_changes": len(pass_1),
        "pass_2_changes": len(pass_2),
        "pass_3_changes": len(pass_3),
        "focused_tinsley_changes": len(focused),
        "merged_changes": len(merged),
        "revisions": merged,
    }
    atomic_write_json(work_dir / "revisions.json", report)
    print(json.dumps({key: value for key, value in report.items() if key != "revisions"}, ensure_ascii=False), flush=True)
    if not parsed.apply:
        return 0
    backup = rewrite_k_e_epub(k_e_epub, original_pairs, merged)
    convert_epub(k_e_epub, k_epub, overwrite=True)
    cache_updates = update_translation_cache(work_dir, original_pairs, merged)
    full_cache_sync_updates = synchronize_full_translation_cache(work_dir, k_e_epub)
    print(
        json.dumps(
            {
                "backup": str(backup),
                "k_e": str(k_e_epub),
                "k": str(k_epub),
                "cache_updates": cache_updates,
                "full_cache_sync_updates": full_cache_sync_updates,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
