#!/usr/bin/env python3
"""Claude AI Literary X-Ray Harvester & Injector for Fiction Library.

Connects to https://claude.ai to generate high-fidelity, deep literary X-Ray dossiers
(등장인물 심층 소개, 인물 관계도 및 심리 역학, 주요 배경 및 상징, 핵심 테마 및 용어 해설)
for all fiction novels across the library.

Caches structured dossiers in `data/fiction_xray_cache/` and injects them into
[k], [k-e], [study], [e-s], and [xteink] editions.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
import browser_cookie3

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
CACHE_DIR = ROOT / "data" / "fiction_xray_cache"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = Path.home() / "Library" / "Application Support" / "AudiobookStudio" / "browser_profiles" / "claude"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

from audiobook_studio.epub_xray_policy import purge_xray_from_epub

def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", s)

def load_cached_dossier(book_title: str, author: str) -> dict | None:
    slug = f"{slugify(author)}_{slugify(book_title)}"
    cache_file = CACHE_DIR / f"{slug}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_cached_dossier(book_title: str, author: str, data: dict):
    slug = f"{slugify(author)}_{slugify(book_title)}"
    cache_file = CACHE_DIR / f"{slug}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_cookies_for_playwright() -> list[dict]:
    try:
        cj = browser_cookie3.chrome()
        playwright_cookies = []
        for c in cj:
            if "claude.ai" in c.domain:
                cookie_dict = {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain if c.domain.startswith(".") else f".{c.domain}",
                    "path": c.path or "/",
                    "secure": bool(c.secure),
                    "httpOnly": bool(c.has_nonstandard_attr("HttpOnly")),
                }
                if c.expires:
                    cookie_dict["expires"] = int(c.expires)
                playwright_cookies.append(cookie_dict)
        return playwright_cookies
    except Exception as e:
        print(f"⚠️ Warning: Could not extract Chrome cookies automatically: {e}")
        return []

def build_claude_xray_prompt(title: str, author: str) -> str:
    clean_t = re.sub(r"^\[(study|e-s|ks|kindle|k|k-e|xteink)\]\s*", "", title)
    clean_t = re.sub(r"\s*\([^)]*\)$", "", clean_t).strip()

    return f"""다음 소설에 대한 독서 도우미 '킨들 X-Ray(등장인물 및 용어 도감)'을 작성해줘.
- 소설 제목: {clean_t}
- 작가: {author}

반드시 아래 4가지 항목을 100% 한국어로 충실하고 깊이 있게 작성하여 순수 JSON 포맷으로만 응답해줘:

