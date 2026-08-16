# analyze_document_with_web_services.py

`analyze_document_with_chatgpt_web.py`의 확장판. 단일 ChatGPT 웹 분석(`--analysis-mode basic`)뿐 아니라, **ChatGPT 웹 → Claude 웹 → Gemini 웹을 순서대로 거치는 "심화 분석"**(`--analysis-mode deep`)을 지원한다. 세 웹 서비스 각각의 자동화(Chrome 경로, 표시 여부, 재시도 등)를 모두 인자로 노출한다.

파일: `scripts/analyze_document_with_web_services.py` (약 1,311줄)

## 분석 모드

- `basic` (기본): ChatGPT 웹 한 번으로 분석.
- `deep`: ChatGPT 웹 결과를 다시 Claude 웹에 검토시키고, 그 결과를 다시 Gemini 웹에 검토시켜 세 서비스의 시각을 순차적으로 반영한 최종 분석을 만든다. `ClaudeWebUsageLimitError`로 Claude 웹 사용량 한도에 걸리면 그 단계를 건너뛴다.

## CLI

```bash
python3 scripts/analyze_document_with_web_services.py \
  --input-file <docx/pdf/epub/txt> \
  [--output-file <결과.md>] [--work-dir <중간 산출물 폴더>] \
  --analysis-mode {basic,deep} \
  --max-chars-per-chunk 6000 --request-timeout-sec 900 \
  --chatgpt-web-chrome-path <경로> --gemini-web-chrome-path <경로> \
  [--chatgpt-web-visible] [--gemini-web-visible] [--claude-web-visible] \
  ...
```

## 관련 문서
- [analyze_document_with_chatgpt_web.md](analyze_document_with_chatgpt_web.md) — ChatGPT 단일 분석만 하는 더 단순한 버전
- [apply_deep_analysis_results.md](apply_deep_analysis_results.md) — 이 스크립트의 분석 결과를 DOCX에 반영하는 다음 단계
