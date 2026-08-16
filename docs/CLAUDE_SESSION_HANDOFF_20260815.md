# Audiobook Maker 세션 인수인계

기준 시각: 2026-08-16 00:03 KST

## 최종 상태

- 영문 EPUB 원서 기반 일반 번역 방식만 운영한다.
- LaunchAgent `com.haijun.audiobook.continuous-translation`이 12개 작업 큐를 관리한다.
- 세 계정은 계정별 동시 실행 1개로 병렬 가동 중이다.
- 작업 GUI `http://127.0.0.1:7870/`에는 현재 실행 중인 3개 작업만 표시된다.
- 7870 GUI는 현재 로그인 세션의 launchd job
  `com.haijun.audiobook.runtime-preview-7870`으로 실행 중이다.
- Git 작업 트리에는 이번 세션 전부터 이어진 많은 변경이 있다. 관련 없는 변경을 되돌리지 않는다.

00:03 KST 실측 스냅샷:

| 계정 | 공급자 | 작업 | 진행 | 상태 |
|---|---|---|---:|---|
| main | Gemini | Dead of Eve | 0/146 | 청크 1 브라우저 재시도 중 |
| account2 | Gemini | Mad Mabel | 36/94 캐시 보존 | 30분 감사 후 재시작 완료 |
| chatgpt | ChatGPT web | Dark Notes | 0/133 | 영구 Chrome 시작 중, 180초 감시 적용 |

ChatGPT는 사용자 수동 확인에서 현재 제한이 없었고 자동화 프로필에도 활성 rate-limit 상태가 없다.
로컬 인물관계 가이드는 `generation_policy=chatgpt-request-efficiency`로 정상 생성됐다. 다만 같은
자동화 프로필을 직접 진단했을 때 사이드바 계정 등급이 **Free**로 표시됐다. 원래 의도한 유료
ChatGPT 계정과 실제 로그인 계정 등급이 일치하지 않으므로 과거에 Gemini보다 먼저 대화 제한이 발생한 가장
강한 원인이다. 유료 계정을 의도했다면 이 영구 프로필에서 계정을 다시 확인해야 한다.

## 효율 비교와 원인

- 초기 동일 일반 번역 구간에서 Gemini account2는 약 45.7청크/시간, 중앙 청크 간격 약 53초였다.
- 재시작과 최근 오류를 포함한 최신 30분 감사의 Gemini 합산 작업자 처리량은 약 21청크/시간이다.
- 7870 실시간 추정치는 Mad Mabel 약 38청크/시간, Cage 약 10청크/시간이었다.
- ChatGPT는 이전 제한 때문에 아직 완료 청크가 없어 실제 처리량 비교값이 없다. 기본 자동 요청 간격은
  300초이므로 제한이 없더라도 Gemini보다 느린 보조 처리 계정으로 보는 것이 안전하다.

확인된 병목:

1. ChatGPT의 서로 다른 과거 작업 제한 이력이 한 파일에 누적돼 일반 번역 간격을 최대 15분으로
   과도하게 올렸다.
2. 이미 만료된 제한 기록만 있어도 일반 클릭/응답 오류를 rate limit으로 오진하고 20분 cooldown을
   다시 열 수 있었다.
3. 같은 제한 팝업을 재관찰할 때 별도 사고로 중복 집계하고 cooldown을 다시 20분 연장했다.
4. ChatGPT 첫 웹 요청이 번역이 아닌 인물관계 조사여서 실패 시 0청크 상태로 끝났다.
5. 30분 감사가 스케줄러 재시작 전 오류를 새 오류로 읽어 정상 재개한 계정을 다시 격리했다.
6. Gemini는 `prompt_interaction_failed`, 응답 ID 누락, 빈 응답/timeout이 발생하지만 자동 재시도 후
   체크포인트는 계속 증가한다. Pam 원문의 긴 대화와 민감한 장면에서 형식 오류가 상대적으로 많다.
