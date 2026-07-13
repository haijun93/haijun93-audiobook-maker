from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.remove_readrobe_text_from_epubs import WATERMARK_PATTERN, scrub_epub, scrub_text


def test_scrub_text_removes_english_and_korean_watermark_variants() -> None:
    source = "readrobe.com / www.readrobe . com / 리드로브닷컴 / 리드 로브 닷 컴 / 출처리드로브.com에서"

    cleaned, count = scrub_text(source)

    assert count == 5
    assert not WATERMARK_PATTERN.search(cleaned)


def test_scrub_epub_removes_watermarks_and_preserves_valid_archive(tmp_path: Path) -> None:
    epub = tmp_path / "sample.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "OEBPS/chapter.xhtml",
            '<?xml version="1.0" encoding="utf-8"?><html><body>'
            "<p>Text readrobe.com text</p><p>리드로브닷컴</p>"
            "</body></html>",
        )
        archive.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0" encoding="utf-8"?><package><metadata>'
            "<title>www.readrobe.com</title></metadata></package>",
        )

    result = scrub_epub(epub)

    assert result == {"files_changed": 2, "replacements": 3, "status": "updated"}
    with zipfile.ZipFile(epub) as archive:
        assert archive.namelist()[0] == "mimetype"
        assert archive.testzip() is None
        combined = " ".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name != "mimetype"
        )
    assert not WATERMARK_PATTERN.search(combined)
