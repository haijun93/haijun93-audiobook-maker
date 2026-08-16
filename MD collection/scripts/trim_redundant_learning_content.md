# trim_redundant_learning_content.py

4과목 문서(`TARGETS`)의 해설 문단(`"해설: ... 핵심: ... [두문자: #...]"` 형식, `extract_explanation_parts`로 파싱)에서 **중복되거나 불필요하게 늘어진 학습 내용**을 줄이는 정리 스크립트. "핵심" 요약과 "두문자"(니모닉) 태그만 남기고 군더더기 설명을 압축하는 방식이다.

파일: `scripts/trim_redundant_learning_content.py`

## CLI

```bash
python3 scripts/trim_redundant_learning_content.py
```

## 관련 문서
- [group_shared_explanations.md](group_shared_explanations.md) — 문항 간 중복 해설을 찾는 비슷한 취지의 다른 스크립트
