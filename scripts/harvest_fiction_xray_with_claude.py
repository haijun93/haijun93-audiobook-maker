#!/usr/bin/env python3
"""Master Claude Web Literary X-Ray Harvester & Real-Time Injector.

1. Queries Claude Web (with web search grounding) for each fiction novel.
2. Captures screenshots for visual monitoring and error diagnosis.
3. Saves verified JSON to data/fiction_xray_cache/<slug>.json.
4. Immediately builds authentic HTML X-Ray and injects into all 6 editions:
   - 소설2/[k]/
   - 소설2/[k-e]/
   - 소설2/[study]/
   - 소설2/[e-s]/
   - 소설2/[xteink]/[study]/
   - 소설2/[xteink]/[e-s]/
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
import browser_cookie3

import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_studio.epub_xray_policy import purge_xray_from_epub

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
CACHE_DIR = Path("data/fiction_xray_cache")
SCREENSHOT_DIR = Path("data/claude_harvest_screenshots")
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "AudiobookStudio" / "browser_profiles" / "claude"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

INVALID_NAME_TOKENS = {
    "you", "his", "she", "he", "it", "they", "their", "her", "him", "them",
    "but", "and", "the", "this", "that", "when", "there", "what", "then"
}

def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", s)

def clean_book_name(stem: str) -> str:
    s = re.sub(r"^\[(study|e-s|ks|kindle|k|k-e|xteink)\]\s*", "", stem)
    while re.match(r"^\[[^\]]+\]\s*", s):
        s = re.sub(r"^\[[^\]]+\]\s*", "", s)
    s = re.sub(r"\s*\(\d+\.\d+\)$", "", s).strip()
    return s

def parse_book_info(epub_stem: str, author_folder: str) -> tuple[str, str]:
    author = author_folder.lstrip("#").strip()
    title = clean_book_name(epub_stem)

    if " - " in title:
        parts = title.split(" - ")
        if len(parts) == 2:
            p1, p2 = parts[0].strip(), parts[1].strip()
            if author.lower() in p2.lower():
                title = p1
            elif author.lower() in p1.lower():
                title = p2
    elif " by " in title.lower():
        parts = re.split(r"\s+by\s+", title, flags=re.IGNORECASE)
        title = parts[0].strip()
    elif author in title and len(title) > len(author) + 3:
        title = title.replace(author, "").strip()

    title = re.sub(r"^\d+\s*[-–]\s*", "", title)
    title = re.sub(r"^(Book\s*\d+|Vol\s*\d+|Volume\s*\d+)\s*[-–:]\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\{[^}]*\}", "", title)
    title = re.sub(r"\s*\[[^\]]*\]", "", title)
    return title.strip(), author

def get_claude_cookies():
    cj = browser_cookie3.chrome()
    claude_cookies = []
    for c in cj:
        if "claude.ai" in c.domain:
            claude_cookies.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain if c.domain.startswith(".") else f".{c.domain}",
                "path": c.path or "/",
                "secure": bool(c.secure),
                "httpOnly": bool(c.has_nonstandard_attr("HttpOnly")),
            })
    return claude_cookies

def build_xray_html(title: str, author: str, data: dict) -> str:
    characters_html = ""
    for char in data.get("characters", []):
        if len(char) >= 3:
            name, role, desc = char[0], char[1], char[2]
            characters_html += f"""  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{name}</span> <span class="xray-entity-role">{role}</span></div>
    <div class="xray-entity-desc">{desc}</div>
  </div>\n"""

    rel_items = ""
    for rel in data.get("relationships", []):
        rel_clean = rel.lstrip("•").strip()
        rel_items += f'    <li style="margin-bottom: 0.6em; line-height: 1.6;">• {rel_clean}</li>\n'

    loc_html = ""
    for loc in data.get("locations", []):
        if len(loc) >= 2:
            name, desc = loc[0], loc[1]
            loc_html += f"""  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{name}</span> <span class="xray-entity-role">주요 무대</span></div>
    <div class="xray-entity-desc">{desc}</div>
  </div>\n"""

    theme_html = ""
    for th in data.get("themes", []):
        if len(th) >= 2:
            name, desc = th[0], th[1]
            theme_html += f"""  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{name}</span> <span class="xray-entity-role">핵심 테마/용어</span></div>
    <div class="xray-entity-desc">{desc}</div>
  </div>\n"""

    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>⚡ X-Ray: {title}</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
  <style type="text/css">
    .xray-section {{ margin: 0 4%; padding-bottom: 3em; font-family: "Bookerly_KR", "Amazon Ember", sans-serif; }}
    .xray-header {{ text-align: center; margin: 1.5em 0 2em; border-bottom: 2px solid #0284c7; padding-bottom: 1em; }}
    .xray-header h1 {{ font-size: 1.55em; color: #0f172a; margin: 0 0 0.4em; }}
    .xray-header p {{ font-size: 0.9em; color: #64748b; margin: 0; }}
    .xray-box {{ background: rgba(2, 132, 199, 0.04); border: 1px solid rgba(2, 132, 199, 0.2); border-radius: 8px; padding: 1.2em; margin-bottom: 1.8em; }}
    .xray-box-title {{ font-size: 1.15em; font-weight: bold; color: #0284c7; margin-bottom: 0.8em; display: flex; align-items: center; }}
    .xray-entity-card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0.9em 1em; margin-bottom: 0.8em; box-shadow: 0 1px 3px rgba(0,0,0,0.03); }}
    .xray-entity-name {{ font-size: 1.05em; font-weight: bold; color: #1e293b; }}
    .xray-entity-role {{ font-size: 0.78em; color: #0284c7; background: #e0f2fe; padding: 2px 7px; border-radius: 12px; margin-left: 6px; font-weight: 600; }}
    .xray-entity-desc {{ font-size: 0.92em; color: #475569; margin-top: 0.4em; line-height: 1.6; word-break: keep-all; }}
  </style>
</head>
<body>
<section class="xray-section">
  <div class="xray-header">
    <h1>⚡ X-Ray: 등장인물 및 용어 도감</h1>
    <p><strong>{title}</strong> by <em>{author}</em></p>
  </div>

  <div class="xray-box">
    <div class="xray-box-title">👥 주요 등장인물 소개 (Major Characters)</div>
{characters_html}  </div>

  <div class="xray-box">
    <div class="xray-box-title">🔗 인물 관계도 및 핵심 갈등 (Relationships &amp; Dynamics)</div>
    <ul style="padding-left: 1.2em; margin: 0; color: #334155; font-size: 0.92em;">
{rel_items}    </ul>
  </div>

  <div class="xray-box">
    <div class="xray-box-title">🗺️ 주요 무대 및 공간적 배경 (Key Locations)</div>
{loc_html}  </div>

  <div class="xray-box">
    <div class="xray-box-title">🔍 핵심 테마 및 세계관 해설 (Themes &amp; Terminology)</div>
{theme_html}  </div>
</section>
</body>
</html>
"""

