# export_docx_to_pdf_epub.py

macOS의 **Pages 앱을 AppleScript로 원격 조작**해 DOCX 문서를 PDF와 EPUB으로 동시에 내보내는 스크립트. EPUB 표지는 DOCX 첫 페이지를 이미지로 렌더링(`PyMuPDF`)해 고정한다.

파일: `scripts/export_docx_to_pdf_epub.py`

## 동작

1. `osascript`로 Pages를 실행 → DOCX 열기 → `export ... as PDF` / `export ... as EPUB` 명령으로 두 형식 모두 내보내기 → 문서 닫기(저장하지 않음).
2. `render_pdf_first_page_to_png_bytes()`로 방금 만든 PDF의 첫 페이지를 지정 DPI(`--cover-dpi`, 기본 144)로 렌더링해 EPUB 표지 이미지로 심는다.

## CLI

```bash
python3 scripts/export_docx_to_pdf_epub.py <입력 DOCX> \
  [--output-pdf <경로>] [--output-epub <경로>] [--cover-dpi 144]
```

## 전제 조건 및 성격

- **macOS + Pages 앱이 실제로 설치되어 있어야** 동작한다(AppleScript로 GUI 앱을 원격 조작하므로 헤드리스 서버에서는 쓸 수 없다).
- EPUB 소설 번역 파이프라인과는 무관하고, 개인 학습용 DOCX 문서(공무원 시험 자료 등, [batch 6 문서군](enhance_civil_v1_doc.md) 참고)를 여러 리더 기기용으로 내보내는 문서 준비 파이프라인의 한 단계다.

## 관련 문서
- [prepare_docx_for_reader_exports.md](prepare_docx_for_reader_exports.md) — 내보내기 전 DOCX 정리 단계
- [optimize_pdfs_for_kindle_scribe.md](optimize_pdfs_for_kindle_scribe.md) — 기기별 레이아웃 최적화
