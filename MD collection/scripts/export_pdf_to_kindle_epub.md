# export_pdf_to_kindle_epub.py

PDF를 Kindle용 EPUB으로 변환하는 스크립트. **단독 CLI 도구이면서 동시에, EPUB 번역 배치 파이프라인이 PDF 원서를 처리할 때 내부적으로 재사용하는 라이브러리이기도 하다** — `webui/workflow_runner.py`가 `from export_pdf_to_kindle_epub import build_epub as build_reflow_epub`로 임포트해서 쓴다.

파일: `scripts/export_pdf_to_kindle_epub.py`

## 두 가지 모드

- `--mode reflow` (기본): PDF 텍스트를 페이지 단위로 추출(`PyMuPDF`/`fitz`)해 EPUB 텍스트로 재구성 — 글자 크기 조절 등 리더 기기의 재흐름 기능을 그대로 쓸 수 있다.
- `--mode fixed`: 원본 페이지 레이아웃을 그대로 보존.

## 파일명 정제 (`clean_pdf_title`)

유출 사이트에서 받은 PDF는 파일명이 `_OceanofPDF.com_Cage_of_Ice_and_Echoes_-_Pam_Godwin` 식으로 지저분한 경우가 많다. 이걸 그대로 EPUB의 `dc:title`에 넣으면 표지 플레이스홀더, 온라인 표지 검색, 번역 프롬프트까지 지저분한 제목이 퍼진다 — 그래서 `oceanofpdf.com` 등 워터마크와 `[k]`/`[k-e]` 접두사를 먼저 제거하고 사람이 읽을 수 있는 제목으로 정제한다.

## CLI

```bash
python3 scripts/export_pdf_to_kindle_epub.py <입력 PDF> [--output-epub <경로>] [--mode {reflow,fixed}]
```

## 배치 파이프라인에서의 역할

`webui/workflow_runner.py`의 `prepare_epub()`이 소스 파일 확장자가 `.pdf`일 때 이 스크립트의 `build_epub(source, converted, language="en", page_label="Page")`를 직접 호출해 번역 가능한 EPUB으로 먼저 변환한 뒤, 그 결과물을 `translate_epub_with_chatgpt_web_to_study_epub.py`에 넘긴다 — 즉 PDF 원서도 배치 번역 대상이 될 수 있는 것은 이 스크립트 덕분이다.

## 관련 문서
- [translate_epub_with_chatgpt_web_to_study_epub.md](translate_epub_with_chatgpt_web_to_study_epub.md)
- [EPUB 배치 번역 중복작업 방지 처리절차](../EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md)
