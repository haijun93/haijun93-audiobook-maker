#!/usr/bin/env python3
"""이미 확정된 한국어 번역([k-e])은 절대 재번역하지 않고, 그 번역문에 학습노트(※학습:)만
새로 채워 [study]/[e-s]를 만든다.

레거시 파이프라인(_chatgpt_translate_work 등)으로 번역된 Pam Godwin 도서들처럼, 번역 당시
학습노트 기능이 없었던 책들은 [k-e]는 있지만 [study]가 없다. 이 스크립트는:
  1. --input-epub을 현재(수정된) extract_sections()로 다시 구조 분석하고,
  2. --source-work-dir의 기존 번역 캐시(블록ID -> 한국어 번역문)를 그대로 불러오고,
  3. 그 한국어 번역문은 절대 수정하지 않은 채, 블록마다 학습노트 한 줄만 웹 제공자에게
     새로 요청해 붙인다(번역 자체는 요청하지 않음).

이렇게 만든 결과는 --work-dir에 표준 chunk_XXXX.json 캐시로 저장되므로, 이후
translate_epub_with_chatgpt_web_to_study_epub.py --build-only로 그대로 재사용할 수 있다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

import translate_epub_with_chatgpt_web_to_study_epub as pipeline  # noqa: E402
from webui.workflow_diagnostics import WorkflowDiagnostics, load_workflow_diagnostics  # noqa: E402

from bs4 import BeautifulSoup  # noqa: E402
import zipfile  # noqa: E402

STUDY_NOTE_MARKER = pipeline.STUDY_NOTE_MARKER
BACKFILL_STATUS_FILE = "study_note_backfill_status.json"


def load_sections_from_live_k_e_epub(epub_path: Path) -> list[pipeline.SourceSection]:
    """이미 서재에 있는 [k-e] EPUB 자체를 원본 소스로 삼아 섹션/블록을 복원한다.

    레거시 work-dir 캐시가 아예 없거나 불완전한 책들(예: 여러 번의 재작업 이력만 남고 완전한
    번역 캐시는 남아있지 않은 경우)에도 쓸 수 있는 가장 안전한 방법이다 - 이미 배포된 [k-e]
    파일 안에서 영어(en)와 한국어(ko)가 같은 <p class="pair"> 안에 나란히 들어있으므로, 다른
    추출 시점과 짝을 맞출 필요 없이 그 파일 자체가 이미 올바르게 정렬된 정답이다."""
    z = zipfile.ZipFile(epub_path)
    names = [n for n in z.namelist() if n.lower().endswith((".xhtml", ".html")) and "nav" not in n.lower() and "cover" not in n.lower()]
    names.sort()
    sections: list[pipeline.SourceSection] = []
    counter = 0
    for name in names:
        soup = BeautifulSoup(z.read(name), "html.parser")
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else Path(name).stem
        blocks: list[pipeline.SourceBlock] = []
        for pair in soup.find_all(class_="pair"):
            # 대부분의 [k-e]는 <span class="en">/<span class="ko">지만, 일부(예: Calibre로
            # 재저장된 파일)는 정리 과정에서 class="ko"가 빠지고 xml:lang="ko"만 남는다.
            # class로 먼저 찾고, 없으면 xml:lang/lang 속성으로 다시 찾는다.
            en = pair.find(class_="en") or pair.find(attrs={"xml:lang": "en"}) or pair.find(lang="en")
            ko = pair.find(class_="ko") or pair.find(attrs={"xml:lang": "ko"}) or pair.find(lang="ko")
            if en is None or ko is None:
                continue
            en_text = en.get_text(separator=" ", strip=True)
            ko_text = ko.get_text(separator=" ", strip=True)
            if not en_text and not ko_text:
                continue
            counter += 1
            block_id = f"B{counter:05d}"
            blocks.append(pipeline.SourceBlock(id=block_id, text=en_text))
            blocks[-1].__dict__["_ko"] = ko_text
        if blocks:
            sections.append(pipeline.SourceSection(title=title, filename=Path(name).name, blocks=blocks))
    return sections


def cache_from_live_sections(sections: list[pipeline.SourceSection]) -> dict[str, str]:
    return {block.id: block.__dict__.get("_ko", "") for section in sections for block in section.blocks}


def build_note_prompt(chunk, chunk_count: int, book_title: str, *, safety_retry: bool = False) -> str:
    role = (
        "- 당신은 영어-한국어 대조 학습 교재를 만드는 영어 교육 전문가입니다.\n"
        "- 아래 각 SEGMENT는 영어 원문과, 이미 확정되어 절대 바꿀 수 없는 한국어 번역문 쌍입니다."
    )
    if safety_retry:
        role += (
            "\n- 이 작업은 어휘/문법 학습 노트만 작성하는 것으로, 새로운 서사나 장면 묘사를 "
            "만들어내지 않습니다. 원문에 민감한 내용이 있어도 그 내용 자체를 다시 서술하지 말고, "
            "학습에 유용한 표현만 사전적으로 짚어주세요."
        )
    return f"""사용자가 정당하게 소유한 EPUB `{book_title}`의 일부에 대해, 이미 완성된 한국어 번역문에
