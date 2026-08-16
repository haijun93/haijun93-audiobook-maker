# EPUB 배치 번역 중복작업 방지 처리절차

이 문서는 폴더 일괄 번역 배치(`webui/workflow_runner.py`의 `batch_translation` 작업)가 같은 책을 두 번 번역하지 않도록 실제로 수행하는 처리 절차를 설명한다. 새로 설계된 절차가 아니라, 저장소에 이미 구현되어 실제로 동작 중인 코드를 그대로 기술한 것이다.

저장소 루트: `/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker`
관련 파일: `webui/workflow_runner.py`, `webui/book_organizer.py`

## 전체 구조 — 3단계 방어선

배치는 소스 폴더(예: `/Users/hyeokjunkong/Desktop/소설2/new books from vk`)를 스캔할 때마다, 아래 3단계를 순서대로 통과한 파일만 실제로 번역한다.

```
소스 폴더 스캔 (source_files)
  └─ 1단계: 파일명 사전 필터        ─ 이미 [k] 서재에 "같은 파일명"으로 있으면 목록에서 아예 제외
       ↓ (통과한 파일들 = 배치 대상 목록)
run_batch() 루프 진입
  └─ 2단계: 서지정보(제목/작가) 대조 ─ finished/서재 등록부와 퍼지 매칭, 일치하면 원본을 finished로 이동하고 스킵
       ↓ (매치 안 됨)
  └─ 3단계: 산출물 존재 여부 확인   ─ translate_one() 안에서, [k-e]/[k] 결과물이 이미 있으면 번역 자체를 건너뜀
       ↓ (셋 다 통과해야) 실제 번역 실행
```


> **[2026-08-16 현행화 업데이트]**:
> 1. **다중 계정 병렬 프로필 락 (.audiobook_web_profile.lock)**: Gemini 3개 계정 및 ChatGPT 1개 계정이 서로 다른 포트/프로필 디렉터리를 사용하여 프로세스 간 경합 없이 중복 없는 안전한 병렬 번역을 수행합니다.
> 2. **산출물 표준 위치 스캔**: 의 4대 표준 서재(, , , )를 직접 스캔하여 임시 작업 폴더 유무와 관계없이 기존 완성작을 100% 탐지하여 중복 번역을 원천 차단합니다.

## 1단계 — 파일명 사전 필터 (`source_files()`)

`webui/workflow_runner.py:354`의 `source_files()`가 배치 대상 목록을 만들 때 적용하는 필터.

1. 확장자 필터: `.epub`, `.pdf`, `.mobi`만 대상으로 한다.
2. 출력 트리 제외: `output_root`(배치 결과물이 쌓이는 폴더, 보통 소스 폴더 자신)에 속한 파일은 제외한다.
3. 접두사 제외: 파일명이 `[k]`, `[k-e]`, `[e]`, `[study]`, `[e-s]` 중 하나로 시작하면 제외한다 (이미 번역된 산출물 자체가 소스로 다시 잡히는 것을 방지).
4. **원본 파일명 기준 중복 제외**: `get_existing_korean_books(korean_root)` (`webui/book_organizer.py:455`)가 `/Users/hyeokjunkong/Desktop/소설2/[k]` 서재 폴더 전체를 재귀적으로 훑어, `"[k] " + 원본파일명` 형태의 파일이 존재하면 그 `원본파일명`을 집합에 담는다. 배치 대상 목록에서 이 집합에 들어있는 파일명과 **정확히 일치**하는 파일은 제외한다.

이 단계는 **파일명 문자열 완전 일치**만 잡아낸다. 원본 파일명이 조금이라도 다르면(리네임, 워터마크 태그 차이 등) 이 단계에서는 걸러지지 않고 2단계로 넘어간다.

## 2단계 — 서지정보(제목/작가) 대조 (`run_batch()` 내부)

`run_batch()`가 파일 목록을 확정한 직후, 배치 시작 시점에 **한 번** 아래 세 가지 등록부를 합쳐 `finished_registry`를 만든다 (`webui/workflow_runner.py:449`).

