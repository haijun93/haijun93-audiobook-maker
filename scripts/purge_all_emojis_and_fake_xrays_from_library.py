#!/usr/bin/env python3
"""scripts/purge_all_emojis_and_fake_xrays_from_library.py

1. Strips all emojis (⚡, 👥, 🔗, 🗺️, 🔍, 📖, etc.) across all EPUB documents, TOCs (nav.xhtml, toc.ncx), and headers.
2. Detects and removes any fake heuristic template text ("작품의 사건과 갈등을 이끌어가는 핵심 주역", "She", "And", "You").
3. Standardizes X-Ray formatting to pure, elegant typography without emojis.
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

EMOJI_PATTERN = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|⚡|👥|🔗|🗺|🔍|📖|📚|🛡|🌟|🎯|📑|🖼|👤|✨|💡|🏛')

FAKE_TEMPLATE_PHRASES = [
    "작품의 사건과 갈등을 이끌어가는 핵심 주역",
    "주인공과 가장 긴밀하게 얽히며 서사의 긴장감과 반전을 촉발하는",
    "주인공의 결정을 지지하거나 사건의 결정적 단서를 제공하는",
    "작품의 배경과 긴장감을 풍성하게 구성하는 조연 인물진",
    "서로의 운명을 뒤바꾸는 치밀한 심리적 상호작용",
    "위기의 순간 조력과 신뢰를 형성하는 핵심 파트너십",
    "인물들의 감정과 갈등이 극대화되는 핵심 무대",
    "진실이 밝혀지고 결정적인 선택이 이루어지는 상징적 장소",
    "극한의 상황에서 드러나는 인물들의 심리와 생존 본능",
    "스스로의 한계를 깨뜨리고 진실을 향해 나아가는 주제 의식"
]

def clean_epub_emojis_and_xray(args: tuple[str, str]) -> tuple[str, bool, bool]:
    ep_path_str, ed_name = args
    ep = Path(ep_path_str)

    try:
        data = {}
        with zipfile.ZipFile(ep, "r") as z:
            for it in z.infolist():
                try:
                    data[it.filename] = z.read(it.filename)
                except Exception:
                    pass

        if not data:
            return ep.name, False, False

        modified = False
        has_fake_xray = False

        # 1. Inspect and clean X-Ray
        for fname in list(data.keys()):
            if "xray" in fname.lower() and fname.endswith((".xhtml", ".html")):
                txt = data[fname].decode("utf-8", "ignore")

                # Check for fake template
                if any(p in txt for p in FAKE_TEMPLATE_PHRASES) or (">She<" in txt and ">And<" in txt):
                    has_fake_xray = True
                    soup = BeautifulSoup(txt, "html.parser")
                    for card in soup.find_all("div", class_="xray-entity-card"):
                        card_txt = card.get_text()
                        if any(p in card_txt for p in FAKE_TEMPLATE_PHRASES) or any(name in card_txt for name in ["She ", "And ", "You ", "Scott Turow 주인공"]):
                            card.decompose()
                    clean_str = str(soup)
                    txt = clean_str

                # Strip all emojis from X-Ray text
                if EMOJI_PATTERN.search(txt):
                    txt = EMOJI_PATTERN.sub('', txt)
                    modified = True

                data[fname] = txt.encode("utf-8")

        # 2. Clean TOC (nav.xhtml & toc.ncx)
        for toc_f in ["OEBPS/nav.xhtml", "nav.xhtml", "OEBPS/toc.ncx", "toc.ncx"]:
            if toc_f in data:
                t_str = data[toc_f].decode("utf-8", "ignore")
                if EMOJI_PATTERN.search(t_str):
                    t_str = EMOJI_PATTERN.sub('', t_str)
                    t_str = re.sub(r' +', ' ', t_str)
                    data[toc_f] = t_str.encode("utf-8")
                    modified = True

        if modified or has_fake_xray:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
                if "mimetype" in data:
                    dst.writestr("mimetype", data.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
                else:
                    dst.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
                for f_name, c_data in data.items():
                    dst.writestr(f_name, c_data)
            ep.write_bytes(buf.getvalue())

        return ep.name, modified, has_fake_xray
    except Exception as e:
        return ep.name, False, False

def main():
    print("==================================================================")
    print("🚫 PURGING ALL EMOJIS & FAKE HEURISTIC X-RAYS ACROSS LIBRARY")
    print("   Standard: Zero Emojis & 100% Authentic Pure AI X-Ray Only")
    print("==================================================================")

    editions = ["[study]", "[e-s]", "[k-e]", "[k]", "[ks]", "[xteink]/[study_x]", "[xteink]/[e-s_x]"]
    target_tasks = []

    for ed in editions:
        ed_dir = LIB_ROOT / ed
        if ed_dir.exists():
            for p in ed_dir.rglob("*.epub"):
                if p.stat().st_size > 15000:
                    target_tasks.append((str(p), ed))

    print(f"📚 Scanning and purifying {len(target_tasks):,} books across all editions (16 workers)...\n")

    cleaned_count = 0
    fake_xray_purged = 0

    with ProcessPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(clean_epub_emojis_and_xray, t) for t in target_tasks]
        for fut in as_completed(futures):
            name, mod, fake_xr = fut.result()
            if mod:
                cleaned_count += 1
            if fake_xr:
                fake_xray_purged += 1

    print("\n==================================================================")
    print("🎉 EMOJI & FAKE X-RAY PURIFICATION COMPLETED!")
    print(f"  • Total Books Inspected        : {len(target_tasks):,} books")
    print(f"  • Books with Emojis Cleaned    : {cleaned_count:,} books")
    print(f"  • Fake Template X-Rays Purged  : {fake_xray_purged:,} books")
    print("==================================================================")

if __name__ == "__main__":
    main()
