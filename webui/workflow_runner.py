#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webui.book_organizer import (  # noqa: E402
    archive_duplicate_source,
    build_finished_registry,
    build_html_collection_registry,
    build_library_registry,
    extract_metadata_from_epub,
    find_finished_match,
    get_existing_korean_books,
)
from webui.platform import discover_ebook_convert  # noqa: E402
from webui.storage import atomic_write_json  # noqa: E402
from webui.workflow_diagnostics import (  # noqa: E402
    WorkflowDiagnostics,
    diagnose_failure,
    load_workflow_diagnostics,
)

SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export_pdf_to_kindle_epub import build_epub as build_reflow_epub  # noqa: E402
from build_xteink_dedicated_editions import build_xteink_book_pair  # noqa: E402
from make_english_study_epubs import convert_epub as convert_epub_to_english_study  # noqa: E402
from make_korean_only_epubs import convert_epub, output_name  # noqa: E402
from translate_epub_with_chatgpt_web_to_study_epub import all_blocks, extract_sections  # noqa: E402
from translation_quality_checks import is_english_word_sample  # noqa: E402


TRANSLATION_EXTENSIONS = {".epub", ".pdf", ".mobi"}
AUDIO_EXTENSIONS = {".txt", ".epub", ".docx", ".pdf", ".mobi"}

# 배치 중 한 권이 실패해도 곧장 다음 권으로 넘어가지 않고, 같은 work-dir을 재사용해
# 이미 완료된 청크는 건너뛰고 실패했던 지점부터 이어서 재시도한다. Gemini 웹 서비스의
# 일시적 장애(temporary_service_error, timeout 등)는 몇 분 내로 회복되는 경우가 많으므로
# 매 재시도 사이에 지수 백오프로 대기한다.
BOOK_RETRY_ATTEMPTS = 3
BOOK_RETRY_BASE_DELAY_SEC = 60
BATCH_PAUSE_KINDS = {
    "usage_limit",
    "rate_limit",
    "account_unavailable",
    "session_expired",
    "region_unavailable",
    "profile_in_use",
}
BATCH_TRANSIENT_KINDS = {
    "temporary_service_error",
    "network_error",
    "timeout_or_empty_response",
    "prompt_interaction_failed",
}

# 이미 번역이 끝난 원서 EPUB을 모아 두는 폴더. 배치 번역 시 이 목록의 제목/작가와
# 대조해 중복 번역을 피한다.
FINISHED_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2/finished")

# [k] 컬렉션 전체를 요약한 정적 카탈로그 페이지. finished 폴더에는 아직 옮겨지지 않았지만
# 이미 [k]에 번역이 완료돼 있는 작품도 이 목록과 대조해 중복 번역을 피한다. 이 스냅샷은
# 생성 시점 이후 서재에 추가된 책은 반영하지 못하므로, K_LIBRARY_ROOT 실시간 스캔과 함께
# 사용한다(스냅샷은 빠른 1차 필터, 실시간 스캔이 최종 안전망).
K_COLLECTION_HTML = Path("/Users/hyeokjunkong/Desktop/소설2/k_collection_blog.html")

