# run_k_e_batch_with_shutdown.py

`run_soseol2_chatgpt_k_e_batch.py`보다도 더 이전 세대의 배치 러너. 지금은 쓰이지 않는 **구(舊) 서재 폴더**(`~/Desktop/소설/#books_source` → `~/Desktop/소설/#[k-e]`, "소설2"가 아니라 "소설")를 대상으로 고정된 `Job` 목록을 순서대로 번역한다.

파일: `scripts/run_k_e_batch_with_shutdown.py`

## 특징

- 파일마다 자동으로 대상을 스캔하는 게 아니라, 코드 안에 `Job(source_name, output_name, korean_title)` 목록을 하드코딩해두고 그것만 순회한다.
- `--shutdown`: 모든 작업이 끝나면 macOS를 실제로 종료(`shutdown`)하는 옵션이 있다 — 오래 걸리는 배치를 밤새 돌려두고 끝나면 컴퓨터가 꺼지도록 하는 용도.
- `--only <문자열...>`: source/output/title에 포함된 문자열로 대상 Job만 골라 실행.
- `--no-korean-only`: `[k]` 생성 생략.
- `--cooldown-seconds` (기본 3600초 = 1시간): 책 사이 대기시간이 `run_soseol2_...`보다 훨씬 길게 잡혀 있다.

## 지금도 유효한가

대상 폴더(`~/Desktop/소설/#books_source`)와 하드코딩된 `Job` 목록이 현재 작업 중인 `소설2` 서재/배치와 무관하다. **사실상 레거시 스크립트**로, 지금 진행 중인 EPUB 번역 작업에는 직접 관여하지 않는다. `--shutdown` 옵션이나 전체 구조를 참고용으로만 남겨둔다.

## 관련 문서
- [run_soseol2_chatgpt_k_e_batch.md](run_soseol2_chatgpt_k_e_batch.md) — 같은 계열의 더 최신 버전
