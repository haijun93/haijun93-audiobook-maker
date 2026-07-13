#!/usr/bin/env python3
"""Use web-provider retry idle time to review and safely refine completed EPUBs."""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from final_epub_literary_review import review_epub_literary_style
from final_epub_dialogue_consistency_review import review_dialogue_consistency
from final_epub_quality_audit import audit_epub, write_reports
from final_epub_tone_review import review_epub_tone


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path("/Users/hyeokjunkong/Desktop/소설2")
REFINE_DARK_NOTES = ROOT / "scripts" / "refine_dark_notes_honorifics.py"
REFINE_CORRUPT = ROOT / "scripts" / "refine_corrupt_honorifics.py"


@dataclass(frozen=True)
class WorkGuide:
    work_dir: Path
    guide: Path | None
    key: str
    expected_names: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    epub: Path
    kind: str
    work_dir: Path
    guide: Path | None


@dataclass
class MaintenanceRecord:
    epub: str
    kind: str
    work_dir: str
    guide: str
    before_status: str = ""
    after_status: str = ""
    review_report: str = ""
    dialogue_pass2_status: str = ""
    dialogue_pass2_report: str = ""
    literary_status: str = ""
    literary_report: str = ""
    quality_status: str = ""
    quality_report: str = ""
    quality_issues: list[str] | None = None
    quality_warnings: list[str] | None = None
    action: str = "reviewed"
    details: str = ""


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"^\[k(?:-e)?\]\s*", "", text)
    text = re.sub(r"\.epub$", "", text)
    text = re.sub(r"(?i)\b(?:readrobe|com|epub|zlibrary|zlib|retail)\b", " ", text)
    text = re.sub(r"[^0-9a-z가-힣]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_key(text: str) -> str:
    return normalize(text).replace(" ", "")


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", text).strip("_")
    return re.sub(r"_+", "_", slug)[:120] or "epub"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def work_guides(source_dir: Path) -> list[WorkGuide]:
    work_root = source_dir / "_chatgpt_translate_work"
    guides: list[WorkGuide] = []
    if not work_root.exists():
        return guides
    for manifest_path in sorted(work_root.rglob("manifest.json")):
        work_dir = manifest_path.parent
        manifest = load_json(manifest_path)
        guide_path = work_dir / "relationship_guide.txt"
        guide = guide_path if guide_path.exists() else None
        expected: list[str] = []
        output_epub = manifest.get("output_epub")
        if output_epub:
            output_name = Path(str(output_epub)).name
            expected.append(output_name)
            if output_name.startswith("[k-e]"):
                expected.append(output_name.replace("[k-e]", "[k]", 1))
        title = str(manifest.get("book_title") or manifest.get("ko_book_title") or "")
        key_parts = [work_dir.name, title, " ".join(expected)]
        guides.append(
            WorkGuide(
                work_dir=work_dir,
                guide=guide,
                key=compact_key(" ".join(key_parts)),
                expected_names=tuple(dict.fromkeys(expected)),
            )
        )
    return guides


def match_guide(epub: Path, guides: list[WorkGuide]) -> WorkGuide | None:
    name = epub.name
    for guide in guides:
        if name in guide.expected_names:
            return guide
    key = compact_key(epub.stem)
    if not key:
        return None
    best: tuple[int, WorkGuide] | None = None
    for guide in guides:
        score = 0
        if key and key in guide.key:
            score = len(key)
        elif guide.key and guide.key in key:
            score = len(guide.key)
        else:
            tokens = [token for token in normalize(epub.stem).split() if len(token) >= 4]
            guide_tokens = set(normalize(guide.key).split())
            overlap = sum(1 for token in tokens if token in guide_tokens or token in guide.key)
            if overlap >= max(2, min(4, len(tokens))):
                score = overlap
        if score and (best is None or score > best[0]):
            best = (score, guide)
    return best[1] if best else None


def discover_candidates(source_dir: Path) -> list[Candidate]:
    guides = work_guides(source_dir)
    candidates: dict[Path, Candidate] = {}
    for root, kind in ((source_dir / "[k-e]", "k-e"), (source_dir / "[k]", "k")):
        if not root.exists():
            continue
        for epub in sorted(root.rglob("*.epub")):
            guide = match_guide(epub, guides)
            if not guide:
                fallback_dir = source_dir / "_completed_epub_reviews" / safe_slug(epub.stem)
                candidates[epub.resolve()] = Candidate(
                    epub=epub,
                    kind=kind,
                    work_dir=fallback_dir,
                    guide=None,
                )
                continue
            candidates[epub.resolve()] = Candidate(
                epub=epub,
                kind=kind,
                work_dir=guide.work_dir,
                guide=guide.guide,
            )
    return list(candidates.values())


def latest_review_json(candidate: Candidate) -> Path:
    out_dir = candidate.work_dir / "final_tone_reviews"
    return out_dir / f"{safe_slug(candidate.epub.stem)}.tone_review_latest.json"


def latest_literary_json(candidate: Candidate) -> Path:
    out_dir = candidate.work_dir / "final_literary_reviews"
    return out_dir / f"{safe_slug(candidate.epub.stem)}.literary_review_latest.json"


def latest_dialogue_pass2_json(candidate: Candidate) -> Path:
    out_dir = candidate.work_dir / "final_dialogue_reviews_pass2"
    return out_dir / f"{safe_slug(candidate.epub.stem)}.dialogue_pass2_latest.json"


def latest_quality_json(candidate: Candidate) -> Path:
    out_dir = candidate.work_dir / "final_quality_audits"
    return out_dir / f"{safe_slug(candidate.epub.stem)}.quality_audit_latest.json"


def current_or_fallback(path: Path, directory: Path, kind: str, marker: str) -> Path:
    if path.exists():
        return path
    if not directory.exists():
        return path
    prefix = "k-e_" if kind == "k-e" else "k_"
    matches = [item for item in directory.glob(f"*.{marker}_latest.json") if item.name.lower().startswith(prefix)]
    return max(matches, key=lambda item: item.stat().st_mtime) if matches else path


def needs_review(candidate: Candidate, force: bool) -> bool:
    if force:
        return True
    checks = (
        (latest_review_json(candidate), candidate.work_dir / "final_tone_reviews", "tone_review"),
        (
            latest_dialogue_pass2_json(candidate),
            candidate.work_dir / "final_dialogue_reviews_pass2",
            "dialogue_pass2",
        ),
        (latest_literary_json(candidate), candidate.work_dir / "final_literary_reviews", "literary_review"),
        (latest_quality_json(candidate), candidate.work_dir / "final_quality_audits", "quality_audit"),
    )
    for latest, directory, marker in checks:
        latest = current_or_fallback(latest, directory, candidate.kind, marker)
        if not latest.exists() or latest.stat().st_mtime < candidate.epub.stat().st_mtime:
            return True
    quality_data = load_json(
        current_or_fallback(
            latest_quality_json(candidate), candidate.work_dir / "final_quality_audits", candidate.kind, "quality_audit"
        )
    )
    if int(quality_data.get("audit_version") or 0) < 4:
        return True
    tone_data = load_json(current_or_fallback(latest_review_json(candidate), candidate.work_dir / "final_tone_reviews", candidate.kind, "tone_review"))
    return tone_data.get("status") == "needs_attention" and known_safe_refiner_applies(candidate)


def known_safe_refiner_applies(candidate: Candidate) -> bool:
    return dark_notes_refiner_applies(candidate) or corrupt_refiner_applies(candidate)


def dark_notes_refiner_applies(candidate: Candidate) -> bool:
    marker = normalize(candidate.epub.stem)
    return "dark notes" in marker and "pam godwin" in marker and REFINE_DARK_NOTES.exists()


def corrupt_refiner_applies(candidate: Candidate) -> bool:
    marker = normalize(candidate.epub.stem)
    has_title = "corrupt" in marker
    has_author = "penelope" in marker or "douglas" in marker
    return has_title and has_author and REFINE_CORRUPT.exists()


def parse_total_replacements(output: str) -> int:
    match = re.search(r"total_replacements=(\d+)", output)
    return int(match.group(1)) if match else 0


def parse_corrupt_replacements(output: str) -> int:
    try:
        payload = json.loads(output)
    except Exception:
        return 0
    if not isinstance(payload, list):
        return 0
    total = 0
    for item in payload:
        hits = item.get("replacement_hits", {}) if isinstance(item, dict) else {}
        if isinstance(hits, dict):
            total += sum(int(value or 0) for value in hits.values())
    return total


def run_known_safe_refiner(candidate: Candidate) -> tuple[bool, str]:
    if dark_notes_refiner_applies(candidate):
        dry_cmd = [sys.executable, str(REFINE_DARK_NOTES), "--epub", str(candidate.epub), "--dry-run"]
        dry = subprocess.run(dry_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
        if dry.returncode != 0:
            return False, f"dark_notes_refiner_dry_run_failed: {dry.stdout.strip()[:500]}"
        total = parse_total_replacements(dry.stdout)
        if total <= 0:
            return False, "dark_notes_refiner_no_safe_replacements"
        cmd = [sys.executable, str(REFINE_DARK_NOTES), "--epub", str(candidate.epub)]
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
        if completed.returncode != 0:
            return False, f"dark_notes_refiner_failed: {completed.stdout.strip()[:500]}"
        return True, f"dark_notes_refiner_applied replacements={total}"

    if corrupt_refiner_applies(candidate):
        dry_cmd = [sys.executable, str(REFINE_CORRUPT), "--dry-run", str(candidate.epub)]
        dry = subprocess.run(dry_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
        if dry.returncode != 0:
            return False, f"corrupt_refiner_dry_run_failed: {dry.stdout.strip()[:500]}"
        total = parse_corrupt_replacements(dry.stdout)
        if total <= 0:
            return False, "corrupt_refiner_no_safe_replacements"
        cmd = [sys.executable, str(REFINE_CORRUPT), str(candidate.epub)]
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
        if completed.returncode != 0:
            return False, f"corrupt_refiner_failed: {completed.stdout.strip()[:500]}"
        return True, f"corrupt_refiner_applied replacements={total}"

    return False, ""


def maintain_candidate(candidate: Candidate, *, force: bool) -> MaintenanceRecord:
    record = MaintenanceRecord(
        epub=str(candidate.epub),
        kind=candidate.kind,
        work_dir=str(candidate.work_dir),
        guide=str(candidate.guide or ""),
    )
    out_dir = candidate.work_dir / "final_tone_reviews"
    review = review_epub_tone(candidate.epub, relationship_guide=candidate.guide, out_dir=out_dir, kind=candidate.kind)
    record.before_status = review.status
    record.after_status = review.status
    record.review_report = review.report_path

    if review.status == "needs_attention":
        refined, detail = run_known_safe_refiner(candidate)
        record.details = detail
        if refined:
            review = review_epub_tone(candidate.epub, relationship_guide=candidate.guide, out_dir=out_dir, kind=candidate.kind)
            record.action = "reviewed_refined_reviewed"
            record.after_status = review.status
            record.review_report = review.report_path
        elif detail:
            record.action = "reviewed_no_safe_refiner_change"
    elif force:
        # A force run still counts as a full final check, even when no edits are needed.
        record.action = "reviewed_force"

    dialogue_pass2 = review_dialogue_consistency(
        candidate.epub,
        relationship_guide=candidate.guide,
        out_dir=candidate.work_dir / "final_dialogue_reviews_pass2",
        kind=candidate.kind,
    )
    record.dialogue_pass2_status = dialogue_pass2.status
    record.dialogue_pass2_report = dialogue_pass2.report_path

    literary = review_epub_literary_style(
        candidate.epub,
        out_dir=candidate.work_dir / "final_literary_reviews",
        kind=candidate.kind,
    )
    record.literary_status = literary.status
    record.literary_report = literary.report_path

    quality = audit_epub(
        candidate.epub,
        kind=candidate.kind,
        work_dir=candidate.work_dir,
    )
    quality = write_reports(quality, candidate.work_dir / "final_quality_audits")
    record.quality_status = quality.status
    record.quality_report = quality.report_path
    record.quality_issues = quality.issues
    record.quality_warnings = quality.warnings
    return record


def write_run_report(source_dir: Path, records: list[MaintenanceRecord]) -> tuple[Path, Path]:
    log_dir = source_dir / "_batch_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = log_dir / f"idle_completed_epub_review_{stamp}.json"
    md_path = log_dir / f"idle_completed_epub_review_{stamp}.md"
    payload = {"created_at": datetime.now().isoformat(timespec="seconds"), "records": [asdict(record) for record in records]}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Idle Completed EPUB Review", ""]
    for record in records:
        lines.append(
            f"- `{Path(record.epub).name}` {record.kind}: {record.before_status} -> {record.after_status}, "
            f"{record.action}, tone1=`{record.after_status}`, tone2=`{record.dialogue_pass2_status}`, "
            f"literary=`{record.literary_status}`, "
            f"quality=`{record.quality_status}`"
        )
        lines.append(
            f"  - reports: tone1=`{record.review_report}`, tone2=`{record.dialogue_pass2_report}`, "
            f"literary=`{record.literary_report}`, "
            f"quality=`{record.quality_report}`"
        )
        if record.quality_issues:
            lines.append(f"  - quality issues: {'; '.join(record.quality_issues)}")
        if record.quality_warnings:
            lines.append(f"  - quality warnings: {'; '.join(record.quality_warnings)}")
        if record.details:
            lines.append(f"  - {record.details}")
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return md_path, json_path


def write_pending_queue(source_dir: Path, candidates: list[Candidate]) -> tuple[Path, Path, int]:
    queue: list[dict] = []
    for candidate in candidates:
        tone_path = current_or_fallback(
            latest_review_json(candidate), candidate.work_dir / "final_tone_reviews", candidate.kind, "tone_review"
        )
        literary_path = current_or_fallback(
            latest_literary_json(candidate),
            candidate.work_dir / "final_literary_reviews",
            candidate.kind,
            "literary_review",
        )
        dialogue_pass2_path = current_or_fallback(
            latest_dialogue_pass2_json(candidate),
            candidate.work_dir / "final_dialogue_reviews_pass2",
            candidate.kind,
            "dialogue_pass2",
        )
        quality_path = current_or_fallback(
            latest_quality_json(candidate),
            candidate.work_dir / "final_quality_audits",
            candidate.kind,
            "quality_audit",
        )
        tone = load_json(tone_path)
        literary = load_json(literary_path)
        dialogue_pass2 = load_json(dialogue_pass2_path)
        quality = load_json(quality_path)
        statuses = {
            "tone": str(tone.get("status") or "not_reviewed"),
            "dialogue_pass2": str(dialogue_pass2.get("status") or "not_reviewed"),
            "literary": str(literary.get("status") or "not_reviewed"),
            "quality": str(quality.get("status") or "not_reviewed"),
        }
        if statuses == {
            "tone": "checked",
            "dialogue_pass2": "checked",
            "literary": "checked",
            "quality": "pass",
        }:
            continue
        queue.append(
            {
                "epub": str(candidate.epub),
                "kind": candidate.kind,
                "work_dir": str(candidate.work_dir),
                "statuses": statuses,
                "quality_issues": quality.get("issues") or [],
                "quality_warnings": quality.get("warnings") or [],
                "tone_samples": tone.get("samples") or [],
                "literary_samples": literary.get("samples") or [],
                "reports": {
                    "tone": str(tone_path) if tone_path.exists() else "",
                    "dialogue_pass2": str(dialogue_pass2_path) if dialogue_pass2_path.exists() else "",
                    "literary": str(literary_path) if literary_path.exists() else "",
                    "quality": str(quality_path) if quality_path.exists() else "",
                },
            }
        )

    log_dir = source_dir / "_batch_logs"
    json_path = log_dir / "completed_epub_review_queue_latest.json"
    md_path = log_dir / "completed_epub_review_queue_latest.md"
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total_completed_epubs": len(candidates),
        "pending_count": len(queue),
        "queue": queue,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Completed EPUB Review Queue",
        "",
        f"- updated: `{payload['updated_at']}`",
        f"- completed EPUBs: `{len(candidates)}`",
        f"- pending or not yet reviewed: `{len(queue)}`",
        "",
    ]
    for item in queue:
        statuses = item["statuses"]
        lines.append(
            f"- `{Path(item['epub']).name}` ({item['kind']}): "
            f"tone1=`{statuses['tone']}`, tone2=`{statuses['dialogue_pass2']}`, "
            f"literary=`{statuses['literary']}`, quality=`{statuses['quality']}`"
        )
        if item["quality_issues"]:
            lines.append(f"  - issues: {'; '.join(item['quality_issues'])}")
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return md_path, json_path, len(queue)


def write_live_progress(
    source_dir: Path,
    *,
    due: int,
    processed: int,
    current: Candidate | None,
    last_record: MaintenanceRecord | None,
) -> None:
    log_dir = source_dir / "_batch_logs"
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "candidates_due_at_start": due,
        "processed": processed,
        "remaining_estimate": max(0, due - processed),
        "current_epub": str(current.epub) if current else "",
        "last_record": asdict(last_record) if last_record else None,
    }
    (log_dir / "idle_completed_epub_review_progress.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (log_dir / "idle_completed_epub_review_progress.log").open("a", encoding="utf-8") as handle:
        status = ""
        if last_record:
            status = (
                f" tone1={last_record.after_status} tone2={last_record.dialogue_pass2_status} "
                f"literary={last_record.literary_status} "
                f"quality={last_record.quality_status}"
            )
        handle.write(
            f"[{payload['updated_at']}] processed={processed}/{due} "
            f"current={payload['current_epub']}{status}\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Review/refine completed EPUBs during web-provider retry idle time.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--max-files", type=int, default=40)
    parser.add_argument("--time-budget-sec", type=int, default=600)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source_dir = args.source_dir.expanduser()
    lock_path = source_dir / "_batch_logs" / "idle_completed_epub_review.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(json.dumps({"status": "already_running", "processed": 0, "candidates_due": 0}, ensure_ascii=False))
        return 0
    started = time.monotonic()
    records: list[MaintenanceRecord] = []
    all_candidates = discover_candidates(source_dir)
    candidates = [candidate for candidate in all_candidates if needs_review(candidate, args.force)]
    write_live_progress(source_dir, due=len(candidates), processed=0, current=candidates[0] if candidates else None, last_record=None)

    selected = candidates[: max(0, args.max_files)]
    for index, candidate in enumerate(selected, start=1):
        if records and time.monotonic() - started > max(30, args.time_budget_sec):
            break
        try:
            records.append(maintain_candidate(candidate, force=args.force))
        except Exception as exc:  # noqa: BLE001 - log and keep the cooldown maintenance moving.
            records.append(
                MaintenanceRecord(
                    epub=str(candidate.epub),
                    kind=candidate.kind,
                    work_dir=str(candidate.work_dir),
                    guide=str(candidate.guide or ""),
                    action="error",
                    details=str(exc),
                )
            )
        next_candidate = selected[index] if index < len(selected) else None
        write_live_progress(
            source_dir,
            due=len(candidates),
            processed=len(records),
            current=next_candidate,
            last_record=records[-1],
        )

    report = {}
    if records:
        md_path, json_path = write_run_report(source_dir, records)
        report = {"md": str(md_path), "json": str(json_path)}
    queue_md, queue_json, pending_count = write_pending_queue(source_dir, all_candidates)

    print(
        json.dumps(
            {
                "candidates_due": len(candidates),
                "processed": len(records),
                "report": report,
                "queue": {"md": str(queue_md), "json": str(queue_json), "pending_count": pending_count},
                "records": [asdict(record) for record in records],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