7. 7870 서버 메모리의 `_known` 목록이 설정에서 제거된 과거 작업을 1시간 표시했다.
8. 스케줄러 재시작 시 VK 배치 wrapper가 자식 재시도 간격에 있으면 account2를 빈 계정으로 오인했다.
9. 번역 프로세스가 EPUB를 추출한 뒤 Chrome profile lock을 만들기 전에는 실행 중임을 판별하지 못했다.
10. launchd 인계 순간 `ps` 결과가 비면 상태 파일에 살아 있는 PID가 있어도 새 작업을 시작했다.
11. ChatGPT의 `sync_playwright()` 또는 영구 Chrome 시작이 반환되지 않아 요청 전 무한 대기가 가능했다.
12. 이전 PID가 남긴 오래된 heartbeat 때문에 새 wrapper를 시작 직후 정지시키는 사례가 있었다.

## 구현한 개선

ChatGPT 요청 보호와 복구:

- 페이싱 사고를 `general_translation` scope로 분리했다. 오래된 다른 workflow 사고는 일반 번역
  간격을 올리지 않는다.
- 실제 `blocked_until`이 남은 상태만 active rate limit으로 판정한다.
- 같은 제한 에피소드의 팝업 재관찰은 사고 1건으로 유지하고, 필요 시 180초만 연장한다.
- 정상 응답 3회 후 페널티 간격 450초를 기본 300초로 자동 완화한다.
- 요청 슬롯을 먼저 확보한 뒤 prompt box를 다시 찾아 입력하므로 긴 대기 중 stale element가 되는
  가능성을 줄였다.
- ChatGPT는 웹 인물관계 조사 요청을 생략하고 로컬 가이드를 캐시한다. 첫 허용 요청이 바로 번역
  청크가 되어 체크포인트를 남긴다.
- 현재 UI의 `#prompt-textarea`, ProseMirror, `role=textbox`를 모두 지원하고 visible send 버튼을
  우선 사용한다.
- Playwright와 영구 Chrome 시작 단계를 분리해 heartbeat로 기록한다. 영구 Chrome 시작은 120초
  프로필별 watchdog, 스케줄러는 두 시작 단계에 180초 상위 watchdog을 적용한다.

30분 자가진단과 GUI:

- 오류 집계 시작점을 `period_start`, 현재 실행 `started_at`, 직전 감사 `audited_at` 중 가장 늦은
  시각으로 제한했다. 과거 오류로 새 실행을 중단하지 않는다.
- 공급자별 완료 청크, 청크/시간, 초/청크, 오류율, 계정 제한 오류, 공급자 오류를 계산한다.
- 7870 운영 감사 영역에 Gemini/ChatGPT 처리량과 오류율을 표시한다.
- 단일 진행 샘플을 임의의 1청크 진전으로 계산하지 않는다.
- 현재 scheduler inventory에서 제거된 관리 작업은 프로세스 종료 즉시 GUI 메모리에서도 제거한다.
- 30분 감사는 현재 실행 시작 전 오류를 다시 사용하지 않으며, 이전 PID heartbeat도 무시한다.

3계정 병렬 정책:

- Gemini main: Pam 일반 번역 우선.
- Gemini account2: VK 3권을 우선 처리한 뒤 공유 Pam 큐를 가져간다.
- ChatGPT: ChatGPT 선호 Pam 작업을 300초 기본 간격으로 처리한다.
- 각 계정은 preferred 작업을 먼저 선택하지만, 자기 큐가 끝나면 호환되는 다른 대기 작업을 가져가
  idle 시간을 줄인다.
- ChatGPT 오류는 ChatGPT 계정만 격리하며 두 Gemini 작업은 계속한다.
- Gemini가 더 빠르므로 대량 처리의 주력은 두 Gemini 계정이고, ChatGPT는 쉬지 않는 보조 병렬
  작업자로 사용한다.
- VK wrapper, 번역 worker의 `work-dir`, profile lock, 저장된 live PID를 독립 점유 신호로 사용한다.
- 스케줄러 시작 뒤 8초 동안 기존 작업 인계만 확인한다. 순간적인 빈 process scan으로 새 작업을
  시작하지 않으며, 종료된 `running` 상태만 자동으로 `pending`에 돌려놓는다.

## 주요 파일

