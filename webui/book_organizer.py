#!/usr/bin/env python3
"""
번역된 EPUB 파일을 장르와 작가에 따라 자동으로 분류하여 저장하는 모듈.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


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


def organize_single_epub(
    epub_path: Path,
    korean_root: Path,
    bilingual_root: Path,
) -> bool:
    """단일 EPUB 파일을 분류하여 이동"""
    
    filename = epub_path.name
    
    # 한글 버전인지 한영 버전인지 판단
    is_korean_only = filename.startswith("[k] ")
    is_bilingual = filename.startswith("[k-e] ")
    
    if not (is_korean_only or is_bilingual):
        return False
    
    try:
        # 메타데이터 추출
        metadata = extract_metadata_from_epub(epub_path)
        
        # 장르 결정
        genre = guess_genre_from_title(filename, metadata)
        
        # 작가명 정제
        author = sanitize_folder_name(metadata["author"])
        genre_folder = sanitize_folder_name(genre)
        
        # 대상 폴더 결정
        target_root = korean_root if is_korean_only else bilingual_root
        
        # 폴더 구조 생성: [k 또는 k-e]/장르/작가/
        target_folder = target_root / genre_folder / author
        target_folder.mkdir(parents=True, exist_ok=True)
        
        # 파일 이동
        target_path = target_folder / filename
        shutil.move(str(epub_path), str(target_path))
        
        return True
    
    except Exception as e:
        print(f"Warning: Failed to organize {filename}: {e}")
        return False


def organize_from_output_dir(
    output_dir: Path,
    korean_root: Path,
    bilingual_root: Path,
) -> int:
    """
    output 폴더에서 EPUB 파일들을 찾아서 분류.
    
    Returns:
        이동된 파일 수
    """
    
    if not output_dir.exists():
        return 0
    
    # 대상 폴더 생성
    for folder in [korean_root, bilingual_root]:
        folder.mkdir(parents=True, exist_ok=True)
    
    # EPUB 파일 찾기
    epub_files = list(output_dir.glob("[k]*epub")) + list(output_dir.glob("[k-e]*epub"))
    
    moved_count = 0
    for epub_path in epub_files:
        if organize_single_epub(epub_path, korean_root, bilingual_root):
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

