import unittest

from korean_audiobook.config import ProcessingConfig
from korean_audiobook.korean_text_processing import (
    build_document_plan,
    normalize_text,
    number_to_korean,
)


class KoreanNumberTests(unittest.TestCase):
    def test_number_to_korean_integer(self) -> None:
        self.assertEqual(number_to_korean("2026"), "이천이십육")

    def test_number_to_korean_decimal(self) -> None:
        self.assertEqual(number_to_korean("3.14"), "삼점 일사")


class KoreanNormalizationTests(unittest.TestCase):
    def test_dates_units_and_percent_are_normalized(self) -> None:
        config = ProcessingConfig()
        text = normalize_text("2026-03-13, 12kg, 50%", config)

        self.assertIn("이천이십육년 삼월 십삼일", text)
        self.assertIn("십이킬로그램", text)
        self.assertIn("오십퍼센트", text)


class DocumentPlanTests(unittest.TestCase):
    def test_document_plan_preserves_chapters(self) -> None:
        config = ProcessingConfig(max_chunk_chars=60)
        text = "제1장\n\n\"안녕하세요.\" 그가 말했다.\n\n제2장\n\n오늘은 맑다."

        plan = build_document_plan(text, config)

        self.assertEqual(len(plan.chapters), 2)
        self.assertEqual(plan.chapters[0].title, "제1장")
        self.assertTrue(plan.chapters[0].chunks[0].is_dialogue)
        self.assertEqual(plan.chapters[1].title, "제2장")


if __name__ == "__main__":
    unittest.main()
