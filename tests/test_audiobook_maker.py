import base64
import json
import signal
import subprocess
import sys
import time
import unittest
import zipfile
import fitz
from argparse import Namespace
from json import loads
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import audiobook_maker


class ChromeDiscoveryTests(unittest.TestCase):
    def test_environment_override_takes_precedence(self) -> None:
        with TemporaryDirectory() as tmpdir:
            executable = Path(tmpdir) / "chrome"
            executable.touch()
            with patch.dict("os.environ", {"AUDIOBOOK_CHROME_PATH": str(executable)}):
                self.assertEqual(audiobook_maker.discover_chrome_executable(), str(executable))

    def test_returns_empty_string_when_chrome_is_unavailable(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with patch("audiobook_maker.Path.is_file", return_value=False):
                with patch("audiobook_maker.shutil.which", return_value=None):
                    self.assertEqual(audiobook_maker.discover_chrome_executable(), "")

    def test_session_probe_rejects_empty_chrome_path(self) -> None:
        with patch("audiobook_maker.load_chatgpt_web_modules") as load_modules:
            self.assertFalse(audiobook_maker.chatgpt_web_session_available(""))
        load_modules.assert_not_called()


class HeadingDetectionTests(unittest.TestCase):
    def test_detects_korean_chapter_heading(self) -> None:
        self.assertTrue(audiobook_maker.looks_like_heading("제1장"))

    def test_rejects_regular_sentence(self) -> None:
        self.assertFalse(audiobook_maker.looks_like_heading("그날 밤은 유난히 조용했다."))

    def test_rejects_answer_marker_line_as_heading(self) -> None:
        self.assertFalse(audiobook_maker.looks_like_heading("● 정답: O"))

    def test_rejects_korean_mixed_ox_title_as_uppercase_heading(self) -> None:
        self.assertFalse(audiobook_maker.looks_like_heading("노동법 OX 통합본"))


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
                text="첫 번째 조각\n\n두 번째 조각",
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

    def test_retry_split_merges_overly_short_exact_copy_fragments(self) -> None:
        text = "1. 사회보장수급권은 정당한 권한이 있는 기관에 서면으로 통지하여 포기할 수 있고, 그 포기는 취소할 수 있다."
        mismatch = audiobook_maker.ChatGPTWebExactCopyMismatchError(
            "응답 텍스트가 입력과 일치하지 않습니다",
            response_text="사회보장수급권은 정당한 권한이 있는",
        )

        with TemporaryDirectory() as tmpdir:
            child_sections = audiobook_maker.build_retry_child_sections(
                Path(tmpdir),
                prefix="004_23",
                text=text,
                last_error=mismatch,
            )

        self.assertEqual(
            [audiobook_maker.normalize_chatgpt_web_copy(section.text) for section in child_sections],
            [
                "1. 사회보장수급권은 정당한 권한이 있는 기관에 서면으로 통지하여",
                "포기할 수 있고, 그 포기는 취소할 수 있다.",
            ],
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

    def test_merge_short_adjacent_audio_sections_groups_small_neighbors(self) -> None:
        sections = [
            audiobook_maker.AudioSection(index=1, title="제1장", text="가" * 120),
            audiobook_maker.AudioSection(index=2, title=None, text="나" * 180),
            audiobook_maker.AudioSection(index=3, title=None, text="다" * 210),
            audiobook_maker.AudioSection(index=4, title=None, text="라" * 220),
        ]

        merged = audiobook_maker.merge_short_adjacent_audio_sections(
            sections,
            min_chars=600,
            max_chars=1800,
        )

        self.assertEqual(len(merged), 1)
        self.assertGreaterEqual(len(merged[0].text), 600)
        self.assertEqual(merged[0].title, "제1장")

    def test_merge_short_adjacent_audio_sections_flushes_before_new_title(self) -> None:
        sections = [
            audiobook_maker.AudioSection(index=1, title="제1장", text="가" * 350),
            audiobook_maker.AudioSection(index=2, title="제2장", text="나" * 350),
        ]

        merged = audiobook_maker.merge_short_adjacent_audio_sections(
            sections,
            min_chars=600,
            max_chars=1800,
        )

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].title, "제1장")
        self.assertEqual(merged[1].title, "제2장")

    def test_merge_short_adjacent_audio_sections_waits_for_word_minimum(self) -> None:
        def words(start: int, count: int) -> str:
            return " ".join(f"단어{n}" for n in range(start, start + count))

        sections = [
            audiobook_maker.AudioSection(index=1, title=None, text=words(1, 120)),
            audiobook_maker.AudioSection(index=2, title=None, text=words(121, 120)),
            audiobook_maker.AudioSection(index=3, title=None, text=words(241, 120)),
            audiobook_maker.AudioSection(index=4, title=None, text=words(361, 120)),
            audiobook_maker.AudioSection(index=5, title=None, text=words(481, 120)),
        ]

        merged = audiobook_maker.merge_short_adjacent_audio_sections(
            sections,
            min_chars=30,
            max_chars=3000,
        )

        self.assertEqual(len(merged), 1)
        self.assertGreaterEqual(audiobook_maker.count_text_words(merged[0].text), 600)

    def test_merge_retry_breath_sections_waits_for_word_minimum(self) -> None:
        def words(start: int, count: int) -> str:
            return " ".join(f"단어{n}" for n in range(start, start + count))

        sections = [
            audiobook_maker.AudioSection(index=1, title=None, text=words(1, 120)),
            audiobook_maker.AudioSection(index=2, title=None, text=words(121, 120)),
            audiobook_maker.AudioSection(index=3, title=None, text=words(241, 120)),
            audiobook_maker.AudioSection(index=4, title=None, text=words(361, 120)),
            audiobook_maker.AudioSection(index=5, title=None, text=words(481, 120)),
        ]

        merged = audiobook_maker.merge_retry_breath_sections(
            sections,
            min_chars=30,
        )

        self.assertEqual(len(merged), 1)
        self.assertGreaterEqual(audiobook_maker.count_text_words(merged[0].text), 600)

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

    def test_policy_refusal_detector_accepts_safety_reasons_model_spec_message(self) -> None:
        response = (
            "This content can’t be shown for safety reasons "
            "Learn more about our intended model behavior in our Model Spec."
        )

        self.assertTrue(audiobook_maker.is_chatgpt_web_refusal_response(response))

    def test_policy_refusal_detector_accepts_korean_localized_safety_reasons_message(self) -> None:
        # Found live: the browser launches with --lang=ko, so ChatGPT's web UI shows this same
        # safety banner in Korean instead of English. Only the English wording was in
        # CHATGPT_WEB_REFUSAL_MARKERS, so this landed in chunk_0001_response.txt unrecognized as
        # a refusal - it just kept retrying the same way forever without ever switching to the
        # literary-context retry prompt built for exactly this situation.
        response = (
            "안전상의 이유로 이 콘텐츠를 표시할 수 없습니다 "
            "의도된 모델 동작에 대한 자세한 내용은 모델 사양에서 확인하세요."
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

    def test_default_output_path_uses_study_suffix_in_study_mode(self) -> None:
        args = Namespace(
            output_file=None,
            input_file=Path("/tmp/source.epub"),
            audiobook_mode="study",
        )

        output_path = audiobook_maker.default_output_path(args)

        self.assertEqual(output_path, Path("/tmp/audiobooks/source_study_audiobook.m4a"))

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
        self.assertEqual(audiobook_maker.default_max_chars_per_chunk("gemini_web"), 1600)
        self.assertEqual(audiobook_maker.default_max_chars_per_chunk("gemini_api_tts"), 2500)
        self.assertEqual(audiobook_maker.default_max_chars_per_chunk("unused"), 1800)


class VoiceSelectionTests(unittest.TestCase):
    def test_default_chatgpt_web_voice_is_cove(self) -> None:
        self.assertEqual(audiobook_maker.default_chatgpt_web_voice(), "cove")

    def test_default_gemini_web_voice_is_account_default(self) -> None:
        self.assertEqual(audiobook_maker.default_gemini_web_voice(), "account_default")

    def test_default_gemini_api_tts_voice_is_sulafat(self) -> None:
        self.assertEqual(audiobook_maker.default_gemini_api_tts_voice(), "Sulafat")

    def test_resolve_voice_defaults_chatgpt_web_voice(self) -> None:
        args = Namespace(voice=None, provider="chatgpt_web")

        self.assertEqual(audiobook_maker.resolve_voice(args), "cove")

    def test_resolve_voice_defaults_gemini_web_voice(self) -> None:
        args = Namespace(voice=None, provider="gemini_web")

        self.assertEqual(audiobook_maker.resolve_voice(args), "account_default")

    def test_resolve_voice_defaults_gemini_api_tts_voice(self) -> None:
        args = Namespace(voice=None, provider="gemini_api_tts")

        self.assertEqual(audiobook_maker.resolve_voice(args), "Sulafat")

    def test_resolve_voice_normalizes_chatgpt_web_voice(self) -> None:
        args = Namespace(
            voice="Cove",
            provider="chatgpt_web",
        )

        self.assertEqual(audiobook_maker.resolve_voice(args), "cove")

    def test_resolve_voice_normalizes_gemini_api_tts_voice(self) -> None:
        args = Namespace(
            voice="sulafat",
            provider="gemini_api_tts",
        )

        self.assertEqual(audiobook_maker.resolve_voice(args), "Sulafat")


class GeminiWebNoticeTests(unittest.TestCase):
    def test_classifies_gemini_usage_limit(self) -> None:
        notice = audiobook_maker.classify_gemini_web_notice_text(
            "You've reached your limit on Gemini Pro. Come back at 11:00 PM."
        )

        self.assertIsNotNone(notice)
        self.assertEqual(notice.kind, "usage_limit")
        self.assertEqual(notice.action, "wait_for_limit_refresh")

    def test_classifies_gemini_temporary_service_error(self) -> None:
        notice = audiobook_maker.classify_gemini_web_notice_text(
            "Something went wrong. Please try again later."
        )

        self.assertIsNotNone(notice)
        self.assertEqual(notice.kind, "temporary_service_error")

    def test_classifies_gemini_session_and_prompt_errors(self) -> None:
        session = audiobook_maker.classify_gemini_web_notice_text(
            "Your session has expired. Please sign in again."
        )
        prompt = audiobook_maker.classify_gemini_web_notice_text(
            "Your prompt is too long. Please try a shorter message."
        )

        self.assertEqual(session.kind, "session_expired")
        self.assertEqual(prompt.kind, "prompt_too_long")

    def test_classifies_gemini_account_and_region_errors(self) -> None:
        account = audiobook_maker.classify_gemini_web_notice_text(
            "Gemini isn't available for this account."
        )
        region = audiobook_maker.classify_gemini_web_notice_text(
            "Gemini isn't currently supported in your country."
        )

        self.assertEqual(account.kind, "account_unavailable")
        self.assertEqual(region.kind, "region_unavailable")


class GeminiApiTtsModelTests(unittest.TestCase):
    def test_normalize_gemini_api_tts_model_defaults_to_flash_preview(self) -> None:
        self.assertEqual(
            audiobook_maker.normalize_gemini_api_tts_model_name(""),
            "gemini-2.5-flash-preview-tts",
        )

    def test_normalize_gemini_api_tts_model_aliases_flash_name(self) -> None:
        self.assertEqual(
            audiobook_maker.normalize_gemini_api_tts_model_name("gemini-2.5-flash-tts"),
            "gemini-2.5-flash-preview-tts",
        )

    def test_normalize_gemini_api_tts_model_aliases_pro_name(self) -> None:
        self.assertEqual(
            audiobook_maker.normalize_gemini_api_tts_model_name("gemini-2.5-pro-tts"),
            "gemini-2.5-pro-preview-tts",
        )


class GeminiApiTtsRateLimitTests(unittest.TestCase):
    def test_extract_retry_after_seconds_from_text_parses_retry_hint(self) -> None:
        actual = audiobook_maker.extract_retry_after_seconds_from_text("Please retry in 39.174204654s.")

        self.assertEqual(actual, 40.174204654)

    def test_extract_retry_after_seconds_from_text_returns_none_without_hint(self) -> None:
        self.assertIsNone(audiobook_maker.extract_retry_after_seconds_from_text("HTTP 429"))


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

    def test_chatgpt_web_study_prompt_includes_summary_and_transition_guidance(self) -> None:
        section = audiobook_maker.AudioSection(
            index=1,
            title="1. 헌법 · 연혁",
            text="헌법 제32조와 주요 연혁을 정리한다.",
            next_title="2. 근로기준법 총론",
            chapter_index=1,
        )

        prompt = audiobook_maker.build_chatgpt_web_study_prompt(section)

        self.assertIn("암기 포인트", prompt)
        self.assertIn("1. 헌법 · 연혁", prompt)
        self.assertIn("2. 근로기준법 총론", prompt)

    def test_gemini_web_prompt_includes_default_reading_instructions(self) -> None:
        prompt = audiobook_maker.build_gemini_web_repeat_prompt("안녕하세요.")

        self.assertIn("추가 참고 지침", prompt)
        self.assertIn("한국어 원어민 전문 성우", prompt)
        self.assertIn("안녕하세요.", prompt)

    def test_gemini_api_tts_prompt_includes_transcript_and_direction(self) -> None:
        prompt = audiobook_maker.build_gemini_api_tts_prompt("안녕하세요.")

        self.assertIn("# AUDIO PROFILE", prompt)
        self.assertIn("# TRANSCRIPT", prompt)
        self.assertIn("반드시 아래 TRANSCRIPT만 읽고", prompt)
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

    def test_classify_chatgpt_web_notice_text_detects_rate_limit_notice(self) -> None:
        notice = audiobook_maker.classify_chatgpt_web_notice_text(
            "요청을 너무 빠르게 보내고 있습니다. 데이터를 보호하기 위해 대화 액세스가 일시적으로 제한되었습니다."
        )

        self.assertEqual(
            notice,
            audiobook_maker.ChatGPTWebNotice(
                kind="conversation_rate_limit",
                action="reset_chat",
                message=audiobook_maker.normalize_chatgpt_web_copy(
                    "요청을 너무 빠르게 보내고 있습니다. 데이터를 보호하기 위해 대화 액세스가 일시적으로 제한되었습니다."
                ),
            ),
        )

    def test_classify_chatgpt_web_notice_text_detects_speed_only_rate_limit_notice(self) -> None:
        notice = audiobook_maker.classify_chatgpt_web_notice_text(
            "요청을 너무 빠르게 보내고 있습니다. 몇 분 후 다시 시도해 주세요."
        )

        self.assertEqual(
            notice,
            audiobook_maker.ChatGPTWebNotice(
                kind="rate_limit",
                action="wait",
                message=audiobook_maker.normalize_chatgpt_web_copy(
                    "요청을 너무 빠르게 보내고 있습니다. 몇 분 후 다시 시도해 주세요."
                ),
            ),
        )

    def test_chatgpt_rate_limit_cooldown_is_persisted_per_profile(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"AUDIOBOOK_WEB_PROFILE_DIR": temp_dir}):
                state = audiobook_maker.record_chatgpt_web_rate_limit(
                    "요청을 너무 빠르게 보내고 있습니다.",
                    cooldown_sec=1200,
                    now=1000,
                )
                audiobook_maker.mark_chatgpt_web_rate_limit_recovery_attempted()
                loaded = audiobook_maker.load_chatgpt_web_rate_limit_state()

        self.assertEqual(state["blocked_until"], 2200)
        self.assertEqual(loaded["blocked_until"], 2200)
        self.assertTrue(loaded["recovery_attempted"])
        self.assertEqual(loaded["kind"], "conversation_rate_limit")

    def test_chatgpt_request_pacing_persists_a_five_minute_send_interval(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "AUDIOBOOK_WEB_PROFILE_DIR": temp_dir,
                    "AUDIOBOOK_CHATGPT_MIN_REQUEST_INTERVAL_SEC": "300",
                },
            ):
                first_reserved, first_wait, _state = (
                    audiobook_maker.reserve_chatgpt_web_request_slot(now=1000)
                )
                second_reserved, second_wait, _state = (
                    audiobook_maker.reserve_chatgpt_web_request_slot(now=1100)
                )
                third_reserved, third_wait, loaded = (
                    audiobook_maker.reserve_chatgpt_web_request_slot(now=1300)
                )

        self.assertTrue(first_reserved)
        self.assertEqual(first_wait, 0)
        self.assertFalse(second_reserved)
        self.assertEqual(second_wait, 200)
        self.assertTrue(third_reserved)
        self.assertEqual(third_wait, 0)
        self.assertEqual(loaded["last_send_at"], 1300)

    def test_chatgpt_rate_limit_enables_adaptive_pacing_after_cooldown(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "AUDIOBOOK_WEB_PROFILE_DIR": temp_dir,
                    "AUDIOBOOK_CHATGPT_MIN_REQUEST_INTERVAL_SEC": "300",
                    "AUDIOBOOK_CHATGPT_PENALTY_REQUEST_INTERVAL_SEC": "450",
                    "AUDIOBOOK_CHATGPT_PACING_ESCALATION_SEC": "150",
                },
            ):
                audiobook_maker.record_chatgpt_web_rate_limit(
                    "요청을 너무 빠르게 보내고 있습니다.",
                    cooldown_sec=1200,
                    now=1000,
                )
                during_cooldown = audiobook_maker.reserve_chatgpt_web_request_slot(now=1500)
                after_cooldown = audiobook_maker.reserve_chatgpt_web_request_slot(now=2200)
                too_soon = audiobook_maker.reserve_chatgpt_web_request_slot(now=2300)

        self.assertFalse(during_cooldown[0])
        self.assertEqual(during_cooldown[1], 700)
        self.assertTrue(after_cooldown[0])
        self.assertFalse(too_soon[0])
        self.assertEqual(too_soon[1], 350)
        self.assertEqual(after_cooldown[2]["last_interval_seconds"], 450)

    def test_repeated_chatgpt_rate_limit_escalates_the_pacing_interval(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "AUDIOBOOK_WEB_PROFILE_DIR": temp_dir,
                    "AUDIOBOOK_CHATGPT_PENALTY_REQUEST_INTERVAL_SEC": "450",
                    "AUDIOBOOK_CHATGPT_PACING_ESCALATION_SEC": "150",
                    # 이 테스트는 에스컬레이션 산식(penalty + escalation*(n-1))만 검증하는
                    # 것이므로, 운영 기본 상한(CHATGPT_WEB_PACING_MAX_INTERVAL_SEC)이 바뀌어도
                    # 영향받지 않도록 상한을 직접 명시한다.
                    "AUDIOBOOK_CHATGPT_MAX_REQUEST_INTERVAL_SEC": "900",
                },
            ):
                audiobook_maker.record_chatgpt_web_pacing_incident(
                    detected_at=1000,
                    blocked_until=2200,
                )
                state = audiobook_maker.record_chatgpt_web_pacing_incident(
                    detected_at=1600,
                    blocked_until=2800,
                )
                interval, incidents, _penalty_until = (
                    audiobook_maker.chatgpt_web_pacing_interval(state, now=2000)
                )

        self.assertEqual(len(incidents), 2)
        self.assertEqual(interval, 600)

    def test_chatgpt_pacing_ignores_incidents_from_another_workflow_scope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "AUDIOBOOK_WEB_PROFILE_DIR": temp_dir,
                    "AUDIOBOOK_CHATGPT_PACING_SCOPE": "general_translation",
                    "AUDIOBOOK_CHATGPT_MIN_REQUEST_INTERVAL_SEC": "300",
                },
            ):
                audiobook_maker.record_chatgpt_web_pacing_incident(
                    detected_at=1000,
                    blocked_until=1000,
                    scope="legacy_backfill",
                )
                state = audiobook_maker.load_chatgpt_web_pacing_state()
                interval, incidents, _penalty_until = (
                    audiobook_maker.chatgpt_web_pacing_interval(state, now=1100)
                )

        self.assertEqual(incidents, [])
        self.assertEqual(interval, 300)

    def test_reobserved_chatgpt_modal_stays_one_rate_limit_episode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"AUDIOBOOK_WEB_PROFILE_DIR": temp_dir}):
                audiobook_maker.record_chatgpt_web_rate_limit(
                    "요청을 너무 빠르게 보내고 있습니다.",
                    cooldown_sec=1200,
                    now=1000,
                )
                state = audiobook_maker.record_chatgpt_web_rate_limit(
                    "요청을 너무 빠르게 보내고 있습니다.",
                    cooldown_sec=1200,
                    now=2100,
                )
                pacing = audiobook_maker.load_chatgpt_web_pacing_state()
                _interval, incidents, _penalty_until = (
                    audiobook_maker.chatgpt_web_pacing_interval(pacing, now=2100)
                )

        self.assertEqual(state["episode_started_at"], 1000)
        self.assertEqual(state["blocked_until"], 2280)
        self.assertEqual(state["observation_count"], 2)
        self.assertEqual(len(incidents), 1)

    def test_expired_chatgpt_rate_limit_is_not_active(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"AUDIOBOOK_WEB_PROFILE_DIR": temp_dir}):
                audiobook_maker.record_chatgpt_web_rate_limit(
                    "요청을 너무 빠르게 보내고 있습니다.",
                    cooldown_sec=1200,
                    now=1000,
                )
                active = audiobook_maker.active_chatgpt_web_rate_limit_state(now=1500)
                expired = audiobook_maker.active_chatgpt_web_rate_limit_state(now=2200)

        self.assertTrue(active)
        self.assertEqual(expired, {})

    def test_chatgpt_pacing_returns_to_base_after_three_successes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "AUDIOBOOK_WEB_PROFILE_DIR": temp_dir,
                    "AUDIOBOOK_CHATGPT_PACING_SCOPE": "general_translation",
                    "AUDIOBOOK_CHATGPT_MIN_REQUEST_INTERVAL_SEC": "300",
                    "AUDIOBOOK_CHATGPT_PENALTY_REQUEST_INTERVAL_SEC": "450",
                },
            ):
                audiobook_maker.record_chatgpt_web_pacing_incident(
                    detected_at=1000,
                    blocked_until=1000,
                )
                audiobook_maker.record_chatgpt_web_pacing_success(completed_at=1100)
                audiobook_maker.record_chatgpt_web_pacing_success(completed_at=1200)
                state = audiobook_maker.record_chatgpt_web_pacing_success(completed_at=1300)
                interval, _incidents, penalty_until = (
                    audiobook_maker.chatgpt_web_pacing_interval(state, now=1300)
                )

        self.assertEqual(interval, 300)
        self.assertEqual(penalty_until, 1300)
        self.assertEqual(state["last_pacing_recovery_scope"], "general_translation")

    def test_chatgpt_page_waits_for_prompt_without_unbounded_notice_scan(self) -> None:
        class PromptLocator:
            @property
            def first(self) -> "PromptLocator":
                return self

            def wait_for(self, **_kwargs: object) -> None:
                return None

        class FakePage:
            url = "https://chatgpt.com/"

            def on(self, _event: str, _handler: object) -> None:
                return None

            def goto(self, *_args: object, **_kwargs: object) -> None:
                return None

            def wait_for_timeout(self, _milliseconds: float) -> None:
                return None

            def locator(self, selector: str) -> PromptLocator:
                if selector != audiobook_maker.CHATGPT_WEB_PROMPT_INPUT_SELECTOR:
                    raise AssertionError(selector)
                return PromptLocator()

        page = FakePage()
        with patch("audiobook_maker.wait_for_recorded_chatgpt_web_rate_limit"):
            with patch("audiobook_maker.verify_chatgpt_web_session"):
                with patch("audiobook_maker.handle_chatgpt_web_page_notices") as notices:
                    audiobook_maker.prepare_chatgpt_web_page(
                        page,
                        timeout_error_cls=TimeoutError,
                    )

        notices.assert_not_called()

    def test_chatgpt_session_verification_accepts_expected_plus_account(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "AUDIOBOOK_WEB_PROFILE_DIR": temp_dir,
                    "AUDIOBOOK_CHATGPT_EXPECTED_ACCOUNT": "haijun93@gmail.com",
                    "AUDIOBOOK_CHATGPT_EXPECTED_TIER": "plus",
                },
            ):
                with patch(
                    "audiobook_maker.inspect_chatgpt_web_session",
                    return_value={
                        "ok": True,
                        "status": 200,
                        "authenticated": True,
                        "email": "haijun93@gmail.com",
                        "tier": "plus",
                    },
                ):
                    health = audiobook_maker.verify_chatgpt_web_session(object())

            persisted = json.loads(
                (Path(temp_dir) / "chatgpt" / ".chatgpt_session_health.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(health["status"], "verified")
        self.assertEqual(persisted["tier"], "plus")

    def test_chatgpt_session_verification_rejects_free_profile_for_plus_account(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "AUDIOBOOK_WEB_PROFILE_DIR": temp_dir,
                    "AUDIOBOOK_CHATGPT_EXPECTED_TIER": "plus",
                },
            ):
                with patch(
                    "audiobook_maker.inspect_chatgpt_web_session",
                    return_value={
                        "ok": True,
                        "status": 200,
                        "authenticated": True,
                        "email": "haijun93@gmail.com",
                        "tier": "free",
                    },
                ):
                    with self.assertRaisesRegex(RuntimeError, "error_kind=account_mismatch"):
                        audiobook_maker.verify_chatgpt_web_session(object())

    def test_chatgpt_session_verification_rejects_expired_session_immediately(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"AUDIOBOOK_WEB_PROFILE_DIR": temp_dir}):
                with patch(
                    "audiobook_maker.inspect_chatgpt_web_session",
                    return_value={"ok": True, "status": 200, "authenticated": False},
                ):
                    with self.assertRaisesRegex(RuntimeError, "error_kind=session_expired"):
                        audiobook_maker.verify_chatgpt_web_session(object())

    def test_unavailable_chatgpt_prompt_does_not_reopen_expired_rate_limit(self) -> None:
        class FakePage:
            url = "https://chatgpt.com/"
            _chatgpt_dialog_messages: list[str] = []

        with patch(
            "audiobook_maker.load_chatgpt_web_rate_limit_state",
            return_value={"detected_at": time.time(), "message": "요청을 너무 빠르게"},
        ):
            with patch("audiobook_maker.record_chatgpt_web_rate_limit") as record_limit:
                with self.assertRaisesRegex(RuntimeError, "error_kind=prompt_interaction_failed"):
                    audiobook_maker.raise_for_unavailable_chatgpt_prompt(FakePage())

        record_limit.assert_not_called()

    def test_chatgpt_prompt_fill_failure_during_active_limit_opens_cooldown(self) -> None:
        class PromptLocator:
            @property
            def first(self) -> "PromptLocator":
                return self

            def fill(self, _prompt: str, **_kwargs: object) -> None:
                raise TimeoutError("prompt fill blocked")

        class FakePage:
            url = "https://chatgpt.com/"

            def locator(self, selector: str) -> PromptLocator:
                if selector != audiobook_maker.CHATGPT_WEB_PROMPT_INPUT_SELECTOR:
                    raise AssertionError(selector)
                return PromptLocator()

        with patch(
            "audiobook_maker.active_chatgpt_web_rate_limit_state",
            return_value={"message": "요청을 너무 빠르게"},
        ):
            with patch("audiobook_maker.wait_for_chatgpt_web_request_slot"):
                with patch("audiobook_maker.record_chatgpt_web_rate_limit") as record_limit:
                    with self.assertRaisesRegex(RuntimeError, "error_kind=rate_limit"):
                        audiobook_maker.send_chatgpt_web_prompt(
                            FakePage(),
                            "prompt",
                            timeout_error_cls=TimeoutError,
                        )

        record_limit.assert_called_once_with("요청을 너무 빠르게")

    def test_chatgpt_prompt_prefers_visible_send_button_over_enter(self) -> None:
        actions: list[str] = []

        class PromptLocator:
            @property
            def first(self) -> "PromptLocator":
                return self

            def fill(self, prompt: str, **_kwargs: object) -> None:
                actions.append(f"fill:{prompt}")

        class ButtonLocator:
            @property
            def first(self) -> "ButtonLocator":
                return self

            def count(self) -> int:
                return 1

            def is_visible(self) -> bool:
                return True

            def is_enabled(self) -> bool:
                return True

            def click(self, **_kwargs: object) -> None:
                actions.append("button")

        class Keyboard:
            def press(self, key: str) -> None:
                actions.append(f"keyboard:{key}")

        class FakePage:
            url = "https://chatgpt.com/c/test"
            keyboard = Keyboard()

            def locator(self, selector: str):
                if selector == audiobook_maker.CHATGPT_WEB_PROMPT_INPUT_SELECTOR:
                    return PromptLocator()
                if selector == 'button[data-testid="send-button"]':
                    return ButtonLocator()
                raise AssertionError(selector)

            def wait_for_url(self, *_args: object, **_kwargs: object) -> None:
                return None

        with patch("audiobook_maker.wait_for_chatgpt_web_request_slot"):
            audiobook_maker.send_chatgpt_web_prompt(
                FakePage(),
                "prompt",
                timeout_error_cls=TimeoutError,
            )

        self.assertEqual(actions, ["fill:prompt", "button"])

    def test_classify_chatgpt_web_notice_text_detects_login_required_notice(self) -> None:
        notice = audiobook_maker.classify_chatgpt_web_notice_text(
            "세션이 만료되었습니다. 다시 로그인해 주세요."
        )

        self.assertEqual(notice.kind, "login_required")
        self.assertEqual(notice.action, "raise")

    def test_classify_chatgpt_web_notice_text_detects_retryable_error_notice(self) -> None:
        notice = audiobook_maker.classify_chatgpt_web_notice_text(
            "Something went wrong while generating the response."
        )

        self.assertEqual(notice.kind, "retryable_error")
        self.assertEqual(notice.action, "retry")

    def test_choose_chatgpt_web_notice_prioritizes_login_over_retryable_error(self) -> None:
        notice = audiobook_maker.choose_chatgpt_web_notice(
            [
                "Something went wrong while generating the response.",
                "세션이 만료되었습니다. 다시 로그인해 주세요.",
            ]
        )

        self.assertEqual(notice.kind, "login_required")

    def test_chatgpt_generation_active_detects_stop_button(self) -> None:
        class FakeLocator:
            def __init__(self, visible: bool) -> None:
                self.visible = visible

            @property
            def first(self):
                return self

            def count(self) -> int:
                return 1 if self.visible else 0

            def is_visible(self) -> bool:
                return self.visible

        class FakePage:
            def locator(self, selector: str) -> FakeLocator:
                return FakeLocator(selector == 'button[data-testid="stop-button"]')

        self.assertTrue(audiobook_maker.chatgpt_web_generation_is_active(FakePage()))

    def test_chatgpt_study_note_chunk_allows_slow_response_start(self) -> None:
        self.assertTrue(audiobook_maker.chatgpt_web_request_allows_slow_start("notes_chunk_0029"))
        self.assertTrue(audiobook_maker.chatgpt_web_request_allows_slow_start("chunk_0029"))
        self.assertTrue(audiobook_maker.chatgpt_web_request_allows_slow_start("relationship_guide"))
        self.assertFalse(audiobook_maker.chatgpt_web_request_allows_slow_start("title_translation"))

    def test_progress_heartbeat_observer_failure_does_not_break_work(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "heartbeat.json"

            def fail_observer(_payload: dict[str, object]) -> None:
                raise RuntimeError("diagnostics unavailable")

            heartbeat = audiobook_maker.ProgressHeartbeat(path, observer=fail_observer)
            heartbeat.beat(stage="wait_for_response", detail="still working")

            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["stage"], "wait_for_response")

    def test_chatgpt_service_limit_is_not_treated_as_content_resplit(self) -> None:
        error = RuntimeError(
            "ChatGPT error_kind=rate_limit retry_action=exponential_backoff: try again later"
        )

        self.assertTrue(audiobook_maker.is_chatgpt_web_pause_error(error))
        self.assertFalse(audiobook_maker.should_resplit_chatgpt_web_section(error))

    def test_chatgpt_exact_copy_mismatch_is_content_resplit_candidate(self) -> None:
        mismatch = audiobook_maker.ChatGPTWebExactCopyMismatchError(
            "response differs from input",
            response_text="shortened response",
        )
        wrapped = RuntimeError("ChatGPT web section failed")
        wrapped.__cause__ = mismatch

        self.assertTrue(audiobook_maker.should_resplit_chatgpt_web_section(wrapped))

    def test_read_chatgpt_web_notice_messages_consumes_dialog_messages(self) -> None:
        class MissingLocator:
            @property
            def first(self) -> "MissingLocator":
                return self

            def wait_for(self, **_kwargs: object) -> None:
                raise TimeoutError

        class FakePage:
            def __init__(self) -> None:
                self._chatgpt_dialog_messages = ["요청을 너무 빠르게 보내고 있습니다."]

            def locator(self, _selector: str) -> MissingLocator:
                return MissingLocator()

        page = FakePage()

        first = audiobook_maker.read_chatgpt_web_notice_messages(page)
        second = audiobook_maker.read_chatgpt_web_notice_messages(page)

        self.assertEqual(first, ["요청을 너무 빠르게 보내고 있습니다."])
        self.assertEqual(second, [])

    def test_close_chatgpt_web_notice_ui_uses_dismiss_button_first(self) -> None:
        with patch("audiobook_maker.click_chatgpt_web_notice_button", return_value=True):
            page = Mock()

            closed = audiobook_maker.close_chatgpt_web_notice_ui(page)

        self.assertTrue(closed)
        page.evaluate.assert_not_called()

    def test_chatgpt_web_dismiss_button_labels_include_korean_acknowledge(self) -> None:
        self.assertIn("알겠습니다", audiobook_maker.CHATGPT_WEB_DISMISS_BUTTON_LABELS)

    def test_close_chatgpt_web_notice_ui_uses_dom_modal_button_fallback(self) -> None:
        page = Mock()

        with patch("audiobook_maker.click_chatgpt_web_notice_button", return_value=False):
            with patch(
                "audiobook_maker.click_chatgpt_web_notice_button_via_dom",
                side_effect=[True],
            ) as dom_click:
                closed = audiobook_maker.close_chatgpt_web_notice_ui(page)

        self.assertTrue(closed)
        dom_click.assert_called_once()

    def test_close_chatgpt_web_notice_ui_falls_back_to_escape(self) -> None:
        page = Mock()
        page.evaluate.side_effect = RuntimeError("no dom")
        page.keyboard = Mock()

        with patch("audiobook_maker.click_chatgpt_web_notice_button", return_value=False):
            closed = audiobook_maker.close_chatgpt_web_notice_ui(page)

        self.assertTrue(closed)
        page.keyboard.press.assert_called_once_with("Escape")


