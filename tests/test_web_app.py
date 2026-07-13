from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pytest

from web_app import create_app
from webui.job_manager import (
    JobManager,
    JobValidationError,
    safe_book_stem,
    safe_file_stem,
    scan_folder_sources,
    validate_settings,
    validate_translation_settings,
)


FAKE_RUNNER = r"""
import argparse
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input-file", required=True)
parser.add_argument("--output-file", required=True)
parser.add_argument("--heartbeat-file", required=True)
args, _ = parser.parse_known_args()
source = Path(args.input_file).read_text(encoding="utf-8")
heartbeat = Path(args.heartbeat_file)
heartbeat.write_text(json.dumps({"stage": "synthesis", "label": "1 / 2"}), encoding="utf-8")
print("fake engine started", flush=True)
if "SLOW_JOB" in source:
    time.sleep(30)
output = Path(args.output_file)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(b"test-audio")
heartbeat.write_text(json.dumps({"stage": "complete", "label": "2 / 2"}), encoding="utf-8")
print("fake engine completed", flush=True)
"""


FAKE_WORKFLOW_RUNNER = r"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--task", required=True)
parser.add_argument("--input-file")
parser.add_argument("--source-dir")
parser.add_argument("--output-dir", required=True)
parser.add_argument("--artifact-manifest-file", required=True)
parser.add_argument("--heartbeat-file", required=True)
parser.add_argument("--translation-output", default="both")
args, _ = parser.parse_known_args()

root = Path(args.output_dir).resolve()
root.mkdir(parents=True, exist_ok=True)
artifacts = []
if args.task == "translation":
    if args.translation_output in {"both", "bilingual"}:
        path = root / "[k-e] Sample Book.epub"
        path.write_bytes(b"bilingual-epub")
        artifacts.append({"path": path.name, "kind": "bilingual_epub"})
    if args.translation_output in {"both", "korean"}:
        path = root / "[k] Sample Book.epub"
        path.write_bytes(b"korean-epub")
        artifacts.append({"path": path.name, "kind": "korean_epub"})
elif args.task == "batch_translation":
    for folder, prefix, kind in (("[k-e]", "[k-e]", "bilingual_epub"), ("[k]", "[k]", "korean_epub")):
        path = root / folder / f"{prefix} Batch Book.epub"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(kind.encode())
        artifacts.append({"path": str(path.relative_to(root)), "kind": kind})
else:
    path = root / "Batch Book_audiobook.m4a"
    path.write_bytes(b"batch-audio")
    artifacts.append({"path": path.name, "kind": "audio"})

