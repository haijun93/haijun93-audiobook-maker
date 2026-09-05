from __future__ import annotations

import json
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


def test_find_existing_item_work_dir_matches_by_recorded_input_epub(tmp_path: Path) -> None:
    # A book fully translated in an earlier run (e.g. work/0016_Book) must still be found
    # even if this run's fresh file-order scan would now number it differently
    # (e.g. work/0019_Book) - otherwise its completed translation cache is orphaned and
    # the book gets silently retranslated from scratch.
    work_root = tmp_path / "work"
    source = tmp_path / "Outlander.epub"
    source.write_bytes(b"source")
    old_dir = work_root / "0016_Outlander"
    (old_dir / "translation").mkdir(parents=True)
    (old_dir / "translation" / "manifest.json").write_text(
        json.dumps({"input_epub": str(source.resolve())}), encoding="utf-8"
    )

    found = workflow_runner.find_existing_item_work_dir(work_root, source)

    assert found == old_dir


def test_find_existing_item_work_dir_ignores_other_books(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    source = tmp_path / "Outlander.epub"
    source.write_bytes(b"source")
    other_source = tmp_path / "Different Book.epub"
    other_source.write_bytes(b"other")
    other_dir = work_root / "0001_Different Book"
    (other_dir / "translation").mkdir(parents=True)
    (other_dir / "translation" / "manifest.json").write_text(
        json.dumps({"input_epub": str(other_source.resolve())}), encoding="utf-8"
    )

    found = workflow_runner.find_existing_item_work_dir(work_root, source)

    assert found is None


def test_find_existing_item_work_dir_returns_none_when_work_root_missing(tmp_path: Path) -> None:
    assert workflow_runner.find_existing_item_work_dir(tmp_path / "no-such-dir", tmp_path / "Book.epub") is None


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


def test_source_files_excludes_finished_subfolder(tmp_path: Path) -> None:
    # run_batch() archives each completed book's source into source_dir/finished/ - a
    # recursive rescan must not pick those back up as new sources to translate.
    (tmp_path / "Book.epub").write_bytes(b"book")
    finished_dir = tmp_path / "finished"
    finished_dir.mkdir()
    (finished_dir / "Already Done.epub").write_bytes(b"done")

    sources = workflow_runner.source_files(
        tmp_path,
        operation="batch_translation",
        recursive=True,
        output_root=tmp_path,
    )

    assert [path.name for path in sources] == ["Book.epub"]


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
    assert [artifact["kind"] for artifact in artifacts] == ["english_epub", "bilingual_epub", "korean_epub"]


def test_translation_command_includes_study_output_flag_when_given(tmp_path: Path) -> None:
    args = SimpleNamespace(
        translation_provider="gemini",
        max_chars=6000,
        max_attempts=5,
        chunks_per_conversation=10,
        inter_request_delay=4.0,
        request_timeout=1200,
        visible=False,
    )

    command = workflow_runner.translation_command(
        source_epub=tmp_path / "Book.epub",
        bilingual_output=tmp_path / "[k-e] Book.epub",
        work_dir=tmp_path / "work",
        heartbeat_file=tmp_path / "heartbeat.json",
        args=args,
        study_output=tmp_path / "[study] Book.epub",
    )

    assert "--study-output-epub" in command
    assert str(tmp_path / "[study] Book.epub") in command


def test_translation_command_omits_study_output_flag_when_not_given(tmp_path: Path) -> None:
    args = SimpleNamespace(
        translation_provider="gemini",
        max_chars=6000,
        max_attempts=5,
        chunks_per_conversation=10,
        inter_request_delay=4.0,
        request_timeout=1200,
        visible=False,
    )

    command = workflow_runner.translation_command(
        source_epub=tmp_path / "Book.epub",
        bilingual_output=tmp_path / "[k-e] Book.epub",
        work_dir=tmp_path / "work",
        heartbeat_file=tmp_path / "heartbeat.json",
        args=args,
    )

    assert "--study-output-epub" not in command
    assert command.count("--heartbeat-file") == 1


def test_batch_retry_policy_pauses_immediately_for_account_failure() -> None:
    retry, delay, diagnosis = workflow_runner.batch_retry_policy(
        RuntimeError(
            "ChatGPT error_kind=account_unavailable retry_action=pause_for_account_recovery"
        ),
        book_attempt=1,
    )

    assert retry is False
    assert delay == 0
    assert diagnosis["kind"] == "account_unavailable"


def test_batch_retry_policy_retries_transient_service_failure() -> None:
    retry, delay, diagnosis = workflow_runner.batch_retry_policy(
        RuntimeError("Gemini error_kind=temporary_service_error retry_action=exponential_backoff"),
        book_attempt=1,
    )

    assert retry is True
    assert delay == workflow_runner.BOOK_RETRY_BASE_DELAY_SEC
    assert diagnosis["kind"] == "temporary_service_error"


def test_translate_one_builds_study_epub_alongside_bilingual_and_korean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "Book.epub"
    source.write_bytes(b"source")
    output_root = tmp_path / "output"
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

    captured_commands: list[list[str]] = []

    def fake_run(command: list[str]) -> None:
        captured_commands.append(command)
        bilingual = output_root / "[k-e]" / "[k-e] Book.epub"
        study = output_root / "[study]" / "[study] Book.epub"
        bilingual.parent.mkdir(parents=True, exist_ok=True)
        study.parent.mkdir(parents=True, exist_ok=True)
        bilingual.write_bytes(b"new-bilingual")
        study.write_bytes(b"new-study")

    def fake_convert(input_path: Path, output_path: Path, _overwrite: bool) -> None:
        output_path.write_bytes(b"derived:" + input_path.read_bytes())

    monkeypatch.setattr(workflow_runner, "run_child", fake_run)
    monkeypatch.setattr(workflow_runner, "convert_epub", fake_convert)
    monkeypatch.setattr(workflow_runner, "convert_epub_to_english_study", fake_convert)

    artifacts = workflow_runner.translate_one(
        source,
        output_root=output_root,
        work_dir=tmp_path / "work",
        heartbeat_file=tmp_path / "heartbeat.json",
        args=args,
        split_output_dirs=True,
    )

    assert "--study-output-epub" in captured_commands[0]
    assert [artifact["kind"] for artifact in artifacts] == [
        "english_epub",
        "bilingual_epub",
        "korean_epub",
        "study_epub",
        "english_study_epub",
    ]
    assert (output_root / "[study]" / "[study] Book.epub").read_bytes() == b"new-study"
    assert (output_root / "[e]" / "[e] Book.epub").read_bytes() == b"source"
    assert (output_root / "[e-s]" / "[e-s] Book.epub").read_bytes() == b"derived:new-study"


def test_translate_one_backfills_missing_english_copy_without_retranslating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A book translated before the [e] output existed already has [k-e]/[k]/[study] -
    # only [e] is missing. Backfilling it should just copy the prepared source, with no
    # web-automation subprocess call.
    source = tmp_path / "Book.epub"
    source.write_bytes(b"source")
    output_root = tmp_path / "output"
    for rel in (
        "[k-e]/[k-e] Book.epub",
        "[k]/[k] Book.epub",
        "[study]/[study] Book.epub",
        "[e-s]/[e-s] Book.epub",
    ):
        path = output_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"already-done")
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

    def fail_if_called(_command: list[str]) -> None:
        raise AssertionError("run_child should not be called when only [e] needs backfilling")

    monkeypatch.setattr(workflow_runner, "run_child", fail_if_called)

    artifacts = workflow_runner.translate_one(
        source,
        output_root=output_root,
        work_dir=tmp_path / "work",
        heartbeat_file=tmp_path / "heartbeat.json",
        args=args,
        split_output_dirs=True,
    )

    assert (output_root / "[e]" / "[e] Book.epub").read_bytes() == b"source"
    assert {artifact["kind"] for artifact in artifacts} == {
        "english_epub",
        "bilingual_epub",
        "korean_epub",
        "study_epub",
        "english_study_epub",
    }


