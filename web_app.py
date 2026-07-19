#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import io
import os
import threading
import webbrowser
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

from audiobook_maker import discover_chrome_executable, resolve_ffmpeg_binary
from webui.job_manager import JobManager, JobValidationError, scan_folder_sources
from webui.platform import discover_ebook_convert


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = ROOT / ".webui"


def bool_form(name: str) -> bool:
    return str(request.form.get(name) or "").lower() in {"1", "true", "yes", "on"}


def bool_value(value: Any) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def ebook_convert_available() -> bool:
    executable = discover_ebook_convert()
    return bool(executable and Path(executable).is_file())


def create_app(
    *,
    data_root: Path | None = None,
    manager: JobManager | None = None,
    max_upload_mb: int = 100,
) -> Flask:
    upload_limit_mb = max(1, int(max_upload_mb))
    app = Flask(
        __name__,
        template_folder=str(ROOT / "webui" / "templates"),
        static_folder=str(ROOT / "webui" / "static"),
        static_url_path="/static",
    )
    app.config.update(
        MAX_CONTENT_LENGTH=upload_limit_mb * 1024 * 1024,
        JSON_SORT_KEYS=False,
    )
    owns_manager = manager is None
    job_manager = manager or JobManager(
        data_root or Path(os.getenv("AUDIOBOOK_WEB_DATA_DIR", str(DEFAULT_DATA_ROOT)))
    )
    app.extensions["job_manager"] = job_manager
    if owns_manager:
        atexit.register(job_manager.close)

    @app.after_request
    def set_security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; media-src 'self'; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error):
        return jsonify({"error": f"Upload exceeds the {upload_limit_mb} MB limit"}), 413

    @app.errorhandler(JobValidationError)
    def invalid_job(error: JobValidationError):
        return jsonify({"error": str(error)}), 400

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/favicon.ico")
    def favicon():
        return send_file(ROOT / "webui" / "static" / "icons" / "play.svg", mimetype="image/svg+xml")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/system")
    def system_status():
        chrome = discover_chrome_executable()
        return jsonify(
            {
                "chrome_available": bool(chrome and Path(chrome).is_file()),
                "chrome_name": Path(chrome).name if chrome else "",
                "ffmpeg_available": bool(resolve_ffmpeg_binary()),
                "gemini_api_key": bool(
                    os.getenv("GEMINI_API_KEY", "").strip()
                    or os.getenv("GOOGLE_API_KEY", "").strip()
                ),
                "ebook_convert_available": ebook_convert_available(),
                "max_upload_mb": upload_limit_mb,
            }
        )

    @app.get("/api/jobs")
    def list_jobs():
        return jsonify({"jobs": job_manager.list_jobs()})

    @app.post("/api/jobs")
    def create_job():
        source_kind = str(request.form.get("source_kind") or "file")
        if source_kind not in {"file", "text"}:
            raise JobValidationError("Unsupported source type")
        if source_kind == "text":
            text = str(request.form.get("text") or "").strip()
            if not text:
                raise JobValidationError("Enter text to create an audiobook")
            source_name = str(request.form.get("text_name") or "direct_text.txt")
            if not source_name.lower().endswith(".txt"):
                source_name += ".txt"
            source_stream = io.BytesIO(text.encode("utf-8"))
        else:
            upload = request.files.get("file")
            if upload is None or not upload.filename:
                raise JobValidationError("Choose a source file")
            source_name = upload.filename
            source_stream = upload.stream

        settings: dict[str, Any] = {
            "provider": request.form.get("provider"),
            "mode": request.form.get("mode"),
            "voice": request.form.get("voice"),
            "max_chars": request.form.get("max_chars"),
            "bitrate": request.form.get("bitrate"),
            "max_attempts": request.form.get("max_attempts"),
            "model": request.form.get("model"),
            "visible": bool_form("visible"),
        }
        job = job_manager.create_job(
            source_name=source_name,
            source_stream=source_stream,
            settings=settings,
        )
        return jsonify({"job": job}), 201

    @app.post("/api/jobs/translation")
    def create_translation_job():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            raise JobValidationError("Choose an EPUB, PDF, or MOBI source file")
        if Path(upload.filename).suffix.lower() == ".mobi" and not ebook_convert_available():
            raise JobValidationError("MOBI translation requires Calibre or EBOOK_CONVERT_PATH")
        settings: dict[str, Any] = {
            "translation_provider": request.form.get("translation_provider"),
            "translation_output": request.form.get("translation_output"),
            "max_chars": request.form.get("max_chars"),
            "max_attempts": request.form.get("max_attempts"),
            "chunks_per_conversation": request.form.get("chunks_per_conversation"),
            "inter_request_delay": request.form.get("inter_request_delay"),
            "request_timeout": request.form.get("request_timeout"),
            "visible": bool_form("visible"),
            "overwrite": bool_form("overwrite"),
        }
        job = job_manager.create_translation_job(
            source_name=upload.filename,
            source_stream=upload.stream,
            settings=settings,
        )
        return jsonify({"job": job}), 201

    @app.post("/api/folders/scan")
    def scan_folder():
        payload = request.get_json(silent=True) or {}
        summary = scan_folder_sources(
            str(payload.get("source_dir") or ""),
            operation=str(payload.get("operation") or ""),
            recursive=bool_value(payload.get("recursive")),
        )
        return jsonify(summary)

    @app.post("/api/jobs/batch")
    def create_batch_job():
        payload = request.get_json(silent=True) or {}
        operation = str(payload.get("operation") or "")
        settings: dict[str, Any]
        if operation == "batch_translation":
            settings = {
                "translation_provider": payload.get("translation_provider"),
                "translation_output": payload.get("translation_output"),
                "max_chars": payload.get("max_chars"),
                "max_attempts": payload.get("max_attempts"),
                "chunks_per_conversation": payload.get("chunks_per_conversation"),
                "inter_request_delay": payload.get("inter_request_delay"),
                "request_timeout": payload.get("request_timeout"),
                "visible": bool_value(payload.get("visible")),
                "recursive": bool_value(payload.get("recursive")),
                "overwrite": bool_value(payload.get("overwrite")),
                "priority_substrings": payload.get("priority_substrings"),
                "disable_web_fallback": bool_value(payload.get("disable_web_fallback")),
            }
        else:
            settings = {
                "provider": payload.get("provider"),
                "mode": payload.get("mode"),
                "voice": payload.get("voice"),
                "max_chars": payload.get("max_chars"),
                "bitrate": payload.get("bitrate"),
                "max_attempts": payload.get("max_attempts"),
                "model": payload.get("model"),
                "visible": bool_value(payload.get("visible")),
                "recursive": bool_value(payload.get("recursive")),
                "overwrite": bool_value(payload.get("overwrite")),
            }
        job = job_manager.create_folder_job(
            operation=operation,
            source_dir=str(payload.get("source_dir") or ""),
            output_dir=str(payload.get("output_dir") or "") or None,
            settings=settings,
        )
        return jsonify({"job": job}), 201

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id: str):
        try:
            return jsonify({"job": job_manager.public_job(job_id)})
        except KeyError:
            return jsonify({"error": "Job not found"}), 404

    @app.get("/api/jobs/<job_id>/log")
    def get_job_log(job_id: str):
        try:
            offset = int(request.args.get("offset", "0"))
        except ValueError:
            return jsonify({"error": "Log offset must be an integer"}), 400
        try:
            return jsonify(job_manager.read_log(job_id, offset=offset))
        except KeyError:
            return jsonify({"error": "Job not found"}), 404

    @app.post("/api/jobs/<job_id>/stop")
    def stop_job(job_id: str):
        try:
            return jsonify({"job": job_manager.stop_job(job_id)})
        except KeyError:
            return jsonify({"error": "Job not found"}), 404

    @app.delete("/api/jobs/<job_id>")
    def delete_job(job_id: str):
        try:
            job_manager.delete_job(job_id)
            return "", 204
        except KeyError:
            return jsonify({"error": "Job not found"}), 404

    @app.get("/api/jobs/<job_id>/download")
    def download_job(job_id: str):
        try:
            path = job_manager.output_path(job_id)
            inline = request.args.get("inline") == "1"
            return send_file(path, as_attachment=not inline, download_name=path.name, conditional=True)
        except (KeyError, FileNotFoundError):
            return jsonify({"error": "Output is not ready"}), 404

    @app.get("/api/jobs/<job_id>/artifacts/<int:index>")
    def download_artifact(job_id: str, index: int):
        try:
            path = job_manager.artifact_path(job_id, index)
            inline = request.args.get("inline") == "1" and path.suffix.lower() in {".m4a", ".mp3", ".wav"}
            return send_file(path, as_attachment=not inline, download_name=path.name, conditional=True)
        except (KeyError, FileNotFoundError):
            return jsonify({"error": "Artifact is not ready"}), 404

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Korean Audiobook Maker web interface.")
    parser.add_argument("--host", default=os.getenv("AUDIOBOOK_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("AUDIOBOOK_WEB_PORT", "7860")))
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("AUDIOBOOK_WEB_DATA_DIR", str(DEFAULT_DATA_ROOT))),
    )
    parser.add_argument(
        "--max-upload-mb",
        type=int,
        default=int(os.getenv("AUDIOBOOK_MAX_UPLOAD_MB", "100")),
    )
    parser.add_argument("--no-open-browser", action="store_true")
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow binding beyond localhost. The web UI has no built-in authentication.",
    )
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_remote:
        raise SystemExit("Refusing a non-local host without --allow-remote")
    app = create_app(data_root=args.data_dir, max_upload_mb=args.max_upload_mb)
    url_host = "127.0.0.1" if args.host in {"0.0.0.0", "::", "::1"} else args.host
    url = f"http://{url_host}:{args.port}"
    if not args.no_open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"Audiobook Studio: {url}", flush=True)
    if args.debug:
        app.run(host=args.host, port=args.port, debug=True, use_reloader=False)
    else:
        from waitress import serve

        serve(app, host=args.host, port=args.port, threads=8)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
