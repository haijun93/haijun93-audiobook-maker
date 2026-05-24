#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_maker import (
    CHATGPT_WEB_CHROME_PATH,
    DEFAULT_CHATGPT_WEB_MAX_ATTEMPTS,
    ProgressHeartbeat,
    beat_heartbeat,
    chatgpt_web_launch_args,
    extract_chatgpt_conversation_id,
    input_file_format,
    is_chatgpt_web_refusal_response,
    load_chatgpt_web_cookies,
    load_chatgpt_web_modules,
    load_source_text,
    normalized_file_text,
    prepare_chatgpt_web_page,
    send_chatgpt_web_prompt,
    split_into_sections,
    wait_for_chatgpt_web_response,
)


DEFAULT_ANALYSIS_INSTRUCTIONS = """당신은 문서 분석 전문가입니다.
아래에 제공되는 문서 내용을 바탕으로 학습자에게 실제로 도움이 되는 분석만 작성하세요.

분석 원칙:
1. 문서에 실제로 있는 내용만 바탕으로 분석합니다.
2. 문서의 핵심 주제, 구조, 반복되는 쟁점, 암기 포인트, 비교해서 봐야 할 부분을 정리합니다.
3. 불필요한 칭찬, 메타 코멘트, 추상적인 조언은 넣지 않습니다.
4. 이해를 돕기 위해 표가 유리한 경우 Markdown 표를 사용합니다.
5. 문서가 시험 대비 자료라면 출제 포인트, 혼동하기 쉬운 지점, 회독 순서를 우선 정리합니다.
6. 결과는 한국어 Markdown으로 작성합니다.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DOCX/PDF/EPUB/TXT 문서를 ChatGPT 웹 서비스로 분석합니다."
    )
    parser.add_argument("--input-file", type=Path, required=True, help="분석할 입력 문서 경로")
    parser.add_argument("--output-file", type=Path, help="분석 결과 출력 파일 경로(.md/.txt)")
    parser.add_argument("--work-dir", type=Path, help="중간 프롬프트/응답 저장 폴더")
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=6000,
        help="문서 분석용 세그먼트 최대 글자 수(기본: 6000)",
    )
    parser.add_argument(
        "--request-timeout-sec",
        type=int,
        default=900,
        help="각 분석 요청의 응답 대기 시간(초, 기본: 900)",
    )
    parser.add_argument(
        "--chatgpt-web-chrome-path",
        default=CHATGPT_WEB_CHROME_PATH,
        help="ChatGPT 웹 자동화에 사용할 Chrome 실행 파일 경로",
    )
    parser.add_argument(
        "--chatgpt-web-visible",
        action="store_true",
        help="기본값은 창을 화면 밖으로 띄웁니다. 이 옵션을 주면 보이게 실행합니다.",
    )
    parser.add_argument(
        "--chatgpt-web-max-attempts",
        type=int,
        default=DEFAULT_CHATGPT_WEB_MAX_ATTEMPTS,
        help=f"ChatGPT 웹 분석 재시도 횟수(기본: {DEFAULT_CHATGPT_WEB_MAX_ATTEMPTS})",
    )
    parser.add_argument(
        "--analysis-instructions",
        default=DEFAULT_ANALYSIS_INSTRUCTIONS,
        help="문서 분석 시 함께 보낼 추가 지침",
    )
    parser.add_argument(
        "--analysis-instructions-file",
        type=Path,
        help="문서 분석 지침 파일 경로. 주어지면 --analysis-instructions 대신 사용합니다.",
    )
    parser.add_argument(
        "--final-format",
        choices=("markdown", "text"),
        default="markdown",
        help="최종 분석 결과 포맷 힌트(기본: markdown)",
    )
    parser.add_argument(
        "--heartbeat-file",
        type=Path,
        help="외부 watchdog가 진행 상태를 감시할 heartbeat 파일 경로",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="중간 산출물 폴더를 유지합니다. 기본도 유지이지만 명시적으로 남길 때 사용합니다.",
    )
    return parser.parse_args()


def resolve_output_file(args: argparse.Namespace) -> Path:
    if args.output_file:
        return args.output_file.expanduser().resolve()
    suffix = ".analysis.md" if args.final_format == "markdown" else ".analysis.txt"
    return args.input_file.expanduser().resolve().with_suffix(suffix)


def resolve_work_dir(args: argparse.Namespace, output_file: Path) -> Path:
    if args.work_dir:
        return args.work_dir.expanduser().resolve()
    base_name = output_file.name.rsplit(".", 1)[0]
    return output_file.parent / f"{base_name}_work"


def read_analysis_instructions(args: argparse.Namespace) -> str:
    if args.analysis_instructions_file:
        return args.analysis_instructions_file.expanduser().read_text(encoding="utf-8").strip()
    return str(args.analysis_instructions).strip()


def load_document_text(path: Path) -> str:
    ns = SimpleNamespace(text=None, input_file=path.expanduser().resolve())
    return normalized_file_text(load_source_text(ns))


def build_analysis_sections(text: str, max_chars: int) -> list[str]:
    return [section.text for section in split_into_sections(text, max_chars=max_chars) if section.text.strip()]


def build_chunk_analysis_prompt(
    *,
    input_name: str,
    instructions: str,
    chunk_text: str,
    chunk_index: int,
    chunk_count: int,
    final_format: str,
) -> str:
    return f"""다음은 문서 `{input_name}`의 일부입니다.
