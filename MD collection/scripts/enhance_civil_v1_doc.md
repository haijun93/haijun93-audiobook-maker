# enhance_civil_v1_doc.py

공무원(1차) 시험 대비 **민법(civil law) OX(참/거짓) 학습자료 DOCX**를 다시 파싱해, 문항마다 해설을 보강하고 보기 좋게 재조립하는 스크립트. `enhance_management_v1_doc.py`/`enhance_social_insurance_v1_doc.py`/`enhance_labor_ox_updated_doc.py`와 같은 계열(같은 구조, 과목만 다름)의 첫 번째 예시다.

파일: `scripts/enhance_civil_v1_doc.py` (약 750줄)
기본 입력: `~/Desktop/1차 시험/#STD/260416/civil_law_OX_integrated_2026_v1.docx`

## 공통 패턴 (이 계열 스크립트 전체에 해당)

1. **파싱** (`parse_existing_doc`): 기존 DOCX에서 문항(지문/정답 O·X/기존 해설)을 구조화된 객체로 추출.
2. **분류/초점 추출**: 근거 조문·판례(`extract_basis_focus`)와 지문 자체(`extract_statement_focus`) 중 어느 쪽이 이 문제의 핵심 쟁점인지 판단(`select_focus`), 핵심 쟁점 키(`build_focus_key`)와 예시 문구(`build_focus_example`)를 만든다.
3. **해설 재작성** (`build_explanation`): 위 정보를 조합해 일관된 형식의 해설 문단을 만든다.
4. **한국어 텍스트 보정**: `Kiwi`(형태소 분석기)로 붙어있는 한국어 텍스트에 필요한 띄어쓰기를 추가(`needs_spacing`/`space_text`).
5. **재조립** (`build_doc`): `SECTION_ORDER`(과목별 대단원 순서)에 따라 문항을 정렬해 새 DOCX를 생성, 원본은 먼저 백업(`backup_file`).

## 민법 전용 대단원 순서 (`SECTION_ORDER`)

```
총칙·권리능력·법원 / 의사표시·법률행위·대리 / 물건·물권 / 채권·계약·불법행위 / 법인 / 친족·상속 / 기타
```

## CLI

```bash
python3 scripts/enhance_civil_v1_doc.py [입력 docx 경로(기본값 위 참고)]
```

## 관련 문서
- [enhance_management_v1_doc.md](enhance_management_v1_doc.md), [enhance_social_insurance_v1_doc.md](enhance_social_insurance_v1_doc.md), [enhance_labor_ox_updated_doc.md](enhance_labor_ox_updated_doc.md) — 같은 패턴의 다른 과목
- [prepare_docx_for_reader_exports.md](prepare_docx_for_reader_exports.md), [optimize_pdfs_for_kindle_scribe.md](optimize_pdfs_for_kindle_scribe.md) — 이 스크립트가 만든 DOCX를 리더 기기용으로 내보내는 다음 단계
