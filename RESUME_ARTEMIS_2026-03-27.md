# Artemis Resume Notes (updated 2026-03-29)

## Repo State

- Branch: `main`
- Provider: `chatgpt_web`
- Voice: `cove`
- Launch mode used for resume: detached `screen` session
- Current detached session state:
  - no active `screen` session

## External Audiobook Job State

- Input file:
  - `/Users/hyeokjunkong/Desktop/소설/Artemis/Andy_Weir_-_Artemis_ko_chatgpt.txt`
- Output file:
  - `/Users/hyeokjunkong/Desktop/소설/Artemis/audiobooks/Andy_Weir_-_Artemis_ko_chatgpt_audiobook_chatgpt_web_cove.m4a`
- Work dir:
  - `/Users/hyeokjunkong/Desktop/소설/Artemis/audiobooks/Andy_Weir_-_Artemis_ko_chatgpt_audiobook_chatgpt_web_cove_work`
- Live log:
  - `/Users/hyeokjunkong/Desktop/소설/Artemis/audiobooks/logs/artemis_chatgpt_web_cove_resume_20260328_231234.log`

## Current Snapshot

- Resume run start:
  - `2026-03-28 23:12:35 KST`
- Final heartbeat:
  - time: `2026-03-29 02:31:25 KST`
  - stage: `done`
  - detail: `Andy_Weir_-_Artemis_ko_chatgpt_audiobook_chatgpt_web_cove.m4a`
- Final wrapper exit:
  - time: `2026-03-29 02:31:33 KST`
  - code: `0`
- Final work-dir snapshot:
  - numbered main mp3 count: `175`
  - highest numbered main mp3 file: `175.mp3`

## Recovery Notes

- The previous detached run from `2026-03-27` is no longer active.
- `screen -ls` showed no active session before restart.
- The stale heartbeat from the old run stopped at:
  - `2026-03-27 22:55:29 KST`
  - label: `37/175`
  - stage: `wait_for_response`
- The resumed run cleared the old `037` boundary and completed through `175.mp3`.

## Completion Verification

- Final audiobook:
  - `/Users/hyeokjunkong/Desktop/소설/Artemis/audiobooks/Andy_Weir_-_Artemis_ko_chatgpt_audiobook_chatgpt_web_cove.m4a`
- File size:
  - `424,981,177 bytes` (`405M` from `ls -lh`)
- `ffprobe` summary:
  - duration: `35813.328s` (`9h 56m 53.328s`)
  - bit_rate: `94932`
- Repo tests on `2026-03-29`:
  - `python3 -m unittest discover -s tests -p 'test_*.py'`
  - result: `Ran 42 tests in 10.416s` / `OK`

## Monitoring Commands

Run from this repository root:

```bash
screen -ls
tail -f "/Users/hyeokjunkong/Desktop/소설/Artemis/audiobooks/logs/artemis_chatgpt_web_cove_20260327_220148.log"
cat "/Users/hyeokjunkong/Desktop/소설/Artemis/audiobooks/Andy_Weir_-_Artemis_ko_chatgpt_audiobook_chatgpt_web_cove_work/chatgpt_web_job_heartbeat.json"
```

At the time of this update, the heartbeat reports `stage: done` and there is no active `screen` session to monitor.

## Manual Resume Command

If the `screen` session stops, restart with:

```bash
VOICE=cove REQUEST_TIMEOUT_SEC=600 CHATGPT_WEB_VISIBLE=0 SHUTDOWN_ON_SUCCESS=0 \
./scripts/run_chatgpt_web_job.sh \
  "/Users/hyeokjunkong/Desktop/소설/Artemis/Andy_Weir_-_Artemis_ko_chatgpt.txt" \
  "/Users/hyeokjunkong/Desktop/소설/Artemis/audiobooks/Andy_Weir_-_Artemis_ko_chatgpt_audiobook_chatgpt_web_cove.m4a" \
  "/Users/hyeokjunkong/Desktop/소설/Artemis/audiobooks/Andy_Weir_-_Artemis_ko_chatgpt_audiobook_chatgpt_web_cove_work"
```
