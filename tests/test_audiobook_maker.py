import subprocess
import unittest
from argparse import Namespace
from json import loads
from pathlib import Path
from types import SimpleNamespace
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

    def test_retry_split_uses_sentence_units_for_policy_refusal(self) -> None:
        text = "첫 문장이다. 둘째 문장이다. 셋째 문장이다."
        refusal = audiobook_maker.ChatGPTWebExactCopyMismatchError(
            "응답 텍스트가 입력과 일치하지 않습니다",
            response_text=(
                "그 요청은 도와드릴 수 없습니다. "
                "성적으로 노골적이고 동의가 불분명한 장면의 그대로 복제·낭독용 출력은 제공할 수 없습니다."
            ),
        )

        with TemporaryDirectory() as tmpdir:
            child_sections = audiobook_maker.build_retry_child_sections(
                Path(tmpdir),
                prefix="157",
                text=text,
                last_error=refusal,
            )

        self.assertEqual(
            [section.text for section in child_sections],
            ["첫 문장이다.", "둘째 문장이다.", "셋째 문장이다."],
        )

    def test_retry_split_uses_breath_units_when_single_sentence_still_hits_policy_refusal(self) -> None:
        text = "그는 숨을 고르고, 천천히 고개를 들며 다음 말을 이었다."
        refusal = audiobook_maker.ChatGPTWebExactCopyMismatchError(
            "응답 텍스트가 입력과 일치하지 않습니다",
            response_text=(
                "그 요청은 도와드릴 수 없습니다. "
                "성적으로 노골적이고 동의가 불분명한 장면의 그대로 복제·낭독용 출력은 제공할 수 없습니다."
            ),
        )

        with TemporaryDirectory() as tmpdir:
            child_sections = audiobook_maker.build_retry_child_sections(
                Path(tmpdir),
                prefix="157_02",
                text=text,
                last_error=refusal,
            )

        self.assertEqual(
            [section.text for section in child_sections],
            ["그는 숨을 고르고,", "천천히 고개를 들며", "다음 말을 이었다."],
        )

    def test_split_text_into_breath_units_balances_plain_word_runs(self) -> None:
        self.assertEqual(
            audiobook_maker.split_text_into_breath_units("하나 둘 셋 넷 다섯 여섯 일곱"),
            ["하나 둘 셋 넷", "다섯 여섯 일곱"],
        )

    def test_retry_split_detects_wrapped_policy_refusal(self) -> None:
        text = "첫 문장이다. 둘째 문장이다."
        refusal = audiobook_maker.ChatGPTWebExactCopyMismatchError(
            "응답 텍스트가 입력과 일치하지 않습니다",
            response_text=(
                "그 요청은 도와드릴 수 없습니다. "
                "성적으로 노골적이고 동의가 불분명한 장면의 그대로 복제·낭독용 출력은 제공할 수 없습니다."
            ),
        )
        wrapped = RuntimeError("ChatGPT 웹 섹션 합성 실패")
        wrapped.__cause__ = refusal

        with TemporaryDirectory() as tmpdir:
            child_sections = audiobook_maker.build_retry_child_sections(
                Path(tmpdir),
                prefix="157",
                text=text,
                last_error=wrapped,
            )

        self.assertEqual(
            [section.text for section in child_sections],
            ["첫 문장이다.", "둘째 문장이다."],
        )

    def test_policy_refusal_detector_accepts_variant_refusal_wording(self) -> None:
        response = (
            "그건 그대로 재출력할 수 없어. "
            "취한 상태와 강압이 섞인 성적 묘사라서 도와줄 수 없는 요청이야."
        )

        self.assertTrue(audiobook_maker.is_chatgpt_web_refusal_response(response))

    def test_policy_refusal_detector_accepts_softened_reading_rewrite_offer(self) -> None:
        response = (
            "그 문장은 그대로 재출력해드릴 수 없습니다. "
            "수위를 낮춘 낭독용 문장으로는 이렇게 바꿀 수 있습니다."
        )

        self.assertTrue(audiobook_maker.is_chatgpt_web_refusal_response(response))

    def test_policy_refusal_detector_accepts_non_explicit_audiobook_rewrite_offer(self) -> None:
        response = (
            "그 요청은 도와드릴 수 없어요. "
            "오디오북 낭독용으로는 수위를 낮춘 비노골적 문장으로 다듬거나, "
            "감정선만 살린 문장으로 바꿔드릴 수 있어요."
        )

        self.assertTrue(audiobook_maker.is_chatgpt_web_refusal_response(response))