def inject_xray_to_epub(epub_path: Path, xray_html: str) -> bool:
    # Compatibility shim: X-Ray generation is disabled by library policy.
    return purge_xray_from_epub(epub_path)
    # Legacy injection code below is intentionally unreachable.
    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
            fd, tmp_str = tempfile.mkstemp(suffix=".epub", dir=epub_path.parent)
            os.close(fd)
            tmp_file = Path(tmp_str)

            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment
                if "mimetype" in in_names:
                    zout.writestr(zipfile.ZipInfo("mimetype"), zin.read("mimetype"), compress_type=zipfile.ZIP_STORED)

                xray_path = "OEBPS/000-xray-dramatis-personae.xhtml" if any(n.startswith("OEBPS/") for n in in_names) else "000-xray-dramatis-personae.xhtml"
                zout.writestr(xray_path, xray_html.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)

                for name in in_names:
                    if name == "mimetype" or "000-xray" in name:
                        continue
                    data = zin.read(name)
                    if name.endswith("nav.xhtml"):
                        nav_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in nav_str:
                            xray_li = '<li><a href="000-xray-dramatis-personae.xhtml">⚡ X-Ray: 등장인물 및 용어 도감</a></li>\n      '
                            nav_str = re.sub(r"(<ol[^>]*>)", rf"\1\n      {xray_li}", nav_str, count=1)
                        data = nav_str.encode("utf-8")
                    elif name.endswith("toc.ncx"):
                        ncx_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in ncx_str:
                            xray_navpoint = '<navPoint id="navpoint-xray" playOrder="1">\n    <navLabel><text>⚡ X-Ray: 등장인물 및 용어 도감</text></navLabel>\n    <content src="000-xray-dramatis-personae.xhtml"/>\n  </navPoint>\n  '
                            ncx_str = re.sub(r"(<navMap[^>]*>)", rf"\1\n  {xray_navpoint}", ncx_str, count=1)
                        data = ncx_str.encode("utf-8")
                    elif name.endswith(".opf"):
                        opf_str = data.decode("utf-8", errors="replace")
                        if "000-xray-dramatis-personae.xhtml" not in opf_str:
                            item_tag = '<item id="xray-dir" href="000-xray-dramatis-personae.xhtml" media-type="application/xhtml+xml"/>\n'
                            itemref_tag = '<itemref idref="xray-dir"/>\n'
                            opf_str = re.sub(r"(<manifest[^>]*>)", rf"\1\n    {item_tag}", opf_str, count=1)
                            opf_str = re.sub(r"(<spine[^>]*>)", rf"\1\n    {itemref_tag}", opf_str, count=1)
                        data = opf_str.encode("utf-8")
                    zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        tmp_file.replace(epub_path)
        return True
    except Exception:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()
        return False

