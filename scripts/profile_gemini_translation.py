#!/usr/bin/env python3
"""
30-minute Gemini Web Translation Forensic Profiler (3-Account Multi-Worker).

Monitors all 3 live Gemini workers simultaneously, captures screenshots during
key stage transitions, records response latency, streaming throughput, error/notice
messages, rate-limit incidents, and pacing behaviour.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
CONV_ID = "0bf3f7cc-1ca3-467f-8edb-d8cfe588aca5"
ARTIFACT_DIR = Path(
    f"/Users/hyeokjunkong/.gemini/antigravity-ide/brain/{CONV_ID}/gemini_profiler"
)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR = ARTIFACT_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_JSON = ARTIFACT_DIR / "gemini_profiling_report.json"
REPORT_MD   = ARTIFACT_DIR / "gemini_profiling_report.md"

DURATION_SEC        = 1800   # 30 minutes
SAMPLE_INTERVAL_SEC = 10


# ── Helpers ──────────────────────────────────────────────────────────────────

def take_screenshot(tag):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fp = SCREENSHOTS_DIR / (ts + "_" + tag[:60] + ".png")
    try:
        subprocess.run(["screencapture", "-x", "-m", str(fp)], check=True, timeout=6)
        return str(fp)
    except Exception:
        return None


def get_gemini_workers():
    workers = []
    try:
        res = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
    except Exception:
        return workers

    for line in res.stdout.splitlines():
        if "translate_epub_with_chatgpt_web_to_study_epub.py" not in line:
            continue
        if "--web-provider chatgpt" in line:
            continue
        if "--web-provider gemini" not in line:
            continue

        parts = line.split()
        pid = int(parts[1])
        work_dir = None
        inter_delay = None

        # Parse --work-dir robustly from full cmdline
        if "--work-dir" in line:
            idx = line.index("--work-dir") + len("--work-dir ")
            rest = line[idx:]
            end = rest.find(" --")
            work_dir = Path(rest[:end].strip() if end != -1 else rest.strip())

        # Parse --inter-request-delay-sec
        if "--inter-request-delay-sec" in line:
            idx = line.index("--inter-request-delay-sec") + len("--inter-request-delay-sec ")
            try:
                inter_delay = float(line[idx:].split()[0])
            except Exception:
                pass

        if work_dir and (work_dir / "heartbeat.json").exists():
            workers.append({"pid": pid, "work_dir": work_dir, "inter_delay": inter_delay})

    return workers


def read_heartbeat(work_dir):
    try:
        return json.loads((work_dir / "heartbeat.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_detail(detail):
    out = {"chars": 0, "stable_polls": 0, "empty_polls": 0}
    for key in ("chars", "stable_polls", "empty_polls"):
        if key + "=" in detail:
            try:
                out[key] = int(detail.split(key + "=")[-1].split()[0])
            except Exception:
                pass
    return out


def generate_markdown_report(report):
    lines = [
        "# Gemini Web 30-Min Translation Forensic Report (3 Accounts)",
        "",
        "- **Profiler Start Time**: `" + str(report.get("profiler_started_at")) + "`",
        "- **Last Updated**: `"         + str(report.get("profiler_updated_at")) + "`",
        "- **Elapsed Time**: `"         + str(report.get("elapsed_seconds")) + "s` / `1800s`",
        "- **Active Workers**: `"       + str(len(report.get("workers", {}))) + "`",
        "- **Total Samples**: `"        + str(report.get("total_samples")) + "`",
        "- **Screenshots**: `"          + str(report.get("screenshots_captured")) + "`",
        "",
    ]

    for wid, wd in report.get("workers", {}).items():
        lines += [
            "---",
            "## Worker: `" + wid + "` (PID: `" + str(wd.get("pid")) + "`)",
            "",
            "**Book**: " + str(wd.get("book")),
            "**Inter-request delay**: `" + str(wd.get("inter_delay")) + "s`",
            "",
        ]

        chunks = wd.get("completed_chunks", [])
        if chunks:
            lines += [
                "### Chunk Performance",
                "",
                "| Section | Duration | Chars | Speed (c/s) | Completed At |",
                "|---|---|---|---|---|",
            ]
            for c in chunks:
                dur = c.get("duration_sec", 0)
                chars = c.get("chars", 0)
                spd = round(chars / dur, 1) if dur > 0 else 0.0
                lines.append("| `" + str(c.get("section")) + "` | " +
                              str(dur) + "s | " + str(chars) + " | " +
                              str(spd) + " | " + str(c.get("timestamp")) + " |")
            lines.append("")

        stages = wd.get("stage_durations_sec", {})
        if stages:
            lines += [
                "### Stage Breakdown",
                "",
                "| Stage | Cumulative Time (s) |",
                "|---|---|",
            ]
            for st, secs in sorted(stages.items(), key=lambda x: -x[1]):
                lines.append("| `" + st + "` | " + str(secs) + "s |")
            lines.append("")

        incidents = wd.get("incidents", [])
        if incidents:
            lines += ["### Rate-Limit / Error Incidents", ""]
            for inc in incidents:
                lines.append("- `[" + inc["timestamp"] + "]` stage=`" +
                              inc["stage"] + "` detail=`" + inc["detail"] + "`")
            lines.append("")

        latest = wd.get("latest_sample", {})
        if latest:
            lines += [
                "### Latest State",
                "",
                "```json",
                json.dumps(latest, indent=2, ensure_ascii=False),
                "```",
                "",
            ]

    lines += ["---", "## Recent Screenshots", ""]
    for s in sorted(SCREENSHOTS_DIR.glob("*.png"), reverse=True)[:12]:
        lines.append("- `[" + s.name + "](" + str(s) + ")`")

    return "\n".join(lines)


def main():
    print("[" + datetime.now().isoformat() + "] Starting 30-min Gemini Profiler (3 accounts)...")
    start_time = time.time()
    total_samples = 0
    worker_states = {}

    take_screenshot("profiler_start")

    while time.time() - start_time < DURATION_SEC:
        now = time.time()
        elapsed = int(now - start_time)
        workers = get_gemini_workers()
        if not workers:
            time.sleep(SAMPLE_INTERVAL_SEC)
            continue

        event_tags = []

        for w in workers:
            wid = w["work_dir"].name
            hb = read_heartbeat(w["work_dir"])
            if not hb:
                continue

            stage   = str(hb.get("stage") or "")
            label   = str(hb.get("label") or "")
            section = str(hb.get("section_prefix") or "")
            detail  = str(hb.get("detail") or "")
            pid     = int(hb.get("pid") or w["pid"])
            parsed  = parse_detail(detail)
            chars   = parsed["chars"]

            if wid not in worker_states:
                worker_states[wid] = {
                    "pid": pid,
                    "book": wid,
                    "inter_delay": w.get("inter_delay"),
                    "last_stage": "",
                    "last_section": "",
                    "last_chars": 0,
                    "chunk_start_time": now,
                    "completed_chunks": [],
                    "stage_durations_sec": {},
                    "stage_entered_at": now,
                    "incidents": [],
                    "latest_sample": {},
                }

            ws = worker_states[wid]
            ws["pid"] = pid
            if w.get("inter_delay") is not None:
                ws["inter_delay"] = w["inter_delay"]

            # Chunk transition
            if section and section != ws["last_section"]:
                dur = round(now - ws["chunk_start_time"], 1)
                if ws["last_section"]:
                    ws["completed_chunks"].append({
                        "section": ws["last_section"],
                        "duration_sec": dur,
                        "chars": ws["last_chars"],
                        "timestamp": datetime.now().isoformat(),
                    })
                ws["chunk_start_time"] = now
                ws["last_section"] = section
                event_tags.append("g_" + wid[:25] + "_new_" + section[:20])

            # Stage transition
            if stage != ws["last_stage"]:
                prev = ws["last_stage"]
                if prev:
                    spent = round(now - ws["stage_entered_at"], 1)
                    ws["stage_durations_sec"][prev] = ws["stage_durations_sec"].get(prev, 0) + spent
                ws["stage_entered_at"] = now
                ws["last_stage"] = stage
                event_tags.append("g_" + wid[:25] + "_" + stage[:25])

                if any(k in stage for k in ("rate_limit", "error", "retry", "sleep", "blocked")):
                    ws["incidents"].append({
                        "timestamp": datetime.now().isoformat(),
                        "stage": stage,
                        "detail": detail,
                    })

            # First token
            if chars > 0 and ws["last_chars"] == 0:
                event_tags.append("g_" + wid[:25] + "_first_tokens")

            # 5-min checkpoint
            if elapsed > 0 and elapsed % 300 == 0:
                event_tags.append("checkpoint_" + str(elapsed) + "s")

            ws["latest_sample"] = {
                "timestamp": datetime.now().isoformat(),
                "elapsed_sec": elapsed,
                "pid": pid,
                "stage": stage,
                "label": label,
                "section": section,
                "detail": detail,
                "chars": chars,
                "stable_polls": parsed["stable_polls"],
                "empty_polls": parsed["empty_polls"],
            }
            ws["last_chars"] = chars
            total_samples += 1

        for tag in list(set(event_tags)):
            take_screenshot(tag)

        workers_report = {}
        for wid, ws in worker_states.items():
            workers_report[wid] = {
                "pid": ws["pid"],
                "book": ws["book"],
                "inter_delay": ws["inter_delay"],
                "completed_chunks": ws["completed_chunks"],
                "stage_durations_sec": ws["stage_durations_sec"],
                "incidents": ws["incidents"],
                "latest_sample": ws["latest_sample"],
            }

        report = {
            "profiler_started_at": datetime.fromtimestamp(start_time).isoformat(),
            "profiler_updated_at": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "total_samples": total_samples,
            "screenshots_captured": len(list(SCREENSHOTS_DIR.glob("*.png"))),
            "workers": workers_report,
        }
        REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        REPORT_MD.write_text(generate_markdown_report(report), encoding="utf-8")

        time.sleep(SAMPLE_INTERVAL_SEC)

    # Final
    print("[" + datetime.now().isoformat() + "] Gemini profiling completed.")
    print("  Workers monitored : " + str(len(worker_states)))
    print("  Total samples     : " + str(total_samples))
    print("  Screenshots       : " + str(len(list(SCREENSHOTS_DIR.glob("*.png")))))
    print("  Report MD         : " + str(REPORT_MD))

    print("\n===== BOTTLENECK ANALYSIS =====")
    for wid, ws in worker_states.items():
        print("\n[" + wid + "]")
        if ws["stage_durations_sec"]:
            top = sorted(ws["stage_durations_sec"].items(), key=lambda x: -x[1])[:5]
            print("  Top time-consuming stages:")
            for st, sec in top:
                print("    " + st + ": " + str(sec) + "s")
        if ws["incidents"]:
            print("  Rate-limit incidents: " + str(len(ws["incidents"])))
            for inc in ws["incidents"]:
                print("    [" + inc["timestamp"] + "] " + inc["stage"] + " -> " + inc["detail"])
        else:
            print("  Rate-limit incidents: 0 OK")
        if ws["completed_chunks"]:
            durs = [c["duration_sec"] for c in ws["completed_chunks"]]
            avg = sum(durs) / len(durs)
            print("  Chunk durations: min=" + str(min(durs)) + "s avg=" +
                  str(round(avg, 1)) + "s max=" + str(max(durs)) + "s")


if __name__ == "__main__":
    main()