class SourceLoadingTests(unittest.TestCase):
    def test_is_low_quality_ox_statement_detects_choice_only_lines(self) -> None:
        self.assertTrue(audiobook_maker.is_low_quality_ox_statement("ㄱ"))
        self.assertTrue(audiobook_maker.is_low_quality_ox_statement("ㄱ, ㄴ"))
        self.assertTrue(audiobook_maker.is_low_quality_ox_statement("①, ③"))
        self.assertFalse(audiobook_maker.is_low_quality_ox_statement("근로조건의 기준은 인간의 존엄성을 보장하도록 법률로 정한다."))

    def test_remove_low_quality_ox_blocks_drops_entire_question_blocks(self) -> None:
        text = (
            "■ 헌법·총론\n"
            "27. ㄱ\n"
            "● 정답: O\n"
            "근거: 대한민국 헌법\n"
            "해설: 정답은 O입니다.\n"
            "출처: 2016 A형 26번\n"
            "28. 제대로 된 문장이다.\n"
            "● 정답: X\n"
            "근거: 대한민국 헌법\n"
            "해설: 기존 해설\n"
            "출처: 2016 A형 27번\n"
        )

        stripped = audiobook_maker.remove_low_quality_ox_blocks(text)

        self.assertNotIn("27. ㄱ", stripped)
        self.assertNotIn("출처: 2016 A형 26번", stripped)
        self.assertIn("28. 제대로 된 문장이다.", stripped)

    def test_build_correct_choice_explanation_map_uses_matching_o_entry(self) -> None:
        entries = [
            {
                "number": 1,
                "year": "2014",
                "question_no": 17,
                "option_no": "1",
                "statement": "문제 [선택지 1: 첫 번째 보기]",
                "answer": "X",
                "source": "2014 A형 17번",
            },
            {
                "number": 2,
                "year": "2014",
                "question_no": 17,
                "option_no": "3",
                "statement": "문제 [선택지 3: 올바른 보기]",
                "answer": "O",
                "source": "2014 A형 17번",
            },
        ]

        explanation_map = audiobook_maker.build_correct_choice_explanation_map(entries)

        self.assertEqual(
            explanation_map["2014 A형 17번"],
            "정답은 X입니다. 이 원문 문제의 정답 선택지는 3번입니다. 올바른 보기.",
        )

    def test_replace_x_explanations_with_correct_answers_rewrites_only_x_entries(self) -> None:
        text = (
            "1. 첫 문제 [선택지 1: 보기]\n"
            "● 정답: X\n"
            "해설: 기존 해설\n"
            "출처: 2014 A형 17번\n"
            "2. 둘째 문제\n"
            "● 정답: O\n"
            "해설: 유지 해설"
        )

        rewritten = audiobook_maker.replace_x_explanations_with_correct_answers(
            text,
            {"2014 A형 17번": "정답은 X입니다. 이 원문 문제의 정답 선택지는 3번입니다. 올바른 보기."},
        )

        self.assertIn(
            "해설: 정답은 X입니다. 이 원문 문제의 정답 선택지는 3번입니다. 올바른 보기.",
            rewritten,
        )
        self.assertIn("해설: 유지 해설", rewritten)

    def test_strip_repetitive_audio_guidance_sentences_removes_requested_sentence(self) -> None:
        text = (
            "해설: 정답은 O입니다. "
            "관련 조문의 정확한 표현과 요건을 법령 원문에서 확인하고 암기하시기 바랍니다. "
            "다음 문장입니다."
        )

        stripped = audiobook_maker.strip_repetitive_audio_guidance_sentences(text)

        self.assertEqual(stripped, "해설: 정답은 O입니다. 다음 문장입니다.")

    def test_strip_repetitive_audio_guidance_sentences_removes_legal_match_sentence(self) -> None:
        text = (
            "해설: 정답은 O입니다. "
            "위 진술은 대한민국 헌법에서 규정하는 내용과 일치합니다. "
            "다음 문장입니다."
        )

        stripped = audiobook_maker.strip_repetitive_audio_guidance_sentences(text)

        self.assertEqual(stripped, "해설: 정답은 O입니다. 다음 문장입니다.")

    def test_strip_repetitive_audio_guidance_sentences_removes_any_matching_law_sentence(self) -> None:
        text = (
            "해설: 정답은 O입니다. "
            "위 진술은 노동조합 및 노동관계조정법에서 규정하는 내용과 일치합니다. "
            "다음 문장입니다."
        )

        stripped = audiobook_maker.strip_repetitive_audio_guidance_sentences(text)

        self.assertEqual(stripped, "해설: 정답은 O입니다. 다음 문장입니다.")

    def test_strip_repetitive_audio_guidance_sentences_removes_ox_answer_sheet_phrase(self) -> None:
        text = (
            "머리말입니다. "
            "OX 정답표 구간 정답 최종 정오표 항목 최종 확인 "
            "다음 문장입니다."
        )

        stripped = audiobook_maker.strip_repetitive_audio_guidance_sentences(text)

        self.assertEqual(stripped, "머리말입니다. 다음 문장입니다.")

    def test_strip_repetitive_audio_guidance_sentences_removes_nine_answer_pattern_phrase(self) -> None:
        text = (
            "머리말입니다. "
            "정답표 · 최종 정오표 정답은 9개씩 묶어서 확인하면 오답 패턴이 더 잘 보인다. "
            "다음 문장입니다."
        )

        stripped = audiobook_maker.strip_repetitive_audio_guidance_sentences(text)

        self.assertEqual(stripped, "머리말입니다. 다음 문장입니다.")

    def test_strip_audio_source_lines_removes_source_paragraphs(self) -> None:
        text = (
            "1. 첫 문제\n\n"
            "정답: O\n\n"
            "출처: 2014 A형 14번\n\n"
            "2. 둘째 문제"
        )

        stripped = audiobook_maker.strip_audio_source_lines(text)

        self.assertEqual(stripped, "1. 첫 문제\n\n정답: O\n\n2. 둘째 문제")

    def test_strip_audio_source_lines_keeps_non_source_mentions(self) -> None:
        text = "해설: 판례의 출처를 함께 검토한다."

        stripped = audiobook_maker.strip_audio_source_lines(text)

        self.assertEqual(stripped, audiobook_maker.normalize_text(text))

    def test_strip_ox_answer_checklist_lines_removes_dense_answer_summary(self) -> None:
        text = (
            "10. X 11. O 12. O 13. X 14. O 15. O 16. X 17. O 18. O\n\n"
            "다음 문제 본문"
        )

        stripped = audiobook_maker.strip_ox_answer_checklist_lines(text)

        self.assertEqual(stripped, "다음 문제 본문")

    def test_strip_ox_answer_checklist_lines_removes_grouped_answer_summary_with_ranges(self) -> None:
        text = (
            "19~27 19. X 20. X 21. O 22. X 23. O 24. O 25. O 26. X 27. O "
            "28~36 28. O 29. X 30. X 31. O 32. O 33. O 34. O 35. O 36. X\n\n"
            "다음 본문"
        )

        stripped = audiobook_maker.strip_ox_answer_checklist_lines(text)

        self.assertEqual(stripped, "다음 본문")

    def test_strip_ox_answer_checklist_lines_keeps_single_answer_statement(self) -> None:
        text = "10. X가 정답이라는 설명은 뒤 문단에서 다룬다."

        stripped = audiobook_maker.strip_ox_answer_checklist_lines(text)

        self.assertEqual(stripped, text)

    def test_strip_ox_answer_checklist_lines_removes_range_only_lines(self) -> None:
        text = "19~27\n28~36\n\n다음 본문"

        stripped = audiobook_maker.strip_ox_answer_checklist_lines(text)

        self.assertEqual(stripped, "다음 본문")

    def test_strip_non_learning_ascii_lines_removes_url_and_domain_lines(self) -> None:
        text = (
            "https://www.law.go.kr/lsLinkProc.do?foo=bar\n"
            "www.openai.com/docs\n"
            "남는 본문"
        )

        stripped = audiobook_maker.strip_non_learning_ascii_lines(text)

        self.assertEqual(stripped, "남는 본문")

    def test_strip_non_learning_ascii_lines_removes_long_pure_english_sentence(self) -> None:
        text = (
            "OpenAI API quickstart guide for speech synthesis and browser automation\n\n"
            "다음 본문"
        )

        stripped = audiobook_maker.strip_non_learning_ascii_lines(text)

        self.assertEqual(stripped, "다음 본문")

    def test_strip_non_learning_ascii_lines_keeps_short_study_terms(self) -> None:
        text = "SWOT\nBCG matrix\nERP\n본문"

        stripped = audiobook_maker.strip_non_learning_ascii_lines(text)

        self.assertEqual(stripped, audiobook_maker.normalize_text(text))

    def test_strip_trailing_official_law_reference_section_removes_reference_appendix(self) -> None:
        text = (
            "458. 마지막 문제\n\n"
            "정답: O\n\n"
            "5. 공식 법령 확인 경로\n\n"
            "사회보장기본법\n"
            "https://www.law.go.kr/lsLinkProc.do?foo=bar\n"
        )

        stripped = audiobook_maker.strip_trailing_official_law_reference_section(text)

        self.assertEqual(stripped, "458. 마지막 문제\n\n정답: O")

    def test_strip_trailing_official_law_reference_section_keeps_regular_mid_document_heading(self) -> None:
        text = (
            "1. 공식 법령 확인 경로\n\n"
            "이 부분은 본문 중간 안내일 뿐입니다.\n\n"
            "마지막 문단"
        )

        stripped = audiobook_maker.strip_trailing_official_law_reference_section(text)

        self.assertEqual(stripped, audiobook_maker.normalize_text(text))

    def create_sample_epub(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
            )
            archive.writestr(
                "EPUB/content.opf",
                """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ch1" href="text/ch001.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="text/ch002.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="nav"/>
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
  </spine>
</package>
""",
            )
            archive.writestr(
                "EPUB/nav.xhtml",
                """<html xmlns="http://www.w3.org/1999/xhtml"><body><nav><ol><li>목차</li></ol></nav></body></html>""",
            )
            archive.writestr(
                "EPUB/text/ch001.xhtml",
                """<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>1. 헌법</h1><p>근로의 권리를 정리한다.</p></body></html>""",
            )
            archive.writestr(
                "EPUB/text/ch002.xhtml",
                """<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>2. 근로기준법</h1><ul><li>근로조건</li><li>해고 제한</li></ul></body></html>""",
            )

    def create_sample_docx(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
            )
            archive.writestr(
                "_rels/.rels",
                """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
            )
            archive.writestr(
                "word/document.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>노동법 핵심 체계 정리</w:t></w:r></w:p>
    <w:p><w:r><w:t>공인노무사 1차</w:t></w:r></w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="1"/></w:pPr>
      <w:r><w:t>1. 헌법 · 연혁</w:t></w:r>
    </w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="2"/></w:pPr>
      <w:r><w:t>1-1. 헌법 제32조 핵심</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>근로권과 적정임금 보장을 정리한다.</w:t></w:r></w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="1"/></w:pPr>
      <w:r><w:t>2. 임금</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>통상임금과 평균임금을 비교한다.</w:t></w:r></w:p>
  </w:body>
</w:document>
""",
            )

    def create_sample_pdf(self, path: Path) -> None:
        document = fitz.open()

        intro_page = document.new_page()
        intro_page.insert_text((72, 72), "Labor Law Notes")
        intro_page.insert_text((72, 100), "Core precedents")
        intro_page.insert_text((72, 128), "Contents")
        intro_page.insert_text((72, 790), "1")

        section_page = document.new_page()
        section_page.insert_text((72, 72), "S E C T I O N")
        section_page.insert_text((72, 100), "General")
        section_page.insert_text((72, 124), "2 cases")
        section_page.insert_text((72, 170), "No.001")
        section_page.insert_text((72, 194), "Customary practice")
        section_page.insert_text((72, 218), "Mnemonic")
        section_page.insert_text((72, 242), "[sample cue]")
        section_page.insert_text((72, 266), "Holding")
        section_page.insert_text((72, 290), "Internal practice can become part of a labor contract.")
        section_page.insert_text((72, 790), "2")

        next_page = document.new_page()
        next_page.insert_text((72, 72), "No.002")
        next_page.insert_text((72, 100), "Favorability principle")
        next_page.insert_text((72, 128), "Key point")
        next_page.insert_text((72, 156), "A revised CBA includes priority application of the revised terms.")
        next_page.insert_text((72, 790), "3")

        another_section = document.new_page()
        another_section.insert_text((72, 72), "S E C T I O N")
        another_section.insert_text((72, 100), "Wages")
        another_section.insert_text((72, 124), "1 case")
        another_section.insert_text((72, 170), "No.003")
        another_section.insert_text((72, 194), "Wage criteria")
        another_section.insert_text((72, 218), "Money paid regularly in return for work.")
        another_section.insert_text((72, 790), "4")

        document.save(path)
        document.close()

    def test_load_epub_chapters_reads_spine_order_and_titles(self) -> None:
        with TemporaryDirectory() as tmpdir:
            epub_path = Path(tmpdir) / "sample.epub"
            self.create_sample_epub(epub_path)

            chapters = audiobook_maker.load_epub_chapters(epub_path)

        self.assertEqual([chapter.title for chapter in chapters], ["1. 헌법", "2. 근로기준법"])
        self.assertEqual(chapters[0].text, "근로의 권리를 정리한다.")
        self.assertIn("근로조건", chapters[1].text)
        self.assertIn("해고 제한", chapters[1].text)

    def test_input_file_format_detects_docx(self) -> None:
        self.assertEqual(audiobook_maker.input_file_format(Path("/tmp/sample.docx")), "docx")

    def test_input_file_format_detects_pdf(self) -> None:
        self.assertEqual(audiobook_maker.input_file_format(Path("/tmp/sample.pdf")), "pdf")

    def test_load_docx_chapters_uses_heading_1_as_chapter_boundary(self) -> None:
        with TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            self.create_sample_docx(docx_path)

            chapters = audiobook_maker.load_docx_chapters(docx_path)

        self.assertEqual([chapter.title for chapter in chapters], ["1. 헌법 · 연혁", "2. 임금"])
        self.assertIn("노동법 핵심 체계 정리", chapters[0].text)
        self.assertIn("1-1. 헌법 제32조 핵심", chapters[0].text)
        self.assertIn("통상임금과 평균임금을 비교한다.", chapters[1].text)

    def test_load_docx_chapters_accepts_heading1_style_id(self) -> None:
        with TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample_heading1.docx"
            with zipfile.ZipFile(docx_path, "w") as archive:
                archive.writestr(
                    "[Content_Types].xml",
                    """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
                )
                archive.writestr(
                    "_rels/.rels",
                    """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
                )
                archive.writestr(
                    "word/document.xml",
                    """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>1. 총론</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>첫 장 내용</w:t></w:r></w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>2. 각론</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>둘째 장 내용</w:t></w:r></w:p>
  </w:body>
</w:document>
""",
                )

            chapters = audiobook_maker.load_docx_chapters(docx_path)

        self.assertEqual([chapter.title for chapter in chapters], ["1. 총론", "2. 각론"])

    def test_load_docx_text_preserves_paragraph_order(self) -> None:
        with TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "sample.docx"
            self.create_sample_docx(docx_path)

            text = audiobook_maker.load_docx_text(docx_path)

        self.assertIn("노동법 핵심 체계 정리", text)
        self.assertIn("1. 헌법 · 연혁", text)
        self.assertIn("2. 임금", text)

    def test_load_pdf_chapters_groups_pages_by_section_marker(self) -> None:
        with TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "sample.pdf"
            self.create_sample_pdf(pdf_path)

            chapters = audiobook_maker.load_pdf_chapters(pdf_path)

        self.assertEqual([chapter.title for chapter in chapters], ["General", "Wages"])
        self.assertIn("Labor Law Notes", chapters[0].text)
        self.assertIn("Contents", chapters[0].text)
        self.assertIn("No.001", chapters[0].text)
        self.assertIn("No.002", chapters[0].text)
        self.assertNotIn("\n2\n", f"\n{chapters[0].text}\n")
        self.assertIn("No.003", chapters[1].text)

    def test_load_pdf_text_omits_page_number_blocks(self) -> None:
        with TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "sample.pdf"
            self.create_sample_pdf(pdf_path)

            text = audiobook_maker.load_pdf_text(pdf_path)

        self.assertIn("Labor Law Notes", text)
        self.assertIn("Favorability principle", text)
        self.assertNotIn("\n1\n", f"\n{text}\n")

    def test_looks_like_docx_top_level_heading_accepts_numbered_title(self) -> None:
        self.assertTrue(audiobook_maker.looks_like_docx_top_level_heading("1. 헌법 · 연혁"))
        self.assertFalse(audiobook_maker.looks_like_docx_top_level_heading("1-1. 헌법 제32조 핵심"))

    def test_build_study_audio_sections_sets_next_title(self) -> None:
        chapters = [
            audiobook_maker.SourceChapter(index=1, title="1장", text="첫 장 내용"),
            audiobook_maker.SourceChapter(index=2, title="2장", text="둘째 장 내용"),
        ]

        sections = audiobook_maker.build_study_audio_sections(chapters, max_source_chars=3500)

        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0].next_title, "2장")
        self.assertIsNone(sections[1].next_title)

    def test_merge_short_adjacent_chapters_combines_neighboring_short_chapters(self) -> None:
        chapters = [
            audiobook_maker.SourceChapter(index=1, title="1장", text="가" * 900),
            audiobook_maker.SourceChapter(index=2, title="2장", text="나" * 120),
            audiobook_maker.SourceChapter(index=3, title="3장", text="다" * 180),
            audiobook_maker.SourceChapter(index=4, title="4장", text="라" * 950),
            audiobook_maker.SourceChapter(index=5, title="5장", text="마" * 80),
        ]

        merged = audiobook_maker.merge_short_adjacent_chapters(chapters, min_chars=300)

        self.assertEqual([chapter.title for chapter in merged], ["1장", "2장", "4장"])
        self.assertEqual(len(merged), 3)
        self.assertIn("2장", merged[1].text)
        self.assertIn("3장", merged[1].text)
        self.assertIn("5장", merged[2].text)


