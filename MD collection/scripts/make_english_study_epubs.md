# make_english_study_epubs.py

영어학습용 대조본(`[study]`) EPUB에서 한국어 번역 부분을 제거해 **영어 원문 + 학습노트만 남긴** `[e-s]` EPUB을 만드는 스크립트. `make_korean_only_epubs.py`(한국어만 남기는 변환기)의 정반대 역할로, 같은 `<p class="pair">`/`<h2>` 구조에서 이번엔 `class="en"`/`class="study-note"`만 남기고 `class="ko"`를 제거한다. 2026-08-09 사용자 요청으로 도입했다.

파일: `scripts/make_english_study_epubs.py`

## 왜 필요한가

`[study]`는 영어 원문 + 한국어 번역 + 학습노트가 모두 있는 대조본이다. 한국어 번역 없이 **영어 원문을 그대로 읽으면서 학습노트만 참고하고 싶은 경우**(중급 이상 학습자, 원서 몰입 독서)를 위해 한국어 번역 줄만 뺀 버전이 `[e-s]`다.

## 언제 쓰는가

- `webui/workflow_runner.py`의 `translate_one()`이 `[study]`를 만드는 경우(= `--translation-output`이 `both`/`bilingual`일 때) 책마다 자동으로 `[study]` 완성 직후 호출한다 — 추가 웹 번역 요청 없이 이미 완성된 `[study]` 파일에서 로컬로 파생된다.
- 서재에 이미 있는 기존 `[study]` 책들에서 소급으로 `[e-s]`를 만들 때는 폴더 단위 CLI를 쓴다(캐시나 원본 EPUB 없이도, 이미 완성된 `[study]` 파일의 HTML 안에 영어 원문과 학습노트가 이미 들어 있으므로 재번역이 필요 없다).

## 변환 방식

`<p class="pair">` 문단마다 `class="en"` 텍스트와(있으면) `class="study-note"` 텍스트만 남기고 `class="ko"` 텍스트는 버린 뒤 문단을 재구성한다. `<h2>`(제목/헌사 같은 전체 대문자 짧은 텍스트) 안의 `class="ko"` span은 일반 트리 순회로 제거한다. 그 외에:

- CSS에서 `span.en`(영어를 회색/축소로 보이게 하던 규칙 — 이제 영어가 본문이므로 불필요)과 `p.pair` 레이아웃 규칙을 제거한다. `span.study-note` 스타일은 그대로 남겨 노트가 계속 눈에 띄게 한다.
- OPF의 `dc:identifier`(새 UUID, `"::english-study-only"` 접미사)·`dc:language`(`en`으로 변경)·`dcterms:modified`를 갱신한다.
- 각 xhtml 챕터의 `<html xml:lang="ko" lang="ko">`도 `en`으로 바꾼다(본문이 한국어에서 영어 중심으로 바뀌었으므로).

## 안전장치

`make_korean_only_epubs.py`와 동일한 패턴을 그대로 따른다:

- 변환 전 `epub_integrity.validate_epub()`으로 **원본(`[study]`)의 무결성**을 먼저 검증하고, 실패하면 변환 자체를 하지 않는다.
- 변환 후 결과물도 다시 `validate_epub()`으로 검증하고, 실패하면 예외를 던진다.
- `remove_readrobe_text_from_epubs.scrub_epub()`으로 유출 사이트 워터마크 최종 제거.
- 출력이 이미 존재하고 `--overwrite`가 아니면, 재변환 대신 기존 파일의 워터마크만 다시 스크럽하고 무결성만 재검증한 뒤 스킵(`skipped: 1`)한다.

## 단일 파일 변환 (배치 파이프라인이 실제로 쓰는 방식)

```bash
PYTHONPATH="<저장소 루트>:<저장소 루트>/scripts" python3 -c "
from pathlib import Path
from make_english_study_epubs import convert_epub, output_name

src = Path('<... [study] 파일 경로 ...>')
dst = src.parent.parent / '[e-s]' / output_name(src.name)
dst.parent.mkdir(parents=True, exist_ok=True)
print(convert_epub(src, dst, overwrite=False))
"
```

`output_name()`은 `"[study] 제목.epub"` → `"[e-s] 제목.epub"` 규칙으로 파일명을 바꾼다.

## CLI (폴더 단위, 하위 폴더 재귀 탐색)

```bash
python3 scripts/make_english_study_epubs.py <[study] 폴더> [--output-root <출력 폴더>] [--overwrite]
```

`<[study] 폴더>` 안(장르/작가 하위 폴더 포함)의 `[study]*.epub` 전체를 찾아, `--output-root`(생략 시 형제 `[e-s]` 폴더)에 같은 상대 경로 구조로 `[e-s]*.epub`을 만든다.

2026-08-09에 서재 전체(`/Users/hyeokjunkong/Desktop/소설2/[study]`, 179권)에 다음처럼 한 번 소급 실행했다:

```bash
python3 scripts/make_english_study_epubs.py "$HOME/Desktop/소설2/[study]" --output-root "$HOME/Desktop/소설2/[e-s]"
```

## 관련 문서
- [make_korean_only_epubs.md](make_korean_only_epubs.md) — 반대 방향(한국어만 남기는) 변환기, 이 스크립트가 그대로 따라 한 패턴
- [translate_epub_with_chatgpt_web_to_study_epub.md](translate_epub_with_chatgpt_web_to_study_epub.md) — `[study]` 원본을 만드는 상위 파이프라인
- [EPUB 영어학습자용 [study] 버전 토익 학습노트 절차](../EPUB%20영어학습자용%20%5Bstudy%5D%20버전%20토익%20학습노트%20절차.md)
