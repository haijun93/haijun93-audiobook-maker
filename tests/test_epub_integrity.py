from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest
from defusedxml.common import DefusedXmlException


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from epub_integrity import validate_epub  # noqa: E402
import make_korean_only_epubs as korean_only  # noqa: E402
from safe_xml import safe_fromstring  # noqa: E402
from translate_epub_with_chatgpt_web_to_study_epub import (  # noqa: E402
    SourceBlock,
    SourceSection,
    build_epub,
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