# [k] 서재 폴더 자체. 배치 시작 시마다 이 폴더를 직접(재귀적으로) 스캔해 정적 스냅샷보다
# 최신인 중복(예: 배치 도중 서재로 분류·이동된 책)까지 잡아낸다.
K_LIBRARY_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2/[k]")
LIBRARY_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def readable_stem(path: Path) -> str:
    stem = unicodedata.normalize("NFKC", path.stem)
    stem = re.sub(r"^\[(?:e|s|k|k-e)\]\s*", "", stem, flags=re.IGNORECASE)
    # Piracy-site watermarks baked into the downloaded filename - strip them so they never
    # leak into generated output filenames or per-book work directory names.
    stem = re.sub(r"(?i)[_\s]*oceanofpdf[._\s-]*com[_\s]*", " ", stem)
    stem = re.sub(r"(?i)[_\s]*readrobe[._\s-]*com[_\s]*", " ", stem)
    # "@my_fiction_books"-style tags (including truncated/typo'd variants) some sources
    # append after the author name.
    stem = re.sub(r"(?i)[@_]*my[_\s]*fiction[_\s]*\)?books?", " ", stem)
    stem = re.sub(r"(?i)[\s_]*@[a-z_]*\s*$", "", stem)
    # Machine-generated "Title_-_Author" separator -> plain space, matching the "Title
    # Author" (no dash) convention already used across the library.
    stem = re.sub(r"_-_", " ", stem)
    stem = re.sub(r"[_-]+", " ", stem)
    # Stray parentheses around an author name ("(Poppy Z. Brite)") aren't part of the
    # "Title Author" convention; drop the punctuation but keep whatever text was inside.
    stem = stem.replace("(", " ").replace(")", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = re.sub(r"[\\/:*?\"<>|]+", "", stem)
    # Placeholder author some sources fall back to when the real one is missing.
    stem = re.sub(r"(?i)\bUnknown\s*$", "", stem).strip()
    stem = _collapse_repeated_author(stem)
    return stem[:180] or "Book"


def _collapse_repeated_author(stem: str) -> str:
    """Drop an earlier duplicate of the trailing author name.

    Some sources garble the filename into "Title Author Author" or "Lastname Firstname
    ... Firstname Lastname" (the same name spelled out twice, sometimes with different
    casing/spacing). If the last 2-3 words also appear earlier in the stem, keep only
    the final occurrence.
    """
    words = stem.split(" ")
    for tail_len in (3, 2):
        if len(words) < tail_len * 2:
            continue
        tail = [w.lower() for w in words[-tail_len:]]
        body = words[:-tail_len]
        for i in range(len(body) - tail_len + 1):
            if [w.lower() for w in body[i : i + tail_len]] == tail:
                return " ".join(body[:i] + body[i + tail_len :] + words[-tail_len:])
    return stem


def find_existing_item_work_dir(work_root: Path, source: Path) -> Path | None:
    """이전 배치 실행에서 이 책을 이미 번역한 작업 디렉터리가 있으면 찾아 재사용한다.

    run_batch()의 book별 작업 폴더명(item_work)은 그 실행 시점에 source_files()가 매긴
    순번을 접두사로 쓴다(예: "0016_...", "0019_..."). --priority-substrings를 바꾸거나
    폴더 안 파일 구성이 달라지면 같은 책이 다음 실행에서 다른 순번을 받아 완전히 새 폴더로
    떨어지는데, 그러면 이미 끝난 수백~수천 청크 분량의 번역 캐시를 통째로 못 찾고 처음부터
    다시 번역하게 된다(수 시간 낭비 + 예전에 통과했던 것과 같은 종류의 오류가 재발할 위험).
    manifest.json에 기록된 input_epub 절대경로가 지금 처리하려는 source와 정확히 일치하는
    기존 폴더가 있으면 그걸 재사용해 이런 낭비를 막는다.
    """
    if not work_root.exists():
        return None
    try:
        resolved_source = source.resolve()
    except OSError:
        return None
    for candidate in sorted(work_root.iterdir()):
        if not candidate.is_dir():
            continue
        manifest_path = candidate / "translation" / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        recorded_input = manifest.get("input_epub")
        if not recorded_input:
            continue
        try:
            if Path(recorded_input).resolve() == resolved_source:
                return candidate
        except OSError:
            continue
    return None


def beat(path: Path, *, stage: str, label: str = "", detail: str = "") -> None:
    atomic_write_json(
        path,
        {
            "iso_time": utc_now(),
            "stage": stage,
            "label": label,
            "detail": detail,
        },
    )


def write_batch_status(
    path: Path | None,
    *,
    total: int,
    targets: list[str],
    current: str | None,
    current_index: int | None,
    completed: list[dict[str, str]],
    status: str = "running",
    diagnosis: dict[str, object] | None = None,
) -> None:
    if path is None:
        return
    atomic_write_json(
        path,
        {
            "iso_time": utc_now(),
            "total": total,
            "targets": targets,
            "current": current,
            "current_index": current_index,
            "completed": completed,
            "completed_count": len(completed),
            "status": status,
            "diagnosis": diagnosis,
        },
    )


def run_child(command: list[str]) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True, stdin=subprocess.DEVNULL)


def prepare_epub(source: Path, work_dir: Path) -> Path:
    suffix = source.suffix.lower()
    if suffix == ".epub":
        return source
    converted = work_dir / "converted_source.epub"
    converted.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".pdf":
        print(f"Extracting reflowable English EPUB from PDF: {source.name}", flush=True)
        build_reflow_epub(source, converted, language="en", page_label="Page")
        return converted
    if suffix == ".mobi":
        ebook_convert = discover_ebook_convert()
        if not ebook_convert or not Path(ebook_convert).is_file():
            raise RuntimeError(
                "MOBI conversion requires Calibre. Install Calibre or set EBOOK_CONVERT_PATH."
            )
        run_child([ebook_convert, str(source), str(converted)])
        if not converted.is_file() or converted.stat().st_size == 0:
            raise RuntimeError("Calibre did not create an EPUB from the MOBI source")
        return converted
    raise RuntimeError(f"Unsupported book format: {suffix}")


