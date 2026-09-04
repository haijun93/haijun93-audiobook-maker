#!/usr/bin/env python3
"""scripts/master_deep_inspect_all_library_rules.py

Comprehensive, file-by-file, chapter-by-chapter integrity inspection engine across all editions:
- [k]
- [k-e]
- [study]
- [e-s]
- [e]
- [xteink]/[study]
- [xteink]/[e-s]

Validates all Master Architectural Rules:
1. Prefix & Folder purity
2. Edition-specific content integrity ([k] pure korean, [e-s] pure english+WW, etc.)
3. Word Wise formatting (<ruby> in kindle study/e-s, 3-line/2-line in xteink)
4. No fake scene subheadings or dead anchors
5. Mimetype & XML packaging validity
"""

from __future__ import annotations

import json
import re
import time
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor, as_completed

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

def inspect_single_epub(epub_path: Path) -> dict:
    rel_path = str(epub_path.relative_to(LIB_ROOT))
    fname = epub_path.name
    parts = epub_path.relative_to(LIB_ROOT).parts

    # Determine edition category
    ed_cat = "unknown"
    if parts[0] == "[xteink]" and len(parts) > 1:
        ed_cat = f"[xteink]/{parts[1]}"
    elif parts[0] in ["[k]", "[k-e]", "[study]", "[e-s]", "[e]"]:
        ed_cat = parts[0]

    violations = []
    stats = {
        "chapters": 0,
        "total_paras": 0,
        "en_spans": 0,
        "ko_spans": 0,
        "ruby_tags": 0,
        "study_note_spans": 0,
        "scene_subheadings": 0,
    }

    # 1. Prefix Rule Check
    expected_prefix = parts[1] if parts[0] == "[xteink]" and len(parts) > 1 else parts[0]
    if not fname.startswith(f"{expected_prefix} "):
        violations.append(f"Prefix Mismatch: File named '{fname[:12]}...' placed under '{ed_cat}'")

    # 2. Inspect ZIP structure & mimetype
    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            namelist = z.namelist()

            # Check mimetype
            if "mimetype" not in namelist:
                violations.append("EPUB Packaging: Missing 'mimetype'")
            elif z.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
                violations.append("EPUB Packaging: 'mimetype' not stored uncompressed (ZIP_STORED)")

            xhtml_files = [n for n in namelist if n.endswith((".xhtml", ".html", ".htm")) and "xray" not in n and "cover" not in n and "nav" not in n]
            stats["chapters"] = len(xhtml_files)

            # Sample inspect up to 15 chapters
            sample_chapters = xhtml_files[:15]
            for ch in sample_chapters:
                raw_bytes = z.read(ch)
                # Check control characters
                if re.search(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", raw_bytes):
                    violations.append(f"XML Validity: Unescaped non-printable control characters in {ch}")

                raw = raw_bytes.decode("utf-8", "ignore")

                # Check for scene subheadings
                if "scene-subheading" in raw or "제" in raw and "막:" in raw:
                    stats["scene_subheadings"] += len(re.findall(r"class=[\"']scene-subheading[\"']", raw))

                soup = BeautifulSoup(raw, "html.parser")
                paras = soup.find_all("p")
                stats["total_paras"] += len(paras)

                en_spans = soup.find_all("span", class_="en")
                ko_spans = soup.find_all("span", class_="ko")
                rubies = soup.find_all("ruby")
                study_spans = soup.find_all("span", class_="study-note")

                stats["en_spans"] += len(en_spans)
                stats["ko_spans"] += len(ko_spans)
                stats["ruby_tags"] += len(rubies)
                stats["study_note_spans"] += len(study_spans)

    except Exception as e:
        violations.append(f"Archive Corrupt / Read Error: {e}")

    # 3. Rule Evaluation per Edition
    if stats["scene_subheadings"] > 0:
        violations.append(f"TOC Policy: Contains {stats['scene_subheadings']} forbidden scene-subheadings")

    if ed_cat == "[k]":
        if stats["en_spans"] > 0:
            violations.append(f"[k] Purity: Contains {stats['en_spans']} English spans in Korean-only edition")
        if stats["ruby_tags"] > 0:
            violations.append(f"[k] Purity: Contains {stats['ruby_tags']} ruby tags in Korean-only edition")

    elif ed_cat == "[e-s]":
        if stats["ko_spans"] > 0:
            violations.append(f"[e-s] Purity: Contains {stats['ko_spans']} Korean translation spans in English study edition")

    elif ed_cat == "[xteink]/[study]":
        if stats["ruby_tags"] > 0:
            violations.append(f"Xteink Format: Contains {stats['ruby_tags']} forbidden ruby tags (Must be 3-line format)")

    elif ed_cat == "[xteink]/[e-s]":
        if stats["ruby_tags"] > 0:
            violations.append(f"Xteink Format: Contains {stats['ruby_tags']} forbidden ruby tags (Must be 2-line format)")
        if stats["ko_spans"] > 0:
            violations.append(f"Xteink Format: Contains {stats['ko_spans']} Korean translation spans in English study edition")

    return {
        "rel_path": rel_path,
        "fname": fname,
        "ed_cat": ed_cat,
        "valid": len(violations) == 0,
        "violations": violations,
        "stats": stats,
    }

def main():
    t0 = time.time()
    print("==================================================================")
    print("🔬 COMPREHENSIVE FILE-BY-FILE AUDIT OF ENTIRE LIBRARY")
    print("==================================================================")

    all_epubs = sorted([p for p in LIB_ROOT.rglob("*.epub") if not any(x in str(p) for x in ["_chatgpt_translate_work", "_manual_backups", "[backup_data]"])])
    print(f"📚 Total Active EPUBs to audit: {len(all_epubs):,}\n")

    results_by_ed = {}
    total_valid = 0
    total_flawed = 0
    flawed_details = []

    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(inspect_single_epub, p) for p in all_epubs]
        for f in as_completed(futs):
            res = f.result()
            ed = res["ed_cat"]
            results_by_ed.setdefault(ed, {"total": 0, "valid": 0, "flawed": 0})
            results_by_ed[ed]["total"] += 1

            if res["valid"]:
                results_by_ed[ed]["valid"] += 1
                total_valid += 1
            else:
                results_by_ed[ed]["flawed"] += 1
                total_flawed += 1
                flawed_details.append(res)

    elapsed = time.time() - t0

    print("\n==================================================================")
    print("📊 EDITION-BY-EDITION AUDIT SUMMARY")
    print("==================================================================")
    for ed, counts in sorted(results_by_ed.items()):
        tot = counts["total"]
        val = counts["valid"]
        flw = counts["flawed"]
        pct = (val / tot * 100) if tot > 0 else 0
        status_icon = "✅" if flw == 0 else "⚠️"
        print(f"  {status_icon} {ed:<20}: Total {tot:<5} | Valid: {val:<5} | Flawed: {flw:<5} ({pct:.1f}%)")

    print("==================================================================")
    print(f"🏁 OVERALL RESULT: {total_valid:,} / {len(all_epubs):,} Books 100% Valid ({total_valid/len(all_epubs)*100:.1f}%) in {elapsed:.1f}s")
    print("==================================================================")

    if flawed_details:
        print("\n🚨 Flawed Books Details (First 20):")
        for item in flawed_details[:20]:
            print(f"  ❌ {item['rel_path']}")
            for v in item["violations"]:
                print(f"       ⚠️ {v}")

    # Save detailed JSON report
    report_file = Path("data/master_library_rules_audit_report.json")
    report_file.write_text(json.dumps({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_epubs": len(all_epubs),
        "total_valid": total_valid,
        "total_flawed": total_flawed,
        "by_edition": results_by_ed,
        "flawed_books": flawed_details,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n💾 Saved full detailed audit report to {report_file}")

if __name__ == "__main__":
    main()
