from __future__ import annotations

import asyncio
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .config import AppConfig
from .utils import detect_torch_device, ensure_dir

class BaseTTSEngine(ABC):
    name = "base"
    output_suffix = ".wav"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @abstractmethod
    def signature(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def synthesize_to_file(self, text: str, output_path: Path) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return None


class EdgeTTSEngine(BaseTTSEngine):
    name = "edge"
    output_suffix = ".mp3"

    def signature(self) -> dict[str, Any]:
        engine = self.config.engine
        return {
            "engine": self.name,
            "voice": engine.voice,
            "rate": engine.edge_rate,
            "volume": engine.edge_volume,
            "pitch": engine.edge_pitch,
        }

    def synthesize_to_file(self, text: str, output_path: Path) -> None:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError("edge-tts가 필요합니다. `python -m pip install edge-tts`를 실행하세요.") from exc

        async def save() -> None:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.config.engine.voice,
                rate=self.config.engine.edge_rate,
                volume=self.config.engine.edge_volume,
                pitch=self.config.engine.edge_pitch,
            )
            await communicate.save(str(output_path))

        asyncio.run(save())


class MeloTTSEngine(BaseTTSEngine):
    name = "melo"
    output_suffix = ".wav"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config)
        self._model = None

    def signature(self) -> dict[str, Any]:
        engine = self.config.engine
        return {
            "engine": self.name,
            "voice": engine.voice,
            "language": engine.melo_language,
            "device": detect_torch_device(engine.device),
            "speed": engine.speed,
        }

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from melo.api import TTS
        except ImportError as exc:
            raise RuntimeError(
                "MeloTTS가 필요합니다. 공식 저장소를 설치한 뒤 다시 실행하세요: "
                "`git clone https://github.com/myshell-ai/MeloTTS.git && cd MeloTTS && python -m pip install -e .`"
            ) from exc
        self._model = TTS(language=self.config.engine.melo_language, device=detect_torch_device(self.config.engine.device))
        return self._model

    def synthesize_to_file(self, text: str, output_path: Path) -> None:
        model = self._load_model()
        speaker_map = getattr(getattr(model, "hps", None), "data", None)
        spk2id = getattr(speaker_map, "spk2id", {}) if speaker_map is not None else {}
        voice = self.config.engine.voice or self.config.engine.melo_language
        if voice not in spk2id:
            available = ", ".join(sorted(spk2id)) if spk2id else "(없음)"
            raise RuntimeError(f"MeloTTS speaker `{voice}` 를 찾지 못했습니다. 사용 가능: {available}")
        model.tts_to_file(
            text,
            spk2id[voice],
            str(output_path),
            speed=self.config.engine.speed,
        )


class XTTSv2Engine(BaseTTSEngine):
    name = "xtts_v2"
    output_suffix = ".wav"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config)
        self._tts = None

    def signature(self) -> dict[str, Any]:
        engine = self.config.engine
        return {
            "engine": self.name,
            "model": engine.xtts_model,
            "speaker_wav": str(Path(engine.speaker_wav).expanduser()) if engine.speaker_wav else "",
            "voice": engine.voice,
            "device": detect_torch_device(engine.device),
            "speed": engine.speed,
        }

    def _load_model(self) -> Any:
        if self._tts is not None:
            return self._tts
        try:
            from TTS.api import TTS
        except ImportError as exc:
            raise RuntimeError("XTTS-v2에는 Coqui TTS가 필요합니다. `python -m pip install TTS`를 실행하세요.") from exc
        device = detect_torch_device(self.config.engine.device)
        tts = TTS(self.config.engine.xtts_model)
        if hasattr(tts, "to"):
            tts = tts.to(device)
        self._tts = tts
        return self._tts

    def synthesize_to_file(self, text: str, output_path: Path) -> None:
        model = self._load_model()
        speaker_wav = self.config.engine.speaker_wav.strip()
        if not speaker_wav:
            raise RuntimeError("XTTS-v2는 `--speaker-wav` 기준 음성 파일이 필요합니다.")
        kwargs = {
            "text": text,
            "file_path": str(output_path),
            "speaker_wav": str(Path(speaker_wav).expanduser()),
            "language": "ko",
        }
        if self.config.engine.speed != 1.0:
            kwargs["speed"] = self.config.engine.speed
        try:
            model.tts_to_file(**kwargs)
        except TypeError:
            kwargs.pop("speed", None)
            model.tts_to_file(**kwargs)


def build_engine(config: AppConfig) -> BaseTTSEngine:
    name = config.engine.name
    if name == "edge":
        return EdgeTTSEngine(config)
    if name == "melo":
        return MeloTTSEngine(config)
    if name == "xtts_v2":
        return XTTSv2Engine(config)
    raise ValueError(f"지원하지 않는 엔진입니다: {name}")


def list_supported_engines() -> tuple[str, ...]:
    return ("edge", "melo", "xtts_v2")


def synthesize_text_to_tempfile(engine: BaseTTSEngine, text: str, directory: Path) -> Path:
    ensure_dir(directory)
    fd, raw_path = tempfile.mkstemp(prefix="tts_", suffix=engine.output_suffix, dir=str(directory))
    Path(raw_path).unlink(missing_ok=True)
    Path(raw_path).touch()
    Path(raw_path).unlink()
    output_path = Path(raw_path)
    engine.synthesize_to_file(text, output_path)
    return output_path