def translation_command(
    *,
    source_epub: Path,
    bilingual_output: Path,
    work_dir: Path,
    heartbeat_file: Path,
    args: argparse.Namespace,
    provider_fallback_state_dir: Path | None = None,
    study_output: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "translate_epub_with_chatgpt_web_to_study_epub.py"),
        "--input-epub",
        str(source_epub),
        "--output-epub",
        str(bilingual_output),
        "--work-dir",
        str(work_dir),
        "--heartbeat-file",
        str(heartbeat_file),
        "--web-provider",
        args.translation_provider,
        "--max-chars-per-chunk",
        str(args.max_chars),
        "--web-max-attempts",
        str(args.max_attempts),
        "--chunks-per-conversation",
        str(args.chunks_per_conversation),
        "--inter-request-delay-sec",
        str(args.inter_request_delay),
        "--request-timeout-sec",
        str(args.request_timeout),
    ]
    if args.visible:
        command.append("--web-visible")
    if getattr(args, "disable_overnight_web_fallback", False):
        command.append("--disable-overnight-web-fallback")
    if provider_fallback_state_dir is not None:
        command.extend(["--provider-fallback-state-dir", str(provider_fallback_state_dir)])
    if study_output is not None:
        command.extend(["--study-output-epub", str(study_output)])
    return command


def child_workflow_diagnostics(item_work: Path, task: str) -> dict[str, object]:
    child_dir = item_work / ("translation" if task == "batch_translation" else "audio")
    return load_workflow_diagnostics(child_dir)


def batch_retry_policy(
    error: BaseException,
    *,
    book_attempt: int,
    child_diagnostics: dict[str, object] | None = None,
) -> tuple[bool, int, dict[str, object]]:
    child_diagnostics = child_diagnostics or {}
    child_diagnosis = child_diagnostics.get("diagnosis")
    diagnosis = (
        dict(child_diagnosis)
        if isinstance(child_diagnosis, dict) and child_diagnosis.get("kind")
        else diagnose_failure(error).to_dict()
    )
    kind = str(diagnosis.get("kind") or "unknown_error")
    if kind in BATCH_PAUSE_KINDS:
        return False, 0, diagnosis
    if kind in BATCH_TRANSIENT_KINDS:
        retry = book_attempt < BOOK_RETRY_ATTEMPTS
        delay = min(900, BOOK_RETRY_BASE_DELAY_SEC * (2 ** (book_attempt - 1))) if retry else 0
        return retry, delay, diagnosis
    if kind in {"child_process_failed", "unknown_error"}:
        retry = book_attempt < min(2, BOOK_RETRY_ATTEMPTS)
        return retry, BOOK_RETRY_BASE_DELAY_SEC if retry else 0, diagnosis
    return False, 0, diagnosis


def normalize_output_root(root: Path) -> Path:
    """Ensure root never ends with an edition folder like [k], [k-e], [study], [e-s], [e]."""
    cur = root.resolve()
    while cur.name in {"[k]", "[k-e]", "[study]", "[e-s]", "[e]", "xteink"}:
        cur = cur.parent
    return cur


