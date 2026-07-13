#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import subprocess
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from build_yale_oyc_game_theory_course_epub import (
    Section,
    Session,
    esc,
    extract_lecture_sections,
    fetch_text,
    normalize_space,
    pdf_paragraphs,
    safe_slug,
    sentence_items_from_paragraphs,
    translate_session,
)
from safe_xml import safe_fromstring


ROOT = Path(__file__).resolve().parents[1]
COURSES_URL = "https://oyc.yale.edu/courses"
TERMS_URL = "https://oyc.yale.edu/terms"
DEFAULT_WORK_DIR = ROOT / ".work" / "yale_oyc_all_courses_work"
DEFAULT_OUTPUT_DIR = ROOT / ".work" / "yale_oyc_all_courses_epubs"


@dataclass(frozen=True)
class Course:
    department: str
    code: str
    title: str
    professor: str
    semester: str
    url: str

    @property
    def slug(self) -> str:
        return safe_slug(f"{self.code} {self.title}")

    @property
    def display_title(self) -> str:
        return f"{self.code}: {self.title}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build sentence-inline English-Korean EPUBs for all Open Yale Courses."
    )
    parser.add_argument("--courses-url", default=COURSES_URL)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-chars", type=int, default=4200)
    parser.add_argument("--skip-translation", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit-courses", type=int, default=0)
    parser.add_argument("--start-index", type=int, default=1, help="1-based course index to start from.")
    parser.add_argument("--only-code", action="append", default=[], help="Course code to process, e.g. ECON 159.")
    parser.add_argument("--shutdown", action="store_true", help="Shut down this Mac after all work completes.")
    return parser.parse_args()


def collect_courses(courses_url: str) -> list[Course]:
    soup = BeautifulSoup(fetch_text(courses_url), "lxml")
    courses: list[Course] = []
    seen: set[str] = set()
    for row in soup.select("tbody tr"):
        code_cell = row.select_one("td.views-field-field-course-number")
        title_cell = row.select_one("td.views-field-title-1")
        dept_cell = row.select_one("td.views-field-title")
        professor_cell = row.select_one("td.views-field-field-course-professor-last-name")
        semester_cell = row.select_one("td.views-field-field-semester")
        if not code_cell or not title_cell:
            continue
        link = code_cell.find("a") or title_cell.find("a")
        if link is None:
            continue
        href = urljoin(courses_url, link.get("href", ""))
        if href in seen:
            continue
        seen.add(href)
        courses.append(
            Course(
                department=normalize_space(dept_cell.get_text(" ", strip=True)) if dept_cell else "",
                code=normalize_space(code_cell.get_text(" ", strip=True)),
                title=normalize_space(title_cell.get_text(" ", strip=True)),
                professor=normalize_space(professor_cell.get_text(" ", strip=True)) if professor_cell else "",
                semester=normalize_space(semester_cell.get_text(" ", strip=True)) if semester_cell else "",
                url=href,
            )
        )
    if not courses:
        raise RuntimeError(f"No courses found at {courses_url}")
    return courses


def collect_course_sessions(course: Course) -> list[Session]:
    soup = BeautifulSoup(fetch_text(course.url), "lxml")
    sessions: list[Session] = []
    seen: set[str] = set()
    exam_counter = 1
    for anchor in soup.find_all("a"):
        href = urljoin(course.url, anchor.get("href", ""))
        text = normalize_space(anchor.get_text(" ", strip=True))
        lecture_match = re.search(r"/lecture-(\d+)$", href)
        exam_match = re.search(r"/exam-(\d+)$", href)
        if lecture_match:
            if href in seen:
                continue
            seen.add(href)
            number = int(lecture_match.group(1))
            sessions.append(
                Session(
                    label=f"Lecture {number}",
                    title=text or f"Lecture {number}",
                    url=href,
                    kind="lecture",
                    number=number,
                )
            )
        elif exam_match:
            if href in seen:
                continue
            seen.add(href)
            number = int(exam_match.group(1))
            label_text = text or f"Exam {number}"
            sessions.append(
                Session(
                    label=label_text,
                    title=label_text,
                    url=href,
                    kind="exam",
                    number=exam_counter,
                )
            )
            exam_counter += 1
    return sessions


def generic_exam_pdf_links(session: Session) -> list[tuple[str, str]]:
    soup = BeautifulSoup(fetch_text(session.url), "lxml")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a"):
        href = urljoin(session.url, anchor.get("href", ""))
        if not href.lower().endswith(".pdf") or href in seen:
            continue
        seen.add(href)
        text = normalize_space(anchor.get_text(" ", strip=True)) or Path(href).name
        lower = text.lower() + " " + href.lower()
        if "solution" in lower or "answer" in lower:
            continue
        links.append((text, href))
    return links


def extract_pdf_text(pdf_url: str, cache_dir: Path) -> str:
    import fitz
    from build_yale_oyc_game_theory_course_epub import fetch_bytes

    cache_dir.mkdir(parents=True, exist_ok=True)
    key = safe_slug(pdf_url)[-80:]
    pdf_file = cache_dir / f"{key}.pdf"
    text_file = cache_dir / f"{key}.txt"
    if text_file.exists():
        return text_file.read_text(encoding="utf-8")
    if not pdf_file.exists():
        pdf_file.write_bytes(fetch_bytes(pdf_url))
    document = fitz.open(pdf_file)
    try:
        text = "\n".join(page.get_text("text") for page in document)
    finally:
        document.close()
    text_file.write_text(text, encoding="utf-8")
    return text


def extract_exam_sections_generic(session: Session, course_work_dir: Path) -> None:
    links = generic_exam_pdf_links(session)
    if not links:
        session.sections = [Section(title=session.heading, sentences=[])]
        return
    sections: list[Section] = []
    source_notes: list[str] = []
    for title, pdf_url in links:
        text = extract_pdf_text(pdf_url, course_work_dir / "pdfs")
        paragraphs = pdf_paragraphs(text)
        sections.append(
            Section(
                title=f"{title} ({pdf_url})",
                sentences=sentence_items_from_paragraphs(paragraphs),
            )
        )
        source_notes.append(pdf_url)
    session.sections = sections
    session.source_note = "; ".join(source_notes)


def collect_session_content(course: Course, sessions: list[Session], course_work_dir: Path) -> None:
    for index, session in enumerate(sessions, start=1):
        print(f"  [collect {index}/{len(sessions)}] {session.heading}", flush=True)
        try:
            if session.kind == "lecture":
                extract_lecture_sections(session)
            else:
                extract_exam_sections_generic(session, course_work_dir)
        except Exception as exc:  # noqa: BLE001 - keep the full batch moving.
            print(f"  [warn] failed to collect {session.heading}: {exc}", flush=True)
            if session.kind == "exam":
                session.sections = [Section(title=f"{session.heading} (source unavailable)", sentences=[])]
                session.source_note = f"Source unavailable: {exc}"
            else:
                raise


def output_filename(course: Course) -> str:
    return f"Yale_OYC_{safe_filename(course.code)}_{safe_filename(course.title)}_Sentence_Inline_English_Korean.epub"


def safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9가-힣._-]+", "_", text.strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:90] or "course"


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


