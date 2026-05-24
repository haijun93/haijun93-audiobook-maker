#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_maker import (
    CHATGPT_WEB_CHROME_PATH,
    DEFAULT_CHATGPT_WEB_MAX_ATTEMPTS,
    GEMINI_WEB_CHROME_PATH,
    ProgressHeartbeat,
    beat_heartbeat,
    chatgpt_web_launch_args,
    extract_chatgpt_conversation_id,
    extract_gemini_web_conversation_id,
    input_file_format,
    is_chatgpt_web_refusal_response,
    load_browser_cookies,
    load_chatgpt_web_cookies,
    load_chatgpt_web_modules,
    load_gemini_web_cookies,
    load_gemini_web_modules,
    load_source_text,
    normalized_file_text,
    prepare_chatgpt_web_page,
    prepare_gemini_web_page,
    send_chatgpt_web_prompt,
    send_gemini_web_prompt,
    split_into_sections,
    wait_for_chatgpt_web_response,
    wait_for_gemini_web_response,
)


CLAUDE_WEB_URL = "https://claude.ai/new"
CLAUDE_WEB_PROMPT_SELECTORS = (
    'div[contenteditable="true"][data-slate-editor="true"]',
    'div[contenteditable="true"][role="textbox"]',
    'div[contenteditable="true"]',
    'textarea',
)
CLAUDE_WEB_RESPONSE_SELECTORS = (
    '[data-testid="assistant-message"]',
    '[data-testid="message-content"]',
    'article[data-testid*="message"]',
    'main article',
)
CLAUDE_WEB_SEND_BUTTON_SELECTORS = (
    'button[aria-label*="Send"]',
    'button[aria-label*="전송"]',
    'button[data-testid*="send"]',
    'form button[type="submit"]',
)
CLAUDE_WEB_USAGE_LIMIT_MARKERS = (
    "usage limit",
    "message limit",
    "rate limit",
    "too many requests",
    "try again later",
    "limit reached",
    "usage cap",
    "resets at",
    "reset at",
    "high demand",
    "temporarily unavailable",
    "upgrade to claude",
    "upgrade your plan",
    "please try again in a little while",
    "한도",
    "사용량 제한",
    "메시지 제한",
    "잠시 후 다시",
)

DEFAULT_CLAUDE_DEEP_TIMEOUT_SEC = 180

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


class ClaudeWebUsageLimitError(RuntimeError):
    """Claude 웹 사용량 한도로 인해 해당 단계를 건너뛰어야 할 때 발생한다."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="문서를 웹 LLM 서비스로 분석합니다. basic=ChatGPT 웹, deep=ChatGPT→클라우드(Claude) 웹→Gemini 웹."
    )
    parser.add_argument("--input-file", type=Path, required=True, help="분석할 입력 문서 경로")
    parser.add_argument("--output-file", type=Path, help="분석 결과 출력 파일 경로(.md/.txt)")
    parser.add_argument("--work-dir", type=Path, help="중간 프롬프트/응답 저장 폴더")
    parser.add_argument(
        "--analysis-mode",
        choices=("basic", "deep"),
        default="basic",
        help="basic=ChatGPT 웹 기본 분석, deep=ChatGPT→클라우드(Claude) 웹→Gemini 웹 심화 분석",
    )
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
        "--gemini-web-chrome-path",
        default=GEMINI_WEB_CHROME_PATH,
        help="Gemini 웹 자동화에 사용할 Chrome 실행 파일 경로",
    )
    parser.add_argument(
        "--claude-web-chrome-path",
        default=CHATGPT_WEB_CHROME_PATH,
        help="Claude 웹 자동화에 사용할 Chrome 실행 파일 경로",
    )
    parser.add_argument("--chatgpt-web-visible", action="store_true")
    parser.add_argument("--gemini-web-visible", action="store_true")
    parser.add_argument("--claude-web-visible", action="store_true")
    parser.add_argument(
        "--chatgpt-web-max-attempts",
        type=int,
        default=DEFAULT_CHATGPT_WEB_MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--gemini-web-max-attempts",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--claude-web-max-attempts",
        type=int,
        default=5,
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
        "--apply-results-to-docx-pdf",
        action="store_true",
        help="심화분석 완료 후 분석 결과를 원본 DOCX와 PDF에 자동 반영합니다.",
    )
    parser.add_argument(
        "--no-pdf-after-apply",
        action="store_true",
        help="자동 반영 시 DOCX만 갱신하고 PDF는 만들지 않습니다.",
    )
    parser.add_argument(
        "--apply-section-title",
        default="문서심화분석 반영",
        help="자동 반영 시 DOCX에 추가/교체할 섹션 제목",
    )
    return parser.parse_args()


def analysis_provider_sequence(mode: str) -> tuple[str, ...]:
    if mode == "deep":
        return ("chatgpt_web", "claude_web", "gemini_web")
    return ("chatgpt_web",)


def resolve_output_file(args: argparse.Namespace) -> Path:
    if args.output_file:
        return args.output_file.expanduser().resolve()
    suffix = ".analysis.md" if args.final_format == "markdown" else ".analysis.txt"
    if args.analysis_mode == "deep":
        suffix = ".deep" + suffix[len(".analysis") :]
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
    text = normalized_file_text(load_source_text(ns))
    stem = path.stem.lower()
    if "ox" in stem:
        trimmed = trim_to_first_question(text)
        if trimmed:
            return trimmed
    return text


def trim_to_first_question(text: str) -> str:
    body_markers = ("Ⅷ. OX 본문", "VII. OX 본문", "OX 본문", "문제 본문")
    for marker in body_markers:
        idx = text.find(marker)
        if idx >= 0:
            text = text[idx + len(marker) :].strip()
            break
    patterns = (
        r"(?m)^(?:문제\s*)?1\.\s+",
        r"(?m)^(?:문제\s*)?1\)\s+",
        r"(?m)^1\s*[-–]\s+",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return text[match.start() :].strip()
    return text.strip()


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


def build_review_prompt(
    *,
    provider: str,
    input_name: str,
    instructions: str,
    chunk_text: str,
    prior_outputs: list[tuple[str, str]],
    final_format: str,
) -> str:
    joined = "\n\n".join(f"## {name}\n{text.strip()}" for name, text in prior_outputs)
    provider_name = {
        "claude_web": "Claude 웹",
        "gemini_web": "Gemini 웹",
    }.get(provider, provider)
    return f"""다음은 문서 `{input_name}`의 한 조각과 그에 대한 선행 분석 결과입니다.
