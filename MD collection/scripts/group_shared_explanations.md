# group_shared_explanations.py

4과목 문서 전체에서, **인접한 여러 문항이 사실상 같은 해설을 공유하는 구간**(`find_runs`)을 찾아 정리하는 스크립트. 문항을 번호(`^\d+\.\s`)와 그 뒤 `"해설:"` 문단으로 파싱(`parse_blocks`)한 뒤, 정규화된 해설 텍스트가 연속으로 같은 구간을 찾아낸다.

파일: `scripts/group_shared_explanations.py`
대상: `~/Desktop/1차 시험/#STD/260416`의 4과목 `DOCX_FILES` 전부

## CLI

```bash
python3 scripts/group_shared_explanations.py
```

## 관련 문서
- [replace_explanations_from_previous_docs.md](replace_explanations_from_previous_docs.md)
- [trim_redundant_learning_content.md](trim_redundant_learning_content.md) — 중복/군더더기 콘텐츠를 줄이는 비슷한 취지의 다른 스크립트