{{
  "title": "{clean_t}",
  "author": "{author}",
  "characters": [
    ["인물명 (원어명)", "역할/신분", "성격, 배경, 행동 동기, 서사적 비중 상세 설명"],
    ["인물명 (원어명)", "역할/신분", "성격, 배경, 행동 동기, 서사적 비중 상세 설명"],
    ["인물명 (원어명)", "역할/신분", "성격, 배경, 행동 동기, 서사적 비중 상세 설명"],
    ["인물명 (원어명)", "역할/신분", "성격, 배경, 행동 동기, 서사적 비중 상세 설명"]
  ],
  "relationships": [
    "• 인물A ↔ 인물B: 핵심 대립/협력/애증 관계 및 심리적 갈등 상세 설명",
    "• 인물A ↔ 인물C: 비밀/신뢰/가족 관계 및 서사적 역학 설명",
    "• 전반적인 인물 간 긴장감과 갈등 구도 요약"
  ],
  "locations": [
    ["핵심 무대/장소명", "작품에서 갖는 공간적 의미, 분위기 및 사건 전개 배경 상세 설명"],
    ["주요 장소명", "작품에서 갖는 공간적 의미, 분위기 및 사건 전개 배경 상세 설명"]
  ],
  "themes": [
    ["핵심 주제 1", "소설을 관통하는 중심 메시지 및 인간 본성에 대한 통찰"],
    ["핵심 용어/복선 2", "세계관 이해에 필수적인 핵심 개념 또는 주요 복선 해설"]
  ]
}}
"""

def generate_xray_xhtml(dossier: dict) -> str:
    clean_t = dossier.get("title", "")
    author = dossier.get("author", "")

    char_cards_html = ""
    for item in dossier.get("characters", []):
        if len(item) >= 3:
            name, role, desc = item[0], item[1], item[2]
            char_cards_html += f'''  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{html.escape(name)}</span> <span class="xray-entity-role">{html.escape(role)}</span></div>
    <div class="xray-entity-desc">{html.escape(desc)}</div>
  </div>\n'''

    rel_items_html = ""
    for rel in dossier.get("relationships", []):
        rel_items_html += f'    <li style="margin-bottom: 0.6em; line-height: 1.6;">{html.escape(rel)}</li>\n'

    loc_cards_html = ""
    for item in dossier.get("locations", []):
        if len(item) >= 2:
            loc_name, loc_desc = item[0], item[1]
            char_cards_html += f'''  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{html.escape(loc_name)}</span> <span class="xray-entity-role">주요 무대</span></div>
    <div class="xray-entity-desc">{html.escape(loc_desc)}</div>
  </div>\n'''

    theme_cards_html = ""
    for item in dossier.get("themes", []):
        if len(item) >= 2:
            th_name, th_desc = item[0], item[1]
            theme_cards_html += f'''  <div class="xray-entity-card">
    <div><span class="xray-entity-name">{html.escape(th_name)}</span> <span class="xray-entity-role">핵심 테마</span></div>
    <div class="xray-entity-desc">{html.escape(th_desc)}</div>
  </div>\n'''

    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>⚡ Claude X-Ray: {html.escape(clean_t)}</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
  <style type="text/css">
    .xray-section {{ margin: 0 4%; padding-bottom: 3em; font-family: "Bookerly_KR", "Amazon Ember", sans-serif; }}
    .xray-header {{ text-align: center; margin: 1.5em 0 2em; border-bottom: 2px solid #0284c7; padding-bottom: 1em; }}
    .xray-header h1 {{ font-size: 1.55em; color: #0f172a; margin: 0 0 0.4em; }}
    .xray-header p {{ font-size: 0.9em; color: #64748b; margin: 0; }}
    .xray-box {{ background: rgba(2, 132, 199, 0.04); border: 1px solid rgba(2, 132, 199, 0.2); border-radius: 8px; padding: 1.2em; margin-bottom: 1.8em; }}
    .xray-box-title {{ font-size: 1.15em; font-weight: bold; color: #0284c7; margin-bottom: 0.8em; }}
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
    <p><strong>{html.escape(clean_t)}</strong> by <em>{html.escape(author)}</em></p>
  </div>

  <div class="xray-box">
    <div class="xray-box-title">👥 주요 등장인물 소개 (Major Characters)</div>
{char_cards_html}  </div>

  <div class="xray-box">
    <div class="xray-box-title">🔗 인물 관계도 및 핵심 갈등 (Relationships &amp; Dynamics)</div>
    <ul style="padding-left: 1.2em; margin: 0; color: #334155; font-size: 0.92em;">
{rel_items_html}    </ul>
  </div>

  <div class="xray-box">
    <div class="xray-box-title">🗺️ 주요 무대 및 공간적 배경 (Key Locations)</div>
{loc_cards_html}  </div>

  <div class="xray-box">
    <div class="xray-box-title">🔍 핵심 테마 및 세계관 해설 (Themes &amp; Terminology)</div>
{theme_cards_html}  </div>
</section>
</body>
</html>
'''

def inject_dossier_to_epub(epub_path: Path, dossier: dict) -> bool:
    # Compatibility shim: X-Ray generation is disabled by library policy.
    return purge_xray_from_epub(epub_path)
    # Legacy injection code below is intentionally unreachable.
    xray_xhtml = generate_xray_xhtml(dossier)
    tmp_file = None
    try:
        with zipfile.ZipFile(epub_path, "r") as zin:
            in_names = zin.namelist()
            fd, tmp_path_str = tempfile.mkstemp(suffix=".epub", dir=epub_path.parent)
            os.close(fd)
            tmp_file = Path(tmp_path_str)

            with zipfile.ZipFile(tmp_file, "w") as zout:
                zout.comment = zin.comment
                if "mimetype" in in_names:
                    zout.writestr(zipfile.ZipInfo("mimetype"), zin.read("mimetype"), compress_type=zipfile.ZIP_STORED)

                xray_path = "OEBPS/000-xray-dramatis-personae.xhtml" if any(n.startswith("OEBPS/") for n in in_names) else "000-xray-dramatis-personae.xhtml"
                zout.writestr(xray_path, xray_xhtml.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)

                for name in in_names:
                    if name == "mimetype" or name == xray_path:
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

def sync_dossier_to_all_editions(rel_path: Path, dossier: dict):
    # Apply to all 6 library editions
    for prefix in ["[k]", "[k-e]", "[study]", "[e-s]", "[xteink]/[study]", "[xteink]/[e-s]"]:
        target_p = LIB_ROOT / prefix / rel_path
        if target_p.exists():
            inject_dossier_to_epub(target_p, dossier)

if __name__ == "__main__":
    print("Claude AI Literary X-Ray Harvester module ready.")
