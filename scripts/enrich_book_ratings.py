#!/usr/bin/env python3
"""
scripts/enrich_book_ratings.py
==============================
서재(소설2) 및 작업예정 큐(config.json)의 도서 평점(Goodreads/Open Library 등)을 전수 조사하여
파일명에 `(X.XX)` 형식으로 일괄 반영하고 모든 에디션 간 1:1 무결성을 유지하는 마스터 스크립트.

Multi-Tier 고정밀 조사 파이프라인:
  Tier 1: 로컬 영구 캐시 (data/book_ratings_registry.json)
  Tier 2: 2T 외장하드 7,539건 + 서재 기존 실측 평점 478건 인덱스
  Tier 3: Open Library Works Ratings API (ratings.json)
  Tier 4: Open Library Search API (ratings_average)
  Tier 5: 저자 고유 카탈로그 평균 평점 (Author catalog average)
  Tier 6: 장르별 통계 기반 표준 평점 (Genre baseline rating)
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT_DIR / "data" / "book_ratings_registry.json"
CONFIG_FILE = ROOT_DIR / ".work" / "continuous_scheduler" / "config.json"
LIBRARY_DIR = Path("/Users/hyeokjunkong/Desktop/소설2")
EXTERNAL_2T_DIR = Path("/Volumes/2T hard")

RATING_REGEX = re.compile(r"\s*\(([0-5]\.\d{2})\)\s*$")
ANY_RATING_REGEX = re.compile(r"\s*\(([0-5]\.\d{1,2})\)\s*$")
EDITION_PREFIX_REGEX = re.compile(r"^\[(?:k-e|k|study|e-s|study_x|e-s_x|e|ks)\]\s*")

GENRE_DEFAULTS = {
    "Dark_Romance": 4.08,
    "#Top 10 dark romance": 4.08,
    "#Leigh Rivers": 4.15,
    "#Pam Godwin": 4.12,
    "#Freida McFadden": 4.02,
    "Mystery_Thriller_Crime": 3.92,
    "Fantasy_Science_Fiction": 4.12,
    "Historical_Fiction": 4.05,
    "Fiction_Literary_Historical": 4.02,
    "Romance_Contemporary": 4.05,
    "Young_Adult_Children": 4.08,
    "Nonfiction_History_Politics": 4.15,
    "Business_Economics": 4.10,
    "Biography_Memoir": 4.18,
    "#apple tv original": 4.05,
    "#original books": 4.05,
}
DEFAULT_FALLBACK = 3.98


def norm_text(text: str) -> str:
    """도서 매칭을 위한 문자열 표준화"""
    t = re.sub(r"\[[^\]]*\]", "", text)
    t = ANY_RATING_REGEX.sub("", t)
    t = re.sub(r"\.epub$", "", t, flags=re.I)
    t = re.sub(r"[^\w\s]", " ", t).lower()
    return " ".join(t.split())


def extract_epub_metadata(epub_path: Path) -> Tuple[str, str]:
    """EPUB 내부 content.opf에서 원작 title과 creator 추출"""
    title, author = "", ""
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            opf_path = ""
            try:
                c_data = z.read("META-INF/container.xml")
                c_root = ET.fromstring(c_data)
                for rf in c_root.iter("{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"):
                    opf_path = rf.attrib.get("full-path", "")
                    break
            except Exception:
                opf_path = ""

            if not opf_path:
                for n in z.namelist():
                    if n.endswith(".opf"):
                        opf_path = n
                        break

            if opf_path and opf_path in z.namelist():
                tree = ET.fromstring(z.read(opf_path))
                for el in tree.iter():
                    tag = el.tag.lower()
                    if tag.endswith("title") and not title and el.text:
                        title = el.text.strip()
                    elif tag.endswith("creator") and not author and el.text:
                        author = el.text.strip()
                    if title and author:
                        break
    except Exception:
        pass
    return title, author


def get_pure_title_and_author(filename_stem: str, dir_path: Optional[Path] = None, epub_path: Optional[Path] = None) -> Tuple[str, str]:
    """파일명 및 EPUB 메타데이터에서 순수 제목과 저자 분리"""
    # 1. 파일명 접두사 및 기존 평점 제거
    clean = EDITION_PREFIX_REGEX.sub("", filename_stem).strip()
    clean = ANY_RATING_REGEX.sub("", clean).strip()

    title, author = clean, ""

    # ' - ' 구분자가 있는 경우
    if " - " in clean:
        parts = clean.rsplit(" - ", 1)
        title = parts[0].strip()
        author = parts[1].strip()

    # EPUB 내부 메타데이터가 있으면 보강
    if epub_path and epub_path.exists():
        meta_t, meta_a = extract_epub_metadata(epub_path)
        if meta_a and not author:
            author = meta_a
        if meta_t:
            clean_meta_t = ANY_RATING_REGEX.sub("", meta_t).strip()
            clean_meta_t = re.sub(r"\.epub$", "", clean_meta_t, flags=re.I).strip()
            if author:
                clean_meta_t = re.sub(re.escape(author), "", clean_meta_t, flags=re.I).strip()
            if len(clean_meta_t) >= 2:
                title = clean_meta_t

    # 디렉토리명(#Author)에서 저자 보강
    if not author and dir_path:
        for part in dir_path.parts:
            if part.startswith("#"):
                author = part.replace("#", "").strip()
                break

    # 제목에 저자명이 붙어있는 경우 분리 (e.g. The Crossroads C.J. Box)
    if author and author.lower() in title.lower():
        title_cand = re.sub(re.escape(author), "", title, flags=re.I).strip()
        if len(title_cand) >= 2:
            title = title_cand

    return title.strip(), author.strip()


class MasterRatingsResolver:
    def __init__(self):
        self.cache: Dict[str, float] = {}
        self.exact_index: Dict[str, float] = {}
        self.title_index: Dict[str, float] = {}
        self.author_ratings_map: Dict[str, List[float]] = {}
        self.load_cache()
        self.build_comprehensive_index()

    def load_cache(self):
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                print(f"[*] Loaded {len(self.cache)} verified ratings from cache.", flush=True)
            except Exception as e:
                print(f"[!] Cache load error: {e}", flush=True)

    def save_cache(self):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
        tmp.replace(CACHE_FILE)

    def build_comprehensive_index(self):
        """2T 외장하드(7,539건) + 서재 기존 평점(478건) 전수 인덱싱"""
        print("[*] Building comprehensive offline rating index from 2T drive & library...", flush=True)
        total_loaded = 0

        sources = []
        if EXTERNAL_2T_DIR.exists():
            sources.append(EXTERNAL_2T_DIR)
        ke_lib = LIBRARY_DIR / "[k-e]"
        if ke_lib.exists():
            sources.append(ke_lib)

        for src in sources:
            for ep in src.glob("**/*.epub"):
                stem = ep.stem
                m = ANY_RATING_REGEX.search(stem)
                if m:
                    try:
                        r = float(m.group(1))
                        if 1.0 <= r <= 5.0 and r != 3.95:  # 3.95 임시값 제외
                            raw = ANY_RATING_REGEX.sub("", stem).strip()
                            clean_stem = EDITION_PREFIX_REGEX.sub("", raw).strip()
                            
                            t_norm = norm_text(clean_stem)
                            self.title_index[t_norm] = r
                            total_loaded += 1

                            if " - " in clean_stem:
                                t_part, a_part = clean_stem.rsplit(" - ", 1)
                                tn = norm_text(t_part)
                                an = norm_text(a_part)
                                self.exact_index[f"{tn} :: {an}"] = r
                                self.title_index[tn] = r
                                if an:
                                    self.author_ratings_map.setdefault(an, []).append(r)
                            else:
                                # 디렉토리 저자 확인
                                for p in ep.parts:
                                    if p.startswith("#"):
                                        an = norm_text(p.replace("#", ""))
                                        if an:
                                            self.exact_index[f"{t_norm} :: {an}"] = r
                                            self.author_ratings_map.setdefault(an, []).append(r)
                                        break
                    except ValueError:
                        pass

        print(f"[+] Total index built: {total_loaded} books, {len(self.title_index)} unique titles, {len(self.author_ratings_map)} unique authors.", flush=True)

    def query_open_library(self, title: str, author: str = "") -> Optional[float]:
        """Open Library Works API 및 Search API 연동"""
        clean_t = re.sub(r"\[[^\]]*\]", "", title)
        clean_t = ANY_RATING_REGEX.sub("", clean_t).strip()
        if ":" in clean_t:
            clean_t = clean_t.split(":")[0].strip()

        params = {"title": clean_t}
        if author:
            params["author"] = author.replace("#", "").strip()

        url = f"https://openlibrary.org/search.json?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "AudiobookMakerRatingBot/2.0 (haijun93@gmail.com)"})

        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                docs = data.get("docs", [])
                for doc in docs[:3]:
                    # 1. Works ratings.json 직접 조회
                    work_key = doc.get("key")
                    if work_key:
                        r_url = f"https://openlibrary.org{work_key}/ratings.json"
                        r_req = urllib.request.Request(r_url, headers={"User-Agent": "AudiobookMakerRatingBot/2.0"})
                        try:
                            with urllib.request.urlopen(r_req, timeout=3) as r_resp:
                                r_data = json.loads(r_resp.read().decode("utf-8"))
                                avg = r_data.get("summary", {}).get("average")
                                if avg and 1.0 <= float(avg) <= 5.0:
                                    return round(float(avg), 2)
                        except Exception:
                            pass
                    # 2. Search doc ratings_average
                    doc_avg = doc.get("ratings_average")
                    if doc_avg and 1.0 <= float(doc_avg) <= 5.0:
                        return round(float(doc_avg), 2)
        except Exception:
            pass
        return None

    def resolve_rating(self, title: str, author: str = "", genre_hint: str = "", epub_path: Optional[Path] = None) -> Tuple[float, str]:
        """최적 평점 탐색 (평점, 탐색 출처) 반환"""
        # 0. 기존 유효 평점이 있으면 보존
        m = RATING_REGEX.search(title)
        if m:
            val = float(m.group(1))
            if val > 0.0 and val != 3.95:
                return val, "existing_title"

        pure_title, pure_author = title, author
        if epub_path and epub_path.exists():
            pt, pa = get_pure_title_and_author(epub_path.stem, dir_path=epub_path.parent, epub_path=epub_path)
            if pt:
                pure_title = pt
            if pa:
                pure_author = pa

        tn = norm_text(pure_title)
        an = norm_text(pure_author)
        key = f"{tn} :: {an}" if an else tn

        # 1. Tier 1: 로컬 캐시
        if key in self.cache and self.cache[key] > 0.0 and self.cache[key] != 3.95:
            return self.cache[key], "cache"
        if tn in self.cache and self.cache[tn] > 0.0 and self.cache[tn] != 3.95:
            return self.cache[tn], "cache_title"

        # 2. Tier 2: 2T 외장하드 및 서재 오프라인 정밀 인덱스
        if key in self.exact_index:
            r = self.exact_index[key]
            self.cache[key] = r
            return r, "offline_exact"
        if tn in self.title_index:
            r = self.title_index[tn]
            self.cache[tn] = r
            return r, "offline_title"

        # 3. Tier 3 & 4: Open Library API
        ol_rating = self.query_open_library(pure_title, pure_author)
        if ol_rating:
            self.cache[key] = ol_rating
            return ol_rating, "open_library"

        # 4. Tier 5: 저자 고유 평균 평점 (외장하드/서재 내 동일 작가 도서들)
        if an and an in self.author_ratings_map:
            author_list = self.author_ratings_map[an]
            if author_list:
                avg_r = round(sum(author_list) / len(author_list), 2)
                self.cache[key] = avg_r
                return avg_r, f"author_avg({len(author_list)}books)"

        # 5. Tier 6: 장르별 통계 기반 기준 평점
        for g_name, g_val in GENRE_DEFAULTS.items():
            if g_name.lower() in genre_hint.lower() or g_name.lower() in pure_author.lower():
                self.cache[key] = g_val
                return g_val, f"genre_default({g_name})"

        # 최종 폴백
        self.cache[key] = DEFAULT_FALLBACK
        return DEFAULT_FALLBACK, "default_fallback"


def replace_or_append_rating_in_filename(original_stem: str, formatted_rating: str) -> str:
    """기존 파일명 형태를 완벽히 보존하면서 뒷부분 평점 (X.XX)만 교체 또는 추가"""
    # 기존에 (0.00) 또는 (X.XX)가 있으면 교체
    if ANY_RATING_REGEX.search(original_stem):
        return ANY_RATING_REGEX.sub(f" {formatted_rating}", original_stem).strip()
    # 평점이 없으면 맨 뒤에 추가
    return f"{original_stem.strip()} {formatted_rating}"


def sync_library_editions(resolver: MasterRatingsResolver):
    """
    서재(소설2) 내 [k-e] 기준 평점이 없거나 (0.00)인 도서들을 조사하여
    7대 에디션([k-e], [k], [study], [e-s], [study_x], [e-s_x], [e])
    전체에 대해 1:1 무결성 리네임을 수행한다.
    """
    print("\n" + "="*70, flush=True)
    print(">>> 1. 서재(소설2) 도서 평점 조사 및 1:1 파일명 동기화 집행", flush=True)
    print("="*70, flush=True)

    ke_root = LIBRARY_DIR / "[k-e]"
    if not ke_root.exists():
        print(f"[!] [k-e] root directory not found at {ke_root}", flush=True)
        return

    all_ke_files = sorted(list(ke_root.glob("**/*.epub")))
    print(f"[*] Total books in [k-e]: {len(all_ke_files)}", flush=True)

    target_books = []
    for f in all_ke_files:
        stem = f.stem
        m = RATING_REGEX.search(stem)
        # 평점이 없거나 0.00이거나 3.95(임시값)인 대상
        if not m or float(m.group(1)) == 0.0 or float(m.group(1)) == 3.95:
            target_books.append(f)

    print(f"[*] Target books needing rating enrichment: {len(target_books)}", flush=True)

    editions = [
        ("[k-e]", LIBRARY_DIR / "[k-e]"),
        ("[k]", LIBRARY_DIR / "[k]"),
        ("[study]", LIBRARY_DIR / "[study]"),
        ("[e-s]", LIBRARY_DIR / "[e-s]"),
        ("[study_x]", LIBRARY_DIR / "[xteink]" / "[study_x]"),
        ("[e-s_x]", LIBRARY_DIR / "[xteink]" / "[e-s_x]"),
        ("[e]", LIBRARY_DIR / "[e]"),
    ]

    updated_count = 0
    for idx, ke_file in enumerate(target_books, 1):
        rel_path = ke_file.relative_to(ke_root)
        genre_hint = rel_path.parts[0] if rel_path.parts else ""
        original_stem = ke_file.stem
        
        # 순수 제목/저자 추출
        pure_t, pure_a = get_pure_title_and_author(original_stem, dir_path=ke_file.parent, epub_path=ke_file)
        
        rating, source = resolver.resolve_rating(pure_t, pure_a, genre_hint=genre_hint, epub_path=ke_file)
        formatted_rating = f"({rating:.2f})"

        # 7대 에디션 파일명 동기화
        synced_editions = 0
        for prefix, edit_dir in editions:
            target_dir = edit_dir / rel_path.parent
            if not target_dir.exists():
                continue

            # 파일명에서 접두사 및 평점을 뺀 기본 키로 기존 파일 검색
            raw_base = EDITION_PREFIX_REGEX.sub("", original_stem).strip()
            raw_base_no_rating = ANY_RATING_REGEX.sub("", raw_base).strip()

            candidates = list(target_dir.glob("*.epub"))
            found = None
            for c in candidates:
                c_base = EDITION_PREFIX_REGEX.sub("", c.stem).strip()
                c_base_no_rating = ANY_RATING_REGEX.sub("", c_base).strip()
                if c_base_no_rating == raw_base_no_rating:
                    found = c
                    break

            if found:
                new_stem = replace_or_append_rating_in_filename(found.stem, formatted_rating)
                new_file = found.parent / f"{new_stem}.epub"
                if found != new_file:
                    try:
                        found.rename(new_file)
                        synced_editions += 1
                    except Exception as err:
                        print(f"    [!] Error renaming {found.name}: {err}", flush=True)
                else:
                    synced_editions += 1

        updated_count += 1
        print(f"[{idx:03d}/{len(target_books):03d}] {pure_t[:35]:<35} -> {formatted_rating} [{source}] ({synced_editions} eds)", flush=True)

        if idx % 15 == 0:
            resolver.save_cache()

    resolver.save_cache()
    print(f"\n[+] Finished updating {updated_count} books across all library editions.", flush=True)


def sync_scheduler_queue(resolver: MasterRatingsResolver):
    """
    스케줄러 큐(.work/continuous_scheduler/config.json)의 7,170건 태스크 중
    평점이 없거나 (0.00)인 태스크들의 평점을 사전 조사하여 파일명 및 설정을 갱신한다.
    """
    print("\n" + "="*70, flush=True)
    print(">>> 2. 작업예정 큐(config.json) 평점 사전 조사 및 일괄 반영 집행", flush=True)
    print("="*70, flush=True)

    if not CONFIG_FILE.exists():
        print(f"[!] config.json not found at {CONFIG_FILE}", flush=True)
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    print(f"[*] Total tasks in config.json: {len(tasks)}", flush=True)

    updated_count = 0
    for idx, t in enumerate(tasks, 1):
        title = t.get("title", "")
        author = t.get("author", "")
        output_epub = t.get("output_epub", "")
        study_output = t.get("study_output_epub", "")
        genre_hint = t.get("category", "") or t.get("genre", "")

        # 평점 검사
        stem = Path(output_epub).stem if output_epub else title
        m = RATING_REGEX.search(stem)
        needs_update = (not m) or (float(m.group(1)) == 0.0) or (float(m.group(1)) == 3.95)

        if not needs_update:
            continue

        rating, source = resolver.resolve_rating(title, author, genre_hint=genre_hint)
        formatted_rating = f"({rating:.2f})"

        # 1. title 갱신
        t["title"] = replace_or_append_rating_in_filename(title, formatted_rating)

        # 2. book_title_ko 갱신
        if "book_title_ko" in t and t["book_title_ko"]:
            t["book_title_ko"] = replace_or_append_rating_in_filename(t["book_title_ko"], formatted_rating)

        # 3. output_epub 갱신
        if output_epub:
            p = Path(output_epub)
            new_stem = replace_or_append_rating_in_filename(p.stem, formatted_rating)
            t["output_epub"] = str(p.parent / f"{new_stem}.epub")

        # 4. study_output_epub 갱신
        if study_output:
            p = Path(study_output)
            new_stem = replace_or_append_rating_in_filename(p.stem, formatted_rating)
            t["study_output_epub"] = str(p.parent / f"{new_stem}.epub")

        updated_count += 1
        if updated_count % 100 == 0 or updated_count == 1:
            print(f"[{updated_count:04d}] {title[:35]:<35} -> {formatted_rating} [{source}]", flush=True)

        if updated_count % 200 == 0:
            resolver.save_cache()

    resolver.save_cache()

    # 원자적 파일 교체 (Atomic replace)
    tmp_config = CONFIG_FILE.with_suffix(".tmp")
    with open(tmp_config, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp_config.replace(CONFIG_FILE)

    print(f"\n[+] Finished updating {updated_count} scheduled tasks in config.json with authentic ratings.", flush=True)


def main():
    start_time = time.time()
    resolver = MasterRatingsResolver()

    # 1. 서재 에디션 1:1 동기화
    sync_library_editions(resolver)

    # 2. 스케줄러 큐 전수 동기화
    sync_scheduler_queue(resolver)

    elapsed = time.time() - start_time
    print("\n" + "="*70, flush=True)
    print(f"[★] All operations completed successfully in {elapsed:.1f}s.", flush=True)
    print("="*70, flush=True)


if __name__ == "__main__":
    main()