| 등록부 | 생성 함수 | 대상 |
|---|---|---|
| finished 폴더 | `build_finished_registry(FINISHED_ROOT)` | `/Users/hyeokjunkong/Desktop/소설2/finished` — 이미 번역이 끝난 원서 원본을 모아둔 폴더 |
| 정적 스냅샷 | `build_html_collection_registry(K_COLLECTION_HTML)` | `k_collection_blog.html`에 내장된 `booksData` — `[k]` 서재 전체를 요약한 정적 카탈로그 |
| 실시간 서재 스캔 | `build_library_registry(K_LIBRARY_ROOT)` | `/Users/hyeokjunkong/Desktop/소설2/[k]` 폴더를 배치 시작 시점에 직접 재귀 스캔 — 정적 스냅샷 생성 이후 새로 서재에 편입된 책까지 잡아낸다 |

배치가 각 파일을 처리하기 직전, `extract_metadata_from_epub()`으로 그 EPUB의 `dc:title`/`dc:creator`를 읽고 `find_finished_match()`로 위 등록부와 대조한다.

- **제목 정규화** (`normalize_book_title`): 괄호 속 부제/에디션 표기 제거, `"a novel"`/`"unabridged"`/`"complete series"`/`"collection"` 등 잡음 문구 제거, 구두점 제거, 소문자화.
- **작가 정규화** (`normalize_book_author`): `,`/`&`/`and`로 분리 후 단어를 정렬 — `"Godwin, Pam"`과 `"Pam Godwin"`이 같은 값이 되도록 흡수.
- **매칭 기준**: 정규화한 제목의 `SequenceMatcher` 유사도가 **0.92 이상**이어야 후보가 되고, 양쪽 작가 정보가 모두 있으면 작가 유사도도 **0.6 이상**이어야 최종 매치로 인정한다 (작가 정보가 없는 쪽이 있으면 제목만으로 판단).
- **매치되면**: `archive_duplicate_source()`가 그 원본 파일을 `FINISHED_ROOT`로 이동시키고(이름 충돌 시 `(2)`, `(3)` 접미사 자동 부여), `batch_status.json`에 `"status": "skipped"`로 기록한 뒤 번역 없이 다음 파일로 넘어간다.

이 단계는 **파일명이 달라도** EPUB 내부 메타데이터로 판단하므로 1단계보다 넓게 잡아낸다. 다만 EPUB의 `dc:title`/`dc:creator`가 비어 있거나 부정확한 파일은 놓칠 수 있다.

**2026-08-05부터**: `run_batch()`가 이번 실행에서 책 한 권을 새로 완료할 때마다(`completed_items.append({"status": "done"})` 직후) 그 책의 원본도 `archive_duplicate_source()`로 **`source_dir/finished/`**(예: `새 책 폴더/finished/`)로 옮긴다. 이건 위 `FINISHED_ROOT`(`소설2/finished`, 배치 시작 시점에 등록부로 읽어 들이는 전역 폴더)와는 다른, **소스 폴더 자체에 딸린 보관함**이다 — 보관 실패(권한 문제 등)는 경고만 찍고 그 책의 성공 여부에는 영향을 주지 않는다. `source_files()`는 이 `finished/` 하위를 항상 스캔에서 제외하므로(`recursive=True`로 돌려도) 방금 보관한 책이 다음 스캔에서 새 소스로 다시 잡히지 않는다.

## 3단계 — 산출물 존재 여부 확인 (`translate_one()`)

앞의 두 단계를 통과했더라도, 실제 번역을 시작하기 직전 `translate_one()` (`webui/workflow_runner.py:219`)이 마지막으로 한 번 더 확인한다.

```python
if not args.overwrite and all(path.is_file() and path.stat().st_size > 0 for path in desired_outputs):
    print(f"SKIP existing translation outputs: {title}")
```

- `desired_outputs`는 `--translation-output` 설정(`both`/`korean`/`bilingual`)에 따라 `[e] {제목}.epub`(정제된 영어 원문 사본), `[k-e] {제목}.epub`, `[k] {제목}.epub`, `[study] {제목}.epub`(토익 학습노트 포함 버전), `[e-s] {제목}.epub`(영어 원문 + 학습노트, 한국어 번역 없음) 중 필요한 파일들이다([자세히](../EPUB%20영어학습자용%20%5Bstudy%5D%20버전%20토익%20학습노트%20절차.md)). `[study]`는 `[k-e]`(대조본)를 만드는 모드일 때만 함께 요구되고, `[e-s]`는 `[study]`를 만드는 모드일 때만 함께 요구되며, `[e]`는 번역 모드와 무관하게 항상 요구된다. 경로는 배치의 `output_root`(보통 소스 폴더 자신) 아래 `[e]/`, `[k-e]/`, `[k]/`, `[study]/`, `[e-s]/` 하위 폴더.
- `title`은 `readable_stem(source)`로 만든, 정제된 파일명 기준 제목이다.
- 필요한 산출물이 **전부 존재하고 크기가 0보다 크면** 번역을 아예 실행하지 않고 SKIP한다. `--overwrite` 옵션을 주면 이 단계를 무시하고 강제로 다시 번역한다.

