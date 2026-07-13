#!/usr/bin/env python3
from __future__ import annotations

import json
import argparse
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from make_korean_only_epubs import convert_epub, output_name
from safe_xml import safe_fromstring


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path("/Users/hyeokjunkong/Desktop/소설/#books_source")
OUTPUT_DIR = Path("/Users/hyeokjunkong/Desktop/소설/#[k-e]")
LOG_DIR = OUTPUT_DIR / "_batch_logs"
TRANSLATE_SCRIPT = ROOT / "scripts" / "translate_epub_with_chatgpt_web_to_study_epub.py"
DEFAULT_COOLDOWN_SECONDS = 60 * 60


@dataclass(frozen=True)
class Job:
    source_name: str
    output_name: str
    korean_title: str

    @property
    def source(self) -> Path:
        return SOURCE_DIR / self.source_name

    @property
    def output(self) -> Path:
        return OUTPUT_DIR / self.output_name

    @property
    def work_dir(self) -> Path:
        return SOURCE_DIR / f"{self.source.stem}_chatgpt_translate_work"


JOBS = [
    Job("01_THE_DEMON_OF_UNREST_by_Erik_Larson.epub", "[k-e] The Demon Of Unrest.epub", "불안의 악마"),
    Job("02_YOU_NEVER_KNOW_by_Tom_Selleck_with_Ellis_Henican.epub", "[k-e] You Never Know.epub", "당신은 모른다"),
    Job("03_THE_END_OF_EVERYTHING_by_Victor_Davis_Hanson.epub", "[k-e] The End Of Everything.epub", "모든 것의 종말"),
    Job("04_BITS_AND_PIECES_by_Whoopi_Goldberg.epub", "[k-e] Bits And Pieces.epub", "조각들"),
    Job("05_THE_ANXIOUS_GENERATION_by_Jonathan_Haidt.epub", "[k-e] The Anxious Generation.epub", "불안 세대"),
    Job("06_COMING_HOME_by_Brittney_Griner_with_Michelle_Burford.epub", "[k-e] Coming Home.epub", "집으로 돌아오기"),
    Job("07_LOVE_MOM_by_Nicole_Saphier.epub", "[k-e] Love Mom.epub", "사랑을 담아, 엄마"),
    Job("08_AN_UNFINISHED_LOVE_STORY_by_Doris_Kearns_Goodwin.epub", "[k-e] An Unfinished Love Story.epub", "끝나지 않은 사랑 이야기"),
    Job("09_NO_GOING_BACK_by_Kristi_Noem.epub", "[k-e] No Going Back.epub", "돌아갈 수 없다"),
    Job("10_THE_BODY_KEEPS_THE_SCORE_by_Bessel_van_der_Kolk.epub", "[k-e] The Body Keeps The Score.epub", "몸은 기억한다"),
    Job("11_THE_BACKYARD_BIRD_CHRONICLES_by_Amy_Tan.epub", "[k-e] The Backyard Bird Chronicles.epub", "뒤뜰 새 연대기"),
    Job("12_THE_WAGER_by_David_Grann.epub", "[k-e] The Wager.epub", "웨이저"),
    Job("13_OUTLIVE_by_Peter_Attia_with_Bill_Gifford.epub", "[k-e] Outlive.epub", "아웃라이브"),
    Job("14_THE_LIGHT_WE_CARRY_by_Michelle_Obama.epub", "[k-e] The Light We Carry.epub", "우리가 지닌 빛"),
    Job("15_THE_HUNDRED_YEARS_39_WAR_ON_PALESTINE_by_Rashid_Khalidi.epub", "[k-e] The Hundred Years War On Palestine.epub", "팔레스타인 백년전쟁"),
    Job("Robot_Series_0_1_I_Robot_-_Isaac_Asimov.epub", "[k-e] I Robot.epub", "아이, 로봇"),
    Job("Robot_Series_0_2_The_Rest_of_the_Robots_-_Isaac_Asimov.epub", "[k-e] The Rest of the Robots.epub", "나머지 로봇들"),
    Job("Robot_Series_0_3_The_Complete_Robot.epub", "[k-e] The Complete Robot.epub", "완전한 로봇"),
    Job("Robot_Series_0_4_Robot_Dreams.epub", "[k-e] Robot Dreams.epub", "로봇 드림"),
    Job("Robot_Series_0_5_Robot_Visions_-_Isaac_Asimov.epub", "[k-e] Robot Visions.epub", "로봇 비전"),
    Job("Robot_Series_0_6_The_Positronic_Man_-_Isaac_Asimov.epub", "[k-e] The Positronic Man.epub", "포지트로닉 인간"),
    Job("Robot_Series_1_The_Caves_of_Steel_-_Isaac_Asimov.epub", "[k-e] The Caves Of Steel.epub", "강철 동굴"),
    Job("Robot_Series_2_The_Naked_Sun_-_Isaac_Asimov.epub", "[k-e] The Naked Sun.epub", "벌거벗은 태양"),
    Job("Robot_Series_3_The_Robots_of_Dawn_-_Isaac_Asimov.epub", "[k-e] The Robots Of Dawn.epub", "새벽의 로봇"),
    Job("The_Tale_of_Despereaux.epub", "[k-e] The Tale Of Despereaux.epub", "데스페로 이야기"),
    Job("The_True_Confessions_Of_Charlotte_Doyle.epub", "[k-e] The True Confessions Of Charlotte Doyle.epub", "샬럿 도일의 진실한 고백"),
    Job("make_it_stick_The_Science_of_Successful_Learning_Peter_C_Brown_Henry_L_Roediger_III_etc.epub", "[k-e] Make It Stick.epub", "메이크 잇 스틱"),
    Job("[e]Never Lie.epub", "[k-e] Never Lie.epub", "네버 라이"),
    Job("[e]First Lie Wins -Ashley Elston.epub", "[k-e] First Lie Wins.epub", "첫 번째 거짓말이 이긴다"),
]


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line, flush=True)
    with (LOG_DIR / "batch_status.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def verify_epub(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing output"
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            required = ["mimetype", "OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx"]
            missing = [name for name in required if name not in names]
            if names[:1] != ["mimetype"]:
                return False, "mimetype is not first zip entry"
            if missing:
                return False, f"missing required files: {missing}"
            texts = {
                name: archive.read(name).decode("utf-8", "replace")
                for name in names
                if name.endswith((".xhtml", ".html", ".opf", ".ncx"))
            }
            missing_markers = sum(text.count("[번역 누락]") for text in texts.values())
            ko_blocks = sum(text.count('class="ko"') for text in texts.values())
            en_blocks = sum(text.count('class="en"') for text in texts.values())
            nav_items = texts.get("OEBPS/nav.xhtml", "").count("<li>")
            ncx_points = texts.get("OEBPS/toc.ncx", "").count("<navPoint")
            for _name, text in texts.items():
                safe_fromstring(text.encode())
    except Exception as exc:
        return False, str(exc)
    if missing_markers:
        return False, f"translation missing markers: {missing_markers}"
    if ko_blocks <= 0 or ko_blocks != en_blocks:
        return False, f"pair count mismatch: ko={ko_blocks} en={en_blocks}"
    if nav_items <= 0 or ncx_points <= 0:
        return False, f"toc missing: nav={nav_items} ncx={ncx_points}"
    return True, f"ok size={path.stat().st_size} pairs={ko_blocks} nav={nav_items}/{ncx_points}"


def verify_korean_only_epub(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing output"
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            if names[:1] != ["mimetype"]:
                return False, "mimetype is not first zip entry"
            texts = {
                name: archive.read(name).decode("utf-8", "replace")
                for name in names
                if name.endswith((".xhtml", ".html", ".opf", ".ncx"))
            }
            missing_markers = sum(text.count("[번역 누락]") for text in texts.values())
            en_blocks = sum(text.count('class="en"') + text.count("class='en'") for text in texts.values())
            pair_blocks = sum(text.count('class="pair"') + text.count("class='pair'") for text in texts.values())
            nav_items = texts.get("OEBPS/nav.xhtml", "").count("<li>")
            ncx_points = texts.get("OEBPS/toc.ncx", "").count("<navPoint")
            for text in texts.values():
                safe_fromstring(text.encode())
    except Exception as exc:
        return False, str(exc)
    if missing_markers:
        return False, f"translation missing markers: {missing_markers}"
    if en_blocks or pair_blocks:
        return False, f"english study markup remains: en={en_blocks} pair={pair_blocks}"
    if nav_items <= 0 or ncx_points <= 0:
        return False, f"toc missing: nav={nav_items} ncx={ncx_points}"
    return True, f"ok size={path.stat().st_size} nav={nav_items}/{ncx_points}"


def ensure_korean_only(job: Job) -> None:
    korean_output = job.output.with_name(output_name(job.output.name))
    ok, reason = verify_korean_only_epub(korean_output)
    if ok:
        log(f"SKIP verified {korean_output.name}: {reason}")
        return
    log(f"PENDING {korean_output.name}: {reason}")
    stats = convert_epub(job.output, korean_output, overwrite=korean_output.exists())
    ok, reason = verify_korean_only_epub(korean_output)
    if not ok:
        raise RuntimeError(f"{korean_output.name} verify failed: {reason}")
    log(
        f"DONE {korean_output.name}: {reason}; "
        f"korean_paragraphs={stats['pairs']} "
        f"extra_english_nodes_removed={stats['en_removed']} "
        f"inline_english_removed={stats['inline_removed']}"
    )


def select_jobs(patterns: list[str]) -> list[Job]:
    if not patterns:
        return JOBS
    lowered = [pattern.lower() for pattern in patterns]
    selected: list[Job] = []
    for job in JOBS:
        haystack = " ".join([job.source_name, job.output_name, job.korean_title]).lower()
        if any(pattern in haystack for pattern in lowered):
            selected.append(job)
    return selected


def run_job(job: Job, attempt: int) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    heartbeat = job.work_dir / "heartbeat.json"
    log_path = LOG_DIR / f"{job.source.stem}.attempt-{attempt:03d}.log"
    cmd = [
        "python3",
        str(TRANSLATE_SCRIPT),
        "--input-epub",
        str(job.source),
        "--output-epub",
        str(job.output),
        "--work-dir",
        str(job.work_dir),
        "--book-title-ko",
        job.korean_title,
        "--max-chars-per-chunk",
        "6000",
        "--request-timeout-sec",
        "1200",
        "--chatgpt-web-max-attempts",
        "5",
        "--chunks-per-conversation",
        "20",
        "--chatgpt-web-visible",
        "--heartbeat-file",
        str(heartbeat),
    ]
    log(f"START {job.output_name} attempt={attempt}")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("\n\n" + "=" * 80 + "\n")
        fh.write(f"{datetime.now().isoformat(timespec='seconds')} {' '.join(cmd)}\n")
        fh.flush()
        proc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    return proc.returncode


def shutdown_computer() -> None:
    log("ALL JOBS VERIFIED. Requesting macOS shutdown.")
    subprocess.run(["osascript", "-e", 'tell application "System Events" to shut down'], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume the #books_source Korean/English EPUB batch.")
    parser.add_argument("--shutdown", action="store_true", help="shut down macOS after all jobs finish")
    parser.add_argument("--only", nargs="*", default=[], help="run only jobs matching these source/output/title substrings")
    parser.add_argument("--no-korean-only", action="store_true", help="do not build [k] EPUBs from verified [k-e] outputs")
    parser.add_argument("--cooldown-seconds", type=int, default=DEFAULT_COOLDOWN_SECONDS)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    attempts: dict[str, int] = {}
    jobs = select_jobs(args.only)
    if not jobs:
        log(f"ERROR no jobs matched: {args.only}")
        return 2
    for job in jobs:
        if not job.source.exists():
            log(f"ERROR source missing: {job.source}")
            return 2
        ok, reason = verify_epub(job.output)
        if ok:
            log(f"SKIP verified {job.output_name}: {reason}")
            if not args.no_korean_only:
                ensure_korean_only(job)
            continue
        log(f"PENDING {job.output_name}: {reason}")
        while True:
            attempts[job.source_name] = attempts.get(job.source_name, 0) + 1
            rc = run_job(job, attempts[job.source_name])
            ok, reason = verify_epub(job.output)
            if ok:
                log(f"DONE {job.output_name}: {reason}")
                if not args.no_korean_only:
                    ensure_korean_only(job)
                break
            heartbeat = job.work_dir / "heartbeat.json"
            heartbeat_summary = ""
            if heartbeat.exists():
                try:
                    data = json.loads(heartbeat.read_text(encoding="utf-8"))
                    heartbeat_summary = f" heartbeat={data.get('stage')} {data.get('label')} {data.get('attempt')} {data.get('detail')}"
                except Exception as exc:
                    heartbeat_summary = f" heartbeat_read_error={exc}"
            log(
                f"RETRY_LATER {job.output_name}: rc={rc}; verify={reason};"
                f"{heartbeat_summary}; cooldown={args.cooldown_seconds}s"
            )
            time.sleep(args.cooldown_seconds)
    if args.shutdown:
        shutdown_computer()
    else:
        log("ALL JOBS VERIFIED. Shutdown not requested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
