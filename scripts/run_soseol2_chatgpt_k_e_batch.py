#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from atomic_io import atomic_write_json
from epub_integrity import validate_epub
from make_korean_only_epubs import convert_epub, output_name
from remove_readrobe_text_from_epubs import scrub_epub
from safe_xml import safe_fromstring


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(str(Path.home()) + "/Desktop/소설2")
READROBE_SOURCE_DIR = SOURCE_DIR / "readrobe.com"
EXTRA_SOURCE_DIRS = (SOURCE_DIR / "new books from vk",)
KE_DIR = SOURCE_DIR / "[k-e]"
K_DIR = SOURCE_DIR / "[k]"
WORK_ROOT = SOURCE_DIR / "_chatgpt_translate_work"
LOG_DIR = SOURCE_DIR / "_batch_logs"
FINISHED_DIR = SOURCE_DIR / "finished"
TRANSLATE_SCRIPT = ROOT / "scripts" / "translate_epub_with_chatgpt_web_to_study_epub.py"
CLASSIFY_SCRIPT = ROOT / "scripts" / "classify_soseol2_epubs_by_category.py"
TONE_REVIEW_SCRIPT = ROOT / "scripts" / "final_epub_tone_review.py"
DIALOGUE_REVIEW_PASS2_SCRIPT = ROOT / "scripts" / "final_epub_dialogue_consistency_review.py"
FINAL_QUALITY_AUDIT_SCRIPT = ROOT / "scripts" / "final_epub_quality_audit.py"
IDLE_TONE_MAINTENANCE_SCRIPT = ROOT / "scripts" / "idle_completed_epub_tone_maintenance.py"


TITLE_MAP = {
    "1-4-You-The-Complete-Series-Caroline_Kepnes": "유 완전판",
    "1_You-Caroline_Kepnes": "유",
    "2_Hidden_Bodies-Caroline_Kepnes": "히든 바디스",
    "2_Hidden_Bodies_-_You_-_Caroline_Kepnes": "히든 바디스",
    "3_You_Love_Me_-_You_-_Caroline_Kepnes": "유 러브 미",
    "4_For_You_And_Only_You-Caroline_Kepnes": "포 유 앤드 온리 유",
    "Obedience_-_Lizzie_B_Brown-1": "오비디언스",
    "Obedience_volume_2_-_Lizzy_b_brown": "오비디언스 2",
    "Shadows_of_fury_R_NIMES": "분노의 그림자",
    "The_Teacher_-_Freida_McFadden": "더 티처",
    "The_Inmate_-_Freida_McFadden": "인메이트",
    "The_Divorce___40_Freida_McFadden__41_": "이혼",
    "The_Intruder_-_Freida_McFadden": "침입자",
    "Vicious_Reign_Monica_Kayne": "잔혹한 지배",
    "Wicked_Sanctuary_A_Dark_Irish_Mafia_Age_Gap_Romance_The_McCarthy_Family_Legacy__Jane_Henry__z-library_sk_1lib_sk_z-lib_sk": "위키드 생추어리",
    "[s] Make_It_Stick_-_Peter_C_Brown_Henry_L_Roediger_III": "메이크 잇 스틱",
    "[s] Moonwalking_With_Einstein__The_Art_and_Sci_-_Joshua_Foer": "문워킹 위드 아인슈타인",
}

PRIORITY_STEMS = {
    "Unlimited_Memory__How_to_Use_Advanced_Lear_-_Kevin_Horsley": -50,
    "harry_lorayne_the_memory_book": -49,
    "The_Rituals_-_Shantel_Tessier": -48,
    "Dominic_O_39_Brien_How_to_Develop_a_Brilliant_Memo": -47,
    "memory-craft-improve-your-memory-using-the-most-powerful-methods-from-around-the-world": -46,
    "[s] Make_It_Stick_-_Peter_C_Brown_Henry_L_Roediger_III": -30,
    "[s] Moonwalking_With_Einstein__The_Art_and_Sci_-_Joshua_Foer": -29,
    "The_Inmate_-_Freida_McFadden": -10,
    "The_Teacher_-_Freida_McFadden": 0,
}

EXCLUDE_NAME_TOKEN_GROUPS = (
    ("오늘밤", "세계", "사랑", "사라진다"),
    ("오늘밤", "세계", "사랑", "사라진다"),
    ("for", "love", "country"),
)

WEB_ACCOUNT_PAUSE_MARKERS = (
    "error_kind=account_unavailable",
    "error_kind=region_unavailable",
    "kind=account_unavailable",
    "kind=region_unavailable",
    "unusual activity",
    "suspicious activity",
    "account has been restricted",
    "비정상적인 접근",
    "비정상적 접근",
    "의심스러운 활동",
    "계정이 제한",
)

GEMINI_USAGE_LIMIT_MARKERS = (
    "error_kind=usage_limit",
    "kind=usage_limit",
    "you've reached your limit",
    "you’ve reached your limit",
    "usage limit",
    "model limit",
    "사용 한도",
    "모델 한도",
    "한도에 도달",
)

GEMINI_RATE_LIMIT_MARKERS = (
    "error_kind=rate_limit",
    "kind=rate_limit",
    "too many requests",
    "rate limit",
    "요청 빈도 제한",
    "너무 많은 요청",
)

WEB_TRANSIENT_RETRY_MARKERS = (
    "error_kind=temporary_service_error",
    "error_kind=network_error",
    "kind=temporary_service_error",
    "kind=network_error",
    "something went wrong",
    "문제가 발생했습니다",
    "인터넷 연결을 확인",
    "응답 본문이 60초 동안 시작되지 않아",
    "timeout_or_empty_response",
)