전체 {chunk_count}개 조각 중 {chunk_index}번째 조각입니다.

분석 지침:
{instructions}

이 조각에 대해서만 다음을 정리하세요.
- 이 조각의 핵심 주제
- 중요한 개념, 숫자, 절차, 비교 포인트
- 앞뒤 조각과 합쳤을 때 최종 문서 분석에 반드시 남겨야 할 내용

응답 형식:
- {final_format} 형식 유지
- 장황한 서론 없이 바로 분석 시작
- 이 조각에 없는 내용은 추측하지 말 것

문서 조각:
{chunk_text}
"""


def build_final_analysis_prompt(
    *,
    input_name: str,
    instructions: str,
    chunk_summaries: list[str],
    final_format: str,
) -> str:
    joined = "\n\n".join(
        f"## 조각 {index}\n{summary.strip()}" for index, summary in enumerate(chunk_summaries, start=1)
    )
    return f"""다음은 문서 `{input_name}`를 여러 조각으로 나누어 분석한 결과입니다.
이제 전체 문서 관점에서 최종 분석본을 하나로 통합하세요.

최종 분석 지침:
{instructions}

최종 결과에는 다음이 포함되면 좋습니다.
- 문서 전체 구조 요약
- 학습자 또는 독자가 바로 활용할 핵심 요점
- 비교해서 봐야 하는 내용
- 반복적으로 등장하는 포인트
- 회독 또는 검토 순서 제안(문서 성격상 필요한 경우)

응답 형식:
- {final_format} 형식 유지
- 조각별 반복 문장은 합쳐서 정리
- 중복 없는 최종본으로 작성
- 문서에 실제로 있는 정보만 사용