def _write_minimal_epub(path: Path, *, title: str, paragraphs: list[str]) -> None:
    body = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        )
        archive.writestr(
            "OEBPS/content.opf",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>Test Author</dc:creator>
  </metadata>
  <manifest>
    <item id="ch1" href="chapter01.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
  </spine>
</package>
""",
        )
        archive.writestr(
            "OEBPS/chapter01.xhtml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>{body}</body></html>
""",
        )


def test_looks_like_english_source_accepts_english_prose(tmp_path: Path) -> None:
    source = tmp_path / "english.epub"
    _write_minimal_epub(
        source,
        title="An English Novel",
        paragraphs=[
            "She walked into the room and looked at him without saying a word for a long moment.",
            "He was the only person who had ever understood what she meant when she talked about the sea.",
            "They had known each other since they were children, and nothing had really changed between them.",
        ],
    )

    assert workflow_runner.looks_like_english_source(source) is True


def test_looks_like_english_source_rejects_non_english_prose(tmp_path: Path) -> None:
    source = tmp_path / "french.epub"
    _write_minimal_epub(
        source,
        title="Un Roman Francais",
        paragraphs=[
            "Elle entra dans la piece et le regarda sans dire un mot pendant un long moment.",
            "Il etait la seule personne qui avait jamais compris ce qu'elle voulait dire en parlant de la mer.",
            "Ils se connaissaient depuis leur enfance, et rien n'avait vraiment change entre eux.",
        ],
    )

    assert workflow_runner.looks_like_english_source(source) is False


