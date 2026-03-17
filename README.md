# Korean Audiobook Maker

한국어 텍스트를 오디오 파일로 만드는 전용 프로젝트입니다.

원본 번역 프로젝트는 별도 저장소로 분리되어 있습니다.
- `https://github.com/haijun93/haijun93-translating`

현재 포함된 주요 경로:
- `audiobook_maker.py`: 단일 CLI 진입점
- `korean_audiobook/`: 장문 오디오북용 실험 패키지
- `tests/`: 핵심 오디오 처리 테스트

## 지원 방식
- `edge`: Microsoft Edge TTS
- `gemini`: Google AI Studio TTS
- `chatgpt`: ChatGPT Voice 수동 세그먼트 워크플로우
- `chatgpt_web`: ChatGPT 웹 로그인 기반 read-aloud 자동화
- `openai`: OpenAI TTS API
- `system`: macOS `say`
- `melo`: MeloTTS

기본 오디오 생성 방식은 `gemini`입니다.
다른 엔진을 쓰고 싶을 때만 `--provider`를 명시하면 됩니다.

## 설치

기본 CLI:

```bash
python3 -m pip install -r requirements.txt
```

기본 provider는 `gemini`이므로, `--provider`를 생략하면 Google AI Studio TTS 경로를 사용합니다.

장문 오디오북 패키지까지 같이 쓰려면:

```bash
python3 -m pip install -r requirements_korean_audiobook.txt
```

권장:
- 시스템 `ffmpeg`가 있으면 가장 좋습니다.
- 시스템 `ffmpeg`가 없으면 `imageio-ffmpeg` fallback을 사용합니다.
- `chatgpt_web`를 쓰려면 Chrome에 `chatgpt.com` 로그인 세션이 있어야 합니다.
- `chatgpt_web`는 `playwright install chromium` 초기 1회 설치가 필요할 수 있습니다.

## 빠른 시작

Edge TTS:

```bash
python3 audiobook_maker.py \
  --provider edge \
  --input-file "./smoke_ko.txt" \
  --output-file "./audiobooks/smoke_edge.m4a" \
  --voice "ko-KR-SunHiNeural"
```

Google AI Studio TTS:

```bash
export GEMINI_API_KEY="AIza..."

python3 audiobook_maker.py \
  --input-file "./smoke_ko.txt" \
  --output-file "./audiobooks/smoke_gemini.m4a" \
  --voice "Sulafat" \
  --gemini-model "gemini-2.5-flash-preview-tts" \
  --gemini-language-code "ko-KR"
```

ChatGPT Voice 수동 워크플로우:

```bash
python3 audiobook_maker.py \
  --provider chatgpt \
  --input-file "./smoke_ko.txt" \
  --output-file "./audiobooks/smoke_chatgpt.m4a" \
  --voice "Spruce" \
  --chatgpt-mode "advanced_voice"
```

`chatgpt` provider는 두 단계입니다.
1. 첫 실행은 `work_dir/chatgpt/segments`, `prompts`, `downloads`를 생성합니다.
2. ChatGPT Voice에서 세그먼트 오디오를 저장한 뒤 같은 명령을 다시 실행하면 최종 파일을 자동 병합합니다.

ChatGPT 웹 read-aloud 자동화:

```bash
python3 audiobook_maker.py \
  --provider chatgpt_web \
  --input-file "./smoke_ko.txt" \
  --output-file "./audiobooks/smoke_chatgpt_web.m4a" \
  --voice "cove"
```

이 방식은 사용자가 좋아했던 `you_bookstore_intro_chatgpt_voice.*` 계열 산출물과 가장 가까운 흐름을 재구성한 것입니다.
1. ChatGPT 웹에 본문 그대로 복사하도록 프롬프트를 보냅니다.
2. 응답 텍스트가 원문과 정확히 일치하는지 검증합니다.
3. 같은 메시지의 read-aloud 오디오를 `backend-api/synthesize`로 받아 최종 오디오로 병합합니다.
4. 작업 폴더에는 `001_prompt.txt`, `001_response.txt`, `001_chatgpt_web.json` 같은 추적 파일이 남습니다.

기본값은 Chrome 창을 화면 밖으로 띄워 invisible 상태처럼 동작합니다. 디버깅이 필요하면 `--chatgpt-web-visible`을 추가하면 됩니다.

긴 작업을 재개 가능하게 돌리고, 성공 후 종료까지 걸고 싶으면:

```bash
SHUTDOWN_ON_SUCCESS=1 MAX_CHARS=1800 \
  ./scripts/run_chatgpt_web_job.sh \
  "./You_-_Caroline_Kepnes_ko_web.txt" \
  "./audiobooks/You_-_Caroline_Kepnes_ko_web_chatgpt_web_cove.m4a"
```

## 실험 패키지

`korean_audiobook/`는 장별 MP3/M4B 생성용 실험 패키지입니다.

```bash
python3 -m korean_audiobook \
  --input-file "./smoke_ko.txt" \
  --output-dir "./korean_audiobook_runs/smoke_edge" \
  --title "스모크 테스트" \
  --author "Local" \
  --engine edge \
  --voice "ko-KR-SunHiNeural"
```

## 테스트

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
