# build_35day_first_exam_master_guide.py

4과목(민법/노동법/사회보험법/경영학) OX 학습자료와 별개로, **시험일까지 35일 학습 계획표**(`[doc] 35day_first_exam_master_guide_2026.docx`)를 처음부터 새로 만드는 스크립트. `python-docx`로 표(`WD_TABLE_ALIGNMENT`)와 스타일을 직접 구성한다.

파일: `scripts/build_35day_first_exam_master_guide.py`
출력: `~/Desktop/1차 시험/#STD/260416/[doc] 35day_first_exam_master_guide_2026.docx` (+ 같은 이름의 PDF)

## CLI

```bash
python3 scripts/build_35day_first_exam_master_guide.py
```

## 관련 문서
- [prepend_memory_study_check_sheet.md](prepend_memory_study_check_sheet.md) — 이 마스터 가이드를 각 과목 문서 앞에 요약해 붙이는 스크립트