class ClearCrashedProfileFlagTests(unittest.TestCase):
    # job_manager.stop_job() sends SIGTERM to the whole process group (Python + Chrome +
    # Playwright's Node driver) at once, so Chrome doesn't get a chance to record a clean exit
    # in its own Preferences before it dies - the next launch inherits exit_type=Crashed, which
    # can trigger crash-recovery UI that interferes with Playwright's own page setup and causes
    # that run to fail too, staying Crashed and repeating. Found live: after stopping a batch
    # job normally (not even a forceful kill), every subsequent launch attempt on that profile
    # failed with TargetClosedError until the Preferences flag was fixed by hand.

    def _write_preferences(self, profile_dir: Path, exit_type: str, exited_cleanly) -> Path:
        default_dir = profile_dir / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)
        prefs_path = default_dir / "Preferences"
        prefs_path.write_text(
            json.dumps({"profile": {"exit_type": exit_type, "exited_cleanly": exited_cleanly}, "other": {"untouched": True}}),
            encoding="utf-8",
        )
        return prefs_path

    def test_noop_when_no_preferences_file_exists(self) -> None:
        with TemporaryDirectory() as tmpdir:
            audiobook_maker.clear_crashed_profile_flag(Path(tmpdir))  # must not raise

    def test_resets_crashed_exit_type_to_normal(self) -> None:
        with TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir)
            prefs_path = self._write_preferences(profile_dir, "Crashed", False)

            audiobook_maker.clear_crashed_profile_flag(profile_dir)

            data = json.loads(prefs_path.read_text(encoding="utf-8"))
            self.assertEqual(data["profile"]["exit_type"], "Normal")
            self.assertTrue(data["profile"]["exited_cleanly"])
            self.assertTrue(data["other"]["untouched"])  # rest of the file preserved

    def test_leaves_an_already_normal_profile_untouched(self) -> None:
        with TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir)
            prefs_path = self._write_preferences(profile_dir, "Normal", True)
            original_mtime = prefs_path.stat().st_mtime_ns

            audiobook_maker.clear_crashed_profile_flag(profile_dir)

            self.assertEqual(prefs_path.stat().st_mtime_ns, original_mtime)


