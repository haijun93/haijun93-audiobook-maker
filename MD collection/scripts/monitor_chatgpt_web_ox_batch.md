# monitor_chatgpt_web_ox_batch.py

4과목 OX 통합본(`사회보험법_OX_통합본_2026최종검수`, `노동법_OX_통합본_2026최종검수`, `민법_OX_통합본_2026최종검수`, `경영학_OX_통합본_2026최종검수`)을 ChatGPT 웹 자동화로 처리하는 배치 작업을 **감시(watchdog)** 하는 스크립트. 이름은 `monitor_chatgpt_web_ox_batch`지만, 실제로는 감시만이 아니라 각 과목의 `Job`(입력/출력/작업디렉터리/heartbeat 경로)을 직접 순회하며 실행까지 담당한다.

파일: `scripts/monitor_chatgpt_web_ox_batch.py`

## 감시 기능

- `heartbeat_file`을 주기적으로 읽어(`--poll-sec`, 기본 60초) 진행 상황을 확인.
- `--stalled-sec`(기본 1800초) 동안 heartbeat 갱신이 없으면 정체로 판단.
- `--watchdog-stall-sec`(1200초)/`--watchdog-semantic-stall-sec`(900초): 완전 무응답과 "의미상 진전 없음"(같은 단계에 오래 머무름)을 구분해서 감지.
- 정체 감지 시 `--batch-pid`로 지정된 프로세스를 `--kill-grace-sec`(15초) 유예 후 종료할 수 있다.
- `is_pid_alive()`로 프로세스 생존 여부를 직접 확인(`os.kill(pid, 0)`).

## CLI 주요 인자

```bash
python3 scripts/monitor_chatgpt_web_ox_batch.py \
  --root-dir <저장소 루트> \
  --batch-pid <감시할 프로세스 PID> \
  --poll-sec 60 --stalled-sec 1800 --kill-grace-sec 15 \
  --progress-log-sec 300 \
  --watchdog-stall-sec 1200 --watchdog-semantic-stall-sec 900 \
  --watchdog-poll-sec 15 --watchdog-log-interval-sec 300 \
  --max-chars 1800 --request-timeout-sec 600 --retry-sleep-sec 20 \
  --chatgpt-web-max-attempts 8
```

## 이 서재의 EPUB 번역 배치와의 관계

**EPUB 번역 배치(`webui/workflow_runner.py`)는 이 스크립트를 쓰지 않는다** — 그쪽은 자체적인 heartbeat/재시도 로직(책 단위 최대 3회 재시도, 지수 백오프)을 갖고 있다. 이 스크립트는 완전히 별개인 공무원 시험 OX 학습자료용 ChatGPT 웹 배치를 감시하기 위해 만들어졌다. "정체 감지 → 프로세스 종료 → 재시작"이라는 감시 패턴 자체는, 이번 세션에서 EPUB 배치가 실제로 겪은 브라우저 세션 행업 상황(수동 개입)과 개념적으로 유사하다.

## 관련 문서
- [enhance_labor_ox_updated_doc.md](enhance_labor_ox_updated_doc.md) 등 배치 6의 나머지 문서 — 이 스크립트가 감시하는 산출물을 만드는 스크립트들