def test_archive_non_english_source_moves_file_out_of_scan_path(tmp_path: Path) -> None:
    source_dir = tmp_path / "new books from vk"
    source_dir.mkdir()
    source = source_dir / "roman.epub"
    source.write_bytes(b"fake-epub-bytes")

    archived_path = workflow_runner.archive_non_english_source(source, source_dir)

    assert archived_path == source_dir / "non-english" / "roman.epub"
    assert archived_path.is_file()
    assert not source.exists()


def test_run_batch_archives_source_into_finished_folder_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A freshly-completed book's source used to just sit in source_dir forever - only
    # sources that were *already* done before this run started got archived (the
    # find_finished_match/SKIP-duplicate branch). This locks in the fix: run_batch()
    # must archive the source itself right after a book it just translated succeeds.
    source_dir = tmp_path / "vk"
    source_dir.mkdir()
    source = source_dir / "Book.epub"
    source.write_bytes(b"fake-epub-bytes")
    output_dir = tmp_path / "output"
    work_dir = tmp_path / "work"

    monkeypatch.setattr(workflow_runner, "build_finished_registry", lambda _dir: [])
    monkeypatch.setattr(workflow_runner, "build_html_collection_registry", lambda _path: [])
    monkeypatch.setattr(workflow_runner, "build_library_registry", lambda _dir: [])
    monkeypatch.setattr(workflow_runner, "get_existing_korean_books", lambda _dir: set())

    def fake_translate_one(source_path: Path, **_kwargs: object) -> list[dict[str, str]]:
        return [{"path": str(source_path), "kind": "k-e"}]

    monkeypatch.setattr(workflow_runner, "translate_one", fake_translate_one)

    args = SimpleNamespace(
        source_dir=source_dir,
        output_dir=output_dir,
        priority_substrings="",
        task="batch_translation",
        recursive=False,
        heartbeat_file=tmp_path / "heartbeat.json",
        batch_status_file=tmp_path / "batch_status.json",
        work_dir=work_dir,
        artifact_manifest_file=tmp_path / "artifacts.json",
    )

    return_code = workflow_runner.run_batch(args)

    assert return_code == 0
    assert not source.exists()
    assert (source_dir / "finished" / "Book.epub").is_file()