def translate_one(
    source: Path,
    *,
    output_root: Path,
    work_dir: Path,
    heartbeat_file: Path,
    args: argparse.Namespace,
    split_output_dirs: bool,
    provider_fallback_state_dir: Path | None = None,
) -> list[dict[str, str]]:
    output_root = normalize_output_root(output_root)
    title = readable_stem(source)
    english_dir = output_root / "[e]" if split_output_dirs else output_root
    bilingual_dir = output_root / "[k-e]" if split_output_dirs else output_root
    korean_dir = output_root / "[k]" if split_output_dirs else output_root
    study_dir = output_root / "[study]" if split_output_dirs else output_root
    english_study_dir = output_root / "[e-s]" if split_output_dirs else output_root
    english_dir.mkdir(parents=True, exist_ok=True)
    bilingual_dir.mkdir(parents=True, exist_ok=True)
    korean_dir.mkdir(parents=True, exist_ok=True)
    english_output = english_dir / f"[e] {title}.epub"
    bilingual_output = bilingual_dir / f"[k-e] {title}.epub"
    korean_output = korean_dir / output_name(bilingual_output.name)
    study_output = study_dir / f"[study] {title}.epub"
    english_study_output = english_study_dir / f"[e-s] {title}.epub"
    wants_bilingual = args.translation_output in {"both", "bilingual"}
    wants_korean = args.translation_output in {"both", "korean"}
    # [study](토익 학습노트 포함 대조본)는 [k-e]와 같은 번역 캐시에서 파생되는 산출물이라,
    # 대조본 자체를 만들지 않는 "korean" 전용 모드에서는 함께 스킵한다.
    wants_study = wants_bilingual
    # [e-s](영어 원문 + 학습노트, 한글 번역 없음)는 [study] 결과물에서 그 자리에서 파생되는
    # 산출물이라 [study]와 항상 함께 만들거나 함께 건너뛴다.
    wants_english_study = wants_study
    # [e](정제된 영어 원문)는 번역 모드와 무관하게 항상 나란히 보관한다 - e/k/k-e/study
    # 네 산출물을 한 세트로 유지하기 위함.
    wants_english = True
    if wants_study:
        study_dir.mkdir(parents=True, exist_ok=True)
    if wants_english_study:
        english_study_dir.mkdir(parents=True, exist_ok=True)
    desired_outputs = [
        path
        for path, wanted in (
            (english_output, wants_english),
            (bilingual_output, wants_bilingual),
            (korean_output, wants_korean),
            (study_output, wants_study),
            (english_study_output, wants_english_study),
        )
        if wanted
    ]

    if not args.overwrite and all(path.is_file() and path.stat().st_size > 0 for path in desired_outputs):
        print(f"SKIP existing translation outputs: {title}", flush=True)
    else:
        translated = False
        needs_translation = (
            args.overwrite or not bilingual_output.is_file() or (wants_study and not study_output.is_file())
        )
        if needs_translation or (wants_english and not english_output.is_file()):
            source_epub = prepare_epub(source, work_dir / "source")
            if wants_english and (args.overwrite or not english_output.is_file()):
                shutil.copy2(source_epub, english_output)
        if needs_translation:
            beat(heartbeat_file, stage="translation_start", label=title, detail=source.name)
            run_child(
                translation_command(
                    source_epub=source_epub,
                    bilingual_output=bilingual_output,
                    work_dir=work_dir / "translation",
                    heartbeat_file=heartbeat_file,
                    args=args,
                    provider_fallback_state_dir=provider_fallback_state_dir,
                    study_output=study_output if wants_study else None,
                )
            )
            translated = True
        if wants_korean and (args.overwrite or translated or not korean_output.is_file()):
            beat(heartbeat_file, stage="korean_epub_start", label=title)
            convert_epub(bilingual_output, korean_output, True)
    if (
            wants_english_study
            and (args.overwrite or translated or not english_study_output.is_file())
            and study_output.is_file()
        ):
            beat(heartbeat_file, stage="english_study_epub_start", label=title)
            convert_epub_to_english_study(study_output, english_study_output, True)

    # The dedicated Xteink editions are derived locally from the completed
    # [study]/[e-s] pair.  Previously they were produced only by a separate
    # full-library batch, which allowed an updated book to retain stale
    # [xteink]/[study_x] and [xteink]/[e-s_x] copies.  Limit this hook to the
    # canonical library root so unit-test/custom output roots are untouched.
    if (
        split_output_dirs
        and output_root == LIBRARY_ROOT
        and wants_study
        and study_output.is_file()
        and english_study_output.is_file()
    ):
        beat(heartbeat_file, stage="xteink_epub_start", label=title)
        build_xteink_book_pair(study_output, english_study_output, xteink_root=output_root / "[xteink]")

    artifacts: list[dict[str, str]] = []
    if wants_english and english_output.is_file():
        artifacts.append({"path": str(english_output.relative_to(output_root)), "kind": "english_epub"})
    if wants_bilingual and bilingual_output.is_file():
        artifacts.append({"path": str(bilingual_output.relative_to(output_root)), "kind": "bilingual_epub"})
    if wants_korean and korean_output.is_file():
        artifacts.append({"path": str(korean_output.relative_to(output_root)), "kind": "korean_epub"})
    if wants_study and study_output.is_file():
        artifacts.append({"path": str(study_output.relative_to(output_root)), "kind": "study_epub"})
    if wants_english_study and english_study_output.is_file():
        artifacts.append(
            {"path": str(english_study_output.relative_to(output_root)), "kind": "english_study_epub"}
        )
    if args.translation_output == "korean" and bilingual_output.is_file():
        bilingual_output.unlink()
    return artifacts


def audio_command(
    *,
    source: Path,
    output: Path,
    work_dir: Path,
    heartbeat_file: Path,
    args: argparse.Namespace,
) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / "audiobook_maker.py"),
        "--input-file",
        str(source),
        "--output-file",
        str(output),
        "--work-dir",
        str(work_dir),
        "--heartbeat-file",
        str(heartbeat_file),
        "--provider",
        args.audio_provider,
        "--audiobook-mode",
        args.audio_mode,
        "--voice",
        args.voice,
        "--audio-bitrate-kbps",
        str(args.bitrate),
        "--max-chars-per-chunk",
        str(args.max_chars),
    ]
    if args.audio_provider == "gemini_web":
        command.extend(["--gemini-web-max-attempts", str(args.max_attempts)])
        if args.visible:
            command.append("--gemini-web-visible")
    elif args.audio_provider == "chatgpt_web":
        command.extend(["--chatgpt-web-max-attempts", str(args.max_attempts)])
        if args.visible:
            command.append("--chatgpt-web-visible")
    else:
        command.extend(
            [
                "--gemini-api-tts-max-attempts",
                str(args.max_attempts),
                "--gemini-api-tts-model",
                args.model,
            ]
        )
    return command


