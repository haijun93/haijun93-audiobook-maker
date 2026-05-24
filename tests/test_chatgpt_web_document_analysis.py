from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "analyze_document_with_chatgpt_web.py"
)
SPEC = importlib.util.spec_from_file_location("chatgpt_web_document_analysis", SCRIPT_PATH)
chatgpt_web_document_analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(chatgpt_web_document_analysis)


class ChatGPTWebDocumentAnalysisTests(unittest.TestCase):
    def test_resolve_output_file_defaults_to_markdown_analysis_path(self) -> None:
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
                },
            )()
            output = chatgpt_web_document_analysis.resolve_output_file(args)
            self.assertEqual(output.name, "sample.analysis.md")

    def test_resolve_work_dir_defaults_from_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "sample.analysis.md"
            args = type("Args", (), {"work_dir": None})()
            work_dir = chatgpt_web_document_analysis.resolve_work_dir(args, output)
            self.assertEqual(work_dir.name, "sample.analysis_work")

    def test_build_chunk_analysis_prompt_contains_chunk_metadata(self) -> None:
        prompt = chatgpt_web_document_analysis.build_chunk_analysis_prompt(
            input_name="sample.docx",
            instructions="핵심을 정리하라.",
            chunk_text="첫 번째 문단",
            chunk_index=2,
            chunk_count=5,
            final_format="markdown",
        )
        self.assertIn("전체 5개 조각 중 2번째", prompt)
        self.assertIn("핵심을 정리하라.", prompt)
        self.assertIn("첫 번째 문단", prompt)

    def test_build_final_analysis_prompt_contains_all_chunk_summaries(self) -> None:
        prompt = chatgpt_web_document_analysis.build_final_analysis_prompt(
            input_name="sample.pdf",
            instructions="중복 없이 통합하라.",
            chunk_summaries=["요약 A", "요약 B"],
            final_format="markdown",
        )
        self.assertIn("문서 `sample.pdf`", prompt)
        self.assertIn("## 조각 1", prompt)
        self.assertIn("요약 A", prompt)
        self.assertIn("요약 B", prompt)


if __name__ == "__main__":
    unittest.main()
