import unittest
from argparse import Namespace
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
        self.assertIn("가" * 20, sections[0].text)

    def test_long_paragraph_splits_into_multiple_sections(self) -> None:
        paragraph = " ".join(["이 문장은 비교적 길다."] * 80)
        text = f"제2장\n\n{paragraph}"

        sections = audiobook_maker.split_into_sections(text, max_chars=220)

        self.assertGreaterEqual(len(sections), 2)
        self.assertTrue(sections[0].text.startswith("제2장\n\n"))
        self.assertEqual(sections[0].title, "제2장")


class VoiceSelectionTests(unittest.TestCase):
    def test_default_korean_voice_prefers_flo(self) -> None:
        voices = [
            audiobook_maker.SayVoice(name="Reed (한국어(대한민국))", locale="ko_KR"),
            audiobook_maker.SayVoice(name="Flo (한국어(대한민국))", locale="ko_KR"),
        ]

        voice = audiobook_maker.default_korean_voice(voices)

        self.assertEqual(voice, "Flo (한국어(대한민국))")

    def test_default_edge_voice_prefers_sunhi(self) -> None:
        voices = [
            {"ShortName": "ko-KR-InJoonNeural", "Locale": "ko-KR"},
            {"ShortName": "ko-KR-SunHiNeural", "Locale": "ko-KR"},
        ]

        voice = audiobook_maker.default_edge_voice(voices)

        self.assertEqual(voice, "ko-KR-SunHiNeural")

    def test_default_melo_voice_is_kr(self) -> None:
        self.assertEqual(audiobook_maker.default_melo_voice(), "KR")

    def test_default_gemini_voice_is_sulafat(self) -> None:
        self.assertEqual(audiobook_maker.default_gemini_voice(), "Sulafat")

    def test_default_chatgpt_voice_is_spruce(self) -> None:
        self.assertEqual(audiobook_maker.default_chatgpt_voice(), "Spruce")

    def test_default_chatgpt_web_voice_is_cove(self) -> None:
        self.assertEqual(audiobook_maker.default_chatgpt_web_voice(), "cove")

    def test_default_gemini_model_is_free_tier(self) -> None:
        self.assertTrue(audiobook_maker.gemini_model_is_free_tier(audiobook_maker.DEFAULT_GEMINI_MODEL))

    def test_default_openai_voice_prefers_marin_for_gpt4o(self) -> None:
        voice = audiobook_maker.default_openai_voice("gpt-4o-mini-tts")

        self.assertEqual(voice, "marin")

    def test_openai_legacy_model_limits_voice_choices(self) -> None:
        choices = audiobook_maker.openai_voice_choices("tts-1-hd")

        self.assertEqual(choices, audiobook_maker.OPENAI_LEGACY_VOICES)


class OutputPathTests(unittest.TestCase):
    def test_default_output_path_uses_dedicated_audiobooks_folder(self) -> None:
        args = Namespace(
            output_file=None,
            input_file=Path("/tmp/source_ko.txt"),
        )

        output_path = audiobook_maker.default_output_path(args)

        self.assertEqual(output_path, Path("/tmp/audiobooks/source_ko_audiobook.m4a"))

    def test_default_audiobook_output_dir_reuses_existing_audiobooks_folder(self) -> None:
        output_dir = audiobook_maker.default_audiobook_output_dir(
            Path("/tmp/audiobooks/source_ko.txt")
        )

        self.assertEqual(output_dir, Path("/tmp/audiobooks"))

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


class DefaultProviderTests(unittest.TestCase):
    def test_parse_args_defaults_provider_to_gemini(self) -> None:
        with patch("sys.argv", ["audiobook_maker.py"]):
            args = audiobook_maker.parse_args()

        self.assertEqual(args.provider, "gemini")


class OpenAIPayloadTests(unittest.TestCase):
    def test_gemini_payload_uses_prebuilt_voice(self) -> None:
        payload = audiobook_maker.build_gemini_speech_payload(
            prompt="읽어줘",
            voice="Sulafat",
            language_code="ko-KR",
        )

        self.assertEqual(
            payload["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"],
            "Sulafat",
        )
        self.assertEqual(payload["generationConfig"]["speechConfig"]["languageCode"], "ko-KR")
        self.assertEqual(payload["generationConfig"]["responseModalities"], ["AUDIO"])


