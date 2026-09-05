#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


A4_WIDTH = Inches(8.27)
A4_HEIGHT = Inches(11.69)
MARGIN_TOP_BOTTOM = Inches(0.62)
MARGIN_LEFT = Inches(0.72)
MARGIN_RIGHT = Inches(0.62)
HEADER_FOOTER_DISTANCE = Inches(0.3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DOCX를 A4 책자 인쇄용 레이아웃으로 최적화합니다."
    )
    parser.add_argument("input_docx", type=Path, help="입력 DOCX 파일")
    parser.add_argument("--output-docx", type=Path, help="출력 DOCX 파일. 기본값은 입력 파일 덮어쓰기")
    return parser.parse_args()


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_file(path: Path, suffix: str) -> Path:
    backup = path.with_name(f"{path.stem}_{suffix}_{timestamp()}{path.suffix}")
    backup.write_bytes(path.read_bytes())
    return backup


def set_style_font(doc: Document, style_name: str, *, size: float, bold: bool | None = None) -> None:
    if style_name not in doc.styles:
        return
    style = doc.styles[style_name]
    style.font.name = "Malgun Gothic"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold


def set_run_font(run, *, size: float | None = None, bold: bool | None = None) -> None:
    run.font.name = "Malgun Gothic"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def infer_cover(doc: Document, input_docx: Path) -> tuple[str, list[str]]:
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    title = None
    for line in lines[:20]:
        if "핵심 암기 마스터" in line or "마스터본" in line:
            if "핵심 암기 마스터" in line:
                title = line
                break
    if title is None:
        for line in lines[:20]:
            if "마스터본" in line:
                title = line
                break
    if title is None:
        for line in lines[:20]:
            if any(word in line for word in ("사회보험법", "사회보장법", "노동법", "민법", "경영학")):
                title = line
                break
    if title is None:
        title = input_docx.stem

    subtitle_candidates: list[str] = []
    for line in lines[:20]:
        if line == title:
            continue
        if any(keyword in line for keyword in ("공인노무사", "반복학습용", "인쇄용 북클릿", "현행 정정", "기출 보강", "숫자", "절차", "오답 함정")):
            subtitle_candidates.append(line)
    subtitles: list[str] = []
    seen = set()
    for line in subtitle_candidates:
        if line in seen:
            continue
        seen.add(line)
        subtitles.append(line)
        if len(subtitles) == 3:
            break
    return title, subtitles


def insert_paragraph_before(paragraph, text: str = "", style: str | None = None):
    new_p = OxmlElement("w:p")
    paragraph._p.addprevious(new_p)
    new_para = paragraph.__class__(new_p, paragraph._parent)
    if style:
        new_para.style = style
    if text:
        new_para.add_run(text)
    return new_para


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_char_begin = OxmlElement("w:fldChar")
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE "
    fld_char_separate = OxmlElement("w:fldChar")
    fld_char_separate.set(qn("w:fldCharType"), "separate")
    fld_char_end = OxmlElement("w:fldChar")
    fld_char_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char_begin)
    run._r.append(instr_text)
    run._r.append(fld_char_separate)
    run._r.append(fld_char_end)
    set_run_font(run, size=9)


def insert_cover_page(doc: Document, title: str, subtitles: list[str]) -> None:
    first_para = doc.paragraphs[0]
    section_break = insert_paragraph_before(first_para)
    title_para = insert_paragraph_before(section_break, title, style="Title")
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_para.paragraph_format.space_before = Pt(220)
    title_para.paragraph_format.space_after = Pt(20)
    for run in title_para.runs:
        set_run_font(run, size=22, bold=True)

    for idx, line in enumerate(subtitles):
        para = insert_paragraph_before(section_break, line)
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_after = Pt(8 if idx < len(subtitles) - 1 else 14)
        for run in para.runs:
            set_run_font(run, size=11.5, bold=False)

    edition_para = insert_paragraph_before(section_break, "A4 Booklet Print Edition")
    edition_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    edition_para.paragraph_format.space_after = Pt(0)
    for run in edition_para.runs:
        set_run_font(run, size=10, bold=False)

    section_break_run = section_break.add_run()
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    section_break_run._r.append(br)


