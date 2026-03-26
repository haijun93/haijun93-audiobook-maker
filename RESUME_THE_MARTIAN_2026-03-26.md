# The Martian Resume Notes (2026-03-26)

## Repo State

- Branch: `main`
- Remote: `origin`
- Verification completed:
  - `python3 -m pytest -q`
  - `42 passed in 10.45s`
- Purpose of current code changes:
  - make the shell watchdog treat heartbeat JSON timestamps as real progress
  - allow retry splitting on shorter exact-copy failures
  - add refusal-driven sentence and breath-unit fallback splitting
  - normalize harmless whitespace and line-break differences in ChatGPT copy checks
  - spokenize domain and email literals before ChatGPT web read-aloud
  - prevent reusing old mp3 artifacts after the underlying text changes
  - wait through the ChatGPT web rate-limit modal while continuing heartbeat updates

## External Audiobook Job State

- Input file:
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/The_Martian_by_Andy_Weir_ko_chatgpt.txt`
- Output file:
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove.m4a`
- Work dir:
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove_work`
- Live log file when stopped:
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/logs/the_martian_chatgpt_web_cove_resume_20260326_214158_after_wait.log`

## Stop Snapshot

- Manual stop time:
  - `2026-03-26 23:29:50 KST`
- Last heartbeat snapshot before stop:
  - time: `2026-03-26 23:29:07`
  - label: `226/238`
  - stage: `audio_fetch_start`
  - attempt: `1`
  - section prefix: `226`
- Current work-dir snapshot at stop:
  - numbered main mp3 count: `223`
  - highest numbered main mp3 file present: `225.mp3`
  - total mp3 files including split children: `233`
  - final combined output file: not present
- Expected immediate resume point:
  - `226` should be retried first on the next run
  - `226.mp3` did not exist at stop time

## Notable Progress During This Session

- The earlier failure chain around `195_02_02_01_02` was cleared.
- The spoken-form replacement for `www.watch-mark-watney-die.com` is already applied in the source/work files for the `195` chain.
- Main chunks advanced through `225.mp3` before stopping.

## External Text Edits Already Applied Outside Repo

These edits live outside git because they are in the novel source/work directory on disk.

- Replaced `www.watch-mark-watney-die.com` with `와치 마크 와트너 다이 닷 컴` in:
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/The_Martian_by_Andy_Weir_ko_chatgpt.txt`
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove_work/195.txt`
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove_work/195_02.txt`
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove_work/195_02_02.txt`
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove_work/195_02_02_01.txt`
  - `/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove_work/195_02_02_01_02.txt`

## Resume Command

Run from this repository root:

```bash
VOICE=cove REQUEST_TIMEOUT_SEC=600 CHATGPT_WEB_VISIBLE=0 SHUTDOWN_ON_SUCCESS=0 \
./scripts/run_chatgpt_web_job.sh \
  "/Users/hyeokjunkong/Desktop/소설/The Martian/The_Martian_by_Andy_Weir_ko_chatgpt.txt" \
  "/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove.m4a" \
  "/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove_work"
```

After completion, verify:

```bash
python3 - <<'PY'
from pathlib import Path
from audiobook_maker import ensure_valid_audio_file
work = Path("/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove_work")
final = Path("/Users/hyeokjunkong/Desktop/소설/The Martian/audiobooks/The_Martian_by_Andy_Weir_ko_chatgpt_audiobook_chatgpt_web_cove.m4a")
for path in sorted(work.glob("*.mp3")) + [final]:
    ensure_valid_audio_file(path)
print("ok")
PY
```