class SpokenLiteralTests(unittest.TestCase):
    def test_spokenize_text_for_readaloud_rewrites_known_domain_override(self) -> None:
        text = "주소는 www.watch-mark-watney-die.com 입니다."

        spoken = audiobook_maker.spokenize_text_for_readaloud(text)

        self.assertEqual(spoken, "주소는 와치 마크 와트너 다이 닷 컴 입니다.")

    def test_spokenize_text_for_readaloud_rewrites_email_address(self) -> None:
        text = "문의는 mark.watney@naver.com 으로 보내 주세요."

        spoken = audiobook_maker.spokenize_text_for_readaloud(text)

        self.assertEqual(spoken, "문의는 마크 와트너 앳 네이버 닷 컴 으로 보내 주세요.")

    def test_section_text_matches_expected_rejects_old_raw_domain_text(self) -> None:
        with TemporaryDirectory() as tmpdir:
            text_path = Path(tmpdir) / "195_02_02.txt"
            text_path.write_text("www.watch-mark-watney-die.com\n", encoding="utf-8")

            matches = audiobook_maker.section_text_matches_expected(
                text_path,
                "와치 마크 와트너 다이 닷 컴",
            )

        self.assertFalse(matches)


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


class ChatGPTWebNormalizationTests(unittest.TestCase):
    def test_normalize_chatgpt_web_copy_treats_newlines_like_spaces(self) -> None:
        actual = audiobook_maker.normalize_chatgpt_web_copy("아마 와치 마크 와트너 다이 닷 컴\n같은 웹사이트도 있겠지.")
        expected = audiobook_maker.normalize_chatgpt_web_copy("아마 와치 마크 와트너 다이 닷 컴 같은 웹사이트도 있겠지.")

        self.assertEqual(actual, expected)

    def test_is_chatgpt_web_rate_limit_text_detects_modal_message(self) -> None:
        message = (
            "Locator.click: Timeout 30000ms exceeded.\n"
            "요청이 너무 빠릅니다. 데이터를 보호하기 위해 대화 액세스가 일시적으로 제한되었습니다."
        )

        self.assertTrue(audiobook_maker.is_chatgpt_web_rate_limit_text(message))


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

    def test_synthesize_chatgpt_web_recurses_into_single_existing_child_before_reusing_split_audio(self) -> None:
        class FakePage:
            def close(self) -> None:
                return None

        class FakeContext:
            def new_page(self) -> FakePage:
                return FakePage()

            def add_cookies(self, _cookies: object) -> None:
                return None

            def close(self) -> None:
                return None

        class FakeBrowser:
            def new_context(self, **_kwargs: object) -> FakeContext:
                return FakeContext()

            def close(self) -> None:
                return None

        class FakePlaywrightManager:
            def __enter__(self) -> SimpleNamespace:
                chromium = SimpleNamespace(launch=lambda **_kwargs: FakeBrowser())
                return SimpleNamespace(chromium=chromium)

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            (work_dir / "001_01.txt").write_text("첫 하위 조각", encoding="utf-8")
            (work_dir / "001_01_01.txt").write_text("첫 번째 더 깊은 조각", encoding="utf-8")
            (work_dir / "001_01_02.txt").write_text("두 번째 더 깊은 조각", encoding="utf-8")
            split_audio_1 = work_dir / "001_01_01.mp3"
            split_audio_2 = work_dir / "001_01_02.mp3"
            split_audio_1.write_bytes(b"audio-1")
            split_audio_2.write_bytes(b"audio-2")

            args = Namespace(
                chatgpt_web_chrome_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                chatgpt_web_max_attempts=3,
                heartbeat_file=None,
                chatgpt_web_visible=False,
                voice="cove",
            )
            sections = [audiobook_maker.AudioSection(index=1, title=None, text="원본 전체 텍스트")]

            with patch(
                "audiobook_maker.load_chatgpt_web_modules",
                return_value=(object(), lambda: FakePlaywrightManager(), RuntimeError),
            ):
                with patch("audiobook_maker.load_chatgpt_web_cookies", return_value=[]):
                    with patch("audiobook_maker.prepare_chatgpt_web_page"):
                        with patch(
                            "audiobook_maker.fetch_chatgpt_web_voice_settings",
                            return_value=("cove", ["cove"]),
                        ):
                            with patch(
                                "audiobook_maker.reuse_existing_audio_if_valid",
                                side_effect=lambda path, label: path in {split_audio_1, split_audio_2},
                            ):
                                audio_files = audiobook_maker.synthesize_chatgpt_web_sections(
                                    sections,
                                    args=args,
                                    voice="cove",
                                    work_dir=work_dir,
                                )

        self.assertEqual(audio_files, [split_audio_1, split_audio_2])


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
