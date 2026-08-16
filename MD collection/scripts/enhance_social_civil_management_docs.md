# enhance_social_civil_management_docs.py

`enhance_civil_v1_doc.py`/`enhance_management_v1_doc.py`/`enhance_social_insurance_v1_doc.py` **세 과목을 한 스크립트에서 선택적으로 재실행**할 수 있게 통합한 버전. `SUBJECT_CONFIG`에 과목별 설정(입력 문서, 관련 JSON)을 모아두고, 사회보험법은 `build_social_insurance_doc()`(해설 개선 건수 보고), 민법/경영학은 `build_choice_subject_doc()`(저품질 문항 제거 건수 보고)으로 나눠 처리한다.

파일: `scripts/enhance_social_civil_management_docs.py`

## CLI

```bash
python3 scripts/enhance_social_civil_management_docs.py [subjects...]
# subjects: social_insurance, civil, management (생략 시 셋 다 실행)
```

## 관련 문서
- [enhance_civil_v1_doc.md](enhance_civil_v1_doc.md), [enhance_management_v1_doc.md](enhance_management_v1_doc.md), [enhance_social_insurance_v1_doc.md](enhance_social_insurance_v1_doc.md) — 이 스크립트가 통합한 개별 버전들
