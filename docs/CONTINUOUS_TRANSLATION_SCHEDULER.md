# 3계정 연속 번역 스케줄러

`webui.continuous_scheduler`는 Gemini 2계정과 ChatGPT 1계정을 하나의 영속 큐로
운영한다. 각 계정에는 브라우저 프로필을 하나만 배정하고, 실행 가능한 작업이 있는 동안
완료 직후 다음 작업을 배정한다.

## 운영 원칙

- 계정별 동시 실행은 1개이며 프로필 lock과 work-dir lock으로 중복 실행을 막는다.
- 작업은 특정 계정에 고정하지 않는다. `providers`가 허용하는 다른 계정이 남은 작업을 가져갈 수 있다.
- `preferred_accounts`는 시작 시 기존 캐시와 계정의 대응을 유지하기 위한 우선순위일 뿐이다.
- 성공 캐시와 work-dir은 실패·재시작 후에도 유지한다.
- 프로세스 종료 원인을 진단 파일에서 읽어 작업 재시도와 계정 cooldown을 분리한다.
- heartbeat가 30분 멎으면 프로세스 그룹을 정리하고 한 번 재개한다. 반복 정지는 회로를 연다.
- Playwright/영구 Chrome 시작 단계는 180초로 별도 감시한다. 시작이 멎으면 해당 프로필의
  Chrome만 정리하고 체크포인트에서 재시작한다.
- 30분마다 이전 감사 이후의 진행량·오류·중단만 증분 분석하고 결과와 대응을 영구 기록한다.
- 오류가 있어도 체크포인트가 정상 증가하면 관찰과 요청 간격 보정만 수행한다. 오류가 진행량보다
  빠르게 누적되거나 체크포인트가 멈춘 경우에만 해당 계정을 격리하고 안전 재시작한다.
- 후처리와 서재 배포는 번역 프로세스 종료 뒤 수행하며 최종 파일은 원자적으로 교체한다.
- 계정이 idle이 되는 정상 사유는 실행 가능한 큐가 없거나, 해당 계정의 제한·세션 문제로
  안전하게 요청할 수 없는 경우뿐이다. 이 사유는 GUI 계정 행에 표시된다.
- 재기동 뒤 8초 동안은 새 작업을 시작하지 않고 기존 프로세스 인계만 확인한다.

## 현재 구성

운영 설정과 상태는 Git 비관리 경로인 `.work/continuous_scheduler/`에 저장된다.

- `config.json`: 계정, 프로필, 작업 명령, 우선순위, 배포 경로
- `state.json`: 시도 횟수, 배정, cooldown, 체크포인트 상태
- `status.json`: GUI와 상태 명령이 읽는 최신 스냅샷
- `events.jsonl`: 시작, 재시도, 완료, 회로 차단 이벤트
- `operations_audits.jsonl`: 30분 증분 운영 감사 전체 이력
- `latest_operations_audit.json`: GUI가 표시하는 최신 감사와 자동 개선 결과
- `logs/`: 계정별 작업 로그와 후처리 로그

현재 Pam Godwin 원서 기반 일반 번역 9권 큐는 다음 명령으로 재생성한다.

```bash
.venv311/bin/python -m scripts.configure_pam_godwin_scheduler \
  --scratch-root "$HOME/Desktop/소설2/_translation_stage"
```

Pam 작업은 `[e]` 원서를 일반 번역기로 6,000자씩 처리하고 한 대화를 최대 10청크까지 재사용한다.
같은 번역 캐시에서 `[k-e]`, `[k]`,
`[study]`, `[e-s]`를 만든 뒤 네 파일을 원자 배포한다. 작업 ID는 `pam-general-*`이고 Gemini와
ChatGPT 양쪽에서 실행 가능하다. 먼저 끝난 호환 계정이 다음 대기 작업을 가져간다.

웹 번역 Chrome은 항상 `headless=False`의 일반 표시 창으로 실행한다. 과거 사용자 요청으로
적용했던 화면 밖 배치, 창 크기 강제, 최소화, 포커스 조작은 사용하지 않는다. Playwright 기본
인자 중 백그라운드 네트워크·타이머·가림 창·렌더러 제한도 선택적으로 제외하고, 고정 viewport도
지정하지 않아 Chrome과 운영체제의 기본 창 동작을 따른다. `--web-visible`은 오래된 실행 명령과의
호환성만 위해 남아 있으며, 옵션 유무와 관계없이 창을 숨기지 않는다.

## 실행과 점검

macOS 로그인과 재부팅 뒤에도 자동으로 시작되는 LaunchAgent:

```text
com.haijun.audiobook.continuous-translation
```

설정 검증, 상태 확인, LaunchAgent 재설치:

```bash
.venv311/bin/python -m scripts.run_continuous_translation_scheduler validate
.venv311/bin/python -m scripts.run_continuous_translation_scheduler status
.venv311/bin/python -m scripts.run_continuous_translation_scheduler install-launch-agent
```

GUI의 실시간 작업 영역은 세 계정 상태와 실제 번역 프로세스를 함께 표시한다.
최신 운영 감사의 발견 건수, 신규 오류, 자동 개선 수, 다음 점검 시각과 공급자별 청크/시간 및
오류율도 같은 영역에 표시한다. scheduler inventory에서 제거된 종료 작업은 과거 상태 카드로
남기지 않는다.

