import subprocess
import unittest
from argparse import Namespace
from json import loads
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import audiobook_maker


class HeadingDetectionTests(unittest.TestCase):
    def test_detects_korean_chapter_heading(self) -> None:
        self.assertTrue(audiobook_maker.looks_like_heading("제1장"))

    def test_rejects_regular_sentence(self) -> None:
        self.assertFalse(audiobook_maker.looks_like_heading("그날 밤은 유난히 조용했다."))


class SectionSplitTests(unittest.TestCase):
    def test_heading_stays_with_first_body_chunk(self) -> None:
        text = "제1장\n\n" + ("가" * 900)

        sections = audiobook_maker.split_into_sections(text, max_chars=900)

        self.assertEqual(len(sections), 1)
        self.assertTrue(sections[0].text.startswith("제1장\n\n"))
        self.assertEqual(sections[0].title, "제1장")

    def test_retry_split_uses_smaller_child_sections_for_short_failures(self) -> None:
        text = " ".join(["가나다라마"] * 80)

        with TemporaryDirectory() as tmpdir:
            child_sections = audiobook_maker.build_retry_child_sections(
                Path(tmpdir),
                prefix="138_02_01",
                text=text,
            )

        self.assertGreater(len(child_sections), 1)
        self.assertTrue(all(len(section.text) < len(text) for section in child_sections))

    def test_retry_split_reuses_existing_direct_child_texts(self) -> None:
        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "138_02_01.txt").write_text("첫 번째 조각", encoding="utf-8")
            (work_dir / "138_02_02.txt").write_text("두 번째 조각", encoding="utf-8")

            child_sections = audiobook_maker.build_retry_child_sections(
                work_dir,
                prefix="138_02",
                text="원본 전체 텍스트",
            )

        self.assertEqual([section.text for section in child_sections], ["첫 번째 조각", "두 번째 조각"])


class OutputPathTests(unittest.TestCase):
    def test_default_output_path_uses_dedicated_audiobooks_folder(self) -> None:
        args = Namespace(
            output_file=None,
            input_file=Path("/tmp/source_ko.txt"),
        )

        output_path = audiobook_maker.default_output_path(args)

        self.assertEqual(output_path, Path("/tmp/audiobooks/source_ko_audiobook.m4a"))

    def test_resolve_output_path_without_input_uses_cwd_audiobooks_folder(self) -> None:
        args = Namespace(
            output_file=None,
            input_file=None,
        )

        output_path = audiobook_maker.resolve_output_path(args)

        self.assertEqual(
            output_path,
            Path.cwd() / audiobook_maker.DEFAULT_AUDIOBOOK_OUTPUT_DIRNAME / "translated_audiobook.m4a",
        )


class ProviderSurfaceTests(unittest.TestCase):
    def test_parse_args_defaults_provider_to_chatgpt_web(self) -> None:
        with patch("sys.argv", ["audiobook_maker.py"]):
            args = audiobook_maker.parse_args()

        self.assertEqual(args.provider, "chatgpt_web")

    def test_parse_args_restricts_provider_choices_to_web_backends(self) -> None:
        with patch("sys.argv", ["audiobook_maker.py", "--provider", "unsupported"]):
            with self.assertRaises(SystemExit):
                audiobook_maker.parse_args()

    def test_default_chunk_size_uses_chatgpt_web_value(self) -> None:
        self.assertEqual(audiobook_maker.default_max_chars_per_chunk("chatgpt_web"), 1800)
        self.assertEqual(audiobook_maker.default_max_chars_per_chunk("unused"), 1800)


class VoiceSelectionTests(unittest.TestCase):
    def test_default_chatgpt_web_voice_is_cove(self) -> None:
        self.assertEqual(audiobook_maker.default_chatgpt_web_voice(), "cove")

    def test_resolve_voice_defaults_chatgpt_web_voice(self) -> None:
        args = Namespace(voice=None, provider="chatgpt_web")

        self.assertEqual(audiobook_maker.resolve_voice(args), "cove")

    def test_resolve_voice_normalizes_chatgpt_web_voice(self) -> None:
        args = Namespace(
            voice="Cove",
            provider="chatgpt_web",
        )

        self.assertEqual(audiobook_maker.resolve_voice(args), "cove")


class ReadingInstructionTests(unittest.TestCase):
    def test_common_reading_instructions_are_used_as_default(self) -> None:
        self.assertEqual(
            audiobook_maker.DEFAULT_CHATGPT_INSTRUCTIONS,
            audiobook_maker.DEFAULT_KOREAN_AUDIOBOOK_READING_INSTRUCTIONS,
        )

    def test_chatgpt_web_prompt_includes_default_reading_instructions(self) -> None:
        prompt = audiobook_maker.build_chatgpt_web_repeat_prompt("안녕하세요.")

        self.assertIn("추가 낭독 지침", prompt)
        self.assertIn("한국어 원어민 전문 성우", prompt)
        self.assertIn("안녕하세요.", prompt)

