# enhance_labor_ox_updated_doc.py

`enhance_civil_v1_doc.py` 계열 중 **가장 많이 발전된 버전**(약 1,300줄). **노동법 OX 학습자료**를 "2026 대비형"으로 보강하며, 다른 과목 스크립트에는 없는 품질관리·최신경향 반영 기능이 추가되어 있다.

파일: `scripts/enhance_labor_ox_updated_doc.py`
기본 입력: `~/Desktop/1차 시험/#STD/260416/labor_law_OX_integrated_2026_v1.docx`
보조 소스: `.work/labor_ox_2026/노동법_OX_통합본_2026최종검수.json` (`SOURCE_JSON`)

## 노동법 전용 대단원 순서 (`SECTION_ORDER`)

```
헌법·총론 / 근로기준법 총칙·근로계약 / 임금·근로시간·휴일·휴가 / 취업규칙·인사·징계·해고 /
개별적 근로관계법 / 노동조합 / 단체교섭·단체협약 / 쟁의행위·노동쟁의조정 / 부당노동행위·노동위원회 / 기타
```

## 다른 과목 스크립트에 없는 기능

- **저품질 문항 자동 제거** (`is_low_quality_ox_statement`, `LOW_QUALITY_OX_STATEMENT_RE`): 지문이 "ㄱ, ㄴ" / "①, ②" 나열만 있고 실제 문장 서술이 없는 문항을 감지해 제거(`removed_low_quality` 카운트로 결과에 보고).
- **문장 성분 점검** (`has_sentence_predicate`, `is_context_free_fragment`): 서술어가 없거나 문맥 없이는 이해할 수 없는 조각 문장인지 판별.
- **쓸모없는 해설 정리** (`strip_useless_explanation`): 정보 없이 반복되는 상투적 해설 문구 제거.
- **법령 용어 치환** (`apply_legal_replacements`): 개정으로 바뀐 법령 용어를 최신 표현으로 일괄 치환.
- **최근 출제 경향 반영** (`load_recent_trend_entries` / `compute_recent_trend`): `SOURCE_JSON`에서 최근 기출 경향 데이터를 불러와 해설에 반영.
- **함정 유형 분류/위원회 노트/암기법**: `enhance_social_insurance_v1_doc.py`와 같은 개념(`classify_trap`, `find_committee_note`, `select_guide`, `select_mnemonic`)을 그대로 갖고 있다.
- **유사 진위형 문항 비교** (`find_similar_true_statements`): 같은 쟁점을 다루는 다른(정답 O인) 문항을 찾아 대조 설명을 붙인다(`explain_with_manual_rule`로 수동 규칙 우선 적용).

## CLI

```bash
python3 scripts/enhance_labor_ox_updated_doc.py [입력 docx 경로(기본값 위 참고)]
```

실행 결과로 `backup=`, `updated=`, `removed_low_quality=`, `final_questions=` 요약을 출력한다.

## 관련 문서
- [enhance_civil_v1_doc.md](enhance_civil_v1_doc.md) — 기본 공통 패턴
- [enhance_social_insurance_v1_doc.md](enhance_social_insurance_v1_doc.md) — 함정분류/암기법 개념을 공유하는 버전
