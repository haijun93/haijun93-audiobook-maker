#!/usr/bin/env python3
"""Create a final structural/content quality audit for generated study EPUBs."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from atomic_io import atomic_write_json, atomic_write_text
from epub_integrity import validate_epub
from remove_readrobe_text_from_epubs import WATERMARK_PATTERN
from safe_xml import safe_fromstring
from translation_quality_checks import assess_translations, count_refusal_markers


TEXT_SUFFIXES = (".xhtml", ".html", ".htm", ".opf", ".ncx")
MINIMUM_ACCEPTED_TRANSLATION_PIPELINE_VERSION = 2
FINAL_QUALITY_AUDIT_VERSION = 5


@dataclass
class CacheAudit:
    manifest_path: str = ""
    source_sections_path: str = ""
    source_block_count: int = 0
    manifest_block_count: int = 0
    manifest_chunk_count: int = 0
    manifest_pipeline_version: int = 0
    final_chunk_file_count: int = 0
    outdated_chunk_file_count: int = 0
    translation_file_count: int = 0
    translation_id_count: int = 0
    missing_translation_id_count: int = 0
    blank_translation_id_count: int = 0
    incomplete_final_chunk_count: int = 0
    severe_translation_quality_count: int = 0
    translation_quality_warning_count: int = 0
    invalid_translation_files: list[str] = field(default_factory=list)
    missing_translation_ids_sample: list[str] = field(default_factory=list)
    incomplete_final_chunks_sample: list[str] = field(default_factory=list)
    suspicious_translation_ids_sample: list[str] = field(default_factory=list)
    translation_quality_findings_sample: list[dict] = field(default_factory=list)


@dataclass
class EpubAudit:
    epub: str
    kind: str
    created_at: str
    audit_version: int = FINAL_QUALITY_AUDIT_VERSION
    size: int = 0
    mimetype_first: bool = False
    integrity_issue_count: int = 0
    integrity_warning_count: int = 0
    integrity_issues: list[str] = field(default_factory=list)
    integrity_warnings: list[str] = field(default_factory=list)
    xml_parse_error_count: int = 0
    xml_parse_errors: list[str] = field(default_factory=list)
    nav_items: int = 0
    ncx_points: int = 0
    missing_marker_count: int = 0
    readrobe_count: int = 0
    refusal_marker_count: int = 0
    pair_blocks: int = 0
    ko_blocks: int = 0
    en_blocks: int = 0
    old_inline_candidate_count: int = 0
    paired_translation_blocks: int = 0
    paired_translation_severe_count: int = 0
    paired_translation_warning_count: int = 0
    paired_translation_findings_sample: list[dict] = field(default_factory=list)
    tone_review_status: str = ""
    tone_review_report: str = ""
    dialogue_review_pass2_status: str = ""
    dialogue_review_pass2_report: str = ""
    dialogue_review_passes_completed: int = 0
    cache: CacheAudit = field(default_factory=CacheAudit)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "pass"
    report_path: str = ""
    json_path: str = ""


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", text).strip("_")
    return re.sub(r"_+", "_", slug)[:120] or "epub"


def read_text_files(archive: zipfile.ZipFile) -> dict[str, str]:
    texts: dict[str, str] = {}
    for name in archive.namelist():
        if name.lower().endswith(TEXT_SUFFIXES):
            texts[name] = archive.read(name).decode("utf-8", "replace")
    return texts


def count_class(text: str, class_name: str) -> int:
    count = 0
    for match in re.finditer(r"class=[\"']([^\"']+)[\"']", text):
        if class_name in match.group(1).split():
            count += 1
    return count


def count_lower(text: str, needle: str) -> int:
    return text.lower().count(needle.lower())


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def assess_epub_pairs(texts: dict[str, str]):
    sources: dict[str, str] = {}
    translations: dict[str, str] = {}
    for name, text in texts.items():
        if not name.lower().endswith((".xhtml", ".html", ".htm")):
            continue
        soup = BeautifulSoup(text, "xml")
        for index, pair in enumerate(soup.select(".pair"), start=1):
            english = pair.select_one(".en")
            korean = pair.select_one(".ko")
            if english is None or korean is None:
                continue
            english_text = english.get_text(" ", strip=True)
            korean_text = korean.get_text(" ", strip=True)
            if not english_text and not korean_text:
                continue
            block_id = f"EPUB:{name}:{index:05d}"
            sources[block_id] = english_text
            translations[block_id] = korean_text
    return assess_translations(sources, translations)


def source_blocks_from_sections(path: Path) -> list[tuple[str, str]]:
    payload = load_json(path)
    blocks: list[tuple[str, str]] = []
    for section in payload.get("sections", []):
        for block in section.get("blocks", []):
            block_id = str(block.get("id") or "")
            text = str(block.get("text") or "")
            if block_id:
                blocks.append((block_id, text))
    return blocks


def build_chunk_ids(blocks: list[tuple[str, str]], max_chars: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current_ids: list[str] = []
    current_len = 0
    for block_id, text in blocks:
        part = f"<<<{block_id}>>>\n{text}\n<<<END_{block_id}>>>"
        projected = current_len + len(part) + 2
        if current_ids and projected > max_chars:
            chunks.append(current_ids)
            current_ids = []
            current_len = 0
        current_ids.append(block_id)
        current_len += len(part) + 2
    if current_ids:
        chunks.append(current_ids)
    return chunks


def audit_cache(work_dir: Path | None) -> CacheAudit:
    audit = CacheAudit()
    if not work_dir:
        return audit
    work_dir = work_dir.expanduser().resolve()
    manifest_path = work_dir / "manifest.json"
    sections_path = work_dir / "source_sections.json"
    audit.manifest_path = str(manifest_path) if manifest_path.exists() else ""
    audit.source_sections_path = str(sections_path) if sections_path.exists() else ""

    manifest = load_json(manifest_path)
    audit.manifest_block_count = int(manifest.get("block_count") or 0)
    audit.manifest_chunk_count = int(manifest.get("chunk_count") or 0)
    audit.manifest_pipeline_version = int(manifest.get("translation_pipeline_version") or 0)
    max_chars = max(2000, int(manifest.get("max_chars_per_chunk") or 6000))

    blocks = source_blocks_from_sections(sections_path) if sections_path.exists() else []
    audit.source_block_count = len(blocks)
    source_ids = [block_id for block_id, _text in blocks]

    translations_dir = work_dir / "translations"
    final_chunk_pattern = re.compile(r"chunk_\d{4}\.json$")
    final_chunk_files = []
    translations: dict[str, str] = {}
    if translations_dir.exists():
        for path in sorted(translations_dir.glob("chunk_*.json")):
            audit.translation_file_count += 1
            if final_chunk_pattern.fullmatch(path.name):
                final_chunk_files.append(path)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                audit.invalid_translation_files.append(str(path))
                continue
            is_final_chunk = final_chunk_pattern.fullmatch(path.name) is not None
            cached = payload.get("translations", {})
            if is_final_chunk:
                chunk_version = int(payload.get("pipeline_version") or 0)
                if chunk_version < MINIMUM_ACCEPTED_TRANSLATION_PIPELINE_VERSION:
                    audit.outdated_chunk_file_count += 1
            if is_final_chunk and isinstance(cached, dict):
                for block_id, text in cached.items():
                    translations[str(block_id)] = str(text or "")
    audit.final_chunk_file_count = len(final_chunk_files)
    audit.translation_id_count = len([block_id for block_id, text in translations.items() if text])

    if source_ids:
        missing = [block_id for block_id in source_ids if not translations.get(block_id)]
        blank = [block_id for block_id in source_ids if block_id in translations and not translations.get(block_id)]
        audit.missing_translation_id_count = len(missing)
        audit.blank_translation_id_count = len(blank)
        audit.missing_translation_ids_sample = missing[:40]

        for index, block_ids in enumerate(build_chunk_ids(blocks, max_chars), start=1):
            chunk_path = translations_dir / f"chunk_{index:04d}.json"
            payload = load_json(chunk_path)
            cached = payload.get("translations", {}) if isinstance(payload, dict) else {}
            if not isinstance(cached, dict) or any(not cached.get(block_id) for block_id in block_ids):
                audit.incomplete_final_chunk_count += 1
                if len(audit.incomplete_final_chunks_sample) < 40:
                    audit.incomplete_final_chunks_sample.append(chunk_path.name)
        assessment = assess_translations(dict(blocks), translations)
        audit.severe_translation_quality_count = assessment.severe_count
        audit.translation_quality_warning_count = assessment.warning_count
        audit.suspicious_translation_ids_sample = assessment.severe_ids[:40]
        audit.translation_quality_findings_sample = [
            {
                "block_id": finding.block_id,
                "severity": finding.severity,
                "code": finding.code,
                "detail": finding.detail,
            }
            for finding in assessment.findings[:60]
        ]
    return audit


def audit_epub(epub_path: Path, *, kind: str, work_dir: Path | None) -> EpubAudit:
    epub_path = epub_path.expanduser().resolve()
    audit = EpubAudit(
        epub=str(epub_path),
        kind=kind,
        created_at=datetime.now().isoformat(timespec="seconds"),
        size=epub_path.stat().st_size if epub_path.exists() else 0,
    )
    if not epub_path.exists():
        audit.issues.append("EPUB 파일이 없습니다.")
        audit.status = "needs_attention"
        return audit

    integrity = validate_epub(
        epub_path,
        require_nav=True,
        require_ncx=True,
        require_cover=True,
    )
    audit.integrity_issues = integrity.issues
    audit.integrity_warnings = integrity.warnings
    audit.integrity_issue_count = len(integrity.issues)
    audit.integrity_warning_count = len(integrity.warnings)

    try:
        with zipfile.ZipFile(epub_path) as archive:
            names = archive.namelist()
            audit.mimetype_first = names[:1] == ["mimetype"]
            texts = read_text_files(archive)
    except Exception as exc:
        audit.issues.append(f"EPUB를 열 수 없습니다: {exc}")
        audit.status = "needs_attention"
        return audit

    for name, text in texts.items():
        try:
            safe_fromstring(text.encode("utf-8"))
        except Exception as exc:
            audit.xml_parse_error_count += 1
            if len(audit.xml_parse_errors) < 20:
                audit.xml_parse_errors.append(f"{name}: {exc}")

        lower_name = name.lower()
        if lower_name.endswith("nav.xhtml"):
            audit.nav_items += text.count("<li")
        if lower_name.endswith(".ncx"):
            audit.ncx_points += text.count("<navPoint")
        audit.missing_marker_count += text.count("[번역 누락]")
        audit.readrobe_count += len(WATERMARK_PATTERN.findall(text))
        audit.pair_blocks += count_class(text, "pair")
        audit.ko_blocks += count_class(text, "ko")
        audit.en_blocks += count_class(text, "en")
        audit.refusal_marker_count += count_refusal_markers(text)
        audit.old_inline_candidate_count += len(re.findall(r"[가-힣][^<]{0,220}\([A-Za-z][^)]{20,}\)", text))

    audit.cache = audit_cache(work_dir)
    if kind == "k-e":
        pair_assessment = assess_epub_pairs(texts)
        audit.paired_translation_blocks = pair_assessment.checked_blocks
        audit.paired_translation_severe_count = pair_assessment.severe_count
        audit.paired_translation_warning_count = pair_assessment.warning_count
        audit.paired_translation_findings_sample = [
            {
                "block_id": finding.block_id,
                "severity": finding.severity,
                "code": finding.code,
                "detail": finding.detail,
            }
            for finding in pair_assessment.findings[:60]
        ]
    if work_dir:
        tone_dir = work_dir.expanduser().resolve() / "final_tone_reviews"
        tone_json = tone_dir / f"{safe_slug(epub_path.stem)}.tone_review_latest.json"
        if not tone_json.exists() and tone_dir.exists():
            prefix = "k-e_" if kind == "k-e" else "k_"
            candidates = [
                path
                for path in tone_dir.glob("*.tone_review_latest.json")
                if path.name.lower().startswith(prefix)
            ]
            if candidates:
                tone_json = max(candidates, key=lambda path: path.stat().st_mtime)
        tone_data = load_json(tone_json)
        audit.tone_review_status = str(tone_data.get("status") or "")
        audit.tone_review_report = str(tone_data.get("report_path") or "")
        pass2_dir = work_dir.expanduser().resolve() / "final_dialogue_reviews_pass2"
        pass2_json = pass2_dir / f"{safe_slug(epub_path.stem)}.dialogue_pass2_latest.json"
        if not pass2_json.exists() and pass2_dir.exists():
            prefix = "k-e_" if kind == "k-e" else "k_"
            candidates = [
                path
                for path in pass2_dir.glob("*.dialogue_pass2_latest.json")
                if path.name.lower().startswith(prefix)
            ]
            if candidates:
                pass2_json = max(candidates, key=lambda path: path.stat().st_mtime)
        pass2_data = load_json(pass2_json)
        audit.dialogue_review_pass2_status = str(pass2_data.get("status") or "")
        audit.dialogue_review_pass2_report = str(pass2_data.get("report_path") or "")
    audit.dialogue_review_passes_completed = int(bool(audit.tone_review_status)) + int(
        bool(audit.dialogue_review_pass2_status)
    )

    if not audit.mimetype_first:
        audit.issues.append("mimetype 항목이 EPUB 첫 번째 항목이 아닙니다.")
    if audit.integrity_issues:
        audit.issues.extend(
            f"EPUB 무결성: {message}"
            for message in audit.integrity_issues
            if f"EPUB 무결성: {message}" not in audit.issues
        )
    if audit.integrity_warnings:
        audit.warnings.extend(
            f"EPUB 무결성: {message}"
            for message in audit.integrity_warnings
            if f"EPUB 무결성: {message}" not in audit.warnings
        )
    if audit.xml_parse_error_count:
        audit.issues.append(f"XML 파싱 오류가 있습니다: {audit.xml_parse_error_count}개")
    if audit.nav_items <= 0 or audit.ncx_points <= 0:
        audit.issues.append(f"목차가 불완전합니다: nav={audit.nav_items}, ncx={audit.ncx_points}")
    if audit.missing_marker_count:
        audit.issues.append(f"[번역 누락] 표시가 남아 있습니다: {audit.missing_marker_count}개")
    if audit.readrobe_count:
        audit.issues.append(f"readrobe.com/리드로브닷컴 문구가 남아 있습니다: {audit.readrobe_count}개")
    if audit.refusal_marker_count:
        audit.issues.append(f"웹 번역 서비스 거절/안전문구 잔여 후보가 있습니다: {audit.refusal_marker_count}개")
    if audit.paired_translation_severe_count:
        audit.issues.append(
            f"EPUB 한영쌍에서 미번역/과도한 축약/중복 후보가 있습니다: "
            f"{audit.paired_translation_severe_count}개"
        )
    if audit.paired_translation_warning_count:
        audit.warnings.append(
            f"EPUB 한영쌍에서 숫자·인용부호·길이 확인 후보가 있습니다: "
            f"{audit.paired_translation_warning_count}개"
        )

    if kind == "k-e":
        if audit.ko_blocks <= 0 or audit.en_blocks <= 0:
            audit.issues.append(f"한영 블록이 부족합니다: ko={audit.ko_blocks}, en={audit.en_blocks}")
        elif audit.ko_blocks != audit.en_blocks:
            audit.issues.append(f"한영 블록 수가 다릅니다: ko={audit.ko_blocks}, en={audit.en_blocks}")
        if audit.pair_blocks <= 0:
            audit.issues.append("최신 span/pair 방식의 한영쌍 블록을 찾지 못했습니다.")
    elif kind == "k":
        if audit.en_blocks or audit.pair_blocks:
            audit.issues.append(f"한글판에 영어학습 마크업이 남아 있습니다: en={audit.en_blocks}, pair={audit.pair_blocks}")
    else:
        audit.warnings.append(f"알 수 없는 kind 값입니다: {kind}")

    if audit.cache.source_block_count:
        if audit.cache.manifest_block_count and audit.cache.manifest_block_count != audit.cache.source_block_count:
            audit.warnings.append(
                f"manifest block_count와 source_sections 수가 다릅니다: "
                f"{audit.cache.manifest_block_count}/{audit.cache.source_block_count}"
            )
        if audit.cache.manifest_chunk_count and audit.cache.manifest_chunk_count != audit.cache.final_chunk_file_count:
            audit.issues.append(
                f"완성 chunk 파일 수가 manifest와 다릅니다: "
                f"{audit.cache.final_chunk_file_count}/{audit.cache.manifest_chunk_count}"
            )
        if audit.cache.missing_translation_id_count:
            audit.issues.append(f"번역 캐시에 누락된 원문 ID가 있습니다: {audit.cache.missing_translation_id_count}개")
        if audit.cache.incomplete_final_chunk_count:
            audit.issues.append(f"완성 chunk 파일 중 불완전한 항목이 있습니다: {audit.cache.incomplete_final_chunk_count}개")
        if audit.cache.invalid_translation_files:
            audit.issues.append(f"읽을 수 없는 번역 캐시 JSON이 있습니다: {len(audit.cache.invalid_translation_files)}개")
        if audit.cache.severe_translation_quality_count:
            audit.issues.append(
                f"미번역/과도한 축약/중복 등 고위험 번역 후보가 있습니다: "
                f"{audit.cache.severe_translation_quality_count}개"
            )
        if audit.cache.outdated_chunk_file_count:
            message = (
                f"이전 번역 파이프라인 캐시가 남아 있습니다: "
                f"{audit.cache.outdated_chunk_file_count}개"
            )
            if audit.cache.manifest_pipeline_version >= MINIMUM_ACCEPTED_TRANSLATION_PIPELINE_VERSION:
                audit.issues.append(message)
            else:
                audit.warnings.append(message)
        if audit.cache.translation_quality_warning_count:
            audit.warnings.append(
                f"숫자·인용부호·길이 비율 등 확인 후보가 있습니다: "
                f"{audit.cache.translation_quality_warning_count}개"
            )
    else:
        audit.warnings.append("source_sections.json이 없어 원문 ID 대조 검수는 건너뛰었습니다.")

    if not audit.tone_review_status:
        audit.issues.append("최종 인물관계/대화톤 검수 결과가 없습니다.")
    elif audit.tone_review_status == "needs_attention":
        audit.warnings.append("최종 대화톤 검수에서 추가 확인 후보가 발견되었습니다.")
    elif audit.tone_review_status not in {"checked", "pass"}:
        audit.issues.append(f"최종 대화톤 검수가 정상 완료되지 않았습니다: {audit.tone_review_status}")
    if not audit.dialogue_review_pass2_status:
        audit.issues.append("2차 대화 연속성 검수 결과가 없습니다.")
    elif audit.dialogue_review_pass2_status == "needs_attention":
        audit.warnings.append("2차 대화 연속성 검수에서 추가 확인 후보가 발견되었습니다.")
    elif audit.dialogue_review_pass2_status not in {"checked", "pass"}:
        audit.issues.append(
            f"2차 대화 연속성 검수가 정상 완료되지 않았습니다: {audit.dialogue_review_pass2_status}"
        )
    if audit.dialogue_review_passes_completed < 2:
        audit.issues.append(
            f"대화체 복수 검수가 완료되지 않았습니다: {audit.dialogue_review_passes_completed}/2"
        )

    audit.status = "needs_attention" if audit.issues else "pass"
    return audit


def render_markdown(audit: EpubAudit) -> str:
    lines = [
        "# Final EPUB Quality Audit",
        "",
        f"- EPUB: `{Path(audit.epub).name}`",
        f"- Kind: `{audit.kind}`",
        f"- Status: `{audit.status}`",
        f"- Created: `{audit.created_at}`",
        "",
        "## Structure",
        "",
        f"- mimetype first: `{audit.mimetype_first}`",
        f"- package/reference integrity: `issues={audit.integrity_issue_count}`, "
        f"`warnings={audit.integrity_warning_count}`",
        f"- XML parse errors: `{audit.xml_parse_error_count}`",
        f"- TOC: `nav={audit.nav_items}`, `ncx={audit.ncx_points}`",
        f"- Study blocks: `pair={audit.pair_blocks}`, `ko={audit.ko_blocks}`, `en={audit.en_blocks}`",
        f"- Residue: `missing={audit.missing_marker_count}`, `readrobe={audit.readrobe_count}`, `refusal={audit.refusal_marker_count}`",
        f"- Tone review: `{audit.tone_review_status or 'missing'}` (`{audit.tone_review_report or '-'}`)",
        f"- Dialogue review pass 2: `{audit.dialogue_review_pass2_status or 'missing'}` "
        f"(`{audit.dialogue_review_pass2_report or '-'}`)",
        f"- Dialogue review passes completed: `{audit.dialogue_review_passes_completed}/2`",
        f"- Paired translation audit: `blocks={audit.paired_translation_blocks}`, "
        f"`severe={audit.paired_translation_severe_count}`, `warnings={audit.paired_translation_warning_count}`",
        "",
        "## Translation Cache",
        "",
        f"- source blocks: `{audit.cache.source_block_count}`",
        f"- manifest blocks/chunks: `{audit.cache.manifest_block_count}` / `{audit.cache.manifest_chunk_count}`",
        f"- manifest pipeline version: `{audit.cache.manifest_pipeline_version}`",
        f"- translation files/final chunks: `{audit.cache.translation_file_count}` / `{audit.cache.final_chunk_file_count}`",
        f"- outdated final chunks: `{audit.cache.outdated_chunk_file_count}`",
        f"- translated IDs: `{audit.cache.translation_id_count}`",
        f"- missing IDs: `{audit.cache.missing_translation_id_count}`",
        f"- incomplete final chunks: `{audit.cache.incomplete_final_chunk_count}`",
        f"- severe translation quality findings: `{audit.cache.severe_translation_quality_count}`",
        f"- translation quality warnings: `{audit.cache.translation_quality_warning_count}`",
        "",
    ]
    if audit.issues:
        lines.extend(["## Issues", ""])
        lines.extend(f"- {issue}" for issue in audit.issues)
        lines.append("")
    if audit.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in audit.warnings)
        lines.append("")
    if audit.cache.missing_translation_ids_sample:
        lines.extend(["## Missing ID Sample", ""])
        lines.append(", ".join(f"`{item}`" for item in audit.cache.missing_translation_ids_sample))
        lines.append("")
    if audit.cache.incomplete_final_chunks_sample:
        lines.extend(["## Incomplete Chunk Sample", ""])
        lines.append(", ".join(f"`{item}`" for item in audit.cache.incomplete_final_chunks_sample))
        lines.append("")
    if audit.cache.suspicious_translation_ids_sample:
        lines.extend(["## Suspicious Translation ID Sample", ""])
        lines.append(", ".join(f"`{item}`" for item in audit.cache.suspicious_translation_ids_sample))
        lines.append("")
    if audit.paired_translation_findings_sample:
        lines.extend(["## EPUB Pair Translation Finding Sample", ""])
        for finding in audit.paired_translation_findings_sample[:30]:
            lines.append(
                f"- `{finding['block_id']}` `{finding['severity']}/{finding['code']}`: {finding['detail']}"
            )
        lines.append("")
    if audit.cache.translation_quality_findings_sample:
        lines.extend(["## Translation Quality Finding Sample", ""])
        for finding in audit.cache.translation_quality_findings_sample[:30]:
            lines.append(
                f"- `{finding['block_id']}` `{finding['severity']}/{finding['code']}`: {finding['detail']}"
            )
        lines.append("")
    if audit.xml_parse_errors:
        lines.extend(["## XML Parse Error Sample", ""])
        lines.extend(f"- `{item}`" for item in audit.xml_parse_errors)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(audit: EpubAudit, out_dir: Path) -> EpubAudit:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = safe_slug(Path(audit.epub).stem)
    report_path = out_dir / f"{stem}.quality_audit_{stamp}.md"
    json_path = out_dir / f"{stem}.quality_audit_{stamp}.json"
    latest_report = out_dir / f"{stem}.quality_audit_latest.md"
    latest_json = out_dir / f"{stem}.quality_audit_latest.json"
    audit.report_path = str(report_path)
    audit.json_path = str(json_path)
    payload = asdict(audit)
    atomic_write_json(json_path, payload)
    atomic_write_json(latest_json, payload)
    markdown = render_markdown(audit)
    atomic_write_text(report_path, markdown)
    atomic_write_text(latest_report, markdown)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Final quality audit for generated Korean/English EPUBs.")
    parser.add_argument("epub", type=Path)
    parser.add_argument("--kind", choices=("k-e", "k"), required=True)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--source-epub", type=Path, help="Reserved for audit traceability.")
    args = parser.parse_args()

    out_dir = args.out_dir or args.epub.expanduser().resolve().parent / "_quality_audits"
    audit = audit_epub(args.epub, kind=args.kind, work_dir=args.work_dir)
    audit = write_reports(audit, out_dir)
    print(
        json.dumps(
            {
                "status": audit.status,
                "report": audit.report_path,
                "json": audit.json_path,
                "issues": audit.issues,
                "warnings": audit.warnings,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