class ClearStaleSingletonLockTests(unittest.TestCase):
    # Found live: a translation subprocess's Chrome can outlive its own process (context.close()
    # doesn't always fully tear it down before Python exits) and its SingletonLock then blocks
    # every subsequent launch attempt against the same profile with "Failed to create a
    # ProcessSingleton..." - Playwright's own recovery kill fails with "kill EPERM" in this
    # environment, so nothing clears it automatically. This caused a full book-attempt failure
    # ("Words of Radiance") after burning all 5 retries on this error alone.

    def test_noop_when_no_lock_file_exists(self) -> None:
        with TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir)
            audiobook_maker.clear_stale_singleton_lock(profile_dir)  # must not raise

    def test_cleans_up_lock_pointing_at_a_dead_pid(self) -> None:
        with TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir)
            proc = subprocess.Popen(["true"])
            proc.wait()
            dead_pid = proc.pid
            (profile_dir / "SingletonLock").symlink_to(f"somehost-{dead_pid}")
            (profile_dir / "SingletonCookie").symlink_to("123")

            audiobook_maker.clear_stale_singleton_lock(profile_dir)

            self.assertFalse((profile_dir / "SingletonLock").is_symlink())
            self.assertFalse((profile_dir / "SingletonCookie").is_symlink())

    def test_kills_a_live_process_that_is_actually_using_this_profile_dir(self) -> None:
        with TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir)
            # Embed the profile_dir path in the process's own argv so `ps -o command=` shows it,
            # mirroring how a real orphaned Chrome's command line includes --user-data-dir=<profile_dir>.
            proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", str(profile_dir)])
            try:
                time.sleep(0.2)
                (profile_dir / "SingletonLock").symlink_to(f"somehost-{proc.pid}")

                audiobook_maker.clear_stale_singleton_lock(profile_dir)

                proc.wait(timeout=5)
                self.assertIsNotNone(proc.returncode)
                self.assertFalse((profile_dir / "SingletonLock").is_symlink())
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()

    def test_leaves_an_unrelated_live_process_alone(self) -> None:
        with TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir)
            proc = subprocess.Popen(["sleep", "30"])
            try:
                time.sleep(0.2)
                (profile_dir / "SingletonLock").symlink_to(f"somehost-{proc.pid}")

                audiobook_maker.clear_stale_singleton_lock(profile_dir)

                self.assertIsNone(proc.poll())  # still alive - was not killed
                self.assertTrue((profile_dir / "SingletonLock").is_symlink())
            finally:
                proc.kill()
                proc.wait()

    def test_profile_browser_cleanup_targets_only_matching_chrome_processes(self) -> None:
        profile_dir = Path("/tmp/provider-profile")
        process_table = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "  123 /Applications/Google Chrome.app/Google Chrome "
                f"--user-data-dir={profile_dir}\n"
                f"  124 /usr/bin/python worker.py --user-data-dir={profile_dir}\n"
                "  125 /Applications/Google Chrome.app/Google Chrome "
                "--user-data-dir=/tmp/other-profile\n"
            ),
            stderr="",
        )
        signals: list[tuple[int, int]] = []

        def fake_kill(pid: int, sig: int) -> None:
            signals.append((pid, sig))
            if sig == 0:
                raise ProcessLookupError

        with patch("audiobook_maker.subprocess.run", return_value=process_table):
            with patch("audiobook_maker.os.kill", side_effect=fake_kill):
                stopped = audiobook_maker.terminate_web_profile_browser_processes(
                    profile_dir,
                    wait_seconds=0,
                )

        self.assertEqual(stopped, [123])
        self.assertIn((123, signal.SIGTERM), signals)
        self.assertNotIn((124, signal.SIGTERM), signals)
        self.assertNotIn((125, signal.SIGTERM), signals)


