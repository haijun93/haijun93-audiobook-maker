#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from remove_readrobe_text_from_epubs import scrub_epub
from safe_xml import safe_fromstring


SOURCE_DIR = Path(str(Path.home()) + "/Desktop/소설2")
K_ROOT = SOURCE_DIR / "[k]"
KE_ROOT = SOURCE_DIR / "[k-e]"
CLASSIFICATION_DIR = SOURCE_DIR / "_classification"
USER_AGENT = "CodexLocalEpubGenreClassifier/1.0"

CATEGORY_DIRS = {
    "Mystery_Thriller_Crime",
    "Romance_Dark_Romance",
    "Fantasy_Science_Fiction",
    "Horror_Dark_Fiction",
    "Literary_General_Fiction",
    "Historical_Fiction",
    "Young_Adult_Children",
    "Classics",
    "Nonfiction_History_Politics",
    "Biography_Memoir",
    "Psychology_Self_Help",
    "Science_Nature_Technology",
    "Business_Economics",
    "Poetry_Essays",
    "Uncategorized",
}

AUTHOR_FOLDER_NAMES = {
    "Freida McFadden",
    "Isaac Asimov",
    "Patricia Cornwell",
    "Caroline Kepnes",
    "Sarah Pinborough",
    "Bethany Jadin",
    "Lizzie B Brown",
    "Elle Kennedy",
    "Andy Weir",
    "Navessa Allen",
    "H D Carlton",
    "Pam Godwin",
    "John Grisham",
    "Paula Hawkins",
    "Daniel Silva",
    "James Patterson",
}

AUTHOR_FOLDER_ALIASES = (
    ("Freida McFadden", ("freida mcfadden", "mcfadden freida", "프리다 맥패든", "housemaid", "하우스메이드", "never lie", "절대 거짓말", "the teacher", "더 티처", "inmate", "인메이트", "divorce", "이혼", "intruder", "침입자")),
    ("Isaac Asimov", ("isaac asimov", "asimov isaac", "아이작 아시모프", "robot series", "i robot", "complete robot", "로봇", "강철 동굴", "벌거벗은 태양", "새벽의 로봇")),
    ("Patricia Cornwell", ("patricia cornwell", "cornwell patricia", "kay scarpetta", "scarpetta", "스카페타")),
    ("Caroline Kepnes", ("caroline kepnes", "kepnes caroline", "you series", "hidden bodies", "you love me", "히든 바디스", "유 러브 미", "포 유 앤드 온리 유")),
    ("Sarah Pinborough", ("sarah pinborough", "pinborough sarah", "tales from the kingdoms", "poison sarah", "charm sarah", "beauty sarah", "mayhem", "death house", "cross her heart")),
    ("Bethany Jadin", ("bethany jadin", "the code", "vested interest", "hidden agenda", "broken process")),
    ("Lizzie B Brown", ("lizzie b brown", "brown lizzie b", "obedience", "오비디언스")),
    ("Elle Kennedy", ("elle kennedy", "elle kenedy", "off campus", "the deal")),
    ("Andy Weir", ("andy weir", "앤디 위어", "project hail mary", "martian", "마션", "artemis", "아르테미스")),
    ("Navessa Allen", ("navessa allen", "lights out", "caught up")),
    ("H D Carlton", ("h d carlton", "hd carlton", "does it hurt", "haunting adeline", "haunting adelline")),
    ("Pam Godwin", ("pam godwin", "dark notes")),
    ("John Grisham", ("john grisham", "the firm", "펌")),
    ("Paula Hawkins", ("paula hawkins", "girl on the train", "걸 온 더 트레인")),
    ("Daniel Silva", ("daniel silva", "inside job")),
    ("James Patterson", ("james patterson", "house of cross")),
)

MUST_READ_ALIASES = (
    "readrobe.com",
    "unlimited memory",
    "kevin horsley",
    "the memory book",
    "harry lorayne",
    "verity",
    "collen hoover",
    "colleen hoover",
    "does it hurt",
    "hd carlton",
    "h d carlton",
    "dark notes",
    "pam godwin",
    "the deal",
    "elle kenedy",
    "elle kennedy",
    "haunting adelline",
    "haunting adeline",
    "my dark vanessa",
    "kate elizabeth russell",
    "mindfck",
    "s t abby",
)

