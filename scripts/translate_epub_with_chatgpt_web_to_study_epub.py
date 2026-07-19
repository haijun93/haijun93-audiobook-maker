#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

try:
    import fcntl
except ImportError:  # Windows uses msvcrt locking below.
    fcntl = None  # type: ignore[assignment]

from atomic_io import atomic_output_path, atomic_write_json, atomic_write_text
from book_cover_lookup import find_online_cover
from epub_integrity import validate_epub
from final_epub_dialogue_consistency_review import review_dialogue_consistency
from final_epub_tone_review import review_epub_tone
from remove_readrobe_text_from_epubs import scrub_epub, scrub_text
from safe_xml import safe_fromstring
from translation_quality_checks import assess_translations, extract_segment_sources

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_maker import (  # noqa: E402
    CHATGPT_WEB_CHROME_PATH,
    DEFAULT_CHATGPT_WEB_MAX_ATTEMPTS,
    GEMINI_WEB_CHROME_PATH,
    ProgressHeartbeat,
    beat_heartbeat,
    chatgpt_web_launch_args,
    classify_gemini_web_notice_text,
    extract_chatgpt_conversation_id,
    extract_gemini_web_conversation_id,
    handle_chatgpt_web_page_notices,
    is_chatgpt_web_refusal_response,
    load_chatgpt_web_cookies,
    load_chatgpt_web_modules,
    load_gemini_web_cookies,
    load_gemini_web_modules,
    normalize_chatgpt_web_copy,
    normalized_file_text,
    prepare_chatgpt_web_page,
    prepare_gemini_web_page,
    read_last_chatgpt_web_response,
    send_chatgpt_web_prompt,
    send_gemini_web_prompt,
    wait_for_chatgpt_web_response,
    wait_for_gemini_web_response,
)


TRANSLATION_PIPELINE_VERSION = 3
MINIMUM_ACCEPTED_CACHE_VERSION = 2
RELATIONSHIP_GUIDE_VERSION = 3
ERROR_TAXONOMY_VERSION = 1
WEB_PROVIDER_MARKER = ".translation_web_provider"
GEMINI_MARKER_OPEN_TEMPLATE = "[[[BEGIN:{block_id}]]]"
GEMINI_MARKER_CLOSE_TEMPLATE = "[[[END:{block_id}]]]"
WEB_PROVIDERS = ("chatgpt", "gemini")
OVERNIGHT_FALLBACK_PROVIDER = "chatgpt"
OVERNIGHT_FALLBACK_START_HOUR = 18
OVERNIGHT_FALLBACK_END_HOUR = 9
GEMINI_DOWN_RECHECK_SEC = 900
PROVIDER_FALLBACK_STATE_FILE = "provider_fallback_state.json"


@dataclass
class SourceBlock:
    id: str
    text: str


@dataclass
class SourceSection:
    title: str
    filename: str
    blocks: list[SourceBlock] = field(default_factory=list)


@dataclass
class TranslationChunk:
    index: int
    block_ids: list[str]
    text: str
    context_before: str = ""
    context_after: str = ""


