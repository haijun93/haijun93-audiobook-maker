#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import mimetypes
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from bs4 import BeautifulSoup, Tag

from build_ted_sentence_inline_study_epub import split_english_sentences
from build_ted_transcript_study_epub import Segment, Talk, translate_talk
from safe_xml import safe_fromstring


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://oyc.yale.edu/economics/econ-159/lecture-2"
DEFAULT_WORK_DIR = ROOT / ".work" / "yale_oyc_econ159_lecture2_sentence_work"
DEFAULT_OUTPUT = ROOT / ".work" / "Yale_OYC_ECON159_Lecture02_Sentence_Inline_English_Korean.epub"


@dataclass(frozen=True)
class SentenceItem:
    sid: str
    english: str


@dataclass
class LectureChapter:
    number: int
    title: str
    timecode: str
    paragraphs: list[str]
    sentences: list[SentenceItem]

    @property
    def heading(self) -> str:
        if self.timecode:
            return f"Chapter {self.number}. {self.title} [{self.timecode}]"
        return f"Chapter {self.number}. {self.title}"


@dataclass
class Lecture:
    url: str
    course_title: str
    lecture_title: str
    speaker: str
    chapters: list[LectureChapter]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a sentence-inline English-Korean EPUB from an Open Yale Courses lecture transcript."
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--model", default="exaone3.5:7.8b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--max-chars", type=int, default=7000)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--skip-translation", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N lecture chapters.")
    return parser.parse_args()


def normalize_space(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("…", "...")
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" .", ".").replace(" ,", ",").replace(" ?", "?").replace(" !", "!")
    return text.strip()


def parse_chapter_heading(text: str) -> tuple[int, str, str]:
    match = re.match(r"Chapter\s+(\d+)\.\s*(.*?)\s*(?:\[(.*?)\])?$", text)
    if not match:
        raise ValueError(f"Could not parse chapter heading: {text}")
    return int(match.group(1)), match.group(2).strip(), (match.group(3) or "").strip()


def extract_lecture(url: str) -> Lecture:
    raw_html = urlopen(url, timeout=60).read().decode("utf-8", errors="replace")
    soup = BeautifulSoup(raw_html, "lxml")
    content = soup.find(id="inline_content")
    if content is None:
        raise RuntimeError("Could not find transcript inline_content in OYC page.")

    course_title = normalize_space(content.find("h1").get_text(" ", strip=True))
    lecture_title = normalize_space(content.find("h2").get_text(" ", strip=True))

    chapters: list[LectureChapter] = []
    current: LectureChapter | None = None
    for child in content.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "h3":
            if current is not None:
                chapters.append(current)
            number, title, timecode = parse_chapter_heading(normalize_space(child.get_text(" ", strip=True)))
            current = LectureChapter(number=number, title=title, timecode=timecode, paragraphs=[], sentences=[])
            continue
        if child.name == "p" and current is not None:
            text = normalize_space(child.get_text(" ", strip=True))
            if not text or text.lower() == "[end of transcript]":
                continue
            current.paragraphs.append(text)
    if current is not None:
        chapters.append(current)

    if not chapters:
        raise RuntimeError("No transcript chapters found.")

    speaker = "Professor Ben Polak"
    for chapter in chapters:
        sentences: list[SentenceItem] = []
        for paragraph in chapter.paragraphs:
            for sentence in split_english_sentences(paragraph):
                sentence = normalize_space(sentence)
                if sentence:
                    sentences.append(SentenceItem(sid=f"S{len(sentences) + 1:03d}", english=sentence))
        chapter.sentences = sentences

    return Lecture(
        url=url,
        course_title=course_title,
        lecture_title=lecture_title,
        speaker=speaker,
        chapters=chapters,
    )


def chapter_as_talk(lecture: Lecture, chapter: LectureChapter) -> Talk:
    return Talk(
        title=f"{lecture.lecture_title} - {chapter.heading}",
        speaker=lecture.speaker,
        event=lecture.course_title,
        date="Open Yale Courses",
        plays="",
        description="",
        source_file=Path(lecture.url),
        segments=[Segment("", item.english) for item in chapter.sentences],
    )


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


def build_intro(lecture: Lecture) -> str:
    items = "\n".join(
        f'<li><a href="chapter-{index:02d}.xhtml">{esc(chapter.heading)}</a> - {len(chapter.sentences)} sentences</li>'
        for index, chapter in enumerate(lecture.chapters, start=1)
    )
    return make_xhtml(
        lecture.lecture_title,
        f"""
<section class="intro">
  <h1>{esc(lecture.lecture_title)}</h1>
  <p class="meta">{esc(lecture.course_title)} · {esc(lecture.speaker)}</p>
  <p>Open Yale Courses 강의 스크립트를 문장 단위로 나누어 영어 원문 뒤에 한국어 번역을 괄호로 붙인 개인 영어학습용 EPUB입니다.</p>
  <h2>목차</h2>
  <ol>
    {items}
  </ol>
  <h2>출처 및 라이선스</h2>
  <p>Source: {esc(lecture.speaker)}, {esc(lecture.course_title)} (Yale University: Open Yale Courses), <a href="{esc(lecture.url)}">{esc(lecture.url)}</a>. Accessed {datetime.now().strftime("%Y-%m-%d")}.</p>
  <p>License: Creative Commons BY-NC-SA 3.0. Open Yale Courses Terms of Use: <a href="https://oyc.yale.edu/terms">https://oyc.yale.edu/terms</a>.</p>
</section>
""",
    )


