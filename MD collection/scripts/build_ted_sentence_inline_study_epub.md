# build_ted_sentence_inline_study_epub.py

`build_ted_transcript_study_epub.py`와 같은 TED 대본/번역 로직(`Talk`, `Segment`, `translate_talk`, `unique_talks`를 그대로 임포트)을 재사용하되, 결과물 레이아웃이 다르다 — 문단 단위 대조가 아니라 **문장 하나하나를 영어 원문 바로 아래(인라인)에 한국어 번역과 함께 배치**하는 EPUB을 만든다.

파일: `scripts/build_ted_sentence_inline_study_epub.py`

## 문장 분리 처리

`ABBREVIATIONS` 목록(`Mr.`, `Dr.`, `U.S.`, `e.g.` 등)을 문장 종결 마침표로 오인하지 않도록 제외하면서 대본을 문장 단위로 정확히 분할한다 — 영어 문장 분리에서 흔한 함정(약어 뒤 마침표)을 처리하기 위한 전용 규칙.

## CLI

```bash
python3 scripts/build_ted_sentence_inline_study_epub.py \
  [<대본 텍스트 파일...>] \
  --output <출력 epub, 기본: .work/TED_Transcript_Based_Sentence_Inline_English_Korean_Study.epub> \
  --work-dir <작업 디렉터리> \
  --model gemma4:26b --ollama-url http://127.0.0.1:11434/api/generate \
  --max-chars 7000 --timeout 1200 \
  [--skip-translation] [--limit N]
```

인자를 지정하지 않으면 `build_ted_transcript_study_epub.py`와 같은 기본 첨부파일 경로(`DEFAULT_ATTACHMENT_PATHS`)를 사용한다.

## 관련 문서
- [build_ted_transcript_study_epub.md](build_ted_transcript_study_epub.md) — 이 스크립트가 로직을 가져오는 기반 모듈