중복 실행 방지는 한 신호에 의존하지 않는다. VK batch wrapper, 번역 worker의 `--work-dir`,
provider profile lock, 상태 파일의 실제 생존 PID를 차례로 확인한다. 일시적으로 process table이
비어도 저장 PID가 살아 있으면 계정을 점유 상태로 유지하고, 이전 PID가 남긴 heartbeat는 새 작업의
정지 근거로 사용하지 않는다.

```text
http://127.0.0.1:7860
http://127.0.0.1:7870
```

## 장애 대응

| 상태 | 의미 | 자동 대응 |
|---|---|---|
| `running` | 스케줄러가 계정에 작업 배정 | 완료 즉시 다음 작업 배정 |
| `external` | 기존 프로세스와 프로필 lock 발견 | 중복 실행 없이 관찰·인계 |
| `retry_wait` | 작업 자체 재시도 대기 | 지수 backoff 뒤 다른 호환 계정도 사용 가능 |
| `cooldown` | 해당 계정 요청 제한 | 다른 계정은 계속 실행, 제한 해제 뒤 복귀 |
| `attention` | 로그인·계정 상태 확인 필요 | 계정만 격리하고 다른 계정은 계속 실행 |
| `blocked` | 입력·의존성·반복 정지 등 회로 차단 | 증거와 로그 보존, 수동 원인 제거 필요 |
| `idle_no_work` | 호환되는 실행 가능 작업 없음 | 설정 파일에 작업이 추가되면 자동 감지 |

## 30분 운영 감사

기본 주기는 `operations_audit_interval_seconds=1800`이다. 각 작업의 직전 감사 완료량을
기준점으로 저장하고, 현재 실행 시작 또는 직전 감사보다 오래된 오류를 신규 오류에서 제외한 뒤
다음 순서로 판정한다.

1. heartbeat가 제한을 넘겼는지 확인한다.
2. 완료 체크포인트 증가량과 새 오류 이벤트를 집계한다.
3. 계정·세션·요청 제한, 공급자 일시 오류, 응답 ID 형식 오류, 진행 정체를 분리한다.
4. 오류 중에도 진행 중이면 작업을 유지하고 요청 간격·재시도 설정만 보수화한다.
5. 공급자 오류가 진행량의 2배 이상이거나 30분간 완료가 없으면 체크포인트를 보존한 채
   해당 프로필만 쿨다운하고 재시작한다.

자동 조정은 작업 상태의 `runtime_overrides`에 저장되어 다음 실행 명령에 반영된다. 웹 작업은
기본 웹 재시도 3회, 요청 간격 8초로 시작하며 반복 오류 시 간격을 최대 30초까지 늘린다.
응답 ID 오류가 반복되면 기존 청크 경계는 그대로 보존하고, 누락 ID만 두 그룹으로 나눠 남은
시도에 배정하며 형식 재시도를 2회로 제한한다. 청크 경계를 실행 중 바꾸면 `chunk_XXXX.json`
체크포인트의 의미가 달라지므로 운영 감사는 `max_chars_per_chunk`를 자동 변경하지 않는다. 정상
계정과 다른 작업은 영향을 받지 않는다. 이미 `retry_wait`에 들어간 작업은 신규 긴급 중단이 아닌
예약된 복구 대기로 분류한다.

ChatGPT 계정은 일반 번역 scope에서 기본 요청 간격 300초를 사용한다. 새 제한이 확인되면
450초부터 반복 사고 수에 따라 최대 900초까지 늘리며, 정상 응답 3회 뒤 기본 간격으로 복귀한다.
같은 제한 팝업 재관찰은 하나의 사고로 합치고 실제 `blocked_until`이 지난 기록은 일반 브라우저
오류를 rate limit으로 바꾸지 않는다. ChatGPT 작업은 첫 웹 요청을 관계도 조사에 소비하지 않고
로컬 관계 가이드를 만들어 첫 요청부터 번역 체크포인트를 생성한다.
입력창은 `#prompt-textarea`, ProseMirror, `role=textbox` UI를 모두 지원하고 visible send 버튼을
우선 사용한다. 2026-08-16 실측에서 자동화 프로필의 계정 등급이 `Free`로 표시됐으므로, 설정상
유료 계정을 의도했다면 해당 영구 프로필의 로그인·구독을 별도로 확인해야 한다.

account2의 현재 최우선 큐는 `new books from vk`의 미완료 3권이다. 각 책은 개별 작업이므로
진행률과 heartbeat가 GUI에 표시되고, `Mad Mabel` → `The Five-Star Weekend` → `How to Stop Time`
순서로 처리한다. 완료가 확인된 `The Deal`, `Better Than the Movies`는 다시 번역하지 않는다.

스케줄러 설정은 매 poll마다 다시 읽으므로 작업 추가를 위해 프로세스를 재시작할 필요가 없다.
계정 비밀번호나 쿠키는 설정 파일에 저장하지 않고 기존 영구 Chrome 프로필만 사용한다.
