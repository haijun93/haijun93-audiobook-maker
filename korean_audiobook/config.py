from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .utils import slugify


ENGINE_CHOICES = ("edge", "melo", "xtts_v2")


@dataclass
class ProcessingConfig:
    max_chunk_chars: int = 180
    min_chunk_chars: int = 25
    sentence_gap_ms: int = 320
    comma_gap_ms: int = 170
    dialogue_gap_ms: int = 440
    paragraph_gap_ms: int = 900
    chapter_gap_ms: int = 1800
    normalize_numbers: bool = True
    normalize_dates: bool = True
    normalize_units: bool = True
    keep_english_titles: bool = True


@dataclass
class EngineConfig:
    name: str = "edge"
    voice: str = "ko-KR-SunHiNeural"
    device: str = "auto"
    speed: float = 1.0
    speaker_wav: str = ""
    xtts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    melo_language: str = "KR"
    edge_rate: str = "+0%"
    edge_volume: str = "+0%"
    edge_pitch: str = "+0Hz"
    target_sample_rate: int = 24000


@dataclass
class MasteringConfig:
    enable: bool = True
    target_lufs: float = -18.0
    true_peak_db: float = -2.0
    loudness_range: float = 11.0
    highpass_hz: int = 45
    lowpass_hz: int = 12500
    trim_silence: bool = True
    trim_threshold_db: float = -45.0
    trim_start_silence_sec: float = 0.05
    trim_stop_silence_sec: float = 0.20
    output_sample_rate: int = 44100
    bitrate_kbps: int = 128


@dataclass
class OutputConfig:
    export_format: str = "mp3"
    export_m4b: bool = False
    chapter_dirname: str = "chapters"


@dataclass
class AppConfig:
    input_file: Path
    output_dir: Path
    title: str
    author: str
    work_dir: Path
    cache_dir: Path
    resume: bool = True
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    mastering: MasteringConfig = field(default_factory=MasteringConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    def build_signature(self) -> dict[str, Any]:
        return {
            "processing": asdict(self.processing),
            "engine": asdict(self.engine),
            "mastering": asdict(self.mastering),
            "output": asdict(self.output),
        }

    @property
    def chapter_output_dir(self) -> Path:
        return self.output_dir / self.output.chapter_dirname

    @property
    def final_mp3_path(self) -> Path:
        return self.output_dir / f"{slugify(self.title, fallback='audiobook')}.mp3"

    @property
    def final_m4b_path(self) -> Path:
        return self.output_dir / f"{slugify(self.title, fallback='audiobook')}.m4b"


def build_app_config(args: Any) -> AppConfig:
    input_file = Path(args.input_file).expanduser().resolve()
    title = args.title or input_file.stem
    output_dir = Path(args.output_dir or (input_file.parent / f"{input_file.stem}_audiobook")).expanduser().resolve()
    work_dir = Path(args.work_dir or (output_dir / "_work")).expanduser().resolve()
    cache_dir = Path(args.cache_dir or (output_dir / "_cache")).expanduser().resolve()

    processing = ProcessingConfig(
        max_chunk_chars=args.max_chars_per_chunk,
        min_chunk_chars=args.min_chars_per_chunk,
        sentence_gap_ms=args.sentence_gap_ms,
        comma_gap_ms=args.comma_gap_ms,
        dialogue_gap_ms=args.dialogue_gap_ms,
        paragraph_gap_ms=args.paragraph_gap_ms,
        chapter_gap_ms=args.chapter_gap_ms,
        normalize_numbers=not args.no_normalize_numbers,
        normalize_dates=not args.no_normalize_dates,
        normalize_units=not args.no_normalize_units,
    )
    engine_name = args.engine
    default_voice = (
        "ko-KR-SunHiNeural"
        if engine_name == "edge"
        else ("KR" if engine_name == "melo" else "")
    )
    engine = EngineConfig(
        name=args.engine,
        voice=args.voice or default_voice,
        device=args.device,
        speed=args.speed,
        speaker_wav=args.speaker_wav or "",
        xtts_model=args.xtts_model,
        melo_language=args.melo_language,
        edge_rate=args.edge_rate,
        edge_volume=args.edge_volume,
        edge_pitch=args.edge_pitch,
        target_sample_rate=args.engine_sample_rate,
    )
    mastering = MasteringConfig(
        enable=not args.no_mastering,
        target_lufs=args.target_lufs,
        true_peak_db=args.true_peak_db,
        loudness_range=args.loudness_range,
        highpass_hz=args.highpass_hz,
        lowpass_hz=args.lowpass_hz,
        trim_silence=not args.no_trim_silence,
        trim_threshold_db=args.trim_threshold_db,
        trim_start_silence_sec=args.trim_start_silence_sec,
        trim_stop_silence_sec=args.trim_stop_silence_sec,
        output_sample_rate=args.output_sample_rate,
        bitrate_kbps=args.bitrate_kbps,
    )
    output = OutputConfig(
        export_format="mp3",
        export_m4b=args.export_m4b,
        chapter_dirname=args.chapter_dirname,
    )
    return AppConfig(
        input_file=input_file,
        output_dir=output_dir,
        title=title,
        author=args.author,
        work_dir=work_dir,
        cache_dir=cache_dir,
        resume=not args.no_resume,
        processing=processing,
        engine=engine,
        mastering=mastering,
        output=output,
    )
