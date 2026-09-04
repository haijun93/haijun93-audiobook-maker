#!/usr/bin/env python3
"""
30-minute ChatGPT Web Translation Forensic Profiler & Screenshot Analyzer.
Monitors the live translation process, captures screenshots during transitions,
records response latency, streaming throughput, error/notice messages, and fast-caching timings.
"""

import json
import time
from datetime import datetime
from pathlib import Path
import subprocess

CONV_ID = "0bf3f7cc-1ca3-467f-8edb-d8cfe588aca5"
ARTIFACT_DIR = Path(f"/Users/hyeokjunkong/.gemini/antigravity-ide/brain/{CONV_ID}/chatgpt_profiler")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR = ARTIFACT_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = ARTIFACT_DIR / "chatgpt_profiling_report.json"
REPORT_MD = ARTIFACT_DIR / "chatgpt_profiling_report.md"

DURATION_SEC = 1800  # 30 minutes
SAMPLE_INTERVAL_SEC = 10


def get_chatgpt_work_dirs() -> list[Path]:
    base = Path("/Users/hyeokjunkong/Desktop/소설2/_chatgpt_translate_work")
    if not base.exists():
        return []

    # Check if there is an explicit chatgpt provider running in ps
    try:
        res = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if "web-provider chatgpt" in line:
                for part in line.split():
                    if "/_chatgpt_translate_work/" in part:
                        p = Path(part)
                        if p.exists() and (p / "heartbeat.json").exists():
                            return [p]
    except Exception:
        pass

    candidates = []
    for p in base.iterdir():
        if p.is_dir() and "Well_of_Ascension" in p.name:
            hb = p / "heartbeat.json"
            if hb.exists():
                return [p]
        if p.is_dir():
            hb = p / "heartbeat.json"
            if hb.exists():
                candidates.append((hb.stat().st_mtime, p))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in candidates[:1]] if candidates else []



def take_screenshot(tag: str) -> str | None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{tag}.png"
    filepath = SCREENSHOTS_DIR / filename
    try:
        subprocess.run(["screencapture", "-x", "-m", str(filepath)], check=True, timeout=5)
        return str(filepath)
    except Exception:
        return None


def generate_markdown_report(report_data: dict) -> str:
    lines = [
        "# 📊 ChatGPT Web 30-Minute Translation & Latency Forensic Report",
        "",
        f"- **Profiler Start Time**: `{report_data.get('profiler_started_at')}`",
        f"- **Last Updated**: `{report_data.get('profiler_updated_at')}`",
        f"- **Elapsed Time**: `{report_data.get('elapsed_seconds')}s` / `{report_data.get('total_duration_seconds')}s`",
        f"- **Active Book**: `{report_data.get('active_book')}` (PID: `{report_data.get('pid')}`)",
        f"- **Total Samples Collected**: `{report_data.get('total_samples')}`",
        f"- **Screenshots Captured**: `{report_data.get('screenshots_captured')}`",
        "",
        "## ⏱️ Chunk Transitions & Performance Metrics",
        "",
        "| Section / Chunk | Duration | Chars | Avg Speed (char/s) | Completed At |",
        "|---|---|---|---|---|",
    ]

    for tr in report_data.get("completed_chunks", []):
        dur = tr.get("duration_sec", 0)
        chars = tr.get("chars", 0)
        speed = round(chars / dur, 1) if dur > 0 else 0
        lines.append(f"| `{tr.get('section')}` | {dur}s | {chars} | {speed} c/s | {tr.get('timestamp')} |")

    if not report_data.get("completed_chunks"):
        lines.append("| *(No chunks finalized in this window yet)* | - | - | - | - |")

    lines.extend([
        "",
        "## 📸 Recent Transition Screenshots",
        "",
    ])

    # List recent screenshots
    screenshots = sorted(SCREENSHOTS_DIR.glob("*.png"), reverse=True)[:6]
    if screenshots:
        for s in screenshots:
            lines.append(f"- `[{s.name}]({str(s)})`")
    else:
        lines.append("- *(No screenshots captured yet)*")

    lines.extend([
        "",
        "## 🔍 Real-Time Diagnostic State",
        "",
        "```json",
        json.dumps(report_data.get("recent_samples", [])[-1] if report_data.get("recent_samples") else {}, indent=2, ensure_ascii=False),
        "```",
    ])

    return "\n".join(lines)


