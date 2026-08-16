# enhance_social_insurance_v1_doc.py

`enhance_civil_v1_doc.py`와 같은 계열이되, **사회보험법 OX 학습자료**에 특화된 추가 기능이 있는 버전. 공통 패턴(파싱 → 초점 추출 → 해설 재작성 → Kiwi 띄어쓰기 보정 → 재조립)은 [enhance_civil_v1_doc.md](enhance_civil_v1_doc.md) 참고.

파일: `scripts/enhance_social_insurance_v1_doc.py`
기본 입력: `~/Desktop/1차 시험/#STD/260416/social_insurance_law_OX_integrated_2026_v1.docx`
보조 소스: `.work/social_insurance_ox_2026/social_insurance_ox_integrated_2026_final.json` (`SOURCE_JSON`)

## 이 버전에만 있는 기능

- **함정 유형 분류** (`classify_trap` / `trap_comment`): OX 문항이 흔히 틀리는 함정 유형(숫자 바꿔치기, 주체 바꿔치기 등)에 해당하는지 분류해 그에 맞는 코멘트를 붙인다.
- **위원회 노트 탐지** (`find_committee_note`): 출제위원 노트/판례 코멘트가 있으면 찾아서 반영(`is_generic_note`로 의미 없는 일반 문구는 걸러냄).
- **암기법/가이드 선택** (`select_guide` / `select_mnemonic`): 문항 성격에 맞는 암기 가이드·니모닉을 골라 붙인다.
- 별도 대단원 순서(`SECTION_ORDER`) 없이, JSON 소스와 문항 자체의 분류 로직으로 순서를 정한다.

## CLI

```bash
python3 scripts/enhance_social_insurance_v1_doc.py [입력 docx 경로(기본값 위 참고)]
```

## 관련 문서
- [enhance_civil_v1_doc.md](enhance_civil_v1_doc.md) — 공통 패턴 상세 설명
- [enhance_labor_ox_updated_doc.md](enhance_labor_ox_updated_doc.md) — 같은 함정 분류/암기법 아이디어를 더 발전시킨 버전
