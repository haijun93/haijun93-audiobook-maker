from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pytest

from web_app import create_app
from webui.job_manager import JobManager, JobValidationError, safe_file_stem, validate_settings


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


def make_manager(tmp_path: Path, *, start_worker: bool = True) -> JobManager:
    runner = tmp_path / "fake_runner.py"
    runner.write_text(FAKE_RUNNER, encoding="utf-8")
    return JobManager(
        tmp_path / "data",
        runner_script=runner,
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


def test_validate_settings_rejects_unknown_provider() -> None:
    with pytest.raises(JobValidationError, match="Unsupported provider"):
        validate_settings(settings(provider="shell"))


def test_closed_manager_rejects_new_jobs(tmp_path: Path) -> None:
    manager = make_manager(tmp_path, start_worker=False)
    manager.close()
    with pytest.raises(JobValidationError, match="shutting down"):
        manager.create_job(
            source_name="late.txt",
            source_stream=io.BytesIO(b"late"),
            settings=settings(),
        )


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
        assert "frame-ancestors 'none'" in index.headers["Content-Security-Policy"]

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