당신은 {provider_name} 검토 단계입니다.

검토 지침:
{instructions}

당신의 역할:
1. 앞선 분석의 누락, 오해, 중복을 점검합니다.
2. 문서 조각 원문과 대조하여 틀린 해석이 있으면 바로잡습니다.
3. 더 명확하고 더 압축된 최종 조각 분석본을 만듭니다.

응답 형식:
- {final_format} 형식 유지
- '누락/오류 점검' 같은 메타 설명 없이 바로 개선된 분석본만 출력

문서 조각:
{chunk_text}

선행 분석:
{joined}
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


def build_final_review_prompt(
    *,
    provider: str,
    input_name: str,
    instructions: str,
    prior_outputs: list[tuple[str, str]],
    final_format: str,
) -> str:
    joined = "\n\n".join(f"## {name}\n{text.strip()}" for name, text in prior_outputs)
    provider_name = {
        "claude_web": "Claude 웹",
        "gemini_web": "Gemini 웹",
    }.get(provider, provider)
    return f"""다음은 문서 `{input_name}`의 전체 분석본 초안과 검토본입니다.
당신은 {provider_name} 최종 검증 단계입니다.

검증 지침:
{instructions}

당신의 역할:
1. 초안과 검토본을 비교하여 문서 내용에 맞는 방향으로 정리합니다.
2. 중복, 군더더기, 불필요한 메타 표현을 없앱니다.
3. 문서 기반 최종 분석본만 출력합니다.

응답 형식:
- {final_format} 형식 유지
- 검토 의견을 따로 쓰지 말고 최종본만 출력

이전 단계 결과:
{joined}
"""


