from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from webui import workflow_runner


def test_readable_stem_preserves_title_words() -> None:
    assert workflow_runner.readable_stem(Path("[e]The_Memory-Book.epub")) == "The Memory Book"


def test_readable_stem_strips_oceanofpdf_watermark() -> None:
    assert (
        workflow_runner.readable_stem(Path("_OceanofPDF.com_Buckled_-_Pam_Godwin.epub"))
        == "Buckled Pam Godwin"
    )


def test_prepare_epub_reflows_english_pdf(tmp_path: Path) -> None:
    source = tmp_path / "lecture.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "An English sentence for translation.")
    document.save(source)
    document.close()

    output = workflow_runner.prepare_epub(source, tmp_path / "work")

    assert output.is_file()
    with zipfile.ZipFile(output) as archive:
        opf = archive.read("OEBPS/content.opf").decode("utf-8")
        assert "<dc:language>en</dc:language>" in opf
        assert "An English sentence" in " ".join(
            archive.read(name).decode("utf-8", "ignore")
            for name in archive.namelist()
            if name.endswith(".xhtml")
        )


def test_prepare_epub_requires_calibre_for_mobi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "book.mobi"
    source.write_bytes(b"mobi")
    monkeypatch.setattr(workflow_runner, "discover_ebook_convert", lambda: "")

    with pytest.raises(RuntimeError, match="Calibre"):
        workflow_runner.prepare_epub(source, tmp_path / "work")


def test_source_files_excludes_generated_editions(tmp_path: Path) -> None:
    (tmp_path / "Book.epub").write_bytes(b"book")
    (tmp_path / "[k-e] Book.epub").write_bytes(b"translated")
    (tmp_path / "[k] Book.epub").write_bytes(b"translated")

    sources = workflow_runner.source_files(
        tmp_path,
        operation="batch_translation",
        recursive=False,
        output_root=tmp_path,
    )

    assert [path.name for path in sources] == ["Book.epub"]


def test_translate_one_rebuilds_korean_when_bilingual_is_new(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "Book.epub"
    source.write_bytes(b"source")
    output_root = tmp_path / "output"
    korean = output_root / "[k]" / "[k] Book.epub"
    korean.parent.mkdir(parents=True)
    korean.write_bytes(b"old-korean")
    args = SimpleNamespace(
        translation_output="both",
        overwrite=False,
        translation_provider="gemini",
        max_chars=6000,
        max_attempts=5,
        chunks_per_conversation=10,
        inter_request_delay=4.0,
        request_timeout=1200,
        visible=False,
    )

    monkeypatch.setattr(workflow_runner, "prepare_epub", lambda path, _work: path)

    def fake_run(_command: list[str]) -> None:
        bilingual = output_root / "[k-e]" / "[k-e] Book.epub"
        bilingual.parent.mkdir(parents=True, exist_ok=True)
        bilingual.write_bytes(b"new-bilingual")

    def fake_convert(input_path: Path, output_path: Path, _overwrite: bool) -> None:
        output_path.write_bytes(b"derived:" + input_path.read_bytes())

    monkeypatch.setattr(workflow_runner, "run_child", fake_run)
    monkeypatch.setattr(workflow_runner, "convert_epub", fake_convert)

    artifacts = workflow_runner.translate_one(
        source,
        output_root=output_root,
        work_dir=tmp_path / "work",
        heartbeat_file=tmp_path / "heartbeat.json",
        args=args,
        split_output_dirs=True,
    )

    assert korean.read_bytes() == b"derived:new-bilingual"
    assert [artifact["kind"] for artifact in artifacts] == ["bilingual_epub", "korean_epub"]
