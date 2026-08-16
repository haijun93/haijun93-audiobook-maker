# enhance_other_subject_x_explanations.py

`labor`/`civil`/`management` 세 과목의 `[doc] ..._OX_integrated_2026_v1.docx`를 대상으로, `enhance_*_v1_doc.py`가 적용한 것과는 별개로 **함정 표현(TRIGGER_PHRASES: "아니다", "할 수 없다", "무효이다", "반드시", "언제나" 등)이 포함된 지문의 해설을 추가로 다듬는** 후속 보정 스크립트. 각 과목의 `CONFIGS`(문서/PDF/원본 백업 경로)가 코드에 고정되어 있다.

파일: `scripts/enhance_other_subject_x_explanations.py`
대상 폴더: `~/Desktop/1차 시험/#STD/260416`

## CLI

```bash
python3 scripts/enhance_other_subject_x_explanations.py
```

인자 없이 실행하면 `CONFIGS`에 등록된 3과목을 순서대로 처리한다.

## 관련 문서
- [enhance_civil_v1_doc.md](enhance_civil_v1_doc.md), [enhance_management_v1_doc.md](enhance_management_v1_doc.md), [enhance_labor_ox_updated_doc.md](enhance_labor_ox_updated_doc.md) — 1차 보강
- [enhance_social_insurance_x_explanations.md](enhance_social_insurance_x_explanations.md) — 같은 개념을 사회보험법에 적용한 버전
