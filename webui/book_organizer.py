#!/usr/bin/env python3
"""
번역된 EPUB 파일을 장르와 작가에 따라 자동으로 분류하여 저장하는 모듈.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree as ET


# /Users/<user>/Desktop/소설2 에 실제로 존재하는 장르 폴더명과 맞춘 분류 체계.
# (예전에는 한글 장르명("로맨스", "판타지" 등)을 썼지만, 실제 서재 폴더 구조는
# 영문 스네이크케이스 이름을 쓰고 있어 자동 분류 결과와 실제 폴더가 어긋났었다.)
CATEGORY_DIRS = (
    "Mystery_Thriller_Crime",
    "Dark_Romance",
    "Romance",
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
)

# 장르 자동 분류를 거치지 않고 항상 "#작가명" 최상위 큐레이션 폴더로 보내는 작가들
# (예: #Pam Godwin, #Freida McFadden과 같은 방식). normalize_book_author()로 정규화한
# 값을 키로 쓴다.
CURATED_AUTHOR_FOLDERS: dict[str, str] = {
    "leigh rivers": "#Leigh Rivers",
}

# Open Library/Google Books 조회가 실패하거나(신간이라 subject가 비어있음) 429 등으로
# 막혔을 때도 곧장 정확한 장르로 보내기 위한 수동 큐레이션 표. `normalize_book_title(title)
# + "|" + normalize_book_author(author)`를 키로 쓰며(카테고리 캐시와 같은 형식),
# `guess_genre_online()`에서 네트워크 조회보다 먼저 확인한다. 2026-08-14 서재 감사에서
# Uncategorized에 쌓여 있던 책들을 정리하며 채운 항목들 — 대부분 출간된 지 얼마 안 돼
# Open Library에 subject 태그가 아직 없거나(신간), 이번 세션에서 Google Books API
# 요청이 429(Too Many Requests)로 막혀 있던 경우다.
CURATED_GENRE_BY_TITLE: dict[str, str] = {
    "a forsaken prophecy|mcewan stacey": "Fantasy_Science_Fiction",
    "cool machine|colson whitehead": "Literary_General_Fiction",
    "private rites|armfield julia": "Horror_Dark_Fiction",
    "ride steady|ashley kristen": "Romance",
    "sunrise on the reaping|collins suzanne": "Young_Adult_Children",
    "the silent patient by alex michaelides noble publishing|noble publishing": "Mystery_Thriller_Crime",
    "the big short inside the doomsday machine|lewis michael": "Business_Economics",
    "the book of days|francesca kay": "Literary_General_Fiction",
    "the book of lost hours|gelfuso hayley": "Fantasy_Science_Fiction",
    "the break up pact|emma lord": "Romance",
    "the cipher|isabella maldonado": "Mystery_Thriller_Crime",
    "the complete witcher|andrzej sapkowski": "Fantasy_Science_Fiction",
    "the compound|aisling rawle": "Literary_General_Fiction",
    "the dream hotel|laila lalami": "Literary_General_Fiction",
    "the heart in winter|barry kevin": "Historical_Fiction",
    "the housewife|barelli natalie": "Mystery_Thriller_Crime",
    "the perfect divorce|jeneva rose": "Mystery_Thriller_Crime",
    "the poppy fields|erlick nikki": "Literary_General_Fiction",
    "the river she became|emily varga": "Fantasy_Science_Fiction",
    "the shampoo effect|jackson jenny": "Literary_General_Fiction",
    "the shock of the fall|filer nathan": "Literary_General_Fiction",
    "the silence|daisy pearce": "Mystery_Thriller_Crime",
    "the sirens|emilia hart": "Historical_Fiction",
    "the wedding people|alison espach": "Literary_General_Fiction",
    "the wide wide sea|hampton sides": "Nonfiction_History_Politics",
    "this changes everything capitalism vs the climate|klein naomi": "Nonfiction_History_Politics",
    "to explain the world the discovery of modern science|steven weinberg": "Science_Nature_Technology",
    "troublemaker surviving hollywood and scientology|leah remini": "Biography_Memoir",
    "we love you bunny|awad mona": "Horror_Dark_Fiction",
    "what lies between us|john marrs": "Mystery_Thriller_Crime",
    "when the moon hits your eye|john scalzi": "Fantasy_Science_Fiction",
    "the mistake|elle kennedy": "Romance",
    "the complete foundation trilogy|asimov isaac": "Fantasy_Science_Fiction",
    "the long game|rachel reid": "Romance",
    "the rebel witch|ciccarelli kristen": "Fantasy_Science_Fiction",
    "mad mabel|hepworth sally": "Mystery_Thriller_Crime",
    "wind and truth|brandon sanderson": "Fantasy_Science_Fiction",
    "the lord of the rings|jrr tolkien": "Fantasy_Science_Fiction",
    "whistler|ann patchett": "Literary_General_Fiction",
    "would like to meet|rachel winters": "Romance",
    "the impossible fortune|osman richard": "Mystery_Thriller_Crime",
    "the man who died twice|osman richard": "Mystery_Thriller_Crime",
    "when to rob a bank and 131 more warped suggestions and well intended rants|d levitt steven": "Business_Economics",
    "the safekeep|der van wouden yael": "Historical_Fiction",
    "divine rivals|rebecca ross": "Romance_Contemporary",
    "ruthless vows|rebecca ross": "Romance_Contemporary",
    "the five star weekend|elin hilderbrand": "Romance_Contemporary",
    "the five-star weekend|elin hilderbrand": "Romance_Contemporary",
    "five star summer|ella monroe": "Romance_Contemporary",
    "godel escher bach an eternal golden braid|douglas r hofstadter": "Science_Nature_Technology",
    "the selfish gene|richard dawkins": "Science_Nature_Technology",
}

# 키워드는 순서대로 검사하며 먼저 매칭되는 장르를 사용한다.
CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Young_Adult_Children", ("young adult", "teen novel", "children's", "middle grade")),
    ("Horror_Dark_Fiction", ("horror", "ghost story", "gothic", "occult", "haunting", "vampire")),
    (
        "Dark_Romance",
        (
            "dark romance",
            "erotic",
            "billionaire",
            "reverse harem",
            "mafia romance",
            "bully romance",
            "monster romance",
            "dubious consent",
        ),
    ),
    # 평범한 로맨스("romance"/"love story" 같은 일반 표현만 걸리는 경우)는 서재의 별도
    # "Romance" 폴더(다크 로맨스가 아닌 일반/컨템포러리 로맨스)로 보낸다. 예전에는 이 둘을
    # 구분하지 않고 "romance"라는 단어만 있으면 무조건 Dark_Romance로 보냈는데, 그
    # 결과 Abby Jimenez/Colleen Hoover처럼 실제로는 Romance 폴더에 맞는 작가들이 다크 로맨스
    # 폴더로 잘못 옮겨지는 문제가 있었다(2026-08-06 서재 감사에서 발견).
    ("Romance", ("romance", "love story", "romantic comedy", "chick lit")),
    (
        "Mystery_Thriller_Crime",
        ("thriller", "suspense", "mystery", "detective", "crime", "murder", "serial killer", "whodunit"),
    ),
    (
        "Fantasy_Science_Fiction",
        (
            "science fiction",
            "sci-fi",
            "fantasy",
            "dystopian",
            "space opera",
            "robot",
            "magic",
            "dragon",
            "paranormal",
        ),
    ),
    ("Historical_Fiction", ("historical fiction", "war stor", "frontier")),
    ("Classics", ("classic",)),
    (
        "Nonfiction_History_Politics",
        ("history", "politic", "government", "war of", "revolution", "military", "warfare"),
    ),
    ("Biography_Memoir", ("biography", "autobiography", "memoir", "diaries", "diary of")),
    ("Psychology_Self_Help", ("self-help", "self help", "psychology", "mental health", "trauma")),
    ("Science_Nature_Technology", ("nature", "technology", "biology", "physics", "science of")),
    ("Business_Economics", ("business", "economics", "finance", "management", "leadership")),
    ("Poetry_Essays", ("poetry", "poems", "essays", "essay collection")),
    (
        "Literary_General_Fiction",
        (
            "literary fiction",
            "domestic fiction",
            "psychological fiction",
            "women fiction",
            "family life",
            "a novel",
            "fiction",
        ),
    ),
)

# Open Library/Google Books subject 목록으로 채점할 때는 제외하는, 너무 흔해서 신호가 안 되는
# 키워드("fiction" 한 단어는 거의 모든 소설의 subject에 들어있어 특정 장르를 가리키지 못한다).
# 반대로 제목만 보고 추측하는 guess_genre_from_title()의 최후 수단으로는 여전히 유효하므로
# CATEGORY_KEYWORDS 자체에서는 빼지 않고, subject 채점 단계에서만 걸러낸다.
_SUBJECT_SCORING_EXCLUDED_KEYWORDS = frozenset({"fiction", "a novel"})

DEFAULT_GENRE = "Literary_General_Fiction"

# Goodreads에는 공개 API가 없고(2020년 종료) 스크레이핑은 이용 약관에 어긋나므로,
# 같은 목적(장르/서가 분류)을 위해 Open Library와 Google Books의 공개 subject/category
# 메타데이터를 대신 사용한다. classify_soseol2_epubs_by_category.py와 같은 방식이다.
_USER_AGENT = "AudiobookStudioGenreClassifier/1.0"


def _request_json(url: str, params: dict[str, str], timeout: float = 8.0) -> dict | None:
    full_url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(full_url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except (OSError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None


def _open_library_subjects(title: str, author: str) -> list[str] | None:
    params = {"title": title, "limit": "5", "fields": "title,author_name,subject"}
    if author and author.lower() != "unknown author":
        params["author"] = author
    data = _request_json("https://openlibrary.org/search.json", params)
    for doc in (data or {}).get("docs", []) or []:
        subjects = doc.get("subject") or []
        if subjects:
            return [str(subject) for subject in subjects[:40]]
    return None


def _google_books_subjects(title: str, author: str) -> list[str] | None:
    query = f'intitle:"{title}"'
    if author and author.lower() != "unknown author":
        query += f' inauthor:"{author}"'
    data = _request_json(
        "https://www.googleapis.com/books/v1/volumes",
        {"q": query, "maxResults": "5", "printType": "books", "fields": "items(volumeInfo/categories)"},
    )
    for item in (data or {}).get("items", []) or []:
        categories = (item.get("volumeInfo") or {}).get("categories") or []
        if categories:
            return [str(category) for category in categories]
    return None


def _category_cache_path() -> Path:
    return Path.home() / "Desktop" / "소설2" / "_classification" / "category_cache.json"


def _load_category_cache() -> dict[str, str]:
    path = _category_cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_category_cache(cache: dict[str, str]) -> None:
    path = _category_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def classify_genre_subjects(subjects: list[str]) -> str | None:
    """
    Open Library/Google Books에서 받은 subject/category 목록으로 장르를 채점해서 고른다.

    책 한 권의 subject는 보통 5~40개나 되고, 여러 장르 키워드가 동시에 걸리는 경우가 흔하다
    (예: "Between the World and Me"는 "BIOGRAPHY & AUTOBIOGRAPHY / Personal Memoirs"와
    "HISTORY / United States / General"이 같이 나온다). 예전에는 CATEGORY_KEYWORDS 순서상
    먼저 검사되는 장르가 무조건 이겼는데, 그러면 실제로는 근거가 더 약한 장르가 우연히 먼저
    걸려서 이기는 경우가 생긴다. 이제는 subject 전체에서 각 장르가 몇 번이나 근거를 얻는지
    세어 가장 근거가 많은 장르를 고르고, 동점이면 예전과 같은 우선순위로 정한다.

    "FICTION / Mystery & Detective / General"처럼 "/"로 구분된 서점 매대 분류(BISAC) 형태의
    subject는 자유 텍스트 태그보다 훨씬 신뢰도가 높은 신호이므로 가중치를 3배 준다.
    """
    if not subjects:
        return None

    scores: dict[str, float] = {}
    for subject in subjects:
        lowered = subject.lower()
        weight = 3.0 if "/" in subject else 1.0
        for genre, keywords in CATEGORY_KEYWORDS:
            for keyword in keywords:
                if keyword in _SUBJECT_SCORING_EXCLUDED_KEYWORDS:
                    continue
                # "Magic realism"은 문예 기법을 가리키는 문학 용어지 판타지 장르가 아니다.
                if keyword == "magic" and "magic realism" in lowered:
                    continue
                if keyword in lowered:
                    scores[genre] = scores.get(genre, 0.0) + weight
                    break  # 같은 subject 문자열이 같은 장르에 중복으로 점수를 주지 않는다.

    if not scores:
        return None

    priority = {genre: index for index, (genre, _keywords) in enumerate(CATEGORY_KEYWORDS)}
    return max(scores, key=lambda genre: (scores[genre], -priority[genre]))


def core_series_search_title(title: str, author: str) -> str | None:
    """
    "Diana Gabaldon - Outlander Series 1-10 Anthology"처럼 여러 권을 하나로 묶은 팬 편집
    합본 파일명은 그 자체로는 실제 서지 항목과 매칭되지 않는다(그런 앤솔로지가 통째로
    Open Library/Google Books에 등록돼 있을 리 없다). 저자명 접두사와 "Series 1-10",
    "Anthology", "Boxed Set" 같은 합본 표시를 제거해 원작 시리즈 이름만 남긴 대체 검색어를
    만든다. 원제와 달라진 게 없으면(정리할 게 없었으면) None을 돌려준다.
    """
    cleaned = title
    author_clean = (author or "").strip()
    if author_clean:
        for sep in (" - ", ": "):
            prefix = f"{author_clean}{sep}"
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):]
                break

    cleaned = re.sub(r"(?i)\bseries\s*\d+\s*[-–]\s*\d+\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\b(anthology|boxed?\s*set|complete\s+series|omnibus|collection)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:")

    if cleaned and cleaned.lower() != title.lower():
        return cleaned
    return None


def guess_genre_online(filename: str, metadata: dict, *, use_network: bool = True) -> str:
    """
    가능하면 Open Library / Google Books의 실제 서지 분류(subject/category)를 이용해 장르를
    추측하고, 조회에 실패하면 제목 키워드 추측으로 대체한다. (Goodreads는 공개 API가 없다.)
    둘 다 조회가 되면 두 출처의 subject를 합쳐서 채점하므로, 한쪽만 봤을 때보다 더 근거가
    풍부한 판단을 할 수 있다.

    원제로 조회해서 아무 subject도 못 찾으면, 팬 편집 합본 표시를 걷어낸 대체 검색어
    (`core_series_search_title`)로 한 번 더 시도한다.
    """
    title = metadata.get("title") or ""
    author = metadata.get("author") or ""
    cache_key = normalize_book_title(title) + "|" + normalize_book_author(author)

    curated = CURATED_GENRE_BY_TITLE.get(cache_key)
    if curated:
        return curated

    if use_network and cache_key.strip("|"):
        cache = _load_category_cache()
        cached = cache.get(cache_key)
        if cached:
            return cached

        search_titles = [title]
        core_title = core_series_search_title(title, author)
        if core_title:
            search_titles.append(core_title)

        for search_title in search_titles:
            combined_subjects: list[str] = []
            for lookup in (_open_library_subjects, _google_books_subjects):
                subjects = lookup(search_title, author)
                if subjects:
                    combined_subjects.extend(subjects)

            if combined_subjects:
                genre = classify_genre_subjects(combined_subjects)
                if genre:
                    cache[cache_key] = genre
                    _save_category_cache(cache)
                    return genre

    return guess_genre_from_title(filename, metadata)


def _rating_cache_path() -> Path:
    return Path.home() / "Desktop" / "소설2" / "_classification" / "rating_cache.json"


def _load_rating_cache() -> dict[str, float | None]:
    path = _rating_cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_rating_cache(cache: dict[str, float | None]) -> None:
    path = _rating_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def _google_books_rating(title: str, author: str) -> float | None:
    query = f'intitle:"{title}"'
    if author and author.lower() != "unknown author":
        query += f' inauthor:"{author}"'
    data = _request_json(
        "https://www.googleapis.com/books/v1/volumes",
        {
            "q": query,
            "maxResults": "5",
            "printType": "books",
            "fields": "items(volumeInfo/averageRating,volumeInfo/ratingsCount)",
        },
    )
    for item in (data or {}).get("items", []) or []:
        info = item.get("volumeInfo") or {}
        rating = info.get("averageRating")
        if isinstance(rating, (int, float)) and (info.get("ratingsCount") or 0) > 0:
            return round(float(rating), 2)
    return None


def guess_average_rating(metadata: dict, *, use_network: bool = True) -> float | None:
    """
    Google Books의 공개 averageRating을 조회해 서재 파일명에 쓰는 "(4.34)" 형식의
    평점을 만든다. 조회에 실패하거나 등록된 평점이 없으면 None(평점 없이 이동).
    """
    title = metadata.get("title") or ""
    author = metadata.get("author") or ""
    if not use_network or not title.strip():
        return None

    cache_key = normalize_book_title(title) + "|" + normalize_book_author(author)
    cache = _load_rating_cache()
    if cache_key in cache:
        return cache[cache_key]

    rating = _google_books_rating(title, author)
    cache[cache_key] = rating
    _save_rating_cache(cache)
    return rating


_METADATA_CACHE: dict[tuple[str, float, int], dict[str, str]] = {}


def extract_metadata_from_epub(epub_path: Path) -> dict[str, str]:
    """
    EPUB 파일에서 메타데이터 추출 (작가, 제목, 언어 등).

    같은 실행 안에서 (경로, mtime, 크기)가 같으면 캐시를 재사용한다. 재분류/레지스트리
    스캔처럼 같은 서재 폴더를 파일 하나하나에 대해 반복해서 훑는 작업(예: 작가가 이미
    다른 장르 폴더에 자리 잡았는지 찾는 `_find_established_genre_folder`)이 서재 전체
    EPUB을 매번 다시 열어 파싱하지 않도록 하기 위함이다 - 파일이 수백 개인 서재에서
    이게 없으면 사실상 O(재분류 대상 수 × 서재 전체 파일 수)로 느려진다.
    """
    try:
        stat_result = epub_path.stat()
        cache_key: tuple[str, float, int] | None = (str(epub_path), stat_result.st_mtime, stat_result.st_size)
    except OSError:
        cache_key = None
    if cache_key is not None and cache_key in _METADATA_CACHE:
        return _METADATA_CACHE[cache_key]

    metadata = {
        "title": "Unknown",
        "author": "Unknown Author",
        "genre": DEFAULT_GENRE,
        "language": "en",
    }

    try:
        with zipfile.ZipFile(epub_path, "r") as zip_file:
            # content.opf 또는 package.opf 찾기
            opf_files = [f for f in zip_file.namelist() if f.endswith(".opf")]
            if not opf_files:
                return metadata
            
            opf_content = zip_file.read(opf_files[0])
            root = ET.fromstring(opf_content)
            
            # 네임스페이스 정의
            namespaces = {
                "dc": "http://purl.org/dc/elements/1.1/",
                "opf": "http://www.idpf.org/2007/opf",
            }
            
            # 제목 추출
            title_elem = root.find(".//dc:title", namespaces)
            if title_elem is not None and title_elem.text:
                metadata["title"] = title_elem.text.strip()
            
            # 작가 추출
            author_elem = root.find(".//dc:creator", namespaces)
            if author_elem is not None and author_elem.text:
                metadata["author"] = author_elem.text.strip()
            
            # 언어 추출
            language_elem = root.find(".//dc:language", namespaces)
            if language_elem is not None and language_elem.text:
                metadata["language"] = language_elem.text.strip()
    
    except Exception as e:
        print(f"Warning: Could not extract metadata from {epub_path.name}: {e}")

    if cache_key is not None:
        _METADATA_CACHE[cache_key] = metadata
    return metadata


def guess_genre_from_title(filename: str, metadata: dict) -> str:
    """파일명과 메타데이터에서 /소설2 실제 폴더명 체계에 맞는 장르 추측"""
    search_text = (filename + " " + metadata.get("title", "")).lower()

    for genre, keywords in CATEGORY_KEYWORDS:
        if any(keyword in search_text for keyword in keywords):
            return genre

    return DEFAULT_GENRE


def sanitize_folder_name(name: str) -> str:
    """폴더명으로 사용 가능하도록 정제"""
    name = unicodedata.normalize("NFKC", name)
    # "/", "\\"는 그냥 지우면 "11/22/63" 같은 제목이 "112263"으로 붙어버리므로 "-"로 치환한다.
    name = re.sub(r"[/\\]+", "-", name)
    name = re.sub(r"[:*?\"<>|]+", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] or "Unknown"


def sanitize_filename_part(name: str) -> str:
    """파일명 구성 요소(제목/작가)로 사용 가능하도록 정제"""
    name = unicodedata.normalize("NFKC", name)
    # "/", "\\"는 그냥 지우면 "11/22/63" 같은 제목이 "112263"으로 붙어버리므로 "-"로 치환한다.
    name = re.sub(r"[/\\]+", "-", name)
    name = re.sub(r"[:*?\"<>|]+", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:160] or "Unknown"


def clean_metadata_field(value: str) -> str:
    """제목/작가 표기에서 부제·에디션 표기·유출 사이트 표식 등 잡음을 제거한다."""
    value = unicodedata.normalize("NFKC", value or "").strip()
    value = re.sub(r"\((?:unabridged|abridged)\)", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*[:\-–—]\s*(?:a novel|a memoir)\s*$", "", value, flags=re.IGNORECASE)
    # 불법 공유/스캔 출처 표식 제거 (예: "@my_fiction_books", "@my fiction books", z-library 등)
    value = re.sub(r"@\s*[\w .-]*(?:fiction[_ ]?books|z[_ -]?library|readrobe)[\w .-]*", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bmy[_ ]fiction[_ ]books\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bz[_ -]?library\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\breadrobe(?:\.com)?\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"@\S+", " ", value)
    # 밑줄은 원래 공백이었던 경우가 대부분이라 공백으로 치환한다.
    value = value.replace("_", " ")
    value = re.sub(r"\s+", " ", value).strip(" -_")
    return value


def build_organized_filename(prefix: str, metadata: dict, *, rating: float | None = None) -> str:
    """정리된 파일명을 만든다: "[prefix] 작품명 작가명 (평점).epub" (그 밖의 표식 제거)"""
    title = sanitize_filename_part(clean_metadata_field(metadata.get("title") or "Unknown"))
    author = sanitize_filename_part(clean_metadata_field(metadata.get("author") or "Unknown Author"))
    stem = sanitize_filename_part(f"{prefix} {title} {author}")
    if rating is not None:
        stem = f"{stem} ({rating:.2f})"
    return f"{stem}.epub"


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 2
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        counter += 1
    return candidate


def _existing_author_epubs(genre_folder: Path, author_key: str) -> list[Path]:
    """genre_folder 바로 아래(하위폴더 제외)에 있는, 같은 작가의 기존 EPUB 파일들."""
    if not author_key or not genre_folder.exists():
        return []
    matches = []
    for child in sorted(genre_folder.glob("*.epub")):
        try:
            meta = extract_metadata_from_epub(child)
        except Exception:
            continue
        if normalize_book_author(meta.get("author", "")) == author_key:
            matches.append(child)
    return matches


def _existing_author_folder(genre_folder: Path, author_key: str) -> Path | None:
    if not author_key or not genre_folder.exists():
        return None
    for child in genre_folder.iterdir():
        if child.is_dir() and normalize_book_author(child.name) == author_key:
            return child
    return None


def _find_established_genre_folder(target_root: Path, author_key: str) -> Path | None:
    """
    같은 작가의 책이 이미 어느 장르 폴더에 자리 잡고 있다면 그 장르 폴더를 반환한다.
    (예: Elle Kennedy가 이미 Dark_Romance에 있다면, 장르 키워드 추측이 빗나가더라도
    새 작품을 항상 그 폴더로 보낸다.)
    """
    if not author_key or not target_root.exists():
        return None
    # "#"로 시작하는 폴더(#must read 등)는 장르 폴더가 아니라 별도 큐레이션 폴더이므로 제외한다.
    # Uncategorized도 제외한다 - 그건 실제 장르가 아니라 "분류 실패" 임시 보관함이므로, 같은
    # 작가의 책 2권 이상이 우연히 거기 함께 떨어졌다고 해서 앞으로도 계속 거기로 보내면 안 된다
    # (분류를 다시 시도할 방법이 없어져 영영 미분류로 남는다).
    genre_dirs = [
        child
        for child in target_root.iterdir()
        if child.is_dir() and not child.name.startswith("#") and child.name != DEFAULT_GENRE
    ]
    for genre_dir in genre_dirs:
        if _existing_author_folder(genre_dir, author_key) is not None:
            return genre_dir
    for genre_dir in genre_dirs:
        if _existing_author_epubs(genre_dir, author_key):
            return genre_dir
    return None


def organize_single_epub(
    epub_path: Path,
    target_root: Path,
    *,
    use_network: bool = True,
    mode: str = "move",
    force_genre: str | None = None,
) -> bool:
    """
    단일 EPUB 파일을 장르/작가 폴더로 분류하여 서재에 반영하고 파일명을 정리한다.

    같은 작가의 작품이 이미 2편 이상이면(또는 이번 이동으로 2편이 되면) 장르 폴더
    아래 작가명 하위 폴더에 모으고, 1편뿐이면 작가 폴더 없이 장르 폴더에 바로 둔다.

    mode="move"면 원본을 서재로 옮기고, mode="copy"면 원본은 그대로 두고 서재에 사본을
    만든다(작업 상세 화면의 다운로드 링크가 계속 살아있어야 하는 자동화 파이프라인용).
    force_genre를 주면 자동 추측 대신 그 장르로 강제 분류한다(수동 재검토용).
    """
    filename = epub_path.name
    lowered = filename.lower()
    if lowered.startswith("[k-e]"):
        prefix = "[k-e]"
    elif lowered.startswith("[k]"):
        prefix = "[k]"
    elif lowered.startswith("[e]"):
        prefix = "[e]"
    elif lowered.startswith("[study]"):
        prefix = "[study]"
    elif lowered.startswith("[e-s]"):
        prefix = "[e-s]"
    else:
        return False

    try:
        metadata = extract_metadata_from_epub(epub_path)
        author = clean_metadata_field(metadata.get("author") or "Unknown Author")
        author_key = normalize_book_author(author)
        unknown_key = normalize_book_author("Unknown Author")

        curated_folder_name = CURATED_AUTHOR_FOLDERS.get(author_key)

        if curated_folder_name is not None:
            destination_folder = target_root / curated_folder_name
            destination_folder.mkdir(parents=True, exist_ok=True)
            genre_folder = destination_folder
            existing_folder = destination_folder
        elif force_genre:
            genre_folder = target_root / sanitize_folder_name(force_genre)
        else:
            genre_folder = _find_established_genre_folder(target_root, author_key) if author_key != unknown_key else None
            if genre_folder is None:
                genre = guess_genre_online(filename, metadata, use_network=use_network)
                genre_folder = target_root / sanitize_folder_name(genre)

        if curated_folder_name is None:
            genre_folder.mkdir(parents=True, exist_ok=True)
            existing_folder = _existing_author_folder(genre_folder, author_key) if author_key != unknown_key else None

        if existing_folder is not None:
            destination_folder = existing_folder
        else:
            all_matches = _existing_author_epubs(genre_folder, author_key) if author_key != unknown_key else []
            # genre_folder가 epub_path가 지금 있는 폴더와 같을 수 있다(재분류 시나리오) -
            # 그러면 이 스캔이 처리 중인 파일 자기 자신을 "기존 동일 작가 작품"으로 잘못
            # 집어내 자기 자신을 작가 폴더로 옮겨버릴 수 있으므로 제외한다.
            siblings = [sibling for sibling in all_matches if sibling != epub_path]
            if siblings:
                # 두 번째 작품이 들어오는 시점 -> 작가 하위 폴더를 새로 만들고 기존 파일도 옮긴다.
                destination_folder = genre_folder / sanitize_folder_name(author)
                destination_folder.mkdir(parents=True, exist_ok=True)
                for sibling in siblings:
                    shutil.move(str(sibling), str(_unique_destination(destination_folder / sibling.name)))
            else:
                destination_folder = genre_folder

        if destination_folder == epub_path.parent:
            # 다시 분류를 시도했지만 결국 지금 있는 폴더로 되돌아온 경우(예: 여전히
            # Uncategorized) - 자기 자신 위로 옮기면 _unique_destination이 그걸 "이미
            # 존재"로 보고 "(2)" 붙은 중복 파일을 만들어버리므로 아무 것도 하지 않는다.
            return False

        rating = guess_average_rating(metadata, use_network=use_network)
        new_name = build_organized_filename(prefix, metadata, rating=rating)
        destination_path = _unique_destination(destination_folder / new_name)
        if mode == "copy":
            shutil.copy2(str(epub_path), str(destination_path))
        else:
            shutil.move(str(epub_path), str(destination_path))
        return True

    except Exception as e:
        print(f"Warning: Failed to organize {filename}: {e}")
        return False


def organize_from_output_dir(
    output_dir: Path,
    korean_root: Path,
    bilingual_root: Path,
    *,
    english_root: Path | None = None,
    study_root: Path | None = None,
    english_study_root: Path | None = None,
    use_network: bool = True,
    mode: str = "move",
) -> int:
    """
    output 폴더에서 EPUB 파일들을 찾아 장르/작가/평점에 따라 분류한다.

    단일 번역 작업은 output_dir 바로 아래에 "[k] ...epub"을 두고, 폴더 일괄 번역
    (또는 "new books from vk" 같은 대량 스테이징 폴더)은 output_dir/[k], output_dir/[k-e],
    output_dir/[e], output_dir/[study], output_dir/[e-s] 하위 폴더에 결과물을 나눠 둔다. 두
    레이아웃을 모두 찾는다. english_root/study_root/english_study_root를 생략하면 해당
    버전의 파일은 건드리지 않는다(예: 아직 그 버전을 만들지 않는 예전 파이프라인 호출부와의
    호환).

    Returns:
        서재에 반영된 파일 수
    """

    if not output_dir.exists():
        return 0

    prefix_targets: list[tuple[str, Path]] = [("[k-e]", bilingual_root), ("[k]", korean_root)]
    if english_root is not None:
        prefix_targets.append(("[e]", english_root))
    if study_root is not None:
        prefix_targets.append(("[study]", study_root))
    if english_study_root is not None:
        prefix_targets.append(("[e-s]", english_study_root))

    for _, target_root in prefix_targets:
        target_root.mkdir(parents=True, exist_ok=True)

    valid_prefixes = tuple(prefix for prefix, _ in prefix_targets)
    search_roots = [output_dir] + [output_dir / prefix for prefix, _ in prefix_targets]
    seen: set[str] = set()
    epub_files: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.epub")):
            if not path.name.lower().startswith(valid_prefixes):
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            epub_files.append(path)

    moved_count = 0
    for epub_path in epub_files:
        name_lower = epub_path.name.lower()
        target_root = next(root for prefix, root in prefix_targets if name_lower.startswith(prefix))
        if organize_single_epub(epub_path, target_root, use_network=use_network, mode=mode):
            moved_count += 1

    return moved_count


def reclassify_uncategorized(library_root: Path, *, use_network: bool = True, mode: str = "move") -> int:
    """
    library_root/Uncategorized(그 아래 예전에 생겼던 작가별 하위 폴더 포함)에 있는 EPUB들을
    다시 장르 분류한다. Open Library/Google Books 조회가 그때는 실패했거나(예: API 일일 쿼터
    초과) 제목 키워드로도 못 맞혀서 Uncategorized에 남아있는 책들을, 나중에 다시 온라인 조회를
    시도해 제대로 된 장르 폴더로 옮기기 위한 것이다. `organize_single_epub()`을 그대로
    재사용하므로, 이미 정리된 다른 책들과 같은 규칙(작가별 하위 폴더 자동 생성, 평점 추가)이
    똑같이 적용된다.

    Returns:
        새 장르 폴더로 옮겨진 파일 수 (Open Library/Google Books가 여전히 장르를 찾지
        못해 Uncategorized에 그대로 남은 책은 세지 않는다)
    """
    uncategorized_dir = library_root / DEFAULT_GENRE
    if not uncategorized_dir.exists():
        return 0

    moved_count = 0
    for epub_path in sorted(uncategorized_dir.rglob("*.epub")):
        if organize_single_epub(epub_path, library_root, use_network=use_network, mode=mode):
            moved_count += 1

    for child in sorted(uncategorized_dir.iterdir()):
        if child.is_dir() and not any(child.iterdir()):
            child.rmdir()

    return moved_count


def audit_author_genre_placements(library_root: Path, *, use_network: bool = True) -> list[dict[str, object]]:
    """
    서재의 작가별 하위 폴더들이 지금 다시 조회하면 나올 장르와 실제로 자리 잡은 장르 폴더가
    서로 어긋나 있지는 않은지 점검한다. 자동으로 옮기지는 않고, 의심되는 항목만 목록으로
    돌려준다(장르가 겹치는 작가도 있어서 오탐 가능성이 있으므로 사람이 검토 후 처리한다).

    `organize_single_epub()`의 `_find_established_genre_folder()`는 "같은 작가의 책이
    이미 한 장르 폴더에 있으면 새 책도 그 폴더로 보낸다"는 규칙을 쓰는데, 이건 그 작가의
    첫 배치가 애초에 잘못 분류돼 있었을 경우 그 실수를 다시 조회도 안 해보고 영구히 그대로
    이어가게 만든다(예: Paula Hawkins가 한 번 Historical_Fiction에 잘못 들어가면, 그 뒤로
    들어오는 모든 Paula Hawkins 책이 계속 그 폴더로 간다 - 2026-08-06에 실제로 발견된 사례).
    각 작가 폴더에서 대표로 한 권만 뽑아 `guess_genre_online()`으로 다시 조회하므로, 작가당
    조회 1회로 비용을 억제한다.

    Returns:
        [{"author": 폴더명, "current_folder": 지금 폴더, "suggested_folder": 다시 조회한
          장르, "representative_book": 대표로 조회에 쓴 파일 경로}, ...]
    """
    findings: list[dict[str, object]] = []
    if not library_root.exists():
        return findings

    for genre_dir in sorted(library_root.iterdir()):
        if not genre_dir.is_dir() or genre_dir.name.startswith("#") or genre_dir.name == DEFAULT_GENRE:
            continue
        for author_dir in sorted(genre_dir.iterdir()):
            if not author_dir.is_dir():
                continue
            representative = next(iter(sorted(author_dir.glob("*.epub"))), None)
            if representative is None:
                continue
            metadata = extract_metadata_from_epub(representative)
            suggested = guess_genre_online(representative.name, metadata, use_network=use_network)
            if suggested and suggested != DEFAULT_GENRE and suggested != genre_dir.name:
                findings.append(
                    {
                        "author": author_dir.name,
                        "current_folder": genre_dir.name,
                        "suggested_folder": suggested,
                        "representative_book": representative,
                    }
                )

    return findings


def get_existing_korean_books(korean_root: Path) -> set[str]:
    """
    이미 존재하는 한글 번역본 파일명 목록 반환.
    원본 파일명을 기준으로 중복 체크를 위해 사용.
    
    Args:
        korean_root: 한글 번역본 루트 폴더 ([k])
    
    Returns:
        {원본_파일명, ...} 집합
    """
    
    if not korean_root.exists():
        return set()
    
    existing_books = set()
    
    # [k] 폴더의 모든 EPUB 파일 찾기
    for epub_path in korean_root.rglob("*.epub"):
        filename = epub_path.name
        # [k] 접두사 제거해서 원본 파일명 복원
        if filename.startswith("[k] "):
            original_name = filename[4:]  # "[k] " 제거
            existing_books.add(original_name)

    return existing_books


NOISE_TITLE_PHRASES = (
    "unabridged",
    "a novel",
    "the complete series",
    "complete series",
    "special edition",
    "book club edition",
    "anniversary edition",
    "boxed set",
    "collection",
    "novel",
)

FINISHED_TITLE_MATCH_THRESHOLD = 0.92


def normalize_book_title(value: str) -> str:
    """제목 대조용 정규화: 괄호 속 부제/에디션 표기, 구두점, 대소문자 차이를 제거한다."""
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = value.lower()
    for phrase in NOISE_TITLE_PHRASES:
        value = value.replace(phrase, " ")
    value = re.sub(r"[^a-z0-9가-힣]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_book_author(value: str) -> str:
    """
    작가명 대조용 정규화: "성, 이름" / "이름 성" 표기 차이를 흡수한다.
    단어 단위로 쪼개 정렬하므로 "Godwin, Pam"과 "Pam Godwin"이 같은 값으로 정규화된다.
    """
    raw = unicodedata.normalize("NFKC", value or "")
    parts = re.split(r"\s*(?:,|&|\band\b)\s*", raw, flags=re.IGNORECASE)
    words: list[str] = []
    for part in parts:
        if part.strip():
            words.extend(normalize_book_title(part).split())
    return " ".join(sorted(words))


def build_finished_registry(finished_dir: Path) -> list[dict[str, object]]:
    """finished 폴더(번역이 이미 끝난 원서 모음)에서 제목/작가 대조 목록을 만든다."""
    registry: list[dict[str, object]] = []
    if not finished_dir.exists():
        return registry
    for epub_path in sorted(finished_dir.glob("*.epub")):
        metadata = extract_metadata_from_epub(epub_path)
        registry.append(
            {
                "path": epub_path,
                "title": metadata["title"],
                "author": metadata["author"],
                "norm_title": normalize_book_title(metadata["title"]),
                "norm_author": normalize_book_author(metadata["author"]),
            }
        )
    return registry


def build_library_registry(library_root: Path) -> list[dict[str, object]]:
    """
    [k] 서재 폴더(장르/작가 하위 폴더 포함) 전체를 실시간으로 훑어 제목/작가 대조 목록을
    만든다. `k_collection_blog.html` 같은 정적 스냅샷은 그 이후에 서재로 새로 옮겨진 책을
    반영하지 못해 중복 번역을 놓칠 수 있으므로, 배치 시작 시점의 실제 폴더 상태를 직접
    스캔해 항상 최신 상태로 중복을 잡아낸다.
    """
    registry: list[dict[str, object]] = []
    if not library_root.exists():
        return registry
    for epub_path in sorted(library_root.rglob("*.epub")):
        try:
            metadata = extract_metadata_from_epub(epub_path)
        except Exception:
            continue
        registry.append(
            {
                "path": epub_path,
                "title": metadata["title"],
                "author": metadata["author"],
                "norm_title": normalize_book_title(metadata["title"]),
                "norm_author": normalize_book_author(metadata["author"]),
            }
        )
    return registry


def build_html_collection_registry(html_path: Path) -> list[dict[str, object]]:
    """
    [k] 컬렉션 안내 페이지(k_collection_blog.html)에 내장된 booksData JS 배열에서
    제목/작가 대조 목록을 만든다. 이 페이지는 [k] 폴더 전체를 요약한 정적 카탈로그이므로,
    실제 epub 파일을 일일이 열어보지 않고도 이미 번역된 작품 목록을 빠르게 대조할 수 있다.
    """
    registry: list[dict[str, object]] = []
    if not html_path.exists():
        return registry
    try:
        text = html_path.read_text(encoding="utf-8")
    except OSError:
        return registry

    match = re.search(r"const\s+booksData\s*=\s*(\[.*?\])\s*;", text, re.DOTALL)
    if not match:
        return registry
    try:
        books = json.loads(match.group(1))
    except (ValueError, json.JSONDecodeError):
        return registry

    for book in books:
        title = str(book.get("title") or "")
        author = str(book.get("author") or "")
        rel_path = book.get("rel_path")
        registry.append(
            {
                "path": Path(rel_path) if rel_path else html_path,
                "title": title,
                "author": author,
                "norm_title": normalize_book_title(title),
                "norm_author": normalize_book_author(author),
            }
        )
    return registry


def find_finished_match(
    title: str,
    author: str,
    registry: list[dict[str, object]],
) -> dict[str, object] | None:
    """제목/작가가 finished 목록의 항목과 같은 작품인지 판단한다."""
    norm_title = normalize_book_title(title)
    norm_author = normalize_book_author(author)
    if not norm_title or norm_title == "unknown":
        return None

    best: dict[str, object] | None = None
    best_ratio = 0.0
    for entry in registry:
        entry_title = str(entry["norm_title"])
        if not entry_title:
            continue
        ratio = SequenceMatcher(None, norm_title, entry_title).ratio()
        if ratio < FINISHED_TITLE_MATCH_THRESHOLD:
            continue
        entry_author = str(entry["norm_author"])
        author_known = (
            bool(norm_author)
            and norm_author != "unknown author"
            and bool(entry_author)
            and entry_author != "unknown author"
        )
        if author_known:
            author_ratio = SequenceMatcher(None, norm_author, entry_author).ratio()
            if author_ratio < 0.6:
                continue
        if ratio > best_ratio:
            best_ratio = ratio
            best = entry
    return best


def archive_duplicate_source(source: Path, finished_dir: Path) -> Path:
    """이미 번역이 끝난 것으로 확인된 원본 EPUB을 finished 폴더로 옮긴다."""
    finished_dir.mkdir(parents=True, exist_ok=True)
    target_path = finished_dir / source.name
    if target_path.exists():
        stem, suffix = target_path.stem, target_path.suffix
        counter = 2
        while target_path.exists():
            target_path = finished_dir / f"{stem} ({counter}){suffix}"
            counter += 1
    shutil.move(str(source), str(target_path))
    return target_path