def build_intro(course: Course, sessions: list[Session]) -> str:
    lecture_count = sum(1 for session in sessions if session.kind == "lecture")
    exam_count = sum(1 for session in sessions if session.kind == "exam")
    sentence_count = sum(session.sentence_count for session in sessions)
    rows = "\n".join(
        f'<li><a href="{esc(session.filename)}">{esc(session.heading)}</a> - {session.sentence_count} sentences</li>'
        for session in sessions
    )
    return make_xhtml(
        course.display_title,
        f"""
<section class="intro">
  <h1>{esc(course.display_title)}</h1>
  <p class="meta">{esc(course.department)} · {esc(course.professor)} · {esc(course.semester)}</p>
  <p>Open Yale Courses 강의 자료를 영어학습용으로 구성했습니다. 각 문장은 영어 원문 뒤에 한국어 번역을 괄호로 붙였습니다.</p>
  <p class="meta">Lectures: {lecture_count} · Exams: {exam_count} · Sentence pairs: {sentence_count}</p>
  <h2>목차</h2>
  <ol>
    {rows}
  </ol>
  <h2>출처 및 라이선스</h2>
  <p>Source: {esc(course.professor)}, {esc(course.display_title)} (Yale University: Open Yale Courses), <a href="{esc(course.url)}">{esc(course.url)}</a>. Accessed {datetime.now().strftime("%Y-%m-%d")}.</p>
  <p>License: Creative Commons BY-NC-SA 3.0. Open Yale Courses Terms of Use: <a href="{TERMS_URL}">{TERMS_URL}</a>.</p>
</section>
""",
    )