이 단계 덕분에, 배치 작업(`workflow_runner.py`)이 도중에 중단됐다가 **다시 처음부터 전체 폴더를 재스캔해도** 이미 끝난 책은 몇 초 안에 SKIP되고, 실제로는 아직 끝나지 않은 책부터 이어서 진행된다. `run_batch()`는 재시작할 때마다 `completed_items` 목록 자체는 새로 만들지만(누적되지 않음), 이 3단계 파일 존재 확인이 있어 실질적으로는 "이어서 진행"하는 것과 같은 효과를 낸다.

## work_dir 재사용 안정성 (`find_existing_item_work_dir`) — 2026-08-04 수정

3단계(산출물 존재 확인)가 정상 동작하려면, 애초에 `translate_one()`이 그 책의 **예전 작업 디렉터리**(청크 캐시가 쌓여 있는 `work/NNNN_제목/`)를 다시 찾아내야 한다. 이 매칭이 깨지면 산출물이 이미 디스크에 있어도 3단계 SKIP까지 도달하지 못하고, 빈 새 work_dir을 만들어 웹 번역을 처음부터 다시 시도하게 된다.

**버그였던 방식**: `run_batch()`가 각 책의 `item_work` 경로를 `f"{index:04d}_{readable_stem(source)[:80]}"`로 계산했는데, 여기서 `index`는 **이번 실행에서 정렬된 파일 목록 안에서의 위치**였다. `--priority-substrings`에 새 문자열을 추가하는 등으로 정렬 순서가 한 칸이라도 바뀌면, 이미 완료된 책이 예전과 다른 `index`를 받아 **비어 있는 새 work_dir**로 매핑됐다. 3단계가 그 새 디렉터리에서 청크 캐시를 찾지 못하니 `needs_translation=True`가 되어 웹 번역을 처음부터 재시도했다.

실제로 이 버그로 `Diana Gabaldon - Outlander Series 1-10 Anthology`가 `work/0016_Outlander.../`(캐시 1522청크, `[k-e]`/`[k]` 산출물 완성 상태)에서 `work/0019_Outlander.../`(빈 캐시)로 잘못 매핑되어, 563청크를 낭비하며 재번역하다가 `untranslated_identity` 품질 검증에 걸려 3회 시도 모두 실패 처리됐다.

**수정**: `find_existing_item_work_dir(work_root, source)` (`webui/workflow_runner.py`)가 `item_work` 계산 전에 먼저 실행된다. `work_root` 아래 모든 하위 디렉터리를 훑어 `translation/manifest.json`을 읽고, 그 안의 `input_epub` 절대경로가 지금 처리하려는 소스 파일과 **정확히 일치**하는 디렉터리를 찾으면 그것을 그대로 재사용한다. 못 찾을 때만 `index` 기반 새 경로로 폴백한다.

```python
item_work = find_existing_item_work_dir(args.work_dir.resolve(), source) or (
    args.work_dir.resolve() / f"{index:04d}_{readable_stem(source)[:80]}"
)
```

이 매칭은 `index`(정렬 순서)가 아니라 `manifest.json`에 기록된 **원본 파일의 절대경로**를 기준으로 하므로, `--priority-substrings`를 바꾸거나 소스 폴더에 파일이 추가/삭제되어 정렬 순서가 흔들려도 흔들리지 않는다. 이후 어떤 재정렬이 일어나도 이미 진행된 책은 항상 자기 work_dir을 다시 찾는다.

관련 테스트: `tests/test_web_workflow_runner.py`의 `test_find_existing_item_work_dir_matches_by_recorded_input_epub`, `..._ignores_other_books`, `..._returns_none_when_work_root_missing`.

## 파일명 정제가 중복판정에 미치는 영향 (`readable_stem`, `clean_metadata_field`)

