import tempfile
import unittest
from pathlib import Path

from korean_audiobook.config import build_app_config
from korean_audiobook.main import build_parser
from korean_audiobook.tts_engine import (
    EdgeTTSEngine,
    MeloTTSEngine,
    XTTSv2Engine,
    build_engine,
    list_supported_engines,
)


class EngineSelectionTests(unittest.TestCase):
    def parse_config(self, *extra_args: str):
        parser = build_parser()
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "book.txt"
            input_file.write_text("안녕하세요.", encoding="utf-8")
            args = parser.parse_args(
                [
                    "--input-file",
                    str(input_file),
                    "--author",
                    "Tester",
                    *extra_args,
                ]
            )
            return build_app_config(args)

    def test_supported_engine_list_includes_remaining_backends(self) -> None:
        self.assertEqual(list_supported_engines(), ("edge", "melo", "xtts_v2"))

    def test_edge_default_voice_is_korean_edge_voice(self) -> None:
        config = self.parse_config("--engine", "edge")
        self.assertEqual(config.engine.voice, "ko-KR-SunHiNeural")

    def test_melo_default_voice_is_kr(self) -> None:
        config = self.parse_config("--engine", "melo")
        self.assertEqual(config.engine.voice, "KR")

    def test_build_engine_returns_edge_engine(self) -> None:
        config = self.parse_config("--engine", "edge")
        self.assertIsInstance(build_engine(config), EdgeTTSEngine)

    def test_build_engine_returns_melo_engine(self) -> None:
        config = self.parse_config("--engine", "melo")
        self.assertIsInstance(build_engine(config), MeloTTSEngine)

    def test_build_engine_returns_xtts_engine(self) -> None:
        config = self.parse_config("--engine", "xtts_v2")
        self.assertIsInstance(build_engine(config), XTTSv2Engine)


if __name__ == "__main__":
    unittest.main()