Path(args.heartbeat_file).write_text(
    json.dumps({"stage": "complete", "label": "1 / 1"}), encoding="utf-8"
)
Path(args.artifact_manifest_file).write_text(
    json.dumps({"root": str(root), "artifacts": artifacts, "failures": []}), encoding="utf-8"
)
print(f"fake workflow completed: {args.task}", flush=True)
"""


def make_manager(tmp_path: Path, *, start_worker: bool = True) -> JobManager:
    runner = tmp_path / "fake_runner.py"
    runner.write_text(FAKE_RUNNER, encoding="utf-8")
    workflow_runner = tmp_path / "fake_workflow_runner.py"
    workflow_runner.write_text(FAKE_WORKFLOW_RUNNER, encoding="utf-8")
    return JobManager(
        tmp_path / "data",
        runner_script=runner,
        workflow_runner_script=workflow_runner,
        python_executable=sys.executable,
        start_worker=start_worker,
    )


def settings(**overrides):
    values = {
        "provider": "gemini_api_tts",
        "mode": "plain",
        "voice": "Sulafat",
        "max_chars": "2500",
        "bitrate": "96",
        "max_attempts": "3",
        "model": "gemini-2.5-flash-preview-tts",
        "visible": False,
    }
    values.update(overrides)
    return values


def translation_settings(**overrides):
    values = {
        "translation_provider": "gemini",
        "translation_output": "both",
        "max_chars": "6000",
        "max_attempts": "5",
        "chunks_per_conversation": "10",
        "inter_request_delay": "4",
        "request_timeout": "1200",
        "visible": False,
        "recursive": False,
        "overwrite": False,
    }
    values.update(overrides)
    return values


def wait_for_status(manager: JobManager, job_id: str, expected: set[str], timeout: float = 6) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = manager.public_job(job_id)
        if job["status"] in expected:
            return job
        time.sleep(0.04)
    raise AssertionError(f"job did not reach {expected}: {manager.public_job(job_id)}")


def test_safe_file_stem_removes_paths_and_punctuation() -> None:
    assert safe_file_stem("../../나의 책 (final)!.epub") == "나의_책_final"


def test_safe_book_stem_removes_known_edition_prefix() -> None:
    assert safe_book_stem("[e]Never_Lie.epub") == "Never_Lie"
    assert safe_book_stem("[e]Mr. Mercedes.epub") == "Mr_Mercedes"


def test_validate_settings_rejects_unknown_provider() -> None:
    with pytest.raises(JobValidationError, match="Unsupported provider"):
        validate_settings(settings(provider="shell"))


def test_validate_translation_settings_rejects_invalid_output() -> None:
    with pytest.raises(JobValidationError, match="Unsupported translation output"):
        validate_translation_settings(translation_settings(translation_output="html"))


def test_scan_folder_sources_filters_outputs_and_honors_recursion(tmp_path: Path) -> None:
    (tmp_path / "Book.epub").write_bytes(b"book")
    (tmp_path / "[k] Book.epub").write_bytes(b"translated")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "Document.pdf").write_bytes(b"pdf")

    top = scan_folder_sources(tmp_path, operation="batch_translation")
    recursive = scan_folder_sources(tmp_path, operation="batch_translation", recursive=True)

    assert top["total"] == 1
    assert recursive["total"] == 2
    assert recursive["counts"] == {"epub": 1, "pdf": 1}


def test_scan_folder_sources_rejects_blank_path() -> None:
    with pytest.raises(JobValidationError, match="source folder"):
        scan_folder_sources("", operation="batch_translation")


def test_closed_manager_rejects_new_jobs(tmp_path: Path) -> None:
    manager = make_manager(tmp_path, start_worker=False)
    manager.close()
    with pytest.raises(JobValidationError, match="shutting down"):
        manager.create_job(
            source_name="late.txt",
            source_stream=io.BytesIO(b"late"),
            settings=settings(),
        )


def test_job_commands_forward_gemini_web_settings(tmp_path: Path) -> None:
    manager = make_manager(tmp_path, start_worker=False)
    try:
        audio = manager.create_job(
            source_name="narration.txt",
            source_stream=io.BytesIO(b"text"),
            settings=settings(provider="gemini_web", voice="account_default", visible=True),
        )
        audio_command = manager.build_command(manager._read_job(audio["id"]))
        assert ["--provider", "gemini_web"] == audio_command[
            audio_command.index("--provider") : audio_command.index("--provider") + 2
        ]
        assert "--gemini-web-visible" in audio_command

        translation = manager.create_translation_job(
            source_name="book.epub",
            source_stream=io.BytesIO(b"epub"),
            settings=translation_settings(visible=True),
        )
        translation_command = manager.build_command(manager._read_job(translation["id"]))
        assert ["--task", "translation"] == translation_command[
            translation_command.index("--task") : translation_command.index("--task") + 2
        ]
        assert ["--translation-provider", "gemini"] == translation_command[
            translation_command.index("--translation-provider") : translation_command.index("--translation-provider") + 2
        ]
        assert "--visible" in translation_command
    finally:
        manager.close()


def test_job_manager_completes_and_exposes_log_and_output(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    try:
        job = manager.create_job(
            source_name="../sample.txt",
            source_stream=io.BytesIO("안녕하세요".encode()),
            settings=settings(),
        )
        completed = wait_for_status(manager, job["id"], {"completed"})

        assert completed["progress"] == 100
        assert completed["download_ready"] is True
        assert manager.output_path(job["id"]).read_bytes() == b"test-audio"
        assert "fake engine completed" in manager.read_log(job["id"])["text"]
        assert manager._job_dir(job["id"]).joinpath("input/sample.txt").is_file()
    finally:
        manager.close()


def test_job_manager_creates_korean_and_bilingual_epubs(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    try:
        job = manager.create_translation_job(
            source_name="Sample_Book.epub",
            source_stream=io.BytesIO(b"source-epub"),
            settings=translation_settings(),
        )
        completed = wait_for_status(manager, job["id"], {"completed"})

        assert completed["job_type"] == "translation"
        assert [item["kind"] for item in completed["artifacts"]] == ["bilingual_epub", "korean_epub"]
        assert manager.artifact_path(job["id"], 0).read_bytes() == b"bilingual-epub"
        assert manager.artifact_path(job["id"], 1).read_bytes() == b"korean-epub"
    finally:
        manager.close()


@pytest.mark.parametrize(
    ("operation", "expected_kind"),
    [("batch_translation", "bilingual_epub"), ("batch_audio", "audio")],
)
def test_job_manager_runs_folder_workflows(
    tmp_path: Path,
    operation: str,
    expected_kind: str,
) -> None:
    source = tmp_path / "books"
    source.mkdir()
    (source / "Book.epub").write_bytes(b"book")
    output = tmp_path / "results"
    batch_settings = translation_settings() if operation == "batch_translation" else settings(provider="gemini_web", voice="account_default")
    manager = make_manager(tmp_path)
    try:
        job = manager.create_folder_job(
            operation=operation,
            source_dir=str(source),
            output_dir=str(output),
            settings=batch_settings,
        )
        completed = wait_for_status(manager, job["id"], {"completed"})

        assert completed["job_type"] == operation
        assert completed["artifacts"][0]["kind"] == expected_kind
        manager.delete_job(job["id"])
        assert any(output.rglob("*.*"))
    finally:
        manager.close()


def test_job_manager_can_cancel_running_process(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    try:
        job = manager.create_job(
            source_name="slow.txt",
            source_stream=io.BytesIO(b"SLOW_JOB"),
            settings=settings(),
        )
        wait_for_status(manager, job["id"], {"running"})
        manager.stop_job(job["id"])
        cancelled = wait_for_status(manager, job["id"], {"cancelled"})
        assert cancelled["download_ready"] is False
    finally:
        manager.close()


def test_queued_job_is_recovered_after_restart(tmp_path: Path) -> None:
    first = make_manager(tmp_path, start_worker=False)
    job = first.create_job(
        source_name="resume.txt",
        source_stream=io.BytesIO("다시 시작".encode()),
        settings=settings(),
    )
    first.close()

    second = make_manager(tmp_path)
    try:
        completed = wait_for_status(second, job["id"], {"completed"})
        assert completed["message"] == "Audiobook ready"
    finally:
        second.close()


def test_web_api_runs_job_and_downloads_result(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    app = create_app(manager=manager, max_upload_mb=2)
    app.config["TESTING"] = True
    client = app.test_client()
    try:
        index = client.get("/")
        assert index.status_code == 200
        assert b"Audiobook Studio" in index.data
        assert b'id="translation-form"' in index.data
        assert b'id="batch-form"' in index.data
        assert "frame-ancestors 'none'" in index.headers["Content-Security-Policy"]
        assert client.get("/favicon.ico").status_code == 200

        response = client.post(
            "/api/jobs",
            data={
                **settings(),
                "source_kind": "text",
                "text": "웹 테스트",
                "text_name": "web.txt",
            },
        )
        assert response.status_code == 201
        job_id = response.get_json()["job"]["id"]
        wait_for_status(manager, job_id, {"completed"})

        listing = client.get("/api/jobs").get_json()["jobs"]
        assert listing[0]["id"] == job_id
        assert client.get(f"/api/jobs/{job_id}/download").data == b"test-audio"
        assert "fake engine" in client.get(f"/api/jobs/{job_id}/log").get_json()["text"]
    finally:
        manager.close()


def test_web_api_translates_upload_and_downloads_each_edition(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    app = create_app(manager=manager)
    app.config["TESTING"] = True
    client = app.test_client()
    try:
        response = client.post(
            "/api/jobs/translation",
            data={
                **translation_settings(),
                "file": (io.BytesIO(b"epub"), "Sample.epub"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 201
        job_id = response.get_json()["job"]["id"]
        completed = wait_for_status(manager, job_id, {"completed"})

        assert len(completed["artifacts"]) == 2
        assert client.get(f"/api/jobs/{job_id}/artifacts/0").data == b"bilingual-epub"
        assert client.get(f"/api/jobs/{job_id}/artifacts/1").data == b"korean-epub"
        assert client.get(f"/api/jobs/{job_id}/artifacts/2").status_code == 404
    finally:
        manager.close()


def test_web_api_scans_and_starts_folder_batch(tmp_path: Path) -> None:
    source = tmp_path / "books"
    source.mkdir()
    (source / "Book.epub").write_bytes(b"book")
    output = tmp_path / "translated"
    manager = make_manager(tmp_path)
    app = create_app(manager=manager)
    app.config["TESTING"] = True
    client = app.test_client()
    try:
        scan = client.post(
            "/api/folders/scan",
            json={"source_dir": str(source), "operation": "batch_translation", "recursive": False},
        )
        assert scan.status_code == 200
        assert scan.get_json()["counts"] == {"epub": 1}

        response = client.post(
            "/api/jobs/batch",
            json={
                **translation_settings(),
                "operation": "batch_translation",
                "source_dir": str(source),
                "output_dir": str(output),
            },
        )
        assert response.status_code == 201
        completed = wait_for_status(manager, response.get_json()["job"]["id"], {"completed"})
        assert len(completed["artifacts"]) == 2
    finally:
        manager.close()


def test_web_api_rejects_mobi_without_calibre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = make_manager(tmp_path)
    app = create_app(manager=manager)
    app.config["TESTING"] = True
    monkeypatch.setattr("web_app.ebook_convert_available", lambda: False)
    try:
        response = app.test_client().post(
            "/api/jobs/translation",
            data={
                **translation_settings(),
                "file": (io.BytesIO(b"mobi"), "Sample.mobi"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        assert "Calibre" in response.get_json()["error"]
    finally:
        manager.close()


def test_web_api_rejects_unsupported_upload(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    app = create_app(manager=manager)
    app.config["TESTING"] = True
    try:
        response = app.test_client().post(
            "/api/jobs",
            data={
                **settings(),
                "source_kind": "file",
                "file": (io.BytesIO(b"payload"), "malware.exe"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        assert "supported" in response.get_json()["error"]
    finally:
        manager.close()


def test_web_api_rejects_unknown_source_type(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    app = create_app(manager=manager)
    app.config["TESTING"] = True
    try:
        response = app.test_client().post(
            "/api/jobs",
            data={**settings(), "source_kind": "url", "text": "ignored"},
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "Unsupported source type"
    finally:
        manager.close()


def test_web_api_rejects_invalid_log_offset(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    app = create_app(manager=manager)
    app.config["TESTING"] = True
    try:
        response = app.test_client().get(f"/api/jobs/{'a' * 32}/log?offset=NaN")
        assert response.status_code == 400
        assert response.get_json()["error"] == "Log offset must be an integer"
    finally:
        manager.close()
