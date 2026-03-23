# YOU Novel Resume Notes (2026-03-23)

## Repo State

- Branch: `main`
- Remote: `origin`
- Purpose of current code changes:
  - allow retry splitting on shorter exact-copy failures
  - normalize harmless spacing before punctuation in ChatGPT copy checks
  - prefer existing retry child text files over retrying a known-bad parent chunk
  - add `pytest` invocation note and config
  - remove unused `edge-tts` dependency from `requirements.txt`

## External Audiobook Job State

- Input file:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/YOU - A Novel(Kor).txt`
- Output file:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a`
- Work dir:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work`
- Log file from last run:
  - `/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/logs/you_novel_chatgpt_web_cove_20260323_192005.log`

## Current Progress Snapshot

- Background job was stopped intentionally by user.
- Last recorded progress in log reached main chunk `099`.
- Main chunk `100` failed after browser/page closure errors:
  - `Page.wait_for_timeout: Target page, context or browser has been closed`
  - `Page.goto: net::ERR_ABORTED`
- Current work-dir snapshot at stop time:
  - numbered main mp3 count: `97`
  - highest numbered main mp3 file present: `099.mp3`
  - total mp3 files including split children: `110`

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
VOICE=cove REQUEST_TIMEOUT_SEC=600 CHATGPT_WEB_VISIBLE=0 \
./scripts/run_chatgpt_web_job.sh \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/YOU - A Novel(Kor).txt" \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove.m4a" \
  "/Users/hyeokjunkong/Desktop/소설/YOU - A Novel(Kor)/audiobooks/YOU - A Novel(Kor)_audiobook_chatgpt_web_cove_work"
```

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
