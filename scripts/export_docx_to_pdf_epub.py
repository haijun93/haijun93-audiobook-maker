#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import fitz


CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
IBOOKS_NS = "http://vocabulary.itunes.apple.com/rdf/ibooks/vocabulary-extensions-1.0/"

ET.register_namespace("", OPF_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("ibooks", IBOOKS_NS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="macOS Pages로 DOCX를 PDF/EPUB로 내보내고 EPUB 표지를 첫 페이지 내용으로 고정합니다."
    )
    parser.add_argument("input_docx", type=Path, help="입력 DOCX 파일")
    parser.add_argument("--output-pdf", type=Path, help="출력 PDF 경로")
    parser.add_argument("--output-epub", type=Path, help="출력 EPUB 경로")
    parser.add_argument(
        "--cover-dpi",
        type=int,
        default=144,
        help="EPUB 표지로 쓸 첫 페이지 렌더 해상도(dpi, 기본: 144)",
    )
    return parser.parse_args()


def resolve_output_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    input_docx = args.input_docx.expanduser().resolve()
    pdf_path = args.output_pdf.expanduser().resolve() if args.output_pdf else input_docx.with_suffix(".pdf")
    epub_path = (
        args.output_epub.expanduser().resolve() if args.output_epub else input_docx.with_suffix(".epub")
    )
    return pdf_path, epub_path


def export_docx_with_pages(input_docx: Path, pdf_path: Path, epub_path: Path) -> None:
    applescript = f"""
set inputPath to POSIX file "{input_docx.as_posix()}"
set pdfPath to POSIX file "{pdf_path.as_posix()}"
set epubPath to POSIX file "{epub_path.as_posix()}"

tell application "Pages"
\tactivate
\tset docRef to open inputPath
\tdelay 3
\texport docRef to pdfPath as PDF
\texport docRef to epubPath as EPUB
\tclose docRef saving no
end tell
"""
    subprocess.run(["osascript", "-e", applescript], check=True)


def render_pdf_first_page_to_png_bytes(pdf_path: Path, *, dpi: int) -> bytes:
    with fitz.open(pdf_path) as pdf:
        if pdf.page_count < 1:
            raise RuntimeError(f"PDF에 페이지가 없습니다: {pdf_path}")
        scale = dpi / 72.0
        page = pdf.load_page(0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png")


def resolve_epub_package_path(epub_path: Path, archive: zipfile.ZipFile) -> str:
    container_text = archive.read("META-INF/container.xml")
    container_root = ET.fromstring(container_text)
    rootfile = container_root.find(f".//{{{CONTAINER_NS}}}rootfile")
    if rootfile is None:
        raise RuntimeError(f"EPUB package document를 찾지 못했습니다: {epub_path}")
    package_path = (rootfile.attrib.get("full-path") or "").strip()
    if not package_path:
        raise RuntimeError(f"EPUB package document 경로가 비어 있습니다: {epub_path}")
    return package_path


def ensure_epub_cover_from_png(epub_path: Path, cover_png_bytes: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir)
        with zipfile.ZipFile(epub_path) as archive:
            archive.extractall(temp_root)
            package_path = resolve_epub_package_path(epub_path, archive)

        opf_path = temp_root / package_path
        opf_tree = ET.parse(opf_path)
        package = opf_tree.getroot()

        manifest = package.find(f"{{{OPF_NS}}}manifest")
        metadata = package.find(f"{{{OPF_NS}}}metadata")
        if manifest is None or metadata is None:
            raise RuntimeError(f"EPUB OPF 구조가 올바르지 않습니다: {epub_path}")

        cover_rel_path = Path("images") / "cover.png"
        cover_abs_path = opf_path.parent / cover_rel_path
        cover_abs_path.parent.mkdir(parents=True, exist_ok=True)
        cover_abs_path.write_bytes(cover_png_bytes)

        for item in list(manifest):
            item_id = item.attrib.get("id", "")
            properties = item.attrib.get("properties", "")
            href = item.attrib.get("href", "")
            if item_id == "cover-image" or "cover-image" in properties.split() or href == cover_rel_path.as_posix():
                manifest.remove(item)

        ET.SubElement(
            manifest,
            f"{{{OPF_NS}}}item",
            {
                "id": "cover-image",
                "href": cover_rel_path.as_posix(),
                "media-type": "image/png",
                "properties": "cover-image",
            },
        )

        for meta in list(metadata):
            if meta.tag != f"{{{OPF_NS}}}meta":
                continue
            if meta.attrib.get("name") == "cover":
                metadata.remove(meta)

        ET.SubElement(
            metadata,
            f"{{{OPF_NS}}}meta",
            {
                "name": "cover",
                "content": "cover-image",
            },
        )

        opf_tree.write(opf_path, encoding="utf-8", xml_declaration=True)
        rewrite_epub_archive(temp_root, epub_path)


def rewrite_epub_archive(extracted_root: Path, epub_path: Path) -> None:
    with zipfile.ZipFile(epub_path, "w") as archive:
        mimetype_path = extracted_root / "mimetype"
        if mimetype_path.exists():
            archive.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
        for path in sorted(extracted_root.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(extracted_root).as_posix()
            if rel_path == "mimetype":
                continue
            archive.write(path, rel_path, compress_type=zipfile.ZIP_DEFLATED)


def main() -> int:
    args = parse_args()
    input_docx = args.input_docx.expanduser().resolve()
    if not input_docx.exists():
        raise SystemExit(f"입력 DOCX를 찾지 못했습니다: {input_docx}")

    output_pdf, output_epub = resolve_output_paths(args)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_epub.parent.mkdir(parents=True, exist_ok=True)

    export_docx_with_pages(input_docx, output_pdf, output_epub)
    cover_png_bytes = render_pdf_first_page_to_png_bytes(output_pdf, dpi=args.cover_dpi)
    ensure_epub_cover_from_png(output_epub, cover_png_bytes)

    print(f"PDF: {output_pdf}")
    print(f"EPUB: {output_epub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