class ChatGPTWebWorkflowTests(unittest.TestCase):
    def test_chatgpt_web_launch_args_do_not_override_legacy_hidden_window(self) -> None:
        args = audiobook_maker.chatgpt_web_launch_args(visible=False)

        self.assertEqual(args, [])

    def test_chatgpt_web_launch_args_do_not_override_visible_window(self) -> None:
        args = audiobook_maker.chatgpt_web_launch_args(visible=True)

        self.assertEqual(args, [])

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

        class FakePlaywrightManager:
            def __enter__(self) -> SimpleNamespace:
                chromium = SimpleNamespace(launch_persistent_context=lambda *_args, **_kwargs: FakeContext())
                return SimpleNamespace(chromium=chromium)

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        with TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            combined_child_text = "첫 번째 더 깊은 조각\n\n두 번째 더 깊은 조각"
            (work_dir / "001_01.txt").write_text(combined_child_text, encoding="utf-8")
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
            sections = [audiobook_maker.AudioSection(index=1, title=None, text=combined_child_text)]

            with patch(
                "audiobook_maker.load_chatgpt_web_modules",
                return_value=(object(), lambda: FakePlaywrightManager(), RuntimeError),
            ):
                with patch("audiobook_maker.load_chatgpt_web_cookies", return_value=[]):
                    with patch(
                        "audiobook_maker.web_provider_profile_dir",
                        return_value=work_dir / "_browser_profile",
                    ):
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


