# translate_epub_with_chatgpt_web_to_study_epub.py

영문 EPUB 한 권을 웹 자동화(Gemini 또는 ChatGPT 웹, Playwright 기반)로 한국어 대조 학습용 EPUB로 번역하는 이 저장소의 **핵심 번역 엔진**. `webui/workflow_runner.py`의 배치 번역이 책 한 권마다 이 스크립트를 서브프로세스로 호출한다. 단독으로도 실행 가능하다.

저장소 루트: `/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker`
파일: `scripts/translate_epub_with_chatgpt_web_to_study_epub.py` (약 3,700줄)

## 언제 쓰는가

- 배치 번역(`workflow_runner.py`)이 자동으로 호출 — 보통 사람이 직접 실행할 일은 없다.
- 예외: 배치 도중 특정 책 하나만 별도로 재시도해야 할 때(브라우저 세션 행업, 검증기 오탐 등), 배치를 잠시 멈춰두고 **이 스크립트를 그 책 하나에 대해서만 직접 실행**한다 — `--work-dir`을 그 책의 기존 작업 디렉터리로 지정하면 이미 번역된 청크는 캐시에서 재사용하고 실패했던 부분부터 이어서 진행한다. (수동 재시도 절차 예시는 아래 참고.)

## 전체 파이프라인 순서 (`main()`)

1. **입력 검증 및 잠금**: 입력 EPUB 존재 확인 → `work_dir` 생성 → `.translation.lock` 파일로 같은 작업 디렉터리에 대한 중복 실행 방지(파일 락, 이미 실행 중이면 즉시 종료).
2. **웹 제공자 결정**: `--web-provider`가 없으면 이전 실행 상태(`provider_fallback_state.json`)를 보고 자동 결정(`resolve_web_provider`), 이번 실행에서 쓸 제공자를 다시 기록(`persist_web_provider`).
3. **원문 추출**: `extract_sections()`로 EPUB에서 장(section)/문단블록(block, ID `B00001` 형태)을 뽑아 `manifest.json`, `source_sections.json`으로 저장. 장 제목은 `parse_ncx_nav()`(레거시 `toc.ncx`) → `parse_epub3_nav()`(EPUB3 `<nav epub:type="toc">`, 2026-08-03 추가) → 그래도 없으면 챕터 파일명 순으로 시도한다. `toc.ncx` 없이 EPUB3 nav만 있는 원서(TED 강연 모음집 등 커스텀 빌더로 만든 EPUB에서 흔함)를 이 순서로 지원하지 않으면, 목차/장 제목이 전부 "chapter-001" 같은 파일명으로 뭉개진 채 번역되는 결함이 생긴다 — 실제로 TED 강연 모음집 작업에서 이 결함이 발견되어 `parse_epub3_nav()`를 추가했다.
4. **청크 분할**: `build_chunks()`로 블록들을 `--max-chars-per-chunk`(기본 8500자) 단위로 묶어 번역 청크(`TranslationChunk`)를 만든다.
5. **번역 실행** (`--build-only`가 아니면): `translate_missing_chunks()` — 아래 "번역 단계 상세" 참고.
6. **EPUB 조립** (`--translate-only`가 아니면): 캐시된 번역(`load_translation_cache`)을 읽어 빈 블록이 있으면 즉시 실패시키고, `build_epub()`으로 한영 대조 EPUB(`[k-e]`, 학습노트 없는 순수본)을 생성. `scrub_epub()`으로 유출 사이트 워터마크 문자열을 최종 제거. 원문/번역문은 XHTML에 넣기 전에 `clean_text()`를 거치는데, 이 함수가 XML에서 금지된 raw 제어문자(예: 나쁜 PDF 추출로 섞여 들어온 `\x07`)도 함께 제거한다 — `html.escape()`만으로는 `&`/`<`/`>` 등만 이스케이프될 뿐 이런 제어문자는 그대로 남아 결과 XHTML이 아예 파싱 불가능(`not well-formed (invalid token)`)해지기 때문이다.
6-1. **`[study]` 조립** (`--study-output-epub`이 지정된 경우만): 같은 캐시로 `build_epub(..., include_study_notes=True)`를 한 번 더 호출해, 번역문에 섞여 있던 토익 학습노트(`※학습: ...`, `split_translation_and_note()`로 분리)를 별도 `span.study-note`에 남긴 두 번째 EPUB을 만든다 — 추가 웹 요청 없음. 자세한 내용은 [EPUB 영어학습자용 [study] 버전 토익 학습노트 절차](../EPUB%20영어학습자용%20%5Bstudy%5D%20버전%20토익%20학습노트%20절차.md) 참고.
7. **최종 검수 4종** (`--skip-final-tone-review`가 아니면 1~3 실행, 4는 항상 실행):
   - **톤 검사** (`review_epub_tone`, → `final_tone_reviews/`)
   - **대화 일관성 2차 검사** (`review_dialogue_consistency`, → `final_dialogue_reviews_pass2/`)
   - **용어 일관성 검사** (`parse_terminology_glossary` + `check_terminology_consistency`, → `final_terminology_reviews/`)
   - **형식/표지 최종 검수** (`review_epub_presentation_quality`) — PDF 원본을 변환했을 때 표지/제목에 정제되지 않은 파일명이 노출되거나, 목차가 "페이지 N" 식으로만 나열되는 문제를 감지.
   각 검수는 실패해도 EPUB 생성 자체를 막지 않고, 실패 사유를 `*_error.txt`로 남긴 뒤 계속 진행한다.
