#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


USER_AGENT = "CodexLocalEpubCoverTool/1.0"


@dataclass
class OnlineCover:
    data: bytes
    media_type: str
    source: str
    title: str = ""
    author: str = ""


def normalize_for_match(text: str) -> str:
    text = re.sub(r"[_\-]+", " ", text or "")
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^0-9a-zA-Z가-힣 ]+", " ", text)
    text = re.sub(r"\b(the|a|an|by|and)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def clean_search_title(title: str) -> str:
    text = re.sub(r"[_]+", " ", title or "")
    text = re.sub(r"^\s*\[[^\]]+\]\s*", "", text)
    text = re.sub(r"^\s*\d{1,3}\s+", "", text)
    text = re.sub(r"^\s*\d{1,3}[\s._-]+", "", text)
    text = re.sub(r"\s+by\s+.+$", "", text, flags=re.I)
    text = re.sub(r"\bSentence Inline English Korean\b", "", text, flags=re.I)
    text = re.sub(r"\bEnglish Korean Study\b", "", text, flags=re.I)
    text = re.sub(r"\bKorean English Study\b", "", text, flags=re.I)
    text = re.sub(r"\bStudy EPUB\b", "", text, flags=re.I)
    text = re.sub(r"\bEPUB\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -_")
    return text or title


def score_title(query_title: str, candidate_title: str) -> float:
    query = normalize_for_match(clean_search_title(query_title))
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
    scores = [SequenceMatcher(None, query, normalize_for_match(author)).ratio() for author in candidate_authors if author]
    return max(scores, default=0.0)


def author_match_required(query_author: str) -> bool:
    return bool(re.search(r"[A-Za-z]", query_author or ""))


def acceptable_author_match(query_author: str, candidate_authors: list[str]) -> bool:
    if not author_match_required(query_author):
        return True
    return score_author(query_author, candidate_authors) >= 0.45


def request_json(url: str, params: dict[str, str], timeout: float = 5.0) -> dict[str, Any] | None:
    full_url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except (OSError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def download_bytes(url: str, timeout: float = 7.0) -> tuple[bytes, str] | None:
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
            media_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    except (OSError, urllib.error.HTTPError, urllib.error.URLError):
        return None
    if len(data) < 1024:
        return None
    if not media_type.startswith("image/"):
        media_type = media_type_from_bytes(data)
    if not media_type.startswith("image/"):
        return None
    return data, media_type


def media_type_from_bytes(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if data.lstrip().startswith(b"<svg") or b"<svg" in data[:300].lower():
        return "image/svg+xml"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "image/webp"
    return "application/octet-stream"


def cache_key(title: str, author: str) -> str:
    raw = f"{clean_search_title(title)}\n{author}".encode("utf-8", "replace")
    return hashlib.sha256(raw).hexdigest()[:24]


def read_cached(cache_dir: Path | None, title: str, author: str) -> OnlineCover | None:
    if cache_dir is None:
        return None
    meta_path = cache_dir / f"{cache_key(title, author)}.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        data_path = cache_dir / meta["file"]
        if data_path.exists():
            return OnlineCover(
                data=data_path.read_bytes(),
                media_type=meta["media_type"],
                source=meta["source"],
                title=meta.get("title", ""),
                author=meta.get("author", ""),
            )
    except Exception:
        return None
    return None


def write_cached(cache_dir: Path | None, query_title: str, query_author: str, cover: OnlineCover) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "image/webp": ".webp",
    }.get(cover.media_type, ".img")
    key = cache_key(query_title, query_author)
    data_name = f"{key}{suffix}"
    (cache_dir / data_name).write_bytes(cover.data)
    (cache_dir / f"{key}.json").write_text(
        json.dumps(
            {
                "file": data_name,
                "media_type": cover.media_type,
                "source": cover.source,
                "title": cover.title,
                "author": cover.author,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def google_books_cover(title: str, author: str) -> OnlineCover | None:
    search_title = clean_search_title(title)
    queries = []
    if author:
        queries.append(f'intitle:"{search_title}" inauthor:"{author}"')
    queries.append(f'intitle:"{search_title}"')
    queries.append(search_title)
    best: tuple[float, dict[str, Any]] | None = None
    for query in queries:
        data = request_json(
            "https://www.googleapis.com/books/v1/volumes",
            {
                "q": query,
                "maxResults": "5",
                "printType": "books",
                "projection": "lite",
            },
        )
        for item in (data or {}).get("items", []) or []:
            info = item.get("volumeInfo", {}) or {}
            links = info.get("imageLinks", {}) or {}
            if not links:
                continue
            candidate_title = info.get("title", "")
            candidate_authors = info.get("authors", []) or []
            if not acceptable_author_match(author, candidate_authors):
                continue
            score = score_title(search_title, candidate_title) * 0.78 + score_author(author, candidate_authors) * 0.22
            if best is None or score > best[0]:
                best = (score, info)
        if best and best[0] >= 0.82:
            break
        time.sleep(0.1)
    if not best or best[0] < 0.72:
        return None
    info = best[1]
    links = info.get("imageLinks", {}) or {}
    for key in ("extraLarge", "large", "medium", "small", "thumbnail", "smallThumbnail"):
        url = links.get(key)
        if not url:
            continue
        url = re.sub(r"[?&]edge=curl", "", url)
        downloaded = download_bytes(url)
        if downloaded:
            data, media_type = downloaded
            return OnlineCover(
                data=data,
                media_type=media_type,
                source=f"Google Books: {url}",
                title=info.get("title", ""),
                author=", ".join(info.get("authors", []) or []),
            )
    return None


def open_library_cover(title: str, author: str) -> OnlineCover | None:
    search_title = clean_search_title(title)
    params = {
        "title": search_title,
        "limit": "8",
        "fields": "title,author_name,cover_i,edition_key,isbn",
    }
    if author:
        params["author"] = author
    data = request_json("https://openlibrary.org/search.json", params)
    best: tuple[float, dict[str, Any]] | None = None
    for doc in (data or {}).get("docs", []) or []:
        cover_id = doc.get("cover_i")
        if not cover_id:
            continue
        candidate_title = doc.get("title", "")
        candidate_authors = doc.get("author_name", []) or []
        if not acceptable_author_match(author, candidate_authors):
            continue
        score = score_title(search_title, candidate_title) * 0.78 + score_author(author, candidate_authors) * 0.22
        if best is None or score > best[0]:
            best = (score, doc)
    if not best or best[0] < 0.72:
        return None
    doc = best[1]
    url = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg"
    downloaded = download_bytes(url)
    if not downloaded:
        return None
    data, media_type = downloaded
    return OnlineCover(
        data=data,
        media_type=media_type,
        source=f"Open Library: {url}",
        title=doc.get("title", ""),
        author=", ".join(doc.get("author_name", []) or []),
    )


def find_online_cover(title: str, author: str = "", cache_dir: Path | None = None) -> OnlineCover | None:
    cached = read_cached(cache_dir, title, author)
    if cached:
        return cached
    for lookup in (open_library_cover, google_books_cover):
        cover = lookup(title, author)
        if cover:
            write_cached(cache_dir, title, author, cover)
            return cover
        time.sleep(0.2)
    return None
