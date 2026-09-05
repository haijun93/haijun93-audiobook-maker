# prepare_docx_for_reader_exports.py

`export_docx_to_pdf_epub.py`/`optimize_pdfs_for_kindle_scribe.py`로 내보내기 전에, 공무원 시험 OX 학습자료 DOCX에서 **더 이상 필요 없는 안내 문구 줄**을 제거하고 서식을 정리하는 전처리 스크립트.

파일: `scripts/prepare_docx_for_reader_exports.py`

## 동작

- `REMOVE_EXACT_LINES`에 정확히 일치하는 문단(예: `"정답은 9개씩 묶어서 확인하면 오답 패턴이 더 잘 보인다."`, `"OX 정답표"`, `"최종 정오표"` 등 — 편집 과정에서 남은 안내/헤더 문구)을 통째로 삭제.
- 글꼴을 `Malgun Gothic`(+ `w:eastAsia` 속성)으로 통일해 리더 앱/PDF 내보내기 시 한글이 깨지지 않게 한다.

## CLI

```bash
python3 scripts/prepare_docx_for_reader_exports.py <docx 파일...>
```

## 파이프라인 순서

```
prepare_docx_for_reader_exports.py (안내문구 제거·서식 정리)
  → optimize_pdfs_for_kindle_scribe.py (Scribe/Kindle6 레이아웃으로 PDF 재생성)
  → export_docx_to_pdf_epub.py (Pages로 PDF/EPUB 내보내기, 필요 시)
```

소설 EPUB 번역 파이프라인과는 무관한, 공무원 시험 학습자료 전용 문서 준비 단계다.

## 관련 문서
- [optimize_pdfs_for_kindle_scribe.md](optimize_pdfs_for_kindle_scribe.md)
- [export_docx_to_pdf_epub.md](export_docx_to_pdf_epub.md)
- [optimize_docx_for_a4_booklet.md](optimize_docx_for_a4_booklet.md)