WEB_ADAPTIVE_RETRY_MARKERS = (
    "error_kind=prompt_too_long",
    "kind=prompt_too_long",
    "content can't be shown for safety reasons",
    "content can’t be shown for safety reasons",
    "번역 응답이 거절",
    "content_refusal",
    "minor_context_refusal",
    "missing_translation_ids",
    "응답에서 누락되거나 빈 번역 ID",
)


@dataclass(frozen=True)
class Job:
    source: Path
    output_title: str

    @property
    def output_stem(self) -> str:
        return re.sub(r"^\[s\]\s*", "", self.source.stem, flags=re.I)

    @property
    def output_ke(self) -> Path:
        return KE_DIR / f"[k-e] {self.output_stem}.epub"

    @property
    def output_k(self) -> Path:
        return K_DIR / output_name(self.output_ke.name)

    @property
    def work_dir(self) -> Path:
        try:
            relative_parent = self.source.parent.relative_to(SOURCE_DIR)
        except ValueError:
            relative_parent = Path()
        if str(relative_parent) not in {"", "."}:
            return WORK_ROOT / f"{safe_slug(relative_parent.as_posix())}__{safe_slug(self.source.stem)}"
        return WORK_ROOT / safe_slug(self.source.stem)


@dataclass(frozen=True)
class BookIdentity:
    title_keys: tuple[str, ...]
    author_keys: tuple[str, ...]


@dataclass(frozen=True)
class ProcessedOutput:
    path: Path
    match_key: str


class BatchInterrupted(KeyboardInterrupt):
    """Raised after SIGTERM/SIGHUP so active child work can be cleaned up."""

    def __init__(self, signum: int):
        self.signum = signum
        super().__init__(f"batch interrupted by signal {signum}")


def install_signal_handlers() -> None:
    """Turn process-termination signals into a cleanup-aware interruption."""

    def handle_signal(signum: int, _frame: object) -> None:
        raise BatchInterrupted(signum)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGHUP, handle_signal)


def terminate_process_group(process: subprocess.Popen[object], grace_seconds: float = 10.0) -> None:
    """Stop an active translation and every browser helper it started."""

    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        process.terminate()
    try:
        process.wait(timeout=max(0.0, grace_seconds))
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        process.kill()
    process.wait()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate /소설2 top-level English EPUBs into [k-e] and [k] EPUBs.")
    parser.add_argument("--only", nargs="*", default=[], help="Run only files whose name contains one of these strings.")
    parser.add_argument("--force", action="store_true", help="Rebuild even when verified outputs already exist.")
    parser.add_argument("--no-korean-only", action="store_true", help="Do not build [k] EPUBs.")
    parser.add_argument("--dedupe-only", action="store_true", help="Move source EPUBs that already have verified [k-e] and [k] outputs, then exit.")
    parser.add_argument("--cooldown-seconds", type=int, default=900)
    parser.add_argument("--max-chars-per-chunk", type=int, default=6000)
    parser.add_argument("--chunks-per-conversation", type=int, default=10)
    parser.add_argument("--inter-request-delay-sec", type=float, default=4.0)
    parser.add_argument("--request-timeout-sec", type=int, default=1200)
    parser.add_argument(
        "--web-provider",
        choices=("chatgpt", "gemini"),
        default="gemini",
        help="Translation web provider (default: gemini; chatgpt is legacy opt-in only).",
    )
    parser.add_argument("--web-max-attempts", "--chatgpt-web-max-attempts", dest="web_max_attempts", type=int, default=5)
    parser.add_argument("--web-visible", "--chatgpt-web-visible", dest="web_visible", action="store_true")
    parser.add_argument(
        "--skip-idle-tone-maintenance",
        action="store_true",
        help="웹 번역 서비스 재시도 대기 중 완료 EPUB 통합 검수/보정을 건너뜁니다.",
    )
    parser.add_argument(
        "--idle-tone-maintenance-max-files",
        type=int,
        default=40,
        help="한 번의 한도 쿨다운 동안 최종 통합 검수를 수행할 최대 EPUB 수",
    )
    parser.add_argument(
        "--watch-new-seconds",
        type=int,
        default=300,
        help="When all discovered jobs are verified, wait this many seconds and scan for newly added EPUBs. Use 0 to exit.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9가-힣._-]+", "_", text).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug[:120] or "book"


