# EPUB 번역 품질 검증기 오탐(false positive) 예외 처리 규칙

이 문서는 번역 파이프라인의 자동 품질 검증기(`scripts/translation_quality_checks.py`)가 "번역이 안 됐다(`untranslated_identity` 등)"고 오판하는 문제를 발견했을 때, 그것을 코드 차원에서 어떻게 예외 처리해왔는지 정리한 절차·변경이력 문서다. 검증기 자체의 전체 로직 설명이 아니라, **오탐 예외를 추가/수정할 때의 판단 기준과 지금까지의 사례**에 초점을 둔다.

저장소 루트: `/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker`
관련 파일: `scripts/translation_quality_checks.py`, 테스트: `tests/test_translation_quality_pipeline.py`

## 왜 오탐이 생기는가

`assess_translations()`는 번역문이 원문과 정규화 후 완전히 같으면(`normalized_for_identity` 비교) `untranslated_identity`(심각)로 표시한다 — 이는 실제로 번역가가 빼먹은 문장을 잡아내기 위한 규칙이다. 그런데 책의 앞부분(저작권 페이지, 서지정보, 출판사 임프린트 표기, ISBN, 도서관 카탈로그 인용 등)은 **원문 그대로 두는 것이 오히려 정상**인 경우가 많다. 번역 프롬프트 자체도 "작품명·인명·ISBN·URL은 원문 표기를 유지하라"고 명시한다. 이런 줄까지 그대로 남았다고 실패 처리하면, 실제로는 정상인 번역인데도 웹(Gemini)과 로컬 폴백(gemma4) 모두 같은 이유로 계속 실패해 그 책 전체가 3회 재시도 후 영구 `failed` 처리되는 결과로 이어진다.

## 오탐 여부를 판단하는 원칙

새로운 실패 사례를 볼 때마다 다음을 확인한다.

1. **실패한 블록의 원문 내용을 반드시 직접 확인한다.** `<job_dir>/work/<번호>_<책이름>/translation/source_sections.json`에서 해당 block id(`B00004` 등)를 찾아 실제 문장을 읽는다.
2. **그 문장이 서사/대사(narrative prose)인가, 서지·법적 표기(frontmatter metadata)인가**를 판단한다. 후자라면 원문 유지가 정상일 가능성이 높다.
3. 정상이라고 판단되면, **그 문장 하나만 예외 처리하지 말고 같은 "종류"의 문장을 식별하는 일반 규칙**(정규식/휴리스틱)을 `is_prose_source()`의 예외 목록에 추가한다. 특정 책의 특정 문장 하나만 하드코딩하지 않는다.
4. 예외 규칙은 **좁고 구체적으로** 만든다 — 서사 문장이 우연히 같은 패턴에 걸려 진짜 미번역을 놓치지 않도록, 앵커(`^`), 구두점 조합, 길이 제한 등으로 범위를 최대한 좁힌다.
5. `tests/test_translation_quality_pipeline.py`에 해당 사례를 파라미터로 추가하고 전체 테스트를 돌려 회귀가 없는지 확인한다.

## 현재 예외 체계 구조

`is_prose_source(text)`가 다음을 순서대로 확인해, 하나라도 해당하면 "이 문장은 검증 대상 서사가 아니다"로 판단하고 `untranslated_identity`/`untranslated_latin` 검사를 건너뛴다.