- `audiobook_maker.py`: ChatGPT scope 페이싱, 활성 제한 판정, 에피소드 중복 제거, 성공 완화
- `scripts/translate_epub_with_chatgpt_web_to_study_epub.py`: ChatGPT 로컬 관계 가이드, 성공 기록
- `scripts/configure_pam_godwin_scheduler.py`: 12개 일반 번역 큐와 ChatGPT 페이싱 환경 변수
- `webui/operations_audit.py`: 실행 구간 기반 오류 감사와 공급자 효율 집계
- `webui/continuous_scheduler.py`: 3중 점유 판단, 8초 인계 워밍업, 시작 watchdog, 30분 감사
- `webui/runtime_monitor.py`: 종료·제거된 관리 작업 GUI 정리
- `webui/static/app.js`: 공급자별 처리량/오류율 표시
- `.work/continuous_scheduler/config.json`: 현재 운영 설정
- `.work/continuous_scheduler/state.json`, `status.json`: 현재 런타임 상태

Pam staging 산출물은 더 이상 이전 Claude 세션의 `/private/tmp/...`를 새 작업에 사용하지 않는다.
현재 설정은 영구 경로 `~/Desktop/소설2/_translation_stage/pam_general_translation`을 사용한다.
현재 모든 새 Pam 명령은 이 영구 staging 경로를 사용한다.

## 검증

최종 검증 결과:

```text
pytest: 430 passed, 2 subtests passed
ruff: All checks passed
git diff --check: 통과
scheduler config validate: 통과
```

추가된 핵심 회귀 테스트:

- 다른 workflow scope의 ChatGPT 사고가 일반 번역 페이싱에 섞이지 않음
- 같은 제한 모달 재관찰이 사고 1건으로 유지됨
- 만료된 제한은 active 제한으로 오진하지 않음
- 정상 응답 3회 뒤 기본 요청 간격으로 복구됨
- ChatGPT 관계 가이드가 웹 요청을 소비하지 않음
- 현재 실행 시작 전 오류가 30분 감사의 신규 오류로 집계되지 않음
- scheduler에서 제거된 종료 작업이 GUI에 남지 않음
- 공급자별 처리량과 account restriction 병목 집계
- batch wrapper의 자식 재시도 공백에서도 account2 점유 유지
- profile lock 생성 전 worker와 빈 process scan에서도 live PID로 중복 실행 차단
- 8초 startup adoption grace 뒤에만 새 작업 시작
- 이전 PID heartbeat 무시 및 Playwright/Chrome 시작 180초 감시
- Chrome 시작 실패 시 해당 프로필 Chrome만 정리

## 확인 명령

```bash
.venv311/bin/python -m scripts.run_continuous_translation_scheduler validate
.venv311/bin/python -m scripts.run_continuous_translation_scheduler status
curl -sS http://127.0.0.1:7870/api/runtime | jq
```

ChatGPT 첫 청크와 페이싱 확인:

```bash
jq . "$HOME/Desktop/소설2/_chatgpt_translate_work/pam_general__Dark_Notes_Pam_Godwin_3.92/heartbeat.json"
jq . "$HOME/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles/chatgpt/.chatgpt_request_pacing.json"
```

## 다음 점검 우선순위

1. Dark Notes의 `chunk_0001.json` 생성 여부를 확인한다. 00:02:43부터
   `translation_browser_launch` 상태이므로 180초 이내 다음 단계로 가거나 자동 재시작돼야 한다.
2. 자동화 ChatGPT 프로필의 사이드바가 `Free`로 확인됐다. 유료 계정을 의도했다면
   `~/Library/Application Support/AudiobookStudio-chatgpt/browser_profiles/chatgpt` 프로필 창에서
   올바른 계정·구독을 확인한다.
3. 다음 30분 감사에서 ChatGPT 실제 청크/시간이 provider efficiency에 나타나는지 확인한다.
4. Gemini `prompt_interaction_failed`가 다음 구간에도 높은지 확인한다. 진행이 계속되면 중단하지 말고,
   진행 대비 오류가 임계치를 넘을 때만 해당 세션을 재시작한다.
5. 7870의 `workflows`가 현재 3개만 유지되고 과거 종료 작업이 다시 나타나지 않는지 확인한다.
6. 현재 로그인 세션이 끝난 뒤에도 7870이 필요하면 runtime-preview job을 정식 plist LaunchAgent로
   승격한다. 번역 스케줄러 LaunchAgent는 이미 영구 설치돼 있다.
