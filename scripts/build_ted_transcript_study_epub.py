#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from safe_xml import safe_fromstring


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK_DIR = ROOT / ".work" / "ted_transcript_study_work"
DEFAULT_OUTPUT = ROOT / ".work" / "TED_Transcript_Based_Korean_English_Study.epub"

DEFAULT_ATTACHMENT_PATHS = [
    str(Path.home()) + "/.codex/attachments/f2c8fc01-080a-49b6-8ddb-afc2b565e5d1/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/43ba054b-915f-4fdf-9fcb-abf42712b4b3/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/15b66b61-04a5-4768-b27a-149e9656bca3/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/a1e09361-2016-4399-8cc0-80b5ad844bc0/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/a48c641a-58be-4c6a-8c44-82bdabd9d41d/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/a4214182-ba5e-469b-919c-a3b4a6996afc/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/bd78bc92-c12f-4e78-bd4d-bb5c1b801b36/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/5a2e3d7a-f5b7-4285-8dfc-b79498ca99e1/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/6f7d1d30-93a0-415c-8eb0-4a8005e17ba4/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/99a92e8a-3080-4f88-b494-c3d2dcd7fc6a/pasted-text.txt",
    str(Path.home()) + "/.codex/attachments/c79a4323-09e9-4f4e-9e1c-bcba702f162f/pasted-text.txt",
]

URL_BY_TITLE = {
    "Why the best ideas come from play": "https://www.ted.com/talks/maxwell_pearce_why_the_best_ideas_come_from_play",
    "Where good ideas come from": "https://www.ted.com/talks/steven_johnson_where_good_ideas_come_from",
    "How great leaders inspire action": "https://www.ted.com/talks/simon_sinek_how_great_leaders_inspire_action",
    "The power of vulnerability": "https://www.ted.com/talks/brene_brown_the_power_of_vulnerability",
    "Your body language may shape who you are": "https://www.ted.com/talks/amy_cuddy_your_body_language_may_shape_who_you_are",
    "The happy secret to better work": "https://www.ted.com/talks/shawn_achor_the_happy_secret_to_better_work",
    "The power of introverts": "https://www.ted.com/talks/susan_cain_the_power_of_introverts",
    "Grit: The power of passion and perseverance": "https://www.ted.com/talks/angela_lee_duckworth_grit_the_power_of_passion_and_perseverance",
    "The next outbreak? We're not ready": "https://www.ted.com/talks/bill_gates_the_next_outbreak_we_re_not_ready",
    "Inside the mind of a master procrastinator": "https://www.ted.com/talks/tim_urban_inside_the_mind_of_a_master_procrastinator",
}


@dataclass(frozen=True)
class Segment:
    timecode: str
    text: str


@dataclass
class Talk:
    title: str
    speaker: str
    event: str
    date: str
    plays: str
    description: str
    source_file: Path
    segments: list[Segment]

    @property
    def slug(self) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return base or hashlib.sha1(self.title.encode(), usedforsecurity=False).hexdigest()[:12]

    @property
    def url(self) -> str:
        return URL_BY_TITLE.get(self.title, "https://www.ted.com/talks")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a private Korean-English Kindle study EPUB from user-provided TED transcript text files."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--model", default="gemma4:26b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--max-chars", type=int, default=3000)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--skip-translation", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N unique talks.")
    parser.add_argument("paths", nargs="*", type=Path, help="TED pasted-text transcript files.")
    return parser.parse_args()