원본 파일명에는 다운로드 출처를 나타내는 워터마크(`OceanofPDF.com`, `readrobe.com`, `@my_fiction_books` 등)나 저자명이 중복 표기된 경우가 섞여 있다. `readable_stem()` (`webui/workflow_runner.py:66`)이 이런 잡음을 제거해 산출물 파일명(`title`)을 만들기 때문에, **워터마크만 다르고 실제로는 같은 책인 두 원본 파일**이 산출물 단계에서는 같은 파일명으로 수렴해 3단계(산출물 존재 확인)에서 자연스럽게 걸러지는 경우가 있다. 다만 이는 어디까지나 파일명 정제의 부수효과이며, 1·2단계처럼 명시적으로 "중복이다"라고 판단하는 로직은 아니다.

## 알려진 한계

1. **같은 배치 실행 안에서 동시에 존재하는 동일 도서의 두 변형 파일은 서로 잡아내지 못할 수 있다.** `finished_registry`는 `run_batch()` 시작 시점에 **딱 한 번** 만들어지고, 배치 도중 완료된 책은 `K_LIBRARY_ROOT`(`[k]` 서재)나 `FINISHED_ROOT`로 자동 편입되지 않는다(그건 `book_organizer.py`의 `organize_from_output_dir`가 담당하는 별도 절차이며 배치 번역 자체가 호출하지 않는다). 따라서 예를 들어 `"제목.epub"`과 `"제목_renamed.epub"`처럼 파일명이 다른 같은 책 두 권이 **같은 배치 목록에 동시에 들어있으면**, 1단계(파일명 완전 일치 아님)와 2단계(배치 시작 시점엔 둘 다 아직 "완료 전"이라 등록부에 없음) 모두 통과해 **둘 다 번역될 수 있다.** 이런 파일들은 배치를 돌리기 전에 사람이 미리 하나를 정리해두는 것이 안전하다.
2. **EPUB 메타데이터가 부정확하면 2단계가 무력화된다.** `dc:title`/`dc:creator`가 비어 있거나 원서와 무관한 값이면 서지 대조 자체가 성립하지 않는다.
3. **재작명/외부 변경으로 인한 배치 목록과 실제 파일의 불일치**는 이 절차가 다루지 않는다. 예를 들어 배치가 파일 목록을 확정한 뒤 사람이 그 파일을 지우거나 이름을 바꾸면, 배치는 그 파일이 사라진 이름으로 계속 재시도하다가 결국 실패 처리한다. 이런 경우 재발을 막으려면 아래의 수동 제외 절차를 쓴다.

## 수동 제외 절차 (`_excluded_do_not_retry/`)

위 자동 절차로 걸러지지 않는 예외적인 경우(예: 배치 도중 파일이 외부에서 삭제/재작명돼 이후 재시도가 계속 실패하고, 사용자가 명시적으로 "이 책은 다시 시도하지 말라"고 지시한 경우)를 위한 관행이다. 코드로 강제되는 절차는 아니고, 소스 폴더 안에 `_excluded_do_not_retry/` 하위 폴더를 만들어 해당 원본 EPUB을 그 안으로 옮겨두는 방식이다. `source_files()`는 소스 폴더를 비재귀(`recursive` 옵션이 꺼져 있으면) 또는 재귀적으로 스캔하는데, 배치가 재귀 스캔이 아닌 한 하위 폴더 안의 파일은 애초에 목록에 잡히지 않으므로 이후 어떤 배치 재시작에도 다시 집히지 않는다.

실제 적용 사례: `job b0282cd32bee4d0ea73e7be8eb9d0796` 배치 도중 `"Naked in Death Nora Roberts (2).epub"` 타겟이 외부에서 사라지고 `"Naked in death - Nora Roberts.epub"`라는 다른 이름의 파일만 남아 배치가 이를 새 소스로 오인해 재시도하려는 상황이 발생했다. 사용자가 재시도하지 말라고 명시적으로 지시해, 해당 파일을 `/Users/hyeokjunkong/Desktop/소설2/new books from vk/_excluded_do_not_retry/`로 이동시켜 이후 배치 재스캔에서 제외했다.

## 요약: 새 책이 배치에서 최종적으로 번역되기까지

```
원본 파일 발견
  → [1단계] [k] 서재에 같은 파일명 있음? ─ 있으면 제외
  → [2단계] 제목/작가가 finished·서재 등록부와 0.92(제목)/0.6(작가) 이상 유사? ─ 맞으면 원본을 finished로 이동, 스킵
  → [3단계] [k-e]/[k] 산출물이 이미 존재하고 비어있지 않음? ─ 있으면 SKIP
  → 위 세 관문을 모두 통과해야 실제로 번역 서브프로세스를 실행한다.
```
