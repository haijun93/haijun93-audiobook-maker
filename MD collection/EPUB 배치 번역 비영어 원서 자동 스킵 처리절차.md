# EPUB 배치 번역 비영어 원서 자동 스킵 처리절차

이 문서는 배치 번역(`webui/workflow_runner.py`)이 **영어가 아닌 원서를 번역 시도 없이 감지해 스킵하고 격리하는 절차**를 설명한다. 2026-08-02 사용자 요청으로 새로 추가된 기능이며, [EPUB 배치 번역 중복작업 방지 처리절차](EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md)가 설명하는 관문들과 같은 위치(`run_batch()`의 파일별 처리 직전)에 있지만 목적은 다르다 — 중복이 아니라 **번역 파이프라인의 언어 전제(영어 원서 → 한국어 번역)에 맞지 않는 책을 걸러내는 것**이다.

저장소 루트: `/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker`
관련 파일: `webui/workflow_runner.py`, `scripts/translation_quality_checks.py`

## 왜 필요한가

이 파이프라인은 영어 원서를 한국어로 번역하는 것을 전제로 프롬프트와 검증기가 구성되어 있다. 원서 자체가 프랑스어/스페인어 등 다른 언어(라틴 문자든 아니든)면, 웹 번역이 제목·인명 등 고유명사를 원문 유지하는 정상적인 동작을 하더라도 대부분의 블록이 "원문 그대로"로 남아 `untranslated_identity`로 계속 판정되고, book-level 재시도 3회를 전부 소진한 뒤 영구 `failed` 처리된다. 재시도로는 근본적으로 해결되지 않는 원인이므로, 번역을 시도하기 전에 미리 걸러내는 편이 낫다.

## 판별 방법 (`looks_like_english_source`, `webui/workflow_runner.py`)

1. `translate_epub_with_chatgpt_web_to_study_epub.py`의 `extract_sections()`를 그대로 재사용해 원서에서 문단 블록을 뽑는다(별도 파싱 로직을 새로 만들지 않음).
2. 40자 이상인 블록을 순서대로 이어 붙여 최대 4000자 표본을 만든다.
3. `translation_quality_checks.is_english_word_sample()`로 판정: 라틴 알파벳 단어를 뽑아, 그중 영어 흔한 기능어(`ENGLISH_FUNCTION_WORDS` — the/a/of/to/in/is/are/was 등, 이미 검증기가 다른 목적으로 쓰던 목록)의 비율이 8% 미만이면 "영어 아님"으로 판정한다.
   - 실제 영어 산문은 기능어 비율이 훨씬 높아(보통 15% 이상) 오탐 위험이 낮다.
   - 프랑스어/스페인어 등 다른 라틴 문자 언어는 영어 기능어 목록과 겹치는 단어가 거의 없어 낮은 비율로 잡힌다.
   - 한글/일본어/중국어 등 비라틴 문자 원서는애초에 라틴 알파벳 단어 수 자체가 최소 기준(40단어) 미만이라 바로 걸러진다.
4. 원서를 열지 못하는 등 표본 추출 자체가 실패하면, 오탐으로 정상 번역을 막지 않도록 **기본값은 "영어로 간주"** (`True`)한다.

## 스킵 시 처리 (`run_batch()` 내부)

기존 중복 검사(`find_finished_match`) 바로 다음 관문으로 추가되어 있다. 비영어로 판정되면:

1. `archive_non_english_source()`가 원본 파일을 소스 폴더 바로 아래 **`non-english/`** 하위 폴더로 이동(이름 충돌 시 `(2)`, `(3)` 접미사 자동 부여) — `_excluded_do_not_retry/` 관행과 같은 원리로, 배치가 재귀 스캔이 아닌 한 하위 폴더 안 파일은 이후 재스캔에서 다시 집히지 않는다.
2. `batch_status.json`에 `{"status": "skipped", "reason": "non_english_source"}`로 기록.
3. 번역 서브프로세스를 아예 실행하지 않고 다음 파일로 진행 — book-level 재시도 3회를 소모하지 않는다.

## 테스트

`tests/test_web_workflow_runner.py`:
- `test_looks_like_english_source_accepts_english_prose` — 정상 영어 산문은 통과
- `test_looks_like_english_source_rejects_non_english_prose` — 프랑스어 산문은 거부
- `test_archive_non_english_source_moves_file_out_of_scan_path` — 격리 이동 및 스캔 경로 이탈 확인

## 관련 문서
- [EPUB 배치 번역 중복작업 방지 처리절차](EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md) — 같은 위치의 다른 관문들(파일명 완전일치, 서지정보 대조, 산출물 존재 확인)
- [EPUB 번역 품질 검증기 오탐 예외 처리 규칙](EPUB%20번역%20품질%20검증기%20오탐%20예외%20처리%20규칙.md) — `ENGLISH_FUNCTION_WORDS`를 이미 다른 목적(구성 언어/외국어 대사 판별)으로 쓰고 있던 곳