영어 학습 노트만 추가합니다. 번역 자체는 이미 끝났으므로 절대 다시 번역하지 않습니다.

역할:
{role}

작업 목적:
- 이 결과물은 토익(TOEIC) 700점 수준 학습자가 만점을 목표로 영어 원문과 이미 확정된
  한국어 번역문을 대조하며 공부하는 개인 학습용 교재에 들어갈 학습 노트입니다.
- 재배포하거나 상업적으로 이용하지 않으며, 사용자 개인 학습 용도로만 사용됩니다.

중요 규칙:
1. 아래 각 SEGMENT의 [영어 원문]과 [한국어 번역 - 확정, 수정 금지]를 읽고, 그 SEGMENT에 대한
   학습 노트만 한 줄 작성합니다. 번역문을 다시 쓰거나 고치지 않습니다.
2. 학습 노트 형식: 표현1 - 뜻/설명; 표현2 - 뜻/설명
   - 그 문장에서 가장 익혀둘 만한 요소(단어 뜻, 구동사(phrasal verb), 숙어, 문법 포인트,
     자연스러운 collocation(연어) 등) 하나 이상을 골라 간결히 설명합니다.
   - "a", "the", "is", "he", "go" 같은 극초급 단어로만 이루어진 아주 짧은 문장이거나,
     감탄사 한 단어·인명만 있는 문장처럼 정말로 학습할 요소가 전혀 없는 경우에만
     예외적으로 빈 내용을 출력합니다(그래도 ID 마커 쌍은 반드시 출력).
   - 영어 원문 문장 전체를 노트에 반복하지 말고 표현과 뜻만 간결하게 씁니다.
3. 출력은 반드시 아래 ID 마커 형식만 사용하고, 각 ID는 정확히 한 번씩 출력합니다.
4. 한국어 번역문이나 영어 원문 자체를 출력하지 마세요. 학습 노트 내용만 출력합니다.

출력 형식 예:
<<<EXAMPLE_ID>>>
표현 - 뜻/설명; 표현2 - 뜻/설명
<<<END_EXAMPLE_ID>>>

현재 조각: {chunk.index}/{chunk_count}