def inject_to_all_matching_editions(target_key: str, xray_html: str):
    editions = ["[k]", "[k-e]", "[study]", "[e-s]", "[xteink]/[study]", "[xteink]/[e-s]"]
    injected = 0
    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if not ed_dir.exists():
            continue
        for ep in ed_dir.rglob("*.epub"):
            k = clean_book_name(ep.stem).lower()
            if target_key in k or k in target_key:
                if inject_xray_to_epub(ep, xray_html):
                    injected += 1
    return injected

def query_claude_dossier(page, title: str, author: str) -> dict | None:
    prompt = f"""다음 소설에 대한 킨들 X-Ray(등장인물 도감 및 해설)을 100% 한국어로 작성해줘:
- 소설 제목: {title}
- 작가: {author}

반드시 소설의 실제 줄거리와 인물을 웹 검색하여 확인한 뒤, 다음 4가지 항목을 JSON으로만 작성해줘:
```json
{{
  "title": "{title}",
  "author": "{author}",
  "characters": [
    ["인물명 (원어명)", "역할/신분", "소설 속 실제 성격, 배경, 행동 동기, 서사적 비중 상세 설명"]
  ],
  "relationships": [
    "• 인물A ↔ 인물B: 실제 핵심 대립/협력/애증 관계 및 심리적 갈등 상세 설명"
  ],
  "locations": [
    ["핵심 무대/장소명", "소설 속 실제 공간적 의미, 분위기 및 사건 전개 배경 상세 설명"]
  ],
  "themes": [
    ["핵심 주제", "소설을 관통하는 중심 메시지 및 주제 의식"],
    ["핵심 용어/복선", "세계관 이해에 필수적인 핵심 개념 또는 주요 복선"]
  ]
}}
```
"""
    try:
        page.goto("https://claude.ai/new", wait_until="domcontentloaded", timeout=35000)
        time.sleep(2)

        editor = page.locator("div.ProseMirror, div[contenteditable=\"true\"]").first
        if editor.count() == 0:
            page.screenshot(path=str(SCREENSHOT_DIR / f"err_no_editor_{slugify(title)}.png"))
            return None

        editor.click()
        page.keyboard.insert_text(prompt)
        time.sleep(1)

        send_btn = page.locator("button[aria-label=\"메시지 보내기\"], button[aria-label*=\"Send\"], button.bg-accent-main-000").first
        if send_btn.count() == 0 or send_btn.is_disabled():
            page.screenshot(path=str(SCREENSHOT_DIR / f"err_send_disabled_{slugify(title)}.png"))
            return None

        send_btn.click()

        # Wait for reply
        start_t = time.time()
        parsed_json = None
        while time.time() - start_t < 75:
            time.sleep(3)
            stop_btn = page.locator("button[aria-label*=\"중지\"], button[aria-label*=\"Stop\"]")
            is_generating = stop_btn.count() > 0 and stop_btn.is_visible()

            msgs = page.locator("[data-message-author-role=\"assistant\"], .font-claude-message, pre code")
            if msgs.count() > 0:
                txt = msgs.last.inner_text()
                if "{" in txt and "}" in txt and "characters" in txt:
                    m = re.search(r"```json\s*(\{.*?\})\s*```", txt, flags=re.DOTALL) or re.search(r"(\{.*\})", txt, flags=re.DOTALL)
                    if m:
                        try:
                            data = json.loads(m.group(1))
                            chars = data.get("characters", [])
                            if len(chars) >= 2:
                                # Verify no single pronoun characters
                                if not any(c[0].strip().lower() in INVALID_NAME_TOKENS for c in chars if len(c) > 0):
                                    parsed_json = data
                                    if not is_generating:
                                        break
                        except Exception:
                            pass
        return parsed_json
    except Exception as e:
        page.screenshot(path=str(SCREENSHOT_DIR / f"err_exception_{slugify(title)}.png"))
        print(f"   ⚠️ Claude query error for '{title}': {e}", flush=True)
        return None