def audio_one(
    source: Path,
    *,
    output_root: Path,
    work_dir: Path,
    heartbeat_file: Path,
    args: argparse.Namespace,
) -> list[dict[str, str]]:
    title = readable_stem(source)
    output_root.mkdir(parents=True, exist_ok=True)
    output = output_root / f"{title}_audiobook.m4a"
    if not args.overwrite and output.is_file() and output.stat().st_size > 0:
        print(f"SKIP existing audiobook: {output.name}", flush=True)
    else:
        prepared = prepare_epub(source, work_dir / "source") if source.suffix.lower() == ".mobi" else source
        beat(heartbeat_file, stage="audiobook_start", label=title, detail=source.name)
        run_child(
            audio_command(
                source=prepared,
                output=output,
                work_dir=work_dir / "audio",
                heartbeat_file=heartbeat_file,
                args=args,
            )
        )
    return [{"path": str(output.relative_to(output_root)), "kind": "audio"}] if output.is_file() else []


# 이 배치는 영어 원서를 한국어로 번역하는 파이프라인이다. 원서 자체가 영어가 아니면
# (프랑스어/스페인어 등 다른 라틴 문자 언어든, 비라틴 문자 언어든) 정상적으로 번역해도
# 대부분의 블록이 원문 그대로 남아 untranslated_identity로 계속 실패하고, 책 단위 재시도
# 3회를 전부 소진하게 된다 - 재시도로는 절대 해결되지 않는 원인이므로, 번역을 시도하기 전에
# 미리 걸러내 재시도 없이 스킵한다.
def looks_like_english_source(source: Path) -> bool:
    try:
        _title, _creator, sections = extract_sections(source)
    except Exception:
        return True  # 샘플링 자체가 안 되면 평소대로 번역을 시도(오탐으로 막지 않음).
    sample_parts: list[str] = []
    sample_len = 0
    for block in all_blocks(sections):
        text = block.text.strip()
        if len(text) < 40:
            continue
        sample_parts.append(text)
        sample_len += len(text)
        if sample_len >= 4000:
            break
    return is_english_word_sample(" ".join(sample_parts))


def archive_non_english_source(source: Path, source_dir: Path) -> Path:
    """비영어 원서를 소스 폴더 바로 아래 non-english/ 로 옮긴다.

    source_files()가 재귀 스캔이 아닌 한 하위 폴더 안 파일은 애초에 다시 스캔되지 않으므로,
    _excluded_do_not_retry/ 관행과 마찬가지로 이후 배치 재시작에서도 다시 집히지 않는다.
    """
    target_dir = source_dir / "non-english"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source.name
    if target_path.exists():
        stem, suffix = target_path.stem, target_path.suffix
        counter = 2
        while target_path.exists():
            target_path = target_dir / f"{stem} ({counter}){suffix}"
            counter += 1
    shutil.move(str(source), str(target_path))
    return target_path


def source_files(
    source_dir: Path,
    *,
    operation: str,
    recursive: bool,
    output_root: Path,
    priority_substrings: tuple[str, ...] = (),
) -> list[Path]:
    extensions = TRANSLATION_EXTENSIONS if operation == "batch_translation" else AUDIO_EXTENSIONS
    iterator = source_dir.rglob("*") if recursive else source_dir.iterdir()
    output_root = output_root.resolve()
    exclude_output_tree = output_root != source_dir.resolve()
    files: list[Path] = []
    for path in iterator:
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if exclude_output_tree:
            try:
                path.resolve().relative_to(output_root)
                continue
            except ValueError:
                pass
        if path.name.lower().startswith(("[k]", "[k-e]", "[e]", "[study]", "[e-s]")):
            continue
        # source_dir/finished 는 이미 끝난 원본을 보관해두는 폴더다(run_batch()가 책 완료
        # 시마다 원본을 여기로 옮긴다) - recursive=True로 돌리면 rglob이 그 안까지 훑어서
        # 이미 끝난 책을 새 소스로 다시 집어올리게 되므로 항상 제외한다.
        try:
            if path.resolve().relative_to(source_dir.resolve()).parts[0].lower() == "finished":
                continue
        except (ValueError, IndexError):
            pass
        files.append(path.resolve())

    # 배치 번역일 때 이미 번역된 파일들을 제외
    if operation == "batch_translation":
        korean_root = Path("/Users/hyeokjunkong/Desktop/소설2/[k]").expanduser().resolve()
        existing_books = get_existing_korean_books(korean_root)
        if existing_books:
            files = [f for f in files if f.name not in existing_books]

    lowered_priority = tuple(term.lower() for term in priority_substrings if term)

    def sort_key(item: Path) -> tuple[int, str]:
        name_lower = item.name.lower()
        is_priority = any(term in name_lower for term in lowered_priority)
        return (0 if is_priority else 1, item.name.casefold())

    return sorted(files, key=sort_key)[:1000]