class GeminiGuardTests(unittest.TestCase):
    def test_validate_gemini_api_key_accepts_aiza_prefix(self) -> None:
        audiobook_maker.validate_gemini_api_key("AIzaSyExampleValidLookingKey")

    def test_validate_gemini_api_key_rejects_project_like_identifier(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "AIza"):
            audiobook_maker.validate_gemini_api_key("gen-lang-client-0222957486")

    def test_gpt4o_payload_includes_instructions(self) -> None:
        payload = audiobook_maker.build_openai_speech_payload(
            text="안녕하세요",
            model="gpt-4o-mini-tts",
            voice="marin",
            response_format="wav",
            speed=1.0,
            instructions="차분한 한국어 오디오북 톤",
        )

        self.assertEqual(payload["voice"], "marin")
        self.assertEqual(payload["response_format"], "wav")
        self.assertEqual(payload["instructions"], "차분한 한국어 오디오북 톤")

    def test_tts1_payload_omits_instructions(self) -> None:
        payload = audiobook_maker.build_openai_speech_payload(
            text="안녕하세요",
            model="tts-1-hd",
            voice="alloy",
            response_format="wav",
            speed=1.0,
            instructions="차분한 한국어 오디오북 톤",
        )

        self.assertNotIn("instructions", payload)


class ChatGPTWorkflowTests(unittest.TestCase):
    def test_chatgpt_default_chunk_size_is_1800(self) -> None:
        self.assertEqual(audiobook_maker.default_max_chars_per_chunk("chatgpt"), 1800)

    def test_chatgpt_prompt_mentions_segment_and_voice(self) -> None:
        prompt = audiobook_maker.build_chatgpt_segment_prompt(
            text="안녕하세요.",
            voice="Spruce",
            mode="advanced_voice",
            instructions="차분하게 읽어줘.",
            index=1,
            total=3,
        )

        self.assertIn("세그먼트 1/3", prompt)
        self.assertIn("선호 음성: Spruce", prompt)
        self.assertIn("안녕하세요.", prompt)

    def test_collect_chatgpt_imported_audio_files_reports_missing_segments(self) -> None:
        sections = [
            audiobook_maker.AudioSection(index=1, title=None, text="첫 문장"),
            audiobook_maker.AudioSection(index=2, title=None, text="둘째 문장"),
        ]

        with TemporaryDirectory() as temp_dir:
            import_dir = Path(temp_dir)
            (import_dir / "001.m4a").write_bytes(b"fake")

            audio_files, missing = audiobook_maker.collect_chatgpt_imported_audio_files(
                sections,
                import_dir=import_dir,
            )

        self.assertEqual(audio_files, [import_dir / "001.m4a"])
        self.assertEqual(missing, [2])


class ChatGPTWebWorkflowTests(unittest.TestCase):
    def test_chatgpt_web_prompt_wraps_text_verbatim(self) -> None:
        prompt = audiobook_maker.build_chatgpt_web_repeat_prompt("안녕하세요.")

        self.assertIn("[본문 시작]", prompt)
        self.assertIn("안녕하세요.", prompt)
        self.assertIn("[본문 끝]", prompt)

    def test_chatgpt_web_launch_args_hide_window_by_default(self) -> None:
        args = audiobook_maker.chatgpt_web_launch_args(visible=False)

        self.assertIn("--window-position=-2400,-2400", args)
        self.assertIn("--window-size=1280,900", args)

    def test_extract_chatgpt_conversation_id(self) -> None:
        conversation_id = audiobook_maker.extract_chatgpt_conversation_id(
            "https://chatgpt.com/c/1234-abcd?model=gpt-4o"
        )

        self.assertEqual(conversation_id, "1234-abcd")

    def test_resolve_voice_normalizes_chatgpt_web_voice(self) -> None:
        args = Namespace(
            voice="Cove",
            provider="chatgpt_web",
            melo_language="KR",
            gemini_voice="",
            openai_model="gpt-4o-mini-tts",
        )

        self.assertEqual(audiobook_maker.resolve_voice(args), "cove")

class AudioFormatTests(unittest.TestCase):
    def test_m4a_uses_aac(self) -> None:
        codec_args = audiobook_maker.ffmpeg_codec_args(Path("book.m4a"), 96)

        self.assertEqual(codec_args, ["-vn", "-c:a", "aac", "-b:a", "96k"])

    def test_concat_line_escapes_single_quotes(self) -> None:
        path = Path("/tmp/it's-book.aiff").resolve()
        line = audiobook_maker.ffmpeg_concat_line(path)

        expected = "file '{}'".format(str(path).replace("'", r"'\''"))
        self.assertEqual(line, expected)


if __name__ == "__main__":
    unittest.main()
