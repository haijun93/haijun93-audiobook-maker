# EPUB 영어학습자용 [study] 버전 — 토익 학습노트 절차

이 문서는 배치 번역이 책마다 만드는 4번째 산출물 **`[study]`** 를 설명한다. `[study]`는 한영 대조(`[k-e]`)와 내용은 같지만, 토익(TOEIC) 700점 수준 학습자가 만점을 목표로 공부할 수 있도록 **문장마다 선별적으로 어휘/구동사/숙어 학습노트가 추가된 버전**이다. 2026-08-02 사용자 요청으로 도입했고, 같은 날 후속 요청으로 "`[k-e]`는 학습노트 없는 순수 대조본으로 되돌리고, `[study]`가 학습노트를 전담"하는 지금의 4-산출물 구조(`e`/`k`/`k-e`/`study`)로 확정됐다.

저장소 루트: `/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker`
관련 파일: `scripts/translate_epub_with_chatgpt_web_to_study_epub.py`, `webui/workflow_runner.py`, `scripts/make_korean_only_epubs.py`, `scripts/make_english_study_epubs.py`
관련 테스트: `tests/test_epub_integrity.py`, `tests/test_web_workflow_runner.py`, `tests/test_book_organizer.py`


> **[2026-08-16 현행화 업데이트]**:
> 1. **[e-s] 에디션 공식 파이프라인 승격**: 를 통해 서재 전체 278권에 대한 (영어 원문 + 학습노트본) 일괄 생성 및 동기화가 완료되었습니다.
> 2. **서재 표준 경로 직행 규칙**: 별도 임시 폴더(예: )를 만들지 않고, 모든 산출물은 의 4대 표준 폴더(, , , ) 내 작가별 하위 디렉터리(예: )로 즉시 자동 분류 및 저장됩니다.
> 3. **4대 계정 병렬 번역 체계 지원**: Gemini 3계정(, , )과 ChatGPT 1계정이 독립된 브라우저 프로필과 쿠키 자가치유(Self-Healing) 엔진으로 무중단 가동됩니다.

## 산출물 구조

배치 한 권당 폴더 5개, 파일 5개가 생긴다(전부 `output_root`, 보통 소스 폴더 자신 아래):

| 폴더 | 파일명 | 내용 |
|---|---|---|
| `[e]/` | `[e] 제목.epub` | 정제된 영어 원문 사본(번역 없음, `prepare_epub()`이 준비한 원본을 그대로 저장 — 2026-08-03 추가) |
| `[k-e]/` | `[k-e] 제목.epub` | 영어 원문 + 한국어 번역만(학습노트 없는 **순수 대조본**) |
| `[k]/` | `[k] 제목.epub` | 한국어 번역만(`[k-e]`에서 파생) |
| `[study]/` | `[study] 제목.epub` | `[k-e]`와 내용은 같지만 문장마다 **학습노트가 붙은 버전** |
| `[e-s]/` | `[e-s] 제목.epub` | `[study]`에서 한국어 번역만 뺀 버전 — **영어 원문 + 학습노트만** (2026-08-09 추가) |

`[study]`는 `[k-e]`와 별개 파일이지만 **같은 번역 캐시에서 동시에 만들어지므로 추가 웹 요청이 들지 않는다.** `[e-s]`는 `[study]`가 이미 완성된 뒤 그 파일에서 로컬로 파생되므로(`make_english_study_epubs.py`), 이 역시 추가 웹 요청이 들지 않는다.

## 동작 원리

