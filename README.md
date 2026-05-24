# Korean Audiobook Maker

한국어 `txt`/`epub`/`docx`/`pdf`를 오디오북으로 만드는 프로젝트입니다.

현재 지원하는 생성 방식은 다음 세 가지입니다.
- `chatgpt_web`: ChatGPT 웹 로그인 기반 read-aloud 자동화
- `gemini_web`: Gemini 웹 로그인 기반 `듣기` 자동화
- `gemini_api_tts`: Gemini Developer API 기반 TTS

오디오북 모드는 두 가지입니다.
- `plain`: 원문을 그대로 낭독
- `study`: 장마다 `핵심 요약 -> 암기 포인트 -> 반복 리마인드 -> 다음 장 연결` 흐름으로 재구성한 학습용 오디오북

## 설치

```bash
python3 -m pip install -r requirements.txt
```

권장 사항:
- 시스템 `ffmpeg`가 있으면 가장 좋습니다.
- 시스템 `ffmpeg`가 없으면 `imageio-ffmpeg` fallback을 사용합니다.
- `chatgpt_web`를 쓰려면 Chrome에 `chatgpt.com` 로그인 세션이 있어야 합니다.
- `gemini_web`를 쓰려면 Chrome에 `gemini.google.com` 로그인 세션이 있어야 합니다.
- `gemini_api_tts`를 쓰려면 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY` 환경변수가 필요합니다.
- `playwright install chromium` 초기 1회 설치가 필요할 수 있습니다.

## 기본 낭독 지침

모든 오디오북 생성 방식의 기본 낭독 지침은 공통입니다.
- 한국어 원어민 전문 성우가 읽는 오디오북 톤
- 외국어식 억양, 영어식 강세, 문장 끝 올림 억양 지양
- 문장 흐름 중심의 자연스러운 호흡과 리듬
- 따뜻하고 차분하며 오래 들어도 피로하지 않은 톤
- 감정선은 살리되 과장 연기는 하지 않는 방향

필요하면 ChatGPT 웹용 추가 낭독 지침으로 덮어쓸 수 있습니다.

## 빠른 시작

```bash
python3 audiobook_maker.py \
  --provider chatgpt_web \
  --input-file "./smoke_ko.txt" \
  --output-file "./audiobooks/smoke_chatgpt_web.m4a" \
  --voice "cove"
```

```bash
python3 audiobook_maker.py \
  --provider chatgpt_web \
  --audiobook-mode study \
  --input-file "./book.epub" \
  --output-file "./audiobooks/book_study_chatgpt_web.m4a" \
  --voice "cove"
```

```bash
python3 audiobook_maker.py \
  --provider gemini_web \
  --input-file "./smoke_ko.txt" \
  --output-file "./audiobooks/smoke_gemini_web.m4a" \
  --voice "account_default"
```

```bash
export GEMINI_API_KEY="your_api_key_here"

python3 audiobook_maker.py \
  --provider gemini_api_tts \
  --input-file "./smoke_ko.txt" \
  --output-file "./audiobooks/smoke_gemini_api_tts.m4a" \
  --voice "Sulafat"
```

`gemini_web` 참고:
- 현재 웹 자동화는 계정에 설정된 Gemini 기본 음성을 사용합니다.
- 따라서 `--voice`는 현재 `account_default`만 지원합니다.
- 실제 음성 변경은 Gemini 앱의 `Gemini's Voice` 설정에서 먼저 바꿔 둬야 합니다.

`gemini_api_tts` 참고:
- 기본 모델은 `gemini-2.5-flash-preview-tts` 입니다.
- `gemini-2.5-flash-tts`, `gemini-2.5-pro-tts`를 넣으면 각각 현재 공식 preview 모델 코드로 자동 정규화합니다.
- 기본 음성은 `Sulafat` 입니다.
- 기본 세그먼트 길이는 `2500`자입니다.
- `--list-voices --provider gemini_api_tts` 로 공식 지원 voice 목록을 볼 수 있습니다.
- 추가 낭독 지침은 `--gemini-api-tts-reading-instructions` 로 넣을 수 있습니다.

