#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


DEFAULT_EPUB = Path("/Users/hyeokjunkong/Desktop/소설/#[k-e]/[k-e] Artemis.epub")
P_RE = re.compile(r"<p(?P<attrs>[^>]*)>(?P<body>.*?)</p>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
LATIN_RE = re.compile(r"[A-Za-z]")


def split_inline_pair(body: str) -> tuple[str, str] | None:
    stripped = body.strip()
    if not stripped or TAG_RE.search(stripped):
        return None
    if stripped in {"&#160;", "&nbsp;"}:
        return None

    end = len(stripped) - 1
    if end < 0 or stripped[end] != ")":
        return None

    depth = 0
    start = -1
    for index in range(end, -1, -1):
        char = stripped[index]
        if char == ")":
            depth += 1
        elif char == "(":
            depth -= 1
            if depth == 0:
                start = index
                break
    if start <= 0:
        pair = split_inline_pair_fallback(stripped)
        if pair is None:
            return None
        korean, english = pair
    else:
        korean = stripped[:start].rstrip()
        english = stripped[start:].strip()
    if not korean or not LATIN_RE.search(english):
        return None
    return korean, english


def split_inline_pair_fallback(stripped: str) -> tuple[str, str] | None:
    """Handle a few legacy Artemis lines with unbalanced trailing parentheses."""
    candidates = list(re.finditer(r"\s+\(", stripped))
    for match in reversed(candidates):
        korean = stripped[: match.start()].rstrip()
        english = stripped[match.start() :].strip()
        if korean and english.startswith("(") and LATIN_RE.search(english):
            return korean, english
    return None


def convert_xhtml(text: str) -> tuple[str, int]:
    converted = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal converted
        attrs = match.group("attrs")
        body = match.group("body")
        if "class=" in attrs and re.search(r"class=[\"'][^\"']*(?:space|scene-break|pair)[^\"']*[\"']", attrs):
            return match.group(0)
        pair = split_inline_pair(body)
        if pair is None:
            return match.group(0)
        ko, en = pair
        converted += 1
        return (
            '<p class="pair">'
            f'<span class="ko" xml:lang="ko">{ko}</span> '
            f'<span class="en" xml:lang="en">{en}</span>'
            "</p>"
        )

    converted_text = P_RE.sub(replace, text)
    repaired_text, repaired = repair_known_pair_splits(converted_text)
    return repaired_text, converted + repaired


def repair_known_pair_splits(text: str) -> tuple[str, int]:
    replacements = {
        (
            '<p class="pair"><span class="ko" xml:lang="ko">그는 로버를 몰아 도시 쪽으로 돌아갔다. '
            '“스보보다랑 네 아버지한테 연락해서 네가 무사하다고 알려.</span> '
            '<span class="en" xml:lang="en">(He drove us back toward town.)</span></p>\n'
            '<p class="pair"><span class="ko" xml:lang="ko">”</span> '
            '<span class="en" xml:lang="en">(“You should call Svoboda and your dad to let him know you’re okay.”)</span></p>'
        ): (
            '<p class="pair"><span class="ko" xml:lang="ko">그는 로버를 몰아 도시 쪽으로 돌아갔다.</span> '
            '<span class="en" xml:lang="en">(He drove us back toward town.)</span></p>\n'
            '<p class="pair"><span class="ko" xml:lang="ko">“스보보다랑 네 아버지한테 연락해서 네가 무사하다고 알려.”</span> '
            '<span class="en" xml:lang="en">(“You should call Svoboda and your dad to let him know you’re okay.”)</span></p>'
        )
    }
    repaired = 0
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new, 1)
            repaired += 1
    return text, repaired


def update_css(css: str) -> str:
    if "span.en" in css and "p.pair" in css:
        return css
    addition = """
p.pair {
  margin-bottom: 0.76em;
}
p.scene-break {
  margin: 1.4em 0;
  text-align: center;
}
span.en {
  color: #4a4a4a;
  font-size: 0.94em;
}
"""
    return css.rstrip() + "\n" + addition.lstrip()


def update_modified_timestamp(opf: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return re.sub(
        r"<meta property=\"dcterms:modified\">[^<]+</meta>",
        f'<meta property="dcterms:modified">{timestamp}</meta>',
        opf,
        count=1,
    )


def validate_epub(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if names[:1] != ["mimetype"]:
            raise RuntimeError("mimetype must be the first ZIP entry")
        for name in names:
            lower = name.lower()
            if lower.endswith((".xhtml", ".html", ".htm", ".opf", ".ncx")):
                ET.fromstring(archive.read(name))


def rewrite_epub(epub: Path, backup_dir: Path) -> dict[str, int]:
    epub = epub.expanduser().resolve()
    if not epub.exists():
        raise FileNotFoundError(epub)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{epub.stem}.before_span_conversion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.epub"
    shutil.copy2(epub, backup)

    counts: dict[str, int] = {}
    with zipfile.ZipFile(epub) as source:
        infos = source.infolist()
        payload: dict[str, bytes] = {}
        for info in infos:
            data = source.read(info.filename)
            lower = info.filename.lower()
            if lower.endswith((".xhtml", ".html", ".htm")) and not lower.endswith("nav.xhtml"):
                text = data.decode("utf-8")
                converted_text, converted = convert_xhtml(text)
                if converted:
                    counts[info.filename] = converted
                    data = converted_text.encode("utf-8")
            elif lower.endswith(".css"):
                data = update_css(data.decode("utf-8")).encode("utf-8")
            elif lower.endswith(".opf"):
                data = update_modified_timestamp(data.decode("utf-8")).encode("utf-8")
            payload[info.filename] = data

    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub", dir=str(epub.parent)) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        with zipfile.ZipFile(tmp_path, "w") as out:
            mimetype = payload.get("mimetype", b"application/epub+zip")
            out.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)
            for info in infos:
                if info.filename == "mimetype":
                    continue
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.comment = info.comment
                zi.extra = info.extra
                zi.internal_attr = info.internal_attr
                zi.external_attr = info.external_attr
                zi.create_system = info.create_system
                out.writestr(zi, payload[info.filename], compress_type=zipfile.ZIP_DEFLATED)
        validate_epub(tmp_path)
        tmp_path.replace(epub)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        shutil.copy2(backup, epub)
        raise

    validate_epub(epub)
    counts["_backup"] = str(backup)  # type: ignore[assignment]
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Artemis legacy inline bilingual EPUB to span pair format.")
    parser.add_argument("--epub", type=Path, default=DEFAULT_EPUB)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_EPUB.parent / "_batch_logs")
    args = parser.parse_args()

    result = rewrite_epub(args.epub, args.backup_dir)
    backup = result.pop("_backup")
    total = sum(int(value) for value in result.values())
    print(f"converted_pairs={total}")
    print(f"backup={backup}")
    for name, count in sorted(result.items()):
        print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
