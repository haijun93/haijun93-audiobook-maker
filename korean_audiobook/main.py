from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .audiobook_builder import AudiobookBuilder
from .config import ENGINE_CHOICES, build_app_config
from .tts_engine import list_supported_engines
from .utils import require_binary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="한국어 txt 파일을 장별 오디오북으로 변환합니다."
    )
    parser.add_argument("--input-file", help="한국어 원문 txt 파일")
    parser.add_argument("--output-dir", help="출력 폴더. 기본값은 입력 파일 옆 `<stem>_audiobook`")
    parser.add_argument("--title", help="오디오북 제목")
    parser.add_argument("--author", default="Unknown", help="저자명")
    parser.add_argument("--work-dir", help="중간 파일 폴더")
    parser.add_argument("--cache-dir", help="캐시 폴더")
    parser.add_argument("--engine", choices=ENGINE_CHOICES, default="edge", help="TTS 엔진")
    parser.add_argument("--voice", default="", help="엔진별 voice 이름")
    parser.add_argument("--device", default="auto", help="`auto`, `cpu`, `cuda`, `mps`")
    parser.add_argument("--speed", type=float, default=1.0, help="엔진 속도 배율")
    parser.add_argument("--speaker-wav", help="XTTS-v2 기준 음성 wav")
    parser.add_argument("--xtts-model", default="tts_models/multilingual/multi-dataset/xtts_v2")
    parser.add_argument("--melo-language", default="KR")
    parser.add_argument("--edge-rate", default="+0%")
    parser.add_argument("--edge-volume", default="+0%")
    parser.add_argument("--edge-pitch", default="+0Hz")
    parser.add_argument("--engine-sample-rate", type=int, default=24000)
    parser.add_argument("--max-chars-per-chunk", type=int, default=180)
    parser.add_argument("--min-chars-per-chunk", type=int, default=25)
    parser.add_argument("--sentence-gap-ms", type=int, default=320)
    parser.add_argument("--comma-gap-ms", type=int, default=170)
    parser.add_argument("--dialogue-gap-ms", type=int, default=440)
    parser.add_argument("--paragraph-gap-ms", type=int, default=900)
    parser.add_argument("--chapter-gap-ms", type=int, default=1800)
    parser.add_argument("--no-normalize-numbers", action="store_true")
    parser.add_argument("--no-normalize-dates", action="store_true")
    parser.add_argument("--no-normalize-units", action="store_true")
    parser.add_argument("--no-mastering", action="store_true")
    parser.add_argument("--no-trim-silence", action="store_true")
    parser.add_argument("--target-lufs", type=float, default=-18.0)
    parser.add_argument("--true-peak-db", type=float, default=-2.0)
    parser.add_argument("--loudness-range", type=float, default=11.0)
    parser.add_argument("--highpass-hz", type=int, default=45)
    parser.add_argument("--lowpass-hz", type=int, default=12500)
    parser.add_argument("--trim-threshold-db", type=float, default=-45.0)
    parser.add_argument("--trim-start-silence-sec", type=float, default=0.05)
    parser.add_argument("--trim-stop-silence-sec", type=float, default=0.20)
    parser.add_argument("--output-sample-rate", type=int, default=44100)
    parser.add_argument("--bitrate-kbps", type=int, default=128)
    parser.add_argument("--export-m4b", action="store_true")
    parser.add_argument("--chapter-dirname", default="chapters")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--list-engines", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_engines:
        for engine in list_supported_engines():
            print(engine)
        return 0
    if not args.input_file:
        parser.error("--input-file is required unless --list-engines is used")

    require_binary("ffmpeg")
    require_binary("ffprobe")

    config = build_app_config(args)
    result = AudiobookBuilder(config).build()

    print(f"완료: {result.final_mp3}")
    print(f"장 파일 수: {len(result.chapter_mp3_files)}")
    print(f"총 청크 수: {result.total_chunks}")
    print(f"manifest: {result.manifest_path}")
    if result.final_m4b:
        print(f"m4b: {result.final_m4b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