def write_artifact(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def load_claude_web_cookies(browser_cookie3_module) -> list[dict[str, object]]:
    return load_browser_cookies(
        browser_cookie3_module,
        domain_names=("claude.ai",),
        read_error_prefix="Chrome 에서 Claude 웹 쿠키를 읽지 못했습니다",
        missing_error="Chrome 에 로그인된 claude.ai 쿠키를 찾지 못했습니다.",
    )


def _first_visible_locator(page, selectors: tuple[str, ...]):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count() and locator.is_visible():
                return locator
        except Exception:
            continue
    return None


def read_page_body_text(page) -> str:
    try:
        return normalized_file_text(page.locator("body").inner_text(timeout=5_000))
    except Exception:
        return ""


def is_claude_web_usage_limit_text(text: str) -> bool:
    normalized = normalized_file_text(text)
    lowered = normalized.lower()
    if not normalized:
        return False
    return any(marker in lowered for marker in CLAUDE_WEB_USAGE_LIMIT_MARKERS)


def claude_web_usage_limit_message(page, exc: Exception | None = None) -> str | None:
    candidates: list[str] = []
    if exc is not None:
        candidates.append(str(exc))
    body_text = read_page_body_text(page)
    if body_text:
        candidates.append(body_text)
    for candidate in candidates:
        if is_claude_web_usage_limit_text(candidate):
            return normalized_file_text(candidate)
    return None


def prepare_claude_web_page(
    page,
    *,
    timeout_error_cls,
    heartbeat: ProgressHeartbeat | None = None,
    label: str | None = None,
    section_prefix: str | None = None,
    attempt: int | None = None,
) -> None:
    beat_heartbeat(
        heartbeat,
        stage="open_page",
        label=label,
        section_prefix=section_prefix,
        attempt=attempt,
        detail="claude_web_open",
    )
    page.goto(CLAUDE_WEB_URL, wait_until="domcontentloaded")
    if any(token in page.url for token in ("login", "auth", "signin")):
        raise RuntimeError("Claude 웹 로그인 페이지로 이동했습니다. Claude 세션을 확인하세요.")
    deadline = time.time() + 30
    while time.time() < deadline:
        locator = _first_visible_locator(page, CLAUDE_WEB_PROMPT_SELECTORS)
        if locator is not None:
            return
        page.wait_for_timeout(500)
    raise timeout_error_cls("Claude 웹 프롬프트 입력창을 찾지 못했습니다.")


def read_last_claude_response(page) -> str:
    for selector in CLAUDE_WEB_RESPONSE_SELECTORS:
        locator = page.locator(selector)
        try:
            count = locator.count()
        except Exception:
            count = 0
        if count < 1:
            continue
        texts: list[str] = []
        for index in range(count):
            try:
                text = locator.nth(index).inner_text().strip()
            except Exception:
                continue
            normalized = normalized_file_text(text)
            if normalized:
                texts.append(normalized)
        if texts:
            return texts[-1]
    return read_page_body_text(page)


def send_claude_web_prompt(
    page,
    prompt: str,
    *,
    timeout_error_cls,
    heartbeat: ProgressHeartbeat | None = None,
    label: str | None = None,
    section_prefix: str | None = None,
    attempt: int | None = None,
) -> int:
    prompt_locator = _first_visible_locator(page, CLAUDE_WEB_PROMPT_SELECTORS)
    if prompt_locator is None:
        raise TimeoutError("Claude 웹 프롬프트 입력창을 찾지 못했습니다.")
    previous_count = 0
    previous_text = read_last_claude_response(page)
    for selector in CLAUDE_WEB_RESPONSE_SELECTORS:
        try:
            previous_count = max(previous_count, page.locator(selector).count())
        except Exception:
            continue
    try:
        tag_name = (prompt_locator.evaluate("(el) => el.tagName") or "").lower()
    except Exception:
        tag_name = ""
    try:
        if tag_name == "textarea":
            prompt_locator.fill(prompt, timeout=30_000)
        else:
            prompt_locator.click(timeout=30_000)
            prompt_locator.evaluate(
                """(el, value) => {
                  el.focus();
                  el.textContent = value;
                  el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: value}));
                }""",
                prompt,
            )
    except timeout_error_cls as exc:
        raise TimeoutError("Claude 웹 프롬프트 입력에 실패했습니다.") from exc

    beat_heartbeat(
        heartbeat,
        stage="submit_prompt",
        label=label,
        section_prefix=section_prefix,
        attempt=attempt,
        detail=f"chars={len(prompt)}",
    )
    for selector in CLAUDE_WEB_SEND_BUTTON_SELECTORS:
        button = page.locator(selector).first
        try:
            if button.count() and button.is_visible():
                button.click(timeout=15_000)
                return previous_count
        except Exception:
            continue
    try:
        prompt_locator.press("Enter")
    except Exception as exc:
        raise RuntimeError("Claude 웹 전송 버튼을 찾지 못했습니다.") from exc
    return previous_count, previous_text


def wait_for_claude_web_response(
    page,
    *,
    previous_response_count: int,
    previous_response_text: str,
    timeout_sec: int,
    heartbeat: ProgressHeartbeat | None = None,
    label: str | None = None,
    section_prefix: str | None = None,
    attempt: int | None = None,
) -> str:
    deadline = time.time() + max(10, timeout_sec)
    last_text = ""
    stable_polls = 0
    baseline_text = normalized_file_text(previous_response_text)
    while time.time() < deadline:
        response_count = 0
        for selector in CLAUDE_WEB_RESPONSE_SELECTORS:
            try:
                response_count = max(response_count, page.locator(selector).count())
            except Exception:
                continue
        current_text = read_last_claude_response(page)
        if current_text and current_text == last_text:
            stable_polls += 1
        elif current_text:
            last_text = current_text
            stable_polls = 0
        beat_heartbeat(
            heartbeat,
            stage="wait_for_response",
            label=label,
            section_prefix=section_prefix,
            attempt=attempt,
            detail=f"stable_polls={stable_polls} chars={len(current_text)}",
        )
        current_normalized = normalized_file_text(current_text)
        is_new_response = bool(current_normalized and current_normalized != baseline_text)
        if current_text and stable_polls >= 2 and (response_count > previous_response_count or is_new_response):
            return current_text
        page.wait_for_timeout(1500)
    raise TimeoutError("Claude 웹 응답 완료를 기다리다 시간 초과되었습니다.")


def request_chatgpt_web_analysis(
    *,
    context,
    timeout_error_cls,
    args: argparse.Namespace,
    prompt: str,
    heartbeat: ProgressHeartbeat | None,
    label: str,
    prefix: str,
) -> dict[str, str]:
    max_attempts = max(1, int(args.chatgpt_web_max_attempts))
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        page = context.new_page()
        try:
            beat_heartbeat(heartbeat, stage="analysis_attempt_start", label=label, section_prefix=prefix, attempt=attempt)
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
                timeout_sec=args.request_timeout_sec,
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
            return {"conversation_id": conversation_id, "message_id": message_id, "response_text": response_text}
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
    if last_error:
        raise last_error
    raise RuntimeError("ChatGPT 웹 분석에 실패했습니다.")


def request_gemini_web_analysis(
    *,
    context,
    timeout_error_cls,
    args: argparse.Namespace,
    prompt: str,
    heartbeat: ProgressHeartbeat | None,
    label: str,
    prefix: str,
) -> dict[str, str]:
    max_attempts = max(1, int(args.gemini_web_max_attempts))
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        page = context.new_page()
        try:
            beat_heartbeat(heartbeat, stage="analysis_attempt_start", label=label, section_prefix=prefix, attempt=attempt)
            prepare_gemini_web_page(
                page,
                timeout_error_cls=timeout_error_cls,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            previous_response_count, previous_listen_count = send_gemini_web_prompt(
                page,
                prompt,
                timeout_error_cls=timeout_error_cls,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            response_text = wait_for_gemini_web_response(
                page,
                previous_response_count=previous_response_count,
                previous_listen_count=previous_listen_count,
                timeout_sec=args.request_timeout_sec,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            if not normalized_file_text(response_text):
                raise RuntimeError("Gemini 분석 응답이 비어 있습니다.")
            conversation_id = extract_gemini_web_conversation_id(page.url) or ""
            return {"conversation_id": conversation_id, "message_id": "", "response_text": response_text}
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
    if last_error:
        raise last_error
    raise RuntimeError("Gemini 웹 분석에 실패했습니다.")


def request_claude_web_analysis(
    *,
    context,
    timeout_error_cls,
    args: argparse.Namespace,
    prompt: str,
    heartbeat: ProgressHeartbeat | None,
    label: str,
    prefix: str,
) -> dict[str, str]:
    max_attempts = max(1, int(args.claude_web_max_attempts))
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        page = context.new_page()
        try:
            beat_heartbeat(heartbeat, stage="analysis_attempt_start", label=label, section_prefix=prefix, attempt=attempt)
            prepare_claude_web_page(
                page,
                timeout_error_cls=timeout_error_cls,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            previous_response_count, previous_response_text = send_claude_web_prompt(
                page,
                prompt,
                timeout_error_cls=timeout_error_cls,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            response_text = wait_for_claude_web_response(
                page,
                previous_response_count=previous_response_count,
                previous_response_text=previous_response_text,
                timeout_sec=args.request_timeout_sec,
                heartbeat=heartbeat,
                label=label,
                section_prefix=prefix,
                attempt=attempt,
            )
            if not normalized_file_text(response_text):
                raise RuntimeError("Claude 분석 응답이 비어 있습니다.")
            return {"conversation_id": page.url, "message_id": "", "response_text": response_text}
        except Exception as exc:
            usage_limit_message = claude_web_usage_limit_message(page, exc)
            if usage_limit_message:
                raise ClaudeWebUsageLimitError(usage_limit_message) from exc
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
    if last_error:
        raise last_error
    raise RuntimeError("Claude 웹 분석에 실패했습니다.")


def provider_request_fn(provider: str):
    if provider == "chatgpt_web":
        return request_chatgpt_web_analysis
    if provider == "claude_web":
        return request_claude_web_analysis
    if provider == "gemini_web":
        return request_gemini_web_analysis
    raise RuntimeError(f"지원하지 않는 분석 provider 입니다: {provider}")


def start_sync_playwright_compat(sync_playwright_factory):
    """Start Playwright sync API safely even if the host process already has a running loop."""

    original_get_running_loop = asyncio.get_running_loop
    original_check_running = asyncio.base_events.BaseEventLoop._check_running
    try:
        current_loop = original_get_running_loop()
        loop_running = current_loop.is_running()
    except RuntimeError:
        loop_running = False

    if not loop_running:
        manager = sync_playwright_factory()
        return manager, manager.start()

    first_call = True

    def _compat_get_running_loop():
        nonlocal first_call
        if first_call:
            first_call = False
            raise RuntimeError()
        return original_get_running_loop()

    asyncio.get_running_loop = _compat_get_running_loop
    asyncio.base_events.BaseEventLoop._check_running = lambda self: None
    try:
        manager = sync_playwright_factory()
        playwright = manager.start()
        return manager, playwright
    finally:
        asyncio.get_running_loop = original_get_running_loop
        asyncio.base_events.BaseEventLoop._check_running = original_check_running


def open_provider_context(provider: str, args: argparse.Namespace):
    if provider == "chatgpt_web":
        browser_cookie3, sync_playwright, timeout_error_cls = load_chatgpt_web_modules()
        cookies = load_chatgpt_web_cookies(browser_cookie3)
        chrome_path = args.chatgpt_web_chrome_path
        visible = args.chatgpt_web_visible
    elif provider == "claude_web":
        browser_cookie3, sync_playwright, timeout_error_cls = load_chatgpt_web_modules()
        cookies = load_claude_web_cookies(browser_cookie3)
        chrome_path = args.claude_web_chrome_path
        visible = args.claude_web_visible
    elif provider == "gemini_web":
        browser_cookie3, sync_playwright, timeout_error_cls = load_gemini_web_modules()
        cookies = load_gemini_web_cookies(browser_cookie3)
        chrome_path = args.gemini_web_chrome_path
        visible = args.gemini_web_visible
    else:
        raise RuntimeError(f"지원하지 않는 분석 provider 입니다: {provider}")
    playwright_manager, playwright = start_sync_playwright_compat(sync_playwright)
    browser = playwright.chromium.launch(
        headless=False,
        executable_path=str(Path(chrome_path).expanduser()),
        args=chatgpt_web_launch_args(visible=visible),
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1200})
    context.add_cookies(cookies)
    return playwright_manager, browser, context, timeout_error_cls


def write_json_artifact(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def close_provider_resource(resource) -> None:
    if not resource:
        return
    playwright_manager, browser, context, _ = resource
    try:
        context.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
    try:
        playwright_manager.stop()
    except Exception:
        pass


def execute_provider_request(
    *,
    provider: str,
    args: argparse.Namespace,
    prompt: str,
    heartbeat: ProgressHeartbeat | None,
    label: str,
    prefix: str,
):
    resource = open_provider_context(provider, args)
    try:
        _, _, context, timeout_error_cls = resource
        request_fn = provider_request_fn(provider)
        return request_fn(
            context=context,
            timeout_error_cls=timeout_error_cls,
            args=args,
            prompt=prompt,
            heartbeat=heartbeat,
            label=label,
            prefix=prefix,
        )
    finally:
        close_provider_resource(resource)


def claude_deep_runtime_args(args: argparse.Namespace):
    data = vars(args).copy()
    timeout_sec = int(data.get("request_timeout_sec", DEFAULT_CLAUDE_DEEP_TIMEOUT_SEC))
    data["request_timeout_sec"] = min(timeout_sec, DEFAULT_CLAUDE_DEEP_TIMEOUT_SEC)
    return SimpleNamespace(**data)


def run_basic_analysis(
    *,
    sections: list[str],
    input_file: Path,
    args: argparse.Namespace,
    instructions: str,
    work_dir: Path,
    heartbeat: ProgressHeartbeat | None,
) -> str:
    provider = "chatgpt_web"
    chunk_outputs: list[str] = []
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
        write_artifact(work_dir / f"{prefix}_{provider}_prompt.txt", prompt)
        result = execute_provider_request(
            provider=provider,
            args=args,
            prompt=prompt,
            heartbeat=heartbeat,
            label=f"기본문서분석 {index}/{len(sections)}",
            prefix=f"{prefix}_{provider}",
        )
        write_artifact(work_dir / f"{prefix}_{provider}_response.txt", result["response_text"])
        write_json_artifact(work_dir / f"{prefix}_{provider}_meta.json", result)
        chunk_outputs.append(result["response_text"].strip())
    if len(chunk_outputs) == 1:
        return chunk_outputs[0].strip()
    final_prompt = build_final_analysis_prompt(
        input_name=input_file.name,
        instructions=instructions,
        chunk_summaries=chunk_outputs,
        final_format=args.final_format,
    )
    write_artifact(work_dir / f"final_{provider}_prompt.txt", final_prompt)
    final_result = execute_provider_request(
        provider=provider,
        args=args,
        prompt=final_prompt,
        heartbeat=heartbeat,
        label="기본문서분석 최종정리",
        prefix=f"final_{provider}",
    )
    write_artifact(work_dir / f"final_{provider}_response.txt", final_result["response_text"])
    write_json_artifact(work_dir / f"final_{provider}_meta.json", final_result)
    return final_result["response_text"].strip()


def run_deep_analysis(
    *,
    sections: list[str],
    input_file: Path,
    args: argparse.Namespace,
    instructions: str,
    work_dir: Path,
    heartbeat: ProgressHeartbeat | None,
) -> tuple[str, dict[str, object]]:
    providers = analysis_provider_sequence("deep")
    claude_available = True
    claude_fallback_triggered = False
    claude_fallback_reason = ""
    chunk_outputs: list[str] = []
    for index, section_text in enumerate(sections, start=1):
        prefix = f"chunk_{index:03d}"
        chatgpt_prompt = build_chunk_analysis_prompt(
            input_name=input_file.name,
            instructions=instructions,
            chunk_text=section_text,
            chunk_index=index,
            chunk_count=len(sections),
            final_format=args.final_format,
        )
        write_artifact(work_dir / f"{prefix}_chatgpt_web_prompt.txt", chatgpt_prompt)
        chatgpt_result = execute_provider_request(
            provider="chatgpt_web",
            args=args,
            prompt=chatgpt_prompt,
            heartbeat=heartbeat,
            label=f"심화분석 ChatGPT {index}/{len(sections)}",
            prefix=f"{prefix}_chatgpt_web",
        )
        write_artifact(work_dir / f"{prefix}_chatgpt_web_response.txt", chatgpt_result["response_text"])
        write_json_artifact(work_dir / f"{prefix}_chatgpt_web_meta.json", chatgpt_result)

        gemini_prior_outputs: list[tuple[str, str]] = [("ChatGPT 분석", chatgpt_result["response_text"])]
        if claude_available:
            claude_prompt = build_review_prompt(
                provider="claude_web",
                input_name=input_file.name,
                instructions=instructions,
                chunk_text=section_text,
                prior_outputs=gemini_prior_outputs,
                final_format=args.final_format,
            )
            write_artifact(work_dir / f"{prefix}_claude_web_prompt.txt", claude_prompt)
            claude_args = claude_deep_runtime_args(args)
            try:
                claude_result = execute_provider_request(
                    provider="claude_web",
                    args=claude_args,
                    prompt=claude_prompt,
                    heartbeat=heartbeat,
                    label=f"심화분석 Claude {index}/{len(sections)}",
                    prefix=f"{prefix}_claude_web",
                )
                write_artifact(work_dir / f"{prefix}_claude_web_response.txt", claude_result["response_text"])
                write_json_artifact(work_dir / f"{prefix}_claude_web_meta.json", claude_result)
                gemini_prior_outputs.append(("Claude 검토", claude_result["response_text"]))
            except Exception as exc:
                claude_available = False
                claude_fallback_triggered = True
                claude_fallback_reason = normalized_file_text(str(exc))
                reason = "usage_limit" if isinstance(exc, ClaudeWebUsageLimitError) else "request_error"
                beat_heartbeat(
                    heartbeat,
                    stage="provider_fallback",
                    label=f"심화분석 Claude {index}/{len(sections)}",
                    section_prefix=f"{prefix}_claude_web",
                    detail=f"claude_{reason}_skip_to_chatgpt_gemini",
                )
                write_json_artifact(
                    work_dir / f"{prefix}_claude_web_meta.json",
                    {
                        "provider": "claude_web",
                        "skipped": True,
                        "reason": reason,
                        "message": claude_fallback_reason,
                    },
                )
                write_artifact(
                    work_dir / "claude_web_fallback_notice.txt",
                    f"Claude 웹 단계를 완료하지 못해 이후 단계는 ChatGPT 웹 + Gemini 웹 교차 검증으로 진행합니다.\n\n{claude_fallback_reason}",
                )
        gemini_prompt = build_review_prompt(
            provider="gemini_web",
            input_name=input_file.name,
            instructions=instructions,
            chunk_text=section_text,
            prior_outputs=gemini_prior_outputs,
            final_format=args.final_format,
        )
        write_artifact(work_dir / f"{prefix}_gemini_web_prompt.txt", gemini_prompt)
        gemini_result = execute_provider_request(
            provider="gemini_web",
            args=args,
            prompt=gemini_prompt,
            heartbeat=heartbeat,
            label=f"심화분석 Gemini {index}/{len(sections)}",
            prefix=f"{prefix}_gemini_web",
        )
        write_artifact(work_dir / f"{prefix}_gemini_web_response.txt", gemini_result["response_text"])
        write_json_artifact(work_dir / f"{prefix}_gemini_web_meta.json", gemini_result)
        chunk_outputs.append(gemini_result["response_text"].strip())

    final_chatgpt_prompt = build_final_analysis_prompt(
        input_name=input_file.name,
        instructions=instructions,
        chunk_summaries=chunk_outputs,
        final_format=args.final_format,
    )
    write_artifact(work_dir / "final_chatgpt_web_prompt.txt", final_chatgpt_prompt)
    final_chatgpt_result = execute_provider_request(
        provider="chatgpt_web",
        args=args,
        prompt=final_chatgpt_prompt,
        heartbeat=heartbeat,
        label="심화분석 최종 ChatGPT",
        prefix="final_chatgpt_web",
    )
    write_artifact(work_dir / "final_chatgpt_web_response.txt", final_chatgpt_result["response_text"])
    write_json_artifact(work_dir / "final_chatgpt_web_meta.json", final_chatgpt_result)

    final_gemini_prior_outputs: list[tuple[str, str]] = [("ChatGPT 통합본", final_chatgpt_result["response_text"])]
    if claude_available:
        final_claude_prompt = build_final_review_prompt(
            provider="claude_web",
            input_name=input_file.name,
            instructions=instructions,
            prior_outputs=final_gemini_prior_outputs,
            final_format=args.final_format,
        )
        write_artifact(work_dir / "final_claude_web_prompt.txt", final_claude_prompt)
        final_claude_args = claude_deep_runtime_args(args)
        try:
            final_claude_result = execute_provider_request(
                provider="claude_web",
                args=final_claude_args,
                prompt=final_claude_prompt,
                heartbeat=heartbeat,
                label="심화분석 최종 Claude",
                prefix="final_claude_web",
            )
            write_artifact(work_dir / "final_claude_web_response.txt", final_claude_result["response_text"])
            write_json_artifact(work_dir / "final_claude_web_meta.json", final_claude_result)
            final_gemini_prior_outputs.append(("Claude 검토본", final_claude_result["response_text"]))
        except Exception as exc:
            claude_available = False
            claude_fallback_triggered = True
            claude_fallback_reason = normalized_file_text(str(exc))
            reason = "usage_limit" if isinstance(exc, ClaudeWebUsageLimitError) else "request_error"
            beat_heartbeat(
                heartbeat,
                stage="provider_fallback",
                label="심화분석 최종 Claude",
                section_prefix="final_claude_web",
                detail=f"claude_{reason}_skip_to_chatgpt_gemini",
            )
            write_json_artifact(
                work_dir / "final_claude_web_meta.json",
                {
                    "provider": "claude_web",
                    "skipped": True,
                    "reason": reason,
                    "message": claude_fallback_reason,
                },
            )
            write_artifact(
                work_dir / "claude_web_fallback_notice.txt",
                f"Claude 웹 단계를 완료하지 못해 이후 단계는 ChatGPT 웹 + Gemini 웹 교차 검증으로 진행합니다.\n\n{claude_fallback_reason}",
            )
    final_gemini_prompt = build_final_review_prompt(
        provider="gemini_web",
        input_name=input_file.name,
        instructions=instructions,
        prior_outputs=final_gemini_prior_outputs,
        final_format=args.final_format,
    )
    write_artifact(work_dir / "final_gemini_web_prompt.txt", final_gemini_prompt)
    final_gemini_result = execute_provider_request(
        provider="gemini_web",
        args=args,
        prompt=final_gemini_prompt,
        heartbeat=heartbeat,
        label="심화분석 최종 Gemini",
        prefix="final_gemini_web",
    )
    write_artifact(work_dir / "final_gemini_web_response.txt", final_gemini_result["response_text"])
    write_json_artifact(work_dir / "final_gemini_web_meta.json", final_gemini_result)
    effective_providers = ["chatgpt_web"]
    if claude_available:
        effective_providers.append("claude_web")
    effective_providers.append("gemini_web")
    return final_gemini_result["response_text"].strip(), {
        "effective_providers": effective_providers,
        "claude_fallback_triggered": claude_fallback_triggered,
        "claude_fallback_reason": claude_fallback_reason,
    }


def write_manifest(
    *,
    manifest_path: Path,
    args: argparse.Namespace,
    input_file: Path,
    output_file: Path,
    work_dir: Path,
    chunk_count: int,
    effective_providers: list[str] | None = None,
    claude_fallback_triggered: bool = False,
    claude_fallback_reason: str = "",
) -> None:
    payload = {
        "analysis_mode": args.analysis_mode,
        "providers": list(analysis_provider_sequence(args.analysis_mode)),
        "effective_providers": effective_providers or list(analysis_provider_sequence(args.analysis_mode)),
        "input_file": str(input_file),
        "input_format": input_file_format(input_file),
        "output_file": str(output_file),
        "work_dir": str(work_dir),
        "chunk_count": chunk_count,
        "request_timeout_sec": args.request_timeout_sec,
        "chatgpt_web_visible": bool(args.chatgpt_web_visible),
        "claude_web_visible": bool(args.claude_web_visible),
        "gemini_web_visible": bool(args.gemini_web_visible),
        "chatgpt_web_max_attempts": int(args.chatgpt_web_max_attempts),
        "claude_web_max_attempts": int(args.claude_web_max_attempts),
        "gemini_web_max_attempts": int(args.gemini_web_max_attempts),
        "max_chars_per_chunk": int(args.max_chars_per_chunk),
        "final_format": args.final_format,
        "claude_fallback_triggered": bool(claude_fallback_triggered),
        "claude_fallback_reason": claude_fallback_reason,
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
    write_manifest(
        manifest_path=work_dir / "analysis_manifest.json",
        args=args,
        input_file=input_file,
        output_file=output_file,
        work_dir=work_dir,
        chunk_count=len(sections),
    )
    analysis_meta: dict[str, object] = {
        "effective_providers": list(analysis_provider_sequence(args.analysis_mode)),
        "claude_fallback_triggered": False,
        "claude_fallback_reason": "",
    }
    if args.analysis_mode == "deep":
        final_response, analysis_meta = run_deep_analysis(
            sections=sections,
            input_file=input_file,
            args=args,
            instructions=instructions,
            work_dir=work_dir,
            heartbeat=heartbeat,
        )
    else:
        final_response = run_basic_analysis(
            sections=sections,
            input_file=input_file,
            args=args,
            instructions=instructions,
            work_dir=work_dir,
            heartbeat=heartbeat,
        )
    write_manifest(
        manifest_path=work_dir / "analysis_manifest.json",
        args=args,
        input_file=input_file,
        output_file=output_file,
        work_dir=work_dir,
        chunk_count=len(sections),
        effective_providers=list(analysis_meta.get("effective_providers") or []),
        claude_fallback_triggered=bool(analysis_meta.get("claude_fallback_triggered")),
        claude_fallback_reason=str(analysis_meta.get("claude_fallback_reason") or ""),
    )
    output_file.write_text(final_response.rstrip() + "\n", encoding="utf-8")
    if args.apply_results_to_docx_pdf and input_file.suffix.lower() == ".docx":
        from scripts.apply_deep_analysis_results import apply_analysis

        apply_result = apply_analysis(
            input_file,
            output_file,
            None,
            section_title=args.apply_section_title,
            make_pdf=not args.no_pdf_after_apply,
        )
        beat_heartbeat(heartbeat, stage="apply_complete", detail=json.dumps(apply_result, ensure_ascii=False))
    beat_heartbeat(heartbeat, stage="analysis_complete", detail=str(output_file))
    print(f"input: {input_file}", file=sys.stderr)
    print(f"output: {output_file}", file=sys.stderr)
    print(f"work_dir: {work_dir}", file=sys.stderr)
    print(f"mode: {args.analysis_mode}", file=sys.stderr)
    print(f"chunks: {len(sections)}", file=sys.stderr)
    if args.apply_results_to_docx_pdf and input_file.suffix.lower() == ".docx":
        print("apply: docx/pdf updated", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