8. 완료 시 표준출력에 JSON 요약(`sections`/`blocks`/`chunks`/각 검수 결과)을 출력하고 `.translation.lock`을 해제한다.

## 번역 단계 상세 (`translate_missing_chunks` 계열)

- **인물관계/말투 가이드 선(先)생성** (`ensure_relationship_guide`): 책의 앞부분 표본으로 웹 서비스에 인물관계·호칭·말투 규칙을 먼저 물어 `relationship_guide.txt`로 캐시(`RELATIONSHIP_GUIDE_VERSION`로 캐시 무효화 관리). 웹 요청이 끝내 실패하면 로컬 휴리스틱(`build_local_relationship_guide`)으로 대체.
- **대화 재사용 번역** (`translate_missing_chunks_reusing_conversations`): `--chunks-per-conversation`(기본 1) 개 청크마다 대화를 이어가며 요청, 매 요청 사이 `--inter-request-delay-sec` 대기.
- **품질 검증** (`validate_chunk_translations`, `scripts/translation_quality_checks.py`): 마커 유출, 미번역, 길이 이상치 등을 심각도별로 판정 — 자세한 오탐 예외 규칙은 별도 문서 [EPUB 번역 품질 검증기 오탐 예외 처리 규칙](../EPUB%20번역%20품질%20검증기%20오탐%20예외%20처리%20규칙.md) 참고.
- **검증 실패 시 재시도 경로**: 새 대화로 재시도(`fresh_chat_then_subchunk_retry`) → 그래도 실패하면 `translate_refused_chunk_in_subchunks`로 더 잘게 쪼개 재시도 → 특정 블록이 계속 거절되면 마지막 수단으로 로컬 Ollama 모델(`--ollama-refusal-model`, 기본 비활성 아님)로 그 블록만 번역(`translation_ollama_refusal_fallback_start` 스테이지).
- **자정~오전 자동 폴백** (`--disable-overnight-web-fallback`로 끌 수 있음): 야간(18:00~09:00)·주말에 Gemini 웹이 오류/일시중단되면 ChatGPT 웹으로 자동 전환. **주의**: 현재 프로젝트 정책상 ChatGPT 사용이 중단된 상태이므로, 실제 배치 실행 시 항상 `--disable-overnight-web-fallback`을 켜서 호출한다.
- **ChatGPT 무료 사용량 자체 제한**: `--chatgpt-free-tier-message-limit`/`--chatgpt-free-tier-window-hours`로 롤링 시간 창 안 메시지 수를 스스로 제한(무료 계정 한도 초과로 인한 오류 방지).

## 주요 CLI 인자