조각별 분석:
{joined}
"""


def write_artifact(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def request_chatgpt_web_analysis(
    *,
    context,
    timeout_error_cls,
    chrome_args: argparse.Namespace,
    prompt: str,
    heartbeat: ProgressHeartbeat | None,
    label: str,
    prefix: str,
) -> tuple[str, str]:
    max_attempts = max(1, int(chrome_args.chatgpt_web_max_attempts))
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        page = context.new_page()
        try:
            beat_heartbeat(
                heartbeat,
                stage="analysis_attempt_start",
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            prepare_chatgpt_web_page(
                page,
                timeout_error_cls=timeout_error_cls,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            send_chatgpt_web_prompt(
                page,
                prompt,
                timeout_error_cls=timeout_error_cls,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            message_id, response_text = wait_for_chatgpt_web_response(
                page,
                timeout_sec=chrome_args.request_timeout_sec,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            conversation_id = extract_chatgpt_conversation_id(page.url)
            if not conversation_id:
                raise RuntimeError("ChatGPT conversation_id 를 찾지 못했습니다.")
            if not message_id:
                raise RuntimeError("ChatGPT message_id 를 찾지 못했습니다.")
            if not normalized_file_text(response_text):
                raise RuntimeError("ChatGPT 분석 응답이 비어 있습니다.")
            if is_chatgpt_web_refusal_response(response_text):
                preview = normalized_file_text(response_text)[:200].replace("\n", " ")
                raise RuntimeError(f"ChatGPT 분석 응답이 거절되었습니다: {preview}")
            beat_heartbeat(
                heartbeat,
                stage="analysis_response_received",
                label=label,
                section_prefix=prefix,
                attempt=attempt,
                detail=f"message_id={message_id}",
            )
            return conversation_id, response_text
        except Exception as exc:
            last_error = exc
            beat_heartbeat(
                heartbeat,
                stage="analysis_attempt_error",
                label=label,
                section_prefix=prefix,
                attempt=attempt,
                detail=str(exc)[:300],
            )
        finally:
            page.close()

    if last_error is not None:
        raise last_error
    raise RuntimeError("ChatGPT 웹 문서 분석에 실패했습니다.")


def write_manifest(
    *,
    manifest_path: Path,
    args: argparse.Namespace,
    input_file: Path,
    output_file: Path,
    work_dir: Path,
    chunk_count: int,
) -> None:
    payload = {
        "provider": "chatgpt_web",
        "input_file": str(input_file),
        "input_format": input_file_format(input_file),
        "output_file": str(output_file),
        "work_dir": str(work_dir),
        "chunk_count": chunk_count,
        "request_timeout_sec": args.request_timeout_sec,
        "chatgpt_web_visible": bool(args.chatgpt_web_visible),
        "chatgpt_web_max_attempts": int(args.chatgpt_web_max_attempts),
        "chatgpt_web_chrome_path": str(args.chatgpt_web_chrome_path),
        "max_chars_per_chunk": int(args.max_chars_per_chunk),
        "final_format": args.final_format,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_file = args.input_file.expanduser().resolve()
    if not input_file.exists():
        raise SystemExit(f"입력 문서를 찾지 못했습니다: {input_file}")

    output_file = resolve_output_file(args)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    work_dir = resolve_work_dir(args, output_file)
    work_dir.mkdir(parents=True, exist_ok=True)

    heartbeat = ProgressHeartbeat(args.heartbeat_file) if args.heartbeat_file else None
    instructions = read_analysis_instructions(args)
    document_text = load_document_text(input_file)
    if not document_text.strip():
        raise SystemExit(f"문서에서 분석 가능한 텍스트를 찾지 못했습니다: {input_file}")

    sections = build_analysis_sections(document_text, max_chars=max(1200, int(args.max_chars_per_chunk)))
    if not sections:
        sections = [document_text]

    manifest_path = work_dir / "analysis_manifest.json"
    write_manifest(
        manifest_path=manifest_path,
        args=args,
        input_file=input_file,
        output_file=output_file,
        work_dir=work_dir,
        chunk_count=len(sections),
    )

    browser_cookie3, sync_playwright, timeout_error_cls = load_chatgpt_web_modules()
    cookies = load_chatgpt_web_cookies(browser_cookie3)

    chunk_outputs: list[str] = []
    beat_heartbeat(heartbeat, stage="analysis_browser_launch", detail="playwright_start")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            executable_path=str(Path(args.chatgpt_web_chrome_path).expanduser()),
            args=chatgpt_web_launch_args(visible=args.chatgpt_web_visible),
        )
        context = None
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 1200})
            context.add_cookies(cookies)

            for index, section_text in enumerate(sections, start=1):
                prefix = f"chunk_{index:03d}"
                prompt = build_chunk_analysis_prompt(
                    input_name=input_file.name,
                    instructions=instructions,
                    chunk_text=section_text,
                    chunk_index=index,
                    chunk_count=len(sections),
                    final_format=args.final_format,
                )
                write_artifact(work_dir / f"{prefix}_prompt.txt", prompt)
                conversation_id, response_text = request_chatgpt_web_analysis(
                    context=context,
                    timeout_error_cls=timeout_error_cls,
                    chrome_args=args,
                    prompt=prompt,
                    heartbeat=heartbeat,
                    label=f"문서분석 {index}/{len(sections)}",
                    prefix=prefix,
                )
                write_artifact(work_dir / f"{prefix}_response.txt", response_text)
                write_artifact(
                    work_dir / f"{prefix}_meta.json",
                    json.dumps(
                        {
                            "conversation_id": conversation_id,
                            "chunk_index": index,
                            "chunk_count": len(sections),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
                chunk_outputs.append(response_text.strip())

            if len(chunk_outputs) == 1:
                final_response = chunk_outputs[0].strip()
            else:
                final_prompt = build_final_analysis_prompt(
                    input_name=input_file.name,
                    instructions=instructions,
                    chunk_summaries=chunk_outputs,
                    final_format=args.final_format,
                )
                write_artifact(work_dir / "final_prompt.txt", final_prompt)
                _, final_response = request_chatgpt_web_analysis(
                    context=context,
                    timeout_error_cls=timeout_error_cls,
                    chrome_args=args,
                    prompt=final_prompt,
                    heartbeat=heartbeat,
                    label="문서분석 최종정리",
                    prefix="final",
                )
                write_artifact(work_dir / "final_response.txt", final_response)
                final_response = final_response.strip()
        finally:
            if context is not None:
                context.close()
            browser.close()

    output_file.write_text(final_response.rstrip() + "\n", encoding="utf-8")
    beat_heartbeat(heartbeat, stage="analysis_complete", detail=str(output_file))
    print(f"input: {input_file}", file=sys.stderr)
    print(f"output: {output_file}", file=sys.stderr)
    print(f"work_dir: {work_dir}", file=sys.stderr)
    print(f"chunks: {len(sections)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
