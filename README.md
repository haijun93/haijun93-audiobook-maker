# Korean Audiobook Maker

한국어 텍스트를 오디오북으로 만드는 프로젝트입니다.

현재 남아 있는 생성 방식은 하나뿐입니다.
- `chatgpt_web`: ChatGPT 웹 로그인 기반 read-aloud 자동화

## 설치

```bash
python3 -m pip install -r requirements.txt
```

권장 사항:
- 시스템 `ffmpeg`가 있으면 가장 좋습니다.
- 시스템 `ffmpeg`가 없으면 `imageio-ffmpeg` fallback을 사용합니다.
- `chatgpt_web`를 쓰려면 Chrome에 `chatgpt.com` 로그인 세션이 있어야 합니다.
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

## 장시간 작업 재개

```bash
MAX_CHARS=1800 \
./scripts/run_chatgpt_web_job.sh \
  "./book.txt" \
  "./audiobooks/book_chatgpt_web_cove.m4a"
```

기본적으로 watchdog가 켜져 있습니다.
- `WATCHDOG_STALL_SEC=120`: heartbeat나 산출물 갱신이 120초 없으면 현재 합성 프로세스를 강제 종료하고 즉시 재시작합니다.
- `WATCHDOG_POLL_SEC=15`: 정체 여부를 확인하는 주기입니다.
- `WATCHDOG_KILL_GRACE_SEC=10`: 정상 종료를 기다린 뒤 강제 종료로 넘어가기 전 유예 시간입니다.

`run_chatgpt_web_job.sh`는 Python을 unbuffered 모드로 실행하고, 작업 폴더 안에 heartbeat JSON 파일을 남겨 외부 감시가 실제 진행 상태를 추적할 수 있게 합니다.

## 산출물

작업 폴더에 다음 추적 파일을 남깁니다.
- 원문 세그먼트 텍스트
- 프롬프트
- 응답 본문
- ChatGPT 웹 메타데이터 JSON
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