def readable_title_from_stem(stem: str) -> str:
    if stem in TITLE_MAP:
        return TITLE_MAP[stem]
    text = re.sub(r"z-library.*$", "", stem, flags=re.I)
    text = re.sub(r"[_-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or stem


def read_epub_metadata_title_author(path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            opf_name = next((name for name in archive.namelist() if name.lower().endswith(".opf")), None)
            if not opf_name:
                return "", ""
            root = safe_fromstring(archive.read(opf_name))
    except Exception:
        return "", ""
    ns = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "opf": "http://www.idpf.org/2007/opf",
    }
    title_node = root.find(".//dc:title", ns)
    creator_node = root.find(".//dc:creator", ns)
    title = "".join(title_node.itertext()).strip() if title_node is not None else ""
    creator = "".join(creator_node.itertext()).strip() if creator_node is not None else ""
    return title, creator


def has_hangul(text: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in text)


def original_title_from_stem(stem: str) -> str:
    text = re.sub(r"^\[s\]\s*", "", stem, flags=re.I)
    text = re.sub(r"z-library.*$", "", text, flags=re.I)
    text = text.replace("__40_", " ").replace("__41_", " ")
    text = text.replace("_40_", " ").replace("_41_", " ")
    text = re.sub(r"___+", " ", text)
    text = re.sub(r"[_-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or stem


def output_title_for_source(path: Path) -> str:
    meta_title, _meta_author = read_epub_metadata_title_author(path)
    if meta_title and not has_hangul(meta_title):
        return re.sub(r"\s+", " ", meta_title).strip()
    return original_title_from_stem(path.stem)


def strip_leading_source_index(text: str) -> str:
    return re.sub(r"^\s*\d{1,3}(?:[-_]\d{1,3})?[-_.\s]+", "", text).strip()


def normalize_match_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("&", " and ")
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"(?i)\b(?:epub|retail|z[- ]?library|z[- ]?lib|my fiction books|readrobe com)\b", " ", text)
    text = re.sub(r"(?i)\b39\b", " ", text)
    text = re.sub(r"'s\b", "s", text, flags=re.I)
    text = re.sub(r"[_./+:-]+", " ", text)
    text = re.sub(r"[^0-9A-Za-z가-힣]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def without_trailing_duplicate_number(key: str) -> str:
    tokens = key.split()
    if len(tokens) > 1 and tokens[-1].isdigit() and int(tokens[-1]) < 100:
        return " ".join(tokens[:-1])
    return key


def add_key(keys: list[str], text: str) -> None:
    key = without_trailing_duplicate_number(normalize_match_text(strip_leading_source_index(text)))
    if len(key) >= 2 and key not in keys:
        keys.append(key)


def source_identity(path: Path) -> BookIdentity:
    title_keys: list[str] = []
    author_keys: list[str] = []
    meta_title, meta_author = read_epub_metadata_title_author(path)
    add_key(title_keys, meta_title)
    add_key(author_keys, meta_author)

    raw = path.stem
    stem = strip_leading_source_index(raw)
    add_key(title_keys, stem)
    add_key(title_keys, readable_title_from_stem(raw))

    human = re.sub(r"[_]+", " ", stem)
    for marker in ("_-_", " - ", "_by_", " by "):
        if marker in stem:
            before, after = stem.split(marker, 1)
            add_key(title_keys, before)
            add_key(author_keys, after)
        if marker in human:
            before, after = human.split(marker, 1)
            add_key(title_keys, before)
            add_key(author_keys, after)

    by_match = re.search(r"(?i)\bby\b", human)
    if by_match:
        add_key(title_keys, human[: by_match.start()])
        add_key(author_keys, human[by_match.end() :])

    return BookIdentity(title_keys=tuple(title_keys), author_keys=tuple(author_keys))


def processed_outputs(root: Path) -> list[ProcessedOutput]:
    if not root.exists():
        return []
    outputs: list[ProcessedOutput] = []
    for path in sorted(root.rglob("*.epub")):
        stem = path.stem
        stem = re.sub(r"^\[k-e\]\s*", "", stem, flags=re.I)
        stem = re.sub(r"^\[k\]\s*", "", stem, flags=re.I)
        key = without_trailing_duplicate_number(normalize_match_text(stem))
        if key:
            outputs.append(ProcessedOutput(path=path, match_key=key))
    return outputs


def contains_phrase(haystack: str, needle: str) -> bool:
    return haystack == needle or haystack.startswith(needle + " ") or haystack.endswith(" " + needle) or f" {needle} " in f" {haystack} "


def token_subset(needle: str, haystack: str) -> bool:
    needle_tokens = [token for token in needle.split() if len(token) > 1]
    haystack_tokens = set(haystack.split())
    return bool(needle_tokens) and all(token in haystack_tokens for token in needle_tokens)


def same_book(identity: BookIdentity, output: ProcessedOutput) -> bool:
    for title_key in identity.title_keys:
        title_tokens = title_key.split()
        title_match = contains_phrase(output.match_key, title_key) or token_subset(title_key, output.match_key)
        if not title_match:
            continue
        if len(title_tokens) <= 1:
            return any(contains_phrase(output.match_key, author_key) or token_subset(author_key, output.match_key) for author_key in identity.author_keys)
        return True
    return False


def find_processed_output(identity: BookIdentity, outputs: list[ProcessedOutput]) -> ProcessedOutput | None:
    for output in outputs:
        if same_book(identity, output):
            return output
    return None


def is_excluded_source(path: Path) -> bool:
    normalized_name = unicodedata.normalize("NFC", path.name).lower()
    raw_name = path.name.lower()
    return any(
        all(token.lower() in normalized_name or token.lower() in raw_name for token in tokens)
        for tokens in EXCLUDE_NAME_TOKEN_GROUPS
    )


def discover_jobs_in(source_dir: Path, patterns: list[str]) -> list[Job]:
    lowered = [pattern.lower() for pattern in patterns]
    jobs: list[Job] = []
    def sort_key(path: Path) -> tuple[int, int, str]:
        return (PRIORITY_STEMS.get(path.stem, 100), path.stat().st_size, path.name.lower())

    if not source_dir.exists():
        return jobs
    for source in sorted(source_dir.glob("*.epub"), key=sort_key):
        haystack = source.name.lower()
        explicit_match = bool(lowered) and any(pattern in haystack for pattern in lowered)
        priority_override = PRIORITY_STEMS.get(source.stem, 100) < 0
        if source.name.startswith("[k"):
            continue
        if source.name.startswith("[s]") and not (explicit_match or priority_override):
            continue
        if is_excluded_source(source):
            continue
        if lowered and not explicit_match:
            continue
        jobs.append(Job(source=source, output_title=output_title_for_source(source)))
    return jobs


def discover_jobs(patterns: list[str]) -> list[Job]:
    primary_jobs = discover_jobs_in(SOURCE_DIR, patterns)
    priority_primary = [job for job in primary_jobs if PRIORITY_STEMS.get(job.source.stem, 100) < 0]
    regular_primary = [job for job in primary_jobs if PRIORITY_STEMS.get(job.source.stem, 100) >= 0]
    readrobe_jobs = discover_jobs_in(READROBE_SOURCE_DIR, patterns)
    if priority_primary or readrobe_jobs:
        return priority_primary + readrobe_jobs + regular_primary
    if regular_primary:
        return regular_primary
    jobs: list[Job] = []
    for source_dir in EXTRA_SOURCE_DIRS:
        jobs.extend(discover_jobs_in(source_dir, patterns))
    return jobs


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line, flush=True)
    with (LOG_DIR / "soseol2_k_e_batch.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def acquire_batch_lock():
    lock_path = LOG_DIR / "soseol2_k_e_batch.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.close()
        raise SystemExit("소설 번역 배치가 이미 실행 중입니다.") from exc
    lock_handle.write(f"pid={os.getpid()} started={datetime.now().isoformat(timespec='seconds')}\n")
    lock_handle.flush()
    return lock_handle


def translation_retry_cooldown(args: argparse.Namespace, attempt: int, text: str) -> int:
    lowered = text.lower()
    if any(marker in lowered for marker in WEB_ACCOUNT_PAUSE_MARKERS):
        return min(21600, 3600 * max(1, min(attempt, 6)))
    if any(marker in lowered for marker in GEMINI_USAGE_LIMIT_MARKERS):
        return max(args.cooldown_seconds, min(18000, 1800 * max(1, min(attempt, 10))))
    if any(marker in lowered for marker in GEMINI_RATE_LIMIT_MARKERS):
        return min(1800, 300 * max(1, min(attempt, 6)))
    if "error_kind=session_expired" in lowered or "kind=session_expired" in lowered:
        return min(3600, 600 * max(1, min(attempt, 6)))
    if any(marker in lowered for marker in WEB_TRANSIENT_RETRY_MARKERS):
        return min(120, 15 * (2 ** max(0, min(attempt - 1, 3))))
    if any(marker in lowered for marker in WEB_ADAPTIVE_RETRY_MARKERS):
        return 5
    return 120


def should_use_retry_idle_time(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in WEB_ACCOUNT_PAUSE_MARKERS
        + GEMINI_USAGE_LIMIT_MARKERS
        + GEMINI_RATE_LIMIT_MARKERS
        + WEB_TRANSIENT_RETRY_MARKERS
    )


def run_idle_tone_maintenance(args: argparse.Namespace, cooldown: int, detail: str) -> float:
    if args.skip_idle_tone_maintenance or not IDLE_TONE_MAINTENANCE_SCRIPT.exists():
        return 0.0
    started = time.monotonic()
    time_budget = max(60, max(0, cooldown - 30))
    command = [
        sys.executable,
        str(IDLE_TONE_MAINTENANCE_SCRIPT),
        "--source-dir",
        str(SOURCE_DIR),
        "--time-budget-sec",
        str(time_budget),
        "--max-files",
        str(max(0, args.idle_tone_maintenance_max_files)),
    ]
    log(f"IDLE_TONE_MAINTENANCE start time_budget={time_budget}s detail={detail[:240]}")
    try:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=time_budget + 90)
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        log(f"IDLE_TONE_MAINTENANCE timeout elapsed={elapsed:.1f}s")
        return elapsed
    elapsed = time.monotonic() - started
    output = completed.stdout.strip()
    if completed.returncode != 0:
        log(f"IDLE_TONE_MAINTENANCE failed rc={completed.returncode} elapsed={elapsed:.1f}s output={output[:1000]}")
        return elapsed
    summary = output[:1400]
    try:
        data = json.loads(output)
        summary = (
            f"processed={data.get('processed')} candidates_due={data.get('candidates_due')} "
            f"report={data.get('report')}"
        )
    except Exception:
        pass
    log(f"IDLE_TONE_MAINTENANCE done elapsed={elapsed:.1f}s {summary}")
    return elapsed


def text_files(archive: zipfile.ZipFile) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in archive.namelist():
        lower = name.lower()
        if lower.endswith((".xhtml", ".html", ".htm", ".opf", ".ncx")):
            result[name] = archive.read(name).decode("utf-8", "replace")
    return result


def count_class(text: str, class_name: str) -> int:
    count = 0
    for match in re.finditer(r"class=[\"']([^\"']+)[\"']", text):
        if class_name in match.group(1).split():
            count += 1
    return count


def verify_ke(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing output"
    integrity = validate_epub(path, require_nav=True, require_ncx=True, require_cover=True)
    if not integrity.valid:
        return False, "integrity failed: " + "; ".join(integrity.issues[:5])
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if names[:1] != ["mimetype"]:
                return False, "mimetype is not first"
            texts = text_files(archive)
            for name, text in texts.items():
                if name.lower().endswith((".xhtml", ".html", ".htm", ".opf", ".ncx")):
                    safe_fromstring(text.encode("utf-8"))
            nav_items = sum(text.count("<li") for name, text in texts.items() if name.lower().endswith("nav.xhtml"))
            ncx_points = sum(text.count("<navPoint") for name, text in texts.items() if name.lower().endswith(".ncx"))
            missing_markers = sum(text.count("[번역 누락]") for text in texts.values())
            ko_blocks = sum(count_class(text, "ko") for text in texts.values())
            en_blocks = sum(count_class(text, "en") for text in texts.values())
            pair_blocks = sum(count_class(text, "pair") for text in texts.values())
    except Exception as exc:
        return False, str(exc)
    if missing_markers:
        return False, f"translation missing markers: {missing_markers}"
    if ko_blocks <= 0 or en_blocks <= 0 or ko_blocks != en_blocks:
        return False, f"pair count mismatch: ko={ko_blocks} en={en_blocks}"
    if pair_blocks <= 0:
        return False, "no pair blocks"
    if nav_items <= 0 or ncx_points <= 0:
        return False, f"toc missing: nav={nav_items} ncx={ncx_points}"
    return True, f"ok size={path.stat().st_size} pairs={pair_blocks} ko/en={ko_blocks}/{en_blocks} toc={nav_items}/{ncx_points}"


def verify_k(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing output"
    integrity = validate_epub(path, require_nav=True, require_ncx=True, require_cover=True)
    if not integrity.valid:
        return False, "integrity failed: " + "; ".join(integrity.issues[:5])
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if names[:1] != ["mimetype"]:
                return False, "mimetype is not first"
            texts = text_files(archive)
            for name, text in texts.items():
                if name.lower().endswith((".xhtml", ".html", ".htm", ".opf", ".ncx")):
                    safe_fromstring(text.encode("utf-8"))
            nav_items = sum(text.count("<li") for name, text in texts.items() if name.lower().endswith("nav.xhtml"))
            ncx_points = sum(text.count("<navPoint") for name, text in texts.items() if name.lower().endswith(".ncx"))
            missing_markers = sum(text.count("[번역 누락]") for text in texts.values())
            en_blocks = sum(count_class(text, "en") for text in texts.values())
            pair_blocks = sum(count_class(text, "pair") for text in texts.values())
    except Exception as exc:
        return False, str(exc)
    if missing_markers:
        return False, f"translation missing markers: {missing_markers}"
    if en_blocks or pair_blocks:
        return False, f"english study markup remains: en={en_blocks} pair={pair_blocks}"
    if nav_items <= 0 or ncx_points <= 0:
        return False, f"toc missing: nav={nav_items} ncx={ncx_points}"
    return True, f"ok size={path.stat().st_size} toc={nav_items}/{ncx_points}"


def run_translation(job: Job, args: argparse.Namespace, attempt: int) -> int:
    heartbeat = job.work_dir / "heartbeat.json"
    log_path = LOG_DIR / f"{safe_slug(job.source.stem)}.attempt-{attempt:03d}.log"
    cmd = [
        sys.executable,
        str(TRANSLATE_SCRIPT),
        "--input-epub",
        str(job.source),
        "--output-epub",
        str(job.output_ke),
        "--work-dir",
        str(job.work_dir),
        "--book-title-ko",
        job.output_title,
        "--max-chars-per-chunk",
        str(args.max_chars_per_chunk),
        "--request-timeout-sec",
        str(args.request_timeout_sec),
        "--web-max-attempts",
        str(args.web_max_attempts),
        "--chunks-per-conversation",
        str(args.chunks_per_conversation),
        "--inter-request-delay-sec",
        str(max(0.0, args.inter_request_delay_sec)),
        "--heartbeat-file",
        str(heartbeat),
    ]
    if args.web_provider:
        cmd.extend(["--web-provider", args.web_provider])
    if args.web_visible:
        cmd.append("--web-visible")
    provider_label = args.web_provider or "auto"
    log(f"START {job.source.name} -> {job.output_ke.name} attempt={attempt} provider={provider_label}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("\n\n" + "=" * 80 + "\n")
        fh.write(f"{datetime.now().isoformat(timespec='seconds')} {' '.join(cmd)}\n")
        fh.flush()
        process = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return process.wait()
        except BaseException:
            terminate_process_group(process)
            raise


def run_final_tone_review(job: Job, epub_path: Path, kind: str) -> None:
    if not TONE_REVIEW_SCRIPT.exists() or not epub_path.exists():
        return
    out_dir = job.work_dir / "final_tone_reviews"
    latest_json = out_dir / f"{safe_slug(epub_path.stem)}.tone_review_latest.json"
    if latest_json.exists() and latest_json.stat().st_mtime >= epub_path.stat().st_mtime:
        try:
            data = json.loads(latest_json.read_text(encoding="utf-8"))
            log(f"TONE_REVIEW skip current {kind} {epub_path.name}: status={data.get('status')} report={data.get('report_path')}")
        except Exception:
            log(f"TONE_REVIEW skip current {kind} {epub_path.name}: {latest_json}")
        return

    command = [
        sys.executable,
        str(TONE_REVIEW_SCRIPT),
        str(epub_path),
        "--out-dir",
        str(out_dir),
        "--kind",
        kind,
    ]
    guide = job.work_dir / "relationship_guide.txt"
    if guide.exists():
        command.extend(["--relationship-guide", str(guide)])
    try:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        log(f"TONE_REVIEW timeout {kind} {epub_path.name}")
        return
    output = completed.stdout.strip()
    if completed.returncode != 0:
        log(f"TONE_REVIEW failed {kind} {epub_path.name}: rc={completed.returncode}; {output}")
        return
    status = ""
    report = ""
    try:
        data = json.loads(output)
        status = str(data.get("status", ""))
        report = str(data.get("report", ""))
    except Exception:
        report = output
    log(f"TONE_REVIEW done {kind} {epub_path.name}: status={status or 'unknown'} report={report}")


def scrub_generated_epub(epub_path: Path, kind: str) -> None:
    result = scrub_epub(epub_path)
    status = str(result.get("status") or "")
    if status.startswith("error:"):
        raise RuntimeError(f"WATERMARK_CLEANUP failed {kind} {epub_path.name}: {status}")
    replacements = int(result.get("replacements") or 0)
    if replacements:
        log(
            f"WATERMARK_CLEANUP done {kind} {epub_path.name}: "
            f"replacements={replacements} files={result.get('files_changed')}"
        )


def run_final_dialogue_review_pass2(job: Job, epub_path: Path, kind: str) -> None:
    if not DIALOGUE_REVIEW_PASS2_SCRIPT.exists() or not epub_path.exists():
        return
    out_dir = job.work_dir / "final_dialogue_reviews_pass2"
    latest_json = out_dir / f"{safe_slug(epub_path.stem)}.dialogue_pass2_latest.json"
    if latest_json.exists() and latest_json.stat().st_mtime >= epub_path.stat().st_mtime:
        try:
            data = json.loads(latest_json.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        log(
            f"DIALOGUE_REVIEW_PASS2 skip current {kind} {epub_path.name}: "
            f"status={data.get('status')} report={data.get('report_path')}"
        )
        return
    command = [
        sys.executable,
        str(DIALOGUE_REVIEW_PASS2_SCRIPT),
        str(epub_path),
        "--out-dir",
        str(out_dir),
        "--kind",
        kind,
    ]
    guide = job.work_dir / "relationship_guide.txt"
    if guide.exists():
        command.extend(["--relationship-guide", str(guide)])
    try:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        log(f"DIALOGUE_REVIEW_PASS2 timeout {kind} {epub_path.name}")
        return
    output = completed.stdout.strip()
    if completed.returncode != 0:
        log(f"DIALOGUE_REVIEW_PASS2 failed {kind} {epub_path.name}: rc={completed.returncode}; {output[:1000]}")
        return
    try:
        data = json.loads(output)
        status = str(data.get("status") or "unknown")
        report = str(data.get("report") or "")
    except Exception:
        status = "unknown"
        report = output
    log(f"DIALOGUE_REVIEW_PASS2 done {kind} {epub_path.name}: status={status} report={report}")


def run_final_quality_audit(job: Job, epub_path: Path, kind: str) -> tuple[bool, dict]:
    if not FINAL_QUALITY_AUDIT_SCRIPT.exists() or not epub_path.exists():
        return False, {"status": "failed", "issues": ["quality audit script or EPUB is missing"]}
    out_dir = job.work_dir / "final_quality_audits"
    command = [
        sys.executable,
        str(FINAL_QUALITY_AUDIT_SCRIPT),
        str(epub_path),
        "--kind",
        kind,
        "--out-dir",
        str(out_dir),
        "--work-dir",
        str(job.work_dir),
    ]
    if job.source.exists():
        command.extend(["--source-epub", str(job.source)])
    try:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        log(f"QUALITY_AUDIT timeout {kind} {epub_path.name}")
        return False, {"status": "failed", "issues": ["quality audit timeout"]}
    output = completed.stdout.strip()
    if completed.returncode != 0:
        log(f"QUALITY_AUDIT failed {kind} {epub_path.name}: rc={completed.returncode}; {output[:1000]}")
        return False, {"status": "failed", "issues": [output[:1000]]}
    status = ""
    report = ""
    issue_count = 0
    data: dict = {}
    try:
        data = json.loads(output)
        status = str(data.get("status", ""))
        report = str(data.get("report", ""))
        issue_count = len(data.get("issues") or [])
    except Exception:
        report = output
    log(f"QUALITY_AUDIT done {kind} {epub_path.name}: status={status or 'unknown'} issues={issue_count} report={report}")
    return status == "pass", data


def quarantine_failed_quality_output(job: Job, epub_path: Path, kind: str, audit: dict) -> None:
    if not epub_path.exists():
        return
    backup_dir = job.work_dir / "quality_gate_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = backup_dir / f"{safe_slug(epub_path.stem)}.{kind}.failed_{stamp}.epub"
    suffix = 2
    while destination.exists():
        destination = backup_dir / f"{safe_slug(epub_path.stem)}.{kind}.failed_{stamp}_{suffix}.epub"
        suffix += 1
    epub_path.replace(destination)
    issues = "; ".join(str(item) for item in audit.get("issues", []))
    log(f"QUALITY_GATE hold {kind} {epub_path.name}: backup={destination}; issues={issues[:1200]}")


def pending_jobs(jobs: list[Job], args: argparse.Namespace) -> list[tuple[Job, str]]:
    pending: list[tuple[Job, str]] = []
    for job in jobs:
        ok_ke, reason_ke = verify_ke(job.output_ke)
        if not ok_ke:
            pending.append((job, f"[k-e] {reason_ke}"))
            continue
        if not args.no_korean_only:
            ok_k, reason_k = verify_k(job.output_k)
            if not ok_k:
                pending.append((job, f"[k] {reason_k}"))
    return pending


def ensure_korean_only(job: Job, overwrite: bool) -> None:
    ok, reason = verify_k(job.output_k)
    if ok and not overwrite:
        log(f"SKIP [k] verified {job.output_k.name}: {reason}")
        return
    K_DIR.mkdir(parents=True, exist_ok=True)
    stats = convert_epub(job.output_ke, job.output_k, overwrite=True)
    ok, reason = verify_k(job.output_k)
    if not ok:
        raise RuntimeError(f"[k] verify failed {job.output_k.name}: {reason}")
    log(
        f"DONE [k] {job.output_k.name}: {reason}; "
        f"korean_paragraphs={stats['pairs']} en_removed={stats['en_removed']} inline_removed={stats['inline_removed']}"
    )


def unique_finished_path(source: Path) -> Path:
    FINISHED_DIR.mkdir(parents=True, exist_ok=True)
    destination = FINISHED_DIR / source.name
    if not destination.exists():
        return destination
    if destination.stat().st_size == source.stat().st_size:
        return destination
    for index in range(1, 10000):
        candidate = FINISHED_DIR / f"{source.stem}__{index}{source.suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find unique finished path for {source.name}")


def move_completed_source(job: Job, args: argparse.Namespace) -> None:
    if not job.source.exists():
        return
    ok_ke, reason_ke = verify_ke(job.output_ke)
    ok_k, reason_k = (True, "skipped by --no-korean-only")
    if not args.no_korean_only:
        ok_k, reason_k = verify_k(job.output_k)
    if not (ok_ke and ok_k):
        log(f"KEEP source not fully verified {job.source.name}: [k-e] {reason_ke}; [k] {reason_k}")
        return
    destination = unique_finished_path(job.source)
    if destination.exists() and destination.stat().st_size == job.source.stat().st_size:
        job.source.unlink()
        log(f"MOVED source duplicate already in finished {job.source.name} -> {destination}")
        return
    job.source.rename(destination)
    log(f"MOVED source to finished {job.source.name} -> {destination}")


def classify_completed_outputs(job: Job) -> None:
    if not CLASSIFY_SCRIPT.exists():
        return
    files = [str(path) for path in (job.output_k, job.output_ke) if path.exists()]
    if not files:
        return
    command = [sys.executable, str(CLASSIFY_SCRIPT), "--quiet", "--files", *files]
    try:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        log(f"CLASSIFY timeout {job.source.name}")
        return
    if completed.returncode == 0:
        log(f"CLASSIFY outputs {job.source.name}: {completed.stdout.strip()}")
    else:
        log(f"CLASSIFY failed {job.source.name}: rc={completed.returncode}; {completed.stdout.strip()}")


def prune_already_completed_sources(jobs: list[Job], args: argparse.Namespace) -> list[Job]:
    if args.force:
        return jobs
    ke_outputs = processed_outputs(KE_DIR)
    k_outputs = processed_outputs(K_DIR)
    remaining: list[Job] = []
    moved = 0
    for job in jobs:
        identity = source_identity(job.source)
        match_ke = find_processed_output(identity, ke_outputs)
        match_k = find_processed_output(identity, k_outputs)
        if not (match_ke and match_k):
            remaining.append(job)
            continue
        ok_ke, reason_ke = verify_ke(match_ke.path)
        ok_k, reason_k = verify_k(match_k.path)
        if not (ok_ke and ok_k):
            log(
                f"KEEP possible duplicate not verified {job.source.name}: "
                f"[k-e] {match_ke.path.name if match_ke else '-'} {reason_ke}; "
                f"[k] {match_k.path.name if match_k else '-'} {reason_k}"
            )
            remaining.append(job)
            continue
        destination = unique_finished_path(job.source)
        if args.dry_run:
            log(
                f"DRY-RUN DUPLICATE source already completed {job.source.name} -> {destination}; "
                f"[k-e]={match_ke.path.name}; [k]={match_k.path.name}"
            )
        elif destination.exists() and destination.stat().st_size == job.source.stat().st_size:
            job.source.unlink()
            log(
                f"DUPLICATE source removed; already completed and already in finished {job.source.name}; "
                f"[k-e]={match_ke.path.name}; [k]={match_k.path.name}"
            )
        else:
            job.source.rename(destination)
            log(
                f"DUPLICATE source moved to finished {job.source.name} -> {destination}; "
                f"[k-e]={match_ke.path.name}; [k]={match_k.path.name}"
            )
        moved += 1
    if moved:
        log(f"DUPLICATE scan moved/skipped sources={moved}; remaining_sources={len(remaining)}")
    return remaining


def main() -> int:
    args = parse_args()
    install_signal_handlers()
    KE_DIR.mkdir(parents=True, exist_ok=True)
    K_DIR.mkdir(parents=True, exist_ok=True)
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _batch_lock = acquire_batch_lock()

    attempts: dict[str, int] = {}
    cycle = 0
    while True:
        cycle += 1
        jobs = discover_jobs(args.only)
        if not jobs:
            if args.watch_new_seconds <= 0 or args.force:
                log(f"ALL SOSEOL2 JOBS VERIFIED. No source EPUBs matched: {args.only}. Shutdown not requested.")
                return 0
            log(f"NO SOURCE EPUBS MATCHED. Waiting {args.watch_new_seconds}s for newly added source EPUBs.")
            time.sleep(args.watch_new_seconds)
            continue
        jobs = prune_already_completed_sources(jobs, args)
        if args.dedupe_only:
            log(f"DEDUPE-ONLY complete. remaining_sources={len(jobs)}")
            return 0
        if not jobs:
            if args.watch_new_seconds <= 0 or args.force:
                log("ALL SOSEOL2 JOBS VERIFIED. All discovered source EPUBs were already completed. Shutdown not requested.")
                return 0
            log(f"ALL DISCOVERED SOURCE EPUBS WERE ALREADY COMPLETED. Waiting {args.watch_new_seconds}s for newly added source EPUBs.")
            time.sleep(args.watch_new_seconds)
            continue
        atomic_write_json(
            LOG_DIR / "soseol2_jobs_manifest.json",
            [
                {
                    "source": str(job.source),
                    "output_title": job.output_title,
                    "output_ke": str(job.output_ke),
                    "output_k": str(job.output_k),
                }
                for job in jobs
            ],
        )

        if args.dry_run:
            for index, job in enumerate(jobs, start=1):
                print(f"{index:02d}. {job.source.name} -> {job.output_ke.name} / {job.output_k.name} ({job.output_title})")
            return 0

        pending_before = pending_jobs(jobs, args)
        log(f"SCAN cycle={cycle} sources={len(jobs)} pending={len(pending_before)}")
        for index, job in enumerate(jobs, start=1):
            log(f"QUEUE {index}/{len(jobs)} {job.source.name}")
            ok, reason = verify_ke(job.output_ke)
            rebuilt_ke = False
            job_blocked = False
            if ok and not args.force:
                log(f"SKIP [k-e] verified {job.output_ke.name}: {reason}")
                scrub_generated_epub(job.output_ke, "k-e")
                run_final_tone_review(job, job.output_ke, "k-e")
                run_final_dialogue_review_pass2(job, job.output_ke, "k-e")
                quality_ok, quality_data = run_final_quality_audit(job, job.output_ke, "k-e")
                if not quality_ok:
                    quarantine_failed_quality_output(job, job.output_ke, "k-e", quality_data)
                    job_blocked = True
            else:
                log(f"PENDING [k-e] {job.output_ke.name}: {reason}")
                while True:
                    attempts[job.source.name] = attempts.get(job.source.name, 0) + 1
                    rc = run_translation(job, args, attempts[job.source.name])
                    ok, reason = verify_ke(job.output_ke)
                    if ok:
                        log(f"DONE [k-e] {job.output_ke.name}: {reason}")
                        scrub_generated_epub(job.output_ke, "k-e")
                        run_final_tone_review(job, job.output_ke, "k-e")
                        run_final_dialogue_review_pass2(job, job.output_ke, "k-e")
                        quality_ok, quality_data = run_final_quality_audit(job, job.output_ke, "k-e")
                        if not quality_ok:
                            quarantine_failed_quality_output(job, job.output_ke, "k-e", quality_data)
                            job_blocked = True
                        rebuilt_ke = True
                        break
                    heartbeat = job.work_dir / "heartbeat.json"
                    heartbeat_summary = ""
                    if heartbeat.exists():
                        try:
                            data = json.loads(heartbeat.read_text(encoding="utf-8"))
                            heartbeat_summary = f" heartbeat={data.get('stage')} {data.get('label')} {data.get('attempt')} {data.get('detail')}"
                        except Exception as exc:
                            heartbeat_summary = f" heartbeat_read_error={exc}"
                    retry_detail = f"{reason} {heartbeat_summary}"
                    cooldown = translation_retry_cooldown(
                        args,
                        attempts[job.source.name],
                        retry_detail,
                    )
                    log(
                        f"RETRY_LATER [k-e] {job.output_ke.name}: rc={rc}; verify={reason};"
                        f"{heartbeat_summary}; cooldown={cooldown}s"
                    )
                    elapsed = 0.0
                    if should_use_retry_idle_time(retry_detail):
                        elapsed = run_idle_tone_maintenance(args, cooldown, retry_detail)
                    remaining_sleep = max(0.0, cooldown - elapsed)
                    if remaining_sleep:
                        time.sleep(remaining_sleep)
            if job_blocked:
                log(f"QUALITY_GATE deferred source; source remains in queue: {job.source.name}")
                continue
            if not args.no_korean_only:
                ensure_korean_only(job, overwrite=args.force or rebuilt_ke)
                scrub_generated_epub(job.output_k, "k")
                run_final_tone_review(job, job.output_k, "k")
                run_final_dialogue_review_pass2(job, job.output_k, "k")
                quality_ok, quality_data = run_final_quality_audit(job, job.output_k, "k")
                if not quality_ok:
                    quarantine_failed_quality_output(job, job.output_k, "k", quality_data)
                    log(f"QUALITY_GATE deferred source after [k] audit: {job.source.name}")
                    continue
            move_completed_source(job, args)
            classify_completed_outputs(job)

        refreshed_jobs = discover_jobs(args.only)
        pending_after = pending_jobs(refreshed_jobs, args)
        if pending_after:
            log(f"RESCAN found pending/new jobs={len(pending_after)}; continuing.")
            continue
        if args.watch_new_seconds <= 0 or args.force:
            log("ALL SOSEOL2 JOBS VERIFIED. Shutdown not requested.")
            return 0
        log(f"ALL SOSEOL2 JOBS VERIFIED. Waiting {args.watch_new_seconds}s for newly added source EPUBs.")
        time.sleep(args.watch_new_seconds)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BatchInterrupted as exc:
        log(f"STOP batch interrupted by signal {exc.signum}; active translation was cleaned up.")
        raise SystemExit(128 + exc.signum) from None
    except KeyboardInterrupt:
        log("STOP batch interrupted by keyboard; active translation was cleaned up.")
        raise SystemExit(130) from None