def build_session_page(session: Session, translations: dict[str, dict[str, str]]) -> str:
    section_html: list[str] = []
    for section in session.sections:
        section_translations = translations.get(section.title, {})
        sentence_lines = []
        for item in section.sentences:
            korean = section_translations.get(item.sid, "[번역 누락]")
            sentence_lines.append(
                f'<p class="sentence"><span class="en">{esc(item.english)}</span> <span class="ko">({esc(korean)})</span></p>'
            )
        if not sentence_lines:
            sentence_lines.append('<p class="sentence"><span class="en">No transcript text was available for this item.</span> <span class="ko">(이 항목에는 사용할 수 있는 스크립트 텍스트가 없습니다.)</span></p>')
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


def build_ncx(course: Course, sessions: list[Session], uid: str) -> str:
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
  <docTitle><text>{esc(course.display_title)}</text></docTitle>
  <navMap>
{chr(10).join(points)}
  </navMap>
</ncx>
"""


def build_opf(course: Course, sessions: list[Session], uid: str, modified: str) -> str:
    manifest = "\n".join(
        f'    <item id="session-{index:02d}" href="{esc(session.filename)}" media-type="application/xhtml+xml"/>'
        for index, session in enumerate(sessions, start=1)
    )
    spine = "\n".join(f'    <itemref idref="session-{index:02d}"/>' for index in range(1, len(sessions) + 1))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0" xml:lang="ko">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">{uid}</dc:identifier>
    <dc:title>{esc(course.display_title)} - Sentence Inline English-Korean Study</dc:title>
    <dc:language>ko</dc:language>
    <dc:creator>{esc(course.professor)}</dc:creator>
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


def write_epub(output: Path, course: Course, sessions: list[Session], translations: dict[str, dict[str, dict[str, str]]]) -> None:
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
        "OEBPS/content.opf": build_opf(course, sessions, uid, modified),
        "OEBPS/nav.xhtml": build_nav(sessions),
        "OEBPS/toc.ncx": build_ncx(course, sessions, uid),
        "OEBPS/style.css": style_css(),
        "OEBPS/intro.xhtml": build_intro(course, sessions),
    }
    for session in sessions:
        files[f"OEBPS/{session.filename}"] = build_session_page(session, translations[session.heading])

    with zipfile.ZipFile(output, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name, content in files.items():
            media_type = mimetypes.guess_type(name)[0]
            compress_type = zipfile.ZIP_DEFLATED if media_type != "application/epub+zip" else zipfile.ZIP_STORED
            epub.writestr(name, content.encode("utf-8"), compress_type=compress_type)


def validate_epub(path: Path, expected_sessions: int, require_no_skip: bool) -> dict[str, int | bool]:
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
        stats = {
            "session_pages": len(session_files),
            "nav": "OEBPS/nav.xhtml" in names,
            "ncx": "OEBPS/toc.ncx" in names,
            "sentences": joined.count('class="sentence"'),
            "inline_parenthetical_matches": len(inline_pattern.findall(joined)),
            "missing_markers": joined.count("[번역 누락]"),
            "skip_markers": joined.count("[번역 생략]"),
            "collection_failed_markers": joined.count("collection failed"),
        }
        if stats["missing_markers"]:
            raise RuntimeError(f"Missing translation markers: {stats['missing_markers']}")
        if require_no_skip and stats["skip_markers"]:
            raise RuntimeError(f"Skipped translation markers: {stats['skip_markers']}")
        if stats["collection_failed_markers"]:
            raise RuntimeError(f"Collection failed markers: {stats['collection_failed_markers']}")
        if stats["sentences"] != stats["inline_parenthetical_matches"]:
            raise RuntimeError("Inline parenthetical sentence format mismatch.")
        return stats


def process_course(course_index: int, course_count: int, course: Course, args: argparse.Namespace) -> dict[str, object]:
    course_work_dir = args.work_dir / course.slug
    course_work_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / output_filename(course)

    if output.exists() and not args.force and not args.skip_translation:
        try:
            stats = validate_epub(output, expected_sessions=count_existing_session_pages(output), require_no_skip=True)
            print(f"[course {course_index}/{course_count}] skip existing {course.display_title}", flush=True)
            return {"course": asdict(course), "output": str(output), "status": "skipped", "stats": stats}
        except Exception:
            pass

    print(f"[course {course_index}/{course_count}] {course.display_title}", flush=True)
    sessions = collect_course_sessions(course)
    collect_session_content(course, sessions, course_work_dir)
    sessions = [session for session in sessions if session.sections]
    print(f"[course {course_index}/{course_count}] sessions={len(sessions)} sentences={sum(s.sentence_count for s in sessions)}", flush=True)

    translations: dict[str, dict[str, dict[str, str]]] = {}
    for session_index, session in enumerate(sessions, start=1):
        print(f"[course {course_index}/{course_count}] [session {session_index}/{len(sessions)}] {session.heading} - {session.sentence_count} sentences", flush=True)
        translations[session.heading] = translate_session(session, args, course_work_dir / "translations")

    write_epub(output, course, sessions, translations)
    stats = validate_epub(output, expected_sessions=len(sessions), require_no_skip=not args.skip_translation)
    print(f"[course {course_index}/{course_count}] done {output} {stats}", flush=True)
    return {"course": asdict(course), "output": str(output), "status": "done", "stats": stats}


def count_existing_session_pages(path: Path) -> int:
    with zipfile.ZipFile(path) as epub:
        return sum(1 for name in epub.namelist() if re.fullmatch(r"OEBPS/(lecture|exam)-\d\d\.xhtml", name))


def shutdown_mac() -> None:
    subprocess.run(["osascript", "-e", 'tell application "System Events" to shut down'], check=False)


def main() -> None:
    args = parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    courses = collect_courses(args.courses_url)
    if args.only_code:
        wanted = {code.strip().lower() for code in args.only_code}
        courses = [course for course in courses if course.code.lower() in wanted]
    if args.start_index > 1:
        courses = courses[args.start_index - 1 :]
    if args.limit_courses:
        courses = courses[: args.limit_courses]
    if not courses:
        raise SystemExit("No courses selected.")

    manifest_path = args.work_dir / "course_manifest.json"
    manifest_path.write_text(json.dumps([asdict(course) for course in courses], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[manifest] courses={len(courses)} path={manifest_path}", flush=True)

    results: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    completed = False
    try:
        for index, course in enumerate(courses, start=1):
            try:
                result = process_course(index, len(courses), course, args)
            except Exception as exc:  # noqa: BLE001 - record course failures and keep the batch resumable.
                print(f"[course {index}/{len(courses)}] error {course.display_title}: {exc}", flush=True)
                result = {"course": asdict(course), "output": "", "status": "error", "error": repr(exc)}
                errors.append({"course": course.display_title, "error": repr(exc)})
            results.append(result)
            (args.work_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(0.5)
        if errors:
            error_path = args.work_dir / "errors.json"
            error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
            raise RuntimeError(f"{len(errors)} course(s) failed; see {error_path}")
        completed = True
        print(f"[all done] output_dir={args.output_dir}", flush=True)
    finally:
        if args.shutdown and completed:
            print("[shutdown] requested", flush=True)
            shutdown_mac()
        elif args.shutdown:
            print("[shutdown] skipped because batch did not complete successfully", flush=True)


if __name__ == "__main__":
    main()