1. **프롬프트** (`build_translation_prompt`, 규칙 11): 모델에게 번역할 때 문장 뒤에 `※학습: 표현 - 뜻/설명` 한 줄을 덧붙이도록 지시한다. **2026-08-08부터 기준이 크게 바뀌었다** — 예전엔 "학습할 만한 표현이 있는 문장에만 선별적으로" 달았는데, 사용자가 "노트가 잘 안 보인다"고 지적해서 지금은 **기본적으로 거의 모든 문장에** 단다("a", "the", "is" 같은 극초급 단어로만 된 문장처럼 정말 예외적인 경우에만 생략). 이 지시는 항상 켜져 있다 — 캐시에는 번역문과 노트가 항상 같이 저장된다.
2. **번역 캐시는 무변경**: 모델 응답은 `<<<B00001>>> 번역문 ※학습: ... <<<END_B00001>>>` 형태로 오지만, `parse_translation_response`/청크 캐시 JSON/`validate_chunk_translations`(`translation_quality_checks.py`)는 전부 이 텍스트를 지금까지처럼 "번역문 하나"로 취급한다. 청크 재사용(캐시 히트)도 그대로 작동한다.
3. **EPUB 조립 시점에 갈라진다** (`xhtml_for_section(section, translations, include_study_notes=...)`):
   - `include_study_notes=False`(`[k-e]`용): `split_translation_and_note()`로 `"※학습:"` 뒷부분을 아예 버리고 번역문만 렌더링.
   - `include_study_notes=True`(`[study]`용): 번역문은 `class="ko"` span에, 노트는 별도 `class="study-note"` span에 나눠 렌더링.
   - **문단 순서: 2026-08-08부터 `[k-e]`/`[study]` 둘 다 "영어 → 한글(→ 학습노트)" 순서다.** 예전엔 `[study]`가 "한글→영어→노트", `[k-e]`가 "한글→영어"였는데, 사용자가 "영어를 먼저 보고 싶다"고 요청해서 두 산출물 다 영어를 맨 앞에 오도록 통일했다(제목/헌사처럼 전체 대문자 짧은 텍스트를 렌더링하는 `<h2>` 분기도 동일하게 바뀜).
   ```html
   <!-- [study] 예시. [k-e]는 study-note span만 없고 순서는 동일. -->
   <p class="pair">
     <span class="en" xml:lang="en">He tried to break the ice with a joke.</span><br/>
     <span class="ko" xml:lang="ko">그는 농담으로 어색한 분위기를 풀려고 했다.</span><br/>
     <span class="study-note" xml:lang="ko">※ break the ice - 서먹함을 깨다</span>
   </p>
   ```
4. `build_epub()`은 `include_study_notes` 인자를 그대로 받아 `xhtml_for_section`에 전달한다. `[study]`는 `[k-e]`와 다른 `dc:identifier`(uuid5 네임스페이스 문자열에 `"::with-study-notes"` 접미사 추가)를 받아 같은 책의 두 파생본이 식별자를 공유하지 않는다.

## 스크립트 CLI (`translate_epub_with_chatgpt_web_to_study_epub.py`)

```bash
python3 scripts/translate_epub_with_chatgpt_web_to_study_epub.py \
  --input-epub <원서> \
  --output-epub <출력 [k-e] 경로> \
  --study-output-epub <출력 [study] 경로> \   # 생략하면 [study] 자체를 안 만듦
  --work-dir <작업 디렉터리> \
  ...
```

`--study-output-epub`을 지정하면, `[k-e]`를 만든 뒤(웹 번역 없이) 같은 캐시로 `[study]`도 바로 만든다.

## 배치 파이프라인 연동 (`webui/workflow_runner.py`)

`translate_one()`이 `output_root / "[study]" / f"[study] {title}.epub"` 경로를 계산해 `--translation-output`이 `both` 또는 `bilingual`일 때(= `[k-e]`를 만드는 모드일 때) 항상 함께 만든다. `translation_output == "korean"`(한글본만 원할 때)이면 `[study]`도 함께 스킵한다 — `[study]`는 대조본 파생물이라 대조본 자체를 안 만드는 모드와는 같이 안 만든다.

기존 책에 `[k-e]`는 있는데 `[study]`가 없으면(이 기능 도입 이전에 번역된 책), 재실행 시 `translate_one()`이 이를 감지해 번역 스크립트를 다시 호출한다 — 이미 모든 청크가 캐시돼 있으므로 웹 요청 없이 `[study]`만 빠르게 새로 만든다.

## `[e]`(정제된 영어 원문) — 번역과 무관하게 항상 보관

`[e]`는 번역 결과물이 아니라, `prepare_epub()`이 준비한 **원문 그대로의 사본**이다(PDF/MOBI였다면 이미 이 단계에서 EPUB으로 변환된 버전, 원래 EPUB이었다면 그 파일 자체). `readable_stem()`이 만든 정제된 제목(`[e] {title}.epub`)으로 `[e]/` 폴더에 저장해, 나중에 원문만 다시 보고 싶을 때 지저분한 원본 파일명(`_OceanofPDF.com_...`) 대신 깔끔한 이름으로 찾을 수 있게 한다.

- `--translation-output` 설정과 무관하게(`both`/`korean`/`bilingual` 전부) 항상 만든다 — 번역 여부와 상관없이 e/k/k-e/study 네 산출물을 한 세트로 유지하기 위함.
- 번역이 필요 없는 경우에도(예: `[k-e]`/`[k]`/`[study]`는 이미 있고 `[e]`만 빠진 책) `prepare_epub()`만 한 번 더 불러 복사하며, **웹 번역 서브프로세스(`run_child`)는 호출하지 않는다** — 순수 로컬 파일 복사라 비용이 거의 없다.

