# run_followup_chatgpt_web_jobs.py

한 작업이 끝나기를 기다렸다가, 끝나면 이어서 다른 작업들을 순서대로 실행해주는 아주 작은 대기열(queue) 유틸리티. 번역 파이프라인 전용은 아니고, `run_chatgpt_web_job.sh` 셸 스크립트로 실행되는 어떤 웹 작업에도 쓸 수 있는 범용 도구다.

파일: `scripts/run_followup_chatgpt_web_jobs.py` (94줄)

## 동작

1. `--wait-input-file`이 포함된 `run_chatgpt_web_job.sh` 프로세스가 `ps` 출력에서 사라지고, `--wait-output-file`이 생성될 때까지 `--poll-sec`(기본 60초) 간격으로 대기(`target_still_running`).
2. 대기가 끝나면 `--job INPUT OUTPUT WORK_DIR` 형태로 등록된 후속 작업들을 순서대로 `./scripts/run_chatgpt_web_job.sh <input> <output> <work_dir>`로 실행.
3. 모든 진행 상황을 `--log-file`에 타임스탬프와 함께 append.

## CLI

```bash
python3 scripts/run_followup_chatgpt_web_jobs.py \
  --repo-root <저장소 루트> \
  --wait-input-file <먼저 끝나야 하는 작업의 입력 파일명> \
  --wait-output-file <그 작업의 출력 파일 경로> \
  --log-file <로그 파일 경로> \
  --poll-sec 60 \
  --job <input1> <output1> <workdir1> \
  --job <input2> <output2> <workdir2> ...
```

## 언제 쓰는가

여러 개의 웹 자동화 작업(같은 브라우저 세션을 동시에 쓸 수 없는 작업들)을 "하나 끝나면 다음" 식으로 순차 예약해두고 싶을 때. 지금의 EPUB 배치 번역(`workflow_runner.py`)은 자체적으로 순차 처리를 하므로 이 스크립트가 관여하지 않지만, `translate_epub_with_chatgpt_web_to_study_epub.py`가 아닌 `run_chatgpt_web_job.sh` 기반의 다른 웹 작업 체계와 함께 쓰도록 만들어진 범용 대기열 도구다.
