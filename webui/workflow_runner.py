#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webui.book_organizer import (  # noqa: E402
    archive_duplicate_source,
    build_finished_registry,
    extract_metadata_from_epub,
    find_finished_match,
    get_existing_korean_books,
)
from webui.platform import discover_ebook_convert  # noqa: E402
from webui.storage import atomic_write_json  # noqa: E402

SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export_pdf_to_kindle_epub import build_epub as build_reflow_epub  # noqa: E402
from make_korean_only_epubs import convert_epub, output_name  # noqa: E402


TRANSLATION_EXTENSIONS = {".epub", ".pdf", ".mobi"}
AUDIO_EXTENSIONS = {".txt", ".epub", ".docx", ".pdf", ".mobi"}

# 이미 번역이 끝난 원서 EPUB을 모아 두는 폴더. 배치 번역 시 이 목록의 제목/작가와
# 대조해 중복 번역을 피한다.
FINISHED_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2/finished")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def readable_stem(path: Path) -> str:
    stem = unicodedata.normalize("NFKC", path.stem)
    stem = re.sub(r"^\[(?:e|s|k|k-e)\]\s*", "", stem, flags=re.IGNORECASE)
    # Piracy-site watermark ("_OceanofPDF.com_...") baked into the downloaded filename - strip it
    # so it never leaks into generated output filenames or per-book work directory names.
    stem = re.sub(r"(?i)[_\s]*oceanofpdf[._\s-]*com[_\s]*", " ", stem)
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = re.sub(r"[\\/:*?\"<>|]+", "", stem)
    return stem[:180] or "Book"


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
    if provider_fallback_state_dir is not None:
        command.extend(["--provider-fallback-state-dir", str(provider_fallback_state_dir)])
    return command


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
    title = readable_stem(source)
    bilingual_dir = output_root / "[k-e]" if split_output_dirs else output_root
    korean_dir = output_root / "[k]" if split_output_dirs else output_root
    bilingual_dir.mkdir(parents=True, exist_ok=True)
    korean_dir.mkdir(parents=True, exist_ok=True)
    bilingual_output = bilingual_dir / f"[k-e] {title}.epub"
    korean_output = korean_dir / output_name(bilingual_output.name)
    wants_bilingual = args.translation_output in {"both", "bilingual"}
    wants_korean = args.translation_output in {"both", "korean"}
    desired_outputs = [
        path
        for path, wanted in ((bilingual_output, wants_bilingual), (korean_output, wants_korean))
        if wanted
    ]

    if not args.overwrite and all(path.is_file() and path.stat().st_size > 0 for path in desired_outputs):
        print(f"SKIP existing translation outputs: {title}", flush=True)
    else:
        translated = False
        if args.overwrite or not bilingual_output.is_file():
            source_epub = prepare_epub(source, work_dir / "source")
            beat(heartbeat_file, stage="translation_start", label=title, detail=source.name)
            run_child(
                translation_command(
                    source_epub=source_epub,
                    bilingual_output=bilingual_output,
                    work_dir=work_dir / "translation",
                    heartbeat_file=heartbeat_file,
                    args=args,
                    provider_fallback_state_dir=provider_fallback_state_dir,
                )
            )
            translated = True
        if wants_korean and (args.overwrite or translated or not korean_output.is_file()):
            beat(heartbeat_file, stage="korean_epub_start", label=title)
            convert_epub(bilingual_output, korean_output, True)

    artifacts: list[dict[str, str]] = []
    if wants_bilingual and bilingual_output.is_file():
        artifacts.append({"path": str(bilingual_output.relative_to(output_root)), "kind": "bilingual_epub"})
    if wants_korean and korean_output.is_file():
        artifacts.append({"path": str(korean_output.relative_to(output_root)), "kind": "korean_epub"})
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
        if path.name.lower().startswith(("[k]", "[k-e]")):
            continue
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
    artifacts = translate_one(
        source,
        output_root=output_root,
        work_dir=work_dir,
        heartbeat_file=args.heartbeat_file.resolve(),
        args=args,
        split_output_dirs=False,
    )
    write_manifest(args.artifact_manifest_file, root=output_root, artifacts=artifacts, failures=[])
    beat(args.heartbeat_file, stage="complete", label="1/1", detail=f"artifacts={len(artifacts)}")
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
    if not files:
        raise RuntimeError("No supported source files were found in the selected folder")
    artifacts: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    finished_registry = build_finished_registry(FINISHED_ROOT) if args.task == "batch_translation" else []
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
                write_batch_status(
                    args.batch_status_file,
                    total=len(files),
                    targets=targets,
                    current=None,
                    current_index=index,
                    completed=completed_items,
                )
                continue
        item_work = args.work_dir.resolve() / f"{index:04d}_{readable_stem(source)[:80]}"
        try:
            if args.task == "batch_translation":
                artifacts.extend(
                    translate_one(
                        source,
                        output_root=output_root,
                        work_dir=item_work,
                        heartbeat_file=args.heartbeat_file.resolve(),
                        args=args,
                        split_output_dirs=True,
                        provider_fallback_state_dir=args.work_dir.resolve(),
                    )
                )
            else:
                artifacts.extend(
                    audio_one(
                        source,
                        output_root=output_root,
                        work_dir=item_work,
                        heartbeat_file=args.heartbeat_file.resolve(),
                        args=args,
                    )
                )
            completed_items.append({"name": source.name, "status": "done"})
        except Exception as exc:  # noqa: BLE001 - continue the remaining user-selected batch.
            failures.append({"source": source.name, "error": str(exc)})
            print(f"FAILED {source.name}: {exc}", flush=True)
            completed_items.append({"name": source.name, "status": "failed", "error": str(exc)[:500]})
        beat(args.heartbeat_file, stage="batch_item_complete", label=f"{index}/{len(files)}", detail=source.name)
        write_batch_status(
            args.batch_status_file,
            total=len(files),
            targets=targets,
            current=None,
            current_index=index,
            completed=completed_items,
        )
    write_manifest(
        args.artifact_manifest_file,
        root=output_root,
        artifacts=artifacts,
        failures=failures,
    )
    beat(
        args.heartbeat_file,
        stage="complete" if not failures else "complete_with_errors",
        label=f"{len(files)}/{len(files)}",
        detail=f"artifacts={len(artifacts)} failures={len(failures)}",
    )
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
        "--priority-substrings",
        default=None,
        help="쉼표로 구분된 문자열 목록. 배치 대상 파일명에 이 중 하나라도 포함되면 먼저 처리합니다.",
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
