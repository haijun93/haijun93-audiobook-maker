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
- `openai`: OpenAI TTS API
- `system`: macOS `say`
- `melo`: MeloTTS

기본 오디오 생성 방식은 `gemini`가 아니라, CLI에서 명시적으로 `--provider`를 주는 것을 권장합니다.

## 설치

기본 CLI:

```bash
python3 -m pip install -r requirements.txt
```

장문 오디오북 패키지까지 같이 쓰려면:

```bash
python3 -m pip install -r requirements_korean_audiobook.txt
```

권장:
- 시스템 `ffmpeg`가 있으면 가장 좋습니다.
- 시스템 `ffmpeg`가 없으면 `imageio-ffmpeg` fallback을 사용합니다.

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
  --provider gemini \
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