@dataclass
class CoverAsset:
    href: str
    media_type: str
    data: bytes
    source: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="영문 EPUB를 웹 번역 서비스로 소설체 한국어 번역하고 영어학습용 Kindle EPUB를 만듭니다."
    )
    parser.add_argument("--input-epub", type=Path, required=True)
    parser.add_argument("--output-epub", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument(
        "--book-title-ko",
        help="Deprecated name kept for compatibility. This value is used as the output EPUB title.",
    )
    parser.add_argument("--max-chars-per-chunk", type=int, default=8500)
    parser.add_argument("--request-timeout-sec", type=int, default=1200)
    parser.add_argument("--web-provider", choices=WEB_PROVIDERS)
    parser.add_argument("--chatgpt-web-chrome-path", default=CHATGPT_WEB_CHROME_PATH)
    parser.add_argument("--gemini-web-chrome-path", default=GEMINI_WEB_CHROME_PATH)
    parser.add_argument("--web-visible", "--chatgpt-web-visible", dest="web_visible", action="store_true")
    parser.add_argument(
        "--disable-overnight-web-fallback",
        action="store_true",
        help=(
            "야간(18:00~09:00) 및 주말(토/일 종일) 시간대에 Gemini 웹이 오류/일시 중단되어도 "
            "ChatGPT 웹으로 자동 전환하지 않습니다."
        ),
    )
    parser.add_argument(
        "--provider-fallback-state-dir",
        type=Path,
        help=(
            "Gemini 일시 중단 상태를 기록할 공유 디렉터리(배치 작업 시 모든 도서가 같은 곳을 보게 "
            "하여 도서마다 중단 상태를 다시 발견하지 않도록 함). 지정하지 않으면 --work-dir을 사용합니다."
        ),
    )
    parser.add_argument(
        "--draft-provider",
        choices=("ollama", "none"),
        default="ollama",
        help=(
            "번역 전 로컬 Ollama 모델로 초벌 번역을 만들고, 웹 provider는 그 초벌 번역을 다듬어 "
            "완성합니다. 'none'이면 기존처럼 웹 provider가 처음부터 번역합니다."
        ),
    )
    parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_DRAFT_MODEL)
    parser.add_argument("--ollama-host", default=None, help=f"기본값: {DEFAULT_OLLAMA_API_URL}")
    parser.add_argument(
        "--web-max-attempts",
        "--chatgpt-web-max-attempts",
        dest="web_max_attempts",
        type=int,
        default=DEFAULT_CHATGPT_WEB_MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--chunks-per-conversation",
        type=int,
        default=1,
        help="한 웹서비스 대화에서 연속 처리할 번역 조각 수(기본: 1)",
    )
    parser.add_argument(
        "--inter-request-delay-sec",
        type=float,
        default=4.0,
        help="연속 웹 요청 사이의 기본 대기 시간(초)",
    )
    parser.add_argument("--heartbeat-file", type=Path)
    parser.add_argument("--translate-only", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument(
        "--draft-only",
        action="store_true",
        help=(
            "Ollama 초벌 번역만 실행하고 종료합니다(Gemini/ChatGPT 호출 없음). "
            "배치 작업이 다음 책의 초벌 번역을 현재 책 처리 중에 미리 준비해 두는 용도."
        ),
    )
    parser.add_argument(
        "--precomputed-drafts-only",
        action="store_true",
        help=(
            "이 프로세스 자신은 Ollama 초벌 번역을 새로 생성하지 않고, 이미 캐시된 초벌 번역만 "
            "읽어서 사용합니다. 배치 작업의 독립 초벌번역 큐가 같은 work-dir을 이미 채우고 있을 때, "
            "두 프로세스가 동시에 같은 책을 초벌 번역하며 Ollama 단일 슬롯을 두고 경합하는 것을 "
            "막기 위한 옵션입니다."
        ),
    )
    parser.add_argument(
        "--skip-final-tone-review",
        action="store_true",
        help="EPUB 생성 후 인물관계/말투 최종 점검 리포트를 만들지 않습니다.",
    )
    return parser.parse_args()


def resolve_work_dir(args: argparse.Namespace) -> Path:
    if args.work_dir:
        return args.work_dir.expanduser().resolve()
    return args.output_epub.expanduser().resolve().with_suffix(".work")


def resolve_web_provider(args: argparse.Namespace, work_dir: Path) -> str:
    requested = getattr(args, "web_provider", None)
    if requested in WEB_PROVIDERS:
        return requested
    marker_path = work_dir / WEB_PROVIDER_MARKER
    if marker_path.exists():
        pinned = marker_path.read_text(encoding="utf-8").strip().lower()
        if pinned in WEB_PROVIDERS:
            return pinned
    configured = os.getenv("EPUB_TRANSLATION_WEB_PROVIDER", "gemini").strip().lower()
    return configured if configured in WEB_PROVIDERS else "gemini"


def persist_web_provider(work_dir: Path, provider: str) -> None:
    write_text(work_dir / WEB_PROVIDER_MARKER, provider)


def web_max_attempts(args: argparse.Namespace) -> int:
    return max(1, int(getattr(args, "web_max_attempts", getattr(args, "chatgpt_web_max_attempts", 5))))


class OvernightProviderSwitch(Exception):
    """Raised to interrupt the current browser session so it can relaunch on another web provider.

    Gemini's overnight overload banners can persist for hours; rather than sleeping through
    them, an active gemini session in the 18:00-09:00 window (or anytime on Sat/Sun) switches
    to ChatGPT web for the remaining chunks. The next session started by translate_missing_chunks
    tries Gemini again first, so translation resumes on Gemini automatically once it recovers.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def in_web_fallback_window(now: datetime) -> bool:
    """True during the nightly 18:00-09:00 window on any day, and all day on Sat/Sun.

    Weekends get all-day coverage because there's no need to protect daytime Gemini usage
    from an automatic ChatGPT switch-over on days without normal daytime work going on.
    """
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return True
    hour = now.hour
    if OVERNIGHT_FALLBACK_START_HOUR <= OVERNIGHT_FALLBACK_END_HOUR:
        return OVERNIGHT_FALLBACK_START_HOUR <= hour < OVERNIGHT_FALLBACK_END_HOUR
    return hour >= OVERNIGHT_FALLBACK_START_HOUR or hour < OVERNIGHT_FALLBACK_END_HOUR


def overnight_web_fallback_enabled(args: argparse.Namespace) -> bool:
    return not bool(getattr(args, "disable_overnight_web_fallback", False))


def overnight_fallback_active(args: argparse.Namespace, provider: str) -> bool:
    """Whether an active Gemini session should switch to ChatGPT web right now.

    Gates on: the configured provider being Gemini, the feature not being disabled, and being
    inside the fallback time window.
    """
    if provider != "gemini" or not overnight_web_fallback_enabled(args):
        return False
    return in_web_fallback_window(datetime.now())


def provider_fallback_state_dir(args: argparse.Namespace, work_dir: Path) -> Path:
    """Directory used to persist the batch-wide "Gemini is temporarily down" marker.

    Batch runs process many books as separate subprocesses, each with its own --work-dir.
    Without a shared location, every book would have to independently rediscover a Gemini
    outage (3 consecutive temporary errors) before switching, instead of the whole batch
    benefiting from what the previous book already learned. workflow_runner.py points this
    at the batch job's root work directory; a single-book run just uses its own work_dir.
    """
    configured = getattr(args, "provider_fallback_state_dir", None)
    if configured:
        return Path(configured).expanduser().resolve()
    return work_dir


def _fallback_state_path(state_dir: Path) -> Path:
    return state_dir / PROVIDER_FALLBACK_STATE_FILE


def _read_fallback_state(state_dir: Path) -> dict:
    path = _fallback_state_path(state_dir)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_fallback_state(state_dir: Path, updates: dict) -> None:
    state = _read_fallback_state(state_dir)
    state.update(updates)
    path = _fallback_state_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def mark_gemini_temporarily_down(state_dir: Path) -> None:
    _write_fallback_state(
        state_dir,
        {
            "gemini_down_until": (
                datetime.now(timezone.utc) + timedelta(seconds=GEMINI_DOWN_RECHECK_SEC)
            ).isoformat(),
        },
    )


def _state_deadline_active(state: dict, key: str) -> bool:
    deadline = state.get(key)
    if not deadline:
        return False
    try:
        return datetime.now(timezone.utc) < datetime.fromisoformat(deadline)
    except ValueError:
        return False


def resolve_session_provider(args: argparse.Namespace, work_dir: Path) -> str:
    """Effective web provider for the next browser session.

    Only Gemini gets the overnight/weekend auto-fallback: outside the fallback window, when
    the configured provider isn't Gemini, this always returns the configured provider
    unchanged. Otherwise, this returns ChatGPT while Gemini is marked down and Gemini again
    once that marker expires.
    """
    base = active_web_provider(args)
    if not overnight_fallback_active(args, base):
        return base
    shared_state = _read_fallback_state(provider_fallback_state_dir(args, work_dir))
    if not _state_deadline_active(shared_state, "gemini_down_until"):
        return "gemini"
    return OVERNIGHT_FALLBACK_PROVIDER


def args_with_provider(args: argparse.Namespace, provider: str) -> argparse.Namespace:
    if active_web_provider(args) == provider:
        return args
    clone = argparse.Namespace(**vars(args))
    clone.web_provider = provider
    return clone


def translation_prompt_for_provider(prompt: str, provider: str) -> str:
    if provider != "gemini":
        return prompt
    prompt = re.sub(
        r"<<<END_(B\d+)>>>",
        lambda match: GEMINI_MARKER_CLOSE_TEMPLATE.format(block_id=match.group(1)),
        prompt,
    )
    return re.sub(
        r"<<<(B\d+)>>>",
        lambda match: GEMINI_MARKER_OPEN_TEMPLATE.format(block_id=match.group(1)),
        prompt,
    )


def prepare_translation_web_page(page, *, timeout_error_cls, args, heartbeat, label, section_prefix, attempt) -> None:
    prepare = prepare_gemini_web_page if active_web_provider(args) == "gemini" else prepare_chatgpt_web_page
    prepare(
        page,
        timeout_error_cls=timeout_error_cls,
        heartbeat=heartbeat,
        label=label,
        section_prefix=section_prefix,
        attempt=attempt,
    )


def read_opf_path(archive: zipfile.ZipFile) -> str:
    container = safe_fromstring(archive.read("META-INF/container.xml"))
    namespace = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = container.find(".//c:rootfile", namespace)
    if rootfile is None:
        raise RuntimeError("EPUB container에서 package 문서를 찾지 못했습니다.")
    return rootfile.attrib["full-path"]


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def read_spine(epub_path: Path) -> tuple[str, str, list[str], dict[str, bytes]]:
    with zipfile.ZipFile(epub_path) as archive:
        opf_path = read_opf_path(archive)
        opf_dir = str(Path(opf_path).parent)
        if opf_dir == ".":
            opf_dir = ""
        opf = safe_fromstring(archive.read(opf_path))
        ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
        title_node = opf.find(".//dc:title", ns)
        creator_node = opf.find(".//dc:creator", ns)
        title = clean_text(title_node.text or "") if title_node is not None else epub_path.stem
        creator = clean_text(creator_node.text or "") if creator_node is not None else ""
        manifest = {
            item.attrib["id"]: item.attrib
            for item in opf.findall(".//opf:manifest/opf:item", ns)
            if "id" in item.attrib
        }
        spine_hrefs: list[str] = []
        for itemref in opf.findall(".//opf:spine/opf:itemref", ns):
            idref = itemref.attrib.get("idref")
            if not idref or idref not in manifest:
                continue
            item = manifest[idref]
            if item.get("media-type") != "application/xhtml+xml":
                continue
            href = unquote(item.get("href", ""))
            spine_hrefs.append(str(Path(opf_dir, href)) if opf_dir else href)
        resources = {name: archive.read(name) for name in archive.namelist()}
    return title, creator, spine_hrefs, resources


def media_type_from_href(href: str) -> str:
    suffix = Path(href).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def cover_extension(media_type: str, fallback_href: str = "") -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "image/webp": ".webp",
    }
    if media_type in mapping:
        return mapping[media_type]
    suffix = Path(fallback_href).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".svg"


def resolve_opf_href(opf_path: str, href: str) -> str:
    opf_dir = str(Path(opf_path).parent)
    if opf_dir == ".":
        opf_dir = ""
    href = unquote(href.split("#", 1)[0])
    return str(Path(opf_dir, href)) if opf_dir else href


def default_cover_asset(book_title: str, creator: str) -> CoverAsset:
    safe_title = html.escape((book_title or "Korean Study EPUB")[:42])
    safe_creator = html.escape((creator or "")[:42])
    svg = f'''<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="2560" viewBox="0 0 1600 2560">
  <rect width="1600" height="2560" fill="#f4efe6"/>
  <rect x="110" y="110" width="1380" height="2340" fill="none" stroke="#2f3a44" stroke-width="14"/>
  <text x="800" y="980" text-anchor="middle" font-family="serif" font-size="104" font-weight="700" fill="#1f2933">
    <tspan x="800">{safe_title}</tspan>
  </text>
  <text x="800" y="1130" text-anchor="middle" font-family="serif" font-size="52" fill="#4b5563">{safe_creator}</text>
  <text x="800" y="1870" text-anchor="middle" font-family="serif" font-size="48" fill="#5b6470">Korean-English Study Edition</text>
</svg>
'''
    return CoverAsset(
        href="cover.svg",
        media_type="image/svg+xml",
        data=svg.encode("utf-8"),
        source="generated",
    )


def extract_cover_asset(input_epub: Path, book_title: str, creator: str) -> CoverAsset:
    try:
        with zipfile.ZipFile(input_epub) as archive:
            opf_path = read_opf_path(archive)
            root = safe_fromstring(archive.read(opf_path))
            ns = {"opf": "http://www.idpf.org/2007/opf"}
            manifest_items = [
                item
                for item in root.findall(".//opf:manifest/opf:item", ns)
                if item.attrib.get("href")
            ]
            by_id = {item.attrib.get("id", ""): item for item in manifest_items}
            candidates: list[ET.Element] = []

            for meta in root.findall(".//opf:metadata/opf:meta", ns):
                if meta.attrib.get("name", "").lower() == "cover":
                    item = by_id.get(meta.attrib.get("content", ""))
                    if item is not None:
                        candidates.append(item)

            for item in manifest_items:
                media_type = item.attrib.get("media-type", "")
                properties = item.attrib.get("properties", "").split()
                if media_type.startswith("image/") and "cover-image" in properties:
                    candidates.append(item)

            for item in manifest_items:
                media_type = item.attrib.get("media-type", "")
                marker = f"{item.attrib.get('id', '')} {item.attrib.get('href', '')}".lower()
                if media_type.startswith("image/") and "cover" in marker:
                    candidates.append(item)

            seen: set[str] = set()
            for item in candidates:
                href = item.attrib.get("href", "")
                source_name = resolve_opf_href(opf_path, href)
                if source_name in seen or source_name not in archive.namelist():
                    continue
                seen.add(source_name)
                media_type = item.attrib.get("media-type") or media_type_from_href(href)
                if not media_type.startswith("image/"):
                    continue
                ext = cover_extension(media_type, href)
                return CoverAsset(
                    href=f"cover{ext}",
                    media_type=media_type,
                    data=archive.read(source_name),
                    source=source_name,
                )
    except Exception:
        pass
    try:
        cover = find_online_cover(book_title, creator, cache_dir=input_epub.parent / "_cover_cache")
        if cover:
            ext = cover_extension(cover.media_type)
            return CoverAsset(
                href=f"cover{ext}",
                media_type=cover.media_type,
                data=cover.data,
                source=cover.source,
            )
    except Exception:
        pass
    return default_cover_asset(book_title, creator)


def parse_ncx_nav(resources: dict[str, bytes], spine_hrefs: list[str]) -> list[tuple[str, str, int]]:
    ncx_name = next((name for name in resources if name.lower().endswith(".ncx")), None)
    if not ncx_name:
        return []
    ncx_dir = str(Path(ncx_name).parent)
    if ncx_dir == ".":
        ncx_dir = ""
    root = safe_fromstring(resources[ncx_name])
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    nav: list[tuple[str, str, int]] = []
    for point in root.findall(".//ncx:navPoint", ns):
        label = point.find(".//ncx:navLabel/ncx:text", ns)
        content = point.find("ncx:content", ns)
        if label is None or content is None:
            continue
        href = unquote(content.attrib.get("src", "").split("#", 1)[0])
        full_href = str(Path(ncx_dir, href)) if ncx_dir else href
        if full_href in spine_hrefs:
            nav.append((clean_text(label.text or full_href), full_href, spine_hrefs.index(full_href)))
    deduped: list[tuple[str, str, int]] = []
    seen: set[tuple[str, int]] = set()
    for label, href, index in sorted(nav, key=lambda row: row[2]):
        key = (href, index)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((label, href, index))
    return deduped


def blocks_from_xhtml(data: bytes) -> list[str]:
    soup = BeautifulSoup(data, "html.parser")
    blocks: list[str] = []
    for tag in soup.find_all(["h1", "h2", "h3", "p", "blockquote", "li"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if text:
            blocks.append(text)
    if blocks:
        return blocks

    body = soup.body or soup
    text = clean_text(body.get_text(" ", strip=True))
    if not text:
        return []
    return split_plain_text_blocks(text)


def split_plain_text_blocks(text: str, max_chars: int = 1400) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    sentence_parts = re.split(r"(?<=[.!?])\s+(?=(?:[\"'“”‘’(\[])?[A-Z0-9])", text)
    blocks: list[str] = []

    for raw_part in sentence_parts:
        part = clean_text(raw_part)
        if not part:
            continue
        if len(part) > max_chars:
            words = part.split()
            piece: list[str] = []
            piece_len = 0
            for word in words:
                projected = piece_len + len(word) + 1
                if piece and projected > max_chars:
                    blocks.append(clean_text(" ".join(piece)))
                    piece = []
                    piece_len = 0
                piece.append(word)
                piece_len += len(word) + 1
            if piece:
                blocks.append(clean_text(" ".join(piece)))
            continue
        blocks.append(part)
    return blocks


def metadata_section_titles(resources: dict[str, bytes], book_title: str) -> list[str]:
    opf_name = next((name for name in resources if name.lower().endswith(".opf")), None)
    if not opf_name:
        return []
    try:
        root = safe_fromstring(resources[opf_name])
    except Exception:
        return []
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    description = root.find(".//dc:description", ns)
    if description is None or not description.text:
        return []
    text = html.unescape(description.text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    marker = re.search(r"\bCONTENTS\b", text, flags=re.IGNORECASE)
    if marker:
        text = text[marker.end() :]
    candidates: list[str] = []
    seen: set[str] = set()

    def add(title: str) -> None:
        cleaned = clean_text(re.sub(r"\s*\(\d{4}.*?\)\s*$", "", title))
        cleaned = cleaned.strip(" \t\r\n\"“”")
        key = cleaned.lower()
        if cleaned and key not in seen:
            candidates.append(cleaned)
            seen.add(key)

    if book_title:
        add(book_title)
    for match in re.finditer(r'["“]([^"”]+)["”]', text):
        add(match.group(1))
    for line in text.splitlines():
        line = clean_text(line)
        if not line:
            continue
        if line.lower().startswith("introduction by "):
            add("Introduction")
    return candidates


def block_starts_with_title(text: str, title: str) -> bool:
    block = clean_text(text)
    if not block or not title:
        return False
    lower_block = block.lower()
    lower_title = clean_text(title).lower()
    if not lower_block.startswith(lower_title):
        return False
    if len(block) == len(title):
        return True
    return not block[len(title)].isalnum()


def find_title_offset(text: str, title: str, start: int = 0) -> int | None:
    if not text or not title:
        return None
    flags = 0 if len(title.split()) == 1 else re.IGNORECASE
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(title)}(?![A-Za-z0-9])", flags)
    match = pattern.search(text, pos=start)
    return match.start() if match else None


def sliced_blocks(
    blocks: list[SourceBlock],
    start: tuple[int, int],
    end: tuple[int, int],
) -> list[SourceBlock]:
    start_index, start_offset = start
    end_index, end_offset = end
    result: list[SourceBlock] = []
    for index in range(start_index, end_index + 1):
        text = blocks[index].text
        left = start_offset if index == start_index else 0
        right = end_offset if index == end_index else len(text)
        sliced = clean_text(text[left:right])
        if sliced:
            result.append(SourceBlock("", sliced))
    return result


def reassign_block_ids(sections: list[SourceSection]) -> list[SourceSection]:
    counter = 1
    for section in sections:
        for block in section.blocks:
            block.id = f"B{counter:05d}"
            counter += 1
    return sections


def split_sections_by_metadata_titles(
    sections: list[SourceSection],
    titles: list[str],
    book_title: str,
) -> list[SourceSection]:
    if len(sections) > 3 or not titles:
        return sections
    blocks = all_blocks(sections)
    if len(blocks) < 100:
        return sections

    starts: list[tuple[int, int, str]] = []
    search_from = (0, 0)
    for title in titles:
        found: tuple[int, int] | None = None
        for index in range(search_from[0], len(blocks)):
            offset_start = search_from[1] if index == search_from[0] else 0
            offset = find_title_offset(blocks[index].text, title, offset_start)
            if offset is not None:
                found = (index, offset)
                break
        if found is None and title.lower() == book_title.lower() and blocks:
            first = blocks[0].text.lower()
            if title.lower() in first[:120]:
                found = (0, 0)
        if found is None:
            continue
        if starts and found <= (starts[-1][0], starts[-1][1]):
            continue
        starts.append((found[0], found[1], title))
        search_from = (found[0], found[1] + len(title))

    if len(starts) < 3:
        return sections

    refined: list[SourceSection] = []
    if starts[0][0] > 0 or starts[0][1] > 0:
        front_blocks = sliced_blocks(blocks, (0, 0), (starts[0][0], starts[0][1]))
        if front_blocks:
            refined.append(SourceSection("Front Matter", "front.xhtml", front_blocks))
    for position, (start_index, start_offset, title) in enumerate(starts):
        end = (
            (starts[position + 1][0], starts[position + 1][1])
            if position + 1 < len(starts)
            else (len(blocks) - 1, len(blocks[-1].text))
        )
        section_blocks = sliced_blocks(blocks, (start_index, start_offset), end)
        if not section_blocks:
            continue
        refined.append(
            SourceSection(
                title,
                safe_filename_for_section(len(refined) + 1, title),
                section_blocks,
            )
        )
    return reassign_block_ids([section for section in refined if section.blocks])


def safe_filename_for_section(index: int, title: str) -> str:
    if title.lower() == "title page":
        return "front.xhtml"
    if title.lower().startswith("chapter "):
        number = re.sub(r"\D+", "", title)
        if number:
            return f"chapter{int(number):02d}.xhtml"
    if title.lower().startswith("part "):
        number = re.sub(r"\D+", "", title)
        if number:
            return f"part{int(number):02d}.xhtml"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    if not slug:
        slug = f"section-{index:03d}"
    return f"{index:03d}-{slug[:40]}.xhtml"


def is_clear_internal_section_heading(text: str) -> bool:
    compact = clean_text(text)
    lowered = compact.lower()
    if len(compact) > 60:
        return False
    if lowered in {
        "prologue",
        "epilogue",
        "acknowledgments",
        "acknowledgements",
        "about the author",
    }:
        return True
    if re.fullmatch(r"chapter\s+\d+[a-z]?", compact, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"part\s+[ivxlcdm]+", compact, flags=re.IGNORECASE):
        return True
    return False


def split_sparse_sections_by_internal_headings(sections: list[SourceSection]) -> list[SourceSection]:
    if len(sections) > 4:
        return sections
    blocks = all_blocks(sections)
    if len(blocks) < 300:
        return sections
    heading_indexes = [index for index, block in enumerate(blocks) if is_clear_internal_section_heading(block.text)]
    if len(heading_indexes) < 3:
        return sections

    refined: list[SourceSection] = []
    if heading_indexes[0] > 0:
        refined.append(SourceSection("Front Matter", "front.xhtml", blocks[: heading_indexes[0]]))

    for position, start in enumerate(heading_indexes):
        end = heading_indexes[position + 1] if position + 1 < len(heading_indexes) else len(blocks)
        title = blocks[start].text
        refined.append(
            SourceSection(
                title,
                safe_filename_for_section(len(refined) + 1, title),
                blocks[start:end],
            )
        )
    return [section for section in refined if section.blocks]


def extract_sections(epub_path: Path) -> tuple[str, str, list[SourceSection]]:
    title, creator, spine_hrefs, resources = read_spine(epub_path)
    nav = parse_ncx_nav(resources, spine_hrefs)
    if not nav:
        nav = [(Path(href).stem, href, index) for index, href in enumerate(spine_hrefs)]
    sections: list[SourceSection] = []
    block_index = 1
    for section_index, (label, _href, start) in enumerate(nav, start=1):
        next_start = nav[section_index][2] if section_index < len(nav) else len(spine_hrefs)
        if label.strip().lower() == "contents":
            continue
        section = SourceSection(label, safe_filename_for_section(section_index, label))
        for spine_href in spine_hrefs[start:next_start]:
            if spine_href not in resources:
                continue
            for text in blocks_from_xhtml(resources[spine_href]):
                block_id = f"B{block_index:05d}"
                section.blocks.append(SourceBlock(block_id, text))
                block_index += 1
        if section.blocks:
            sections.append(section)
    sections = split_sparse_sections_by_internal_headings(sections)
    sections = split_sections_by_metadata_titles(sections, metadata_section_titles(resources, title), title)
    return title, creator, sections


def translate_title(title: str) -> str:
    lookup = {
        "Title Page": "표제지",
        "Books by Freida McFadden": "프리다 맥패든의 책",
        "Prologue": "프롤로그",
        "Epilogue": "에필로그",
        "Acknowledgments": "감사의 말",
        "Copyright": "판권",
        "Part I": "1부",
        "Part II": "2부",
        "Part III": "3부",
        "Hear More from Freida": "프리다의 다른 이야기",
        "A Letter from Freida": "프리다가 보내는 편지",
    }
    if title in lookup:
        return lookup[title]
    match = re.fullmatch(r"Chapter\s+(\d+)", title, flags=re.IGNORECASE)
    if match:
        return f"{int(match.group(1))}장"
    return title


def infer_korean_book_title(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title).strip()
    lower = normalized.lower()
    lookup = {
        "the housemaid": "하우스메이드",
        "the housemaid's secret": "하우스메이드의 비밀",
        "the housemaid is watching": "하우스메이드가 지켜보고 있다",
    }
    if lower in lookup:
        return lookup[lower]
    if "housemaid's secret" in lower:
        return "하우스메이드의 비밀"
    if "housemaid is watching" in lower:
        return "하우스메이드가 지켜보고 있다"
    if "housemaid" in lower:
        return "하우스메이드"
    return normalized or "영어 학습 EPUB"


def all_blocks(sections: list[SourceSection]) -> list[SourceBlock]:
    return [block for section in sections for block in section.blocks]


def build_chunks(blocks: list[SourceBlock], max_chars: int) -> list[TranslationChunk]:
    chunks: list[TranslationChunk] = []
    current_ids: list[str] = []
    current_parts: list[str] = []
    current_len = 0
    for block in blocks:
        part = f"<<<{block.id}>>>\n{block.text}\n<<<END_{block.id}>>>"
        projected = current_len + len(part) + 2
        if current_parts and projected > max_chars:
            chunks.append(
                TranslationChunk(
                    index=len(chunks) + 1,
                    block_ids=current_ids,
                    text="\n\n".join(current_parts),
                )
            )
            current_ids = []
            current_parts = []
            current_len = 0
        current_ids.append(block.id)
        current_parts.append(part)
        current_len += len(part) + 2
    if current_parts:
        chunks.append(
            TranslationChunk(
                index=len(chunks) + 1,
                block_ids=current_ids,
                text="\n\n".join(current_parts),
            )
        )
    block_positions = {block.id: index for index, block in enumerate(blocks)}
    for chunk in chunks:
        first = block_positions.get(chunk.block_ids[0], 0)
        last = block_positions.get(chunk.block_ids[-1], first)
        before = blocks[max(0, first - 2) : first]
        after = blocks[last + 1 : last + 3]
        chunk.context_before = "\n".join(f"{block.id}: {block.text}" for block in before)[-1200:]
        chunk.context_after = "\n".join(f"{block.id}: {block.text}" for block in after)[:1200]
    return chunks


def relationship_guide_path(work_dir: Path) -> Path:
    return work_dir / "relationship_guide.txt"


def select_relationship_guide_sample(blocks: list[SourceBlock], max_chars: int = 8000) -> str:
    if not blocks:
        return ""

    selected: list[SourceBlock] = []
    seen: set[str] = set()

    def add(block: SourceBlock) -> None:
        if block.id not in seen:
            selected.append(block)
            seen.add(block.id)

    # Sample the whole narrative arc. The former first-block-heavy sampling could
    # miss characters and relationship changes introduced in later chapters.
    target_points = 120
    if len(blocks) <= target_points:
        for block in blocks:
            add(block)
    else:
        for point in range(target_points):
            index = round(point * (len(blocks) - 1) / (target_points - 1))
            add(blocks[index])

    dialogue_blocks = [block for block in blocks if any(mark in block.text for mark in ['"', "“", "”", "‘", "’", "'"])]
    if dialogue_blocks:
        dialogue_points = min(120, len(dialogue_blocks))
        for point in range(dialogue_points):
            index = 0 if dialogue_points == 1 else round(point * (len(dialogue_blocks) - 1) / (dialogue_points - 1))
            add(dialogue_blocks[index])

    positions = {block.id: index for index, block in enumerate(blocks)}
    selected.sort(key=lambda block: positions.get(block.id, 0))

    parts: list[str] = []
    total = 0
    for block in selected:
        part = f"{block.id}: {block.text}"
        if total + len(part) + 1 > max_chars:
            break
        parts.append(part)
        total += len(part) + 1
    return "\n".join(parts)


def build_relationship_guide_prompt(book_title: str, creator: str, blocks: list[SourceBlock]) -> str:
    sample = select_relationship_guide_sample(blocks)
    creator_line = f"\n저자/제작자: {creator}" if creator else ""
    return f"""EPUB `{book_title}`를 한국어로 번역하기 전에 인물관계와 한국어 말투 규칙을 먼저 정리합니다.{creator_line}

아래는 책 전체에서 뽑은 대표 본문 샘플입니다. 샘플만으로 단정하기 어려운 부분은 "추정"이라고 표시하세요.

해야 할 일:
1. 주요 인물, 반복 등장 인물, 화자/서술자를 파악합니다.
2. 인물 간 관계를 간단한 관계도로 정리합니다.
3. 한국어 번역 시 반말/존댓말/격식체 사용 기준을 정합니다.
4. 특히 대화문에서 누가 누구에게 반말을 써야 하는지, 누가 존댓말을 써야 하는지 명시합니다.
5. 관계가 장면에 따라 변하면 변화 조건을 적습니다.
6. 논픽션이거나 인물 대화가 적은 책이면, 인터뷰/인용/전문가/가족/공식 발화의 말투 원칙을 정리합니다.
7. 책 전체에서 반복 등장하는 고유명사(인명, 지명, 조직명 등)의 한국어 표기를 정합니다. 번역 내내 이 표기만 일관되게 사용해야 합니다.
8. 번역문 자체는 만들지 말고, 이후 번역자가 참고할 간결한 한국어 가이드만 출력합니다.

출력 형식:
[인물관계 요약]
- ...

[말투 규칙]
- A -> B: 반말/존댓말/격식체, 이유
- ...

[주의할 호칭과 일관성]
- ...

[고유명사 표기]
- English Name -> 한글 표기
- ...

중요:
- 계획, 안내, "정리하겠습니다" 같은 예고 문장을 쓰지 말고 완성된 가이드 본문만 출력합니다.
- 위 네 개 제목을 반드시 포함합니다.
- 최소 8개 이상의 구체적 말투 규칙을 작성합니다.
- [고유명사 표기]에는 책에서 반복 등장하는 고유명사를 최소 5개 이상, "영어 -> 한글" 형식 한 줄에 하나씩 적습니다.

대표 본문 샘플:
{sample}
"""


def relationship_guide_for_prompt(guide: str) -> str:
    guide = clean_text(guide)
    if not guide:
        return ""
    if len(guide) > 5000:
        guide = guide[:5000].rstrip() + " ..."
    return guide


def relationship_guide_is_complete(guide: str) -> tuple[bool, str]:
    normalized = normalize_chatgpt_web_copy(guide)
    compact = clean_text(normalized)
    if len(compact) < 500:
        return False, f"too short: {len(compact)} chars"
    required_headers = ["[인물관계 요약]", "[말투 규칙]", "[고유명사 표기]"]
    missing = [header for header in required_headers if header not in normalized]
    if missing:
        return False, f"missing headers: {', '.join(missing)}"
    if "정리하겠습니다" in compact[:300] and "[인물관계 요약]" not in compact[:300]:
        return False, "planning sentence instead of completed guide"
    rule_count = len(re.findall(r"->|→|반말|존댓말|격식", normalized))
    if rule_count < 5:
        return False, f"not enough speech-level rules: {rule_count}"
    return True, "ok"


def build_local_relationship_guide(book_title: str, creator: str, blocks: list[SourceBlock]) -> str:
    sample = select_relationship_guide_sample(blocks, max_chars=12000)
    stopwords = {
        "Chapter",
        "Part",
        "Book",
        "Copyright",
        "Contents",
        "Acknowledgments",
        "Epilogue",
        "Prologue",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    }
    counts: dict[str, int] = {}
    for match in re.finditer(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b", sample):
        name = match.group(0).strip()
        if name.split()[0] in stopwords or name in stopwords:
            continue
        counts[name] = counts.get(name, 0) + 1
    names = [name for name, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:16]]
    title_lower = book_title.lower()
    you_notes = ""
    if "you" in title_lower:
        you_notes = """
- Joe Goldberg: 1인칭 화자/서술자일 가능성이 높다. 독백은 집착적이고 친밀한 반말 어조를 기본으로 하되, 대외적 대화는 상대와 상황에 따라 조절한다.
- Beck/Love 등 연애 관계 인물: 친밀하거나 갈등이 격해진 장면에서는 반말을 기본으로 한다. 처음 만남, 고객 응대, 사회적 거리감이 있는 장면은 자연스러운 존댓말을 쓴다.
- 수사기관, 직원, 고객, 낯선 사람: Joe가 속으로는 반말로 판단해도 실제 대화는 존댓말/완곡한 말투를 우선한다.
"""
    name_line = ", ".join(names) if names else "샘플에서 확정 가능한 이름이 제한적이므로 장면별 관계를 우선 추론"
    creator_line = f" / 저자: {creator}" if creator else ""
    return f"""[인물관계 요약]
- 작품: {book_title}{creator_line}
- 주요 인물 후보: {name_line}
- 이 가이드는 웹 번역 서비스의 관계도 응답이 반복적으로 불완전할 때, EPUB 샘플에서 이름 후보와 장면 단서를 뽑아 만든 보수적 번역 가이드다.
- 관계가 확정되지 않은 인물은 현재 장면의 호칭, 행동, 권력관계, 친밀도, 거래/고객 관계를 기준으로 말투를 정한다.
{you_notes}
[말투 규칙]
- 1인칭 내면 독백/서술: 문학적 평서체를 기본으로 하며, 자기 자신이나 독자가 아닌 특정한 "you"를 향한 집착적 호명은 자연스러운 반말 독백으로 처리한다.
- 연인/전 연인/친밀한 친구 사이: 이미 친밀한 관계로 보이면 반말을 기본으로 하되, 비꼼과 분노는 과장하지 않고 원문의 강도만큼 살린다.
- 초면/고객/직장/공식 상대: 실제 대화는 존댓말을 기본으로 한다. 속마음이 상대를 깔보는 경우에도 내면 독백과 발화 말투를 구분한다.
- 가족 사이: 부모-자녀, 형제자매는 한국어 가족관계에 맞춰 반말을 기본으로 하되, 소원하거나 공식적인 장면은 존댓말 가능성을 둔다.
- 상급자/경찰/의사/변호사/교사 등 권위자: 대화는 존댓말 또는 격식체를 우선한다.
- 위협/범죄/마피아/폭력 장면: 위계가 강한 쪽은 반말을 쓸 수 있고, 복종하거나 두려워하는 쪽은 존댓말을 쓸 수 있다.
- 성인 로맨스/갈등 장면: 선정적으로 확대하지 말고, 호칭과 말투는 관계의 친밀도와 권력 차이를 따라 자연스럽게 적용한다.
- 어린 인물/학생/부하가 성인/상급자에게 말할 때: 특별히 친밀하지 않으면 존댓말을 우선한다.
- 화자가 독자에게 직접 말을 거는 듯한 2인칭 서술: 한국어 독백처럼 자연스러운 반말/평서체를 쓰되, 설명문은 지나치게 구어체로 흐르지 않게 한다.
- 관계가 장면 중 변하면, 초반은 존댓말, 친밀 또는 갈등 고조 후에는 반말로 전환할 수 있다.

[주의할 호칭과 일관성]
- 인명은 한 책 안에서 같은 음역을 유지한다.
- 별명, 애칭, 모욕적 호칭은 원문의 정서 강도를 보존하되 한국어에서 어색하지 않게 옮긴다.
- 대화문의 말투와 내면 독백의 말투를 섞지 않는다.
- 불확실한 관계는 지나친 반말보다 존댓말을 우선하고, 반복되는 친밀 단서가 나오면 반말로 조정한다.

[고유명사 표기]
- 이 가이드는 웹 응답이 반복 실패해 로컬 휴리스틱으로 생성되어, 고유명사의 한글 표기를 확정하지 못했습니다. 번역 중 처음 등장하는 표기를 그대로 책 전체에서 유지하세요.
"""


TERMINOLOGY_GLOSSARY_LINE_RE = re.compile(r"^-?\s*([A-Z][A-Za-z.' -]{1,40}?)\s*(?:->|→)\s*([가-힣][가-힣 ]{0,20})\s*$")


def parse_terminology_glossary(guide: str) -> dict[str, str]:
    """Extract the "English Name -> 한글 표기" lines from the relationship guide's
    [고유명사 표기] section into a lookup table used to check translation consistency.

    Deliberately does not run the guide through normalize_chatgpt_web_copy first: that
    helper collapses all whitespace (including newlines) onto one line, which would merge
    every glossary entry together and break this line-by-line parse.
    """
    raw = guide.replace("\r\n", "\n").replace("\r", "\n")
    match = re.search(r"\[고유명사 표기\](.*?)(?:\n\s*\[|\Z)", raw, re.DOTALL)
    if not match:
        return {}
    glossary: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line_match = TERMINOLOGY_GLOSSARY_LINE_RE.match(line.strip())
        if not line_match:
            continue
        name, korean_form = line_match.group(1).strip(), line_match.group(2).strip()
        if name and korean_form:
            glossary[name] = korean_form
    return glossary


@dataclass
class TerminologyFinding:
    name: str
    expected_korean: str
    block_id: str
    translation_snippet: str


def check_terminology_consistency(
    blocks: list[SourceBlock],
    translations: dict[str, str],
    glossary: dict[str, str],
) -> list[TerminologyFinding]:
    """For each glossary name, find source blocks mentioning it and flag any translated
    block whose text doesn't contain the glossary's canonical Korean form - a likely sign
    the name was rendered inconsistently in that spot.
    """
    findings: list[TerminologyFinding] = []
    for name, korean_form in glossary.items():
        name_re = re.compile(rf"\b{re.escape(name)}\b")
        for block in blocks:
            if not name_re.search(block.text):
                continue
            translation = translations.get(block.id, "")
            if not translation:
                continue
            if korean_form not in translation:
                findings.append(
                    TerminologyFinding(
                        name=name,
                        expected_korean=korean_form,
                        block_id=block.id,
                        translation_snippet=translation[:160],
                    )
                )
    return findings


def write_terminology_consistency_report(
    *,
    out_dir: Path,
    glossary: dict[str, str],
    findings: list[TerminologyFinding],
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    status = "checked" if not findings else "needs_attention"
    report = {
        "status": status,
        "glossary": glossary,
        "finding_count": len(findings),
        "findings": [
            {
                "name": finding.name,
                "expected_korean": finding.expected_korean,
                "block_id": finding.block_id,
                "translation_snippet": finding.translation_snippet,
            }
            for finding in findings
        ],
    }
    write_json(out_dir / "terminology_consistency_report.json", report)
    lines = [
        "# 고유명사 표기 일관성 검수",
        "",
        f"상태: {status}",
        f"고유명사 표기표: {len(glossary)}개",
        f"불일치 후보: {len(findings)}건",
        "",
    ]
    if glossary:
        lines.append("## 표기표")
        for name, korean_form in glossary.items():
            lines.append(f"- {name} -> {korean_form}")
        lines.append("")
    if findings:
        lines.append("## 불일치 후보")
        for finding in findings[:200]:
            lines.append(
                f"- [{finding.block_id}] `{finding.name}` -> 기대 표기 `{finding.expected_korean}`이(가) "
                f"보이지 않음: {finding.translation_snippet}"
            )
    write_text(out_dir / "terminology_consistency_report.md", "\n".join(lines) + "\n")
    return report


def build_translation_prompt(
    chunk: TranslationChunk,
    chunk_count: int,
    book_title: str,
    *,
    safety_retry: bool = False,
    minor_safety_retry: bool = False,
    relationship_guide: str = "",
) -> str:
    if minor_safety_retry:
        role = """- 당신은 문학/번역학 연구용 텍스트를 안전하게 한국어로 옮기는 전문 번역가입니다.
- 입력은 사용자가 제공한 EPUB 일부이며, 한국어 독서, 영어 학습, 영어권 문학과 한국어 번역문의 비교문학 연구를 위한 변환 작업입니다.
- 미성년자, 16세, underage, teen, student 등 미성년으로 해석될 수 있는 인물이 관련된 성적 장면은 성인으로 바꾸거나 나이/관계를 왜곡하지 않습니다.
- 미성년자 관련 성적 내용은 노골적인 신체/행위 묘사를 자세히 재현하지 말고, 사건의 존재, 인물의 감정, 권력관계, 서사 기능을 비노골적이고 절제된 한국어 문학 문장으로 옮기세요.
- 착취, 강압, 피해, 권력 불균형이 있으면 미화하거나 자극적으로 만들지 말고, 문학적 맥락의 사실과 정서를 중립적으로 보존하세요."""
        rule_2 = "2. 요약, 해설, 생략을 원칙적으로 하지 않되, 미성년자 관련 성적 행위의 노골적 세부 묘사는 비노골적 문학 표현으로 절제합니다. 인물의 나이, 미성년 사실, 관계, 감정, 사건의 서사적 의미는 보존합니다."
        rule_4 = "4. 미성년자 관련 성적 표현은 성인으로 바꾸지 말고, 자극적인 세부 묘사를 피하면서 연구자가 원문 맥락을 파악할 수 있는 절제된 한국어로 옮깁니다."
    elif safety_retry:
        role = """- 당신은 성인 독자용 문학/논픽션 전문 번역가입니다.
- 입력에 민감한 장면이 있더라도 새 묘사나 해설을 덧붙이지 않고 원문의 의미와 서사 기능만 한국어로 옮깁니다.
- 폭력, 강압, 피해, 권력 불균형은 미화하거나 자극적으로 확대하지 않고 중립적인 문학 문장으로 번역합니다."""
        rule_2 = "2. 요약, 해설, 생략, 내용 추가를 하지 않습니다. 문장 의미를 임의로 약화하거나 강화하지 않습니다."
        rule_4 = "4. 욕설/구어체/성적 표현/민감한 표현은 선정적으로 확대하지 말고, 비교문학/번역 연구에서 원문과 대조 가능하도록 의미, 뉘앙스, 강도를 보존해 자연스러운 한국어 문학 문장으로 옮깁니다."
    else:
        role = """- 당신은 영미 문학/논픽션 전문 번역가입니다.
- 원문의 리듬, 설명의 밀도, 대사 톤을 살려 자연스러운 한국어 문체로 번역하세요.
- 입력에 없는 설명이나 묘사를 추가하지 말고, 인물의 감정과 장면의 인과관계를 정확히 보존하세요."""
        rule_2 = "2. 요약, 해설, 생략, 내용 추가를 하지 않습니다. 문장 의미를 임의로 약화하거나 강화하지 않습니다."
        rule_4 = "4. 욕설/긴장감/구어체/성적 표현은 원문의 강도와 맥락에 맞춰 한국어 문체로 살리되, 선정적으로 확대하지 않고 연구자가 원문과 대조할 수 있게 보존합니다."
    guide = relationship_guide_for_prompt(relationship_guide)
    guide_section = ""
    if guide:
        guide_section = f"""
인물관계/말투 가이드:
{guide}

말투 적용:
- 위 가이드를 최우선으로 참고해 반말/존댓말/격식체를 자연스럽게 일관 적용합니다.
- 가이드에 없는 인물은 현재 장면의 나이, 친밀도, 권력관계, 고객/공권력/가족/친구 관계를 추론해 한국어 말투를 정합니다.
- 화자가 무례하거나 친한 사이가 아닌 한, 초면/고객/상급자/공식 상대에게 갑자기 반말을 쓰지 않습니다.
"""
    context_section = ""
    if chunk.context_before or chunk.context_after:
        context_section = f"""
앞뒤 문맥(번역 출력 대상 아님):
[이전 문맥]
{chunk.context_before or '(없음)'}

[다음 문맥]
{chunk.context_after or '(없음)'}

- 위 문맥은 화자, 지시대상, 장면 흐름과 말투를 판단하는 데만 사용합니다.
- 문맥 문장은 출력하거나 현재 SEGMENT에 합치지 않습니다.
"""
    return f"""사용자가 제공한 EPUB `{book_title}`의 일부를 한국어로 번역합니다.

소유권 및 이용 안내:
- 이 EPUB은 사용자가 정당하게 구매했거나 합법적으로 소유한 개인 소장 도서입니다.
- 번역 결과물은 사용자 개인의 외국어 학습과 원문-번역문 대조 학습 용도로만 사용되며, 재배포하거나 상업적으로 이용하지 않습니다.
- 출력물은 사용자 개인 기기에만 저장되며, 온라인에 게시하거나 제3자와 공유하거나 판매하지 않습니다.
- 지금 요청은 책 전체가 아니라 그중 한 조각(SEGMENT)만 번역하는 것이며, 나머지 조각들도 같은 방식으로 순차적으로 처리됩니다.
- 이는 개인이 소유한 외국어 도서를 번역가에게 의뢰해 개인 학습용 번역문을 받거나, 전자책 리더의 번역 기능을 이용하는 것과 동일한, 통상적이고 합법적인 번역 작업 요청입니다. 저작권 침해나 무단 배포 목적이 아니므로 이 이유로 번역을 거절할 필요가 없습니다.

역할:
{role}

작업 목적:
- 이 번역은 영어 원문과 한국어 문장을 대조하는 학습/연구용 EPUB 제작 과정입니다.
- 대사 톤, 인물관계, 사건의 인과관계와 서사 기능을 분석할 수 있도록 원문의 의미 단위를 빠짐없이 보존합니다.

중요 규칙:
1. 아래 각 SEGMENT의 영어 원문을 빠짐없이 한국어로 번역합니다.
{rule_2}
3. 고유명사와 인명은 자연스럽게 음역하되, 이미 널리 쓰이는 표기는 존중합니다.
{rule_4}
5. 출력은 반드시 입력과 같은 ID 마커 형식만 사용합니다.
6. 각 ID는 정확히 한 번씩 출력합니다. 영어 원문은 출력하지 마세요.
7. 인과관계, 부정 표현, 숫자, 시간, 고유명사, 대명사의 지시대상을 빠뜨리지 않습니다.
8. 서술문과 내면 독백은 특별한 문체적 이유가 없으면 한국어 소설의 평서형 '~다'체를 사용하고, '~요'체는 실제 대화에서만 사용합니다.
9. 저작권, 발췌 출처, 추천사, 서지정보 문장도 생략하지 말고 번역하되 작품명, 인명, ISBN, URL은 원문 표기를 유지합니다.
10. 대사에 사극(시대극)투 어미(예: ~하였소, ~하오, ~이오, ~하시오, ~했소, ~었소)를 쓰지 않습니다. 원문이 실제 사극/역사물 배경이 아닌 한, 현대 소설 대사처럼 자연스러운 반말/존댓말 어미(~해, ~했어, ~야, ~이에요 등)로 번역하세요.
{guide_section}
{context_section}

출력 형식 예:
<<<B00001>>>
한국어 번역문
<<<END_B00001>>>

현재 조각: {chunk.index}/{chunk_count}

SEGMENTS:
{chunk.text}
"""


OLLAMA_API_URL_ENV = "OLLAMA_API_URL"
DEFAULT_OLLAMA_API_URL = "http://localhost:11434"
DEFAULT_OLLAMA_DRAFT_MODEL = "gemma4:26b"
DEFAULT_OLLAMA_TIMEOUT_SEC = 240


def ollama_api_url(args: argparse.Namespace) -> str:
    configured = getattr(args, "ollama_host", None)
    if configured:
        return str(configured).rstrip("/")
    return os.getenv(OLLAMA_API_URL_ENV, DEFAULT_OLLAMA_API_URL).rstrip("/")


def ollama_draft_enabled(args: argparse.Namespace) -> bool:
    return str(getattr(args, "draft_provider", "ollama") or "ollama").lower() == "ollama"


def ollama_server_available(args: argparse.Namespace) -> bool:
    try:
        request = urllib.request.Request(f"{ollama_api_url(args)}/api/tags")
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def build_ollama_draft_prompt(chunk: TranslationChunk, book_title: str) -> str:
    return f"""EPUB `{book_title}`의 일부를 한국어로 초벌 번역합니다.

규칙:
1. 아래 각 SEGMENT의 영어 원문을 빠짐없이 한국어로 번역합니다. 요약, 생략, 해설을 하지 않습니다.
2. 문체를 다듬는 것보다 의미, 인과관계, 대사 내용을 정확하게 옮기는 것을 우선합니다. 다음 단계에서 문체를 다듬을 것이므로 초벌 번역은 다소 투박해도 됩니다.
3. 출력은 반드시 입력과 같은 ID 마커 형식만 사용하고, 각 ID는 정확히 한 번씩 출력합니다. 영어 원문은 출력하지 마세요.
4. 고유명사와 인명은 자연스럽게 음역합니다.

출력 형식 예:
<<<B00001>>>
한국어 초벌 번역문
<<<END_B00001>>>

SEGMENTS:
{chunk.text}
"""


def call_ollama_generate(prompt: str, *, args: argparse.Namespace, timeout_sec: int = DEFAULT_OLLAMA_TIMEOUT_SEC) -> str:
    model = str(getattr(args, "ollama_model", None) or DEFAULT_OLLAMA_DRAFT_MODEL)
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        f"{ollama_api_url(args)}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Ollama 초벌 번역 요청에 실패했습니다: {exc}") from exc
    text = str(body.get("response") or "")
    if not text.strip():
        raise RuntimeError("Ollama 초벌 번역 응답이 비어 있습니다.")
    return text


def ollama_draft_translations(chunk: TranslationChunk, *, args: argparse.Namespace, book_title: str) -> dict[str, str]:
    prompt = build_ollama_draft_prompt(chunk, book_title)
    response = call_ollama_generate(prompt, args=args)
    drafts = parse_translation_response(response, chunk.block_ids)
    fill_passthrough_translations(drafts, chunk)
    return drafts


def ollama_draft_cache_path(work_dir: Path, chunk_index: int) -> Path:
    return work_dir / "ollama_drafts" / f"chunk_{chunk_index:04d}.json"


def load_ollama_draft(work_dir: Path, chunk_index: int) -> dict[str, str] | None:
    path = ollama_draft_cache_path(work_dir, chunk_index)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        translations = payload.get("translations")
        return translations if isinstance(translations, dict) else None
    except Exception:
        return None


def ensure_ollama_drafts(
    *,
    work_dir: Path,
    chunks: list[TranslationChunk],
    args: argparse.Namespace,
    book_title: str,
    heartbeat: ProgressHeartbeat | None,
) -> None:
    """Run the local Ollama draft pass straight through every chunk of the book, one after
    another, before the web provider (Gemini/ChatGPT) starts at all.

    Decoupled from the polish step on purpose: the web provider's pacing/retry delays used to
    block drafting of the next chunk (drafts were generated inline, one at a time, right
    before each web call). Running the whole book's draft pass up front means Ollama keeps
    working at its own local pace the entire time, and the web polish step that follows just
    reads whichever chunks already have a cached draft - it never waits on Ollama itself.
    A chunk that fails to draft (Ollama down, bad response, etc.) is simply skipped so the
    pass keeps moving through the rest of the book; that chunk's polish step later falls back
    to translating directly from English instead of refining a draft.
    """
    if not ollama_draft_enabled(args):
        return
    for chunk in chunks:
        translation_cache = chunk_translation_path(work_dir, chunk.index)
        if cached_chunk_is_complete(translation_cache, chunk.block_ids, chunk):
            continue
        draft_cache = ollama_draft_cache_path(work_dir, chunk.index)
        if draft_cache.exists():
            continue
        prefix = f"chunk_{chunk.index:04d}"
        label = f"초벌 번역 {chunk.index}/{len(chunks)}"
        try:
            drafts = ollama_draft_translations(chunk, args=args, book_title=book_title)
            write_json(draft_cache, {"chunk_index": chunk.index, "translations": drafts})
            beat_heartbeat(heartbeat, stage="ollama_draft_ready", label=label, section_prefix=prefix)
        except Exception as exc:  # noqa: BLE001 - keep drafting the rest of the book regardless
            beat_heartbeat(heartbeat, stage="ollama_draft_failed", label=label, section_prefix=prefix, detail=str(exc)[:300])


def build_polish_prompt(
    chunk: TranslationChunk,
    draft_translations: dict[str, str],
    chunk_count: int,
    book_title: str,
    *,
    safety_retry: bool = False,
    minor_safety_retry: bool = False,
    relationship_guide: str = "",
) -> str:
    base_prompt = build_translation_prompt(
        chunk,
        chunk_count,
        book_title,
        safety_retry=safety_retry,
        minor_safety_retry=minor_safety_retry,
        relationship_guide=relationship_guide,
    )
    source_by_id = chunk_source_texts(chunk)
    draft_segments = []
    for block_id in chunk.block_ids:
        draft_segments.append(
            f"<<<{block_id}>>>\n[원문]\n{source_by_id.get(block_id, '')}\n"
            f"[초벌 번역]\n{draft_translations.get(block_id, '')}\n<<<END_{block_id}>>>"
        )
    draft_section = "\n\n".join(draft_segments)
    polish_instructions = """
추가 작업 안내:
- 아래 SEGMENTS는 [원문]과 로컬 모델이 만든 [초벌 번역]을 함께 제공합니다.
- 초벌 번역을 그대로 베끼지 말고, 자연스러운 문학적 한국어 문체로 다듬어 완성하세요.
- 초벌 번역에 오역, 누락, 어색한 표현이 있으면 원문을 기준으로 바로잡습니다.
- 위에 안내된 인물관계/말투 가이드와 중요 규칙을 최우선으로 적용합니다.
- 출력은 초벌 번역이 아니라, 다듬어 완성한 최종 한국어 번역문이어야 합니다.
"""
    return base_prompt.replace(
        f"SEGMENTS:\n{chunk.text}",
        f"{polish_instructions}\nSEGMENTS ([원문]+[초벌 번역]):\n{draft_section}",
    )


def validate_chunk_translations(
    chunk: TranslationChunk,
    translations: dict[str, str],
    *,
    allow_non_explicit_compression: bool = False,
) -> dict:
    sources = extract_segment_sources(chunk.text)
    assessment = assess_translations(sources, translations)
    blocking = [
        finding
        for finding in assessment.findings
        if finding.severity == "severe"
        and not (allow_non_explicit_compression and finding.code == "likely_truncation")
    ]
    if blocking:
        details = "; ".join(
            f"{finding.block_id}:{finding.code}" for finding in blocking
        )
        raise RuntimeError(f"translation_quality_failed: {details[:800]}")
    return assessment.to_dict()


def parse_translation_response(response: str, expected_ids: list[str]) -> dict[str, str]:
    expected = set(expected_ids)
    translations: dict[str, str] = {}
    duplicates: set[str] = set()
    patterns = (
        re.compile(r"<<<(B\d+)>>>\s*(.*?)\s*<<<END_\1>>>", re.DOTALL),
        re.compile(r"\[\[\[BEGIN:(B\d+)\]\]\]\s*(.*?)\s*\[\[\[END:\1\]\]\]", re.DOTALL),
        # Gemini can render an angle-bracket opening marker as an empty HTML-like
        # element while leaving the closing marker visible. The closing ID still
        # makes this older response format unambiguous and safely recoverable.
        re.compile(r"<<>>\s*(.*?)\s*<<<END_(B\d+)>>>", re.DOTALL),
    )
    for pattern_index, pattern in enumerate(patterns):
        for match in pattern.finditer(response):
            if pattern_index == 2:
                block_id, translated = match.group(2), match.group(1)
            else:
                block_id, translated = match.group(1), match.group(2)
            if block_id not in expected:
                continue
            if block_id in translations:
                duplicates.add(block_id)
                continue
            translations[block_id] = clean_text(translated)
    if duplicates:
        raise RuntimeError(f"웹 번역 응답에 중복 번역 ID가 있습니다: {', '.join(sorted(duplicates)[:10])}")
    return translations


def chunk_source_texts(chunk: TranslationChunk) -> dict[str, str]:
    pattern = re.compile(r"<<<(B\d+)>>>\s*(.*?)\s*<<<END_\1>>>", re.DOTALL)
    return {
        match.group(1): clean_text(match.group(2))
        for match in pattern.finditer(chunk.text)
    }


def is_passthrough_source_text(text: str) -> bool:
    text = clean_text(text)
    return bool(text) and not re.search(r"[A-Za-z0-9가-힣]", text)


def fill_passthrough_translations(translations: dict[str, str], chunk: TranslationChunk) -> None:
    source_by_id = chunk_source_texts(chunk)
    for block_id in chunk.block_ids:
        if translations.get(block_id):
            continue
        source_text = source_by_id.get(block_id, "")
        if is_passthrough_source_text(source_text):
            translations[block_id] = source_text


def chunk_translation_path(work_dir: Path, chunk_index: int) -> Path:
    return work_dir / "translations" / f"chunk_{chunk_index:04d}.json"


def is_refusal_error(exc: Exception) -> bool:
    message = str(exc)
    lowered = message.lower()
    return (
        "번역 응답이 거절" in message
        or "사용 정책" in message
        or "policy" in lowered
        or "content can't be shown for safety reasons" in lowered
        or "content can’t be shown for safety reasons" in lowered
        or "model spec" in lowered
    )


MINOR_CONTEXT_MARKERS = (
    "minor",
    "underage",
    "under-aged",
    "child sexual",
    "sexual content involving minors",
    "teen sexual",
    "sixteen",
    "sixteen-year-old",
    "16-year-old",
    "16 year old",
    "16yo",
    "16 years old",
    "미성년",
    "미성년자",
    "청소년",
    "16세",
    "열여섯",
)

SENSITIVE_CONTEXT_MARKERS = (
    "sexual",
    "sex ",
    "naked",
    "nude",
    "genital",
    "intercourse",
    "molest",
    "rape",
    "assaulted",
    "성적",
    "성행위",
    "강간",
    "추행",
)


def chunk_has_minor_context(chunk: TranslationChunk) -> bool:
    lowered = normalize_chatgpt_web_copy(chunk.text).lower()
    has_minor = any(marker in lowered for marker in MINOR_CONTEXT_MARKERS) or bool(
        re.search(r"\b(?:1[0-7])\s*(?:-| )?(?:year[- ]old|years old|yo)\b", lowered)
    )
    return has_minor and any(marker in lowered for marker in SENSITIVE_CONTEXT_MARKERS)


def is_minor_context_refusal_error(exc: Exception, chunk: TranslationChunk | None = None) -> bool:
    message = normalize_chatgpt_web_copy(str(exc))
    lowered = message.lower()
    explicit_minor_refusal = any(marker in lowered for marker in MINOR_CONTEXT_MARKERS)
    return is_refusal_error(exc) and (explicit_minor_refusal or (chunk is not None and chunk_has_minor_context(chunk)))


def is_missing_translation_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "응답에서 누락되거나 빈 번역 ID" in message
        or "하위 번역에서 누락되거나 빈 ID" in message
        or "번역 누락 또는 빈 블록" in message
        or "중복 번역 ID" in message
    )


def is_prompt_interaction_error(exc: Exception) -> bool:
    """페이지가 열렸지만 프롬프트 입력창을 찾거나 채우지 못한 경우(서비스 거부/한도 배너와는 무관한 UI 상태 문제)."""
    message = str(exc)
    return (
        "프롬프트 입력에 실패" in message
        or "입력창을 찾지 못했습니다" in message
        or "프롬프트 입력창을 찾지 못" in message
    )


def classify_translation_web_error(
    exc: Exception,
    chunk: TranslationChunk | None = None,
) -> tuple[str, str]:
    message = str(exc)
    lowered = message.lower()
    provider_kind = web_provider_error_kind(message)
    provider_actions = {
        "usage_limit": "wait_for_limit_refresh",
        "rate_limit": "exponential_backoff",
        "temporary_service_error": "exponential_backoff",
        "network_error": "short_backoff",
        "session_expired": "refresh_session_then_retry",
        "account_unavailable": "pause_for_account_recovery",
        "region_unavailable": "pause_for_account_recovery",
        "prompt_too_long": "reduce_prompt_and_retry",
    }
    if provider_kind in provider_actions:
        return provider_kind, provider_actions[provider_kind]
    if is_minor_context_refusal_error(exc, chunk):
        return "minor_context_refusal", "non_explicit_minor_context_translation"
    if is_refusal_error(exc):
        return "content_refusal", "literary_prompt_then_subchunk_retry"
    if is_missing_translation_error(exc):
        return "missing_translation_ids", "fresh_chat_then_subchunk_retry"
    if "translation_quality_failed" in lowered:
        return "translation_quality_failure", "fresh_chat_then_subchunk_retry"
    if is_prompt_interaction_error(exc):
        return "prompt_interaction_failed", "reload_page_with_longer_settle_then_retry"
    if "message_id" in lowered:
        return "missing_message_id", "fresh_chat_retry"
    if "응답 본문" in message or "시간 초과" in message or "timeout" in lowered:
        return "timeout_or_empty_response", "fresh_chat_retry_with_backoff"
    if "로그인" in message or "세션이 만료" in message or "log in" in lowered or "session expired" in lowered:
        return "session_expired", "refresh_session_then_retry"
    return "unknown_web_provider_error", "record_and_retry_conservatively"


def should_subchunk_retry_error(exc: Exception) -> bool:
    if is_web_provider_pause_error(exc):
        return False
    kind, _action = classify_translation_web_error(exc)
    return kind in {
        "content_refusal",
        "minor_context_refusal",
        "missing_translation_ids",
        "translation_quality_failure",
        "prompt_too_long",
    }


def append_adaptive_error_event(
    work_dir: Path,
    *,
    prefix: str,
    label: str,
    attempt: int,
    error: Exception,
    chunk: TranslationChunk | None = None,
) -> None:
    kind, action = classify_translation_web_error(error, chunk)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prefix": prefix,
        "label": label,
        "attempt": attempt,
        "kind": kind,
        "action": action,
        "error": str(error)[:1000],
    }
    path = work_dir / "adaptive_error_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def split_chunk_for_safety_retry(chunk: TranslationChunk, max_chars: int) -> list[TranslationChunk]:
    segments: list[SourceBlock] = []
    pattern = re.compile(r"<<<(B\d+)>>>\s*(.*?)\s*<<<END_\1>>>", re.DOTALL)
    for match in pattern.finditer(chunk.text):
        segments.append(SourceBlock(id=match.group(1), text=clean_text(match.group(2))))
    if not segments:
        raise RuntimeError(f"chunk_{chunk.index:04d} 하위 분할 대상 SEGMENT를 찾지 못했습니다.")
    return build_chunks(segments, max_chars)


def load_translation_cache(work_dir: Path) -> dict[str, str]:
    translations: dict[str, str] = {}
    final_chunk_pattern = re.compile(r"chunk_\d{4}\.json$")
    for path in sorted((work_dir / "translations").glob("chunk_*.json")):
        if not final_chunk_pattern.fullmatch(path.name):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for block_id, text in payload.get("translations", {}).items():
            translations[block_id] = text
    return translations


def cached_chunk_is_complete(path: Path, block_ids: list[str], chunk: TranslationChunk | None = None) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    cached = payload.get("translations", {})
    if int(payload.get("pipeline_version") or 0) < MINIMUM_ACCEPTED_CACHE_VERSION:
        return False
    if not all(cached.get(block_id) for block_id in block_ids):
        return False
    if chunk is not None:
        try:
            validate_chunk_translations(
                chunk,
                cached,
                allow_non_explicit_compression=chunk_has_minor_context(chunk),
            )
        except RuntimeError:
            return False
    return True


def is_separator_text(text: str) -> bool:
    compact = clean_text(text)
    if not compact:
        return False
    return bool(re.fullmatch(r"[\*\-–—_~·•\s]{1,120}", compact))


def fill_separator_translations(blocks: list[SourceBlock], translations: dict[str, str]) -> None:
    for block in blocks:
        if not translations.get(block.id) and is_separator_text(block.text):
            translations[block.id] = block.text


def write_json(path: Path, payload: object) -> None:
    atomic_write_json(path, payload, trailing_newline=True)


def write_text(path: Path, text: str) -> None:
    atomic_write_text(path, text.rstrip() + "\n")


class WebProviderError(RuntimeError):
    """Structured error raised by a browser-based translation provider."""

    def __init__(self, provider: str, kind: str, action: str, message: str):
        self.provider = provider
        self.kind = kind
        self.action = action
        self.provider_message = message
        super().__init__(
            f"{provider.title()} error_kind={kind} retry_action={action}: {message[:700]}"
        )


class WebServiceLimitError(WebProviderError):
    """Raised when a provider requires a batch-level pause."""


LEGACY_PROVIDER_ACCOUNT_BLOCK_MARKERS = (
    "unusual activity",
    "suspicious activity",
    "account has been restricted",
    "비정상적인 접근",
    "비정상적 접근",
    "의심스러운 활동",
    "계정이 제한",
)

LEGACY_PROVIDER_USAGE_LIMIT_MARKERS = (
    "too many requests",
    "rate limit",
    "usage limit",
    "message limit",
    "request limit",
    "limit exceeded",
    "limit reached",
    "you've reached your limit",
    "you’ve reached your limit",
    "you have reached your limit",
    "come back later",
    "한도초과",
    "한도 초과",
    "사용량 한도",
    "메시지 한도",
    "요청 한도",
    "한도에 도달",
    "resource has been exhausted",
)

WEB_PROVIDER_PAUSE_KINDS = {
    "usage_limit",
    "rate_limit",
    "session_expired",
    "account_unavailable",
    "region_unavailable",
}

WEB_REFUSAL_MARKERS = (
    "content can't be shown for safety reasons",
    "content can’t be shown for safety reasons",
    "i can't help with that",
    "i can’t help with that",
    "i'm unable to help",
    "i’m unable to help",
    "i cannot assist",
    "요청하신 내용에는 도움을 드릴 수 없",
    "해당 요청에는 응답할 수 없",
)


def active_web_provider(args: argparse.Namespace) -> str:
    provider = str(getattr(args, "web_provider", "gemini") or "gemini").lower()
    return provider if provider in WEB_PROVIDERS else "gemini"


def is_translation_web_refusal_response(response: str, args: argparse.Namespace) -> bool:
    if is_chatgpt_web_refusal_response(response):
        return True
    if (
        re.search(r"<<<B\d+>>>", response)
        and re.search(r"<<<END_B\d+>>>", response)
    ) or (
        re.search(r"\[\[\[BEGIN:B\d+\]\]\]", response)
        and re.search(r"\[\[\[END:B\d+\]\]\]", response)
    ):
        return False
    lowered = normalize_chatgpt_web_copy(response).lower()
    return any(marker in lowered for marker in WEB_REFUSAL_MARKERS)


def web_provider_error_kind(text: str) -> str | None:
    normalized = normalize_chatgpt_web_copy(text)
    lowered = normalized.lower()
    explicit = re.search(r"error_kind=([a-z_]+)", lowered)
    if explicit:
        return explicit.group(1)
    if (
        re.search(r"<<<B\d+>>>", normalized)
        and re.search(r"<<<END_B\d+>>>", normalized)
    ) or (
        re.search(r"\[\[\[BEGIN:B\d+\]\]\]", normalized)
        and re.search(r"\[\[\[END:B\d+\]\]\]", normalized)
    ):
        return None
    if any(marker in lowered for marker in LEGACY_PROVIDER_ACCOUNT_BLOCK_MARKERS):
        return "account_unavailable"
    if any(marker in lowered for marker in LEGACY_PROVIDER_USAGE_LIMIT_MARKERS):
        return "usage_limit"
    notice = classify_gemini_web_notice_text(normalized)
    if notice is not None:
        return notice.kind
    return None


def raise_if_web_provider_error(response: str, provider: str) -> None:
    kind = web_provider_error_kind(response)
    if not kind:
        return
    preview = normalized_file_text(response)[:220].replace("\n", " ")
    action = classify_translation_web_error(RuntimeError(f"error_kind={kind}: {preview}"))[1]
    error_type = WebServiceLimitError if kind in WEB_PROVIDER_PAUSE_KINDS else WebProviderError
    raise error_type(provider, kind, action, preview)


def is_web_provider_pause_error(exc: Exception) -> bool:
    if isinstance(exc, WebServiceLimitError):
        return True
    return web_provider_error_kind(str(exc)) in WEB_PROVIDER_PAUSE_KINDS


def web_provider_retry_sleep_seconds(exc: Exception, attempt: int) -> int:
    kind, _action = classify_translation_web_error(exc)
    if kind == "network_error":
        return min(30, 2 ** max(1, attempt))
    if kind == "temporary_service_error":
        return min(180, 5 * (2 ** max(0, attempt - 1)))
    if kind == "timeout_or_empty_response":
        return min(30, 3 * attempt)
    if kind == "prompt_interaction_failed":
        return min(45, 5 * attempt)
    return min(20, 2 * attempt)


def request_web_translation(
    *,
    context,
    timeout_error_cls,
    args: argparse.Namespace,
    prompt: str,
    refusal_retry_prompt: str | None = None,
    heartbeat: ProgressHeartbeat | None,
    label: str,
    prefix: str,
    work_dir: Path | None = None,
) -> tuple[str, str]:
    last_error: Exception | None = None
    active_prompt = prompt
    provider = active_web_provider(args)
    consecutive_temporary_errors = 0
    for attempt in range(1, web_max_attempts(args) + 1):
        page = None
        try:
            page = context.new_page()
            beat_heartbeat(heartbeat, stage="translation_attempt_start", label=label, section_prefix=prefix, attempt=attempt)
            if provider == "gemini":
                prepare_gemini_web_page(page, timeout_error_cls=timeout_error_cls, heartbeat=heartbeat, label=label, section_prefix=prefix, attempt=attempt)
                web_prompt = translation_prompt_for_provider(active_prompt, provider)
                previous_response_count, previous_listen_count = send_gemini_web_prompt(
                    page,
                    web_prompt,
                    timeout_error_cls=timeout_error_cls,
                    heartbeat=heartbeat,
                    label=label,
                    section_prefix=prefix,
                    attempt=attempt,
                )
                response = wait_for_gemini_web_response(
                    page,
                    previous_response_count=previous_response_count,
                    previous_listen_count=previous_listen_count,
                    timeout_sec=args.request_timeout_sec,
                    heartbeat=heartbeat,
                    label=label,
                    section_prefix=prefix,
                    attempt=attempt,
                )
                conversation_id = extract_gemini_web_conversation_id(page.url)
            else:
                prepare_chatgpt_web_page(page, timeout_error_cls=timeout_error_cls, heartbeat=heartbeat, label=label, section_prefix=prefix, attempt=attempt)
                send_chatgpt_web_prompt(page, active_prompt, timeout_error_cls=timeout_error_cls, heartbeat=heartbeat, label=label, section_prefix=prefix, attempt=attempt)
                message_id, response = wait_for_chatgpt_web_response(page, timeout_sec=args.request_timeout_sec, heartbeat=heartbeat, label=label, section_prefix=prefix, attempt=attempt)
                conversation_id = extract_chatgpt_conversation_id(page.url)
                if not message_id:
                    raise RuntimeError("웹 번역 응답의 message_id를 찾지 못했습니다.")
            if not normalized_file_text(response):
                raise RuntimeError(f"{provider.title()} 번역 응답이 비어 있습니다.")
            raise_if_web_provider_error(response, provider)
            if is_translation_web_refusal_response(response, args):
                preview = normalized_file_text(response)[:200].replace("\n", " ")
                raise RuntimeError(f"{provider.title()} 번역 응답이 거절되었습니다: {preview}")
            if not conversation_id:
                conversation_id = "missing-conversation-id"
            beat_heartbeat(heartbeat, stage="translation_response_received", label=label, section_prefix=prefix, attempt=attempt)
            return conversation_id, response
        except Exception as exc:
            last_error = exc
            beat_heartbeat(heartbeat, stage="translation_attempt_error", label=label, section_prefix=prefix, attempt=attempt, detail=str(exc)[:300])
            if is_web_provider_pause_error(exc) or web_provider_error_kind(str(exc)) == "prompt_too_long":
                raise
            error_kind, _action = classify_translation_web_error(exc)
            consecutive_temporary_errors = consecutive_temporary_errors + 1 if error_kind == "temporary_service_error" else 0
            if (
                work_dir is not None
                and consecutive_temporary_errors >= GEMINI_TEMP_ERROR_BURST_THRESHOLD
                and overnight_fallback_active(args, provider)
            ):
                mark_gemini_temporarily_down(provider_fallback_state_dir(args, work_dir))
                raise OvernightProviderSwitch("gemini_outage") from exc
            if is_refusal_error(exc) and refusal_retry_prompt and active_prompt != refusal_retry_prompt:
                active_prompt = refusal_retry_prompt
                beat_heartbeat(
                    heartbeat,
                    stage="translation_literary_retry_prompt",
                    label=label,
                    section_prefix=prefix,
                    attempt=attempt,
                    detail="refusal_detected; switched to literary context prompt",
                )
            sleep_sec = web_provider_retry_sleep_seconds(exc, attempt)
            beat_heartbeat(
                heartbeat,
                stage="translation_retry_sleep",
                label=label,
                section_prefix=prefix,
                attempt=attempt,
                detail=f"sleep_sec={sleep_sec}; error={str(exc)[:240]}",
            )
            time.sleep(sleep_sec)
        finally:
            if page is not None:
                close_page_quietly(page)
    if last_error:
        raise last_error
    raise RuntimeError(f"{provider.title()} 웹 번역에 실패했습니다.")


def request_web_translation_on_prepared_page(
    *,
    page,
    timeout_error_cls,
    args: argparse.Namespace,
    prompt: str,
    heartbeat: ProgressHeartbeat | None,
    label: str,
    prefix: str,
    attempt: int,
) -> tuple[str, str]:
    provider = active_web_provider(args)
    if provider == "gemini":
        web_prompt = translation_prompt_for_provider(prompt, provider)
        previous_response_count, previous_listen_count = send_gemini_web_prompt(
            page,
            web_prompt,
            timeout_error_cls=timeout_error_cls,
            heartbeat=heartbeat,
            label=label,
            section_prefix=prefix,
            attempt=attempt,
        )
        response = wait_for_gemini_web_response(
            page,
            previous_response_count=previous_response_count,
            previous_listen_count=previous_listen_count,
            timeout_sec=args.request_timeout_sec,
            heartbeat=heartbeat,
            label=label,
            section_prefix=prefix,
            attempt=attempt,
        )
        conversation_id = extract_gemini_web_conversation_id(page.url)
    else:
        previous_message_id, _ = read_last_chatgpt_web_response(page)
        send_chatgpt_web_prompt(
            page,
            prompt,
            timeout_error_cls=timeout_error_cls,
            heartbeat=heartbeat,
            label=label,
            section_prefix=prefix,
            attempt=attempt,
        )
        message_id, response = wait_for_new_legacy_web_response(
            page,
            previous_message_id=previous_message_id,
            timeout_sec=args.request_timeout_sec,
            heartbeat=heartbeat,
            label=label,
            section_prefix=prefix,
            attempt=attempt,
        )
        conversation_id = extract_chatgpt_conversation_id(page.url)
        if not message_id:
            raise RuntimeError("웹 번역 응답의 message_id를 찾지 못했습니다.")
    if not normalized_file_text(response):
        raise RuntimeError(f"{provider.title()} 번역 응답이 비어 있습니다.")
    raise_if_web_provider_error(response, provider)
    if is_translation_web_refusal_response(response, args):
        preview = normalized_file_text(response)[:200].replace("\n", " ")
        raise RuntimeError(f"{provider.title()} 번역 응답이 거절되었습니다: {preview}")
    if not conversation_id:
        conversation_id = "missing-conversation-id"
    beat_heartbeat(heartbeat, stage="translation_response_received", label=label, section_prefix=prefix, attempt=attempt)
    return conversation_id, response


def wait_for_new_legacy_web_response(
    page,
    *,
    previous_message_id: str,
    timeout_sec: int,
    heartbeat: ProgressHeartbeat | None = None,
    label: str | None = None,
    section_prefix: str | None = None,
    attempt: int | None = None,
) -> tuple[str, str]:
    """Track a new response for the optional legacy web-provider backend."""
    deadline = time.monotonic() + timeout_sec
    last_message_id = ""
    last_text = ""
    stable_polls = 0
    empty_polls = 0
    if section_prefix and section_prefix.startswith("chunk_"):
        max_empty_polls = max(40, min(120, timeout_sec // 10))
    else:
        max_empty_polls = max(10, min(20, timeout_sec // 15))

    while time.monotonic() < deadline:
        handle_chatgpt_web_page_notices(
            page,
            heartbeat=heartbeat,
            label=label,
            section_prefix=section_prefix,
            attempt=attempt,
            max_wait_sec=max(5, int(deadline - time.monotonic())),
        )
        message_id, text = read_last_chatgpt_web_response(page)
        normalized = normalize_chatgpt_web_copy(text)
        if previous_message_id and message_id == previous_message_id:
            normalized = ""
        empty_polls = empty_polls + 1 if not normalized else 0
        beat_heartbeat(
            heartbeat,
            stage="wait_for_response",
            label=label,
            section_prefix=section_prefix,
            attempt=attempt,
            detail=f"stable_polls={stable_polls} empty_polls={empty_polls} chars={len(normalized)}",
        )
        if message_id and normalized and message_id == last_message_id and normalized == last_text:
            stable_polls += 1
        else:
            last_message_id = message_id
            last_text = normalized
            stable_polls = 0

        if last_message_id and last_message_id != previous_message_id and last_text and stable_polls >= 3:
            return last_message_id, last_text
        if empty_polls >= max_empty_polls:
            raise TimeoutError("웹 번역 응답 본문이 시작되지 않아 재시도합니다.")

        page.wait_for_timeout(3000)

    raise TimeoutError("웹 번역 응답 완료를 기다리다 시간 초과되었습니다.")


def ensure_relationship_guide(
    *,
    context,
    timeout_error_cls,
    args: argparse.Namespace,
    work_dir: Path,
    book_title: str,
    creator: str,
    blocks: list[SourceBlock],
    heartbeat: ProgressHeartbeat | None,
) -> str:
    path = relationship_guide_path(work_dir)
    if path.exists():
        guide = path.read_text(encoding="utf-8").strip()
        ok, reason = relationship_guide_is_complete(guide)
        metadata_path = work_dir / "relationship_guide.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        except Exception:
            metadata = {}
        guide_version = int(metadata.get("guide_version") or 0)
        if ok and guide_version >= RELATIONSHIP_GUIDE_VERSION:
            beat_heartbeat(heartbeat, stage="relationship_guide_cached", detail=f"chars={len(guide)}")
            return guide
        if ok:
            reason = f"outdated guide version: {guide_version} < {RELATIONSHIP_GUIDE_VERSION}"
        beat_heartbeat(heartbeat, stage="relationship_guide_cache_invalid", detail=reason)

    prompt = build_relationship_guide_prompt(book_title, creator, blocks)
    write_text(work_dir / "prompts" / "relationship_guide_prompt.txt", prompt)
    guide_args = SimpleNamespace(**vars(args))
    guide_args.request_timeout_sec = min(args.request_timeout_sec, 240)
    guide_args.web_max_attempts = min(web_max_attempts(args), 2)
    last_reason = ""
    for guide_attempt in range(1, 3):
        attempt_prompt = prompt
        if guide_attempt > 1:
            attempt_prompt += f"""

이전 응답은 불완전했습니다: {last_reason}
이번에는 예고 문장 없이 완성된 가이드만 출력하세요. 반드시 [인물관계 요약], [말투 규칙], [주의할 호칭과 일관성] 제목을 포함하세요.
"""
            write_text(work_dir / "prompts" / f"relationship_guide_retry_{guide_attempt:02d}_prompt.txt", attempt_prompt)
        beat_heartbeat(
            heartbeat,
            stage="relationship_guide_start",
            label="인물관계/말투 조사",
            section_prefix="relationship_guide",
            attempt=guide_attempt,
        )
        try:
            conversation_id, response = request_web_translation(
                context=context,
                timeout_error_cls=timeout_error_cls,
                args=guide_args,
                prompt=attempt_prompt,
                heartbeat=heartbeat,
                label="인물관계/말투 조사",
                prefix="relationship_guide",
            )
        except Exception as exc:  # noqa: BLE001 - fall back to a conservative local guide if web analysis stalls.
            if is_web_provider_pause_error(exc):
                raise
            last_reason = str(exc)
            beat_heartbeat(
                heartbeat,
                stage="relationship_guide_request_error",
                label="인물관계/말투 조사",
                section_prefix="relationship_guide",
                attempt=guide_attempt,
                detail=last_reason[:300],
            )
            time.sleep(5 * guide_attempt)
            continue
        guide = normalized_file_text(response).strip()
        write_text(work_dir / "responses" / f"relationship_guide_response_{guide_attempt:02d}.txt", response)
        write_text(work_dir / "responses" / "relationship_guide_response.txt", response)
        ok, reason = relationship_guide_is_complete(guide)
        if not ok:
            last_reason = reason
            beat_heartbeat(
                heartbeat,
                stage="relationship_guide_incomplete",
                label="인물관계/말투 조사",
                section_prefix="relationship_guide",
                attempt=guide_attempt,
                detail=reason,
            )
            time.sleep(5 * guide_attempt)
            continue
        write_text(path, guide)
        write_json(
            work_dir / "relationship_guide.json",
            {
                "book_title": book_title,
                "creator": creator,
                "conversation_id": conversation_id,
                "guide_version": RELATIONSHIP_GUIDE_VERSION,
                "chars": len(guide),
                "validation": reason,
            },
        )
        beat_heartbeat(heartbeat, stage="relationship_guide_complete", label="인물관계/말투 조사", detail=f"chars={len(guide)}")
        return guide
    fallback = build_local_relationship_guide(book_title, creator, blocks)
    ok, reason = relationship_guide_is_complete(fallback)
    if not ok:
        raise RuntimeError(f"인물관계/말투 가이드가 불완전합니다: {last_reason}; fallback={reason}")
    write_text(path, fallback)
    write_text(work_dir / "responses" / "relationship_guide_local_fallback.txt", fallback)
    write_json(
        work_dir / "relationship_guide.json",
        {
            "book_title": book_title,
            "creator": creator,
            "conversation_id": "local-fallback-after-web-guide-failure",
            "guide_version": RELATIONSHIP_GUIDE_VERSION,
            "chars": len(fallback),
            "validation": reason,
            "previous_failure": last_reason,
        },
    )
    beat_heartbeat(
        heartbeat,
        stage="relationship_guide_local_fallback",
        label="인물관계/말투 조사",
        detail=f"chars={len(fallback)} previous_failure={last_reason}",
    )
    return fallback


def close_page_quietly(page) -> None:
    try:
        page.close()
    except Exception:
        pass


def pace_web_requests(
    args: argparse.Namespace,
    heartbeat: ProgressHeartbeat | None,
    *,
    label: str,
    prefix: str,
    index: int,
) -> None:
    base_delay = max(0.0, float(args.inter_request_delay_sec))
    if base_delay <= 0:
        return
    delay = base_delay + (index % 3)
    beat_heartbeat(
        heartbeat,
        stage="translation_request_pacing",
        label=label,
        section_prefix=prefix,
        detail=f"sleep_sec={delay:.1f}",
    )
    time.sleep(delay)


def subchunk_translation_path(work_dir: Path, prefix: str) -> Path:
    return work_dir / "translations" / "parts" / f"{prefix}.json"


def translate_refused_chunk_in_subchunks(
    *,
    context,
    timeout_error_cls,
    args: argparse.Namespace,
    work_dir: Path,
    book_title: str,
    relationship_guide: str,
    chunk: TranslationChunk,
    chunk_count: int,
    heartbeat: ProgressHeartbeat | None,
    fallback_reason: str = "content_refusal",
) -> None:
    fallback_max_chars = max(700, min(1200, args.max_chars_per_chunk // 5))
    subchunks = split_chunk_for_safety_retry(chunk, fallback_max_chars)
    combined_translations: dict[str, str] = {}
    conversation_ids: list[str] = []
    start_stage = (
        "translation_refusal_subchunk_start"
        if fallback_reason == "content_refusal"
        else "translation_adaptive_subchunk_start"
    )
    complete_stage = (
        "translation_refusal_subchunk_complete"
        if fallback_reason == "content_refusal"
        else "translation_adaptive_subchunk_complete"
    )
    beat_heartbeat(
        heartbeat,
        stage=start_stage,
        label=f"번역 {chunk.index}/{chunk_count}",
        section_prefix=f"chunk_{chunk.index:04d}",
        detail=f"reason={fallback_reason} subchunks={len(subchunks)} max_chars={fallback_max_chars}",
    )
    for sub_index, subchunk in enumerate(subchunks, start=1):
        prefix = f"chunk_{chunk.index:04d}_part_{sub_index:02d}"
        label = f"번역 {chunk.index}/{chunk_count} 하위 {sub_index}/{len(subchunks)}"
        part_cache = subchunk_translation_path(work_dir, prefix)
        if cached_chunk_is_complete(part_cache, subchunk.block_ids, subchunk):
            payload = json.loads(part_cache.read_text(encoding="utf-8"))
            combined_translations.update(payload["translations"])
            conversation_ids.append(str(payload.get("conversation_id") or "cached-subchunk"))
            beat_heartbeat(
                heartbeat,
                stage="translation_subchunk_cached",
                label=label,
                section_prefix=prefix,
                detail=f"blocks={len(subchunk.block_ids)}",
            )
            continue
        prompt = build_translation_prompt(
            subchunk,
            len(subchunks),
            book_title,
            safety_retry=fallback_reason != "minor_context_refusal",
            minor_safety_retry=fallback_reason == "minor_context_refusal" or chunk_has_minor_context(subchunk),
            relationship_guide=relationship_guide,
        )
        write_text(work_dir / "prompts" / f"{prefix}_prompt.txt", prompt)
        last_error: Exception | None = None
        for quality_attempt in range(1, 4):
            try:
                conversation_id, response = request_web_translation(
                    context=context,
                    timeout_error_cls=timeout_error_cls,
                    args=args,
                    prompt=prompt,
                    heartbeat=heartbeat,
                    label=label,
                    prefix=prefix,
                    work_dir=work_dir,
                )
                write_text(work_dir / "responses" / f"{prefix}_response.txt", response)
                translations = parse_translation_response(response, subchunk.block_ids)
                fill_passthrough_translations(translations, subchunk)
                missing = [block_id for block_id in subchunk.block_ids if not translations.get(block_id)]
                if missing:
                    raise RuntimeError(f"{prefix} 응답에서 누락되거나 빈 번역 ID: {', '.join(missing[:10])}")
                quality = validate_chunk_translations(
                    subchunk,
                    translations,
                    allow_non_explicit_compression=chunk_has_minor_context(subchunk),
                )
                write_json(
                    part_cache,
                    {
                        "chunk_index": subchunk.index,
                        "conversation_id": conversation_id,
                        "pipeline_version": TRANSLATION_PIPELINE_VERSION,
                        "parent_chunk_index": chunk.index,
                        "part_index": sub_index,
                        "block_ids": subchunk.block_ids,
                        "quality": quality,
                        "translations": translations,
                    },
                )
                break
            except Exception as exc:
                last_error = exc
                append_adaptive_error_event(
                    work_dir,
                    prefix=prefix,
                    label=label,
                    attempt=quality_attempt,
                    error=exc,
                    chunk=subchunk,
                )
                kind, action = classify_translation_web_error(exc, subchunk)
                beat_heartbeat(
                    heartbeat,
                    stage="translation_subchunk_error",
                    label=label,
                    section_prefix=prefix,
                    attempt=quality_attempt,
                    detail=f"kind={kind}; action={action}; error={str(exc)[:220]}",
                )
                if isinstance(exc, OvernightProviderSwitch) or is_web_provider_pause_error(exc) or quality_attempt >= 3:
                    raise
                time.sleep(web_provider_retry_sleep_seconds(exc, quality_attempt))
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError(f"{prefix} Gemini 하위 번역에 실패했습니다.")
        combined_translations.update(translations)
        conversation_ids.append(conversation_id)
        if sub_index < len(subchunks):
            pace_web_requests(
                args,
                heartbeat,
                label=label,
                prefix=prefix,
                index=sub_index,
            )

    missing = [block_id for block_id in chunk.block_ids if not combined_translations.get(block_id)]
    if missing:
        raise RuntimeError(f"chunk_{chunk.index:04d} 하위 번역에서 누락되거나 빈 ID: {', '.join(missing[:10])}")
    quality = validate_chunk_translations(
        chunk,
        combined_translations,
        allow_non_explicit_compression=chunk_has_minor_context(chunk),
    )
    write_json(
        chunk_translation_path(work_dir, chunk.index),
        {
            "chunk_index": chunk.index,
            "chunk_count": chunk_count,
            "conversation_id": "+".join(conversation_ids) or "subchunk-fallback",
            "pipeline_version": TRANSLATION_PIPELINE_VERSION,
            "fallback": f"{fallback_reason}_subchunks",
            "block_ids": chunk.block_ids,
            "quality": quality,
            "translations": {block_id: combined_translations[block_id] for block_id in chunk.block_ids},
        },
    )
    beat_heartbeat(
        heartbeat,
        stage=complete_stage,
        label=f"번역 {chunk.index}/{chunk_count}",
        section_prefix=f"chunk_{chunk.index:04d}",
        detail=f"reason={fallback_reason} subchunks={len(subchunks)}",
    )


# temporary_service_error(예: Gemini 1095 배너)가 연달아 발생하면 짧은 지수 백오프로는
# 서비스 부하가 해소되지 않는 경우가 많아, 일정 횟수 연속 실패 시 긴 냉각 시간을 둔다.
GEMINI_TEMP_ERROR_BURST_THRESHOLD = 3
GEMINI_TEMP_ERROR_COOLDOWN_SEC = 300


def translate_missing_chunks_reusing_conversations(
    *,
    context,
    timeout_error_cls,
    args: argparse.Namespace,
    work_dir: Path,
    book_title: str,
    relationship_guide: str,
    chunks: list[TranslationChunk],
    heartbeat: ProgressHeartbeat | None,
) -> None:
    chunk_index = 0
    chunks_per_conversation = max(1, args.chunks_per_conversation)
    consecutive_temporary_errors = 0
    while chunk_index < len(chunks):
        page = context.new_page()
        prepared = False
        completed_on_page = 0
        try:
            while chunk_index < len(chunks) and completed_on_page < chunks_per_conversation:
                chunk = chunks[chunk_index]
                out_path = chunk_translation_path(work_dir, chunk.index)
                if cached_chunk_is_complete(out_path, chunk.block_ids, chunk):
                    chunk_index += 1
                    continue

                prefix = f"chunk_{chunk.index:04d}"
                minor_mode = chunk_has_minor_context(chunk)
                prompt = None
                used_ollama_draft = False
                if ollama_draft_enabled(args):
                    draft_translations = load_ollama_draft(work_dir, chunk.index)
                    if draft_translations is not None:
                        prompt = build_polish_prompt(
                            chunk,
                            draft_translations,
                            len(chunks),
                            book_title,
                            minor_safety_retry=minor_mode,
                            relationship_guide=relationship_guide,
                        )
                        used_ollama_draft = True
                if prompt is None:
                    prompt = build_translation_prompt(
                        chunk,
                        len(chunks),
                        book_title,
                        minor_safety_retry=minor_mode,
                        relationship_guide=relationship_guide,
                    )
                write_text(work_dir / "prompts" / f"{prefix}_prompt.txt", prompt)
                label = f"번역 {chunk.index}/{len(chunks)}"
                last_error: Exception | None = None
                using_safety_retry_prompt = minor_mode
                using_minor_safety_prompt = minor_mode
                fallback_after_attempts: Exception | None = None
                chunk_completed = False
                for attempt in range(1, web_max_attempts(args) + 1):
                    try:
                        if not prepared:
                            prepare_translation_web_page(
                                page,
                                timeout_error_cls=timeout_error_cls,
                                args=args,
                                heartbeat=heartbeat,
                                label=label,
                                section_prefix=prefix,
                                attempt=attempt,
                            )
                            prepared = True
                        beat_heartbeat(
                            heartbeat,
                            stage="translation_attempt_start",
                            label=label,
                            section_prefix=prefix,
                            attempt=attempt,
                        )
                        conversation_id, response = request_web_translation_on_prepared_page(
                            page=page,
                            timeout_error_cls=timeout_error_cls,
                            args=args,
                            prompt=prompt,
                            heartbeat=heartbeat,
                            label=label,
                            prefix=prefix,
                            attempt=attempt,
                        )
                        write_text(work_dir / "responses" / f"{prefix}_response.txt", response)
                        translations = parse_translation_response(response, chunk.block_ids)
                        fill_passthrough_translations(translations, chunk)
                        missing = [block_id for block_id in chunk.block_ids if not translations.get(block_id)]
                        if missing:
                            if is_translation_web_refusal_response(response, args):
                                preview = normalized_file_text(response)[:200].replace("\n", " ")
                                raise RuntimeError(f"{active_web_provider(args).title()} 번역 응답이 거절되었습니다: {preview}")
                            raise RuntimeError(f"{prefix} 응답에서 누락되거나 빈 번역 ID: {', '.join(missing[:10])}")
                        quality = validate_chunk_translations(
                            chunk,
                            translations,
                            allow_non_explicit_compression=minor_mode,
                        )
                        write_json(
                            out_path,
                            {
                                "chunk_index": chunk.index,
                                "chunk_count": len(chunks),
                                "conversation_id": conversation_id,
                                "pipeline_version": TRANSLATION_PIPELINE_VERSION,
                                "block_ids": chunk.block_ids,
                                "quality": quality,
                                "translations": translations,
                                "used_ollama_draft": used_ollama_draft,
                            },
                        )
                        pace_web_requests(
                            args,
                            heartbeat,
                            label=label,
                            prefix=prefix,
                            index=chunk.index,
                        )
                        completed_on_page += 1
                        chunk_index += 1
                        chunk_completed = True
                        consecutive_temporary_errors = 0
                        break
                    except Exception as exc:
                        last_error = exc
                        append_adaptive_error_event(
                            work_dir,
                            prefix=prefix,
                            label=label,
                            attempt=attempt,
                            error=exc,
                            chunk=chunk,
                        )
                        error_kind, error_action = classify_translation_web_error(exc, chunk)
                        beat_heartbeat(
                            heartbeat,
                            stage="translation_attempt_error",
                            label=label,
                            section_prefix=prefix,
                            attempt=attempt,
                            detail=f"kind={error_kind}; action={error_action}; error={str(exc)[:240]}",
                        )
                        if is_web_provider_pause_error(exc):
                            raise
                        if error_kind == "prompt_too_long" or (
                            active_web_provider(args) == "gemini"
                            and error_kind in {
                                "missing_translation_ids",
                                "translation_quality_failure",
                            }
                        ):
                            fallback_after_attempts = exc
                            beat_heartbeat(
                                heartbeat,
                                stage="translation_gemini_subchunk_early",
                                label=label,
                                section_prefix=prefix,
                                attempt=attempt,
                                detail=f"kind={error_kind}; switching to smaller subchunks",
                            )
                            close_page_quietly(page)
                            page = context.new_page()
                            prepared = False
                            completed_on_page = 0
                            break
                        if is_minor_context_refusal_error(exc, chunk) and not using_minor_safety_prompt:
                            prompt = build_translation_prompt(
                                chunk,
                                len(chunks),
                                book_title,
                                minor_safety_retry=True,
                                relationship_guide=relationship_guide,
                            )
                            write_text(work_dir / "prompts" / f"{prefix}_minor_context_retry_prompt.txt", prompt)
                            using_minor_safety_prompt = True
                            using_safety_retry_prompt = True
                            beat_heartbeat(
                                heartbeat,
                                stage="translation_minor_context_retry_prompt",
                                label=label,
                                section_prefix=prefix,
                                attempt=attempt,
                                detail="minor_context_refusal_detected; switched to non-explicit minor-context translation prompt",
                            )
                        elif is_refusal_error(exc) and not using_safety_retry_prompt:
                            prompt = build_translation_prompt(
                                chunk,
                                len(chunks),
                                book_title,
                                safety_retry=True,
                                relationship_guide=relationship_guide,
                            )
                            write_text(work_dir / "prompts" / f"{prefix}_literary_retry_prompt.txt", prompt)
                            using_safety_retry_prompt = True
                            beat_heartbeat(
                                heartbeat,
                                stage="translation_literary_retry_prompt",
                                label=label,
                                section_prefix=prefix,
                                attempt=attempt,
                                detail="refusal_detected; switched to literary context prompt",
                            )
                        elif is_refusal_error(exc) and using_safety_retry_prompt:
                            fallback_after_attempts = exc
                            beat_heartbeat(
                                heartbeat,
                                stage="translation_refusal_subchunk_early",
                                label=label,
                                section_prefix=prefix,
                                attempt=attempt,
                                detail="repeated_refusal_after_literary_prompt; switching to smaller subchunks",
                            )
                            close_page_quietly(page)
                            page = context.new_page()
                            prepared = False
                            completed_on_page = 0
                            break
                        close_page_quietly(page)
                        page = context.new_page()
                        prepared = False
                        completed_on_page = 0
                        if error_kind == "temporary_service_error":
                            consecutive_temporary_errors += 1
                        else:
                            consecutive_temporary_errors = 0
                        if consecutive_temporary_errors >= GEMINI_TEMP_ERROR_BURST_THRESHOLD:
                            if overnight_fallback_active(args, active_web_provider(args)):
                                mark_gemini_temporarily_down(provider_fallback_state_dir(args, work_dir))
                                beat_heartbeat(
                                    heartbeat,
                                    stage="translation_overnight_provider_switch",
                                    label=label,
                                    section_prefix=prefix,
                                    attempt=attempt,
                                    detail=(
                                        f"{GEMINI_TEMP_ERROR_BURST_THRESHOLD}회 연속 temporary_service_error 발생; "
                                        f"야간 시간대이므로 대기 없이 {OVERNIGHT_FALLBACK_PROVIDER} 웹으로 전환"
                                    ),
                                )
                                raise OvernightProviderSwitch("gemini_outage") from exc
                            sleep_sec = GEMINI_TEMP_ERROR_COOLDOWN_SEC
                            consecutive_temporary_errors = 0
                            beat_heartbeat(
                                heartbeat,
                                stage="translation_temporary_error_cooldown",
                                label=label,
                                section_prefix=prefix,
                                attempt=attempt,
                                detail=(
                                    f"{GEMINI_TEMP_ERROR_BURST_THRESHOLD}회 연속 temporary_service_error 발생; "
                                    f"{sleep_sec}초간 냉각 대기"
                                ),
                            )
                        else:
                            sleep_sec = web_provider_retry_sleep_seconds(exc, attempt)
                            beat_heartbeat(
                                heartbeat,
                                stage="translation_retry_sleep",
                                label=label,
                                section_prefix=prefix,
                                attempt=attempt,
                                detail=f"sleep_sec={sleep_sec}; error={str(exc)[:240]}",
                            )
                        time.sleep(sleep_sec)
                if chunk_completed:
                    continue
                if fallback_after_attempts is not None:
                    fallback_reason, _action = classify_translation_web_error(fallback_after_attempts, chunk)
                    translate_refused_chunk_in_subchunks(
                        context=context,
                        timeout_error_cls=timeout_error_cls,
                        args=args,
                        work_dir=work_dir,
                        book_title=book_title,
                        relationship_guide=relationship_guide,
                        chunk=chunk,
                        chunk_count=len(chunks),
                        heartbeat=heartbeat,
                        fallback_reason=fallback_reason,
                    )
                    chunk_index += 1
                    completed_on_page = 0
                    close_page_quietly(page)
                    page = context.new_page()
                    prepared = False
                    continue
                else:
                    if last_error and should_subchunk_retry_error(last_error):
                        fallback_reason, _action = classify_translation_web_error(last_error, chunk)
                        translate_refused_chunk_in_subchunks(
                            context=context,
                            timeout_error_cls=timeout_error_cls,
                            args=args,
                            work_dir=work_dir,
                            book_title=book_title,
                            relationship_guide=relationship_guide,
                            chunk=chunk,
                            chunk_count=len(chunks),
                            heartbeat=heartbeat,
                            fallback_reason=fallback_reason,
                        )
                        chunk_index += 1
                        completed_on_page = 0
                        close_page_quietly(page)
                        page = context.new_page()
                        prepared = False
                        continue
                    if last_error:
                        raise last_error
                    raise RuntimeError(f"{active_web_provider(args).title()} 웹 번역에 실패했습니다.")
        finally:
            close_page_quietly(page)


def _translate_missing_chunks_session(
    *,
    args: argparse.Namespace,
    work_dir: Path,
    book_title: str,
    creator: str,
    blocks: list[SourceBlock],
    chunks: list[TranslationChunk],
    heartbeat: ProgressHeartbeat | None,
) -> None:
    provider = active_web_provider(args)
    if provider == "gemini":
        browser_cookie3, sync_playwright, timeout_error_cls = load_gemini_web_modules()
        cookies = load_gemini_web_cookies(browser_cookie3)
        chrome_path = args.gemini_web_chrome_path
    else:
        browser_cookie3, sync_playwright, timeout_error_cls = load_chatgpt_web_modules()
        cookies = load_chatgpt_web_cookies(browser_cookie3)
        chrome_path = args.chatgpt_web_chrome_path
    beat_heartbeat(heartbeat, stage="translation_browser_launch", detail=f"provider={provider}; playwright_start")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            executable_path=str(Path(chrome_path).expanduser()),
            args=chatgpt_web_launch_args(visible=args.web_visible),
        )
        context = None
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 1200})
            context.add_cookies(cookies)
            relationship_guide = ensure_relationship_guide(
                context=context,
                timeout_error_cls=timeout_error_cls,
                args=args,
                work_dir=work_dir,
                book_title=book_title,
                creator=creator,
                blocks=blocks,
                heartbeat=heartbeat,
            )
            if args.chunks_per_conversation > 1:
                translate_missing_chunks_reusing_conversations(
                    context=context,
                    timeout_error_cls=timeout_error_cls,
                    args=args,
                    work_dir=work_dir,
                    book_title=book_title,
                    relationship_guide=relationship_guide,
                    chunks=chunks,
                    heartbeat=heartbeat,
                )
                return
            for chunk in chunks:
                out_path = chunk_translation_path(work_dir, chunk.index)
                if cached_chunk_is_complete(out_path, chunk.block_ids, chunk):
                    continue
                prefix = f"chunk_{chunk.index:04d}"
                minor_retry = chunk_has_minor_context(chunk)
                prompt = build_translation_prompt(
                    chunk,
                    len(chunks),
                    book_title,
                    minor_safety_retry=minor_retry,
                    relationship_guide=relationship_guide,
                )
                refusal_retry_prompt = build_translation_prompt(
                    chunk,
                    len(chunks),
                    book_title,
                    safety_retry=not minor_retry,
                    minor_safety_retry=minor_retry,
                    relationship_guide=relationship_guide,
                )
                write_text(work_dir / "prompts" / f"{prefix}_prompt.txt", prompt)
                retry_prompt_name = f"{prefix}_minor_context_retry_prompt.txt" if minor_retry else f"{prefix}_literary_retry_prompt.txt"
                write_text(work_dir / "prompts" / retry_prompt_name, refusal_retry_prompt)
                conversation_id, response = request_web_translation(
                    context=context,
                    timeout_error_cls=timeout_error_cls,
                    args=args,
                    prompt=prompt,
                    refusal_retry_prompt=refusal_retry_prompt,
                    heartbeat=heartbeat,
                    label=f"번역 {chunk.index}/{len(chunks)}",
                    prefix=prefix,
                    work_dir=work_dir,
                )
                write_text(work_dir / "responses" / f"{prefix}_response.txt", response)
                translations = parse_translation_response(response, chunk.block_ids)
                fill_passthrough_translations(translations, chunk)
                missing = [block_id for block_id in chunk.block_ids if not translations.get(block_id)]
                if missing:
                    if is_translation_web_refusal_response(response, args):
                        preview = normalized_file_text(response)[:200].replace("\n", " ")
                        error = RuntimeError(f"{provider.title()} 번역 응답이 거절되었습니다: {preview}")
                    else:
                        error = RuntimeError(f"{prefix} 응답에서 누락되거나 빈 번역 ID: {', '.join(missing[:10])}")
                    if should_subchunk_retry_error(error):
                        fallback_reason, _action = classify_translation_web_error(error, chunk)
                        translate_refused_chunk_in_subchunks(
                            context=context,
                            timeout_error_cls=timeout_error_cls,
                            args=args,
                            work_dir=work_dir,
                            book_title=book_title,
                            relationship_guide=relationship_guide,
                            chunk=chunk,
                            chunk_count=len(chunks),
                            heartbeat=heartbeat,
                            fallback_reason=fallback_reason,
                        )
                        continue
                    raise error
                try:
                    quality = validate_chunk_translations(
                        chunk,
                        translations,
                        allow_non_explicit_compression=minor_retry,
                    )
                except RuntimeError as error:
                    append_adaptive_error_event(
                        work_dir,
                        prefix=prefix,
                        label=f"번역 {chunk.index}/{len(chunks)}",
                        attempt=1,
                        error=error,
                        chunk=chunk,
                    )
                    translate_refused_chunk_in_subchunks(
                        context=context,
                        timeout_error_cls=timeout_error_cls,
                        args=args,
                        work_dir=work_dir,
                        book_title=book_title,
                        relationship_guide=relationship_guide,
                        chunk=chunk,
                        chunk_count=len(chunks),
                        heartbeat=heartbeat,
                        fallback_reason="translation_quality_failure",
                    )
                    continue
                write_json(
                    out_path,
                    {
                        "chunk_index": chunk.index,
                        "chunk_count": len(chunks),
                        "conversation_id": conversation_id,
                        "pipeline_version": TRANSLATION_PIPELINE_VERSION,
                        "block_ids": chunk.block_ids,
                        "quality": quality,
                        "translations": translations,
                    },
                )
                pace_web_requests(
                    args,
                    heartbeat,
                    label=f"번역 {chunk.index}/{len(chunks)}",
                    prefix=prefix,
                    index=chunk.index,
                )
        finally:
            if context is not None:
                context.close()
            browser.close()


def translate_missing_chunks(
    *,
    args: argparse.Namespace,
    work_dir: Path,
    book_title: str,
    creator: str,
    blocks: list[SourceBlock],
    chunks: list[TranslationChunk],
    heartbeat: ProgressHeartbeat | None,
) -> None:
    """Run (and resume) the translation browser session, switching web providers on demand.

    Normally this launches one browser session for the configured provider and runs until every
    chunk is translated. When the configured provider is Gemini and it's inside the fallback
    window (18:00-09:00 nightly, or anytime on Sat/Sun), a Gemini outage raises
    OvernightProviderSwitch instead of sleeping through a long cooldown; this loop catches it,
    relaunches the browser on ChatGPT web, and resumes from the on-disk chunk cache. Each new
    session tries Gemini again first, so once Gemini recovers translation resumes on Gemini
    automatically.
    """
    while True:
        session_provider = resolve_session_provider(args, work_dir)
        session_args = args_with_provider(args, session_provider)
        try:
            _translate_missing_chunks_session(
                args=session_args,
                work_dir=work_dir,
                book_title=book_title,
                creator=creator,
                blocks=blocks,
                chunks=chunks,
                heartbeat=heartbeat,
            )
            return
        except OvernightProviderSwitch as switch:
            beat_heartbeat(
                heartbeat,
                stage="translation_overnight_provider_switch_resume",
                detail=f"reason={switch.reason}; previous_provider={session_provider}",
            )
            continue


def strip_source_watermarks(text: str) -> str:
    scrubbed, _count = scrub_text(text)
    return clean_text(scrubbed)


def xhtml_for_section(section: SourceSection, translations: dict[str, str]) -> str:
    title = html.escape(strip_source_watermarks(translate_title(section.title)))
    rows: list[str] = []
    for block in section.blocks:
        english = strip_source_watermarks(block.text)
        korean = strip_source_watermarks(translations.get(block.id, ""))
        if not korean:
            korean = "" if not english else "[번역 누락] " + english
        if len(english) <= 80 and english.upper() == english and re.search(r"[A-Z]", english):
            rows.append(
                f'    <h2><span class="ko" xml:lang="ko">{html.escape(korean)}</span> '
                f'<span class="en" xml:lang="en">({html.escape(english)})</span></h2>'
            )
        else:
            rows.append(
                f'    <p class="pair"><span class="ko" xml:lang="ko">{html.escape(korean)}</span><br />'
                f'<span class="en" xml:lang="en">{html.escape(english)}</span></p>'
            )
    body = "\n".join(rows)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>{title}</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body>
  <section epub:type="chapter">
    <h1>{title}</h1>
{body}
  </section>
</body>
</html>
'''


def styles_css() -> str:
    return '''@charset "utf-8";
html, body { margin: 0; padding: 0; }
body {
  font-family: serif;
  line-height: 1.58;
  word-break: keep-all;
  -webkit-hyphens: none;
  hyphens: none;
}
section { margin: 0; padding: 0; }
h1 {
  font-size: 1.45em;
  line-height: 1.25;
  margin: 1.35em 0 1em;
  text-align: center;
  page-break-before: always;
}
h2 {
  font-size: 1.05em;
  line-height: 1.35;
  margin: 1.15em 0 0.75em;
  text-align: left;
}
p { margin: 0 0 0.86em; text-indent: 0; }
p.pair { margin-bottom: 1em; }
span.en {
  color: #4a4a4a;
  font-size: 0.92em;
}
nav#toc { margin: 0 2%; }
nav#toc h1 { page-break-before: auto; }
nav#toc ol { padding-left: 1.4em; }
nav#toc li { margin: 0.3em 0; }
.cover-page {
  margin: 0;
  padding: 0;
  text-align: center;
  page-break-after: always;
}
.cover-page img {
  display: block;
  margin: 0 auto;
  max-width: 100%;
  max-height: 100%;
}
a { color: inherit; text-decoration: none; }
'''


def cover_xhtml(book_title: str, cover: CoverAsset) -> str:
    safe_title = html.escape(book_title)
    safe_href = html.escape(cover.href)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>표지</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body epub:type="cover">
  <section class="cover-page">
    <img src="{safe_href}" alt="{safe_title}" />
  </section>
</body>
</html>
'''


def nav_xhtml(sections: list[SourceSection]) -> str:
    items = "\n".join(
        f'      <li><a href="{html.escape(section.filename)}">'
        f'{html.escape(strip_source_watermarks(translate_title(section.title)))}</a></li>'
        for section in sections
    )
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>차례</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>차례</h1>
    <ol>
{items}
    </ol>
  </nav>
  <nav epub:type="landmarks" hidden="hidden">
    <h2>Landmarks</h2>
    <ol>
      <li><a epub:type="cover" href="cover.xhtml">표지</a></li>
      <li><a epub:type="toc" href="nav.xhtml">차례</a></li>
      <li><a epub:type="bodymatter" href="{html.escape(sections[0].filename)}">본문</a></li>
    </ol>
  </nav>
</body>
</html>
'''


def ncx(book_title: str, creator: str, uid: str, sections: list[SourceSection]) -> str:
    points = ['''  <navPoint id="navpoint-cover" playOrder="1">
    <navLabel><text>표지</text></navLabel>
    <content src="cover.xhtml"/>
  </navPoint>''', '''  <navPoint id="navpoint-toc" playOrder="2">
    <navLabel><text>차례</text></navLabel>
    <content src="nav.xhtml"/>
  </navPoint>''']
    for index, section in enumerate(sections, start=1):
        points.append(f'''  <navPoint id="navpoint-{index:03d}" playOrder="{index + 2}">
    <navLabel><text>{html.escape(strip_source_watermarks(translate_title(section.title)))}</text></navLabel>
    <content src="{html.escape(section.filename)}"/>
  </navPoint>''')
    return f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="ko">
<head>
  <meta name="dtb:uid" content="{html.escape(uid)}"/>
  <meta name="dtb:depth" content="1"/>
  <meta name="dtb:totalPageCount" content="0"/>
  <meta name="dtb:maxPageNumber" content="0"/>
</head>
<docTitle><text>{html.escape(book_title)}</text></docTitle>
<docAuthor><text>{html.escape(creator)}</text></docAuthor>
<navMap>
{chr(10).join(points)}
</navMap>
</ncx>
'''


def content_opf(book_title: str, creator: str, uid: str, modified: str, sections: list[SourceSection], cover: CoverAsset) -> str:
    manifest = [
        '    <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
        f'    <item id="cover-image" href="{html.escape(cover.href)}" media-type="{html.escape(cover.media_type)}" properties="cover-image"/>',
        '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '    <item id="style" href="styles.css" media-type="text/css"/>',
    ]
    for index, section in enumerate(sections, start=1):
        manifest.append(
            f'    <item id="sec{index:03d}" href="{html.escape(section.filename)}" media-type="application/xhtml+xml"/>'
        )
    spine = ['    <itemref idref="cover" linear="yes"/>', '    <itemref idref="nav" linear="yes"/>'] + [
        f'    <itemref idref="sec{index:03d}"/>' for index in range(1, len(sections) + 1)
    ]
    return f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="ko" prefix="rendition: http://www.idpf.org/vocab/rendition/#">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{html.escape(uid)}</dc:identifier>
    <dc:title>{html.escape(book_title)}</dc:title>
    <dc:creator>{html.escape(creator)}</dc:creator>
    <dc:language>ko</dc:language>
    <meta name="cover" content="cover-image"/>
    <meta property="dcterms:modified">{html.escape(modified)}</meta>
    <meta property="rendition:layout">reflowable</meta>
    <meta property="rendition:orientation">auto</meta>
    <meta property="rendition:spread">auto</meta>
  </metadata>
  <manifest>
{chr(10).join(manifest)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine)}
  </spine>
  <guide>
    <reference type="cover" title="표지" href="cover.xhtml"/>
    <reference type="toc" title="차례" href="nav.xhtml"/>
    <reference type="text" title="본문" href="{html.escape(sections[0].filename)}"/>
  </guide>
</package>
'''


def container_xml() -> str:
    return '''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
'''


def build_epub(
    *,
    output_epub: Path,
    book_title: str,
    ko_book_title: str,
    creator: str,
    sections: list[SourceSection],
    translations: dict[str, str],
    input_epub: Path,
) -> None:
    ko_book_title = strip_source_watermarks(ko_book_title)
    creator = strip_source_watermarks(creator)
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, input_epub.as_posix() + "::chatgpt-web-ko-study-epub"))
    modified = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cover = extract_cover_asset(input_epub, ko_book_title, creator)
    files: dict[str, str] = {
        "META-INF/container.xml": container_xml(),
        "OEBPS/styles.css": styles_css(),
        "OEBPS/content.opf": content_opf(ko_book_title, creator, uid, modified, sections, cover),
        "OEBPS/toc.ncx": ncx(ko_book_title, creator, uid, sections),
        "OEBPS/nav.xhtml": nav_xhtml(sections),
        "OEBPS/cover.xhtml": cover_xhtml(ko_book_title, cover),
    }
    for section in sections:
        files[f"OEBPS/{section.filename}"] = xhtml_for_section(section, translations)
    output_epub.parent.mkdir(parents=True, exist_ok=True)
    with atomic_output_path(output_epub) as temp_epub:
        with zipfile.ZipFile(temp_epub, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            archive.writestr(f"OEBPS/{cover.href}", cover.data, compress_type=zipfile.ZIP_DEFLATED)
            for name, content in files.items():
                archive.writestr(name, content.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        integrity = validate_epub(
            temp_epub,
            require_nav=True,
            require_ncx=True,
            require_cover=True,
        )
        if not integrity.valid:
            raise RuntimeError(
                "임시 EPUB 무결성 검증에 실패했습니다: " + "; ".join(integrity.issues[:8])
            )


def acquire_translation_lock(work_dir: Path):
    lock_path = work_dir / ".translation.lock"
    lock_handle = lock_path.open("w", encoding="utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt

            lock_handle.write(" ")
            lock_handle.flush()
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        lock_handle.close()
        raise SystemExit(f"동일한 작업 디렉터리의 번역이 이미 실행 중입니다: {work_dir}") from exc
    lock_handle.seek(0)
    lock_handle.truncate()
    lock_handle.write(f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}\n")
    lock_handle.flush()
    return lock_handle


def main() -> int:
    args = parse_args()
    input_epub = args.input_epub.expanduser().resolve()
    output_epub = args.output_epub.expanduser().resolve()
    if not input_epub.exists():
        raise SystemExit(f"입력 EPUB를 찾지 못했습니다: {input_epub}")
    work_dir = resolve_work_dir(args)
    work_dir.mkdir(parents=True, exist_ok=True)
    translation_lock = acquire_translation_lock(work_dir)
    args.web_provider = resolve_web_provider(args, work_dir)
    persist_web_provider(work_dir, args.web_provider)
    heartbeat = ProgressHeartbeat(args.heartbeat_file) if args.heartbeat_file else None

    book_title, creator, sections = extract_sections(input_epub)
    # Keep the original-language book title in the generated EPUB. Korean translations
    # belong in the body text, not in the book's title metadata or cover title.
    ko_book_title = args.book_title_ko or book_title
    blocks = all_blocks(sections)
    chunks = build_chunks(blocks, max(2000, args.max_chars_per_chunk))
    write_json(
        work_dir / "manifest.json",
        {
            "input_epub": str(input_epub),
            "output_epub": str(output_epub),
            "work_dir": str(work_dir),
            "book_title": book_title,
            "ko_book_title": ko_book_title,
            "creator": creator,
            "section_count": len(sections),
            "block_count": len(blocks),
            "chunk_count": len(chunks),
            "max_chars_per_chunk": args.max_chars_per_chunk,
            "translation_pipeline_version": TRANSLATION_PIPELINE_VERSION,
            "relationship_guide_version": RELATIONSHIP_GUIDE_VERSION,
            "error_taxonomy_version": ERROR_TAXONOMY_VERSION,
            "web_provider": args.web_provider,
        },
    )
    write_json(
        work_dir / "source_sections.json",
        {
            "sections": [
                {
                    "title": section.title,
                    "filename": section.filename,
                    "blocks": [{"id": block.id, "text": block.text} for block in section.blocks],
                }
                for section in sections
            ]
        },
    )
    beat_heartbeat(heartbeat, stage="extracted", detail=f"blocks={len(blocks)} chunks={len(chunks)}")

    if args.draft_only:
        ensure_ollama_drafts(
            work_dir=work_dir,
            chunks=chunks,
            args=args,
            book_title=book_title,
            heartbeat=heartbeat,
        )
        print(json.dumps({"work_dir": str(work_dir), "chunks": len(chunks), "draft_only": True}, ensure_ascii=False))
        translation_lock.close()
        return 0

    if not args.build_only:
        if not getattr(args, "precomputed_drafts_only", False):
            ensure_ollama_drafts(
                work_dir=work_dir,
                chunks=chunks,
                args=args,
                book_title=book_title,
                heartbeat=heartbeat,
            )
        translate_missing_chunks(
            args=args,
            work_dir=work_dir,
            book_title=book_title,
            creator=creator,
            blocks=blocks,
            chunks=chunks,
            heartbeat=heartbeat,
        )
    if args.translate_only:
        return 0

    translations = load_translation_cache(work_dir)
    fill_separator_translations(blocks, translations)
    missing = [block.id for block in blocks if not translations.get(block.id)]
    if missing:
        raise SystemExit(f"번역 누락 또는 빈 블록 {len(missing)}개가 있어 EPUB를 만들 수 없습니다. 예: {', '.join(missing[:10])}")
    build_epub(
        output_epub=output_epub,
        book_title=book_title,
        ko_book_title=ko_book_title,
        creator=creator,
        sections=sections,
        translations=translations,
        input_epub=input_epub,
    )
    cleanup = scrub_epub(output_epub)
    if str(cleanup.get("status") or "").startswith("error:"):
        raise RuntimeError(f"생성 EPUB 워터마크 삭제 검증에 실패했습니다: {cleanup['status']}")
    tone_review_result: dict[str, str] | None = None
    dialogue_pass2_result: dict[str, str] | None = None
    if not args.skip_final_tone_review:
        try:
            guide_path = relationship_guide_path(work_dir)
            review = review_epub_tone(
                output_epub,
                relationship_guide=guide_path if guide_path.exists() else None,
                out_dir=work_dir / "final_tone_reviews",
                kind="k-e",
            )
            tone_review_result = {
                "status": review.status,
                "report": review.report_path,
                "json": review.json_path,
            }
            beat_heartbeat(
                heartbeat,
                stage="final_tone_review_complete",
                detail=f"status={review.status} report={review.report_path}",
            )
        except Exception as exc:  # noqa: BLE001 - keep EPUB output but make the review failure traceable.
            error_path = work_dir / "final_tone_review_error.txt"
            write_text(error_path, f"{datetime.now().isoformat(timespec='seconds')} {exc}\n")
            tone_review_result = {"status": "failed", "error": str(exc), "error_path": str(error_path)}
            beat_heartbeat(heartbeat, stage="final_tone_review_failed", detail=str(exc)[:300])
        try:
            guide_path = relationship_guide_path(work_dir)
            review2 = review_dialogue_consistency(
                output_epub,
                relationship_guide=guide_path if guide_path.exists() else None,
                out_dir=work_dir / "final_dialogue_reviews_pass2",
                kind="k-e",
            )
            dialogue_pass2_result = {
                "status": review2.status,
                "report": review2.report_path,
                "json": review2.json_path,
            }
            beat_heartbeat(
                heartbeat,
                stage="final_dialogue_review_pass2_complete",
                detail=f"status={review2.status} report={review2.report_path}",
            )
        except Exception as exc:  # noqa: BLE001 - retain EPUB and make the failed second pass traceable.
            error_path = work_dir / "final_dialogue_review_pass2_error.txt"
            write_text(error_path, f"{datetime.now().isoformat(timespec='seconds')} {exc}\n")
            dialogue_pass2_result = {"status": "failed", "error": str(exc), "error_path": str(error_path)}
            beat_heartbeat(heartbeat, stage="final_dialogue_review_pass2_failed", detail=str(exc)[:300])
    terminology_review_result: dict[str, object] | None = None
    if not args.skip_final_tone_review:
        try:
            guide_path = relationship_guide_path(work_dir)
            guide_text = guide_path.read_text(encoding="utf-8") if guide_path.exists() else ""
            glossary = parse_terminology_glossary(guide_text)
            findings = check_terminology_consistency(blocks, translations, glossary) if glossary else []
            report = write_terminology_consistency_report(
                out_dir=work_dir / "final_terminology_reviews",
                glossary=glossary,
                findings=findings,
            )
            terminology_review_result = {
                "status": report["status"],
                "glossary_terms": len(glossary),
                "finding_count": len(findings),
                "report": str(work_dir / "final_terminology_reviews" / "terminology_consistency_report.md"),
            }
            beat_heartbeat(
                heartbeat,
                stage="final_terminology_review_complete",
                detail=f"status={report['status']} findings={len(findings)}",
            )
        except Exception as exc:  # noqa: BLE001 - retain EPUB and make the failed review traceable.
            error_path = work_dir / "final_terminology_review_error.txt"
            write_text(error_path, f"{datetime.now().isoformat(timespec='seconds')} {exc}\n")
            terminology_review_result = {"status": "failed", "error": str(exc), "error_path": str(error_path)}
            beat_heartbeat(heartbeat, stage="final_terminology_review_failed", detail=str(exc)[:300])
    beat_heartbeat(heartbeat, stage="complete", detail=str(output_epub))
    print(
        json.dumps(
            {
                "output_epub": str(output_epub),
                "work_dir": str(work_dir),
                "sections": len(sections),
                "blocks": len(blocks),
                "chunks": len(chunks),
                "final_tone_review": tone_review_result,
                "final_dialogue_review_pass2": dialogue_pass2_result,
                "final_terminology_review": terminology_review_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    translation_lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