class WebProviderSessionTests(unittest.TestCase):
    def test_web_provider_profile_dir_respects_env_override(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"AUDIOBOOK_WEB_PROFILE_DIR": tmpdir}):
                profile_dir = audiobook_maker.web_provider_profile_dir("gemini")

            self.assertEqual(profile_dir, Path(tmpdir) / "gemini")
            self.assertTrue(profile_dir.is_dir())

    def test_prepare_gemini_web_page_detects_guest_mode_without_url_redirect(self) -> None:
        class LoginButtonLocator:
            """Mirrors the real page: multiple '로그인' nodes render, and the
            first one (index 0) is a hidden responsive-layout duplicate while a
            later one is the actually visible button."""

            def count(self) -> int:
                return 4

            def nth(self, index: int) -> "LoginButtonLocator._Node":
                return LoginButtonLocator._Node(visible=index == 1)

            class _Node:
                def __init__(self, *, visible: bool) -> None:
                    self._visible = visible

                def is_visible(self) -> bool:
                    return self._visible

        class FakePage:
            url = "https://gemini.google.com/app"

            def goto(self, _url: str, **_kwargs: object) -> None:
                return None

            def get_by_text(self, text: str, *, exact: bool = False) -> LoginButtonLocator:
                assert text == "로그인"
                assert exact is True
                return LoginButtonLocator()

        with patch(
            "audiobook_maker.wait_for_visible_gemini_locator", return_value=object()
        ):
            with patch("audiobook_maker.install_gemini_web_tts_hook") as install_hook:
                with self.assertRaisesRegex(RuntimeError, "로그인"):
                    audiobook_maker.prepare_gemini_web_page(
                        FakePage(), timeout_error_cls=TimeoutError
                    )

        install_hook.assert_not_called()

    def test_prepare_gemini_web_page_ignores_hidden_login_button_duplicates(self) -> None:
        # 로그인된 상태에서도 반응형 레이아웃용 숨겨진 "로그인" 사본이 DOM에 남아있을 수
        # 있다 - count()만으로는 부족하고, 그중 실제로 화면에 보이는 것이 있는지까지
        # 확인해야 오탐(정상 로그인 세션을 게스트로 오판)을 피할 수 있다.
        class LoginButtonLocator:
            def count(self) -> int:
                return 2

            def nth(self, _index: int) -> "LoginButtonLocator._Node":
                return LoginButtonLocator._Node()

            class _Node:
                def is_visible(self) -> bool:
                    return False

        class FakePage:
            url = "https://gemini.google.com/app"

            def goto(self, _url: str, **_kwargs: object) -> None:
                return None

            def get_by_text(self, text: str, *, exact: bool = False) -> LoginButtonLocator:
                return LoginButtonLocator()

        with patch(
            "audiobook_maker.wait_for_visible_gemini_locator", return_value=object()
        ):
            with patch("audiobook_maker.install_gemini_web_tts_hook") as install_hook:
                audiobook_maker.prepare_gemini_web_page(
                    FakePage(), timeout_error_cls=TimeoutError
                )

        install_hook.assert_called_once()

    def test_prepare_gemini_web_page_accepts_logged_in_session(self) -> None:
        class NoMatchLocator:
            def count(self) -> int:
                return 0

        class FakePage:
            url = "https://gemini.google.com/app"

            def goto(self, _url: str, **_kwargs: object) -> None:
                return None

            def get_by_text(self, text: str, *, exact: bool = False) -> NoMatchLocator:
                return NoMatchLocator()

        with patch(
            "audiobook_maker.wait_for_visible_gemini_locator", return_value=object()
        ):
            with patch("audiobook_maker.install_gemini_web_tts_hook") as install_hook:
                audiobook_maker.prepare_gemini_web_page(
                    FakePage(), timeout_error_cls=TimeoutError
                )

        install_hook.assert_called_once()

        install_hook.assert_called_once()

    def test_ensure_web_provider_session_skips_bootstrap_when_already_logged_in(self) -> None:
        class FakeContext:
            def __init__(self) -> None:
                self.add_cookies_calls = 0

            def new_page(self) -> object:
                return object()

            def add_cookies(self, _cookies: object) -> None:
                self.add_cookies_calls += 1

        context = FakeContext()
        with patch("audiobook_maker.prepare_gemini_web_page") as prepare_mock:
            with patch("audiobook_maker.load_gemini_web_cookies") as load_cookies_mock:
                audiobook_maker.ensure_web_provider_session(
                    context,
                    provider="gemini",
                    timeout_error_cls=RuntimeError,
                    browser_cookie3_module=object(),
                )

        self.assertEqual(prepare_mock.call_count, 1)
        load_cookies_mock.assert_not_called()
        self.assertEqual(context.add_cookies_calls, 0)

    def test_ensure_web_provider_session_can_retain_prepared_page(self) -> None:
        class FakePage:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        class FakeContext:
            def __init__(self) -> None:
                self.page = FakePage()

            def new_page(self) -> FakePage:
                return self.page

        context = FakeContext()
        with patch("audiobook_maker.prepare_chatgpt_web_page"):
            prepared = audiobook_maker.ensure_web_provider_session(
                context,
                provider="chatgpt",
                timeout_error_cls=RuntimeError,
                browser_cookie3_module=object(),
                retain_prepared_page=True,
            )

        self.assertIs(prepared, context.page)
        self.assertFalse(context.page.closed)

    def test_ensure_web_provider_session_bootstraps_once_then_succeeds(self) -> None:
        class FakeContext:
            def __init__(self) -> None:
                self.added_cookies: list[object] = []

            def new_page(self) -> object:
                return object()

            def add_cookies(self, cookies: object) -> None:
                self.added_cookies.append(cookies)

        context = FakeContext()
        with patch(
            "audiobook_maker.prepare_gemini_web_page",
            side_effect=[RuntimeError("Gemini 웹 로그인 페이지로 이동했습니다."), None],
        ) as prepare_mock:
            with patch("audiobook_maker.load_gemini_web_cookies", return_value=["cookie"]) as load_cookies_mock:
                audiobook_maker.ensure_web_provider_session(
                    context,
                    provider="gemini",
                    timeout_error_cls=RuntimeError,
                    browser_cookie3_module=object(),
                )

        self.assertEqual(prepare_mock.call_count, 2)
        load_cookies_mock.assert_called_once()
        self.assertEqual(context.added_cookies, [["cookie"]])

    def test_ensure_web_provider_session_bootstrap_uses_configured_cookie_file(self) -> None:
        class FakeContext:
            def __init__(self) -> None:
                self.added_cookies: list[object] = []

            def new_page(self) -> object:
                return object()

            def add_cookies(self, cookies: object) -> None:
                self.added_cookies.append(cookies)

        context = FakeContext()
        cookie_file = "/tmp/mock/Chrome/Profile/Cookies"
        with patch.dict("os.environ", {"AUDIOBOOK_WEB_BOOTSTRAP_COOKIE_FILE": cookie_file}):
            with patch(
                "audiobook_maker.prepare_gemini_web_page",
                side_effect=[RuntimeError("Gemini 웹 로그인 페이지로 이동했습니다."), None],
            ):
                with patch(
                    "audiobook_maker.load_gemini_web_cookies", return_value=["cookie"]
                ) as load_cookies_mock:
                    audiobook_maker.ensure_web_provider_session(
                        context,
                        provider="gemini",
                        timeout_error_cls=RuntimeError,
                        browser_cookie3_module=object(),
                    )

        load_cookies_mock.assert_called_once_with(load_cookies_mock.call_args[0][0], cookie_file=cookie_file)

    def test_ensure_web_provider_session_raises_when_bootstrap_does_not_help(self) -> None:
        class FakeContext:
            def new_page(self) -> object:
                return object()

            def add_cookies(self, _cookies: object) -> None:
                return None

        context = FakeContext()
        with patch(
            "audiobook_maker.prepare_gemini_web_page",
            side_effect=RuntimeError("여전히 로그인되지 않았습니다."),
        ):
            with patch("audiobook_maker.load_gemini_web_cookies", return_value=["cookie"]):
                with self.assertRaises(RuntimeError):
                    audiobook_maker.ensure_web_provider_session(
                        context,
                        provider="gemini",
                        timeout_error_cls=RuntimeError,
                        browser_cookie3_module=object(),
                    )

    def test_chatgpt_session_does_not_replace_cookies_for_transient_network_error(self) -> None:
        class FakePage:
            def close(self) -> None:
                return None

        class FakeContext:
            def __init__(self) -> None:
                self.add_cookies_calls = 0

            def new_page(self) -> FakePage:
                return FakePage()

            def add_cookies(self, _cookies: object) -> None:
                self.add_cookies_calls += 1

        context = FakeContext()
        with patch(
            "audiobook_maker.prepare_chatgpt_web_page",
            side_effect=RuntimeError("ChatGPT error_kind=network_error retry_action=short_backoff"),
        ):
            with patch("audiobook_maker.load_chatgpt_web_cookies") as load_cookies:
                with self.assertRaisesRegex(RuntimeError, "error_kind=network_error"):
                    audiobook_maker.ensure_web_provider_session(
                        context,
                        provider="chatgpt",
                        timeout_error_cls=RuntimeError,
                        browser_cookie3_module=object(),
                    )

        load_cookies.assert_not_called()
        self.assertEqual(context.add_cookies_calls, 0)

    def test_launch_persistent_web_context_uses_provider_profile_dir(self) -> None:
        class FakeContext:
            pass

        captured: dict[str, object] = {}

        def fake_launch_persistent_context(user_data_dir: str, **kwargs: object) -> FakeContext:
            captured["user_data_dir"] = user_data_dir
            captured["kwargs"] = kwargs
            return FakeContext()

        fake_playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch_persistent_context=fake_launch_persistent_context)
        )

        with TemporaryDirectory() as tmpdir:
            with patch(
                "audiobook_maker.web_provider_profile_dir",
                return_value=Path(tmpdir) / "gemini",
            ):
                context = audiobook_maker.launch_persistent_web_context(
                    fake_playwright,
                    provider="gemini",
                    chrome_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    visible=False,
                )

        self.assertIsInstance(context, FakeContext)
        self.assertEqual(captured["user_data_dir"], str(Path(tmpdir) / "gemini"))
        self.assertEqual(captured["kwargs"]["args"], [])
        self.assertEqual(
            captured["kwargs"]["ignore_default_args"],
            list(audiobook_maker.WEB_CHROME_IGNORED_PLAYWRIGHT_DEFAULT_ARGS),
        )
        self.assertIsNone(captured["kwargs"]["viewport"])
        self.assertFalse(captured["kwargs"]["headless"])
        self.assertEqual(
            captured["kwargs"]["timeout"],
            audiobook_maker.DEFAULT_WEB_BROWSER_LAUNCH_TIMEOUT_SECONDS * 1000,
        )

    def test_launch_failure_cleans_only_the_provider_profile_before_retry(self) -> None:
        fake_playwright = SimpleNamespace(
            chromium=SimpleNamespace(
                launch_persistent_context=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    TimeoutError("browser did not become ready")
                )
            )
        )

        with TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir) / "chatgpt"
            with patch("audiobook_maker.web_provider_profile_dir", return_value=profile_dir):
                with patch(
                    "audiobook_maker.terminate_web_profile_browser_processes",
                    return_value=[123],
                ) as cleanup:
                    with self.assertRaisesRegex(RuntimeError, "error_kind=browser_launch_failed"):
                        audiobook_maker.launch_persistent_web_context(
                            fake_playwright,
                            provider="chatgpt",
                            chrome_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                            visible=True,
                        )

        cleanup.assert_called_once_with(profile_dir)

    def test_launch_persistent_web_context_never_touches_cdp_regardless_of_visible(self) -> None:
        # Both legacy visible values produce the same normal visible Chrome launch, with no CDP
        # window manipulation.
        for visible in (True, False):
            with self.subTest(visible=visible):

                class FakeContext:
                    def __init__(self) -> None:
                        self.new_cdp_session_called = False

                    def new_cdp_session(self, page):
                        self.new_cdp_session_called = True
                        raise AssertionError("launch must not create a CDP session")

                fake_context = FakeContext()
                fake_playwright = SimpleNamespace(
                    chromium=SimpleNamespace(
                        launch_persistent_context=lambda *a, _context=fake_context, **k: _context
                    )
                )

                with TemporaryDirectory() as tmpdir:
                    with patch("audiobook_maker.web_provider_profile_dir", return_value=Path(tmpdir) / "gemini"):
                        audiobook_maker.launch_persistent_web_context(
                            fake_playwright,
                            provider="gemini",
                            chrome_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                            visible=visible,
                        )

                self.assertFalse(fake_context.new_cdp_session_called)

    def test_profile_lock_blocks_second_context_until_first_closes(self) -> None:
        class FakeContext:
            def __init__(self) -> None:
                self.close_handlers = []

            def on(self, event: str, handler) -> None:
                if event == "close":
                    self.close_handlers.append(handler)

            def close(self) -> None:
                for handler in self.close_handlers:
                    handler(self)

        fake_playwright = SimpleNamespace(
            chromium=SimpleNamespace(launch_persistent_context=lambda *_args, **_kwargs: FakeContext())
        )

        with TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir) / "chatgpt"
            with patch("audiobook_maker.web_provider_profile_dir", return_value=profile_dir):
                first = audiobook_maker.launch_persistent_web_context(
                    fake_playwright,
                    provider="chatgpt",
                    chrome_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    visible=False,
                )
                with self.assertRaisesRegex(RuntimeError, "error_kind=profile_in_use"):
                    audiobook_maker.launch_persistent_web_context(
                        fake_playwright,
                        provider="chatgpt",
                        chrome_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                        visible=False,
                    )

                first.close()
                second = audiobook_maker.launch_persistent_web_context(
                    fake_playwright,
                    provider="chatgpt",
                    chrome_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    visible=False,
                )
                second.close()


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

    def test_gemini_web_uses_ogg_temp_audio(self) -> None:
        args = Namespace(provider="gemini_web")

        self.assertEqual(audiobook_maker.temp_audio_suffix(args), ".ogg")

    def test_gemini_api_tts_uses_wav_temp_audio(self) -> None:
        args = Namespace(provider="gemini_api_tts")

        self.assertEqual(audiobook_maker.temp_audio_suffix(args), ".wav")

    def test_partial_audio_path_inserts_partial_before_suffix(self) -> None:
        self.assertEqual(
            audiobook_maker.partial_audio_path(Path("/tmp/book.m4a")),
            Path("/tmp/book.partial.m4a"),
        )

    def test_extract_gemini_web_audio_bytes_from_batchexecute_decodes_ogg_payload(self) -> None:
        expected = b"OggS" + (b"\x00" * 256)
        encoded = base64.b64encode(expected).decode("ascii")
        response = ')]}\'\n\n123\n[["wrb.fr","XqA3Ic","[\\"' + encoded + '\\"]"]]'

        actual = audiobook_maker.extract_gemini_web_audio_bytes_from_batchexecute(response)

        self.assertEqual(actual, expected)

    def test_extract_gemini_web_audio_bytes_from_batchexecute_accepts_missing_padding(self) -> None:
        expected = b"OggS" + (b"\x00" * 257)
        encoded = base64.b64encode(expected).decode("ascii").rstrip("=")
        response = ')]}\'\n\n123\n[["wrb.fr","XqA3Ic","[\\"' + encoded + '\\"]"]]'

        actual = audiobook_maker.extract_gemini_web_audio_bytes_from_batchexecute(response)

        self.assertEqual(actual, expected)

    def test_extract_gemini_web_audio_bytes_from_blob_data_url_decodes_ogg_payload(self) -> None:
        expected = b"OggS" + (b"\x00" * 256)
        encoded = base64.b64encode(expected).decode("ascii")

        actual = audiobook_maker.extract_gemini_web_audio_bytes_from_blob_data_url(
            f"data:audio/ogg;base64,{encoded}"
        )

        self.assertEqual(actual, expected)

    def test_fetch_gemini_web_audio_bytes_uses_blob_url_fallback(self) -> None:
        expected = b"OggS" + (b"\x00" * 256)
        encoded = base64.b64encode(expected).decode("ascii")
        page = Mock()
        page.evaluate.side_effect = [
            None,
            {"ok": True, "count": 1},
            [
                {"kind": "blob_url", "url": "blob:test-audio", "type": "audio/ogg", "size": len(expected)},
                {"kind": "xhr_done", "status": 200, "responseText": "not-audio"},
            ],
            {"ok": True, "dataUrl": f"data:audio/ogg;base64,{encoded}", "type": "audio/ogg", "size": len(expected)},
        ]
        page.wait_for_timeout = Mock()

        actual = audiobook_maker.fetch_gemini_web_audio_bytes(page, timeout_sec=10)

        self.assertEqual(actual, expected)
        page.wait_for_timeout.assert_not_called()

    def test_extract_gemini_api_tts_pcm_bytes_decodes_inline_data(self) -> None:
        expected = b"\x01\x02" * 100
        encoded = base64.b64encode(expected).decode("ascii").rstrip("=")
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "audio/pcm",
                                    "data": encoded,
                                }
                            }
                        ]
                    }
                }
            ]
        }

        actual, mime_type = audiobook_maker.extract_gemini_api_tts_pcm_bytes(payload)

        self.assertEqual(actual, expected)
        self.assertEqual(mime_type, "audio/pcm")

    def test_wav_bytes_from_pcm_s16le_writes_valid_header(self) -> None:
        pcm_bytes = b"\x01\x02" * 100

        actual = audiobook_maker.wav_bytes_from_pcm_s16le(pcm_bytes)

        self.assertTrue(actual.startswith(b"RIFF"))
        self.assertIn(b"WAVE", actual[:16])


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

    def test_audio_observer_records_retry_and_resets_health_after_section_success(self) -> None:
        from webui.workflow_diagnostics import WorkflowDiagnostics, load_workflow_diagnostics

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            diagnostics = WorkflowDiagnostics(root, "audiobook_generation")
            diagnostics.start(stage="synthesis", total_units=2)
            heartbeat = audiobook_maker.ProgressHeartbeat(
                root / "heartbeat.json",
                observer=audiobook_maker.audio_workflow_heartbeat_observer(
                    diagnostics,
                    max_attempts=3,
                ),
            )

            heartbeat.beat(
                stage="section_attempt_error",
                label="1/2",
                section_prefix="001",
                attempt=1,
                detail="network connection reset",
            )
            failed = load_workflow_diagnostics(root)
            self.assertEqual(failed["diagnosis"]["kind"], "network_error")
            self.assertEqual(failed["health"]["state"], "degraded")

            heartbeat.beat(stage="section_complete", label="1/2", section_prefix="001", attempt=2)
            recovered = load_workflow_diagnostics(root)
            self.assertIsNone(recovered["diagnosis"])
            self.assertEqual(recovered["health"]["state"], "healthy")
            self.assertEqual(recovered["progress"]["completed"], 1)

    def test_synthesis_reuses_main_workflow_heartbeat(self) -> None:
        with TemporaryDirectory() as tmpdir:
            heartbeat = audiobook_maker.ProgressHeartbeat(Path(tmpdir) / "heartbeat.json")
            args = Namespace(_progress_heartbeat=heartbeat, heartbeat_file=Path(tmpdir) / "other.json")

            self.assertIs(audiobook_maker.progress_heartbeat_from_args(args), heartbeat)

    def test_main_preserves_failed_workdir_with_diagnostics(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source.txt"
            output = root / "output" / "book.m4a"
            work_dir = root / "work"
            source.write_text("source", encoding="utf-8")
            args = Namespace(
                list_voices=False,
                provider="gemini_api_tts",
                input_file=source,
                output_file=output,
                work_dir=work_dir,
                heartbeat_file=root / "heartbeat.json",
                keep_workdir=False,
                audiobook_mode="plain",
                gemini_api_tts_max_attempts=3,
            )

            with patch("audiobook_maker.parse_args", return_value=args), patch(
                "audiobook_maker.ensure_runtime_ready"
            ), patch("audiobook_maker.resolve_voice", return_value="Sulafat"), patch(
                "audiobook_maker.validate_voice"
            ), patch("audiobook_maker.resolve_max_chars_per_chunk", return_value=2500), patch(
                "audiobook_maker.load_audio_sections",
                side_effect=RuntimeError("오디오북으로 만들 문단을 찾지 못했습니다."),
            ):
                result = audiobook_maker.main()

            diagnostics = json.loads((work_dir / "workflow_diagnostics.json").read_text(encoding="utf-8"))
            self.assertEqual(result, 1)
            self.assertTrue(work_dir.is_dir())
            self.assertEqual(diagnostics["diagnosis"]["kind"], "invalid_input")
            self.assertEqual(
                json.loads((root / "heartbeat.json").read_text(encoding="utf-8"))["stage"],
                "fatal_error",
            )


if __name__ == "__main__":
    unittest.main()
