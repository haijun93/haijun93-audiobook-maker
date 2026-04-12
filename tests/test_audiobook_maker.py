import base64
import subprocess
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


class SourceLoadingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
