#!/usr/bin/env python3
"""
번역된 EPUB 파일을 장르와 작가에 따라 자동으로 분류하여 저장하는 스크립트.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# 설정
FINISHED_FOLDER = Path("/Users/hyeokjunkong/Desktop/소설2/finished")
KOREAN_FOLDER = Path("/Users/hyeokjunkong/Desktop/소설2/[k]")
BILINGUAL_FOLDER = Path("/Users/hyeokjunkong/Desktop/소설2/[k-e]")

# 기본 장르 매핑 (파일명 기반)
GENRE_KEYWORDS = {
    "romance": "로맨스",
    "love": "로맨스",
    "fantasy": "판타지",
    "magic": "판타지",
    "dragon": "판타지",
    "mystery": "미스터리",
    "thriller": "미스터리/스릴러",
    "crime": "미스터리/스릴러",
    "detective": "미스터리",
    "horror": "공포/스릴러",
    "dark": "공포/스릴러",
    "science": "SF/과학소설",
    "sci-fi": "SF/과학소설",
    "future": "SF/과학소설",
    "historical": "역사소설",
    "history": "역사소설",
    "war": "역사소설",
    "adventure": "모험소설",
    "action": "모험소설",
    "literary": "문학",
    "fiction": "일반소설",
    "poetry": "시/에세이",
    "essay": "시/에세이",
    "self-help": "자기계발",
    "business": "경영/비즈니스",
    "psychology": "심리학",
    "learning": "교육/학습",
}

DEFAULT_GENRE = "기타"


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
    """파일명과 메타데이터에서 장르 추측"""
    search_text = (filename + " " + metadata.get("title", "")).lower()

    for keyword, genre in GENRE_KEYWORDS.items():
        if keyword in search_text:
            return genre

    return DEFAULT_GENRE


def sanitize_folder_name(name: str) -> str:
    """폴더명으로 사용 가능하도록 정제"""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[/\\:*?\"<>|]+", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] or "Unknown"


def organize_books() -> None:
    """번역된 책들을 장르와 작가별로 분류"""

    if not FINISHED_FOLDER.exists():
        print(f"❌ Error: {FINISHED_FOLDER} 폴더가 없습니다.")
        return

    # 대상 폴더 생성
    for folder in [KOREAN_FOLDER, BILINGUAL_FOLDER]:
        folder.mkdir(parents=True, exist_ok=True)

    # finished 폴더의 EPUB 파일 찾기
    epub_files = list(FINISHED_FOLDER.glob("*.epub"))

    if not epub_files:
        print(f"⚠️  {FINISHED_FOLDER}에 EPUB 파일이 없습니다.")
        return

    print(f"📚 {len(epub_files)}개 파일 정렬 중...\n")

    korean_moved = 0
    bilingual_moved = 0
    errors = []

    for epub_path in epub_files:
        try:
            filename = epub_path.name

            # 한글 버전인지 한영 버전인지 판단
            is_korean_only = filename.startswith("[k] ")
            is_bilingual = filename.startswith("[k-e] ")

            if not (is_korean_only or is_bilingual):
                continue

            # 메타데이터 추출
            metadata = extract_metadata_from_epub(epub_path)

            # 장르 결정
            genre = guess_genre_from_title(filename, metadata)

            # 작가명 정제
            author = sanitize_folder_name(metadata["author"])
            genre_folder = sanitize_folder_name(genre)

            # 대상 폴더 결정
            if is_korean_only:
                target_root = KOREAN_FOLDER
                moved_count_var = "korean_moved"
            else:
                target_root = BILINGUAL_FOLDER
                moved_count_var = "bilingual_moved"

            # 폴더 구조 생성: [k 또는 k-e]/장르/작가/
            target_folder = target_root / genre_folder / author
            target_folder.mkdir(parents=True, exist_ok=True)

            # 파일 이동
            target_path = target_folder / filename
            shutil.move(str(epub_path), str(target_path))

            if is_korean_only:
                korean_moved += 1
            else:
                bilingual_moved += 1

            print(f"✅ {filename}")
            print(f"   → {genre_folder}/{author}/")
            print()

        except Exception as e:
            errors.append((filename, str(e)))
            print(f"❌ {filename}: {e}\n")

    # 결과 출력
    print("\n" + "="*60)
    print("📊 정렬 완료")
    print("="*60)
    print(f"✅ 한글 버전 이동: {korean_moved}개")
    print(f"✅ 한영 버전 이동: {bilingual_moved}개")

    if errors:
        print(f"\n⚠️  오류 발생: {len(errors)}개")
        for filename, error in errors:
            print(f"  - {filename}: {error}")

    print(f"\n📁 한글 버전: {KOREAN_FOLDER}")
    print(f"📁 한영 버전: {BILINGUAL_FOLDER}")


if __name__ == "__main__":
    organize_books()