class ChatGPTWebWorkflowTests(unittest.TestCase):
    def test_chatgpt_web_launch_args_hide_window_by_default(self) -> None:
        args = audiobook_maker.chatgpt_web_launch_args(visible=False)

        self.assertIn("--window-position=-2400,-2400", args)
        self.assertIn("--window-size=1280,900", args)

    def test_extract_chatgpt_conversation_id(self) -> None:
        conversation_id = audiobook_maker.extract_chatgpt_conversation_id(
            "https://chatgpt.com/c/1234-abcd?model=gpt-4o"
        )

        self.assertEqual(conversation_id, "1234-abcd")


class AudioFormatTests(unittest.TestCase):
    def test_m4a_uses_aac(self) -> None:
        codec_args = audiobook_maker.ffmpeg_codec_args(Path("book.m4a"), 96)

        self.assertEqual(codec_args, ["-vn", "-c:a", "aac", "-b:a", "96k"])

    def test_concat_line_escapes_single_quotes(self) -> None:
        path = Path("/tmp/it's-book.aiff").resolve()
        line = audiobook_maker.ffmpeg_concat_line(path)

        expected = "file '{}'".format(str(path).replace("'", r"'\''"))
        self.assertEqual(line, expected)

    def test_chatgpt_web_uses_mp3_temp_audio(self) -> None:
        args = Namespace(provider="chatgpt_web")

        self.assertEqual(audiobook_maker.temp_audio_suffix(args), ".mp3")

    def test_partial_audio_path_inserts_partial_before_suffix(self) -> None:
        self.assertEqual(
            audiobook_maker.partial_audio_path(Path("/tmp/book.m4a")),
            Path("/tmp/book.partial.m4a"),
        )


class AudioValidationTests(unittest.TestCase):
    def test_find_incomplete_audio_artifacts_detects_partial_audio_files(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "001.partial.mp3").write_bytes(b"x")
            (root / "002.m4a.partial").write_bytes(b"x")
            (root / "003.mp3").write_bytes(b"x")
            (root / "notes.partial.txt").write_text("ignore", encoding="utf-8")

            found = audiobook_maker.find_incomplete_audio_artifacts(root)

        self.assertEqual(
            [path.name for path in found],
            ["001.partial.mp3", "002.m4a.partial"],
        )

    def test_audio_file_looks_complete_rejects_zero_byte_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "empty.mp3"
            path.write_bytes(b"")

            is_valid, reason = audiobook_maker.audio_file_looks_complete(path)

        self.assertFalse(is_valid)
        self.assertIn("0", reason)

    def test_audio_file_looks_complete_accepts_ffprobe_audio_stream(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout='{"streams":[{"codec_type":"audio"}],"format":{"duration":"12.3"}}',
            stderr="",
        )
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "book.mp3"
            path.write_bytes(b"audio")
            with patch("audiobook_maker.resolve_ffprobe_binary", return_value="/usr/bin/ffprobe"):
                with patch("audiobook_maker.run_command", return_value=completed):
                    is_valid, reason = audiobook_maker.audio_file_looks_complete(path)

        self.assertTrue(is_valid)
        self.assertEqual(reason, "")

    def test_audio_file_looks_complete_rejects_missing_audio_stream(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout='{"streams":[{"codec_type":"video"}],"format":{"duration":"12.3"}}',
            stderr="",
        )
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "book.mp3"
            path.write_bytes(b"audio")
            with patch("audiobook_maker.resolve_ffprobe_binary", return_value="/usr/bin/ffprobe"):
                with patch("audiobook_maker.run_command", return_value=completed):
                    is_valid, reason = audiobook_maker.audio_file_looks_complete(path)

        self.assertFalse(is_valid)
        self.assertIn("오디오 스트림", reason)

    def test_combine_audio_files_copies_via_partial_file_then_replaces(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "segment.mp3"
            output = root / "book.mp3"
            source.write_bytes(b"audio")

            with patch("audiobook_maker.ensure_valid_audio_file") as ensure_valid:
                audiobook_maker.combine_audio_files(
                    [source],
                    output_path=output,
                    work_dir=root,
                    bitrate_kbps=96,
                )

            self.assertEqual(output.read_bytes(), b"audio")
            self.assertFalse(audiobook_maker.partial_audio_path(output).exists())
            self.assertEqual(ensure_valid.call_count, 2)


class HeartbeatTests(unittest.TestCase):
    def test_progress_heartbeat_writes_stage_metadata(self) -> None:
        with TemporaryDirectory() as tmpdir:
            heartbeat_path = Path(tmpdir) / "heartbeat.json"

            heartbeat = audiobook_maker.ProgressHeartbeat(heartbeat_path)
            heartbeat.beat(
                stage="waiting",
                label="111/240",
                section_prefix="111",
                attempt=2,
                detail="stable_polls=1",
            )

            payload = loads(heartbeat_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["stage"], "waiting")
        self.assertEqual(payload["label"], "111/240")
        self.assertEqual(payload["section_prefix"], "111")
        self.assertEqual(payload["attempt"], 2)
        self.assertEqual(payload["detail"], "stable_polls=1")


if __name__ == "__main__":
    unittest.main()
