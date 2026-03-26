# YOU Novel Resume Notes (2026-03-23)

## Completion Update (2026-03-26)

- Final output completed:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a`
- Final heartbeat snapshot:
  - time: `2026-03-26 01:12:00`
  - stage: `done`
  - detail: `YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a`
- Manual recovery applied before final resume:
  - rebuilt `156.mp3` from `156_01_01.mp3` + `156_01_02.mp3` + `156_01_03.mp3` + `156_02.mp3` + `156_03.mp3`
  - rebuilt `157.mp3` after expanding refusal detection and regenerating `157_02_01.mp3` through `157_02_04.mp3`
- Verification completed:
  - `python3 -m pytest -q`
  - `36 passed in 10.50s`
  - validated all work-dir mp3 files plus the final `.m4a` with `ensure_valid_audio_file`

## Repo State

- Branch: `main`
- Remote: `origin`
- Purpose of current code changes:
  - allow retry splitting on shorter exact-copy failures
  - normalize harmless spacing before punctuation in ChatGPT copy checks
  - prefer existing retry child text files over retrying a known-bad parent chunk
  - make the shell watchdog treat heartbeat JSON timestamps as real progress
  - add regression coverage for stale heartbeat mtimes
  - add `pytest` invocation note and config
  - remove unused `edge-tts` dependency from `requirements.txt`

## External Audiobook Job State

- Input file:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/YOU - A Novel(Kor).txt`
- Output file:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a`
- Work dir:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work`
- Current live log file:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/logs/you_novel_chatgpt_web_cove_resume_20260325_193955.log`
- Prior restart logs:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/logs/you_novel_chatgpt_web_cove_resume_20260325_193250.log`
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/logs/you_novel_chatgpt_web_cove_resume_20260324_220915.log`

## Current Progress Snapshot

- Background job is running under the patched watchdog wrapper.
- The previous false watchdog restart at `2026-03-25 19:34:54` was caused by relying on filesystem mtimes alone while the heartbeat JSON timestamp was still advancing.
- Latest live heartbeat snapshot when this note was updated:
  - time: `2026-03-25 20:04:18`
  - label: `130/240`
  - stage: `wait_for_response`
  - attempt: `1`
  - detail: `stable_polls=0 chars=1476`
- Current work-dir snapshot:
  - numbered main mp3 count: `126`
  - highest numbered main mp3 file present: `129.mp3`
  - total mp3 files including split children: `147`
  - final combined output file: not present yet
- Confirmed after the watchdog fix:
  - main chunks `115.mp3` through `129.mp3` were produced without a false stall restart
  - the active run advanced beyond the old failure boundary and continued into chunk `130`

## Manual Text Edits Already Applied Outside Repo

These edits exist in the external source/work files and are not tracked by git because they are outside this repository.

- Removed the parenthesized email in the chunk-015 chain:
  - replaced `(asst1@stopitrecords.com)` with nothing
- Replaced the email in the chunk-037 chain and source text:
  - `'HerzogNathaniel@gmail.com'`
  - -> `'HerzogNathaniel 구글 메일를'`

Relevant edited external files include:

- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/YOU - A Novel(Kor).txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/015.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/015_02.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/015_02_02.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/015_02_02_01.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/015_02_02_01_01.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/037.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/037_02.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/037_02_02.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/037_02_02_01.txt`
- `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work/037_02_02_01_02.txt`

## Resume Command

Run from this repository root:

```bash
VOICE=cove REQUEST_TIMEOUT_SEC=600 CHATGPT_WEB_VISIBLE=0 SHUTDOWN_ON_SUCCESS=0 \
./scripts/run_chatgpt_web_job.sh \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/YOU - A Novel(Kor).txt" \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a" \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work"
```

Convenience wrapper:

```bash
./scripts/resume_you_novel_shutdown.sh
```

If you want the machine to stay on while monitoring, keep `SHUTDOWN_ON_SUCCESS=0`.

After completion, verify:

```bash
python3 - <<'PY'
from pathlib import Path
from audiobook_maker import ensure_valid_audio_file
work = Path("/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work")
final = Path("/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a")
for path in sorted(work.glob("*.mp3")) + [final]:
    ensure_valid_audio_file(path)
print("ok")
PY
```
