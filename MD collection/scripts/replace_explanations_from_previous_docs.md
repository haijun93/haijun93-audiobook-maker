# replace_explanations_from_previous_docs.py

4과목(`social`/`labor`/`civil`/그 외) 각각에 대해, **더 이전 버전의 참고 문서**(`이전/` 폴더의 옛 원고, `PREV_DIR`)에 있던 설명을 지금의 `[doc] ..._OX_integrated_2026_v1.docx` 해설에 다시 반영하는 스크립트. 과목마다 `stopwords`(제목/조사/일반 법률 용어 등, 유사도 비교 시 잡음으로 걸러낼 단어 목록)가 따로 정의되어 있다.

파일: `scripts/replace_explanations_from_previous_docs.py`

## 동작

각 과목의 `reference`(이전 버전 문서)와 현재 `docx`를 문항 단위로 대조해, `stopwords`를 제외한 핵심 단어 유사도로 같은 문항을 찾아 **이전 문서의 해설을 지금 문서에 옮겨 붙인다.** 문서 편집을 거듭하며 유실된 예전 설명을 되살릴 때 쓰는 성격의 스크립트다.

## CLI

```bash
python3 scripts/replace_explanations_from_previous_docs.py
```

인자 없이 `CONFIGS`에 등록된 과목들을 순서대로 처리한다.

## 관련 문서
- [group_shared_explanations.md](group_shared_explanations.md) — 반대로 "여러 문항이 같은 해설을 공유하는 경우"를 찾아 정리하는 스크립트