## `[k]`(한글 단독본)에는 자동으로 빠진다

`[k]`는 여전히 `[k-e]`(학습노트 없는 순수본)에서 파생되므로 애초에 노트가 들어갈 일이 없다. `make_korean_only_epubs.py`의 `convert_xhtml()`은 `class="ko"` 요소만 골라 문단을 재구성하므로, 혹시 `[study]`를 `[k]` 변환기에 넣더라도 `study-note` span은 `ko` 클래스가 아니라 자동으로 함께 사라진다(방어적으로 동작 확인됨). CSS 쪽 `convert_css()`에도 안 쓰는 `span.study-note` 규칙 제거가 들어있다.

## `[e-s]`(영어 원문 + 학습노트, 한국어 번역 없음)

`[e-s]`는 `[study]`의 정반대 방향 파생물이다. `scripts/make_english_study_epubs.py`의 `convert_xhtml()`이 `class="en"`/`class="study-note"`만 남기고 `class="ko"`를 제거해 문단을 재구성한다(`make_korean_only_epubs.py`와 대칭 구조, 자세한 내용은 [make_english_study_epubs.md](scripts/make_english_study_epubs.md) 참고).

- `webui/workflow_runner.py`의 `translate_one()`이 `[study]`를 만드는 모드일 때(`wants_study`) `[e-s]`도 항상 함께 만든다(`wants_english_study = wants_study`) — `[study]`가 완성된 직후, 그 파일을 입력으로 로컬 변환만 하므로 추가 웹 요청이 없다.
- `korean` 전용 모드(`[k-e]`/`[study]` 자체를 안 만드는 모드)에서는 `[e-s]`도 함께 스킵한다.
- 배치 소스 스캔(`source_files()`)과 서재 이관(`webui/book_organizer.py`의 `organize_from_output_dir()`/`organize_single_epub()`, `webui/job_manager.py`의 `english_study_root`)에도 `[e]`/`[k]`/`[k-e]`/`[study]`와 같은 수준으로 반영돼 있다 — vk 스테이징에서 서재로 옮길 때 `[e-s]`도 다른 네 버전과 함께 장르/작가 폴더로 분류된다.
- 서재 루트: `~/Desktop/소설2/[e-s]` (기본값, `JobManager.__init__`의 `english_study_root` 인자로 재정의 가능 — 테스트에서는 반드시 `tmp_path` 하위 값을 주입).

## 검수 파이프라인과의 상호작용

- **품질 검증** (`assess_translations`): 캐시된 텍스트에 노트가 섞여 있어도 `untranslated_identity` 오탐을 유발하지 않는다 — 노트 내용이 원문에는 없으므로 정규화 후에도 원문과 절대 같아지지 않는다.
- **최종 톤/대화/문예 검수**: `[k-e]`만 대상으로 실행되고(기존과 동일), `class="ko"`만 선택하므로 `[study]`를 검수 대상에 넣더라도 `study-note` span은 애초에 걸러진다.
- `[study]`는 톤/대화/용어/형식 4종 최종 검수를 **다시 실행하지 않는다** — 내용이 `[k-e]`와 동일(노트만 추가)하므로 중복 검수 비용을 피한다.

## 순서 변경 소급 적용 (2026-08-08) — 재번역 없이 기존 EPUB만 고치는 법

문단 순서가 "한글→영어"에서 "영어→한글"로 바뀌면서, 그 전에 이미 완성돼 서재에 있던 `[k-e]`/`[study]` 파일들도 소급 반영했다. 두 가지 방법을 썼다:

1. **번역 캐시가 아직 있는 책**: `.webui/jobs/*/work/*/translation/`, 레거시 `소설2/_chatgpt_translate_work/*/` 어딘가에 그 책의 `manifest.json`/`source_sections.json`/`translations/chunk_*.json`이 남아 있으면, 그걸로 `build_epub()`을 다시 호출해 통째로 재조립한다(웹 요청 없음, `guess_average_rating` 같은 네트워크 호출도 안 함 — 순수 로컬 캐시 재사용).
2. **번역 캐시가 이미 사라진 책** (이 job 기반 캐시 시스템이 생기기 전에 완료됐거나 캐시가 정리된 경우): 캐시나 원본 EPUB 없이도 고칠 수 있다 — **이미 완성된 EPUB 파일 자체의 HTML 안에 영어 원문과 한글 번역이 둘 다 이미 들어 있으므로**, `reorder_ko_en_pairs_in_epub(epub_path)` (`scripts/translate_epub_with_chatgpt_web_to_study_epub.py`)가 `<p class="pair">`/`<h2>` 안의 `<span class="en">`/`<span class="ko">` 순서를 그 자리에서 바꿔치기한다. 표지·CSS·OPF 등 나머지는 그대로 두고 xhtml 챕터만 다시 쓴 뒤 `validate_epub()`으로 무결성을 확인한다.