| 인자 | 의미 |
|---|---|
| `--input-epub` / `--output-epub` (필수) | 입력 원서 EPUB / 출력 한영 대조 `[k-e]` EPUB 경로 |
| `--study-output-epub` | 지정하면 같은 캐시로 토익 학습노트 포함 `[study]` 버전도 함께 생성(추가 웹 요청 없음) |
| `--work-dir` | 캐시·프롬프트·응답·리뷰가 쌓이는 작업 디렉터리 (지정하지 않으면 자동 결정) |
| `--book-title-ko` | 출력 EPUB 제목에 쓸 한국어 제목(생략 시 원문 제목 유지 — 표지/메타데이터의 책 제목은 원어 유지가 기본값) |
| `--web-provider {gemini,chatgpt}` | 사용할 웹 서비스. 생략 시 이전 상태로 자동 결정 |
| `--max-chars-per-chunk` | 청크당 최대 글자 수 (기본 8500, 배치에서는 보통 6000으로 덮어씀) |
| `--web-max-attempts` (`--chatgpt-web-max-attempts`) | 청크당 웹 요청 재시도 횟수 |
| `--chunks-per-conversation` | 한 대화에서 이어서 처리할 청크 수 |
| `--inter-request-delay-sec` | 요청 사이 대기 시간(초) |
| `--request-timeout-sec` | 응답 대기 타임아웃(초) — 이 타임아웃은 애플리케이션 레벨이며, 브라우저/페이지 자체가 완전히 멈추는 경우까지는 못 잡을 수 있다 |
| `--disable-overnight-web-fallback` | 야간/주말 ChatGPT 자동 폴백 비활성화 — **현재 항상 켜서 실행해야 함(정책)** |
| `--disable-ollama-refusal-fallback` | 거절 블록의 로컬 Ollama 최종 폴백 비활성화 |
| `--translate-only` / `--build-only` | 번역만 하고 EPUB 조립은 생략 / 조립만 하고(캐시된 번역 사용) 번역 요청은 생략 |
| `--skip-final-tone-review` | 4종 최종 검수 중 앞 3종(톤/대화/용어) 생략 (형식 검수는 항상 실행) |
| `--heartbeat-file` | 진행상황을 JSON으로 기록할 heartbeat 파일 경로 |
| `--provider-fallback-state-dir` | `provider_fallback_state.json`을 둘 디렉터리(보통 배치의 work 루트, 여러 책이 폴백 상태를 공유) |

## 단독 실행(수동 재시도) 예시

배치 도중 특정 책의 브라우저 세션이 멈추거나 계속 실패할 때, 메인 배치를 잠시 멈추고 그 책만 별도 heartbeat/log로 재실행하는 방법:

```bash
python3 scripts/translate_epub_with_chatgpt_web_to_study_epub.py \
  --input-epub "<원서 epub 경로>" \
  --output-epub "<출력 [k-e] epub 경로>" \
  --work-dir "<기존 배치의 work/<번호>_<책이름>/translation 디렉터리>" \
  --heartbeat-file "<임시 heartbeat 파일 경로>" \
  --web-provider gemini --max-chars-per-chunk 6000 --web-max-attempts 5 \
  --chunks-per-conversation 10 --inter-request-delay-sec 4.0 --request-timeout-sec 1200 \
  --disable-overnight-web-fallback \
  --provider-fallback-state-dir "<배치의 work 루트>"
```

기존 `work_dir`을 그대로 재사용하므로 이미 완료된 청크는 다시 요청하지 않고, 실패했던 청크부터 이어서 진행한다. 단, **같은 웹 서비스 브라우저 세션을 두 개 동시에 띄우면 안 되므로**, 이 수동 실행 전에 메인 배치 프로세스(`workflow_runner.py`와 그 자식 프로세스)를 반드시 먼저 종료해야 한다.

## 관련 문서
- [EPUB 배치 번역 중복작업 방지 처리절차](../EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md)
- [EPUB 번역 품질 검증기 오탐 예외 처리 규칙](../EPUB%20번역%20품질%20검증기%20오탐%20예외%20처리%20규칙.md)
- [EPUB 대화체(말투) 검수 작업지시서](../EPUB%20대화체(말투)%20검수%20작업지시서.md)
- [EPUB 영어학습자용 [study] 버전 토익 학습노트 절차](../EPUB%20영어학습자용%20%5Bstudy%5D%20버전%20토익%20학습노트%20절차.md)