def compact_lines(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def line_after(lines: list[str], marker: str) -> str:
    for index, line in enumerate(lines):
        if line == marker and index + 1 < len(lines):
            return lines[index + 1]
    return ""


def extract_header(lines: list[str]) -> tuple[str, str, str, str, str]:
    title = ""
    plays = ""
    for index, line in enumerate(lines):
        if re.fullmatch(r"[\d,]+ plays", line):
            plays = line.replace(" plays", "")
            title = lines[index - 1] if index > 0 else ""
            break

    speaker = line_after(lines, "About the speaker")

    event = ""
    date = ""
    for index, line in enumerate(lines):
        if line == "|" and index + 3 < len(lines):
            possible_speaker = lines[index + 1]
            if possible_speaker == speaker or not speaker:
                event = lines[index + 3]
                if index + 4 < len(lines) and lines[index + 4].startswith("•"):
                    date = lines[index + 4].lstrip("• ").strip()
                break

    return title, speaker, event, date, plays


def extract_description(lines: list[str]) -> str:
    try:
        start = lines.index("Read transcript") + 1
    except ValueError:
        return ""
    stop_markers = {"Ideas are better live", "About the speaker", "Transcript"}
    body: list[str] = []
    for line in lines[start:]:
        if line in stop_markers or line.startswith("Transcript ("):
            break
        body.append(line)
    return " ".join(body).strip()


def extract_segments(lines: list[str]) -> list[Segment]:
    transcript_index = next(
        (index for index, line in enumerate(lines) if line.startswith("Transcript (")),
        None,
    )
    if transcript_index is None:
        return []
    english_index = next(
        (index for index in range(transcript_index, len(lines)) if lines[index] == "English"),
        None,
    )
    if english_index is None:
        return []

    end_index = next(
        (index for index in range(english_index + 1, len(lines)) if lines[index] == "Explore"),
        len(lines),
    )
    current_time = ""
    current_text: list[str] = []
    segments: list[Segment] = []

    for line in lines[english_index + 1 : end_index]:
        if re.fullmatch(r"\d\d:\d\d", line):
            if current_time and current_text:
                segments.append(Segment(current_time, normalize_segment_text(current_text)))
            current_time = line
            current_text = []
            continue
        if current_time:
            current_text.append(line)

    if current_time and current_text:
        segments.append(Segment(current_time, normalize_segment_text(current_text)))

    return [segment for segment in segments if segment.text]


def normalize_segment_text(lines: list[str]) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_talk(path: Path) -> Talk:
    lines = compact_lines(path.read_text(encoding="utf-8", errors="replace").splitlines())
    title, speaker, event, date, plays = extract_header(lines)
    description = extract_description(lines)
    segments = extract_segments(lines)
    if not title:
        raise ValueError(f"Could not find title in {path}")
    if not segments:
        raise ValueError(f"Could not find transcript segments in {path}")
    return Talk(
        title=title,
        speaker=speaker,
        event=event,
        date=date,
        plays=plays,
        description=description,
        source_file=path,
        segments=segments,
    )


def unique_talks(paths: list[Path]) -> list[Talk]:
    talks: list[Talk] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            print(f"[skip] missing file: {path}", flush=True)
            continue
        talk = parse_talk(path)
        key = re.sub(r"[^a-z0-9]+", " ", talk.title.lower()).strip()
        if key in seen:
            print(f"[skip] duplicate: {talk.title} ({path})", flush=True)
            continue
        seen.add(key)
        talks.append(talk)
    return talks


def chunk_segments(segments: list[Segment], max_chars: int) -> list[list[tuple[str, Segment]]]:
    chunks: list[list[tuple[str, Segment]]] = []
    current: list[tuple[str, Segment]] = []
    current_chars = 0
    for index, segment in enumerate(segments, start=1):
        sid = f"S{index:03d}"
        size = len(segment.text) + 32
        if current and current_chars + size > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append((sid, segment))
        current_chars += size
    if current:
        chunks.append(current)
    return chunks


def cache_key(talk: Talk, chunk: list[tuple[str, Segment]], model: str) -> str:
    payload = {
        "model": model,
        "title": talk.title,
        "segments": [(sid, segment.timecode, segment.text) for sid, segment in chunk],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def build_prompt(talk: Talk, chunk: list[tuple[str, Segment]]) -> str:
    lines = [
        "You are a professional Korean translator creating a private English-learning EPUB.",
        "Translate each TED transcript segment into natural, polished Korean.",
        "Preserve the speaker's meaning, rhythm, humor, and oral lecture tone.",
        "Return only the translations in the exact ID format below.",
        "Do not add explanations, markdown tables, titles, or English originals.",
        "",
        "Required output format:",
        "[ID: S001]",
        "한국어 번역문",
        "[ID: S002]",
        "한국어 번역문",
        "",
        f"Talk title: {talk.title}",
        f"Speaker: {talk.speaker}",
        "",
        "Segments:",
    ]
    for sid, segment in chunk:
        lines.extend(
            [
                f"[ID: {sid} | {segment.timecode}]",
                segment.text,
                "",
            ]
        )
    return "\n".join(lines)


def call_ollama(prompt: str, args: argparse.Namespace) -> str:
    payload = {
        "model": args.model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.15,
            "top_p": 0.9,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        args.ollama_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body.get("response", "").strip()


def parse_translation_response(response: str) -> dict[str, str]:
    matches = list(re.finditer(r"\[ID:\s*(S\d{3})(?:[^\]]*)\]\s*", response))
    translations: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(response)
        text = response[start:end].strip()
        text = re.sub(r"^```(?:\w+)?|```$", "", text).strip()
        if text:
            translations[match.group(1)] = text
    return translations


def clean_single_translation(response: str) -> str:
    text = response.strip()
    text = re.sub(r"^```(?:\w+)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    text = re.sub(r"^\[ID:\s*S\d{3}(?:[^\]]*)\]\s*", "", text).strip()
    text = re.sub(r"^S\d{3}\s*[:：-]\s*", "", text).strip()
    text = re.sub(r"^한국어\s*번역문\s*[:：-]?\s*", "", text).strip()
    return text


def translate_chunk(
    talk: Talk,
    chunk: list[tuple[str, Segment]],
    args: argparse.Namespace,
    cache_dir: Path,
) -> dict[str, str]:
    key = cache_key(talk, chunk, args.model)
    cache_file = cache_dir / f"{talk.slug}_{key}.json"
    expected = {sid for sid, _segment in chunk}
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        translations = cached.get("translations", {})
        if expected <= set(translations):
            return {sid: translations[sid] for sid in expected}

    if args.skip_translation:
        translations = {sid: "[번역 생략]" for sid in expected}
        cache_file.write_text(
            json.dumps({"translations": translations}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return translations

    prompt = build_prompt(talk, chunk)
    last_error = ""
    last_response = ""
    for attempt in range(1, 4):
        try:
            response = call_ollama(prompt, args)
            last_response = response
            translations = parse_translation_response(response)
            missing = expected - set(translations)
            if not missing:
                cache_file.write_text(
                    json.dumps(
                        {
                            "title": talk.title,
                            "model": args.model,
                            "translations": translations,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                return translations
            last_error = f"missing IDs: {', '.join(sorted(missing))}"
            if len(chunk) > 1 or response.strip():
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = repr(exc)
        time.sleep(2 * attempt)

    if len(chunk) == 1:
        sid, segment = chunk[0]
        fallback = clean_single_translation(last_response)
        if fallback:
            translations = {sid: fallback}
            cache_file.write_text(
                json.dumps(
                    {
                        "title": talk.title,
                        "model": args.model,
                        "translations": translations,
                        "fallback": "single-segment-raw-response",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return translations
        raise RuntimeError(f"Translation failed for {talk.title} {sid} {segment.timecode}: {last_error}")

    print(f"[retry smaller] {talk.title}: {last_error}", flush=True)
    midpoint = max(1, len(chunk) // 2)
    translations: dict[str, str] = {}
    translations.update(translate_chunk(talk, chunk[:midpoint], args, cache_dir))
    translations.update(translate_chunk(talk, chunk[midpoint:], args, cache_dir))
    return translations


def translate_talk(talk: Talk, args: argparse.Namespace, cache_dir: Path) -> dict[str, str]:
    chunks = chunk_segments(talk.segments, args.max_chars)
    all_translations: dict[str, str] = {}
    for index, chunk in enumerate(chunks, start=1):
        print(f"[translate] {talk.title} chunk {index}/{len(chunks)} ({len(chunk)} segments)", flush=True)
        all_translations.update(translate_chunk(talk, chunk, args, cache_dir))
    return all_translations


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def make_xhtml(title: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ko" lang="ko">
<head>
  <title>{escape(title)}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
{body}
</body>
</html>
"""


def build_intro(talks: list[Talk]) -> str:
    rows = "\n".join(
        f"<li><a href=\"chapter-{index:02d}.xhtml\">{escape(talk.title)}</a> - {escape(talk.speaker)}</li>"
        for index, talk in enumerate(talks, start=1)
    )
    return make_xhtml(
        "TED Transcript Study",
        f"""
<section class="intro">
  <h1>TED Transcript Study</h1>
  <p class="notice">사용자가 제공한 TED transcript 텍스트를 기반으로 만든 개인 영어학습용 한영 EPUB입니다.</p>
  <p>각 장은 한국어 번역과 영어 원문을 timestamp별로 배치했습니다. Kindle에서 목차로 강연별 이동이 가능합니다.</p>
  <h2>강연 목록</h2>
  <ol>
    {rows}
  </ol>
</section>
""",
    )


def build_chapter(index: int, talk: Talk, translations: dict[str, str]) -> str:
    blocks: list[str] = []
    for seg_index, segment in enumerate(talk.segments, start=1):
        sid = f"S{seg_index:03d}"
        korean = translations.get(sid, "[번역 누락]")
        blocks.append(
            f"""
<section class="pair" id="{sid}">
  <p class="time">{escape(segment.timecode)}</p>
  <p class="ko">{escape(korean)}</p>
  <p class="en">{escape(segment.text)}</p>
</section>
"""
        )

    description = f"<p class=\"description\">{escape(talk.description)}</p>" if talk.description else ""
    return make_xhtml(
        talk.title,
        f"""
<article>
  <header>
    <p class="chapter-label">Talk {index:02d}</p>
    <h1>{escape(talk.title)}</h1>
    <p class="meta">{escape(talk.speaker)} · {escape(talk.event)} · {escape(talk.date)} · {escape(talk.plays)} plays</p>
    <p class="source"><a href="{escape(talk.url)}">TED page</a></p>
    {description}
  </header>
  {''.join(blocks)}
</article>
""",
    )


def build_nav(talks: list[Talk]) -> str:
    chapter_items = "\n".join(
        f'      <li><a href="chapter-{index:02d}.xhtml">{escape(talk.title)}</a></li>'
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
      <navLabel><text>{escape(talk.title)}</text></navLabel>
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
  <docTitle><text>TED Transcript Study</text></docTitle>
  <navMap>
{chr(10).join(points)}
  </navMap>
</ncx>
"""


def build_opf(talks: list[Talk], uid: str, modified: str) -> str:
    chapter_manifest = "\n".join(
        f'    <item id="chapter-{index:02d}" href="chapter-{index:02d}.xhtml" media-type="application/xhtml+xml"/>'
        for index in range(1, len(talks) + 1)
    )
    chapter_spine = "\n".join(f'    <itemref idref="chapter-{index:02d}"/>' for index in range(1, len(talks) + 1))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0" xml:lang="ko">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">{uid}</dc:identifier>
    <dc:title>TED Transcript Study</dc:title>
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
{chapter_manifest}
  </manifest>
  <spine toc="ncx">
    <itemref idref="intro"/>
{chapter_spine}
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
.notice {
  border-left: 4px solid #245c9f;
  padding-left: 0.8em;
}
.chapter-label, .meta, .source, .description, .time {
  color: #555;
}
.pair {
  border-top: 1px solid #ddd;
  margin: 1.2em 0;
  padding-top: 0.8em;
}
.time {
  font-family: sans-serif;
  font-size: 0.85em;
  margin-bottom: 0.35em;
}
.ko {
  font-size: 1.03em;
  margin: 0.2em 0 0.4em;
}
.en {
  color: #333;
  font-size: 0.92em;
  margin: 0.2em 0 0.8em;
}
"""


def write_epub(output: Path, talks: list[Talk], translations_by_title: dict[str, dict[str, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    uid = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files: dict[str, str | bytes] = {
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
        "OEBPS/intro.xhtml": build_intro(talks),
    }
    for index, talk in enumerate(talks, start=1):
        files[f"OEBPS/chapter-{index:02d}.xhtml"] = build_chapter(
            index,
            talk,
            translations_by_title[talk.title],
        )

    with zipfile.ZipFile(output, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name, content in files.items():
            if isinstance(content, str):
                data = content.encode("utf-8")
            else:
                data = content
            media_type = mimetypes.guess_type(name)[0]
            compress_type = zipfile.ZIP_DEFLATED if media_type != "application/epub+zip" else zipfile.ZIP_STORED
            epub.writestr(name, data, compress_type=compress_type)


def validate_epub(path: Path, expected_chapters: int) -> None:
    with zipfile.ZipFile(path) as epub:
        names = set(epub.namelist())
        required = {
            "mimetype",
            "META-INF/container.xml",
            "OEBPS/content.opf",
            "OEBPS/nav.xhtml",
            "OEBPS/toc.ncx",
            "OEBPS/intro.xhtml",
        }
        missing = sorted(required - names)
        if missing:
            raise RuntimeError(f"EPUB missing required files: {missing}")
        chapter_count = sum(1 for name in names if re.fullmatch(r"OEBPS/chapter-\d\d\.xhtml", name))
        if chapter_count != expected_chapters:
            raise RuntimeError(f"Expected {expected_chapters} chapters, found {chapter_count}")
        for name in ["OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/intro.xhtml"]:
            safe_fromstring(epub.read(name))
        for index in range(1, expected_chapters + 1):
            safe_fromstring(epub.read(f"OEBPS/chapter-{index:02d}.xhtml"))


def main() -> None:
    args = parse_args()
    input_paths = args.paths or [Path(path) for path in DEFAULT_ATTACHMENT_PATHS]
    talks = unique_talks(input_paths)
    if args.limit:
        talks = talks[: args.limit]
    if not talks:
        raise SystemExit("No talks found.")

    args.work_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = args.work_dir / "translations"
    cache_dir.mkdir(parents=True, exist_ok=True)

    translations_by_title: dict[str, dict[str, str]] = {}
    for talk_index, talk in enumerate(talks, start=1):
        print(f"[talk {talk_index}/{len(talks)}] {talk.title} - {len(talk.segments)} segments", flush=True)
        translations_by_title[talk.title] = translate_talk(talk, args, cache_dir)

    write_epub(args.output, talks, translations_by_title)
    validate_epub(args.output, len(talks))
    print(f"[done] {args.output}", flush=True)
    print(f"[done] talks={len(talks)} size={args.output.stat().st_size}", flush=True)


if __name__ == "__main__":
    main()
