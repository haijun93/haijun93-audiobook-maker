#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
from datetime import datetime, timezone
import io
import json
import os
import threading
import time
import webbrowser
import hashlib
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context
from werkzeug.exceptions import RequestEntityTooLarge

from audiobook_maker import (
    EDGE_TTS_DEFAULT_VOICE,
    EDGE_TTS_VOICES,
    EDGE_TTS_VOICE_DESCRIPTIONS,
    chatgpt_web_voice_choices,
    discover_chrome_executable,
    gemini_api_tts_voice_choices,
    gemini_web_voice_choices,
    request_edge_tts_audio_file,
    resolve_ffmpeg_binary,
)
from webui.job_manager import JobManager, JobValidationError, scan_folder_sources
from webui.platform import discover_ebook_convert
from webui.runtime_monitor import RuntimeMonitor


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
    runtime_monitor: RuntimeMonitor | None = None,
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
    monitor = runtime_monitor or RuntimeMonitor(ignored_roots=[job_manager.jobs_root])
    app.extensions["job_manager"] = job_manager
    app.extensions["runtime_monitor"] = monitor
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

    @app.get("/api/runtime")
    def runtime_status():
        return jsonify(monitor.snapshot())

    @app.get("/api/runtime/stream")
    def runtime_status_stream():
        @stream_with_context
        def event_stream():
            while True:
                snapshot = monitor.snapshot()
                yield f"event: runtime\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
                time.sleep(max(0.25, int(snapshot.get("refresh_after_ms") or 1000) / 1000))

        return Response(
            event_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/tts/voices")
    def get_voices():
        provider = str(request.args.get("provider") or "edge_tts").lower()
        if provider == "edge_tts":
            voices = []
            for v_id in EDGE_TTS_VOICES:
                desc = EDGE_TTS_VOICE_DESCRIPTIONS.get(v_id, v_id)
                is_ko = "ko-KR" in v_id
                gender = "Female" if any(f in v_id for f in ("SunHi", "Ava", "Emma", "Ana", "Jenny", "Michelle")) else "Male"
                voices.append({
                    "id": v_id,
                    "name": desc,
                    "lang": "ko-KR" if is_ko else "en-US",
                    "gender": gender,
                    "default_sample": "안녕하세요. 오디오북 제작 스튜디오의 한국어 음성 샘플입니다." if is_ko else "Hello, this is an audiobook preview sample.",
                })
            return jsonify({"provider": "edge_tts", "default_voice": EDGE_TTS_DEFAULT_VOICE, "voices": voices})
        elif provider == "gemini_api_tts":
            voices = [
                {
                    "id": v,
                    "name": f"{v} (Gemini Neural)",
                    "lang": "ko-KR",
                    "gender": "Female" if v in ("Aoede", "Callirrhoe", "Autonoe", "Leda", "Kore", "Despina", "Erinome", "Laomedeia", "Pulcherrima", "Vindemiatrix", "Sulafat") else "Male",
                    "default_sample": "안녕하세요. Gemini API TTS 음성 샘플입니다.",
                }
                for v in gemini_api_tts_voice_choices()
            ]
            return jsonify({"provider": "gemini_api_tts", "default_voice": "Sulafat", "voices": voices})
        elif provider == "chatgpt_web":
            voices = [
                {
                    "id": v,
                    "name": f"{v.title()} (ChatGPT Web)",
                    "lang": "ko-KR",
                    "gender": "Female" if v.lower() in ("juniper", "breeze", "cove", "shimmer", "sol") else "Male",
                    "default_sample": "안녕하세요. ChatGPT 웹 음성 샘플입니다.",
                }
                for v in chatgpt_web_voice_choices()
            ]
            return jsonify({"provider": "chatgpt_web", "default_voice": "cove", "voices": voices})
        else:
            voices = [
                {
                    "id": "account_default",
                    "name": "계정 기본 음성 (Gemini Web)",
                    "lang": "ko-KR",
                    "gender": "Neutral",
                    "default_sample": "안녕하세요. Gemini 웹 음성 샘플입니다.",
                }
            ]
            return jsonify({"provider": "gemini_web", "default_voice": "account_default", "voices": voices})

    @app.get("/api/tts/preview")
    def preview_voice():
        provider = str(request.args.get("provider") or "edge_tts").lower()
        voice = str(request.args.get("voice") or EDGE_TTS_DEFAULT_VOICE).strip()
        is_ko = "ko-KR" in voice or not voice.startswith("en-")
        default_text = "안녕하세요. 오디오북 제작 스튜디오의 한국어 음성 샘플입니다." if is_ko else "Hello, this is an audiobook preview sample."
        sample_text = str(request.args.get("text") or "").strip() or default_text

        if provider == "edge_tts":
            cache_dir = (data_root or Path(os.getenv("AUDIOBOOK_WEB_DATA_DIR", str(DEFAULT_DATA_ROOT)))) / "preview_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            text_hash = hashlib.md5(f"{voice}_{sample_text}".encode("utf-8")).hexdigest()[:12]
            preview_file = cache_dir / f"preview_{voice}_{text_hash}.mp3"
            if not preview_file.is_file() or preview_file.stat().st_size == 0:
                try:
                    request_edge_tts_audio_file(sample_text, preview_file, voice=voice)
                except Exception as exc:
                    return jsonify({"error": f"Preview generation failed: {exc}"}), 500
            return send_file(preview_file, mimetype="audio/mpeg", max_age=86400)
        return jsonify({"error": f"미리듣기는 Edge TTS 음성에서 즉시 지원됩니다."}), 400

    @app.get("/api/batch-report")
    def get_batch_report():
        scheduler_dir = ROOT / ".work" / "continuous_scheduler"
        state_file = scheduler_dir / "state.json"
        config_file = scheduler_dir / "config.json"
        health_file = scheduler_dir / "account_login_health.json"
        latest_audit_file = scheduler_dir / "latest_operations_audit.json"
        audit_log_file = scheduler_dir / "operations_audits.jsonl"
        events_file = scheduler_dir / "events.jsonl"
        
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
        config = json.loads(config_file.read_text(encoding="utf-8")) if config_file.is_file() else {}
        health = json.loads(health_file.read_text(encoding="utf-8")) if health_file.is_file() else {}
        latest_audit = json.loads(latest_audit_file.read_text(encoding="utf-8")) if latest_audit_file.is_file() else {}
        
        # 1. Audit history
        audit_history = []
        if audit_log_file.is_file():
            try:
                lines = audit_log_file.read_text(encoding="utf-8").strip().splitlines()
                for line in lines[-6:]:
                    try:
                        audit_history.append(json.loads(line))
                    except Exception:
                        pass
            except Exception:
                pass

        # 2. Map tasks to executing accounts from events.jsonl
        task_account_map = {}
        if events_file.is_file():
            try:
                for line in events_file.read_text(encoding="utf-8").splitlines():
                    try:
                        ev = json.loads(line)
                        tid = ev.get("task_id")
                        aid = ev.get("account_id")
                        if tid and aid:
                            task_account_map[tid] = aid
                    except Exception:
                        pass
            except Exception:
                pass

        # 3. Scan completion timestamps from standard library epub files in 소설2
        library_root = Path("/Users/hyeokjunkong/Desktop/소설2")
        epub_mtimes = {}
        if library_root.is_dir():
            try:
                for prefix in ["[k-e]", "[k]", "[study]", "[e-s]"]:
                    pref_dir = library_root / prefix
                    if pref_dir.is_dir():
                        for ep in pref_dir.glob("**/*.epub"):
                            mtime = datetime.fromtimestamp(ep.stat().st_mtime).isoformat()
                            for tspec in config.get("tasks", []):
                                title = tspec.get("title", "")
                                clean_title = title.split(" (")[0].strip()
                                if clean_title and clean_title in ep.name:
                                    if tspec["id"] not in epub_mtimes or mtime > epub_mtimes[tspec["id"]]:
                                        epub_mtimes[tspec["id"]] = mtime
            except Exception:
                pass

        # 4. Active & Completed tasks
        active_tasks = []
        completed_tasks = []
        task_states = state.get("tasks", {})
        for tspec in config.get("tasks", []):
            tid = tspec["id"]
            tstate = task_states.get(tid, {})
            status = tstate.get("status", "unknown")
            work_dir = Path(tspec.get("work_dir", ""))
            hb_path = work_dir / "heartbeat.json"
            
            hb = {}
            if hb_path.is_file():
                try:
                    hb = json.loads(hb_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
                    
            completed = hb.get("completed_chunks", hb.get("completed", 0))
            total = hb.get("total_chunks", hb.get("total", 0))
            label = str(hb.get("label") or "")
            
            # If completed/total is 0 but label has '번역 X/Y', parse from label
            if (total == 0 or completed == 0) and "번역 " in label:
                try:
                    import re
                    m = re.search(r"번역\s+(\d+)\s*/\s*(\d+)", label)
                    if m:
                        completed = int(m.group(1))
                        total = int(m.group(2))
                except Exception:
                    pass
                    
            pct = round((completed / total * 100), 1) if total > 0 else 0.0
            
            task_info = {
                "id": tid,
                "title": tspec.get("title", tid),
                "status": status,
                "account_id": tstate.get("account_id"),
                "completed": completed,
                "total": total,
                "progress_percent": pct,
                "stage": hb.get("stage", ""),
                "label": label,
                "detail": hb.get("detail", ""),
                "speed_cph": hb.get("chunks_per_hour", 0.0),
                "eta_minutes": hb.get("eta_minutes"),
                "last_error": tstate.get("error"),
                "started_at": tstate.get("started_at"),
            }
            
            if status in ("completed", "done") or hb.get("stage") == "complete" or tid in epub_mtimes:
                completed_tasks.append(task_info)
            elif status in ("running", "external", "active") or hb.get("label"):
                active_tasks.append(task_info)

        # 5. Completed Timeline with Accounts
        ACCOUNT_LABELS = {
            "main": "계정 1 (haijun93)",
            "account2": "계정 2 (haijun2be)",
            "account3": "계정 3 (ngaytot9)",
            "chatgpt": "ChatGPT (haijun93)",
        }

        completed_timeline = []
        for tspec in config.get("tasks", []):
            tid = tspec["id"]
            tstate = task_states.get(tid, {})
            work_dir = Path(tspec.get("work_dir", ""))
            hb_path = work_dir / "heartbeat.json"
            ev_file = work_dir / "workflow_events.jsonl"
            is_complete = tstate.get("primary_complete") or tstate.get("status") in ("completed", "finalize_wait", "done") or tid in epub_mtimes
            if not is_complete and hb_path.is_file():
                try:
                    hb = json.loads(hb_path.read_text(encoding="utf-8"))
                    if hb.get("stage") == "complete" or hb.get("completed_chunks", 0) >= hb.get("total_chunks", 1):
                        is_complete = True
                except Exception:
                    pass

            if is_complete:
                exec_account = task_account_map.get(tid) or tstate.get("account_id") or (tspec.get("preferred_accounts") or ["main"])[0]
                comp_time = epub_mtimes.get(tid) or tstate.get("completed_at") or tstate.get("started_at")
                
                # Calculate exact translation duration from workflow events
                duration_text = ""
                if ev_file.is_file():
                    try:
                        lines = ev_file.read_text(encoding="utf-8").strip().splitlines()
                        if lines:
                            first_ev = json.loads(lines[0])
                            last_ev = json.loads(lines[-1])
                            t0 = first_ev.get("timestamp")
                            t1 = last_ev.get("timestamp")
                            if t0 and t1:
                                dt0 = datetime.fromisoformat(t0)
                                dt1 = datetime.fromisoformat(t1)
                                sec = max(0, (dt1 - dt0).total_seconds())
                                hrs = int(sec // 3600)
                                mins = int((sec % 3600) // 60)
                                if hrs > 0:
                                    duration_text = f"{hrs}시간 {mins}분"
                                else:
                                    duration_text = f"{mins}분"
                    except Exception:
                        pass

                completed_timeline.append({
                    "id": tid,
                    "title": tspec.get("title", tid),
                    "account_id": exec_account,
                    "account_label": ACCOUNT_LABELS.get(exec_account, exec_account),
                    "completed_at": comp_time,
                    "duration_text": duration_text,
                })

        completed_timeline.sort(key=lambda x: str(x.get("completed_at") or ""), reverse=True)

        account_health = health.get("account_health", {})
        
        now = time.time()
        last_audit_time = latest_audit.get("started_at")
        next_audit_sec = 1800
        if last_audit_time:
            try:
                last_ts = datetime.fromisoformat(last_audit_time).timestamp()
                elapsed = now - last_ts
                next_audit_sec = max(0, int(1800 - (elapsed % 1800)))
            except Exception:
                pass
                
        total_count = len(config.get("tasks", []))
        comp_count = len(completed_timeline)
        act_count = len(active_tasks)
        rem_count = max(0, total_count - comp_count)

        return jsonify({
            "timestamp": health.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "next_audit_seconds": next_audit_sec,
            "summary": {
                "total": total_count,
                "active": act_count,
                "completed": comp_count,
                "remaining": rem_count,
            },
            "accounts": account_health,
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "completed_timeline": completed_timeline,
            "latest_audit": latest_audit,
            "audit_history": audit_history,
        })

    @app.post("/api/batch-report/run-check")
    def trigger_batch_report():
        try:
            import subprocess
            subprocess.Popen([".venv311/bin/python", "scripts/check_accounts_and_report.py"])
            return jsonify({"status": "triggered", "message": "점검이 백그라운드에서 시작되었습니다."})
        except Exception as exc:
            return jsonify({"status": "error", "error": str(exc)}), 500

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
            # 배치 번역(/api/jobs/batch)에는 이 필드가 있는데 단일 번역(이 라우트)에는 빠져
            # 있어서, 이 엔드포인트로 넣은 작업은 요청에 값을 넣어도 전부 무시되고 항상
            # ChatGPT 대체가 허용된 채로 실행되고 있었다("disable_web_fallback" 미지정 시
            # job_manager가 False로 기본 처리). 명시적으로 끄겠다고 보낸 경우가 아니면
            # 기본값을 True(대체 금지)로 둔다 - ChatGPT 사용이 사용자 요청으로 중단된 상태다.
            "disable_web_fallback": bool_form("disable_web_fallback") if "disable_web_fallback" in request.form else True,
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
                "reverse": bool_value(payload.get("reverse")),
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
        reason = f"HTTP POST from {request.remote_addr} UA={request.headers.get('User-Agent', '')[:120]}"
        try:
            return jsonify({"job": job_manager.stop_job(job_id, reason=reason)})
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
    parser.add_argument(
        "--web-account",
        choices=("main", "account2", "account3", "chatgpt"),
        default=os.getenv("AUDIOBOOK_WEB_ACCOUNT"),
        help=(
            "이 인스턴스가 쓸 Playwright 영구 브라우저 프로필 계정(main=haijun93@gmail.com Gemini, "
            "account2=haijun2be@gmail.com Gemini, account3=ngaytot9@gmail.com Gemini, chatgpt=haijun93@gmail.com ChatGPT). 지정하면 "
            "AUDIOBOOK_WEB_PROFILE_DIR을 이 계정의 고정 경로로 자동 설정해, 매번 경로 문자열을 "
            "직접 타이핑하다 계정을 혼용하는 실수를 막는다. 이미 AUDIOBOOK_WEB_PROFILE_DIR이 "
            "환경변수로 설정돼 있고 이 값과 다르면 시작을 거부한다."
        ),
    )
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_remote:
        raise SystemExit("Refusing a non-local host without --allow-remote")
    if args.web_account:
        from audiobook_maker import WEB_ACCOUNT_PROFILE_BASES

        resolved = str(WEB_ACCOUNT_PROFILE_BASES[args.web_account])
        existing = os.environ.get("AUDIOBOOK_WEB_PROFILE_DIR")
        if existing and existing != resolved:
            raise SystemExit(
                f"--web-account={args.web_account}는 프로필 경로 {resolved!r}를 뜻하지만, "
                f"환경변수 AUDIOBOOK_WEB_PROFILE_DIR이 이미 다른 값({existing!r})으로 설정돼 "
                "있습니다. 둘 중 하나만 지정하거나 서로 맞춰주세요."
            )
        os.environ["AUDIOBOOK_WEB_PROFILE_DIR"] = resolved
        print(f"web-account={args.web_account} -> AUDIOBOOK_WEB_PROFILE_DIR={resolved}", flush=True)
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
