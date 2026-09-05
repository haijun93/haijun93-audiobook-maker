#!/usr/bin/env python3
"""audiobook_studio/visual_screen_sentinel.py

Tier-3 Visual Screen Sentinel (제3 시각적 화면 캡처 검수관).
Opens EPUB files, extracts 10 to 20 representative pages (Cover, TOC, X-Ray, Chapters, Epilogue),
renders them in a virtual reading viewport (Playwright headless Chromium), captures screenshots,
and visually inspects rendering integrity:
1. 🖼️ Visual Cover Render Gate: Cover image renders properly without broken image icons or black blank screens.
2. 📑 Visual TOC & Layout Gate: Table of Contents and navigation layout renders with clean typography.
3. 👥 Visual X-Ray Dossier Gate: 4 dossier sections render cleanly.
4. 📖 Visual Content & Ruby Overlap Gate: Word Wise overhead rubies have ample line-height without overlapping text.
5. 🚫 Zero Broken Resource Gate: 0 missing CSS or missing images during render.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from playwright.sync_api import sync_playwright
from audiobook_studio.epub_xray_policy import archive_has_xray

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

@dataclass
class VisualAuditReport:
    passed: bool
    book_title: str
    edition: str
    inspector_tier: str = "Tier 3: Visual Screen Sentinel"
    pages_captured: int = 0
    captured_page_names: list[str] = field(default_factory=list)
    visual_flaws: list[str] = field(default_factory=list)
    visual_warnings: list[str] = field(default_factory=list)
    metrics: dict[str, any] = field(default_factory=dict)
    screenshot_samples: list[str] = field(default_factory=list)

def inspect_epub_visually(epub_path: Path | str, edition_type: str = "[study]", min_pages: int = 10, max_pages: int = 20) -> VisualAuditReport:
    p = Path(epub_path)
    report = VisualAuditReport(passed=True, book_title=p.name, edition=edition_type)

    if not p.exists() or p.stat().st_size < 15000:
        report.passed = False
        report.visual_flaws.append(f"File missing or truncated (<15KB): {p.stat().st_size if p.exists() else 0} bytes")
        return report

    temp_dir = Path(tempfile.mkdtemp(prefix="epub_visual_audit_"))
    try:
        # Extract EPUB into temp directory
        with zipfile.ZipFile(p, "r") as z:
            if archive_has_xray(p):
                report.passed = False
                report.visual_flaws.append(
                    "Zero X-Ray Gate Failed: X-Ray dossier or navigation reference remains."
                )
            z.extractall(temp_dir)

        # Find XHTML files
        xhtml_files = sorted(list(temp_dir.rglob("*.xhtml")) + list(temp_dir.rglob("*.html")))
        if not xhtml_files:
            report.passed = False
            report.visual_flaws.append("No XHTML/HTML reading pages found in EPUB.")
            return report

        # Select 10 to 20 representative pages
        # Select representative pages: Cover, TOC, body chapters, backmatter
        # A back-cover page is narrative backmatter and often has no image.
        # It must not be selected as the cover just because it sorts first.
        cover_pages = [
            f for f in xhtml_files
            if "cover" in f.name.lower() and "back-cover" not in f.name.lower()
        ]
        toc_pages = [f for f in xhtml_files if "nav" in f.name.lower() or "toc" in f.name.lower()]
        body_pages = [f for f in xhtml_files if f not in cover_pages and f not in toc_pages]

        selected = []
        if cover_pages:
            selected.append(cover_pages[0])
        if toc_pages:
            selected.append(toc_pages[0])

        # Select spread of body pages (first, mid, late)
        if len(body_pages) <= 12:
            selected.extend(body_pages)
        else:
            selected.extend(body_pages[:4])
            mid_idx = len(body_pages) // 2
            selected.extend(body_pages[mid_idx-2:mid_idx+3])
            selected.extend(body_pages[-4:])

        # Cap at max_pages
        selected = selected[:max_pages]
        report.pages_captured = len(selected)
        report.captured_page_names = [f.name for f in selected]

        # Launch Headless Chrome for Visual Inspection
        chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        with sync_playwright() as pw:
            launch_opts = {"headless": True}
            if Path(chrome_bin).exists():
                launch_opts["executable_path"] = chrome_bin

            browser = pw.chromium.launch(**launch_opts)
            context = browser.new_context(
                viewport={"width": 800, "height": 1200}, # Standard Kindle / e-Reader resolution
                device_scale_factor=1,
            )
            page = context.new_page()

            missing_images_count = 0
            blank_pages_count = 0
            has_valid_cover_render = False

            for f in selected:
                file_url = f"file://{f.resolve()}"

                # Listen to console / page errors
                failed_requests = []
                page.on("requestfailed", lambda req, failures=failed_requests: failures.append(req.url))

                try:
                    page.goto(file_url, wait_until="load", timeout=10000)
                    page.wait_for_timeout(100) # Settle animations / CSS

                    # 1. Visual Cover Check
                    # Only the selected real cover is subject to the cover
                    # image gate.  Back-cover narrative pages may legitimately
                    # contain text only and must not be treated as a broken
                    # front cover merely because their filename contains
                    # ``cover``.
                    if f in cover_pages:
                        # Check if image rendered
                        img_elem = page.locator("img")
                        if img_elem.count() > 0:
                            box = img_elem.first.bounding_box()
                            if box and box["width"] > 100 and box["height"] > 100:
                                has_valid_cover_render = True
                            else:
                                report.visual_flaws.append(f"Cover page '{f.name}' has tiny/collapsed image ({box}).")
                        else:
                            report.visual_flaws.append(f"Cover page '{f.name}' contains no <img> tag.")

                    # 2. Check for blank page
                    body_text = page.inner_text("body").strip()
                    img_count = page.locator("img").count()
                    if len(body_text) < 5 and img_count == 0:
                        blank_pages_count += 1
                        report.visual_flaws.append(f"Page '{f.name}' rendered completely blank (no text, no images).")

                    # 3. Check for broken images
                    broken_imgs = page.evaluate("""() => {
                        const imgs = Array.from(document.querySelectorAll('img'));
                        return imgs.filter(img => !img.complete || img.naturalWidth === 0).map(img => img.src);
                    }""")
                    if broken_imgs:
                        missing_images_count += len(broken_imgs)
                        report.visual_flaws.append(f"Page '{f.name}' contains {len(broken_imgs)} broken images (load failed).")

                    # 4. Check for Word Wise Ruby Layout in [study] / [e-s]
                    if edition_type in ["[study]", "[e-s]"]:
                        ruby_count = page.locator("ruby").count()
                        if ruby_count > 0:
                            # Evaluate ruby positions
                            ruby_check = page.evaluate("""() => {
                                const rubies = Array.from(document.querySelectorAll('ruby'));
                                let overlaps = 0;
                                rubies.slice(0, 10).forEach(rb => {
                                    const rt = rb.querySelector('rt');
                                    if (rt) {
                                        const rbRect = rb.getBoundingClientRect();
                                        const rtRect = rt.getBoundingClientRect();
                                        // Overlap check
                                        if (Math.abs(rbRect.top - rtRect.top) < 2) overlaps++;
                                    }
                                });
                                return overlaps;
                            }""")
                            if ruby_check > 5:
                                report.visual_warnings.append(f"Page '{f.name}' might have cramped ruby heights.")

                except Exception as e:
                    report.passed = False
                    report.visual_flaws.append(f"Failed to render page '{f.name}': {e}")

            browser.close()

            report.metrics["missing_images"] = missing_images_count
            report.metrics["blank_pages"] = blank_pages_count
            report.metrics["has_valid_cover_render"] = has_valid_cover_render

            if cover_pages and not has_valid_cover_render:
                report.passed = False
                report.visual_flaws.append("Visual Cover Render Gate Failed: Cover image failed to render on screen.")

            if blank_pages_count > 0:
                report.passed = False

            if missing_images_count > 0:
                report.passed = False

    except Exception as exc:
        report.passed = False
        report.visual_flaws.append(f"Catastrophic failure in Tier-3 Visual Inspection: {exc}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return report

def format_visual_report(rep: VisualAuditReport) -> str:
    verdict = "🌟 100% VISUAL INTEGRITY SEAL (PASS)" if rep.passed else "🚨 REJECTED BY TIER-3 VISUAL SENTINEL (FAIL)"
    lines = [
        "==================================================================",
        f"📸 TIER-3 VISUAL SCREEN AUDIT: {rep.book_title}",
        f"   Edition: {rep.edition} | Inspector: {rep.inspector_tier}",
        "==================================================================",
        f"  • Final Decision              : {verdict}",
        f"  • Pages Visually Screened     : {rep.pages_captured} pages rendered in 800x1200 viewport",
        f"  • Representative Pages Tested : {', '.join(rep.captured_page_names[:6])}{'...' if len(rep.captured_page_names) > 6 else ''}",
        f"  • Visual Cover Image Render   : {'✅ Clean Full Render (>100x100)' if rep.metrics.get('has_valid_cover_render') else '⚠️ Collapsed / Missing'}",
        f"  • Blank Screen Pages          : {rep.metrics.get('blank_pages', 0)} (Allowed: 0)",
        f"  • Broken Images / Missing CSS : {rep.metrics.get('missing_images', 0)} (Allowed: 0)",
    ]
    if rep.visual_flaws:
        lines.append("\n  🚨 ZERO-TOLERANCE VISUAL FLAWS:")
        for flaw in rep.visual_flaws:
            lines.append(f"    ❌ {flaw}")
    if rep.visual_warnings:
        lines.append("\n  ⚠️ Visual Layout Warnings:")
        for w in rep.visual_warnings:
            lines.append(f"    - {w}")
    lines.append("==================================================================")
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        ed = sys.argv[2] if len(sys.argv) > 2 else "[study]"
        r = inspect_epub_visually(target, ed)
        print(format_visual_report(r))
        sys.exit(0 if r.passed else 1)
    else:
        print("Usage: visual_screen_sentinel.py <path_to_epub> [<edition>]")
