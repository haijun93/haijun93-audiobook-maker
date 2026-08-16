# make_korean_only_epubs.py

한영 대조(`[k-e]`) EPUB에서 영어 부분을 제거해 한국어 전용(`[k]`) EPUB을 만드는 스크립트. `translate_epub_with_chatgpt_web_to_study_epub.py`가 만든 `[k-e]` 결과물로부터 파생 산출물을 만드는 후처리 단계다.

파일: `scripts/make_korean_only_epubs.py`

## 언제 쓰는가

- `webui/workflow_runner.py`의 `translate_one()`이 `--translation-output both`(기본값)일 때 책마다 자동으로 호출한다.
- 배치 밖에서 특정 책 하나만 수동으로 `[k]` 산출물을 만들어야 할 때(예: 수동 재시도로 `[k-e]`만 새로 완성했을 때) `convert_epub()`을 직접 호출하거나, 폴더 단위 CLI를 사용한다.

## 변환 방식

두 가지 원문 EPUB 구조를 모두 지원한다(`uses_structured_pairs()`로 자동 판별):

1. **구조화된 대조 쌍** (`<p class="pair">` 안에 `class="ko"`/`class="en"` span): `class="ko"` 텍스트만 남기고 문단을 재구성, `class="en"` 요소와 `xml:lang="en"` 요소를 통째로 제거.
2. **인라인 괄호 병기** (구조화되지 않은 경우): 괄호 안 내용에 영문자가 있고 한글이 없으면 그 괄호째 제거(`strip_inline_english_parentheticals`) — 중첩 괄호, 균형 맞추기, 중복 공백/마침표 정리까지 처리.

그 외에 CSS에서 `.en`/`.pair`/`.study-note` 스타일 규칙 제거, OPF의 `dc:identifier`(새 UUID 재발급)·`dc:language`(`ko`로 변경)·`dcterms:modified` 갱신, `"Kindle EPUB"→"한국어판"`/`"Front Matter"→"앞부분"` 라벨 치환을 수행한다.

`[k-e]`는 학습노트가 없는 순수본이라 원래 해당 없지만, 혹시 `[study]`(토익 학습노트 포함 버전, [자세히](../EPUB%20영어학습자용%20%5Bstudy%5D%20버전%20토익%20학습노트%20절차.md))를 이 변환기에 넣더라도 `class="study-note"` span은 `class="ko"`가 아니므로 문단 재구성 시 자동으로 함께 제거된다 — 이 스크립트를 따로 고칠 필요가 없었다.

## 안전장치

- 변환 전 `epub_integrity.validate_epub()`으로 **원본(`[k-e]`)의 무결성**을 먼저 검증하고, 실패하면 변환 자체를 하지 않는다.
- 변환 후 결과물도 다시 `validate_epub()`으로 검증하고, 실패하면 예외를 던진다(불완전한 `[k]` 파일이 조용히 남지 않도록).
- `remove_readrobe_text_from_epubs.scrub_epub()`으로 유출 사이트 워터마크 최종 제거.
- 출력이 이미 존재하고 `--overwrite`가 아니면, 재변환 대신 기존 파일의 워터마크만 다시 스크럽하고 무결성만 재검증한 뒤 스킵(`skipped: 1`)한다.

## 단일 파일 변환 (배치 파이프라인이 실제로 쓰는 방식)

CLI가 폴더 단위로만 동작하므로, 책 한 권만 변환할 때는 함수를 직접 호출한다(`webui/workflow_runner.py`도 이렇게 사용):

```bash
PYTHONPATH="<저장소 루트>:<저장소 루트>/scripts" python3 -c "
from pathlib import Path
from make_korean_only_epubs import convert_epub, output_name

src = Path('<... [k-e] 파일 경로 ...>')
dst = src.parent.parent / '[k]' / output_name(src.name)
dst.parent.mkdir(parents=True, exist_ok=True)
print(convert_epub(src, dst, overwrite=False))
"
```

`output_name()`은 `"[k-e] 제목.epub"` → `"[k] 제목.epub"` 규칙으로 파일명을 바꾼다.

## CLI (폴더 단위)

```bash
python3 scripts/make_korean_only_epubs.py <폴더> [--overwrite]
```

폴더 안의 `[k-e]*.epub` 전체를 찾아 각각 옆에 대응하는 `[k]*.epub`을 만든다. `--overwrite` 없이 재실행하면 이미 만들어진 파일은 스킵(워터마크/무결성만 재확인).

## 관련 문서
- [translate_epub_with_chatgpt_web_to_study_epub.md](translate_epub_with_chatgpt_web_to_study_epub.md) — `[k-e]` 원본을 만드는 상위 파이프라인
- [EPUB 배치 번역 중복작업 방지 처리절차](../EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md) — `translate_one()`이 `[k-e]`/`[k]` 둘 다 있는지 확인해 재실행을 스킵하는 로직에서 이 스크립트의 산출물이 사용된다
- [EPUB 영어학습자용 [study] 버전 토익 학습노트 절차](../EPUB%20영어학습자용%20%5Bstudy%5D%20버전%20토익%20학습노트%20절차.md)