| 함수/패턴 | 잡아내는 것 |
|---|---|
| `FRONTMATTER_METADATA_RE` | 저작권/임프린트/초판/의회도서관/서지 헤더 등 문장 시작 패턴 (예: `Copyright`, `Published ... by`, `First Edition`, `Library of Congress`, `Names:`/`Title:`/... 필드형 CIP 라인) |
| `BARE_DOMAIN_RE` / `ADDRESS_RE` / `ADDRESS_CONTINUATION_RE` | 출판사 주소, 맨도메인(scheme 없는 URL) |
| `is_proper_noun_list` | 후원자/감사 인사 명단처럼 쉼표로 나열된 고유명사 목록 |
| `is_bare_title_subtitle_line` | 마침표 없는 `제목 : 부제` 형태의 책/문서 제목 인용 |
| `is_cip_title_statement_line` | 콜론(` : `)과 슬래시(` / `)를 함께 쓰는 도서관 서지 인용줄 (예: `Before I go to sleep : a novel / S.J. Watson. — 1st ed.`) |
| `is_song_or_quote_attribution_line` | `제목 – 아티스트` 형태의 노래/인용 출처 (en/em dash 또는 일반 하이픈 `-`) |
| `is_constructed_or_foreign_language_line` | Dune의 프레멘어처럼 원작에 등장하는 가상/외국어 대사 (영어 기능어 비율로 판별) |

## 변경 이력

### 2026-08-01 — CIP 서지 인용줄 예외 추가, `published ... by` 패턴 확장

**계기**: 배치 작업 `b0282cd32bee4d0ea73e7be8eb9d0796` 진행 중 `Before I Go To Sleep - S. J. Watson.epub`이 block `B03281:untranslated_identity`로 book-level 재시도 3회 모두 실패(영구 실패 처리). 원문 확인 결과 `"Before I go to sleep : a novel / S.J. Watson. — 1st ed."` — 도서관 CIP 서지 인용줄이었다. 곧이어 다음 책 `Between the World and Me - Ta-Nehisi Coates.epub`도 같은 유형으로 `B00004:untranslated_identity` 실패(`"Published in the United States by Spiegel & Grau, ..."`) — 앞부분 서지/판권 정보에서 반복되는 구조적 패턴임을 확인.

**수정 내용**:
- `FRONTMATTER_METADATA_RE`의 `published\s+by\b` 패턴이 `"Published in the United States by X"`처럼 중간에 단어가 끼면 매칭에 실패하던 것을, 최대 6단어까지 허용하도록 `published\b(?:\s+\S+){0,6}\s+by\b`로 확장.
- 콜론+슬래시 인용 구두점 조합을 식별하는 `CIP_TITLE_STATEMENT_RE`(`\s:\s.{1,80}\s/\s`)와 `is_cip_title_statement_line()`을 신설해 `is_prose_source()` 예외 목록에 추가.

**검증**: `tests/test_translation_quality_pipeline.py`에 두 사례(CIP 인용줄, 확장된 published-by 문장)를 파라미터 테스트로 추가, 전체 테스트 스위트(252개) 통과 확인.

**적용 결과 확인**: 코드 수정 이후 `Between the World and Me`는 자동 book-level 재시도(attempt 2/3)에서 별도 개입 없이 스스로 성공했고, 이미 영구 실패 처리됐던 `Before I Go To Sleep`은 같은 work_dir을 재사용하는 수동 재시도로 복구해 정상 완료했다.

### 2026-08-01 (같은 배치, 후속) — 노래 인용줄 예외에 일반 하이픈 허용

**계기**: 같은 배치에서 `Chokehold A Dark MM Romance - Harleigh Beck.epub`이 block `B00055:untranslated_identity`로 3회 재시도 후 영구 실패. 원문은 `"Everybody Wants To Rule The World - 3TEETH"` — 챕터 제사로 쓰인 노래 제목/아티스트 인용줄이었다. 이미 있는 `is_song_or_quote_attribution_line()`이 en/em dash(`–`/`—`)만 인식하고 일반 ASCII 하이픈(`-`)은 인식하지 못해 발생한 오탐.

**수정 내용**: `is_song_or_quote_attribution_line()`의 구분자 정규식을 `[–—]` → `[-–—]`로 확장해 일반 하이픈도 인식하도록 함.

**검증**: `test_song_or_quote_attribution_line_may_remain_untranslated`에 이 사례를 추가, 전체 테스트 스위트(254개) 통과 확인.
