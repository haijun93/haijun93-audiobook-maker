#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import re
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import fitz
from bs4 import BeautifulSoup, Tag

from build_ted_sentence_inline_study_epub import split_english_sentences
from safe_xml import safe_fromstring


ROOT = Path(__file__).resolve().parents[1]
COURSE_URL = "https://oyc.yale.edu/economics/econ-159"
TERMS_URL = "https://oyc.yale.edu/terms"
DEFAULT_WORK_DIR = ROOT / ".work" / "yale_oyc_econ159_full_course_work"
DEFAULT_OUTPUT = ROOT / ".work" / "Yale_OYC_ECON159_Game_Theory_Lectures_01-24_Exams_Sentence_Inline_English_Korean.epub"


@dataclass(frozen=True)
class SentenceItem:
    sid: str
    english: str


@dataclass
class Section:
    title: str
    sentences: list[SentenceItem] = field(default_factory=list)


@dataclass
class Session:
    label: str
    title: str
    url: str
    kind: str
    number: int
    sections: list[Section] = field(default_factory=list)
    source_note: str = ""

    @property
    def heading(self) -> str:
        return f"{self.label}. {self.title}"

    @property
    def filename(self) -> str:
        prefix = "lecture" if self.kind == "lecture" else "exam"
        return f"{prefix}-{self.number:02d}.xhtml"

    @property
    def sentence_count(self) -> int:
        return sum(len(section.sentences) for section in self.sections)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a full ECON 159 Game Theory English-Korean sentence-inline EPUB from Open Yale Courses."
    )
    parser.add_argument("--course-url", default=COURSE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--max-chars", type=int, default=4200)
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N sessions, for testing.")
    parser.add_argument("--skip-translation", action="store_true")
    return parser.parse_args()


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def normalize_space(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    text = text.replace("\xa0", " ")
    text = text.replace("…", "...")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("–", "--").replace("—", "--")
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" .", ".").replace(" ,", ",").replace(" ?", "?").replace(" !", "!")
    return text.strip()


def course_sessions(course_url: str) -> list[Session]:
    soup = BeautifulSoup(fetch_text(course_url), "lxml")
    sessions: list[Session] = []
    exam_number = 1
    for anchor in soup.find_all("a"):
        href = urljoin(course_url, anchor.get("href", ""))
        text = normalize_space(anchor.get_text(" ", strip=True))
        lecture_match = re.search(r"/lecture-(\d+)$", href)
        exam_match = re.search(r"/exam-(\d+)$", href)
        if lecture_match:
            number = int(lecture_match.group(1))
            if 1 <= number <= 24:
                sessions.append(
                    Session(
                        label=f"Lecture {number}",
                        title=text,
                        url=href,
                        kind="lecture",
                        number=number,
                    )
                )
        elif exam_match:
            number = int(exam_match.group(1))
            if number in {1, 2}:
                label = "Midterm Exam" if number == 1 else "Final Exam"
                sessions.append(
                    Session(
                        label=label,
                        title=text,
                        url=href,
                        kind="exam",
                        number=exam_number,
                    )
                )
                exam_number += 1

    sessions.sort(key=lambda session: session_sort_key(session))
    return sessions


def session_sort_key(session: Session) -> tuple[int, int]:
    if session.kind == "lecture":
        if session.number <= 12:
            return (session.number, 0)
        return (session.number + 1, 0)
    if session.label == "Midterm Exam":
        return (13, 0)
    return (26, 0)


def parse_chapter_heading(text: str) -> str:
    return normalize_space(text)


def extract_lecture_sections(session: Session) -> None:
    soup = BeautifulSoup(fetch_text(session.url), "lxml")
    content = soup.find(id="inline_content")
    if content is None:
        raise RuntimeError(f"No transcript found for {session.url}")

    sections: list[Section] = []
    current: Section | None = None
    paragraph_buffer: list[str] = []

    def is_chapter_heading(text: str) -> bool:
        return bool(re.match(r"^Chapter\s+\d+\s*[:.]", text))

    def flush_current() -> None:
        nonlocal current, paragraph_buffer
        if current is None:
            return
        current.sentences = sentence_items_from_paragraphs(paragraph_buffer)
        sections.append(current)
        paragraph_buffer = []

    for child in content.children:
        if not isinstance(child, Tag):
            continue
        text = normalize_space(child.get_text(" ", strip=True))
        if child.name in {"h3", "h4"} or (child.name == "p" and is_chapter_heading(text)):
            flush_current()
            current = Section(title=parse_chapter_heading(text))
            continue
        if child.name == "p" and current is not None:
            if text and text.lower() != "[end of transcript]":
                paragraph_buffer.append(text)
    flush_current()

    if not sections:
        raise RuntimeError(f"No lecture sections found for {session.url}")
    session.sections = sections
    session.source_note = session.url


def exam_pdf_links(session: Session) -> list[tuple[str, str]]:
    soup = BeautifulSoup(fetch_text(session.url), "lxml")
    links: list[tuple[str, str]] = []
    for anchor in soup.find_all("a"):
        text = normalize_space(anchor.get_text(" ", strip=True))
        href = urljoin(session.url, anchor.get("href", ""))
        lower = href.lower()
        if not lower.endswith(".pdf"):
            continue
        if session.label == "Midterm Exam" and "midtermexam" in lower:
            links.append((text or "Midterm Exam PDF", href))
        if session.label == "Final Exam" and "final_exam_2007" in lower and "solutions" not in lower:
            links.append((text or "Final Exam PDF", href))
    return links


def extract_pdf_text(url: str, cache_dir: Path) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    pdf_file = cache_dir / f"{key}.pdf"
    text_file = cache_dir / f"{key}.txt"
    if text_file.exists():
        return text_file.read_text(encoding="utf-8")
    if not pdf_file.exists():
        pdf_file.write_bytes(fetch_bytes(url))
    document = fitz.open(pdf_file)
    pages = [page.get_text("text") for page in document]
    document.close()
    text = "\n".join(pages)
    text_file.write_text(text, encoding="utf-8")
    return text


def extract_exam_sections(session: Session, work_dir: Path) -> None:
    links = exam_pdf_links(session)
    if not links:
        session.sections = [Section(title=session.heading, sentences=[])]
        return

    sections: list[Section] = []
    pdf_cache = work_dir / "pdfs"
    for title, pdf_url in links:
        text = extract_pdf_text(pdf_url, pdf_cache)
        paragraphs = pdf_paragraphs(text)
        section = Section(title=f"{title} ({pdf_url})", sentences=sentence_items_from_paragraphs(paragraphs))
        sections.append(section)
    session.sections = sections
    session.source_note = "; ".join(url for _title, url in links)


def pdf_paragraphs(text: str) -> list[str]:
    text = text.replace("\r", "\n")
    lines = [normalize_space(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if re.fullmatch(r"\d+", line):
            continue
        if re.match(r"^(Econ\s+159|Game\s+Theory|Midterm|Final|Page\s+\d+)", line, flags=re.I):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            paragraphs.append(line)
            continue
        if re.match(r"^(\d+\.|[a-z]\)|\([a-z]\)|Question\s+\d+)", line, flags=re.I) and current:
            paragraphs.append(" ".join(current))
            current = [line]
        else:
            current.append(line)
            if line.endswith((".", "?", "!")) and len(" ".join(current)) > 120:
                paragraphs.append(" ".join(current))
                current = []
    if current:
        paragraphs.append(" ".join(current))
    return [paragraph for paragraph in paragraphs if paragraph]


def sentence_items_from_paragraphs(paragraphs: list[str]) -> list[SentenceItem]:
    items: list[SentenceItem] = []
    for paragraph in paragraphs:
        for sentence in split_english_sentences(paragraph):
            sentence = normalize_space(sentence)
            if sentence:
                items.append(SentenceItem(sid=f"S{len(items) + 1:05d}", english=sentence))
    return items


def chunk_items(items: list[SentenceItem], max_chars: int) -> list[list[SentenceItem]]:
    chunks: list[list[SentenceItem]] = []
    current: list[SentenceItem] = []
    current_chars = 0
    for item in items:
        line = f"[{item.sid}] {item.english}\n"
        if current and current_chars + len(line) > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += len(line)
    if current:
        chunks.append(current)
    return chunks


def google_translate(text: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "en",
            "tl": "ko",
            "dt": "t",
            "q": text,
        }
    )
    url = f"https://translate.googleapis.com/translate_a/single?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in data[0] if part and part[0])


def parse_translation_response(response: str) -> dict[str, str]:
    matches = list(re.finditer(r"\[(S\d{5})\]\s*", response))
    translations: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(response)
        translated = normalize_space(response[start:end])
        if translated:
            translations[match.group(1)] = translated
    return translations


def translate_chunk(items: list[SentenceItem], cache_file: Path, skip_translation: bool) -> dict[str, str]:
    expected = {item.sid for item in items}
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
        translations = cached.get("translations", {})
        invalid_markers = {"[번역 누락]"}
        if not skip_translation:
            invalid_markers.add("[번역 생략]")
        if expected <= set(translations) and not any(translations[sid] in invalid_markers for sid in expected):
            return {sid: translations[sid] for sid in expected}

    if skip_translation:
        translations = {item.sid: "[번역 생략]" for item in items}
        cache_file.write_text(json.dumps({"translations": translations}, ensure_ascii=False, indent=2), encoding="utf-8")
        return translations

    source = "\n".join(f"[{item.sid}] {item.english}" for item in items)
    last_error = ""
    for attempt in range(1, 5):
        try:
            response = google_translate(source)
            translations = parse_translation_response(response)
            missing = expected - set(translations)
            if not missing:
                cache_file.write_text(json.dumps({"translations": translations}, ensure_ascii=False, indent=2), encoding="utf-8")
                return translations
            last_error = f"missing IDs: {', '.join(sorted(missing)[:10])}"
            if len(items) > 1:
                break
        except Exception as exc:  # noqa: BLE001 - keep batch resumable across transient network failures.
            last_error = repr(exc)
            time.sleep(2 * attempt)

    if len(items) == 1:
        item = items[0]
        translation = "[번역 누락]"
        for attempt in range(1, 7):
            try:
                response = google_translate(item.english)
                translation = normalize_space(response)
                if translation:
                    break
            except Exception:
                time.sleep(3 * attempt)
        translations = {item.sid: translation}
        cache_file.write_text(json.dumps({"translations": translations, "fallback": last_error}, ensure_ascii=False, indent=2), encoding="utf-8")
        return translations

    midpoint = max(1, len(items) // 2)
    translations: dict[str, str] = {}
    translations.update(translate_chunk(items[:midpoint], cache_file.with_name(cache_file.stem + "_a.json"), skip_translation))
    translations.update(translate_chunk(items[midpoint:], cache_file.with_name(cache_file.stem + "_b.json"), skip_translation))
    return translations


def translate_session(session: Session, args: argparse.Namespace, cache_dir: Path) -> dict[str, dict[str, str]]:
    session_cache = cache_dir / safe_slug(session.heading)
    session_cache.mkdir(parents=True, exist_ok=True)
    translations: dict[str, dict[str, str]] = {}
    for section_index, section in enumerate(session.sections, start=1):
        print(f"  [section {section_index}/{len(session.sections)}] {section.title} - {len(section.sentences)} sentences", flush=True)
        section_translations: dict[str, str] = {}
        chunks = chunk_items(section.sentences, args.max_chars)
        for chunk_index, chunk in enumerate(chunks, start=1):
            print(f"    [translate] chunk {chunk_index}/{len(chunks)} ({len(chunk)} sentences)", flush=True)
            key = hashlib.sha256(
                json.dumps([(item.sid, item.english) for item in chunk], ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:16]
            section_translations.update(
                translate_chunk(chunk, session_cache / f"section_{section_index:02d}_{key}.json", args.skip_translation)
            )
        translations[section.title] = section_translations
    return translations


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:80] or hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def make_xhtml(title: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ko" lang="ko">
<head>
  <title>{esc(title)}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
{body}
</body>
</html>
"""


def build_intro(sessions: list[Session]) -> str:
    lecture_count = sum(1 for session in sessions if session.kind == "lecture")
    exam_count = sum(1 for session in sessions if session.kind == "exam")
    sentence_count = sum(session.sentence_count for session in sessions)
    rows = "\n".join(
        f'<li><a href="{esc(session.filename)}">{esc(session.heading)}</a> - {session.sentence_count} sentences</li>'
        for session in sessions
    )
    return make_xhtml(
        "ECON 159 Game Theory",
        f"""
<section class="intro">
  <h1>ECON 159 Game Theory</h1>
  <p>Open Yale Courses의 Game Theory 강의 1-24와 Midterm/Final Exam 자료를 영어학습용으로 구성했습니다. 각 문장은 영어 원문 뒤에 한국어 번역을 괄호로 붙였습니다.</p>
  <p class="meta">Lectures: {lecture_count} · Exams: {exam_count} · Sentence pairs: {sentence_count}</p>
  <h2>목차</h2>
  <ol>
    {rows}
  </ol>
  <h2>출처 및 라이선스</h2>
  <p>Source: Ben Polak, Game Theory (Yale University: Open Yale Courses), <a href="{COURSE_URL}">{COURSE_URL}</a>. Accessed {datetime.now().strftime("%Y-%m-%d")}.</p>
  <p>License: Creative Commons BY-NC-SA 3.0. Open Yale Courses Terms of Use: <a href="{TERMS_URL}">{TERMS_URL}</a>.</p>
</section>
""",
    )


def build_session_page(session: Session, translations: dict[str, dict[str, str]]) -> str:
    section_html: list[str] = []
    for section in session.sections:
        sentence_lines = []
        section_translations = translations.get(section.title, {})
        for item in section.sentences:
            korean = section_translations.get(item.sid, "[번역 누락]")
            sentence_lines.append(
                f'<p class="sentence"><span class="en">{esc(item.english)}</span> <span class="ko">({esc(korean)})</span></p>'
            )
        section_html.append(
            f"""
<section class="lecture-section">
  <h2>{esc(section.title)}</h2>
  {''.join(sentence_lines)}
</section>
"""
        )
    source = f'<p class="source">Source: <a href="{esc(session.url)}">{esc(session.url)}</a></p>'
    if session.source_note and session.source_note != session.url:
        source += f'<p class="source">Material: {esc(session.source_note)}</p>'
    return make_xhtml(
        session.heading,
        f"""
<article>
  <header>
    <p class="chapter-label">{esc(session.label)}</p>
    <h1>{esc(session.title)}</h1>
    {source}
  </header>
  {''.join(section_html)}
</article>
""",
    )


def build_nav(sessions: list[Session]) -> str:
    items = "\n".join(
        f'      <li><a href="{esc(session.filename)}">{esc(session.heading)}</a></li>'
        for session in sessions
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>Table of Contents</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>목차</h1>
    <ol>
      <li><a href="intro.xhtml">소개</a></li>
{items}
    </ol>
  </nav>
  <nav epub:type="landmarks" hidden="hidden">
    <ol>
      <li><a epub:type="bodymatter" href="intro.xhtml">Start</a></li>
    </ol>
  </nav>
</body>
</html>
"""


def build_ncx(sessions: list[Session], uid: str) -> str:
    points = [
        """    <navPoint id="navpoint-1" playOrder="1">
      <navLabel><text>소개</text></navLabel>
      <content src="intro.xhtml"/>
    </navPoint>"""
    ]
    for play_order, session in enumerate(sessions, start=2):
        points.append(
            f"""    <navPoint id="navpoint-{play_order}" playOrder="{play_order}">
      <navLabel><text>{esc(session.heading)}</text></navLabel>
      <content src="{esc(session.filename)}"/>
    </navPoint>"""
        )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{uid}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>ECON 159 Game Theory</text></docTitle>
  <navMap>
{chr(10).join(points)}
  </navMap>
</ncx>
"""


def build_opf(sessions: list[Session], uid: str, modified: str) -> str:
    manifest = "\n".join(
        f'    <item id="session-{index:02d}" href="{esc(session.filename)}" media-type="application/xhtml+xml"/>'
        for index, session in enumerate(sessions, start=1)
    )
    spine = "\n".join(f'    <itemref idref="session-{index:02d}"/>' for index in range(1, len(sessions) + 1))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0" xml:lang="ko">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">{uid}</dc:identifier>
    <dc:title>ECON 159 Game Theory - Sentence Inline English-Korean Study</dc:title>
    <dc:language>ko</dc:language>
    <dc:creator>Ben Polak</dc:creator>
    <dc:publisher>Yale University: Open Yale Courses</dc:publisher>
    <dc:rights>Creative Commons BY-NC-SA 3.0</dc:rights>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="style" href="style.css" media-type="text/css"/>
    <item id="intro" href="intro.xhtml" media-type="application/xhtml+xml"/>
{manifest}
  </manifest>
  <spine toc="ncx">
    <itemref idref="intro"/>
{spine}
  </spine>
</package>
"""


def style_css() -> str:
    return """
body {
  color: #151515;
  font-family: serif;
  line-height: 1.62;
  margin: 0;
  padding: 0 2%;
}
h1, h2 {
  line-height: 1.25;
}
a {
  color: #245c9f;
}
.chapter-label, .meta, .source {
  color: #555;
}
.lecture-section {
  margin-top: 1.4em;
}
.sentence {
  border-top: 1px solid #e5e5e5;
  margin: 0;
  padding: 0.55em 0;
}
.en {
  color: #151515;
}
.ko {
  color: #444;
}
"""


def write_epub(output: Path, sessions: list[Session], translations: dict[str, dict[str, dict[str, str]]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    uid = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files: dict[str, str] = {
        "META-INF/container.xml": """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        "OEBPS/content.opf": build_opf(sessions, uid, modified),
        "OEBPS/nav.xhtml": build_nav(sessions),
        "OEBPS/toc.ncx": build_ncx(sessions, uid),
        "OEBPS/style.css": style_css(),
        "OEBPS/intro.xhtml": build_intro(sessions),
    }
    for session in sessions:
        files[f"OEBPS/{session.filename}"] = build_session_page(session, translations[session.heading])

    with zipfile.ZipFile(output, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name, content in files.items():
            media_type = mimetypes.guess_type(name)[0]
            compress_type = zipfile.ZIP_DEFLATED if media_type != "application/epub+zip" else zipfile.ZIP_STORED
            epub.writestr(name, content.encode("utf-8"), compress_type=compress_type)


def validate_epub(path: Path, expected_sessions: int) -> dict[str, int | bool]:
    with zipfile.ZipFile(path) as epub:
        names = set(epub.namelist())
        session_files = sorted(name for name in names if re.fullmatch(r"OEBPS/(lecture|exam)-\d\d\.xhtml", name))
        if len(session_files) != expected_sessions:
            raise RuntimeError(f"Expected {expected_sessions} session pages, found {len(session_files)}")
        for name in ["OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/intro.xhtml", *session_files]:
            safe_fromstring(epub.read(name))
        joined = "\n".join(epub.read(name).decode("utf-8") for name in session_files)
        inline_pattern = re.compile(
            r'<p class="sentence"><span class="en">.+?</span>\s+<span class="ko">\(.+?\)</span></p>'
        )
        return {
            "session_pages": len(session_files),
            "nav": "OEBPS/nav.xhtml" in names,
            "ncx": "OEBPS/toc.ncx" in names,
            "sentences": joined.count('class="sentence"'),
            "inline_parenthetical_matches": len(inline_pattern.findall(joined)),
            "missing_markers": joined.count("[번역 누락]"),
            "skip_markers": joined.count("[번역 생략]"),
        }


def main() -> None:
    args = parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = args.work_dir / "translations"
    cache_dir.mkdir(parents=True, exist_ok=True)

    sessions = course_sessions(args.course_url)
    if args.limit:
        sessions = sessions[: args.limit]
    if not sessions:
        raise SystemExit("No sessions found.")

    for index, session in enumerate(sessions, start=1):
        print(f"[collect {index}/{len(sessions)}] {session.heading}", flush=True)
        if session.kind == "lecture":
            extract_lecture_sections(session)
        else:
            extract_exam_sections(session, args.work_dir)

    total_sentences = sum(session.sentence_count for session in sessions)
    print(f"[collect done] sessions={len(sessions)} sentences={total_sentences}", flush=True)

    translations: dict[str, dict[str, dict[str, str]]] = {}
    for index, session in enumerate(sessions, start=1):
        print(f"[session {index}/{len(sessions)}] {session.heading} - {session.sentence_count} sentences", flush=True)
        translations[session.heading] = translate_session(session, args, cache_dir)

    write_epub(args.output, sessions, translations)
    stats = validate_epub(args.output, len(sessions))
    print(f"[done] {args.output}", flush=True)
    for key, value in stats.items():
        print(f"[done] {key}={value}", flush=True)
    print(f"[done] size={args.output.stat().st_size}", flush=True)


if __name__ == "__main__":
    main()