`study` 모드 참고:
- 입력이 `epub`이면 spine 순서대로 장을 추출합니다.
- 입력이 `docx`이면 Word 문단과 `heading 1` 스타일을 기준으로 큰 단원을 추출합니다.
- 입력이 `pdf`이면 텍스트 블록을 읽고, `SECTION` 시작 페이지를 기준으로 큰 단원을 추출합니다.
- 너무 짧은 인접 장은 학습 흐름이 끊기지 않도록 자동으로 묶어 처리합니다.
- `chatgpt_web`에서는 각 장을 ChatGPT에 보내 학습용 낭독문으로 재구성한 뒤 음성을 받습니다.
- 기본 장 입력 길이는 `3500`자이고, `--study-max-source-chars` 로 조절할 수 있습니다.
- 출력 기본 파일명은 `*_study_audiobook.m4a` 입니다.
- manifest에는 `audiobook_mode`, 장별 `next_title`, `part_index`가 함께 기록됩니다.

## 장시간 작업 재개

```bash
MAX_CHARS=1800 \
./scripts/run_chatgpt_web_job.sh \
  "./book.txt" \
  "./audiobooks/book_chatgpt_web_cove.m4a"
```

```bash
STUDY_MAX_SOURCE_CHARS=3500 \
./scripts/run_chatgpt_web_study_job.sh \
  "./book.epub" \
  "./audiobooks/book_study_chatgpt_web_cove.m4a"
```

```bash
MAX_CHARS=1600 \
./scripts/run_gemini_web_job.sh \
  "./book.txt" \
  "./audiobooks/book_gemini_web.m4a"
```

```bash
export GEMINI_API_KEY="your_api_key_here"

MAX_CHARS=2500 \
./scripts/run_gemini_api_tts_job.sh \
  "./book.txt" \
  "./audiobooks/book_gemini_api_tts.m4a"
```

기본적으로 watchdog가 켜져 있습니다.
- `WATCHDOG_STALL_SEC=1200`: heartbeat나 산출물 갱신이 1200초 없으면 현재 합성 프로세스를 강제 종료하고 즉시 재시작합니다. ChatGPT 웹 rate limit 대기보다 짧게 잡으면 정상 대기 중인 작업도 중복 재시작될 수 있습니다.
- `WATCHDOG_POLL_SEC=15`: 정체 여부를 확인하는 주기입니다.
- `WATCHDOG_KILL_GRACE_SEC=10`: 정상 종료를 기다린 뒤 강제 종료로 넘어가기 전 유예 시간입니다.

Wrapper 스크립트들은 Python을 unbuffered 모드로 실행하고, 작업 폴더 안에 heartbeat JSON 파일을 남겨 외부 감시가 실제 진행 상태를 추적할 수 있게 합니다.

