# optimize_docx_for_a4_booklet.py

DOCX 문서(공무원 시험 OX 학습자료 등)의 페이지 크기·여백·글꼴을 **A4 책자 인쇄용**으로 최적화하는 스크립트. `python-docx`로 문서를 직접 조작한다.

파일: `scripts/optimize_docx_for_a4_booklet.py`

## 동작

- 페이지 크기를 A4(`8.27" x 11.69"`)로, 여백을 인쇄 여유를 고려한 값(위/아래 0.62", 왼쪽 0.72", 오른쪽 0.62")으로 설정.
- 문서 전체 스타일과 실행(run)의 글꼴을 `Malgun Gothic`(한글 인쇄 가독성)으로 통일, `w:eastAsia` 글꼴 속성도 함께 지정(한글이 별도 동아시아 폰트 설정을 따르는 Word/한글 문서 특성 대응).
- 실행 전 원본을 `<파일명>_<접미사>_<타임스탬프>.docx`로 백업(`backup_file`).

## CLI

```bash
python3 scripts/optimize_docx_for_a4_booklet.py <입력 DOCX> [--output-docx <경로, 기본: 원본 덮어쓰기>]
```

## 이 스크립트의 실제 대상

공무원 시험(`1차 시험`) OX 통합 학습자료 DOCX들을 인쇄해서 종이로 보기 좋게 만들 때 쓴다. 소설 EPUB 번역 작업과는 무관하며, [배치 6: 공무원 시험 학습자료 가공 파이프라인](enhance_civil_v1_doc.md)과 같은 계열이다.

## 관련 문서
- [optimize_pdfs_for_kindle_scribe.md](optimize_pdfs_for_kindle_scribe.md) — 인쇄가 아니라 전자기기 화면용 최적화
- [prepare_docx_for_reader_exports.md](prepare_docx_for_reader_exports.md)