MANUAL_CATEGORY_HINTS = (
    ("freida mcfadden", "Mystery_Thriller_Crime"),
    ("john grisham", "Mystery_Thriller_Crime"),
    ("patricia cornwell", "Mystery_Thriller_Crime"),
    ("caroline kepnes", "Mystery_Thriller_Crime"),
    ("paula hawkins", "Mystery_Thriller_Crime"),
    ("daniel silva", "Mystery_Thriller_Crime"),
    ("karin slaughter", "Mystery_Thriller_Crime"),
    ("verity", "Mystery_Thriller_Crime"),
    ("never lie", "Mystery_Thriller_Crime"),
    ("first lie wins", "Mystery_Thriller_Crime"),
    ("the firm", "Mystery_Thriller_Crime"),
    ("scarpetta", "Mystery_Thriller_Crime"),
    ("isaac asimov", "Fantasy_Science_Fiction"),
    ("andy weir", "Fantasy_Science_Fiction"),
    ("robot series", "Fantasy_Science_Fiction"),
    ("project hail", "Fantasy_Science_Fiction"),
    ("the martian", "Fantasy_Science_Fiction"),
    ("rebecca yarros", "Fantasy_Science_Fiction"),
    ("onyx storm", "Fantasy_Science_Fiction"),
    ("sarah j maas", "Fantasy_Science_Fiction"),
    ("dark notes", "Romance_Dark_Romance"),
    ("haunting adeline", "Romance_Dark_Romance"),
    ("does it hurt", "Romance_Dark_Romance"),
    ("lights out", "Romance_Dark_Romance"),
    ("the deal", "Romance_Dark_Romance"),
    ("elle kennedy", "Romance_Dark_Romance"),
    ("navessa allen", "Romance_Dark_Romance"),
    ("wicked sanctuary", "Romance_Dark_Romance"),
    ("vicious reign", "Romance_Dark_Romance"),
    ("bethany jadin", "Romance_Dark_Romance"),
    ("paulo coelho", "Literary_General_Fiction"),
    ("파울로", "Literary_General_Fiction"),
    ("코엘료", "Literary_General_Fiction"),
    ("alchemist", "Literary_General_Fiction"),
    ("demian", "Classics"),
    ("데미안", "Classics"),
    ("stranger albert camus", "Classics"),
    ("이방인", "Classics"),
    ("zorba", "Classics"),
    ("그리스인 조르바", "Classics"),
    ("1984", "Classics"),
    ("my dark vanessa", "Literary_General_Fiction"),
    ("percival everett", "Literary_General_Fiction"),
    ("james by percival", "Literary_General_Fiction"),
    ("small things like these", "Literary_General_Fiction"),
    ("claire keegan", "Literary_General_Fiction"),
    ("a man called ove", "Literary_General_Fiction"),
    ("theo of golden", "Literary_General_Fiction"),
    ("allen levi", "Literary_General_Fiction"),
    ("perfume", "Literary_General_Fiction"),
    ("향수", "Literary_General_Fiction"),
    ("토지", "Historical_Fiction"),
    ("park kyung", "Historical_Fiction"),
    ("the frozen river", "Historical_Fiction"),
    ("wicked by gregory maguire", "Fantasy_Science_Fiction"),
    ("gregory maguire", "Fantasy_Science_Fiction"),
    ("artemis", "Fantasy_Science_Fiction"),
    ("war of the worlds", "Fantasy_Science_Fiction"),
    ("우주전쟁", "Fantasy_Science_Fiction"),
    ("positronic man", "Fantasy_Science_Fiction"),
    ("book of doors", "Fantasy_Science_Fiction"),
    ("tainted cup", "Fantasy_Science_Fiction"),
    ("demon of unrest", "Nonfiction_History_Politics"),
    ("house of cross", "Mystery_Thriller_Crime"),
    ("james patterson", "Mystery_Thriller_Crime"),
    ("david baldacci", "Mystery_Thriller_Crime"),
    ("to die for", "Mystery_Thriller_Crime"),
    ("all the colors of the dark", "Mystery_Thriller_Crime"),
    ("chris whitaker", "Mystery_Thriller_Crime"),
    ("housemaid", "Mystery_Thriller_Crime"),
    ("sarah pinborough", "Mystery_Thriller_Crime"),
    ("cross her heart", "Mystery_Thriller_Crime"),
    ("death house", "Mystery_Thriller_Crime"),
    ("mayhem", "Mystery_Thriller_Crime"),
    ("hundred years war on palestine", "Nonfiction_History_Politics"),
    ("no going back", "Nonfiction_History_Politics"),
    ("the wager", "Nonfiction_History_Politics"),
    ("devil in the white city", "Nonfiction_History_Politics"),
    ("guns germs and steel", "Nonfiction_History_Politics"),
    ("unfinished love story", "Nonfiction_History_Politics"),
    ("unbroken", "Nonfiction_History_Politics"),
    ("end of everything", "Nonfiction_History_Politics"),
    ("anne frank", "Biography_Memoir"),
    ("diary of a young girl", "Biography_Memoir"),
    ("knife by salman rushdie", "Biography_Memoir"),
    ("bits and pieces", "Biography_Memoir"),
    ("light we carry", "Biography_Memoir"),
    ("body keeps the score", "Psychology_Self_Help"),
    ("unlimited memory", "Psychology_Self_Help"),
    ("kevin horsley", "Psychology_Self_Help"),
    ("the memory book", "Psychology_Self_Help"),
    ("harry lorayne", "Psychology_Self_Help"),
    ("make it stick", "Psychology_Self_Help"),
    ("heart talk", "Psychology_Self_Help"),
    ("anxious generation", "Psychology_Self_Help"),
    ("short history of nearly everything", "Science_Nature_Technology"),
    ("braiding sweetgrass", "Science_Nature_Technology"),
    ("outlive", "Science_Nature_Technology"),
    ("backyard bird chronicles", "Science_Nature_Technology"),
    ("princess saves herself", "Poetry_Essays"),
    ("tale of despereaux", "Young_Adult_Children"),
    ("quicksilver", "Romance_Dark_Romance"),
    ("callie hart", "Romance_Dark_Romance"),
    ("nicholas sparks", "Romance_Dark_Romance"),
    ("counting miracles", "Romance_Dark_Romance"),
    ("obedience", "Romance_Dark_Romance"),
    ("initial meeting", "Romance_Dark_Romance"),
    ("shadows of fury", "Romance_Dark_Romance"),
)