def configure_document(doc: Document) -> None:
    for style_name, size, bold in [
        ("Normal", 10.2, False),
        ("Title", 22, True),
        ("Heading 1", 15, True),
        ("Heading 2", 12.5, True),
        ("Heading 3", 11.2, True),
    ]:
        set_style_font(doc, style_name, size=size, bold=bold)

    for section in doc.sections:
        section.page_width = A4_WIDTH
        section.page_height = A4_HEIGHT
        section.top_margin = MARGIN_TOP_BOTTOM
        section.bottom_margin = MARGIN_TOP_BOTTOM
        section.left_margin = MARGIN_LEFT
        section.right_margin = MARGIN_RIGHT
        section.header_distance = HEADER_FOOTER_DISTANCE
        section.footer_distance = HEADER_FOOTER_DISTANCE

    footer = doc.sections[0].footer
    if not footer.paragraphs:
        footer.add_paragraph()
    footer_para = footer.paragraphs[0]
    footer_para.clear()
    add_page_number(footer_para)


def classify_paragraph(text: str) -> str | None:
    if not text:
        return None
    if re.match(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\.", text):
        return "Heading 1"
    if text.startswith("※ "):
        return "Heading 3"
    if text.startswith("•"):
        return "bullet"
    if re.match(r"^\d+\.\s", text) and len(text) < 30:
        return "Heading 3"
    if len(text) <= 24 and not text.endswith(("다.", ".", "이다.", "합니다.")):
        return "Heading 2"
    return "Normal"


def format_body(doc: Document) -> None:
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style.name == "Title":
            pf = para.paragraph_format
            pf.space_before = Pt(220)
            pf.space_after = Pt(20)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in para.runs:
                set_run_font(run, size=22, bold=True)
            continue
        if text == "A4 Booklet Print Edition":
            pf = para.paragraph_format
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in para.runs:
                set_run_font(run, size=10, bold=False)
            continue
        classification = classify_paragraph(text)
        pf = para.paragraph_format

        if classification == "Heading 1":
            para.style = "Heading 1"
            pf.space_before = Pt(12)
            pf.space_after = Pt(5)
            pf.keep_with_next = True
        elif classification == "Heading 2":
            para.style = "Heading 2"
            pf.space_before = Pt(8)
            pf.space_after = Pt(3)
            pf.keep_with_next = True
        elif classification == "Heading 3":
            para.style = "Heading 3"
            pf.space_before = Pt(5)
            pf.space_after = Pt(2)
            pf.keep_with_next = True
        elif classification == "bullet":
            pf.left_indent = Inches(0.18)
            pf.first_line_indent = Inches(-0.12)
            pf.space_before = Pt(1)
            pf.space_after = Pt(1)
            pf.line_spacing = 1.12
        else:
            para.style = "Normal"
            pf.line_spacing = 1.15
            pf.space_before = Pt(0)
            pf.space_after = Pt(2)

        for run in para.runs:
            set_run_font(run, size=10.2 if classification != "Heading 1" else 15)

    for table in doc.tables:
        try:
            table.style = "Table Grid"
        except Exception:
            pass
        for row_idx, row in enumerate(table.rows):
            for cell in row.cells:
                for para in cell.paragraphs:
                    pf = para.paragraph_format
                    pf.line_spacing = 1.05
                    pf.space_before = Pt(0)
                    pf.space_after = Pt(0)
                    for run in para.runs:
                        set_run_font(run, size=9.4, bold=(row_idx == 0))


def optimize_docx_for_a4_booklet(input_docx: Path, output_docx: Path) -> Path:
    doc = Document(str(input_docx))
    configure_document(doc)
    title, subtitles = infer_cover(doc, input_docx)
    insert_cover_page(doc, title, subtitles)
    format_body(doc)
    doc.save(str(output_docx))
    return output_docx


def main() -> int:
    args = parse_args()
    input_docx = args.input_docx.expanduser().resolve()
    if not input_docx.exists():
        raise SystemExit(f"입력 DOCX를 찾지 못했습니다: {input_docx}")

    output_docx = (args.output_docx.expanduser().resolve() if args.output_docx else input_docx)
    backup = backup_file(input_docx, "backup_before_a4_booklet") if output_docx == input_docx else None
    optimize_docx_for_a4_booklet(input_docx, output_docx)
    print(f"input={input_docx}")
    print(f"output={output_docx}")
    print(f"backup={backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
