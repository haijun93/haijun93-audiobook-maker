# apply_deep_analysis_results.py

별도로 작성된 **"문서 심화분석" 마크다운 리포트**의 내용을 DOCX 문서 끝에 고정된 제목의 섹션(기본 `"문서심화분석 반영"`)으로 추가하거나 교체하고, 필요하면 PDF도 다시 만드는 범용 유틸리티. 특정 과목에 종속되지 않은 일반 도구다.

파일: `scripts/apply_deep_analysis_results.py`

## 동작

1. 대상 DOCX를 백업(`backup_file`).
2. 문서 안에 같은 제목(`--section-title`)의 섹션이 이미 있으면 통째로 제거(`remove_existing_section`/`delete_paragraph`).
3. `--analysis-file`(마크다운)의 내용을 그 제목으로 문서 끝에 새로 추가.
4. `--no-pdf`가 아니면 갱신된 DOCX를 PDF로 다시 내보낸다(`--output-pdf` 지정 가능, 기본은 같은 이름의 `.pdf`).

## CLI

```bash
python3 scripts/apply_deep_analysis_results.py \
  --input-docx <반영할 docx> \
  --analysis-file <심화분석 결과 마크다운> \
  [--output-pdf <경로>] [--no-pdf] \
  [--section-title "문서심화분석 반영"]
```

## 언제 쓰는가

과목별 `enhance_*.py`가 만드는 정형화된 해설 보강과 달리, **사람(또는 AI)이 별도로 작성한 자유 형식 분석 결과**를 문서에 반영하고 싶을 때 쓰는 범용 도구다. 특정 과목에 종속되지 않으므로 4개 과목 문서 어디에나 쓸 수 있다.