이 두 방법을 합쳐서 서재의 `[k-e]` 426개 중 398개(문단이 있는 파일 전부, 나머지 28개는 애초에 한글 번역 자체가 없는 별개 데이터 문제), `[study]` 179개 전부를 새 순서로 맞췄다. **결론: 번역 캐시가 없다고 해서 재번역이 필요한 건 아니다** — 이미 만들어진 산출물의 형식만 바뀐 경우엔 그 결과물 자체에서 필요한 정보를 다 뽑아낼 수 있다.

## 알려진 예외 (2026-08-02 세션에서 이 구조로 확정되기 전 산출물)

이 4-산출물 구조가 확정되기 **전** 과도기에 완료된 책 2권은 노트가 `[k-e]`에 직접 들어간 상태로 남아 있고 `[study]`는 아직 없다:
- `Tatiana and Alexander - Paullina Simons` (배치로 완료)
- `TED_Master_Transcript_Collection` (`/Users/hyeokjunkong/Desktop/소설2/[s]/`, 특별 우선 작업으로 완료)

사용자가 요청하면 캐시를 재사용해 `[k-e]`는 노트 없이 재조립하고 `[study]`를 새로 만들 수 있다(웹 재번역 불필요). 별도 요청이 없는 한 자동으로 손대지 않는다.

## 재번역 없이 학습노트를 채울 수 없는 경우

번역 캐시 자체가 없는 책(위 "순서 변경 소급 적용" 2번 케이스)은 `[study]`에 노트가 없거나 예전 기준(선별적)으로만 붙어 있어도, **로컬에서는 못 고친다** — 학습노트는 원문에 없는 내용을 모델이 새로 생성하는 것이라, HTML을 아무리 뒤져도 캐시에 없으면 만들어낼 수 없다. 이 경우 유일한 방법은 그 책을 처음부터 다시 번역하는 것(실제 Gemini 웹 요청 필요, 진행 중인 다른 배치와 브라우저 세션이 겹치지 않을 때만 안전).

## 테스트

- `tests/test_epub_integrity.py`
  - `test_split_translation_and_note_separates_marker_from_translation` / `..._returns_empty_note_when_marker_absent`
  - `test_plain_k_e_build_omits_study_notes_by_default` — `[k-e]`(기본)는 노트가 전혀 안 나오는지 확인
  - `test_plain_k_e_build_also_orders_english_then_korean` — `[k-e]`도 영어→한글 순서인지 확인
  - `test_study_epub_orders_english_then_korean_then_study_note` — `[study]`가 영어→한글→노트 순서인지 확인
  - `test_study_epub_builder_renders_study_note_in_its_own_span_and_korean_only_strips_it` — `[study]`에는 노트가 별도 span으로 남고, `[k]` 변환 후에는 노트가 완전히 사라지는지 종단 검증
  - `test_reorder_ko_en_pairs_to_en_ko_*` (4개) / `test_reorder_ko_en_pairs_in_epub_*` (2개) — 캐시 없이 기존 EPUB의 순서만 바꿔치기하는 소급 적용 유틸리티
- `tests/test_web_workflow_runner.py`
  - `test_translation_command_includes_study_output_flag_when_given` / `..._omits_study_output_flag_when_not_given`
  - `test_translate_one_builds_study_epub_alongside_bilingual_and_korean` — `[e-s]`도 함께 만들어지는지 검증
  - `test_translate_one_backfills_missing_english_copy_without_retranslating`
- `[e-s]` 전용 테스트
  - `tests/test_epub_integrity.py`: `test_english_study_conversion_keeps_navigation_and_cover_valid`, `test_english_study_conversion_keeps_english_and_note_but_drops_korean`, `test_english_study_output_name_maps_study_prefix_to_e_s`, `test_english_study_conversion_preserves_previous_output_after_failure`
  - `tests/test_book_organizer.py`: `test_organize_single_epub_files_english_study_prefix_into_genre_folder`, `test_organize_from_output_dir_moves_all_five_versions_when_roots_given`

## 관련 문서
- [translate_epub_with_chatgpt_web_to_study_epub.md](scripts/translate_epub_with_chatgpt_web_to_study_epub.md)
- [make_korean_only_epubs.md](scripts/make_korean_only_epubs.md)
- [make_english_study_epubs.md](scripts/make_english_study_epubs.md)
- [EPUB 배치 번역 중복작업 방지 처리절차](EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md)
