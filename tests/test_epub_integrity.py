from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import pytest
from defusedxml.common import DefusedXmlException


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from epub_integrity import validate_epub  # noqa: E402
import make_english_study_epubs as english_study  # noqa: E402
import make_korean_only_epubs as korean_only  # noqa: E402
from safe_xml import safe_fromstring  # noqa: E402
from translate_epub_with_chatgpt_web_to_study_epub import (  # noqa: E402
    SourceBlock,
    SourceSection,
    assess_section_split_quality,
    build_epub,
    extract_sections,
    is_translation_web_refusal_response,
    reorder_ko_en_pairs_in_epub,
    reorder_ko_en_pairs_to_en_ko,
    split_translation_and_note,
)


CONTAINER = """<?xml version="1.0" encoding="utf-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

PACKAGE = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">test-book</dc:identifier>
    <dc:title>Test Book</dc:title>
    <meta name="cover" content="cover-image"/>
  </metadata>
  <manifest>
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="cover-image" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>
  </manifest>
  <spine toc="ncx"><itemref idref="chapter"/></spine>
</package>"""

CHAPTER = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><h1 id="chapter-1">Chapter 1</h1></body></html>"""

NCX = """<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap><navPoint id="n1" playOrder="1">
  <navLabel><text>Chapter 1</text></navLabel><content src="chapter.xhtml#chapter-1"/>
</navPoint></navMap></ncx>"""


def write_epub(path: Path, *, nav_target: str = "chapter.xhtml#chapter-1", unsafe_member: bool = False) -> None:
    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><nav><ol>
  <li><a href="{nav_target}">Chapter 1</a></li>
</ol></nav></body></html>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", PACKAGE)
        archive.writestr("OEBPS/chapter.xhtml", CHAPTER)
        archive.writestr("OEBPS/nav.xhtml", nav)
        archive.writestr("OEBPS/toc.ncx", NCX)
        archive.writestr("OEBPS/cover.jpg", b"fake-image-data")
        if unsafe_member:
            archive.writestr("../escaped.txt", "unsafe")


def test_complete_epub_passes_strict_integrity_checks(tmp_path: Path) -> None:
    epub = tmp_path / "valid.epub"
    write_epub(epub)

    report = validate_epub(epub, require_nav=True, require_ncx=True, require_cover=True)

    assert report.valid is True
    assert report.nav_links == 1
    assert report.ncx_links == 1
    assert report.cover_images == 1


def test_broken_navigation_fragment_is_rejected(tmp_path: Path) -> None:
    epub = tmp_path / "broken-nav.epub"
    write_epub(epub, nav_target="chapter.xhtml#missing")

    report = validate_epub(epub, require_nav=True, require_ncx=True, require_cover=True)

    assert report.valid is False
    assert any("missing fragment #missing" in issue for issue in report.issues)


def test_navigation_document_without_links_is_rejected(tmp_path: Path) -> None:
    epub = tmp_path / "empty-nav.epub"
    write_epub(epub, nav_target="")

    report = validate_epub(epub, require_nav=True, require_ncx=True, require_cover=True)

    assert report.valid is False
    assert "EPUB navigation document contains no links" in report.issues


def test_unsafe_zip_member_is_rejected_before_extraction(tmp_path: Path) -> None:
    epub = tmp_path / "unsafe.epub"
    write_epub(epub, unsafe_member=True)

    report = validate_epub(epub)

    assert report.valid is False
    assert any("unsafe member path" in issue for issue in report.issues)


def test_xml_entities_are_forbidden() -> None:
    payload = b'<!DOCTYPE root [<!ENTITY secret "expanded">]><root>&secret;</root>'

    with pytest.raises(DefusedXmlException):
        safe_fromstring(payload)


def test_legacy_ncx_external_dtd_declaration_is_accepted_without_loading_it() -> None:
    payload = b'''<?xml version="1.0"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"/>'''

    root = safe_fromstring(payload)

    assert root.tag.endswith("ncx")


def test_korean_only_conversion_keeps_navigation_and_cover_valid(tmp_path: Path) -> None:
    source = tmp_path / "[k-e] source.epub"
    output = tmp_path / "[k] source.epub"
    write_epub(source)

    korean_only.convert_epub(source, output, overwrite=True)
    report = validate_epub(output, require_nav=True, require_ncx=True, require_cover=True)

    assert report.valid is True


def test_study_epub_builder_publishes_a_strictly_valid_archive(tmp_path: Path) -> None:
    source = tmp_path / "source.epub"
    output = tmp_path / "study.epub"
    write_epub(source)
    section = SourceSection(
        title="Chapter 1",
        filename="chapter-01.xhtml",
        blocks=[SourceBlock(id="B00001", text="The first sentence is translated.")],
    )

    build_epub(
        output_epub=output,
        book_title="Test Book",
        ko_book_title="Test Book",
        creator="Test Author",
        sections=[section],
        translations={"B00001": "첫 문장을 번역했다."},
        input_epub=source,
    )

    report = validate_epub(output, require_nav=True, require_ncx=True, require_cover=True)
    assert report.valid is True


def test_extract_sections_uses_epub3_nav_labels_when_no_ncx_is_present(tmp_path: Path) -> None:
    # Some EPUB3 books (e.g. transcript/talk collections built without a legacy toc.ncx)
    # only have a <nav epub:type="toc"> document. Without an ncx to fall back to,
    # extract_sections() previously used the bare chapter filename as the section
    # title - real chapter/talk titles from the book's own table of contents were lost.
    epub_path = tmp_path / "epub3_only.epub"
    package = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">test-book</dc:identifier>
    <dc:title>Test Talks</dc:title>
  </metadata>
  <manifest>
    <item id="chapter-001" href="chapter-001.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter-002" href="chapter-002.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
  <spine>
    <itemref idref="chapter-001"/>
    <itemref idref="chapter-002"/>
  </spine>
</package>"""
    nav = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<body><nav epub:type="toc" id="toc"><ol>
  <li><a href="chapter-001.xhtml">Do schools kill creativity?</a></li>
  <li><a href="chapter-002.xhtml">The puzzle of motivation</a></li>
