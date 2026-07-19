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
)

# 키워드는 순서대로 검사하며 먼저 매칭되는 장르를 사용한다.
CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Young_Adult_Children", ("young adult", "teen novel", "children's", "middle grade")),
    ("Horror_Dark_Fiction", ("horror", "ghost story", "gothic", "occult", "haunting", "vampire")),
    ("Romance_Dark_Romance", ("romance", "love story", "billionaire", "dark romance", "erotic")),
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
    ("Nonfiction_History_Politics", ("history", "politic", "government", "war of", "revolution")),
    ("Biography_Memoir", ("biography", "autobiography", "memoir", "diaries", "diary of")),
    ("Psychology_Self_Help", ("self-help", "self help", "psychology", "mental health", "trauma")),
    ("Science_Nature_Technology", ("nature", "technology", "biology", "physics", "science of")),
    ("Business_Economics", ("business", "economics", "finance", "management", "leadership")),
    ("Poetry_Essays", ("poetry", "poems", "essays", "essay collection")),
    (
        "Literary_General_Fiction",
        ("literary fiction", "domestic fiction", "psychological fiction", "women fiction", "a novel", "fiction"),
    ),
)

DEFAULT_GENRE = "Uncategorized"

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


def classify_genre_text(text: str) -> str | None:
    lowered = text.lower()
    for genre, keywords in CATEGORY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return genre
    return None


def guess_genre_online(filename: str, metadata: dict, *, use_network: bool = True) -> str:
    """
    가능하면 Open Library / Google Books의 실제 서지 분류(subject/category)를 이용해 장르를
    추측하고, 조회에 실패하면 제목 키워드 추측으로 대체한다. (Goodreads는 공개 API가 없다.)
    """
    title = metadata.get("title") or ""
    author = metadata.get("author") or ""
    cache_key = normalize_book_title(title) + "|" + normalize_book_author(author)

    if use_network and cache_key.strip("|"):
        cache = _load_category_cache()
        cached = cache.get(cache_key)
        if cached:
            return cached
        for lookup in (_open_library_subjects, _google_books_subjects):
            subjects = lookup(title, author)
            if subjects:
                genre = classify_genre_text(" ".join(subjects))
                if genre:
                    cache[cache_key] = genre
                    _save_category_cache(cache)
                    return genre

    return guess_genre_from_title(filename, metadata)


def extract_metadata_from_epub(epub_path: Path) -> dict[str, str]:
    """EPUB 파일에서 메타데이터 추출 (작가, 제목, 언어 등)"""
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


def build_organized_filename(prefix: str, metadata: dict) -> str:
    """정리된 파일명을 만든다: "[prefix] 작품명 작가명.epub" (그 밖의 표식 제거)"""
    title = sanitize_filename_part(clean_metadata_field(metadata.get("title") or "Unknown"))
    author = sanitize_filename_part(clean_metadata_field(metadata.get("author") or "Unknown Author"))
    stem = sanitize_filename_part(f"{prefix} {title} {author}")
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
    (예: Elle Kennedy가 이미 Romance_Dark_Romance에 있다면, 장르 키워드 추측이 빗나가더라도
    새 작품을 항상 그 폴더로 보낸다.)
    """
    if not author_key or not target_root.exists():
        return None
    # "#"로 시작하는 폴더(#must read 등)는 장르 폴더가 아니라 별도 큐레이션 폴더이므로 제외한다.
    genre_dirs = [child for child in target_root.iterdir() if child.is_dir() and not child.name.startswith("#")]
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
    if filename.lower().startswith("[k-e]"):
        prefix = "[k-e]"
    elif filename.lower().startswith("[k]"):
        prefix = "[k]"
    else:
        return False

    try:
        metadata = extract_metadata_from_epub(epub_path)
        author = clean_metadata_field(metadata.get("author") or "Unknown Author")
        author_key = normalize_book_author(author)
        unknown_key = normalize_book_author("Unknown Author")

        if force_genre:
            genre_folder = target_root / sanitize_folder_name(force_genre)
        else:
            genre_folder = _find_established_genre_folder(target_root, author_key) if author_key != unknown_key else None
            if genre_folder is None:
                genre = guess_genre_online(filename, metadata, use_network=use_network)
                genre_folder = target_root / sanitize_folder_name(genre)
        genre_folder.mkdir(parents=True, exist_ok=True)

        existing_folder = _existing_author_folder(genre_folder, author_key) if author_key != unknown_key else None
        if existing_folder is not None:
            destination_folder = existing_folder
        else:
            siblings = _existing_author_epubs(genre_folder, author_key) if author_key != unknown_key else []
            if siblings:
                # 두 번째 작품이 들어오는 시점 -> 작가 하위 폴더를 새로 만들고 기존 파일도 옮긴다.
                destination_folder = genre_folder / sanitize_folder_name(author)
                destination_folder.mkdir(parents=True, exist_ok=True)
                for sibling in siblings:
                    shutil.move(str(sibling), str(_unique_destination(destination_folder / sibling.name)))
            else:
                destination_folder = genre_folder

        new_name = build_organized_filename(prefix, metadata)
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
    use_network: bool = True,
    mode: str = "move",
) -> int:
    """
    output 폴더(단일 번역 작업의 결과물 폴더 또는 폴더 일괄 번역의 [k]/[k-e] 하위 폴더)에서
    EPUB 파일들을 찾아 분류.

    Returns:
        서재에 반영된 파일 수
    """

    if not output_dir.exists():
        return 0

    for folder in (korean_root, bilingual_root):
        folder.mkdir(parents=True, exist_ok=True)

    # 단일 번역 작업은 output_dir 바로 아래에 "[k] ...epub"을 두고, 폴더 일괄 번역은
    # output_dir/[k], output_dir/[k-e] 하위 폴더에 결과물을 나눠 둔다. 두 레이아웃을 모두 찾는다.
    search_roots = [output_dir, output_dir / "[k]", output_dir / "[k-e]"]
    seen: set[str] = set()
    epub_files: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.epub")):
            name_lower = path.name.lower()
            if not (name_lower.startswith("[k-e]") or name_lower.startswith("[k]")):
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            epub_files.append(path)

    moved_count = 0
    for epub_path in epub_files:
        target_root = bilingual_root if epub_path.name.lower().startswith("[k-e]") else korean_root
        if organize_single_epub(epub_path, target_root, use_network=use_network, mode=mode):
            moved_count += 1

    return moved_count


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

