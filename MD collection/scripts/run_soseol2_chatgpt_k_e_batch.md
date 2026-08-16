# run_soseol2_chatgpt_k_e_batch.py

`/Users/hyeokjunkong/Desktop/소설2` 폴더 전체를 대상으로 한 **CLI 기반 배치 번역 오케스트레이터**. 지금 실제로 쓰이고 있는 `webui/workflow_runner.py`(웹 UI 배치 엔진)보다 먼저 만들어진, 터미널에서 직접 돌리는 버전이다. 번역뿐 아니라 분류·중복정리·검수·유휴시간 유지보수까지 한 프로세스 안에서 순서대로 처리하도록 설계되어 있다.

파일: `scripts/run_soseol2_chatgpt_k_e_batch.py` (약 1,130줄)

## 대상 폴더 (하드코딩)

```
SOURCE_DIR            = ~/Desktop/소설2
READROBE_SOURCE_DIR   = ~/Desktop/소설2/readrobe.com
EXTRA_SOURCE_DIRS     = (~/Desktop/소설2/new books from vk,)
KE_DIR / K_DIR         = ~/Desktop/소설2/[k-e], [k]
WORK_ROOT             = ~/Desktop/소설2/_chatgpt_translate_work
LOG_DIR               = ~/Desktop/소설2/_batch_logs
FINISHED_DIR          = ~/Desktop/소설2/finished
```

## 하는 일 (순서대로)

1. 위 소스 폴더들에서 번역 대상 EPUB을 모은다.
2. 각 파일마다 `translate_epub_with_chatgpt_web_to_study_epub.py`를 서브프로세스로 호출.
3. `--no-korean-only`가 아니면 완료된 `[k-e]`로부터 `[k]`도 생성.
4. `classify_soseol2_epubs_by_category.py`로 장르 분류.
5. 톤 검수(`final_epub_tone_review.py`) / 대화 2차 검수(`final_epub_dialogue_consistency_review.py`) / 최종 품질 감사(`final_epub_quality_audit.py`) 스크립트를 연달아 호출.
6. `--dedupe-only`가 아니면, 유휴 시간 유지보수 스크립트(`idle_completed_epub_tone_maintenance.py`)까지 연동.

## 주요 CLI 인자

| 인자 | 의미 |
|---|---|
| `--only <문자열...>` | 파일명에 이 문자열이 포함된 것만 처리 |
| `--force` | 이미 검증된 산출물이 있어도 다시 만든다 |
| `--no-korean-only` | `[k]` 생성 생략 |
| `--dedupe-only` | 이미 `[k-e]`/`[k]`가 검증된 원본만 정리하고 즉시 종료(번역 실행 안 함) |
| `--cooldown-seconds` (기본 900) | 파일 사이 대기시간 |
| `--max-chars-per-chunk` / `--chunks-per-conversation` / `--inter-request-delay-sec` / `--request-timeout-sec` / `--web-max-attempts` / `--web-visible` | `translate_epub_with_chatgpt_web_to_study_epub.py`로 그대로 전달되는 번역 세부 설정 |
| `--dry-run` | 실제 실행 없이 계획만 출력 |

## 현재 배치 파이프라인과의 관계

**현재 웹 UI(`web_app.py`)가 띄우는 배치 작업은 이 스크립트가 아니라 `webui/workflow_runner.py`를 사용한다.** 이 스크립트는 잡 단위(`.webui/jobs/<job_id>/`)로 상태를 관리하지 않고, `소설2` 폴더 자체에 고정된 작업 디렉터리(`_chatgpt_translate_work`)와 로그(`_batch_logs`)를 두는 방식이라 웹 UI의 진행상황 화면(heartbeat/batch_status.json)과는 연동되지 않는다. 터미널에서 웹 UI 없이 전체 서재를 한 번에 정리하고 싶을 때 쓸 수 있는 대안 경로로 남아 있다.

## 관련 문서
- [translate_epub_with_chatgpt_web_to_study_epub.md](translate_epub_with_chatgpt_web_to_study_epub.md)
- [idle_completed_epub_tone_maintenance.md](idle_completed_epub_tone_maintenance.md)
- [classify_soseol2_epubs_by_category.md](classify_soseol2_epubs_by_category.md)
- [EPUB 배치 번역 중복작업 방지 처리절차](../EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md) — 웹 UI 경로(`workflow_runner.py`)의 중복방지 절차 문서