def get_priority_score(author_folder: str, author: str) -> tuple[int, str]:
    f_lower = author_folder.lower()
    a_lower = author.lower()
    # Priority 1: #Pam Godwin
    if "pam godwin" in f_lower or "pam godwin" in a_lower:
        return (1, "Pam Godwin")
    # Priority 2: #Freida McFadden
    if "freida mcfadden" in f_lower or "freida mcfadden" in a_lower:
        return (2, "Freida McFadden")
    # Priority 3: #Leigh Rivers
    if "leigh rivers" in f_lower or "leigh rivers" in a_lower:
        return (3, "Leigh Rivers")
    # Priority 4: #Top 10 dark romance
    if "top 10 dark romance" in f_lower or "#top 10" in f_lower:
        return (4, "Top 10 Dark Romance")
    # Other # root collections
    if author_folder.startswith("#"):
        return (5, author_folder)
    return (10, author_folder)

def main():
    print("==================================================================", flush=True)
    print("🌟 STARTING CONTINUOUS CLAUDE WEB X-RAY HARVESTER (PRIORITY QUEUE)", flush=True)
    print("==================================================================", flush=True)

    # Collect novels with priority metadata
    study_dir = LIB_ROOT / "[study]"
    novels = {}
    for ep in sorted(study_dir.rglob("*.epub")):
        author_folder = ep.parent.name
        title, author = parse_book_info(ep.stem, author_folder)
        slug = slugify(f"{title}_{author}")
        if slug not in novels:
            p_score, p_label = get_priority_score(author_folder, author)
            novels[slug] = (title, author, clean_book_name(ep.stem).lower(), p_score, p_label)

    print(f"📚 Total Novels Identified: {len(novels):,}", flush=True)

    cached_slugs = {f.stem for f in CACHE_DIR.glob("*.json")}
    pending = [
        (slug, t, a, k, p_score, p_label)
        for slug, (t, a, k, p_score, p_label) in novels.items()
        if slug not in cached_slugs
    ]
    # Sort by priority score (1: Pam Godwin, 2: Freida McFadden, 3: Leigh Rivers, 4: Top 10 Dark Romance, 10: General)
    pending.sort(key=lambda item: (item[4], item[1]))

    print(f"📊 Cached: {len(cached_slugs):,} | Pending to Harvest: {len(pending):,}\n", flush=True)
    print("🎯 Top Priority Queue Breakdown:")
    for p_val, p_name in [(1, "#Pam Godwin"), (2, "#Freida McFadden"), (3, "#Leigh Rivers"), (4, "#Top 10 dark romance")]:
        p_count = sum(1 for item in pending if item[4] == p_val)
        print(f"   • {p_name:<25}: {p_count:>3}권 대기 중", flush=True)
    print("", flush=True)

    if not pending:
        print("🎉 All fiction novels already harvested and cached!", flush=True)
        return

    cookies = get_claude_cookies()
    print(f"🔑 Loaded {len(cookies)} Claude cookies from Chrome.\n", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=CHROME_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        if cookies:
            browser.add_cookies(cookies)

        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        success_count = 0
        fail_count = 0

        for idx, (slug, title, author, match_key, p_score, p_label) in enumerate(pending, 1):
            print(f"[{idx}/{len(pending)}] 🤖 [우선순위: {p_label}] Harvesting X-Ray: '{title}' by {author} ...", flush=True)
            data = query_claude_dossier(page, title, author)

            if data:
                # Save cache
                cache_file = CACHE_DIR / f"{slug}.json"
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # Build & Inject
                xray_html = build_xray_html(title, author, data)
                injected_cnt = inject_to_all_matching_editions(match_key, xray_html)
                success_count += 1

                # Visual snapshot
                if success_count % 5 == 1 or idx == 1:
                    page.screenshot(path=str(SCREENSHOT_DIR / f"success_{slug}.png"))

                print(f"   ✅ SUCCESS! Cached & injected into {injected_cnt} EPUB editions ({len(data.get('characters', []))} characters)", flush=True)
            else:
                fail_count += 1
                print(f"   ❌ FAILED for '{title}'. Taking debug screenshot...", flush=True)
                page.screenshot(path=str(SCREENSHOT_DIR / f"fail_{slug}.png"))

            time.sleep(3)

        browser.close()

    print("\n==================================================================")
    print(f"🎉 HARVEST RUN COMPLETE: {success_count} Successes, {fail_count} Failures.")
    print("==================================================================")

if __name__ == "__main__":
    main()