SEGMENTS:
{chunk.text}
"""


def build_note_blocks(blocks, cache: dict[str, str]):
    note_blocks = []
    already_noted: dict[str, str] = {}
    missing_from_cache: list[str] = []
    for block in blocks:
        korean = cache.get(block.id)
        if not korean:
            missing_from_cache.append(block.id)
            continue
        if STUDY_NOTE_MARKER in korean:
            already_noted[block.id] = korean
            continue
        if pipeline.is_separator_text(block.text):
            # "***", "- - -" 같은 장면 구분선은 학습할 표현이 없다 - 모델에게 물어봐도 항상
            # 빈 노트만 돌아오므로, 요청 자체를 보내지 않는다(유료 사용량 절약).
            already_noted[block.id] = korean
            continue
        combined = f"[영어 원문]\n{block.text}\n[한국어 번역 - 확정, 수정 금지]\n{korean}"
        note_blocks.append(pipeline.SourceBlock(id=block.id, text=combined))
    return note_blocks, already_noted, missing_from_cache


def note_prompt_for_block_ids(prompt: str, block_ids: list[str]) -> str:
    """Keep only selected SEGMENT blocks for a targeted format retry."""
    if "SEGMENTS:\n" not in prompt:
        return prompt
    wanted = set(block_ids)
    segments = [
        match.group(0)
        for match in re.finditer(
            r"<<<(B\d+)>>>\s*.*?\s*<<<END_\1>>>",
            prompt,
            re.DOTALL,
        )
        if match.group(1) in wanted
    ]
    if not segments:
        return prompt
    header = prompt.split("SEGMENTS:\n", 1)[0]
    body = "\n\n".join(segments)
    return f"{header}SEGMENTS:\n{body}\n"


def cached_note_chunk_is_complete(path: Path, block_ids: list[str]) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    notes = payload.get("translations")
    return isinstance(notes, dict) and all(block_id in notes for block_id in block_ids)


def apply_cached_note_chunk(
    path: Path,
    block_ids: list[str],
    source_translations: dict[str, str],
    final_translations: dict[str, str],
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    notes = payload["translations"]
    for block_id in block_ids:
        korean = source_translations[block_id]
        note = str(notes[block_id] or "").strip()
        final_translations[block_id] = (
            f"{korean}\n{STUDY_NOTE_MARKER} {note}" if note else korean
        )


def write_backfill_status(
    work_dir: Path,
    chunks: list[pipeline.TranslationChunk],
    *,
    errors: list[dict[str, object]] | None = None,
) -> list[int]:
    completed = [
        chunk.index
        for chunk in chunks
        if cached_note_chunk_is_complete(
            work_dir / "translations" / f"chunk_{chunk.index:04d}.json",
            chunk.block_ids,
        )
    ]
    completed_set = set(completed)
    incomplete = [chunk.index for chunk in chunks if chunk.index not in completed_set]
    pipeline.write_json(
        work_dir / BACKFILL_STATUS_FILE,
        {
            "status": "complete" if not incomplete else "incomplete",
            "chunk_count": len(chunks),
            "completed_count": len(completed),
            "incomplete_count": len(incomplete),
            "completed_chunks": completed,
            "incomplete_chunks": incomplete,
            "errors": errors or [],
        },
    )
    return incomplete


def request_note_chunk(
    *,
    context,
    timeout_error_cls,
    args: argparse.Namespace,
    prompt: str,
    refusal_retry_prompt: str,
    chunk: pipeline.TranslationChunk,
    chunk_count: int,
    work_dir: Path,
    max_attempts: int,
    heartbeat=None,
) -> tuple[str, dict[str, str]]:
    prefix = f"notes_chunk_{chunk.index:04d}"
    last_error: Exception | None = None
    collected_notes: dict[str, str] = {}
    pending_ids = list(chunk.block_ids)
    queued_groups: list[list[str]] = []
    last_conversation_id = ""
    for content_attempt in range(1, max(1, max_attempts) + 1):
        active_prompt = note_prompt_for_block_ids(prompt, pending_ids)
        if content_attempt > 1:
            active_prompt += (
                "\n\n이전 응답은 ID 마커 형식이 불완전했습니다. 위 SEGMENTS의 ID만, "
                "각각 정확히 한 번씩 빠짐없이 출력하세요. 예시 마커는 출력하지 마세요."
            )
            pipeline.write_text(
                work_dir / "prompts" / f"{prefix}_format_retry_{content_attempt:02d}_prompt.txt",
                active_prompt,
            )
        try:
            conversation_id, response = pipeline.request_web_translation(
                context=context,
                timeout_error_cls=timeout_error_cls,
                args=args,
                prompt=active_prompt,
                refusal_retry_prompt=refusal_retry_prompt,
                heartbeat=heartbeat,
                label=f"학습노트 {chunk.index}/{chunk_count}",
                prefix=prefix,
                work_dir=work_dir,
            )
            last_conversation_id = conversation_id
            response_path = work_dir / "responses" / f"{prefix}_response.txt"
            pipeline.write_text(response_path, response)
            pipeline.write_text(
                work_dir / "responses" / f"{prefix}_attempt_{content_attempt:02d}_response.txt",
                response,
            )
            notes = pipeline.parse_translation_response(response, pending_ids)
            collected_notes.update(notes)
            missing_ids = [
                block_id for block_id in chunk.block_ids if block_id not in collected_notes
            ]
            if missing_ids:
                remaining_attempts = max_attempts - content_attempt
                if (
                    not notes
                    and not queued_groups
                    and remaining_attempts >= 2
                    and len(missing_ids) > 1
                ):
                    midpoint = max(1, len(missing_ids) // 2)
                    pending_ids = missing_ids[:midpoint]
                    queued_groups.append(missing_ids[midpoint:])
                elif queued_groups:
                    pending_ids = queued_groups.pop(0)
                else:
                    pending_ids = missing_ids
                raise RuntimeError(
                    f"{prefix} 학습노트 응답에서 누락된 ID: {', '.join(missing_ids[:10])}"
                )
            return last_conversation_id, collected_notes
        except Exception as exc:
            last_error = exc
            pipeline.append_adaptive_error_event(
                work_dir,
                prefix=prefix,
                label=f"학습노트 {chunk.index}/{chunk_count}",
                attempt=content_attempt,
                error=exc,
                chunk=chunk,
                max_attempts=max_attempts,
            )
            if (
                isinstance(exc, pipeline.OvernightProviderSwitch)
                or pipeline.is_web_provider_pause_error(exc)
                or content_attempt >= max_attempts
            ):
                raise
            time.sleep(min(10, content_attempt * 2))
    assert last_error is not None
    raise last_error


def load_legacy_sections(source_work_dir: Path) -> list[pipeline.SourceSection]:
    """레거시 work-dir의 source_sections.json에서 그 번역 캐시가 만들어질 때 실제로 쓰인
    영어 블록 텍스트/섹션 구조를 그대로 복원한다.

    현재(수정된) extract_sections()를 다시 돌리면 블록 ID는 같아 보여도(B00001, B00002, ...)
    그 번호가 가리키는 실제 영어 문장이 레거시 추출 때와 달라질 수 있다 - 실제로 Vanquish에서
    검증해보니 새 추출의 B00020(냉장고 리놀륨 장면)이 레거시 캐시의 B00020(다락방 채찍질 장면)과
    완전히 다른 내용이었다. 블록 ID는 순번일 뿐 내용 해시가 아니므로, 레거시 캐시와 짝지으려면
    반드시 그 캐시가 실제로 생성됐을 때의 원본 영어 텍스트(source_sections.json)를 그대로 써야
    한국어(레거시 캐시)와 영어가 올바르게 대응한다."""
    payload = json.loads((source_work_dir / "source_sections.json").read_text(encoding="utf-8"))
    sections = []
    for entry in payload.get("sections", []):
        blocks = [pipeline.SourceBlock(id=b["id"], text=b["text"]) for b in entry.get("blocks", [])]
        sections.append(pipeline.SourceSection(title=entry.get("title", ""), filename=entry.get("filename", ""), blocks=blocks))
    return sections


def run(args: argparse.Namespace) -> int:
    input_epub = args.input_epub.expanduser().resolve()
    work_dir = args.work_dir.expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "translations").mkdir(parents=True, exist_ok=True)
    (work_dir / "prompts").mkdir(parents=True, exist_ok=True)
    (work_dir / "responses").mkdir(parents=True, exist_ok=True)
    diagnostics = WorkflowDiagnostics(work_dir, "study_note_backfill")
    heartbeat_path = getattr(args, "heartbeat_file", None) or (work_dir / "heartbeat.json")
    heartbeat = pipeline.ProgressHeartbeat(
        Path(heartbeat_path).expanduser().resolve(),
        observer=diagnostics.observe_heartbeat,
    )
    diagnostics.start(
        stage="load_source",
        metadata={"provider": pipeline.active_web_provider(args)},
        evidence_paths={"input_epub": input_epub},
    )
    pipeline.beat_heartbeat(heartbeat, stage="backfill_load_source", detail=str(input_epub))

    if args.live_k_e_epub:
        live_epub = args.live_k_e_epub.expanduser().resolve()
        title_meta, creator, _spine, _res = pipeline.read_spine(live_epub)
        book_title = title_meta or input_epub.stem
        sections = load_sections_from_live_k_e_epub(live_epub)
        blocks = pipeline.all_blocks(sections)
        cache = cache_from_live_sections(sections)
    else:
        source_work_dir = args.source_work_dir.expanduser().resolve()
        source_manifest = json.loads((source_work_dir / "manifest.json").read_text(encoding="utf-8"))
        book_title = source_manifest.get("book_title") or input_epub.stem
        creator = source_manifest.get("creator") or ""
        sections = load_legacy_sections(source_work_dir)
        blocks = pipeline.all_blocks(sections)
        cache = pipeline.load_translation_cache(source_work_dir)
    if not sections:
        raise SystemExit("섹션을 하나도 추출하지 못했습니다 - en/ko 쌍 파싱이 이 EPUB 구조와 맞지 않는 것 같습니다.")
    ko_book_title = args.book_title_ko or book_title

    note_blocks, already_noted, missing = build_note_blocks(blocks, cache)
    print(
        json.dumps(
            {
                "book_title": book_title,
                "total_blocks": len(blocks),
                "already_noted": len(already_noted),
                "needs_note": len(note_blocks),
                "missing_from_source_cache": missing[:20],
                "missing_count": len(missing),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if missing:
        raise SystemExit(
            f"--source-work-dir 캐시에 없는 블록 {len(missing)}개가 있어 중단합니다. "
            f"기존 번역 캐시가 현재 소스와 맞지 않을 수 있습니다. 예: {', '.join(missing[:10])}"
        )

    final_translations: dict[str, str] = dict(cache)
    final_translations.update(already_noted)

    all_chunks = pipeline.build_chunks(note_blocks, max(2000, args.max_chars_per_chunk))
    chunks_to_process = all_chunks[: args.limit_chunks] if args.limit_chunks else all_chunks
    print(f"note chunks to process: {len(chunks_to_process)}/{len(all_chunks)}", flush=True)
    errors: list[dict[str, object]] = []

    for chunk in all_chunks:
        out_path = work_dir / "translations" / f"chunk_{chunk.index:04d}.json"
        if cached_note_chunk_is_complete(out_path, chunk.block_ids):
            apply_cached_note_chunk(out_path, chunk.block_ids, cache, final_translations)

    pending_chunks = [
        chunk
        for chunk in chunks_to_process
        if not cached_note_chunk_is_complete(
            work_dir / "translations" / f"chunk_{chunk.index:04d}.json",
            chunk.block_ids,
        )
    ]
    completed_count = len(all_chunks) - len(
        [
            chunk
            for chunk in all_chunks
            if not cached_note_chunk_is_complete(
                work_dir / "translations" / f"chunk_{chunk.index:04d}.json",
                chunk.block_ids,
            )
        ]
    )
    diagnostics.progress(
        stage="request_notes" if pending_chunks else "validate_cache",
        completed=completed_count,
        total=len(all_chunks),
        current=pending_chunks[0].index if pending_chunks else None,
        detail=f"pending={len(pending_chunks)}",
        success=completed_count > 0,
    )
    pipeline.beat_heartbeat(
        heartbeat,
        stage="backfill_resume",
        label=f"{completed_count}/{len(all_chunks)}",
        detail=f"pending={len(pending_chunks)}",
    )
    if pending_chunks:
        provider = pipeline.active_web_provider(args)
        if provider == "gemini":
            browser_cookie3, sync_playwright, timeout_error_cls = pipeline.load_gemini_web_modules()
            chrome_path = args.gemini_web_chrome_path
        else:
            browser_cookie3, sync_playwright, timeout_error_cls = pipeline.load_chatgpt_web_modules()
            chrome_path = args.chatgpt_web_chrome_path

        with sync_playwright() as playwright:
            context = pipeline.launch_persistent_web_context(
                playwright,
                provider=provider,
                chrome_path=chrome_path,
                visible=args.web_visible,
            )
            try:
                pipeline.ensure_web_provider_session(
                    context,
                    provider=provider,
                    timeout_error_cls=timeout_error_cls,
                    browser_cookie3_module=browser_cookie3,
                    heartbeat=heartbeat,
                )
                consecutive_failures = 0
                for chunk in pending_chunks:
                    prefix = f"notes_chunk_{chunk.index:04d}"
                    out_path = work_dir / "translations" / f"chunk_{chunk.index:04d}.json"
                    prompt = build_note_prompt(chunk, len(all_chunks), book_title)
                    refusal_retry_prompt = build_note_prompt(
                        chunk,
                        len(all_chunks),
                        book_title,
                        safety_retry=True,
                    )
                    pipeline.write_text(work_dir / "prompts" / f"{prefix}_prompt.txt", prompt)

                    try:
                        conversation_id, notes = request_note_chunk(
                            context=context,
                            timeout_error_cls=timeout_error_cls,
                            args=args,
                            prompt=prompt,
                            refusal_retry_prompt=refusal_retry_prompt,
                            chunk=chunk,
                            chunk_count=len(all_chunks),
                            work_dir=work_dir,
                            max_attempts=args.note_max_attempts,
                            heartbeat=heartbeat,
                        )
                    except Exception as exc:
                        if isinstance(exc, pipeline.OvernightProviderSwitch):
                            diagnostics.record_failure(
                                exc,
                                stage=f"학습노트 {chunk.index}/{len(all_chunks)}",
                                attempt=1,
                                max_attempts=1,
                                explicit_kind="gemini_outage",
                                explicit_action="cooldown_profile_then_resume_from_cache",
                            )
                        errors.append(
                            {
                                "chunk_index": chunk.index,
                                "kind": pipeline.classify_translation_web_error(exc, chunk)[0],
                                "error": str(exc)[:1000],
                            }
                        )
                        write_backfill_status(work_dir, all_chunks, errors=errors)
                        print(f"FAILED {prefix}: {exc}", flush=True)
                        if (
                            isinstance(exc, pipeline.OvernightProviderSwitch)
                            or pipeline.is_web_provider_pause_error(exc)
                        ):
                            raise
                        consecutive_failures += 1
                        if consecutive_failures >= 5:
                            raise SystemExit(
                                f"{prefix}까지 연속 {consecutive_failures}개 청크 실패 - 중단 후 "
                                f"재실행이 필요합니다. 마지막 오류: {exc}"
                            ) from exc
                        continue
                    consecutive_failures = 0

                    pipeline.write_json(
                        out_path,
                        {
                            "chunk_index": chunk.index,
                            "chunk_count": len(all_chunks),
                            "conversation_id": conversation_id,
                            "pipeline_version": pipeline.TRANSLATION_PIPELINE_VERSION,
                            "block_ids": chunk.block_ids,
                            "translations": notes,
                        },
                    )
                    apply_cached_note_chunk(out_path, chunk.block_ids, cache, final_translations)
                    write_backfill_status(work_dir, all_chunks, errors=errors)
                    diagnostics.progress(
                        stage="request_notes",
                        completed=sum(
                            cached_note_chunk_is_complete(
                                work_dir / "translations" / f"chunk_{item.index:04d}.json",
                                item.block_ids,
                            )
                            for item in all_chunks
                        ),
                        total=len(all_chunks),
                        current=chunk.index,
                        detail=f"completed={prefix}",
                        success=True,
                    )
                    pipeline.beat_heartbeat(
                        heartbeat,
                        stage="backfill_chunk_complete",
                        label=f"{chunk.index}/{len(all_chunks)}",
                        section_prefix=prefix,
                    )
                    print(f"OK {prefix}", flush=True)
                    pipeline.pace_web_requests(
                        args,
                        heartbeat,
                        label=f"학습노트 {chunk.index}/{len(all_chunks)}",
                        prefix=prefix,
                        index=chunk.index,
                    )
            finally:
                context.close()

    incomplete_chunks = write_backfill_status(work_dir, all_chunks, errors=errors)
    if incomplete_chunks:
        error = RuntimeError(
            f"학습노트 청크 {len(incomplete_chunks)}/{len(all_chunks)}개가 아직 불완전합니다."
        )
        diagnostics.record_failure(
            error,
            stage="validate_cache",
            attempt=1,
            max_attempts=1,
            explicit_kind="missing_translation_ids",
            evidence={"incomplete_chunks": incomplete_chunks[:50]},
        )
        raise SystemExit(
            f"학습노트 청크 {len(incomplete_chunks)}/{len(all_chunks)}개가 불완전하여 EPUB를 "
            f"생성하지 않습니다. 재실행하면 성공 캐시를 유지한 채 이어집니다. "
            f"예: {', '.join(f'{index:04d}' for index in incomplete_chunks[:10])}"
        )

    pipeline.fill_separator_translations(blocks, final_translations)
    missing_final = [block.id for block in blocks if not final_translations.get(block.id)]
    if missing_final:
        raise SystemExit(f"최종 번역 누락 블록 {len(missing_final)}개: {', '.join(missing_final[:10])}")

    pipeline.build_epub(
        output_epub=args.output_epub,
        book_title=book_title,
        ko_book_title=ko_book_title,
        creator=creator,
        sections=sections,
        translations=final_translations,
        input_epub=input_epub,
    )
    cleanup = pipeline.scrub_epub(args.output_epub)
    if str(cleanup.get("status") or "").startswith("error:"):
        raise RuntimeError(f"[k-e] 워터마크 삭제 검증 실패: {cleanup['status']}")

    if args.study_output_epub:
        pipeline.build_epub(
            output_epub=args.study_output_epub,
            book_title=book_title,
            ko_book_title=ko_book_title,
            creator=creator,
            sections=sections,
            translations=final_translations,
            input_epub=input_epub,
            include_study_notes=True,
        )
        study_cleanup = pipeline.scrub_epub(args.study_output_epub)
        if str(study_cleanup.get("status") or "").startswith("error:"):
            raise RuntimeError(f"[study] 워터마크 삭제 검증 실패: {study_cleanup['status']}")

    diagnostics.complete(
        stage="complete",
        artifacts={
            "output_epub": str(args.output_epub),
            "study_output_epub": str(args.study_output_epub) if args.study_output_epub else None,
        },
    )
    pipeline.beat_heartbeat(heartbeat, stage="complete", detail=str(args.output_epub))
    print(
        json.dumps(
            {
                "output_epub": str(args.output_epub),
                "study_epub": str(args.study_output_epub) if args.study_output_epub else None,
                "section_count": len(sections),
                "block_count": len(blocks),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


def build_pipeline_args(*, input_epub: Path, output_epub: Path, work_dir: Path,
                         web_provider: str, web_visible: bool) -> argparse.Namespace:
    old_argv = sys.argv
    try:
        sys.argv = [
            "backfill_study_notes",
            "--input-epub", str(input_epub),
            "--output-epub", str(output_epub),
            "--work-dir", str(work_dir),
            "--web-provider", web_provider,
        ]
        if web_visible:
            sys.argv.append("--web-visible")
        return pipeline.parse_args()
    finally:
        sys.argv = old_argv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-epub", type=Path, required=True)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-work-dir", type=Path,
                              help="기존 (학습노트 없는) 번역 캐시가 있는 work-dir")
    source_group.add_argument("--live-k-e-epub", type=Path,
                              help="--source-work-dir 대신, 이미 서재에 있는 [k-e] EPUB에서 직접 "
                                   "en/ko 쌍을 추출해 소스로 쓴다(완전한 번역 캐시가 남아있지 않은 책용)")
    parser.add_argument("--work-dir", type=Path, required=True,
                         help="새 학습노트 캐시를 저장할 work-dir")
    parser.add_argument("--output-epub", type=Path, required=True)
    parser.add_argument("--study-output-epub", type=Path)
    parser.add_argument("--heartbeat-file", type=Path)
    parser.add_argument("--book-title-ko")
    parser.add_argument("--web-provider", default="chatgpt", choices=("gemini", "chatgpt"))
    parser.add_argument(
        "--web-visible",
        action="store_true",
        default=True,
        help="호환성 옵션입니다. 웹 번역 Chrome은 항상 일반 표시 창으로 실행됩니다.",
    )
    parser.add_argument("--max-chars-per-chunk", type=int, default=6000)
    parser.add_argument("--web-max-attempts", type=int, default=pipeline.DEFAULT_CHATGPT_WEB_MAX_ATTEMPTS)
    parser.add_argument("--inter-request-delay-sec", type=float, default=4.0)
    parser.add_argument("--provider-fallback-state-dir", type=Path)
    parser.add_argument("--note-max-attempts", type=int, default=3,
                        help="응답 ID 형식 오류에 대한 청크별 재시도 횟수")
    parser.add_argument(
        "--chatgpt-account-tier",
        choices=("paid", "free"),
        default=os.environ.get("AUDIOBOOK_CHATGPT_ACCOUNT_TIER", "paid").strip().lower(),
    )
    parser.add_argument("--chatgpt-free-tier-message-limit", type=int, default=25)
    parser.add_argument("--chatgpt-free-tier-window-hours", type=float, default=3.0)
    parser.add_argument("--limit-chunks", type=int, default=0, help="테스트용: 앞쪽 N개 청크만 처리")
    cli_args = parser.parse_args()

    pipeline_args = build_pipeline_args(
        input_epub=cli_args.input_epub,
        output_epub=cli_args.output_epub,
        work_dir=cli_args.work_dir,
        web_provider=cli_args.web_provider,
        web_visible=cli_args.web_visible,
    )
    pipeline_args.input_epub = cli_args.input_epub
    pipeline_args.output_epub = cli_args.output_epub
    pipeline_args.source_work_dir = cli_args.source_work_dir
    pipeline_args.live_k_e_epub = cli_args.live_k_e_epub
    pipeline_args.work_dir = cli_args.work_dir
    pipeline_args.study_output_epub = cli_args.study_output_epub
    pipeline_args.heartbeat_file = cli_args.heartbeat_file or (cli_args.work_dir / "heartbeat.json")
    pipeline_args.book_title_ko = cli_args.book_title_ko
    pipeline_args.max_chars_per_chunk = cli_args.max_chars_per_chunk
    pipeline_args.web_max_attempts = max(1, cli_args.web_max_attempts)
    pipeline_args.inter_request_delay_sec = max(0.0, cli_args.inter_request_delay_sec)
    pipeline_args.provider_fallback_state_dir = cli_args.provider_fallback_state_dir
    pipeline_args.limit_chunks = cli_args.limit_chunks
    pipeline_args.note_max_attempts = max(1, cli_args.note_max_attempts)
    pipeline_args.chatgpt_account_tier = cli_args.chatgpt_account_tier
    pipeline_args.chatgpt_free_tier_message_limit = cli_args.chatgpt_free_tier_message_limit
    pipeline_args.chatgpt_free_tier_window_hours = cli_args.chatgpt_free_tier_window_hours

    work_dir = cli_args.work_dir.expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    translation_lock = pipeline.acquire_translation_lock(work_dir)
    try:
        try:
            return run(pipeline_args)
        except BaseException as exc:
            current = load_workflow_diagnostics(work_dir)
            incidents = current.get("incidents") if isinstance(current.get("incidents"), list) else []
            latest_error = str(incidents[-1].get("error") or "") if incidents else ""
            if str(exc) and str(exc) != latest_error:
                WorkflowDiagnostics(work_dir, "study_note_backfill").record_current_exception(
                    exc,
                    stage=str(current.get("current_stage") or "unhandled_failure"),
                )
            raise
    finally:
        translation_lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