def write_manifest(
    path: Path,
    *,
    root: Path,
    artifacts: list[dict[str, str]],
    failures: list[dict[str, str]],
) -> None:
    atomic_write_json(
        path,
        {
            "root": str(root.resolve()),
            "artifacts": artifacts,
            "failures": failures,
            "completed_at": utc_now(),
        },
    )


def run_single_translation(args: argparse.Namespace) -> int:
    source = args.input_file.resolve()
    output_root = args.output_dir.resolve()
    work_dir = args.work_dir.resolve()
    diagnostics = WorkflowDiagnostics(work_dir, "translation")
    diagnostics.start(
        stage="translate_book",
        total_units=1,
        metadata={"provider": args.translation_provider},
        evidence_paths={"source": source, "output_root": output_root},
    )
    try:
        artifacts = translate_one(
            source,
            output_root=output_root,
            work_dir=work_dir,
            heartbeat_file=args.heartbeat_file.resolve(),
            args=args,
            split_output_dirs=False,
        )
    except BaseException as exc:
        diagnostics.record_current_exception(exc, stage="translate_book")
        raise
    write_manifest(args.artifact_manifest_file, root=output_root, artifacts=artifacts, failures=[])
    beat(args.heartbeat_file, stage="complete", label="1/1", detail=f"artifacts={len(artifacts)}")
    diagnostics.complete(stage="complete", artifacts={"count": len(artifacts)})
    return 0