`run_gemini_api_tts_job.sh` 참고:
- API 키는 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY` 환경변수로 전달합니다.
- 모델은 `GEMINI_API_TTS_MODEL`, voice는 `VOICE`, 최대 재시도 횟수는 `GEMINI_API_TTS_MAX_ATTEMPTS` 환경변수로 조정할 수 있습니다.
- 추가 낭독 지침 파일은 `GEMINI_API_TTS_READING_INSTRUCTIONS_FILE` 로 지정할 수 있습니다.

`run_chatgpt_web_study_job.sh` 참고:
- `txt`와 `epub`를 모두 받을 수 있지만, 장 단위 학습 흐름은 `epub`에서 가장 자연스럽습니다.
- 각 장마다 `핵심 요약`, `암기 포인트`, `한 번 더 기억할 것`, `다음 장 연결`을 포함한 학습용 응답을 ChatGPT 웹에서 생성합니다.
- 음성은 기존과 동일하게 ChatGPT 웹 계정의 로그인 세션과 선택 voice를 사용합니다.
- 긴 작업에서 rate limit이 걸리면 `CHATGPT_WEB_MAX_ATTEMPTS` 환경변수로 재시도 횟수를 더 늘릴 수 있습니다.

## DOCX를 PDF/EPUB로 내보내기

macOS에서 `Pages.app`가 설치되어 있다면 아래 스크립트로 `docx -> pdf + epub`를 한 번에 만들 수 있습니다.

```bash
python3 ./scripts/export_docx_to_pdf_epub.py "/path/to/book.docx"
```

이 스크립트는 다음 순서로 동작합니다.
- Pages로 DOCX를 PDF와 EPUB로 내보냅니다.
- 생성된 PDF의 첫 페이지를 렌더링합니다.
- 그 이미지를 EPUB cover metadata에 넣어, EPUB 표지가 항상 첫 페이지 내용이 되도록 고정합니다.

## 웹 서비스로 문서 분석하기

문서 분석은 두 가지 모드로 지원합니다.

### 1. 기본 문서 분석

기본 분석은 `ChatGPT 웹 서비스`만 사용합니다.

```bash
python3 ./scripts/analyze_document_with_web_services.py \
  --analysis-mode basic \
  --input-file "./book.docx" \
  --output-file "./analysis/book.analysis.md"
```

또는 wrapper 스크립트:

```bash
ANALYSIS_MODE=basic \
./scripts/run_multi_web_document_analysis.sh \
  "./book.docx" \
  "./analysis/book.analysis.md"
```

### 2. 문서 심화 분석

심화 분석은 `ChatGPT 웹 → 클라우드(Claude) 웹 → Gemini 웹` 순서로 같은 문서를 단계적으로 분석하고 검증합니다.
만약 분석 도중 Claude 웹이 사용량 한도로 중단되면, 이후 단계는 자동으로 `ChatGPT 웹 + Gemini 웹` 교차 검증 방식으로 이어집니다.

```bash
python3 ./scripts/analyze_document_with_web_services.py \
  --analysis-mode deep \
  --input-file "./book.docx" \
  --output-file "./analysis/book.deep.md" \
  --apply-results-to-docx-pdf
```

또는 wrapper 스크립트:

```bash
ANALYSIS_MODE=deep \
./scripts/run_multi_web_document_analysis.sh \
  "./book.docx" \
  "./analysis/book.deep.md"
```

`deep + docx` 조합에서는 wrapper 스크립트가 기본적으로 `심화분석 완료 → deep.md 저장 → 원본 docx 반영 → pdf 재생성` 루틴까지 자동 실행합니다.
원하지 않으면 `APPLY_RESULTS_AFTER_ANALYSIS=0`으로 끌 수 있습니다.

문서 분석 스크립트 특징:
- `docx` / `pdf` / `epub` / `txt` 입력 지원
- 문서를 큰 조각으로 나눈 뒤 웹 서비스에 순차 전달
- `basic`: ChatGPT 웹 분석 후 통합
- `deep`: ChatGPT 초안 → 클라우드(Claude) 검토 → Gemini 검증 → 최종 통합본까지 순차 수행
- Claude 웹 사용량 한도 발생 시 자동으로 Claude 단계를 건너뛰고 `ChatGPT + Gemini`로 계속 진행
- `deep + docx`: 분석이 끝나면 `문서심화분석 반영` 섹션을 자동 교체하고 PDF도 다시 생성
- 작업 폴더에 프롬프트, 응답, heartbeat, manifest를 함께 저장
- Chrome의 `chatgpt.com`, `claude.ai`, `gemini.google.com` 로그인 세션이 필요

## 산출물

작업 폴더에 다음 추적 파일을 남깁니다.
- 원문 세그먼트 텍스트
- 프롬프트
- 응답 본문
- ChatGPT 웹 메타데이터 JSON
- Gemini 웹 메타데이터 JSON
- Gemini API TTS 메타데이터 JSON
- 분할 오디오 세그먼트
- watchdog heartbeat JSON

## 테스트

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

`pytest`가 설치돼 있다면 아래 명령도 동작합니다.

```bash
pytest -q
```
