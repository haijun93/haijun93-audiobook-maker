#!/usr/bin/env python3
"""
Integrated Book Downloader Engine (OceanofPDF + Readrobe.com) for AudiobookStudio.

Features:
1. Multi-source search: OceanofPDF (Primary) -> Readrobe.com (Secondary fallback).
2. Auto watermark scrubbing via `remove_readrobe_text_from_epubs.py`.
3. Standard library output to `/Users/hyeokjunkong/Desktop/소설2/[e]/#Author/`.
4. Real-time state reporting to `.work/downloader_status.json` for Web Dashboard SSE.
5. Auto-queuing into Continuous Translation Scheduler.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

try:
    from remove_readrobe_text_from_epubs import scrub_epub
except ImportError:
    scrub_epub = None

LIBRARY_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
DEFAULT_E_ROOT = LIBRARY_ROOT / "[e]"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "AudiobookStudio" / "browser_profiles" / "integrated_downloader"
STATUS_FILE = ROOT / ".work" / "downloader_status.json"


def update_status(
    *,
    status: str,
    target: str,
    source: str = "-",
    detail: str = "",
    progress: str = "",
    recent_downloads: list[dict] | None = None,
    log_line: str = "",
) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    curr = {}
    if STATUS_FILE.exists():
        try:
            curr = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            curr = {}

    logs = curr.get("logs", [])
    if log_line:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{timestamp}] {log_line}")
        logs = logs[-50:]  # keep last 50 lines

    data = {
        "status": status,  # idle, searching, downloading, scrubbing, complete, error
        "target": target,
        "source": source,
        "detail": detail,
        "progress": progress,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "logs": logs,
        "recent_downloads": recent_downloads if recent_downloads is not None else curr.get("recent_downloads", []),
    }
    STATUS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_title(title: str) -> str:
    t = re.sub(r"\s+by\s+.*", "", title, flags=re.IGNORECASE).strip()
    t = re.sub(r"\b(PDF|EPUB)\b", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\[.*?\]", "", t).strip()
    t = re.sub(r"\(\d+\.\d+\)", "", t).strip()
    t = re.sub(r"[^\w\s]", "", t).strip().lower()
    return t


def get_owned_stems(dest_dir: Path) -> set[str]:
    owned = set()
    if dest_dir.exists():
        for p in dest_dir.rglob("*.epub"):
            owned.add(clean_title(p.stem))
    return owned


def is_english_title(title: str) -> bool:
    non_en = ["le ", "de ", "der ", "het ", "das ", "une ", "la ", "les ", "un "]
    tl = title.lower()
    return not any(tl.startswith(p) for p in non_en)


def extract_epub_title(epub_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            opfs = [n for n in z.namelist() if n.endswith(".opf")]
            if opfs:
                soup = BeautifulSoup(z.read(opfs[0]), "xml")
                t = soup.find(["dc:title", "title"])
                if t:
                    raw = t.get_text(strip=True)
                    raw = re.sub(r"\s+by\s+.*", "", raw, flags=re.IGNORECASE).strip()
                    raw = re.sub(r"\[.*?\]", "", raw).strip()
                    raw = re.sub(r":.*", "", raw).strip()
                    return raw
    except Exception:
        pass
    return None


def download_from_page(context, page, detail_url: str, download_dir: Path, timeout_sec: int = 35) -> Path | None:
    print(f"  Visiting detail page: {detail_url}...", flush=True)
    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        pass

    for _ in range(10):
        t = page.title()
        if "잠시만" not in t and "Just a moment" not in t:
            break
        time.sleep(1.5)

    form = page.locator("form:has(input[value*='.epub'])")
    if form.count() == 0:
        form = page.locator("form[action*='fetching'], form[action*='Fetching']")

    if form.count() > 0:
        btn = form.first.locator("input[type='image'], input[type='submit'], button")
        before_files = set(download_dir.iterdir()) if download_dir.exists() else set()

        try:
            # 1. Try popup tab download capture
            new_page = None
            try:
                with context.expect_page(timeout=10000) as new_page_info:
                    if btn.count() > 0:
                        btn.first.click(force=True)
                    else:
                        form.first.evaluate("f => f.submit()")
                new_page = new_page_info.value
            except Exception:
                pass

            if new_page:
                print(f"  Popup tab detected ({new_page.url}). Waiting for download stream...", flush=True)
                with new_page.expect_download(timeout=25000) as download_info:
                    time.sleep(1)
                dl = download_info.value
                temp_path = download_dir / dl.suggested_filename
                dl.save_as(str(temp_path))
                new_page.close()
                return temp_path
            else:
                # 2. Try direct page download capture
                with page.expect_download(timeout=25000) as download_info:
                    time.sleep(1)
                dl = download_info.value
                temp_path = download_dir / dl.suggested_filename
                dl.save_as(str(temp_path))
                return temp_path

        except Exception as e:
            # 3. Fallback: wait for countdown timer and staging scan
            print(f"  Event wait ended ({e}). Scanning staging directory after countdown...", flush=True)
            time.sleep(12)
            if download_dir.exists():
                after_files = set(download_dir.iterdir()) - before_files
                for f in after_files:
                    if f.is_file() and f.stat().st_size > 1000:
                        return f
    return None


def run_integrated_downloader(
    *,
    author: str,
    query: str | None = None,
    dest_dir: Path | None = None,
    source_choice: str = "all",  # "all", "oceanofpdf", "readrobe"
    max_pages: int = 5,
    auto_queue: bool = False,
    visible: bool = True,
) -> list[Path]:
    search_query = query or author
    target_author = author
    author_folder = f"#{target_author}" if not target_author.startswith("#") else target_author
    target_dir = dest_dir or (DEFAULT_E_ROOT / author_folder)
    target_dir.mkdir(parents=True, exist_ok=True)

    owned = get_owned_stems(target_dir)
    update_status(
        status="searching",
        target=f"{target_author} ({search_query})",
        source=source_choice.upper(),
        detail="검색 및 미보유 도서 탐색 시작",
        progress="0%",
        log_line=f"도서 탐색 시작: {target_author} (소스: {source_choice})",
    )

    temp_profile = Path(tempfile.mkdtemp())
    staging_dir = Path(tempfile.mkdtemp())
    downloaded_files: list[Path] = []
    recent_list = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(temp_profile),
            executable_path=CHROME_PATH,
            headless=not visible,
            accept_downloads=True,
            downloads_path=str(staging_dir),
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()

        candidate_links: list[tuple[str, str, str]] = []  # (title, url, source)

        # ── 1. Search OceanofPDF ──────────────────────────────────────
        if source_choice in {"all", "oceanofpdf"}:
            update_status(status="searching", target=target_author, source="OceanofPDF", detail="OceanofPDF 검색 중...")
            for page_idx in range(1, max_pages + 1):
                url = f"https://oceanofpdf.com/page/{page_idx}/?s={search_query.replace(' ', '+')}" if page_idx > 1 else f"https://oceanofpdf.com/?s={search_query.replace(' ', '+')}"
                print(f"[OceanofPDF Page {page_idx}] {url}", flush=True)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(3)
                    for _ in range(8):
                        if "잠시만" not in page.title() and "Just a moment" not in page.title():
                            break
                        time.sleep(1.5)

                    content = ""
                    for _ in range(5):
                        try:
                            content = page.content()
                            if content:
                                break
                        except Exception:
                            time.sleep(1.5)

                    soup = BeautifulSoup(content, "html.parser")
                    articles = soup.find_all("article")
                    if not articles:
                        break
                    for a in articles:
                        h = a.find(["h2", "h3", "h1"])
                        lk = a.find("a")
                        raw_t = h.get_text(strip=True) if h else (lk.get_text(strip=True) if lk else "")
                        href = lk.get("href") if lk else ""
                        if href and is_english_title(raw_t):
                            candidate_links.append((raw_t, href, "OceanofPDF"))
                            print(f"  [OceanofPDF] {raw_t}", flush=True)
                    if not soup.find("a", class_="next"):
                        break
                except Exception as e:
                    print(f"  OceanofPDF search error: {e}", flush=True)
                    break

        # ── 2. Search Readrobe.com ────────────────────────────────────
        if source_choice in {"all", "readrobe"}:
            update_status(status="searching", target=target_author, source="ReadRobe", detail="Readrobe.com 검색 중...")
            for page_idx in range(1, max_pages + 1):
                url = f"https://readrobe.com/page/{page_idx}/?s={search_query.replace(' ', '+')}" if page_idx > 1 else f"https://readrobe.com/?s={search_query.replace(' ', '+')}"
                print(f"[ReadRobe Page {page_idx}] {url}", flush=True)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(4)
                    soup = BeautifulSoup(page.content(), "html.parser")
                    items = soup.find_all(["article", "div", "li"], class_=lambda c: c and any(k in c for k in ["post", "book", "item", "entry"]))
                    found_any = False
                    for a in soup.find_all("a"):
                        raw_t = a.get_text(strip=True)
                        href = a.get("href", "")
                        if "download" in href and "authors" in href and is_english_title(raw_t):
                            candidate_links.append((raw_t, href, "ReadRobe"))
                            found_any = True
                            print(f"  [ReadRobe] {raw_t}", flush=True)
                    if not found_any or not soup.find("a", class_="next"):
                        break
                except Exception as e:
                    print(f"  ReadRobe search error: {e}", flush=True)
                    break

        # ── 3. Filter missing books ───────────────────────────────────
        seen_stems = set()
        missing_queue: list[tuple[str, str, str]] = []
        for raw_t, href, src in candidate_links:
            clean_s = clean_title(raw_t)
            if not clean_s or clean_s in seen_stems:
                continue
            seen_stems.add(clean_s)
            if not any(clean_s == o or clean_s in o or o in clean_s for o in owned):
                missing_queue.append((raw_t, href, src))
                print(f"  🎯 MISSING TO DOWNLOAD: {raw_t} ({src})", flush=True)

        print(f"\nTotal Missing Books To Download: {len(missing_queue)}\n", flush=True)
        update_status(
            status="downloading",
            target=target_author,
            source=source_choice.upper(),
            detail=f"미보유 도서 {len(missing_queue)}권 다운로드 시작",
            progress=f"0 / {len(missing_queue)}",
            log_line=f"미보유 도서 {len(missing_queue)}권 발견 -> 순차 다운로드 진행",
        )

        # ── 4. Download and Scrub ─────────────────────────────────────
        for idx, (raw_t, href, src) in enumerate(missing_queue, 1):
            update_status(
                status="downloading",
                target=f"{raw_t} ({src})",
                source=src,
                detail=f"[{idx}/{len(missing_queue)}] {raw_t} 다운로드 중...",
                progress=f"{idx} / {len(missing_queue)}",
                log_line=f"다운로드 시도 ({src}): {raw_t}",
            )
            try:
                temp_file = download_from_page(context, page, href, staging_dir)
                if temp_file and temp_file.exists() and temp_file.stat().st_size > 1000:
                    # Scrub watermark if readrobe/oceanofpdf
                    if scrub_epub:
                        try:
                            scrub_epub(temp_file)
                        except Exception as e:
                            print(f"  Watermark scrub note: {e}", flush=True)

                    epub_t = extract_epub_title(temp_file) or raw_t
                    clean_t = re.sub(r"\s+by\s+.*", "", epub_t, flags=re.IGNORECASE).strip()
                    clean_t = re.sub(r"\[.*?\]", "", clean_t).strip()
                    clean_t = re.sub(r":.*", "", clean_t).strip()

                    final_name = f"[e] {clean_t} - {target_author}.epub"
                    final_path = target_dir / final_name
                    shutil.copy2(temp_file, final_path)
                    print(f"  ✅ SUCCESS: Saved {final_path.name} ({final_path.stat().st_size:,} bytes)\n", flush=True)
                    downloaded_files.append(final_path)
                    owned.add(clean_title(raw_t))

                    recent_list.append({
                        "title": clean_t,
                        "author": target_author,
                        "source": src,
                        "file": final_name,
                        "size": f"{final_path.stat().st_size:,} B",
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })

                    update_status(
                        status="downloading",
                        target=clean_t,
                        source=src,
                        detail=f"저장 완료: {final_name}",
                        progress=f"{idx} / {len(missing_queue)}",
                        recent_downloads=recent_list,
                        log_line=f"✅ 저장 완료: {final_name} ({src})",
                    )
                else:
                    print(f"  ❌ Failed to download {raw_t} from {src}\n", flush=True)
                    update_status(
                        status="downloading",
                        target=raw_t,
                        source=src,
                        detail=f"다운로드 실패: {raw_t}",
                        progress=f"{idx} / {len(missing_queue)}",
                        log_line=f"❌ 다운로드 실패 ({src}): {raw_t}",
                    )
                time.sleep(2)
            except Exception as e:
                print(f"  Error on {raw_t}: {e}\n", flush=True)

        context.close()

    shutil.rmtree(staging_dir, ignore_errors=True)
    shutil.rmtree(temp_profile, ignore_errors=True)

    update_status(
        status="complete",
        target=target_author,
        source=source_choice.upper(),
        detail=f"총 {len(downloaded_files)}권 수집 완료",
        progress="100%",
        recent_downloads=recent_list,
        log_line=f"🎉 전체 작업 완료: 총 {len(downloaded_files)}권 서재 보관 완료",
    )

    return downloaded_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Integrated Book Downloader (OceanofPDF + ReadRobe)")
    parser.add_argument("--author", type=str, default="Freida McFadden", help="Author name to search")
    parser.add_argument("--query", type=str, default=None, help="Specific search title or query")
    parser.add_argument("--source", type=str, default="all", choices=["all", "oceanofpdf", "readrobe"], help="Source engine")
    parser.add_argument("--dest-dir", type=Path, default=None, help="Target library destination")
    parser.add_argument("--max-pages", type=int, default=5, help="Max search pages")
    parser.add_argument("--auto-queue", action="store_true", help="Queue into continuous translation scheduler")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    args = parser.parse_args()

    downloaded = run_integrated_downloader(
        author=args.author,
        query=args.query,
        dest_dir=args.dest_dir,
        source_choice=args.source,
        max_pages=args.max_pages,
        auto_queue=args.auto_queue,
        visible=not args.headless,
    )
    print("All downloaded paths:", [str(p) for p in downloaded])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
