import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]


class GeminiApiTtsJobWatchdogTests(unittest.TestCase):
    def test_watchdog_restarts_stalled_job_within_two_minutes(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "book.txt"
            output_path = root / "book.m4a"
            work_dir = root / "work"
            fake_script = root / "fake_audiobook_maker.py"

            input_path.write_text("테스트 원문", encoding="utf-8")
            fake_script.write_text(
                textwrap.dedent(
                    """
                    import argparse
                    import json
                    import time
                    from pathlib import Path

                    parser = argparse.ArgumentParser()
                    parser.add_argument("--output-file", type=Path)
                    parser.add_argument("--work-dir", type=Path)
                    parser.add_argument("--heartbeat-file", type=Path)
                    args, _ = parser.parse_known_args()

                    args.work_dir.mkdir(parents=True, exist_ok=True)
                    run_count_path = args.work_dir / "fake_run_count.txt"
                    run_count = int(run_count_path.read_text(encoding="utf-8") if run_count_path.exists() else "0") + 1
                    run_count_path.write_text(str(run_count), encoding="utf-8")

                    if args.heartbeat_file:
                        args.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
                        args.heartbeat_file.write_text(
                            json.dumps({"run_count": run_count, "stage": "fake_start"}) + "\\n",
                            encoding="utf-8",
                        )

                    if run_count == 1:
                        time.sleep(30)
                        raise SystemExit(1)

                    args.output_file.parent.mkdir(parents=True, exist_ok=True)
                    args.output_file.write_bytes(b"audio")
                    if args.heartbeat_file:
                        args.heartbeat_file.write_text(
                            json.dumps({"run_count": run_count, "stage": "done"}) + "\\n",
                            encoding="utf-8",
                        )
                    print("fake success", flush=True)
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "PYTHON_BIN": sys.executable,
                    "AUDIOBOOK_MAKER_SCRIPT": str(fake_script),
                    "WATCHDOG_STALL_SEC": "2",
                    "WATCHDOG_POLL_SEC": "1",
                    "WATCHDOG_KILL_GRACE_SEC": "1",
                    "RETRY_SLEEP_SEC": "1",
                    "SHUTDOWN_ON_SUCCESS": "0",
                }
            )

            result = subprocess.run(
                [
                    "/bin/zsh",
                    str(REPO_ROOT / "scripts" / "run_gemini_api_tts_job.sh"),
                    str(input_path),
                    str(output_path),
                    str(work_dir),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined_output)
            self.assertIn("watchdog: no progress for 2s", combined_output)
            self.assertTrue(output_path.exists())
            self.assertEqual((work_dir / "fake_run_count.txt").read_text(encoding="utf-8"), "2")

    def test_heartbeat_timestamp_prevents_false_restart_when_mtime_stalls(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "book.txt"
            output_path = root / "book.m4a"
            work_dir = root / "work"
            fake_script = root / "fake_audiobook_maker.py"

            input_path.write_text("테스트 원문", encoding="utf-8")
            fake_script.write_text(
                textwrap.dedent(
                    """
                    import argparse
                    import json
                    import os
                    import time
                    from pathlib import Path

                    parser = argparse.ArgumentParser()
                    parser.add_argument("--output-file", type=Path)
                    parser.add_argument("--work-dir", type=Path)
                    parser.add_argument("--heartbeat-file", type=Path)
                    args, _ = parser.parse_known_args()

                    args.work_dir.mkdir(parents=True, exist_ok=True)
                    run_count_path = args.work_dir / "fake_run_count.txt"
                    run_count = int(run_count_path.read_text(encoding="utf-8") if run_count_path.exists() else "0") + 1
                    run_count_path.write_text(str(run_count), encoding="utf-8")

                    if run_count > 1:
                        (args.work_dir / "unexpected_restart.txt").write_text("yes", encoding="utf-8")
                        args.output_file.parent.mkdir(parents=True, exist_ok=True)
                        args.output_file.write_bytes(b"audio")
                        print("unexpected restart", flush=True)
                        raise SystemExit(0)

                    args.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
                    stale_epoch = time.time() - 3600
                    for index in range(4):
                        payload = {
                            "timestamp": round(time.time(), 3),
                            "stage": "still_working",
                            "step": index,
                        }
                        temp_path = args.heartbeat_file.with_name(args.heartbeat_file.name + ".tmp")
                        temp_path.write_text(json.dumps(payload) + "\\n", encoding="utf-8")
                        temp_path.replace(args.heartbeat_file)
                        os.utime(args.heartbeat_file, (stale_epoch, stale_epoch))
                        time.sleep(1.1)

                    args.output_file.parent.mkdir(parents=True, exist_ok=True)
                    args.output_file.write_bytes(b"audio")
                    args.heartbeat_file.write_text(
                        json.dumps({"timestamp": round(time.time(), 3), "stage": "done"}) + "\\n",
                        encoding="utf-8",
                    )
                    print("fake success", flush=True)
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "PYTHON_BIN": sys.executable,
                    "AUDIOBOOK_MAKER_SCRIPT": str(fake_script),
                    "WATCHDOG_STALL_SEC": "3",
                    "WATCHDOG_POLL_SEC": "1",
                    "WATCHDOG_KILL_GRACE_SEC": "1",
                    "RETRY_SLEEP_SEC": "1",
                    "SHUTDOWN_ON_SUCCESS": "0",
                }
            )

            result = subprocess.run(
                [
                    "/bin/zsh",
                    str(REPO_ROOT / "scripts" / "run_gemini_api_tts_job.sh"),
                    str(input_path),
                    str(output_path),
                    str(work_dir),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined_output)
            self.assertNotIn("watchdog: no progress for 3s", combined_output)
            self.assertTrue(output_path.exists())
            self.assertEqual((work_dir / "fake_run_count.txt").read_text(encoding="utf-8"), "1")
            self.assertFalse((work_dir / "unexpected_restart.txt").exists())


if __name__ == "__main__":
    unittest.main()