</ol></nav></body></html>"""
    chapter1 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Good morning. How are you?</p></body></html>"""
    chapter2 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Let's talk about motivation.</p></body></html>"""
    with zipfile.ZipFile(epub_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", package)
        archive.writestr("OEBPS/nav.xhtml", nav)
        archive.writestr("OEBPS/chapter-001.xhtml", chapter1)
        archive.writestr("OEBPS/chapter-002.xhtml", chapter2)

    _title, _creator, sections = extract_sections(epub_path)

    assert [section.title for section in sections] == [
        "Do schools kill creativity?",
        "The puzzle of motivation",
    ]


def test_extract_sections_recovers_internal_headings_from_generic_start_ncx(tmp_path: Path) -> None:
    # A valid but useless NCX with only Start must not become synthetic Chapter N
    # sections when the reading documents contain meaningful semantic headings.
    epub_path = tmp_path / "generic_start.epub"
    package = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Generic Start</dc:title></metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch3" href="ch3.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx"><itemref idref="ch1"/><itemref idref="ch2"/><itemref idref="ch3"/></spine>
</package>"""
    ncx = """<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>
  <navPoint id="start" playOrder="1"><navLabel><text>Start</text></navLabel><content src="ch1.xhtml"/></navPoint>
</navMap></ncx>"""
    with zipfile.ZipFile(epub_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", package)
        archive.writestr("OEBPS/toc.ncx", ncx)
        for number, heading in enumerate(("SPRING", "SUMMER", "FALL"), start=1):
            archive.writestr(
                f"OEBPS/ch{number}.xhtml",
                f'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">'
                f"<body><h2 id=\"heading-{number}\">{heading}</h2>"
                f"<p>Substantial prose for {heading.lower()}.</p></body></html>",
            )

    _title, _creator, sections = extract_sections(epub_path)

    assert [section.title for section in sections] == ["SPRING", "SUMMER", "FALL"]
    assert [section.filename for section in sections] == [
        "001-spring.xhtml",
        "002-summer.xhtml",
        "003-fall.xhtml",
    ]


def test_extract_sections_recovers_chapters_from_inbody_contents_page_when_official_nav_is_broken(
    tmp_path: Path,
) -> None:
    # Found live in a Leigh Rivers book (a scraped/pirated source): the official nav had only
    # 1-2 garbage entries, so the whole book collapsed into one oversized, mislabeled section
    # while every real chapterNN.xhtml came out empty. The book still had a genuine in-body
    # "Contents" page - a plain <a href="...">Chapter N</a> link list - that extract_sections()
    # now uses to recover the real per-chapter split.
    epub_path = tmp_path / "broken_nav.epub"
    chapter_items = "\n".join(f'    <item id="ch{n}" href="ch{n}.xhtml" media-type="application/xhtml+xml"/>' for n in range(1, 7))
    chapter_refs = "\n".join(f'    <itemref idref="ch{n}"/>' for n in range(1, 7))
    package = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">test-book</dc:identifier>
    <dc:title>Test Book</dc:title>
  </metadata>
  <manifest>
    <item id="contents" href="contents.xhtml" media-type="application/xhtml+xml"/>
{chapter_items}
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
  <spine>
    <itemref idref="contents"/>
{chapter_refs}
  </spine>
</package>"""
    # Only one entry, pointing at the contents page itself - everything else would fall into
    # a single unbroken gap without the in-body recovery.
    nav = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<body><nav epub:type="toc" id="toc"><ol>
  <li><a href="contents.xhtml">Foreword</a></li>
</ol></nav></body></html>"""
    contents_page = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><ol>
  <li><a href="ch1.xhtml">Chapter 1</a></li>
  <li><a href="ch2.xhtml">Chapter 2</a></li>
  <li><a href="ch3.xhtml">Chapter 3</a></li>
  <li><a href="ch4.xhtml">Chapter 4</a></li>
  <li><a href="ch5.xhtml">Chapter 5</a></li>
  <li><a href="ch6.xhtml">Chapter 6</a></li>
</ol></body></html>"""
    with zipfile.ZipFile(epub_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", package)
        archive.writestr("OEBPS/nav.xhtml", nav)
        archive.writestr("OEBPS/contents.xhtml", contents_page)
        for n in range(1, 7):
            archive.writestr(
                f"OEBPS/ch{n}.xhtml",
                f'<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml">'
                f"<body><p>This is the real content of chapter {n}. " + ("Padding to stay above the short-stub rejection threshold. " * 5) + "</p></body></html>",
            )

    _title, _creator, sections = extract_sections(epub_path)

    chapter_sections = [section for section in sections if section.title.startswith("Chapter ")]
    assert len(chapter_sections) == 6
    for n, section in enumerate(chapter_sections, start=1):
        text = " ".join(block.text for block in section.blocks)
        assert f"real content of chapter {n}" in text


def test_extract_sections_splits_oversized_nav_gap_when_official_nav_is_too_sparse(
    tmp_path: Path,
) -> None:
    # Found live in an "Insatiable" EPUB: the official nav had only 2 entries for 51 real
    # per-chapter spine files (and, unlike the case above, no in-body Contents page to recover
    # from either). extract_sections() now detects a nav gap that swallows most of the spine
    # and splits it one section per spine file instead of leaving it as a single blob.
    epub_path = tmp_path / "sparse_nav.epub"
    chapter_items = "\n".join(f'    <item id="ch{n}" href="ch{n}.xhtml" media-type="application/xhtml+xml"/>' for n in range(1, 11))
    chapter_refs = "\n".join(f'    <itemref idref="ch{n}"/>' for n in range(1, 11))
    package = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">test-book</dc:identifier>
    <dc:title>Test Book</dc:title>
  </metadata>
  <manifest>
    <item id="intro" href="intro.xhtml" media-type="application/xhtml+xml"/>
{chapter_items}
    <item id="afterword" href="afterword.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
  <spine>
    <itemref idref="intro"/>
{chapter_refs}
    <itemref idref="afterword"/>
  </spine>
</package>"""
    nav = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<body><nav epub:type="toc" id="toc"><ol>
  <li><a href="intro.xhtml">Intro</a></li>
  <li><a href="afterword.xhtml">Afterword</a></li>
</ol></nav></body></html>"""
    with zipfile.ZipFile(epub_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", package)
        archive.writestr("OEBPS/nav.xhtml", nav)
        archive.writestr(
            "OEBPS/intro.xhtml",
            '<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml">'
            "<body><p>Intro text.</p></body></html>",
        )
        archive.writestr(
            "OEBPS/afterword.xhtml",
            '<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml">'
            "<body><p>Afterword text.</p></body></html>",
        )
        for n in range(1, 11):
            archive.writestr(
                f"OEBPS/ch{n}.xhtml",
                f'<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml">'
                f"<body><p>This is the real content of chapter {n}. " + ("Padding to stay above the short-stub rejection threshold. " * 5) + "</p></body></html>",
            )

    _title, _creator, sections = extract_sections(epub_path)

    sizes = [sum(len(block.text) for block in section.blocks) for section in sections]
    assert max(sizes) / sum(sizes) < 0.2
    real_chapter_texts = {
        " ".join(block.text for block in section.blocks) for section in sections
    }
    for n in range(1, 11):
        assert any(f"real content of chapter {n}." in text for text in real_chapter_texts)


def test_assess_section_split_quality_flags_one_dominant_section_with_empty_siblings() -> None:
    sections = [
        SourceSection(title=f"Chapter {n}", filename=f"chapter{n:02d}.xhtml", blocks=[SourceBlock(id="B1", text=f"{n}")])
        for n in range(1, 6)
    ]
    sections.append(
        SourceSection(
            title="PROLOGUE",
            filename="prologue.xhtml",
            blocks=[SourceBlock(id="B6", text="x" * 5000)],
        )
    )

    result = assess_section_split_quality(sections, "Some Book")

    assert result["status"] == "needs_attention"
    assert result["near_empty_sections"] == 5
    assert result["largest_section_fraction"] > 0.6


def test_is_translation_web_refusal_response_catches_korean_copyright_refusal() -> None:
    # Found live in raw Gemini response logs (see COPYRIGHT_REFUSAL_RE's docstring) - without
    # this, the response was accepted as a "translation" instead of triggering the retry with
    # refusal_retry_prompt (which already explains this is a legitimate personal-use request).
    response = (
        "저작권이 있는 출판 도서의 본문을 직접 전량 번역하거나 행 단위로 대조하여 제공해 드리기는 어렵습니다."
    )

    assert is_translation_web_refusal_response(response, argparse.Namespace()) is True


def test_is_translation_web_refusal_response_accepts_real_translation_mentioning_copyright() -> None:
    response = "<<<B00001>>>이 전자책은 저작권이 있는 자료이며 무단 복제를 금합니다.<<<END_B00001>>>"

    assert is_translation_web_refusal_response(response, argparse.Namespace()) is False


def test_assess_section_split_quality_leaves_a_balanced_split_alone() -> None:
    sections = [
        SourceSection(title=f"Chapter {n}", filename=f"chapter{n:02d}.xhtml", blocks=[SourceBlock(id="B1", text="x" * 2000)])
        for n in range(1, 11)
    ]

    result = assess_section_split_quality(sections, "Some Book")

    assert result["status"] == "ok"


def test_split_translation_and_note_separates_marker_from_translation() -> None:
    translation, note = split_translation_and_note(
        "그는 어색한 분위기를 풀려고 애썼다. ※학습: break the ice - 서먹함을 깨다"
    )

    assert translation == "그는 어색한 분위기를 풀려고 애썼다."
    assert note == "break the ice - 서먹함을 깨다"


def test_split_translation_and_note_returns_empty_note_when_marker_absent() -> None:
    translation, note = split_translation_and_note("그는 어색한 분위기를 풀려고 애썼다.")

    assert translation == "그는 어색한 분위기를 풀려고 애썼다."
    assert note == ""


def test_plain_k_e_build_omits_study_notes_by_default(tmp_path: Path) -> None:
    # [k-e] is the plain bilingual reference edition - study notes belong only in the
    # separate [study] variant (include_study_notes=True), not in the default build.
    source = tmp_path / "source.epub"
    bilingual = tmp_path / "[k-e] study.epub"
    write_epub(source)
    section = SourceSection(
        title="Chapter 1",
        filename="chapter-01.xhtml",
        blocks=[SourceBlock(id="B00001", text="He tried to break the ice with a joke.")],
    )

    build_epub(
        output_epub=bilingual,
        book_title="Test Book",
        ko_book_title="Test Book",
        creator="Test Author",
        sections=[section],
        translations={
            "B00001": "그는 농담으로 어색한 분위기를 풀려고 했다. ※학습: break the ice - 서먹함을 깨다",
        },
        input_epub=source,
    )

    with zipfile.ZipFile(bilingual) as archive:
        chapter_xhtml = archive.read("OEBPS/chapter-01.xhtml").decode("utf-8")

    assert "study-note" not in chapter_xhtml
    assert "서먹함을 깨다" not in chapter_xhtml
    ko_start = chapter_xhtml.index('<span class="ko"')
    ko_end = chapter_xhtml.index("</span>", ko_start)
    assert "그는 농담으로 어색한 분위기를 풀려고 했다." in chapter_xhtml[ko_start:ko_end]


def test_study_epub_builder_renders_study_note_in_its_own_span_and_korean_only_strips_it(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.epub"
    study = tmp_path / "[study] study.epub"
    korean = tmp_path / "[k] study.epub"
    write_epub(source)
    section = SourceSection(
        title="Chapter 1",
        filename="chapter-01.xhtml",
        blocks=[SourceBlock(id="B00001", text="He tried to break the ice with a joke.")],
    )

    build_epub(
        output_epub=study,
        book_title="Test Book",
        ko_book_title="Test Book",
        creator="Test Author",
        sections=[section],
        translations={
            "B00001": "그는 농담으로 어색한 분위기를 풀려고 했다. ※학습: break the ice - 서먹함을 깨다",
        },
        input_epub=source,
        include_study_notes=True,
    )

    with zipfile.ZipFile(study) as archive:
        chapter_xhtml = archive.read("OEBPS/chapter-01.xhtml").decode("utf-8")

    assert '<span class="study-note"' in chapter_xhtml
    assert "break the ice - 서먹함을 깨다" in chapter_xhtml
    ko_start = chapter_xhtml.index('<span class="ko"')
    ko_end = chapter_xhtml.index("</span>", ko_start)
    assert "break the ice" not in chapter_xhtml[ko_start:ko_end]
    assert "그는 농담으로 어색한 분위기를 풀려고 했다." in chapter_xhtml[ko_start:ko_end]

    korean_only.convert_epub(study, korean, overwrite=True)
    with zipfile.ZipFile(korean) as archive:
        korean_chapter = archive.read("OEBPS/chapter-01.xhtml").decode("utf-8")

    assert "study-note" not in korean_chapter
    assert "break the ice" not in korean_chapter
    assert "그는 농담으로 어색한 분위기를 풀려고 했다." in korean_chapter


def test_english_study_conversion_keeps_navigation_and_cover_valid(tmp_path: Path) -> None:
    source = tmp_path / "source.epub"
    study = tmp_path / "[study] source.epub"
    output = tmp_path / "[e-s] source.epub"
    write_epub(source)
    section = SourceSection(
        title="Chapter 1",
        filename="chapter-01.xhtml",
        blocks=[SourceBlock(id="B00001", text="He tried to break the ice with a joke.")],
    )

    build_epub(
        output_epub=study,
        book_title="Test Book",
        ko_book_title="Test Book",
        creator="Test Author",
        sections=[section],
        translations={
            "B00001": "그는 농담으로 어색한 분위기를 풀려고 했다. ※학습: break the ice - 서먹함을 깨다",
        },
        input_epub=source,
        include_study_notes=True,
    )

    english_study.convert_epub(study, output, overwrite=True)
    report = validate_epub(output, require_nav=True, require_ncx=True, require_cover=True)

    assert report.valid is True


def test_english_study_conversion_keeps_english_and_note_but_drops_korean(tmp_path: Path) -> None:
    source = tmp_path / "source.epub"
    study = tmp_path / "[study] source.epub"
    output = tmp_path / "[e-s] source.epub"
    write_epub(source)
    section = SourceSection(
        title="Chapter 1",
        filename="chapter-01.xhtml",
        blocks=[SourceBlock(id="B00001", text="He tried to break the ice with a joke.")],
    )

    build_epub(
        output_epub=study,
        book_title="Test Book",
        ko_book_title="Test Book",
        creator="Test Author",
        sections=[section],
        translations={
            "B00001": "그는 농담으로 어색한 분위기를 풀려고 했다. ※학습: break the ice - 서먹함을 깨다",
        },
        input_epub=source,
        include_study_notes=True,
    )

    english_study.convert_epub(study, output, overwrite=True)
    with zipfile.ZipFile(output) as archive:
        chapter_xhtml = archive.read("OEBPS/chapter-01.xhtml").decode("utf-8")
        opf_text = archive.read("OEBPS/content.opf").decode("utf-8")

    assert "He tried to break the ice with a joke." in chapter_xhtml
    assert 'class="study-note"' in chapter_xhtml
    assert "break the ice - 서먹함을 깨다" in chapter_xhtml
    assert 'class="ko"' not in chapter_xhtml
    assert "그는 농담으로 어색한 분위기를 풀려고 했다" not in chapter_xhtml
    assert "<dc:language>en</dc:language>" in opf_text


def test_english_study_output_name_maps_study_prefix_to_e_s() -> None:
    assert english_study.output_name("[study] Some Book.epub") == "[e-s] Some Book.epub"
    assert english_study.output_name("[study]Some Book.epub") == "[e-s]Some Book.epub"
    assert english_study.output_name("Some Book.epub") == "[e-s] Some Book.epub"


def test_english_study_conversion_preserves_previous_output_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.epub"
    study = tmp_path / "[study] source.epub"
    output = tmp_path / "[e-s] source.epub"
    write_epub(source)
    section = SourceSection(
        title="Chapter 1",
        filename="chapter-01.xhtml",
        blocks=[SourceBlock(id="B00001", text="He tried to break the ice with a joke.")],
    )
    build_epub(
        output_epub=study,
        book_title="Test Book",
        ko_book_title="Test Book",
        creator="Test Author",
        sections=[section],
        translations={"B00001": "그는 어색한 분위기를 풀려고 했다."},
        input_epub=source,
        include_study_notes=True,
    )
    output.write_bytes(b"previous-good-output")

    def fail_conversion(_data: bytes) -> tuple[bytes, dict[str, int]]:
        raise RuntimeError("injected conversion failure")

    monkeypatch.setattr(english_study, "convert_xhtml", fail_conversion)

    with pytest.raises(RuntimeError, match="injected conversion failure"):
        english_study.convert_epub(study, output, overwrite=True)

    assert output.read_bytes() == b"previous-good-output"


def test_study_epub_orders_english_then_korean_then_study_note(tmp_path: Path) -> None:
    # 2026-08-07: user asked for [study] to read English -> Korean -> study note,
    # instead of the [k-e]-style Korean -> (note) -> English order.
    source = tmp_path / "source.epub"
    study = tmp_path / "[study] study.epub"
    write_epub(source)
    section = SourceSection(
        title="Chapter 1",
        filename="chapter-01.xhtml",
        blocks=[SourceBlock(id="B00001", text="He tried to break the ice with a joke.")],
    )

    build_epub(
        output_epub=study,
        book_title="Test Book",
        ko_book_title="Test Book",
        creator="Test Author",
        sections=[section],
        translations={
            "B00001": "그는 농담으로 어색한 분위기를 풀려고 했다. ※학습: break the ice - 서먹함을 깨다",
        },
        input_epub=source,
        include_study_notes=True,
    )

    with zipfile.ZipFile(study) as archive:
        chapter_xhtml = archive.read("OEBPS/chapter-01.xhtml").decode("utf-8")

    en_pos = chapter_xhtml.index('<span class="en"')
    ko_pos = chapter_xhtml.index('<span class="ko"')
    note_pos = chapter_xhtml.index('<span class="study-note"')
    assert en_pos < ko_pos < note_pos


def test_plain_k_e_build_also_orders_english_then_korean(tmp_path: Path) -> None:
    # 2026-08-08: [k-e] (the plain bilingual edition) was switched to the same
    # English-then-Korean order as [study], instead of its old Korean-then-English order.
    source = tmp_path / "source.epub"
    bilingual = tmp_path / "[k-e] study.epub"
    write_epub(source)
    section = SourceSection(
        title="Chapter 1",
        filename="chapter-01.xhtml",
        blocks=[SourceBlock(id="B00001", text="He tried to break the ice with a joke.")],
    )

    build_epub(
        output_epub=bilingual,
        book_title="Test Book",
        ko_book_title="Test Book",
        creator="Test Author",
        sections=[section],
        translations={
            "B00001": "그는 농담으로 어색한 분위기를 풀려고 했다. ※학습: break the ice - 서먹함을 깨다",
        },
        input_epub=source,
    )

    with zipfile.ZipFile(bilingual) as archive:
        chapter_xhtml = archive.read("OEBPS/chapter-01.xhtml").decode("utf-8")

    en_pos = chapter_xhtml.index('<span class="en"')
    ko_pos = chapter_xhtml.index('<span class="ko"')
    assert en_pos < ko_pos


def test_korean_only_conversion_preserves_previous_output_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "[k-e] source.epub"
    output = tmp_path / "[k] source.epub"
    write_epub(source)
    output.write_bytes(b"previous-good-output")

    def fail_conversion(_data: bytes, _remove_inline: bool) -> tuple[bytes, dict[str, int]]:
        raise RuntimeError("injected conversion failure")

    monkeypatch.setattr(korean_only, "convert_xhtml", fail_conversion)

    with pytest.raises(RuntimeError, match="injected conversion failure"):
        korean_only.convert_epub(source, output, overwrite=True)

    assert output.read_bytes() == b"previous-good-output"


def test_reorder_ko_en_pairs_to_en_ko_swaps_pair_span_order() -> None:
    old_html = (
        '<p class="pair"><span class="ko" xml:lang="ko">그는 문을 열었다.</span><br />'
        '<span class="en" xml:lang="en">He opened the door.</span></p>'
    )

    new_html, changed = reorder_ko_en_pairs_to_en_ko(old_html)

    assert changed == 1
    assert new_html == (
        '<p class="pair"><span class="en" xml:lang="en">He opened the door.</span><br />'
        '<span class="ko" xml:lang="ko">그는 문을 열었다.</span></p>'
    )


def test_reorder_ko_en_pairs_to_en_ko_preserves_study_note_at_the_end() -> None:
    old_html = (
        '<p class="pair"><span class="ko" xml:lang="ko">그는 어색한 분위기를 풀려고 했다.</span><br />'
        '<span class="en" xml:lang="en">He tried to break the ice.</span>'
        '<br /><span class="study-note" xml:lang="ko">※ break the ice - 서먹함을 깨다</span></p>'
    )

    new_html, changed = reorder_ko_en_pairs_to_en_ko(old_html)

    assert changed == 1
    en_pos = new_html.index('<span class="en"')
    ko_pos = new_html.index('<span class="ko"')
    note_pos = new_html.index('<span class="study-note"')
    assert en_pos < ko_pos < note_pos
    assert "break the ice - 서먹함을 깨다" in new_html


def test_reorder_ko_en_pairs_to_en_ko_swaps_heading_order() -> None:
    old_html = '<h2><span class="ko" xml:lang="ko">API</span> <span class="en" xml:lang="en">(API)</span></h2>'

    new_html, changed = reorder_ko_en_pairs_to_en_ko(old_html)

    assert changed == 1
    assert new_html == '<h2><span class="en" xml:lang="en">(API)</span> <span class="ko" xml:lang="ko">API</span></h2>'


def test_reorder_ko_en_pairs_to_en_ko_is_a_no_op_when_already_new_order() -> None:
    already_new = (
        '<p class="pair"><span class="en" xml:lang="en">He opened the door.</span><br />'
        '<span class="ko" xml:lang="ko">그는 문을 열었다.</span></p>'
    )

    new_html, changed = reorder_ko_en_pairs_to_en_ko(already_new)

    assert changed == 0
    assert new_html == already_new


def test_reorder_ko_en_pairs_in_epub_fixes_legacy_file_without_retranslating(tmp_path: Path) -> None:
    # Simulates a book built before 2026-08-08 (Korean-then-English order) whose
    # translation cache no longer exists on disk - reordering must work purely from the
    # already-built EPUB's own HTML, with no source EPUB or cache involved at all.
    legacy_chapter = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1 id="chapter-1">Chapter 1</h1>
<p class="pair"><span class="ko" xml:lang="ko">그는 문을 열었다.</span><br />
<span class="en" xml:lang="en">He opened the door.</span></p>
</body></html>"""
    epub = tmp_path / "[k-e] legacy.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", PACKAGE)
        archive.writestr("OEBPS/chapter.xhtml", legacy_chapter)
        archive.writestr(
            "OEBPS/nav.xhtml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml"><body><nav><ol>'
            '<li><a href="chapter.xhtml#chapter-1">Chapter 1</a></li>'
            "</ol></nav></body></html>",
        )
        archive.writestr("OEBPS/toc.ncx", NCX)
        archive.writestr("OEBPS/cover.jpg", b"fake-image-data")

    changed = reorder_ko_en_pairs_in_epub(epub)

    assert changed == 1
    with zipfile.ZipFile(epub) as archive:
        chapter_xhtml = archive.read("OEBPS/chapter.xhtml").decode("utf-8")
    en_pos = chapter_xhtml.index('<span class="en"')
    ko_pos = chapter_xhtml.index('<span class="ko"')
    assert en_pos < ko_pos
    assert "He opened the door." in chapter_xhtml
    assert "그는 문을 열었다." in chapter_xhtml

    report = validate_epub(epub, require_nav=True, require_ncx=True, require_cover=True)
    assert report.valid is True


def test_reorder_ko_en_pairs_in_epub_returns_zero_for_already_reordered_file(tmp_path: Path) -> None:
    epub = tmp_path / "[k-e] already-new.epub"
    write_epub(epub)  # CHAPTER fixture has no ko/en pair at all

    changed = reorder_ko_en_pairs_in_epub(epub)

    assert changed == 0