CATEGORY_RULES = (
    ("Young_Adult_Children", ("juvenile", "young adult", "teen", "children", "middle grade", "school story")),
    ("Horror_Dark_Fiction", ("horror", "ghost", "gothic", "occult", "supernatural", "vampire", "haunting")),
    (
        "Romance_Dark_Romance",
        (
            "romance",
            "love stories",
            "new adult",
            "contemporary women",
            "billionaire",
            "sports romance",
            "dark romance",
            "erotic",
        ),
    ),
    (
        "Mystery_Thriller_Crime",
        (
            "thriller",
            "suspense",
            "mystery",
            "detective",
            "crime",
            "murder",
            "police",
            "legal stories",
            "psychological fiction",
            "serial killer",
        ),
    ),
    (
        "Fantasy_Science_Fiction",
        (
            "science fiction",
            "fantasy",
            "dystopian",
            "space",
            "robots",
            "magic",
            "dragon",
            "paranormal",
            "adventure stories",
        ),
    ),
    ("Historical_Fiction", ("historical fiction", "war stories", "history fiction", "world war", "frontier")),
    ("Classics", ("classic", "classics", "literary classics")),
    (
        "Nonfiction_History_Politics",
        (
            "history",
            "politics",
            "political science",
            "current events",
            "social science",
            "war",
            "military",
            "palestine",
            "civil rights",
            "government",
        ),
    ),
    ("Biography_Memoir", ("biography", "autobiography", "memoir", "personal narratives", "diaries")),
    (
        "Psychology_Self_Help",
        (
            "self-help",
            "psychology",
            "mental health",
            "trauma",
            "study skills",
            "education",
            "learning",
            "health",
            "body, mind",
        ),
    ),
    (
        "Science_Nature_Technology",
        (
            "science",
            "nature",
            "technology",
            "medical",
            "biology",
            "physics",
            "environment",
            "natural history",
        ),
    ),
    ("Business_Economics", ("business", "economics", "finance", "management", "leadership")),
    ("Poetry_Essays", ("poetry", "essays", "literary collections", "literary criticism")),
    (
        "Literary_General_Fiction",
        (
            "fiction",
            "literary",
            "domestic fiction",
            "family life",
            "american fiction",
            "psychological",
            "women",
        ),
    ),
)


@dataclass
class BookMetadata:
    query_title: str
    query_author: str
    matched_title: str = ""
    matched_authors: str = ""
    subjects: list[str] | None = None
    source: str = "local"


