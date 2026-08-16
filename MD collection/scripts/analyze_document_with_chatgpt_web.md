# analyze_document_with_chatgpt_web.py

DOCX/PDF/EPUB/TXT 어떤 문서든 받아, **ChatGPT 웹 자동화**로 내용을 분석해 마크다운/텍스트 리포트를 만드는 범용 문서 분석 도구. 특정 과목이나 책에 종속되지 않은 기반 유틸리티다.

파일: `scripts/analyze_document_with_chatgpt_web.py`

## 동작

문서를 `--max-chars-per-chunk`(기본 6000자) 단위 세그먼트로 나눠 ChatGPT 웹에 순서대로 분석을 요청하고, 응답을 모아 `--final-format`(`markdown`/`text`)으로 최종 리포트를 만든다. `translate_epub_with_chatgpt_web_to_study_epub.py`와 같은 `audiobook_maker.py` 웹 자동화 기반(Chrome 경로, 재시도, heartbeat)을 공유한다.

## CLI

```bash
python3 scripts/analyze_document_with_chatgpt_web.py \
  --input-file <docx/pdf/epub/txt> \
  [--output-file <결과.md>] [--work-dir <중간 산출물 폴더>] \
  --max-chars-per-chunk 6000 --request-timeout-sec 900 \
  --chatgpt-web-max-attempts <N> [--chatgpt-web-visible] \
  [--analysis-instructions "..."] [--analysis-instructions-file <경로>] \
  --final-format {markdown,text} \
  [--heartbeat-file <경로>] [--keep-workdir]
```

`--analysis-instructions-file`로 분석 지침(예: "이 문서의 논리적 허점을 찾아라")을 파일로 지정할 수 있다.

## 파이프라인에서의 역할

이 스크립트(또는 그 확장판 [analyze_document_with_web_services.py](analyze_document_with_web_services.md))로 만든 분석 결과 마크다운은, [apply_deep_analysis_results.py](apply_deep_analysis_results.md)가 DOCX 문서의 "문서심화분석 반영" 섹션으로 붙여넣는 데 쓰인다 — 즉 "이 스크립트로 분석 → `apply_deep_analysis_results.py`로 문서에 반영"이 한 쌍의 흐름이다.

## 관련 문서
- [analyze_document_with_web_services.md](analyze_document_with_web_services.md) — ChatGPT뿐 아니라 Claude/Gemini까지 넘나드는 심화 버전
- [apply_deep_analysis_results.md](apply_deep_analysis_results.md)
- [translate_epub_with_chatgpt_web_to_study_epub.md](translate_epub_with_chatgpt_web_to_study_epub.md) — 같은 웹 자동화 기반 재사용