def run_batch(args: argparse.Namespace) -> int:
    source_dir = args.source_dir.resolve()
    output_root = args.output_dir.resolve()
    priority_substrings = tuple(
        term.strip() for term in (getattr(args, "priority_substrings", None) or "").split(",") if term.strip()
    )
    files = source_files(
        source_dir,
        operation=args.task,
        recursive=args.recursive,
        output_root=output_root,
        priority_substrings=priority_substrings,
    )
    if getattr(args, "reverse", False):
        # 같은 소스 폴더를 다른 계정/인스턴스와 병렬로 나눠 돌릴 때, 정방향 인스턴스는 앞에서부터
        # 이 뒤집힌 목록의 인스턴스는 뒤에서부터 소비하게 해 서로 다른 책을 집도록 한다.
        files = list(reversed(files))
    if not files:
        raise RuntimeError("No supported source files were found in the selected folder")
    diagnostics = WorkflowDiagnostics(args.work_dir.resolve(), args.task)
    diagnostics.start(
        stage="batch_prepare",
        total_units=len(files),
        metadata={"task": args.task, "source_dir": str(source_dir), "output_root": str(output_root)},
        evidence_paths={"source_dir": source_dir, "output_root": output_root},
    )
    artifacts: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    batch_paused = False
    batch_diagnosis: dict[str, object] | None = None
    finished_registry = (
        build_finished_registry(FINISHED_ROOT)
        + build_html_collection_registry(K_COLLECTION_HTML)
        + build_library_registry(K_LIBRARY_ROOT)
        if args.task == "batch_translation"
        else []
    )
    targets = [source.name for source in files]
    completed_items: list[dict[str, str]] = []
    write_batch_status(
        args.batch_status_file,
        total=len(files),
        targets=targets,
        current=None,
        current_index=None,
        completed=completed_items,
    )
    for index, source in enumerate(files, start=1):
        label = f"{index}/{len(files)} {source.name}"
        diagnostics.progress(
            stage="batch_item",
            completed=len(completed_items),
            total=len(files),
            current=source.name,
            detail=f"index={index} task={args.task}",
        )
        beat(args.heartbeat_file, stage="batch_item_start", label=label, detail=args.task)
        write_batch_status(
            args.batch_status_file,
            total=len(files),
            targets=targets,
            current=source.name,
            current_index=index,
            completed=completed_items,
        )
        if args.task == "batch_translation" and source.is_file() and source.suffix.lower() == ".epub":
            metadata = extract_metadata_from_epub(source)
            match = find_finished_match(metadata["title"], metadata["author"], finished_registry)
            if match:
                archived_path = archive_duplicate_source(source, FINISHED_ROOT)
                print(
                    f"SKIP duplicate (already finished as {match['path'].name}): "
                    f"{source.name} -> moved to {archived_path}",
                    flush=True,
                )
                beat(args.heartbeat_file, stage="batch_item_complete", label=f"{index}/{len(files)}", detail=source.name)
                completed_items.append({"name": source.name, "status": "skipped"})
                diagnostics.progress(
                    stage="batch_item",
                    completed=len(completed_items),
                    total=len(files),
                    current=source.name,
                    detail="duplicate source skipped",
                    success=True,
                )
                write_batch_status(
                    args.batch_status_file,
                    total=len(files),
                    targets=targets,
                    current=None,
                    current_index=index,
                    completed=completed_items,
                )
                continue
            if not looks_like_english_source(source):
                archived_path = archive_non_english_source(source, source_dir)
                print(
                    f"SKIP non-English source (this pipeline translates English originals only): "
                    f"{source.name} -> moved to {archived_path}",
                    flush=True,
                )
                beat(args.heartbeat_file, stage="batch_item_complete", label=f"{index}/{len(files)}", detail=source.name)
                completed_items.append({"name": source.name, "status": "skipped", "reason": "non_english_source"})
                diagnostics.progress(
                    stage="batch_item",
                    completed=len(completed_items),
                    total=len(files),
                    current=source.name,
                    detail="non-English source skipped",
                    success=True,
                )
                write_batch_status(
                    args.batch_status_file,
                    total=len(files),
                    targets=targets,
                    current=None,
                    current_index=index,
                    completed=completed_items,
                )
                continue
        item_work = find_existing_item_work_dir(args.work_dir.resolve(), source) or (
            args.work_dir.resolve() / f"{index:04d}_{readable_stem(source)[:80]}"
        )
        last_exc: Exception | None = None
        book_succeeded = False
        for book_attempt in range(1, BOOK_RETRY_ATTEMPTS + 1):
            try:
                if args.task == "batch_translation":
                    item_artifacts = translate_one(
                        source,
                        output_root=output_root,
                        work_dir=item_work,
                        heartbeat_file=args.heartbeat_file.resolve(),
                        args=args,
                        split_output_dirs=True,
                        provider_fallback_state_dir=args.work_dir.resolve(),
                    )
                else:
                    item_artifacts = audio_one(
                        source,
                        output_root=output_root,
                        work_dir=item_work,
                        heartbeat_file=args.heartbeat_file.resolve(),
                        args=args,
                    )
                artifacts.extend(item_artifacts)
                completed_items.append({"name": source.name, "status": "done"})
                book_succeeded = True
                if args.task == "batch_translation":
                    # 이 책의 번역이 막 끝났으니, 나중에 이 폴더를 다시 훑을 때 원본이 계속
                    # 눈에 밟히지 않도록 소스 폴더 자체의 finished/ 하위로 옮겨둔다. 예전에는
                    # find_finished_match()로 "이미 끝난 걸로 확인된" 중복만 옮겼고(위쪽의
                    # SKIP duplicate 분기), 방금 이번 실행에서 새로 끝낸 책은 옮기는 절차가
                    # 없어서 완료된 원본이 소스 폴더에 계속 쌓였다.
                    try:
                        archived_path = archive_duplicate_source(source, source_dir / "finished")
                        print(f"ARCHIVED completed source: {source.name} -> {archived_path}", flush=True)
                    except Exception as archive_exc:  # noqa: BLE001 - 보관 실패가 성공한 책을 재시도로 몰아넣으면 안 된다.
                        print(
                            f"WARNING: could not archive completed source {source.name}: {archive_exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                break
            except Exception as exc:  # noqa: BLE001 - retried below before giving up on this book.
                last_exc = exc
                child_state = child_workflow_diagnostics(item_work, args.task)
                should_retry, delay, diagnosis = batch_retry_policy(
                    exc,
                    book_attempt=book_attempt,
                    child_diagnostics=child_state,
                )
                batch_diagnosis = diagnosis
                kind = str(diagnosis.get("kind") or "unknown_error")
                diagnostics.record_failure(
                    exc,
                    stage=f"batch_item:{source.name}",
                    attempt=book_attempt,
                    max_attempts=BOOK_RETRY_ATTEMPTS if should_retry else 1,
                    explicit_kind=kind,
                    evidence={
                        "source": str(source),
                        "item_work": str(item_work),
                        "child_diagnostics": str(
                            item_work
                            / ("translation" if args.task == "batch_translation" else "audio")
                            / "workflow_diagnostics.json"
                        ),
                    },
                )
                print(
                    f"BOOK_ATTEMPT_FAILED {source.name} (attempt {book_attempt}/{BOOK_RETRY_ATTEMPTS}) "
                    f"kind={kind}: {exc}",
                    flush=True,
                )
                if kind in BATCH_PAUSE_KINDS:
                    batch_paused = True
                if should_retry:
                    beat(
                        args.heartbeat_file,
                        stage="batch_item_retry",
                        label=label,
                        detail=(
                            f"attempt={book_attempt}/{BOOK_RETRY_ATTEMPTS} "
                            f"retry_in={delay}s error={str(exc)[:200]}"
                        ),
                    )
                    # 같은 work-dir을 재사용하므로 다음 시도는 이미 완료된 청크를 건너뛰고
                    # 실패했던 청크부터 이어서 진행한다 (새 프로세스 = 새 브라우저 세션).
                    time.sleep(delay)
                else:
                    break
        if not book_succeeded:
            assert last_exc is not None
            failures.append({"source": source.name, "error": str(last_exc)})
            print(
                f"FAILED {source.name} after {BOOK_RETRY_ATTEMPTS} book-level attempts: {last_exc}",
                flush=True,
            )
            completed_items.append(
                {
                    "name": source.name,
                    "status": "failed",
                    "error": str(last_exc)[:500],
                    "book_attempts": str(book_attempt),
                    "error_kind": str((batch_diagnosis or {}).get("kind") or "unknown_error"),
                }
            )
        beat(args.heartbeat_file, stage="batch_item_complete", label=f"{index}/{len(files)}", detail=source.name)
        write_batch_status(
            args.batch_status_file,
            total=len(files),
            targets=targets,
            current=None,
            current_index=index,
            completed=completed_items,
            status="paused" if batch_paused else "running",
            diagnosis=batch_diagnosis,
        )
        if batch_paused:
            beat(
                args.heartbeat_file,
                stage="batch_paused",
                label=f"{index}/{len(files)}",
                detail=(
                    f"kind={(batch_diagnosis or {}).get('kind', 'unknown_error')} "
                    f"action={(batch_diagnosis or {}).get('action', '')}"
                ),
            )
            break
    write_manifest(
        args.artifact_manifest_file,
        root=output_root,
        artifacts=artifacts,
        failures=failures,
    )
    beat(
        args.heartbeat_file,
        stage="batch_paused" if batch_paused else ("complete" if not failures else "complete_with_errors"),
        label=f"{len(files)}/{len(files)}",
        detail=f"artifacts={len(artifacts)} failures={len(failures)}",
    )
    write_batch_status(
        args.batch_status_file,
        total=len(files),
        targets=targets,
        current=None,
        current_index=len(completed_items),
        completed=completed_items,
        status="paused" if batch_paused else ("complete_with_errors" if failures else "complete"),
        diagnosis=batch_diagnosis if failures else None,
    )
    if not failures:
        diagnostics.complete(stage="complete", artifacts={"count": len(artifacts)})
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run translation and folder workflows for the web interface.")
    parser.add_argument("--task", choices=("translation", "batch_translation", "batch_audio"), required=True)
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--heartbeat-file", type=Path, required=True)
    parser.add_argument("--batch-status-file", type=Path, default=None)
    parser.add_argument("--artifact-manifest-file", type=Path, required=True)
    parser.add_argument("--translation-provider", choices=("gemini", "chatgpt"), default="gemini")
    parser.add_argument("--translation-output", choices=("both", "korean", "bilingual"), default="both")
    parser.add_argument("--audio-provider", choices=("gemini_web", "chatgpt_web", "gemini_api_tts"), default="gemini_web")
    parser.add_argument("--audio-mode", choices=("plain", "material_only", "study"), default="plain")
    parser.add_argument("--voice", default="account_default")
    parser.add_argument("--model", default="gemini-2.5-flash-preview-tts")
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--bitrate", type=int, default=96)
    parser.add_argument("--chunks-per-conversation", type=int, default=10)
    parser.add_argument("--inter-request-delay", type=float, default=4.0)
    parser.add_argument("--request-timeout", type=int, default=1200)
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--disable-overnight-web-fallback",
        action="store_true",
        help=(
            "야간(18:00~09:00) 및 주말(토/일 종일) 시간대에 Gemini 웹이 오류/일시 중단되어도 "
            "ChatGPT 웹으로 자동 전환하지 않도록, 각 도서 번역 하위 프로세스에 그대로 전달합니다."
        ),
    )
    parser.add_argument(
        "--priority-substrings",
        default=None,
        help="쉼표로 구분된 문자열 목록. 배치 대상 파일명에 이 중 하나라도 포함되면 먼저 처리합니다.",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help=(
            "대상 목록을 뒤에서부터(내림차순) 처리합니다. 같은 소스 폴더를 다른 계정/인스턴스와 "
            "병렬로 나눠 돌릴 때, 한쪽은 --reverse 없이 앞에서부터, 다른 쪽은 --reverse로 뒤에서부터 "
            "진행하면 서로 다른 책을 집어 겹치지 않습니다."
        ),
    )
    args = parser.parse_args()
    if args.task == "translation" and args.input_file is None:
        parser.error("--input-file is required for translation")
    if args.task.startswith("batch_") and args.source_dir is None:
        parser.error("--source-dir is required for batch jobs")
    return args


def main() -> int:
    args = parse_args()
    if args.task == "translation":
        return run_single_translation(args)
    return run_batch(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