@dataclass
class MoveRecord:
    source: str
    destination: str
    root: str
    category: str
    query_title: str
    query_author: str
    matched_title: str
    matched_authors: str
    metadata_source: str
    status: str


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = html.unescape(text)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"[^0-9a-zA-Z가-힣 ]+", " ", text)
    text = re.sub(r"\b(the|a|an|by|and)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def strip_version_prefix(stem: str) -> str:
    text = unicodedata.normalize("NFC", stem)
    text = re.sub(r"^\s*\[k-e\]\s*", "", text, flags=re.I)
    text = re.sub(r"^\s*\[k\]\s*", "", text, flags=re.I)
    text = re.sub(r"^\s*\[e\]\s*", "", text, flags=re.I)
    return text.strip()


def clean_filename_text(text: str) -> str:
    text = html.unescape(text)
    replacements = {
        "_39_": "'",
        "_39": "'",
        "___40_": "(",
        "__40_": "(",
        "_40_": "(",
        "___41_": ")",
        "__41_": ")",
        "_41_": ")",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[_]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -_")


def clean_filename_component(text: str) -> str:
    text = clean_filename_text(strip_version_prefix(text))
    text = re.sub(r"\breadrobe\s*(?:\.|\s)\s*com\b", " ", text, flags=re.I)
    text = re.sub(r"\bepub\b", " ", text, flags=re.I)
    text = re.sub(r"\bmy fiction books\b", " ", text, flags=re.I)
    text = re.sub(r"\bz library\b.*$", " ", text, flags=re.I)
    text = re.sub(r"\b1lib\b.*$", " ", text, flags=re.I)
    text = re.sub(r"[\[\](){}<>「」『』《》〈〉]", " ", text)
    text = re.sub(r"[_\\/:*?\"|.,;!@#$%^&+=~`’'“”‘，。·ㆍ]+", " ", text)
    text = re.sub(r"[-–—]+", " ", text)
    text = "".join(ch if (ch.isspace() or unicodedata.category(ch)[0] in {"L", "N"}) else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def remove_author_from_title(title: str, author: str) -> str:
    title = clean_filename_component(title)
    author = clean_filename_component(author)
    if not title or not author:
        return title
    title_norm = normalize_for_match(title)
    author_norm = normalize_for_match(author)
    if not author_norm:
        return title
    if title_norm.endswith(author_norm):
        words = author.split()
        if words:
            title = re.sub(r"\s+" + r"\s+".join(re.escape(word) for word in words) + r"$", "", title, flags=re.I).strip()
    title = re.sub(r"\bby\s+" + re.escape(author) + r"$", "", title, flags=re.I).strip()
    title = re.sub(r"\bby$", "", title, flags=re.I).strip()
    return title or clean_filename_component(title)


def series_stem(stem: str) -> str:
    cleaned = clean_filename_component(stem)
    haystack = normalize_for_match(cleaned)

    def has(*needles: str) -> bool:
        return any(normalize_for_match(needle) in haystack for needle in needles)

    manual_english_titles = (
        ("The Teacher Freida McFadden", ("더 티처", "the teacher freida mcfadden")),
        ("The Divorce Freida McFadden", ("이혼 freida mcfadden", "the divorce freida mcfadden")),
        ("The Inmate Freida McFadden", ("인메이트", "the inmate freida mcfadden")),
        ("The Intruder Freida McFadden", ("침입자", "the intruder freida mcfadden")),
        ("Never Lie Freida McFadden", ("절대 거짓말", "never lie freida mcfadden")),
        ("Bits And Pieces Whoopi Goldberg", ("비츠 앤 피시스", "bits and pieces whoopi goldberg")),
        ("The Light We Carry Michelle Obama", ("우리가 지닌 빛", "the light we carry michelle obama")),
        ("The Martian Andy Weir", ("마션", "the martian andy weir")),
        ("Artemis Andy Weir", ("아르테미스", "artemis andy weir")),
        ("The Firm John Grisham", ("펌 john grisham", "the firm john grisham")),
        ("The Girl on the Train Paula Hawkins", ("걸 온 더 트레인", "girl on the train paula hawkins")),
        ("An Unfinished Love Story Doris Kearns Goodwin", ("끝나지 않은 사랑 이야기", "unfinished love story doris kearns goodwin")),
        ("No Going Back Kristi Noem", ("돌아갈 수 없다", "no going back kristi noem")),
        ("The End of Everything Victor Davis Hanson", ("모든 것의 끝", "end of everything victor davis hanson")),
        ("The Demon of Unrest Erik Larson", ("불안의 악마", "demon of unrest erik larson")),
        ("The Wager David Grann", ("웨이저", "the wager david grann")),
        ("The Hundred Years War on Palestine Rashid Khalidi", ("팔레스타인 100년 전쟁", "hundred years war on palestine rashid khalidi")),
        ("Make It Stick Peter C Brown Henry L Roediger III Mark A McDaniel", ("메이크 잇 스틱", "make it stick")),
        ("The Body Keeps the Score Bessel van der Kolk MD", ("몸은 기억한다", "body keeps the score bessel")),
        ("The Anxious Generation Jonathan Haidt", ("불안 세대", "anxious generation jonathan haidt")),
        ("Shadows of Fury R NIMES", ("분노의 그림자", "shadows of fury")),
        ("Wicked Sanctuary Jane Henry", ("위키드 생추어리", "wicked sanctuary jane henry")),
        ("Vicious Reign Monica Kayne", ("잔혹한 지배", "vicious reign monica kayne")),
        ("The Backyard Bird Chronicles Amy Tan", ("뒤뜰 새 연대기", "backyard bird chronicles amy tan")),
        ("Outlive Peter Attia MD", ("아웃라이브", "outlive peter attia")),
        ("Love Mom Nicole Saphier M D", ("러브 맘", "love mom nicole saphier")),
        ("You Never Know Tom Selleck", ("유 네버 노우", "you never know tom selleck")),
        ("Coming Home Brittney Griner", ("커밍 홈", "coming home brittney griner")),
        ("Thirteen Reasons Why Jay Asher", ("루머의 루머의 루머", "thirteen reasons why jay asher")),
        ("1984 George Orwell", ("1984년 조지 오웰", "1984 george orwell")),
        ("Zorba the Greek Nikos Kazantzakis", ("그리스인 조르바", "zorba the greek")),
        ("Demian Hermann Hesse", ("데미안 헤르만 헤세", "demian hermann hesse")),
        ("The Stranger Albert Camus", ("이방인 알베르 카뮈", "stranger albert camus")),
        ("The War of the Worlds H G Wells", ("허버트웰즈 우주전쟁", "war of the worlds")),
        ("Land Pak Kyongni", ("토지 박경리", "박경리 대하소설", "land pak kyongni")),
        ("The Alchemist Paulo Coelho", ("연금술사", "alchemist paulo coelho")),
        ("Eleven Minutes Paulo Coelho", ("11분", "eleven minutes paulo coelho")),
        ("The Pilgrimage Paulo Coelho", ("파울로 코엘료 환상", "pilgrimage paulo coelho")),
        ("Perfume The Story of a Murderer Patrick Suskind", ("향수 어느 살인자의 이야기", "perfume story of a murderer")),
        ("A History of the World in 10 1 2 Chapters Julian Barnes", ("1 2장으로 쓴 세계 역사", "history of the world in 10 1 2 chapters")),
        ("Lectures My Reading of the Eastern Classics Shin Young Bok", ("강의 신영복", "나의 동양고전 독법")),
    )
    for target, aliases in manual_english_titles:
        if any(has(alias) for alias in aliases):
            return clean_filename_component(target)

    kay_scarpetta = (
        ("01", "Postmortem", ("postmortem", "포스트모템")),
        ("02", "Body Of Evidence", ("body of evidence", "바디 오브 에비던스")),
        ("03", "All That Remains", ("all that remains", "올 댓 리메인스")),
        ("04", "Cruel and Unusual", ("cruel and unusual", "잔혹하고 이례적인")),
        ("05", "The Body Farm", ("body farm",)),
        ("06", "From Potter s Field", ("potter",)),
        ("07", "Cause Of Death", ("cause of death",)),
        ("08", "Unnatural Exposure", ("unnatural exposure",)),
        ("09", "Point of Origin", ("point of origin",)),
    )
    if has("kay scarpetta", "scarpetta") or any(has(*aliases) for _, _, aliases in kay_scarpetta):
        for number, title, aliases in kay_scarpetta:
            if has(*aliases) or re.search(rf"\b{number}\b", haystack):
                return clean_filename_component(f"Kay Scarpetta {number} {title} Patricia Cornwell")

    housemaid = (
        ("02", "The Housemaids Secret", ("secret", "비밀")),
        ("03", "The Housemaid Is Watching", ("watching", "지켜보고")),
        ("01", "The Housemaid", ("the housemaid", "하우스메이드")),
    )
    if has("housemaid", "하우스메이드"):
        for number, title, aliases in housemaid:
            if has(*aliases) or re.search(rf"\b{number}\b", haystack):
                return clean_filename_component(f"Housemaid {number} {title} Freida McFadden")

    you_series = (
        ("00", "Complete Series", ("complete series", "완전판")),
        ("04", "For You And Only You", ("for you and only you", "포 유 앤드 온리 유")),
        ("03", "You Love Me", ("you love me", "유 러브 미")),
        ("02", "Hidden Bodies", ("hidden bodies", "히든 바디스")),
        ("01", "You", ("you caroline", "유 caroline")),
    )
    if has("caroline kepnes") or any(has(*aliases) for _, _, aliases in you_series):
        for number, title, aliases in you_series:
            if has(*aliases):
                return clean_filename_component(f"You Series {number} {title} Caroline Kepnes")

    robot_series = (
        ("00", "The Complete Robot", ("complete robot", "완전한 로봇")),
        ("01", "I Robot", ("i robot", "아이 로봇")),
        ("02", "The Rest of the Robots", ("rest of the robots", "나머지 로봇")),
        ("03", "Robot Dreams", ("robot dreams", "로봇 드림")),
        ("04", "Robot Visions", ("robot visions", "로봇 비전")),
        ("05", "The Positronic Man", ("positronic", "포지트로닉")),
        ("06", "The Caves of Steel", ("caves of steel", "강철 동굴")),
        ("07", "The Naked Sun", ("naked sun", "벌거벗은 태양")),
        ("08", "The Robots of Dawn", ("robots of dawn", "새벽의 로봇")),
    )
    if has("isaac asimov", "asimov", "robot series") or any(has(*aliases) for _, _, aliases in robot_series):
        for number, title, aliases in robot_series:
            if has(*aliases):
                return clean_filename_component(f"Robot Series {number} {title} Isaac Asimov")

    the_code = (
        ("01", "Vested Interest", ("vested interest",)),
        ("02", "Hidden Agenda", ("hidden agenda",)),
        ("03", "Broken Process", ("broken process",)),
    )
    if has("the code", "bethany jadin") or any(has(*aliases) for _, _, aliases in the_code):
        for number, title, aliases in the_code:
            if has(*aliases):
                return clean_filename_component(f"The Code {number} {title} Bethany Jadin")

    obedience = (
        ("01", "Obedience", ("obedience", "오비디언스")),
        ("02", "Obedience Volume 2", ("volume 2", "오비디언스 2")),
    )
    if has("obedience", "오비디언스"):
        for number, title, aliases in reversed(obedience):
            if has(*aliases):
                return clean_filename_component(f"Obedience {number} {title} Lizzie B Brown")

    kingdom = (
        ("01", "Poison", ("poison",)),
        ("02", "Charm", ("charm",)),
        ("03", "Beauty", ("beauty",)),
    )
    if has("sarah pinborough") or any(has(*aliases) for _, _, aliases in kingdom):
        for number, title, aliases in kingdom:
            if has(*aliases):
                return clean_filename_component(f"Tales from the Kingdoms {number} {title} Sarah Pinborough")
        if has("mayhem"):
            return clean_filename_component("Mayhem 01 Mayhem Sarah Pinborough")
        if has("death house"):
            return clean_filename_component("The Death House Sarah Pinborough")
        if has("cross her heart"):
            return clean_filename_component("Cross Her Heart Sarah Pinborough")

    if has("off campus", "the deal", "elle kennedy", "elle kenedy"):
        if has("the deal"):
            return clean_filename_component("Off Campus 01 The Deal Elle Kennedy")

    if has("vampire sorority sisters", "better off red"):
        return clean_filename_component("Vampire Sorority Sisters 01 Better Off Red Rebekah Weatherspoon")

    return cleaned


def author_looks_like_translator(author: str) -> bool:
    lowered = normalize_for_match(author)
    return any(marker in lowered for marker in ("옮김", "번역", "역자", "translated", "translator"))


def split_title_author_text(text: str) -> tuple[str, str] | None:
    text = clean_filename_text(strip_version_prefix(text))
    by_match = re.match(r"^(?P<title>.+?)\s+by\s+(?P<author>.+)$", text, flags=re.I)
    if by_match:
        return clean_filename_text(by_match.group("title")), clean_filename_text(by_match.group("author"))
    dash_match = re.match(r"^(?P<title>.+?)\s+-\s+(?P<author>.+)$", text)
    if dash_match:
        return clean_filename_text(dash_match.group("title")), clean_filename_text(dash_match.group("author"))
    return None


def normalized_output_name(root: Path, metadata: BookMetadata, path: Path) -> str:
    prefix = "[k-e]" if root == KE_ROOT else "[k]"
    title = metadata.query_title or metadata.matched_title or strip_version_prefix(path.stem)
    author = metadata.query_author or metadata.matched_authors
    path_split = split_title_author_text(strip_version_prefix(path.stem))
    title_split = split_title_author_text(title)
    if (not author or author_looks_like_translator(author)) and path_split:
        title, author = path_split
    elif not author and title_split:
        title, author = title_split
    title = remove_author_from_title(title, author)
    author = clean_filename_component(author)
    stem = f"{title} {author}".strip() if author else title
    stem = clean_filename_component(stem)
    stem = series_stem(stem)
    if not stem:
        stem = clean_filename_component(strip_version_prefix(path.stem)) or "Unknown"
    return f"{prefix} {stem}.epub"


def author_folder_for(metadata: BookMetadata, path: Path, filename: str) -> str:
    texts = [
        metadata.query_title,
        metadata.query_author,
        metadata.matched_title,
        metadata.matched_authors,
        strip_version_prefix(path.stem),
        filename,
    ]
    texts.extend(path.parts[-4:])
    combined = normalize_for_match(" ".join(texts))
    for author, aliases in AUTHOR_FOLDER_ALIASES:
        if any(normalize_for_match(alias) in combined for alias in aliases):
            return author
    return ""


def is_must_read(metadata: BookMetadata, path: Path, filename: str) -> bool:
    texts = [
        metadata.query_title,
        metadata.query_author,
        metadata.matched_title,
        metadata.matched_authors,
        strip_version_prefix(path.stem),
        filename,
    ]
    texts.extend(path.parts[-5:])
    combined = normalize_for_match(" ".join(texts))
    return any(normalize_for_match(alias) in combined for alias in MUST_READ_ALIASES)


def category_from_relative(relative: Path) -> str:
    for part in relative.parts[:-1]:
        if part in CATEGORY_DIRS:
            return part
    return ""


def read_epub_metadata(path: Path) -> tuple[str, str, list[str]]:
    try:
        with zipfile.ZipFile(path) as archive:
            container = safe_fromstring(archive.read("META-INF/container.xml"))
            ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
            rootfile = container.find(".//c:rootfile", ns)
            if rootfile is None:
                return "", "", []
            opf_path = rootfile.attrib.get("full-path", "")
            root = safe_fromstring(archive.read(opf_path))
    except Exception:
        return "", "", []
    title = first_text(root, "{http://purl.org/dc/elements/1.1/}title")
    creator = first_text(root, "{http://purl.org/dc/elements/1.1/}creator")
    subjects = [clean_filename_text(el.text or "") for el in root.findall(".//{http://purl.org/dc/elements/1.1/}subject")]
    return title, creator, [subject for subject in subjects if subject]


def first_text(root: ET.Element, tag: str) -> str:
    for el in root.findall(f".//{tag}"):
        if el.text and el.text.strip():
            return clean_filename_text(el.text.strip())
    return ""


def infer_query_from_path(path: Path) -> tuple[str, str, list[str]]:
    meta_title, meta_author, meta_subjects = read_epub_metadata(path)
    stem = clean_filename_text(strip_version_prefix(path.stem))
    title = clean_filename_text(meta_title or stem)
    author = clean_filename_text(meta_author)
    stem_split = split_title_author_text(stem)
    title_split = split_title_author_text(title)
    if (not author or author_looks_like_translator(author)) and stem_split:
        title, author = stem_split
    elif not author and title_split:
        title, author = title_split
    if author:
        title_norm = normalize_for_match(title)
        author_norm = normalize_for_match(author)
        if author_norm and title_norm.endswith(author_norm):
            title = re.sub(re.escape(author), "", title, flags=re.I).strip(" -_") or title
    if not author:
        fallback_split = split_title_author_text(stem)
        if fallback_split:
            title, author = fallback_split
    title = re.sub(r"^\s*\d{1,3}\s+", "", title).strip()
    title = re.sub(r"^\s*\d{1,3}[._ -]+", "", title).strip()
    return title or stem, author, meta_subjects


def score_title(query_title: str, candidate_title: str) -> float:
    query = normalize_for_match(query_title)
    candidate = normalize_for_match(candidate_title)
    if not query or not candidate:
        return 0.0
    if query == candidate:
        return 1.0
    if query in candidate or candidate in query:
        shorter = min(len(query), len(candidate))
        longer = max(len(query), len(candidate))
        return 0.82 + 0.18 * (shorter / max(longer, 1))
    return SequenceMatcher(None, query, candidate).ratio()


def score_author(query_author: str, candidate_authors: list[str]) -> float:
    query = normalize_for_match(query_author)
    if not query:
        return 0.2
    return max((SequenceMatcher(None, query, normalize_for_match(author)).ratio() for author in candidate_authors), default=0.0)


def request_json(url: str, params: dict[str, str], timeout: float = 8.0) -> dict[str, Any] | None:
    full_url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except (OSError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def open_library_metadata(title: str, author: str) -> BookMetadata | None:
    params = {
        "title": title,
        "limit": "8",
        "fields": "title,author_name,subject,first_publish_year",
    }
    if author:
        params["author"] = author
    data = request_json("https://openlibrary.org/search.json", params)
    best: tuple[float, dict[str, Any]] | None = None
    for doc in (data or {}).get("docs", []) or []:
        candidate_title = doc.get("title", "") or ""
        candidate_authors = doc.get("author_name", []) or []
        score = score_title(title, candidate_title) * 0.78 + score_author(author, candidate_authors) * 0.22
        if best is None or score > best[0]:
            best = (score, doc)
    if not best or best[0] < 0.55:
        return None
    doc = best[1]
    return BookMetadata(
        query_title=title,
        query_author=author,
        matched_title=doc.get("title", "") or "",
        matched_authors=", ".join(doc.get("author_name", []) or []),
        subjects=[str(subject) for subject in (doc.get("subject", []) or [])[:40]],
        source="Open Library",
    )


def google_books_metadata(title: str, author: str) -> BookMetadata | None:
    queries = []
    if author:
        queries.append(f'intitle:"{title}" inauthor:"{author}"')
    queries.append(f'intitle:"{title}"')
    queries.append(title)
    best: tuple[float, dict[str, Any]] | None = None
    for query in queries:
        data = request_json(
            "https://www.googleapis.com/books/v1/volumes",
            {
                "q": query,
                "maxResults": "5",
                "printType": "books",
                "fields": "items(volumeInfo/title,volumeInfo/authors,volumeInfo/categories,volumeInfo/description)",
            },
        )
        for item in (data or {}).get("items", []) or []:
            info = item.get("volumeInfo", {}) or {}
            candidate_title = info.get("title", "") or ""
            candidate_authors = info.get("authors", []) or []
            score = score_title(title, candidate_title) * 0.78 + score_author(author, candidate_authors) * 0.22
            if best is None or score > best[0]:
                best = (score, info)
        if best and best[0] >= 0.78:
            break
        time.sleep(0.15)
    if not best or best[0] < 0.55:
        return None
    info = best[1]
    subjects = [str(category) for category in (info.get("categories", []) or [])]
    description = info.get("description", "")
    if description:
        subjects.append(str(description)[:600])
    return BookMetadata(
        query_title=title,
        query_author=author,
        matched_title=info.get("title", "") or "",
        matched_authors=", ".join(info.get("authors", []) or []),
        subjects=subjects,
        source="Google Books",
    )


def cache_path() -> Path:
    return CLASSIFICATION_DIR / "category_cache.json"


def load_cache() -> dict[str, Any]:
    path = cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict[str, Any]) -> None:
    CLASSIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    cache_path().write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def book_key(path: Path) -> str:
    return normalize_for_match(strip_version_prefix(path.stem))


def lookup_metadata(title: str, author: str, local_subjects: list[str], key: str, cache: dict[str, Any], offline: bool) -> BookMetadata:
    cached = cache.get(key)
    if cached:
        return BookMetadata(**cached["metadata"])
    metadata = BookMetadata(query_title=title, query_author=author, subjects=local_subjects, source="local")
    if not offline:
        for lookup in (open_library_metadata, google_books_metadata):
            found = lookup(title, author)
            if found:
                found.subjects = (local_subjects or []) + (found.subjects or [])
                metadata = found
                break
            time.sleep(0.2)
    return metadata


def classify(metadata: BookMetadata, path: Path) -> str:
    texts = [metadata.query_title, metadata.query_author, metadata.matched_title, metadata.matched_authors, path.stem]
    texts.extend(metadata.subjects or [])
    combined = normalize_for_match(" ".join(texts))
    for needle, category in MANUAL_CATEGORY_HINTS:
        if normalize_for_match(needle) in combined:
            return category
    scores: dict[str, int] = {}
    for category, needles in CATEGORY_RULES:
        score = 0
        for needle in needles:
            if normalize_for_match(needle) in combined:
                score += 1
        if score:
            scores[category] = score
    if scores:
        return max(scores.items(), key=lambda item: (item[1], -list(dict(CATEGORY_RULES)).index(item[0])))[0]
    return "Uncategorized"


def root_for_path(path: Path) -> Path | None:
    try:
        path.relative_to(K_ROOT)
        return K_ROOT
    except ValueError:
        pass
    try:
        path.relative_to(KE_ROOT)
        return KE_ROOT
    except ValueError:
        return None


def iter_default_files(recursive: bool = False) -> list[Path]:
    files: list[Path] = []
    for root in (K_ROOT, KE_ROOT):
        if root.exists():
            pattern = "**/*.epub" if recursive else "*.epub"
            files.extend(sorted(path for path in root.glob(pattern) if path.is_file()))
    return files


def unique_destination(destination: Path, source: Path) -> Path:
    if not destination.exists():
        return destination
    if destination.stat().st_size == source.stat().st_size:
        return destination
    for index in range(2, 10001):
        candidate = destination.with_name(f"{destination.stem} {index}{destination.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find unique destination for {destination}")


def classify_paths(
    paths: list[Path],
    offline: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
    recursive: bool = False,
) -> list[MoveRecord]:
    CLASSIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    records: list[MoveRecord] = []
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".epub":
            continue
        root = root_for_path(path)
        if root is None:
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        scrub_epub(path)
        if len(relative.parts) != 1 and not recursive:
            continue
        title, author, local_subjects = infer_query_from_path(path)
        key = book_key(path)
        metadata = lookup_metadata(title, author, local_subjects, key, cache, offline)
        existing_category = category_from_relative(relative)
        if recursive and existing_category:
            category = existing_category
        else:
            category = classify(metadata, path)
        if category not in CATEGORY_DIRS:
            category = "Uncategorized"
        cache[key] = {"metadata": asdict(metadata), "category": category, "updated_at": datetime.now().isoformat(timespec="seconds")}
        output_name = normalized_output_name(root, metadata, path)
        author_folder = author_folder_for(metadata, path, output_name)
        if is_must_read(metadata, path, output_name):
            destination_dir = root / "#must read"
        elif author_folder == "Freida McFadden":
            destination_dir = root / "#Freida McFadden"
        else:
            destination_dir = root / category
        if author_folder and not destination_dir.name.startswith("#"):
            destination_dir = destination_dir / author_folder
        destination = unique_destination(destination_dir / output_name, path)
        if path == destination:
            continue
        status = "dry-run"
        if not dry_run:
            destination_dir.mkdir(parents=True, exist_ok=True)
            if destination.exists() and destination.stat().st_size == path.stat().st_size:
                path.unlink()
                status = "removed-duplicate"
            else:
                shutil.move(str(path), str(destination))
                status = "moved"
        record = MoveRecord(
            source=str(path),
            destination=str(destination),
            root=str(root),
            category=category,
            query_title=metadata.query_title,
            query_author=metadata.query_author,
            matched_title=metadata.matched_title,
            matched_authors=metadata.matched_authors,
            metadata_source=metadata.source,
            status=status,
        )
        records.append(record)
        if not quiet:
            print(f"{status}: {path.name} -> {root.name}/{category} ({metadata.source})", flush=True)
    if not dry_run:
        save_cache(cache)
    write_report(records)
    return records


def write_report(records: list[MoveRecord]) -> None:
    if not records:
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = CLASSIFICATION_DIR / f"category_move_report_{stamp}.json"
    csv_path = CLASSIFICATION_DIR / f"category_move_report_{stamp}.csv"
    json_path.write_text(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(records[0]).keys()))
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify [k] and [k-e] EPUB files into separate category subfolders.")
    parser.add_argument("--files", nargs="*", type=Path, default=[], help="Specific EPUB files to classify.")
    parser.add_argument("--offline", action="store_true", help="Use only cached/local metadata and filename rules.")
    parser.add_argument("--recursive", action="store_true", help="Also reclassify EPUBs already inside category subfolders.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = args.files or iter_default_files(recursive=args.recursive)
    records = classify_paths(paths, offline=args.offline, dry_run=args.dry_run, quiet=args.quiet, recursive=args.recursive)
    summary: dict[str, int] = {}
    for record in records:
        label = f"{Path(record.root).name}/{record.category}"
        summary[label] = summary.get(label, 0) + 1
    print(json.dumps({"processed": len(records), "summary": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