def build_chapter(index: int, chapter: LectureChapter, translations: dict[str, str]) -> str:
    sentence_html = "\n".join(
        f'<p class="sentence"><span class="en">{esc(item.english)}</span> <span class="ko">({esc(translations.get(item.sid, "[번역 누락]"))})</span></p>'
        for item in chapter.sentences
    )
    return make_xhtml(
        chapter.heading,
        f"""
<article>
  <header>
    <p class="chapter-label">Lecture Chapter {index}</p>
    <h1>{esc(chapter.heading)}</h1>
  </header>
  {sentence_html}
</article>
""",
    )


def build_nav(lecture: Lecture) -> str:
    chapter_items = "\n".join(
        f'      <li><a href="chapter-{index:02d}.xhtml">{esc(chapter.heading)}</a></li>'
        for index, chapter in enumerate(lecture.chapters, start=1)
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
{chapter_items}
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


def build_ncx(lecture: Lecture, uid: str) -> str:
    points = [
        """    <navPoint id="navpoint-1" playOrder="1">
      <navLabel><text>소개</text></navLabel>
      <content src="intro.xhtml"/>
    </navPoint>"""
    ]
    for index, chapter in enumerate(lecture.chapters, start=2):
        points.append(
            f"""    <navPoint id="navpoint-{index}" playOrder="{index}">
      <navLabel><text>{esc(chapter.heading)}</text></navLabel>
      <content src="chapter-{index - 1:02d}.xhtml"/>
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
  <docTitle><text>{esc(lecture.lecture_title)}</text></docTitle>
  <navMap>
{chr(10).join(points)}
  </navMap>
</ncx>
"""


def build_opf(lecture: Lecture, uid: str, modified: str) -> str:
    manifest = "\n".join(
        f'    <item id="chapter-{index:02d}" href="chapter-{index:02d}.xhtml" media-type="application/xhtml+xml"/>'
        for index in range(1, len(lecture.chapters) + 1)
    )
    spine = "\n".join(f'    <itemref idref="chapter-{index:02d}"/>' for index in range(1, len(lecture.chapters) + 1))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0" xml:lang="ko">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">{uid}</dc:identifier>
    <dc:title>{esc(lecture.lecture_title)} - Sentence Inline English-Korean Study</dc:title>
    <dc:language>ko</dc:language>
    <dc:creator>{esc(lecture.speaker)}</dc:creator>
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
.chapter-label, .meta {
  color: #555;
}
.intro {
  margin: 0 auto;
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


def write_epub(output: Path, lecture: Lecture, translations: dict[int, dict[str, str]]) -> None:
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
        "OEBPS/content.opf": build_opf(lecture, uid, modified),
        "OEBPS/nav.xhtml": build_nav(lecture),
        "OEBPS/toc.ncx": build_ncx(lecture, uid),
        "OEBPS/style.css": style_css(),
        "OEBPS/intro.xhtml": build_intro(lecture),
    }
    for index, chapter in enumerate(lecture.chapters, start=1):
        files[f"OEBPS/chapter-{index:02d}.xhtml"] = build_chapter(index, chapter, translations[index])

    with zipfile.ZipFile(output, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name, content in files.items():
            media_type = mimetypes.guess_type(name)[0]
            compress_type = zipfile.ZIP_DEFLATED if media_type != "application/epub+zip" else zipfile.ZIP_STORED
            epub.writestr(name, content.encode("utf-8"), compress_type=compress_type)


def validate_epub(path: Path, expected_chapters: int) -> dict[str, int | bool]:
    with zipfile.ZipFile(path) as epub:
        names = set(epub.namelist())
        chapters = sorted(name for name in names if re.fullmatch(r"OEBPS/chapter-\d\d\.xhtml", name))
        if len(chapters) != expected_chapters:
            raise RuntimeError(f"Expected {expected_chapters} chapters, found {len(chapters)}")
        for name in ["OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/intro.xhtml", *chapters]:
            safe_fromstring(epub.read(name))
        joined = "\n".join(epub.read(name).decode("utf-8") for name in chapters)
        inline_pattern = re.compile(
            r'<p class="sentence"><span class="en">.+?</span>\s+<span class="ko">\(.+?\)</span></p>'
        )
        return {
            "chapters": len(chapters),
            "nav": "OEBPS/nav.xhtml" in names,
            "ncx": "OEBPS/toc.ncx" in names,
            "sentences": joined.count('class="sentence"'),
            "inline_parenthetical_matches": len(inline_pattern.findall(joined)),
            "missing_markers": joined.count("[번역 누락]"),
            "skip_markers": joined.count("[번역 생략]"),
        }


def main() -> None:
    args = parse_args()
    lecture = extract_lecture(args.url)
    if args.limit:
        lecture.chapters = lecture.chapters[: args.limit]
    if not lecture.chapters:
        raise SystemExit("No lecture chapters found.")

    args.work_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = args.work_dir / "translations"
    cache_dir.mkdir(parents=True, exist_ok=True)

    translations: dict[int, dict[str, str]] = {}
    for index, chapter in enumerate(lecture.chapters, start=1):
        print(f"[chapter {index}/{len(lecture.chapters)}] {chapter.heading} - {len(chapter.sentences)} sentences", flush=True)
        translations[index] = translate_talk(chapter_as_talk(lecture, chapter), args, cache_dir)

    write_epub(args.output, lecture, translations)
    stats = validate_epub(args.output, len(lecture.chapters))
    print(f"[done] {args.output}", flush=True)
    for key, value in stats.items():
        print(f"[done] {key}={value}", flush=True)
    print(f"[done] size={args.output.stat().st_size}", flush=True)


if __name__ == "__main__":
    main()
