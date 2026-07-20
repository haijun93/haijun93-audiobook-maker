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

from build_ted_transcript_study_epub import (
    DEFAULT_ATTACHMENT_PATHS,
    Segment,
    Talk,
    translate_talk,
    unique_talks,
)
from safe_xml import safe_fromstring


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK_DIR = ROOT / ".work" / "ted_sentence_inline_study_work"
DEFAULT_OUTPUT = ROOT / ".work" / "TED_Transcript_Based_Sentence_Inline_English_Korean_Study.epub"


@dataclass(frozen=True)
class SentenceItem:
    sid: str
    timecode: str
    english: str


ABBREVIATIONS = [
    "Mr.",
    "Mrs.",
    "Ms.",
    "Dr.",
    "Prof.",
    "Sr.",
    "Jr.",
    "St.",
    "vs.",
    "etc.",
    "e.g.",
    "i.e.",
    "U.S.",
    "U.K.",
    "U.N.",
    "D.C.",
    "A.M.",
    "P.M.",
    "Inc.",
    "Ltd.",
    "Co.",
    "No.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a TED English-Korean sentence-inline Kindle study EPUB."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--model", default="exaone3.5:7.8b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--max-chars", type=int, default=7000)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--skip-translation", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("paths", nargs="*", type=Path)
    return parser.parse_args()


def protect_abbreviations(text: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    protected = text
    for index, abbr in enumerate(ABBREVIATIONS):
        token = f"__ABBR_{index}__"
        replacements[token] = abbr
        protected = protected.replace(abbr, abbr.replace(".", token))
    protected = re.sub(
        r"\b([A-Z])\.",
        lambda match: match.group(1) + "__INIT_DOT__",
        protected,
    )
    replacements["__INIT_DOT__"] = "."
    return protected, replacements


def restore_abbreviations(text: str, replacements: dict[str, str]) -> str:
    restored = text
    for token, original in replacements.items():
        if token == "__INIT_DOT__":
            restored = restored.replace(token, original)
        else:
            restored = restored.replace(token, ".")
    return restored


def split_stage_cues(text: str) -> list[str]:
    pieces: list[str] = []
    pattern = re.compile(r"(\((?:Laughter|Applause|Music|Cheers|Audience|Video|Singing)[^)]*\))")
    for part in pattern.split(text):
        stripped = part.strip()
        if stripped:
            pieces.append(stripped)
    return pieces


def split_english_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    protected, replacements = protect_abbreviations(normalized)
    raw_parts = re.findall(r"[^.!?]+[.!?]+(?:[\"')\]]+)?|[^.!?]+$", protected)
    sentences: list[str] = []
    for raw in raw_parts:
        restored = restore_abbreviations(raw.strip(), replacements)
        for piece in split_stage_cues(restored):
            if piece:
                sentences.append(piece)
    return sentences


def collect_sentences(talk: Talk) -> list[SentenceItem]:
    items: list[SentenceItem] = []
    for segment in talk.segments:
        for sentence in split_english_sentences(segment.text):
            sid = f"S{len(items) + 1:03d}"
            items.append(SentenceItem(sid=sid, timecode=segment.timecode, english=sentence))
    return items


def sentence_talk(talk: Talk, items: list[SentenceItem]) -> Talk:
    return Talk(
        title=talk.title,
        speaker=talk.speaker,
        event=talk.event,
        date=talk.date,
        plays=talk.plays,
        description=talk.description,
        source_file=talk.source_file,
        segments=[Segment(item.timecode, item.english) for item in items],
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


def build_intro(talks: list[Talk], sentence_counts: dict[str, int]) -> str:
    rows = "\n".join(
        f"<li><a href=\"chapter-{index:02d}.xhtml\">{esc(talk.title)}</a> - {esc(talk.speaker)} ({sentence_counts[talk.title]} sentences)</li>"
        for index, talk in enumerate(talks, start=1)
    )
    return make_xhtml(
        "TED Sentence Inline Study",
        f"""
<section class="intro">
  <h1>TED Sentence Inline Study</h1>
  <p>사용자가 제공한 TED 강의 스크립트를 문장 단위로 나누어 영어 원문 뒤에 한국어 번역을 괄호로 붙인 개인 영어학습용 EPUB입니다.</p>
  <h2>목차</h2>
  <ol>
    {rows}
  </ol>
</section>
""",
    )


def build_chapter(
    index: int,
    talk: Talk,
    items: list[SentenceItem],
    translations: dict[str, str],
) -> str:
    by_time: dict[str, list[SentenceItem]] = {}
    for item in items:
        by_time.setdefault(item.timecode, []).append(item)

    blocks: list[str] = []
    for timecode, time_items in by_time.items():
        sentence_lines = []
        for item in time_items:
            korean = translations.get(item.sid, "[번역 누락]")
            sentence_lines.append(
                f'<p class="sentence"><span class="en">{esc(item.english)}</span> '
                f'<span class="ko">({esc(korean)})</span></p>'
            )
        blocks.append(
            f"""
<section class="time-block">
  <p class="time">{esc(timecode)}</p>
  {''.join(sentence_lines)}
</section>
"""
        )

    description = f"<p class=\"description\">{esc(talk.description)}</p>" if talk.description else ""
    return make_xhtml(
        talk.title,
        f"""
<article>
  <header>
    <p class="chapter-label">Talk {index:02d}</p>
    <h1>{esc(talk.title)}</h1>
    <p class="meta">{esc(talk.speaker)} · {esc(talk.event)} · {esc(talk.date)} · {esc(talk.plays)} plays</p>
    <p class="source"><a href="{esc(talk.url)}">TED page</a></p>
    {description}
  </header>
  {''.join(blocks)}
</article>
""",
    )


def build_nav(talks: list[Talk]) -> str:
    chapter_items = "\n".join(
        f'      <li><a href="chapter-{index:02d}.xhtml">{esc(talk.title)}</a></li>'
        for index, talk in enumerate(talks, start=1)
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


def build_ncx(talks: list[Talk], uid: str) -> str:
    points = [
        """    <navPoint id="navpoint-1" playOrder="1">
      <navLabel><text>소개</text></navLabel>
      <content src="intro.xhtml"/>
    </navPoint>"""
    ]
    for index, talk in enumerate(talks, start=2):
        points.append(
            f"""    <navPoint id="navpoint-{index}" playOrder="{index}">
      <navLabel><text>{esc(talk.title)}</text></navLabel>
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
  <docTitle><text>TED Sentence Inline Study</text></docTitle>
  <navMap>
{chr(10).join(points)}
  </navMap>
</ncx>
"""


def build_opf(talks: list[Talk], uid: str, modified: str) -> str:
    manifest = "\n".join(
        f'    <item id="chapter-{index:02d}" href="chapter-{index:02d}.xhtml" media-type="application/xhtml+xml"/>'
        for index in range(1, len(talks) + 1)
    )
    spine = "\n".join(f'    <itemref idref="chapter-{index:02d}"/>' for index in range(1, len(talks) + 1))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0" xml:lang="ko">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">{uid}</dc:identifier>
    <dc:title>TED Sentence Inline English-Korean Study</dc:title>
    <dc:language>ko</dc:language>
    <dc:creator>Codex</dc:creator>
    <dc:publisher>Personal study edition</dc:publisher>
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
.chapter-label, .meta, .source, .description, .time {
  color: #555;
}
.time-block {
  border-top: 1px solid #ddd;
  margin: 1.15em 0;
  padding-top: 0.7em;
}
.time {
  font-family: sans-serif;
  font-size: 0.85em;
  margin-bottom: 0.45em;
}
.sentence {
  margin: 0.58em 0;
}
.ko {
  color: #444;
}
"""


def write_epub(
    output: Path,
    talks: list[Talk],
    sentence_items: dict[str, list[SentenceItem]],
    translations_by_title: dict[str, dict[str, str]],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    uid = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sentence_counts = {title: len(items) for title, items in sentence_items.items()}

    files: dict[str, str] = {
        "META-INF/container.xml": """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        "OEBPS/content.opf": build_opf(talks, uid, modified),
        "OEBPS/nav.xhtml": build_nav(talks),
        "OEBPS/toc.ncx": build_ncx(talks, uid),
        "OEBPS/style.css": style_css(),
        "OEBPS/intro.xhtml": build_intro(talks, sentence_counts),
    }
    for index, talk in enumerate(talks, start=1):
        files[f"OEBPS/chapter-{index:02d}.xhtml"] = build_chapter(
            index,
            talk,
            sentence_items[talk.title],
            translations_by_title[talk.title],
        )

    with zipfile.ZipFile(output, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name, content in files.items():
            data = content.encode("utf-8")
            media_type = mimetypes.guess_type(name)[0]
            compress_type = zipfile.ZIP_DEFLATED if media_type != "application/epub+zip" else zipfile.ZIP_STORED
            epub.writestr(name, data, compress_type=compress_type)


def validate_epub(path: Path, expected_chapters: int) -> dict[str, int | bool]:
    with zipfile.ZipFile(path) as epub:
        names = set(epub.namelist())
        chapters = sorted(name for name in names if re.fullmatch(r"OEBPS/chapter-\d\d\.xhtml", name))
        if len(chapters) != expected_chapters:
            raise RuntimeError(f"Expected {expected_chapters} chapters, found {len(chapters)}")
        for name in ["OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/intro.xhtml", *chapters]:
            safe_fromstring(epub.read(name))
        all_chapters = "\n".join(epub.read(name).decode("utf-8") for name in chapters)
        nav = epub.read("OEBPS/nav.xhtml").decode("utf-8")
        ncx = epub.read("OEBPS/toc.ncx").decode("utf-8")
        return {
            "chapters": len(chapters),
            "nav_links": nav.count("<li><a href="),
            "ncx_navpoints": ncx.count("<navPoint "),
            "sentences": all_chapters.count('class="sentence"'),
            "en_spans": all_chapters.count('class="en"'),
            "ko_spans": all_chapters.count('class="ko"'),
            "missing_markers": all_chapters.count("[번역 누락]"),
            "skip_markers": all_chapters.count("[번역 생략]"),
        }


def main() -> None:
    args = parse_args()
    input_paths = args.paths or [Path(path) for path in DEFAULT_ATTACHMENT_PATHS]
    talks = unique_talks(input_paths)
    if args.limit:
        talks = talks[: args.limit]
    if not talks:
        raise SystemExit("No talks found.")

    args.work_dir.mkdir(parents=True, exist_ok=True)
    translation_cache_dir = args.work_dir / "translations"
    translation_cache_dir.mkdir(parents=True, exist_ok=True)
    sentence_items: dict[str, list[SentenceItem]] = {}
    translations_by_title: dict[str, dict[str, str]] = {}
    for talk_index, talk in enumerate(talks, start=1):
        items = collect_sentences(talk)
        sentence_items[talk.title] = items
        print(f"[talk {talk_index}/{len(talks)}] {talk.title} - {len(items)} sentences", flush=True)
        translations_by_title[talk.title] = translate_talk(
            sentence_talk(talk, items),
            args,
            translation_cache_dir,
        )

    write_epub(args.output, talks, sentence_items, translations_by_title)
    stats = validate_epub(args.output, len(talks))
    print(f"[done] {args.output}", flush=True)
    for key, value in stats.items():
        print(f"[done] {key}={value}", flush=True)
    print(f"[done] size={args.output.stat().st_size}", flush=True)


if __name__ == "__main__":
    main()
