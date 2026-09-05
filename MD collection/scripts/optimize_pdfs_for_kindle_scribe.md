# optimize_pdfs_for_kindle_scribe.py

DOCX 학습자료(공무원 시험 OX 통합본)를 **Kindle Scribe 또는 Kindle 6인치 기기 화면**에 맞는 레이아웃으로 다시 짜서 PDF로 내보내는 스크립트. `optimize_docx_for_a4_booklet.py`가 인쇄용이라면, 이건 전자기기 화면 열람용이다.

파일: `scripts/optimize_pdfs_for_kindle_scribe.py`

## 기기 프로필 (`PROFILE_SETTINGS`)

| 프로필 | 페이지 크기 | 특징 |
|---|---|---|
| `scribe` (기본) | 6.2" x 8.27" | 여백/폰트 크기가 더 크다 |
| `kindle6` | 3.58" x 4.84" | 6인치 기기에서 오른쪽 가장자리 잘림을 줄이기 위해 더 작은 고정 레이아웃 페이지 사용 |

각 프로필은 페이지 크기, 여백, 제목/부제/본문/H1~H3 글자 크기, 줄 간격, 문단 간격, 표 최소 폰트 크기까지 개별 지정되어 있다.

## 기본 대상 파일 (`DEFAULT_DOCX_FILES`, 인자 없이 실행 시 사용)

```
~/Desktop/1차 시험/#STD/260416/civil_law_OX_integrated_2026_v1.docx
~/Desktop/1차 시험/#STD/260416/labor_law_OX_integrated_2026_v1.docx
~/Desktop/1차 시험/#STD/260416/management_OX_integrated_2026_v1.docx
~/Desktop/1차 시험/#STD/260416/social_insurance_law_OX_integrated_2026_v1.docx
```

이 네 과목은 [배치 6: 공무원 시험 학습자료 가공 파이프라인](enhance_civil_v1_doc.md)의 `enhance_civil_v1_doc.py`/`enhance_labor_ox_updated_doc.py`/`enhance_management_v1_doc.py`/`enhance_social_insurance_v1_doc.py`가 만들어내는 산출물과 같은 과목 체계다.

## CLI

```bash
python3 scripts/optimize_pdfs_for_kindle_scribe.py [<docx 파일...>] [--profile {scribe,kindle6}]
```

파일을 지정하지 않으면 위 기본 4개 파일을 처리한다.

## 관련 문서
- [optimize_docx_for_a4_booklet.md](optimize_docx_for_a4_booklet.md)
- [prepare_docx_for_reader_exports.md](prepare_docx_for_reader_exports.md)
- 공무원 시험 학습자료 본문 가공: [enhance_civil_v1_doc.md](enhance_civil_v1_doc.md) 등 배치 6 문서군
