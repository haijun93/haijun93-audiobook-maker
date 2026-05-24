from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "analyze_document_with_web_services.py"
)
SPEC = importlib.util.spec_from_file_location("multi_web_document_analysis", SCRIPT_PATH)
multi_web_document_analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(multi_web_document_analysis)


class MultiWebDocumentAnalysisTests(unittest.TestCase):
    def test_analysis_provider_sequence_for_basic(self) -> None:
        self.assertEqual(
            multi_web_document_analysis.analysis_provider_sequence("basic"),
            ("chatgpt_web",),
        )

    def test_analysis_provider_sequence_for_deep(self) -> None:
        self.assertEqual(
            multi_web_document_analysis.analysis_provider_sequence("deep"),
            ("chatgpt_web", "claude_web", "gemini_web"),
        )

    def test_resolve_output_file_defaults_to_deep_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "sample.docx"
            input_path.write_text("dummy", encoding="utf-8")
            args = type(
                "Args",
                (),
                {
                    "input_file": input_path,
                    "output_file": None,
                    "final_format": "markdown",
                    "analysis_mode": "deep",
                },
            )()
            output = multi_web_document_analysis.resolve_output_file(args)
            self.assertEqual(output.name, "sample.deep.md")

    def test_build_review_prompt_includes_prior_outputs(self) -> None:
        prompt = multi_web_document_analysis.build_review_prompt(
            provider="claude_web",
            input_name="sample.docx",
            instructions="핵심을 검토하라.",
            chunk_text="문서 조각",
            prior_outputs=[("ChatGPT 분석", "초안 내용")],
            final_format="markdown",
        )
        self.assertIn("Claude 웹 검토 단계", prompt)
        self.assertIn("문서 조각", prompt)
        self.assertIn("초안 내용", prompt)

    def test_build_final_review_prompt_includes_prior_outputs(self) -> None:
        prompt = multi_web_document_analysis.build_final_review_prompt(
            provider="gemini_web",
            input_name="sample.pdf",
            instructions="최종 검증하라.",
            prior_outputs=[("ChatGPT 통합본", "통합 초안"), ("Claude 검토본", "검토 결과")],
            final_format="markdown",
        )
        self.assertIn("Gemini 웹 최종 검증 단계", prompt)
        self.assertIn("통합 초안", prompt)
        self.assertIn("검토 결과", prompt)

    def test_is_claude_web_usage_limit_text_detects_limit_notice(self) -> None:
        text = "You've reached your usage limit for Claude. Please try again later."
        self.assertTrue(multi_web_document_analysis.is_claude_web_usage_limit_text(text))

    def test_write_manifest_records_effective_providers_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            manifest_path = tmp_path / "analysis_manifest.json"
            input_path = tmp_path / "sample.docx"
            input_path.write_text("dummy", encoding="utf-8")
            output_path = tmp_path / "sample.deep.md"
            work_dir = tmp_path / "sample_work"
            args = type(
                "Args",
                (),
                {
                    "analysis_mode": "deep",
                    "request_timeout_sec": 900,
                    "chatgpt_web_visible": False,
                    "claude_web_visible": False,
                    "gemini_web_visible": False,
                    "chatgpt_web_max_attempts": 8,
                    "claude_web_max_attempts": 5,
                    "gemini_web_max_attempts": 3,
                    "max_chars_per_chunk": 6000,
                    "final_format": "markdown",
                },
            )()
            multi_web_document_analysis.write_manifest(
                manifest_path=manifest_path,
                args=args,
                input_file=input_path,
                output_file=output_path,
                work_dir=work_dir,
                chunk_count=4,
                effective_providers=["chatgpt_web", "gemini_web"],
                claude_fallback_triggered=True,
                claude_fallback_reason="usage limit",
            )
            payload = manifest_path.read_text(encoding="utf-8")
            self.assertIn('"effective_providers": [', payload)
            self.assertIn('"chatgpt_web"', payload)
            self.assertIn('"gemini_web"', payload)
            self.assertIn('"claude_fallback_triggered": true', payload)
