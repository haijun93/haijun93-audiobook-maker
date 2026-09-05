#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import re
import zipfile
from collections import Counter
from pathlib import Path

import fitz


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PDF를 Kindle용 EPUB으로 변환합니다. 재흐름형 또는 원본 보존형을 선택할 수 있습니다."
    )
    parser.add_argument("input_pdf", type=Path, help="입력 PDF 파일")
    parser.add_argument("--output-epub", type=Path, help="출력 EPUB 경로")
    parser.add_argument(
        "--mode",
        choices=("reflow", "fixed"),
        default="reflow",
        help="reflow=텍스트 재흐름형, fixed=원본 페이지 보존형",
    )
    return parser.parse_args()


def normalize_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_pdf_title(raw_stem: str) -> str:
    """PDF 파일명을 표지/메타데이터에 쓸 수 있는 사람이 읽을 제목으로 정제한다.

    변환되지 않은 원본 파일명(예: ``_OceanofPDF.com_Cage_of_Ice_and_Echoes_-_Pam_Godwin``)이
    그대로 ``dc:title``에 들어가면, 이후 파이프라인 전체(표지 플레이스홀더, 온라인 표지 검색,
    번역 프롬프트)에 더러운 제목이 그대로 퍼진다.
    """
    title = re.sub(r"(?i)[_\s]*oceanofpdf[._\s-]*com[_\s]*", " ", raw_stem)
    title = re.sub(r"^\[(?:e|s|k|k-e)\]\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[_-]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or raw_stem


def collect_pages(pdf_path: Path) -> list[list[str]]:
    pages: list[list[str]] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            lines = [normalize_line(line) for line in page.get_text("text").splitlines()]
            pages.append([line for line in lines if line])
    return pages


def repeated_noise_lines(pages: list[list[str]]) -> set[str]:
    counter: Counter[str] = Counter()
    total_pages = len(pages)
    for lines in pages:
        counter.update(set(lines))

    threshold = max(3, int(total_pages * 0.6))
    removable: set[str] = set()
    for line, count in counter.items():
        if count >= threshold and len(line) <= 40:
            removable.add(line)
    return removable


def should_drop_line(line: str, repeated_noise: set[str]) -> bool:
    if not line:
        return True
    if line in repeated_noise:
        return True
    if re.fullmatch(r"\d+", line):
        return True
    return False


def merge_page_lines(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    buffer = ""

    for raw in lines:
        line = raw.strip()
        if not line:
            if buffer:
                paragraphs.append(buffer.strip())
                buffer = ""
            continue

        bullet_like = line.startswith(("•", "-", "▣", "☞", "⇒", "💡", "💰", "🧑🏻"))
        heading_like = len(line) <= 30 and not line.endswith((".", "다", "요")) and " " in line

        if bullet_like or heading_like:
            if buffer:
                paragraphs.append(buffer.strip())
                buffer = ""
            paragraphs.append(line)
            continue

        if not buffer:
            buffer = line
            continue

        if re.search(r"[.!?]$|다$|요$|함$|됨$|임$|음$", buffer):
            paragraphs.append(buffer.strip())
            buffer = line
        else:
            buffer += " " + line

    if buffer:
        paragraphs.append(buffer.strip())
    return paragraphs


def is_heading_like(para: str) -> bool:
    return len(para) <= 36 and not para.endswith(("다", "요", ".", "함", "됨", "임", "음"))


def first_heading_label(paragraphs: list[str], fallback: str) -> str:
    """목차/네비게이션에 쓸 라벨을 고른다.

    물리적 PDF 페이지 번호("Page 12") 대신, 그 페이지 안에서 실제 장/절 제목처럼 보이는
    첫 줄(예: "40 - Leonid")을 찾아 라벨로 쓴다. 그런 줄이 없으면 기존처럼 페이지 번호를 쓴다.
    """
    for para in paragraphs:
        if not para.startswith(("•", "-", "▣", "☞", "⇒")) and is_heading_like(para):
            return para
    return fallback


def page_to_xhtml(page_num: int, paragraphs: list[str], *, language: str = "ko") -> str:
    body = []
    for para in paragraphs:
        escaped = html.escape(para)
        if para.startswith(("•", "-", "▣", "☞", "⇒")):
            body.append(f"<p class='bullet'>{escaped}</p>")
        elif len(para) <= 36 and not para.endswith(("다", "요", ".", "함", "됨", "임", "음")):
            body.append(f"<h2>{escaped}</h2>")
        else:
            body.append(f"<p>{escaped}</p>")

    content = "\n".join(body)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{html.escape(language)}">
  <head>
    <title>Page {page_num}</title>
    <meta charset="utf-8"/>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
  </head>
  <body>
    {content}
  </body>
</html>
"""


def page_image_xhtml(page_num: int, image_filename: str, title: str) -> str:
    escaped_title = html.escape(title)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="ko">
  <head>
    <title>{escaped_title} - {page_num}</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width,height=device-height"/>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
  </head>
  <body class="fixed-page">
    <div class="page-wrap">
      <img src="images/{image_filename}" alt="{escaped_title} {page_num}"/>
    </div>
  </body>
</html>
"""


def build_epub(
    pdf_path: Path,
    output_epub: Path,
    *,
    language: str = "ko",
    page_label: str = "페이지",
) -> None:
    pages = collect_pages(pdf_path)
    repeated_noise = repeated_noise_lines(pages)

    title = clean_pdf_title(pdf_path.stem)
    chapters: list[tuple[str, str, str]] = []
    for idx, raw_lines in enumerate(pages, start=1):
        filtered = [line for line in raw_lines if not should_drop_line(line, repeated_noise)]
        paragraphs = merge_page_lines(filtered)
        if not paragraphs:
            continue
        filename = f"page_{idx:03}.xhtml"
        label = first_heading_label(paragraphs, f"{page_label} {idx}")
        chapters.append((filename, label, page_to_xhtml(idx, paragraphs, language=language)))

    if not chapters:
        raise RuntimeError("EPUB으로 만들 텍스트를 추출하지 못했습니다.")

    styles = """
body { font-family: serif; line-height: 1.55; margin: 0 0.4em; }
h1, h2 { line-height: 1.25; margin: 1em 0 0.5em; }
h2 { font-size: 1.08em; }
p { margin: 0 0 0.7em; }
.bullet { margin-left: 0.4em; text-indent: -0.4em; }
"""

    nav_items = "\n".join(
        f"<li><a href=\"{filename}\">{html.escape(label)}</a></li>" for filename, label, _ in chapters
    )
    nav_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{html.escape(language)}">
  <head>
    <title>{html.escape(title)}</title>
    <meta charset="utf-8"/>
  </head>
  <body>
    <nav epub:type="toc" id="toc">
      <h1>{html.escape(title)}</h1>
      <ol>
        {nav_items}
      </ol>
    </nav>
  </body>
</html>
"""

    manifest_items = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="styles.css" media-type="text/css"/>',
    ]
    spine_items = []
    for idx, (filename, _, _) in enumerate(chapters, start=1):
        manifest_items.append(
            f'<item id="c{idx}" href="{filename}" media-type="application/xhtml+xml"/>'
        )
        spine_items.append(f'<itemref idref="c{idx}"/>')

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{html.escape(language)}">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{html.escape(title)}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:language>{html.escape(language)}</dc:language>
  </metadata>
  <manifest>
    {' '.join(manifest_items)}
  </manifest>
  <spine>
    {' '.join(spine_items)}
  </spine>
</package>
"""

    container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    output_epub.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_epub, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/nav.xhtml", nav_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/styles.css", styles, compress_type=zipfile.ZIP_DEFLATED)
        for filename, _, chapter in chapters:
            archive.writestr(f"OEBPS/{filename}", chapter, compress_type=zipfile.ZIP_DEFLATED)


def build_fixed_layout_epub(pdf_path: Path, output_epub: Path) -> None:
    title = clean_pdf_title(pdf_path.stem)
    chapters: list[tuple[str, str, str, bytes]] = []

    with fitz.open(pdf_path) as doc:
        for idx, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_name = f"page_{idx:03}.jpg"
            xhtml_name = f"page_{idx:03}.xhtml"
            label = f"페이지 {idx}"
            xhtml = page_image_xhtml(idx, image_name, title)
            chapters.append((xhtml_name, label, xhtml, pix.tobytes("jpeg", jpg_quality=88)))

    styles = """
html, body { margin: 0; padding: 0; }
body.fixed-page { margin: 0; padding: 0; background: #ffffff; }
.page-wrap { width: 100%; text-align: center; }
.page-wrap img { display: block; width: 100%; height: auto; margin: 0 auto; }
"""

    nav_items = "\n".join(
        f"<li><a href=\"{filename}\">{html.escape(label)}</a></li>" for filename, label, _, _ in chapters
    )
    nav_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ko">
  <head>
    <title>{html.escape(title)}</title>
    <meta charset="utf-8"/>
  </head>
  <body>
    <nav epub:type="toc" id="toc">
      <h1>{html.escape(title)}</h1>
      <ol>
        {nav_items}
      </ol>
    </nav>
  </body>
</html>
"""

    manifest_items = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="styles.css" media-type="text/css"/>',
    ]
    spine_items = []
    for idx, (xhtml_name, _, _, _) in enumerate(chapters, start=1):
        image_name = f"images/page_{idx:03}.jpg"
        manifest_items.append(
            f'<item id="c{idx}" href="{xhtml_name}" media-type="application/xhtml+xml"/>'
        )
        manifest_items.append(
            f'<item id="img{idx}" href="{image_name}" media-type="image/jpeg"/>'
        )
        spine_items.append(f'<itemref idref="c{idx}"/>')

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="ko">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{html.escape(title)}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:language>ko</dc:language>
  </metadata>
  <manifest>
    {' '.join(manifest_items)}
  </manifest>
  <spine>
    {' '.join(spine_items)}
  </spine>
</package>
"""

    container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    output_epub.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_epub, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/nav.xhtml", nav_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("OEBPS/styles.css", styles, compress_type=zipfile.ZIP_DEFLATED)
        for idx, (xhtml_name, _, xhtml, image_bytes) in enumerate(chapters, start=1):
            archive.writestr(f"OEBPS/{xhtml_name}", xhtml, compress_type=zipfile.ZIP_DEFLATED)
            archive.writestr(
                f"OEBPS/images/page_{idx:03}.jpg",
                image_bytes,
                compress_type=zipfile.ZIP_DEFLATED,
            )


def main() -> int:
    args = parse_args()
    input_pdf = args.input_pdf.expanduser().resolve()
    if not input_pdf.exists():
        raise SystemExit(f"입력 PDF를 찾지 못했습니다: {input_pdf}")
    output_epub = (
        args.output_epub.expanduser().resolve()
        if args.output_epub
        else input_pdf.with_name(f"[epub] {input_pdf.stem}.epub")
    )
    if args.mode == "fixed":
        build_fixed_layout_epub(input_pdf, output_epub)
    else:
        build_epub(input_pdf, output_epub)
    print(output_epub)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