def test_run_batch_reverse_processes_targets_in_descending_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Two parallel instances (e.g. two Google accounts) can share one source folder
    # without retranslating the same book by having one work forward from the first
    # target and the other work backward from the last (--reverse). This locks in that
    # run_batch() actually consumes the target list in descending order when reverse=True.
    source_dir = tmp_path / "vk"
    source_dir.mkdir()
    (source_dir / "A Book.epub").write_bytes(b"a")
    (source_dir / "B Book.epub").write_bytes(b"b")
    (source_dir / "C Book.epub").write_bytes(b"c")
    output_dir = tmp_path / "output"
    work_dir = tmp_path / "work"

    monkeypatch.setattr(workflow_runner, "build_finished_registry", lambda _dir: [])
    monkeypatch.setattr(workflow_runner, "build_html_collection_registry", lambda _path: [])
    monkeypatch.setattr(workflow_runner, "build_library_registry", lambda _dir: [])
    monkeypatch.setattr(workflow_runner, "get_existing_korean_books", lambda _dir: set())

    processed_order: list[str] = []

    def fake_translate_one(source_path: Path, **_kwargs: object) -> list[dict[str, str]]:
        processed_order.append(source_path.name)
        return []

    monkeypatch.setattr(workflow_runner, "translate_one", fake_translate_one)

    args = SimpleNamespace(
        source_dir=source_dir,
        output_dir=output_dir,
        priority_substrings="",
        task="batch_translation",
        recursive=False,
        reverse=True,
        heartbeat_file=tmp_path / "heartbeat.json",
        batch_status_file=tmp_path / "batch_status.json",
        work_dir=work_dir,
        artifact_manifest_file=tmp_path / "artifacts.json",
    )

    return_code = workflow_runner.run_batch(args)

    assert return_code == 0
    assert processed_order == ["C Book.epub", "B Book.epub", "A Book.epub"]


def test_run_batch_stops_remaining_books_on_account_pause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "A Book.epub").write_bytes(b"a")
    (source_dir / "B Book.epub").write_bytes(b"b")

    monkeypatch.setattr(workflow_runner, "build_finished_registry", lambda _dir: [])
    monkeypatch.setattr(workflow_runner, "build_html_collection_registry", lambda _path: [])
    monkeypatch.setattr(workflow_runner, "build_library_registry", lambda _dir: [])
    monkeypatch.setattr(workflow_runner, "get_existing_korean_books", lambda _dir: set())
    monkeypatch.setattr(
        workflow_runner,
        "extract_metadata_from_epub",
        lambda path: {"title": path.stem, "author": "Tester"},
    )
    monkeypatch.setattr(workflow_runner, "find_finished_match", lambda *_args: None)
    monkeypatch.setattr(workflow_runner, "looks_like_english_source", lambda _path: True)
    attempted: list[str] = []

    def fail_for_account(source: Path, **_kwargs: object) -> list[dict[str, str]]:
        attempted.append(source.name)
        raise RuntimeError(
            "ChatGPT error_kind=account_unavailable retry_action=pause_for_account_recovery"
        )

    monkeypatch.setattr(workflow_runner, "translate_one", fail_for_account)
    args = SimpleNamespace(
        source_dir=source_dir,
        output_dir=tmp_path / "output",
        priority_substrings="",
        task="batch_translation",
        recursive=False,
        reverse=False,
        heartbeat_file=tmp_path / "heartbeat.json",
        batch_status_file=tmp_path / "batch_status.json",
        work_dir=tmp_path / "work",
        artifact_manifest_file=tmp_path / "artifacts.json",
    )

    assert workflow_runner.run_batch(args) == 1
    assert attempted == ["A Book.epub"]
    status = json.loads(args.batch_status_file.read_text(encoding="utf-8"))
    assert status["status"] == "paused"
    assert status["diagnosis"]["kind"] == "account_unavailable"
    assert status["completed"][0]["book_attempts"] == "1"