def main():
    print(f"[{datetime.now().isoformat()}] Starting 30-minute ChatGPT Translation Profiler...")
    start_time = time.time()
    samples = []
    chunk_transitions = []
    last_stage = ""
    last_label = ""
    last_chars = 0
    last_section = ""
    chunk_start_time = time.time()

    # Take an initial screenshot
    take_screenshot("profiler_start")

    while time.time() - start_time < DURATION_SEC:
        now = time.time()
        elapsed = int(now - start_time)

        work_dirs = get_chatgpt_work_dirs()
        if not work_dirs:
            time.sleep(SAMPLE_INTERVAL_SEC)
            continue

        active_dir = work_dirs[0]
        hb_file = active_dir / "heartbeat.json"

        try:
            hb_data = json.loads(hb_file.read_text(encoding="utf-8"))
        except Exception:
            time.sleep(SAMPLE_INTERVAL_SEC)
            continue

        stage = str(hb_data.get("stage") or "")
        label = str(hb_data.get("label") or "")
        section = str(hb_data.get("section_prefix") or "")
        detail = str(hb_data.get("detail") or "")
        pid = int(hb_data.get("pid") or 0)

        # Parse chars and stable_polls from detail
        chars = 0
        stable_polls = 0
        empty_polls = 0
        if "chars=" in detail:
            try:
                chars = int(detail.split("chars=")[-1].split()[0])
            except Exception:
                pass
        if "stable_polls=" in detail:
            try:
                stable_polls = int(detail.split("stable_polls=")[-1].split()[0])
            except Exception:
                pass
        if "empty_polls=" in detail:
            try:
                empty_polls = int(detail.split("empty_polls=")[-1].split()[0])
            except Exception:
                pass

        # Detect transition events
        event_tag = None
        if section != last_section and section:
            event_tag = f"new_section_{section}"
            chunk_duration = now - chunk_start_time
            if last_section:
                chunk_transitions.append({
                    "section": last_section,
                    "label": last_label,
                    "duration_sec": round(chunk_duration, 1),
                    "chars": last_chars,
                    "timestamp": datetime.now().isoformat()
                })
            chunk_start_time = now
            last_section = section
        elif stage != last_stage:
            event_tag = f"stage_{stage}"
            last_stage = stage
        elif chars > 0 and last_chars == 0:
            event_tag = "first_tokens"
        elif stable_polls >= 2 and last_chars == chars and chars > 0:
            event_tag = "completion_detected"
        elif elapsed % 300 == 0:  # Periodic screenshot every 5 minutes
            event_tag = f"checkpoint_{elapsed}s"

        screenshot_path = None
        if event_tag:
            screenshot_path = take_screenshot(event_tag)

        sample = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_sec": elapsed,
            "book": active_dir.name,
            "pid": pid,
            "stage": stage,
            "label": label,
            "section": section,
            "detail": detail,
            "chars": chars,
            "stable_polls": stable_polls,
            "empty_polls": empty_polls,
            "screenshot": screenshot_path
        }
        samples.append(sample)
        last_label = label
        last_chars = chars

        # Periodically save report artifact & markdown
        report = {
            "profiler_started_at": datetime.fromtimestamp(start_time).isoformat(),
            "profiler_updated_at": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "total_duration_seconds": DURATION_SEC,
            "active_book": active_dir.name,
            "pid": pid,
            "total_samples": len(samples),
            "completed_chunks": chunk_transitions,
            "recent_samples": samples[-20:],
            "screenshots_captured": len(list(SCREENSHOTS_DIR.glob("*.png")))
        }
        REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        REPORT_MD.write_text(generate_markdown_report(report), encoding="utf-8")

        time.sleep(SAMPLE_INTERVAL_SEC)

    print(f"[{datetime.now().isoformat()}] 30-minute ChatGPT profiling completed successfully.")


if __name__ == "__main__":
    main()
