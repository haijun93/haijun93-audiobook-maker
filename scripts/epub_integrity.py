#!/usr/bin/env python3
"""Structural integrity checks shared by EPUB builders and batch workflows."""

from __future__ import annotations

import html
import posixpath
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

from safe_xml import safe_fromstring


EPUB_MIMETYPE = b"application/epub+zip"
MAX_MEMBER_COUNT = 10_000
MAX_MEMBER_SIZE = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_SIZE = 2 * 1024 * 1024 * 1024


@dataclass
class EpubIntegrityReport:
    path: str
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    member_count: int = 0
    total_uncompressed_size: int = 0
    rootfile: str = ""
    manifest_items: int = 0
    spine_items: int = 0
    nav_links: int = 0
    ncx_links: int = 0
    cover_images: int = 0

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "valid": self.valid}


def _add_unique(items: list[str], message: str) -> None:
    if message not in items:
        items.append(message)


def _safe_member_name(name: str) -> bool:
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        return False
    normalized = posixpath.normpath(name)
    return normalized not in {".", ".."} and not normalized.startswith("../")


def _resolve_reference(base_member: str, reference: str) -> tuple[str, str, bool, str]:
    value = html.unescape(reference or "").strip()
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return "", "", True, ""
    decoded_path = unquote(parsed.path)
    if decoded_path.startswith(("/", "\\")) or "\\" in decoded_path:
        return "", parsed.fragment, False, f"unsafe absolute reference: {reference}"
    if decoded_path:
        member = posixpath.normpath(posixpath.join(posixpath.dirname(base_member), decoded_path))
    else:
        member = base_member
    if not _safe_member_name(member):
        return "", parsed.fragment, False, f"unsafe relative reference: {reference}"
    return member, unquote(parsed.fragment), False, ""


def _element_ids(archive: zipfile.ZipFile, member: str, cache: dict[str, set[str]]) -> set[str]:
    if member not in cache:
        root = safe_fromstring(archive.read(member))
        cache[member] = {
            value
            for element in root.iter()
            for value in (element.attrib.get("id"), element.attrib.get("name"))
            if value
        }
    return cache[member]


def _validate_reference(
    archive: zipfile.ZipFile,
    names: set[str],
    *,
    base_member: str,
    reference: str,
    label: str,
    report: EpubIntegrityReport,
    id_cache: dict[str, set[str]],
) -> None:
    member, fragment, external, error = _resolve_reference(base_member, reference)
    if external:
        return
    if error:
        _add_unique(report.issues, f"{label}: {error}")
        return
    if member not in names:
        _add_unique(report.issues, f"{label}: missing target {member}")
        return
    if fragment:
        try:
            ids = _element_ids(archive, member, id_cache)
        except Exception as exc:
            _add_unique(report.issues, f"{label}: cannot parse fragment target {member}: {exc}")
            return
        if fragment not in ids:
            _add_unique(report.issues, f"{label}: missing fragment #{fragment} in {member}")


def validate_epub(
    path: Path,
    *,
    require_nav: bool = False,
    require_ncx: bool = False,
    require_cover: bool = False,
) -> EpubIntegrityReport:
    """Validate ZIP, package, manifest, spine, navigation, and cover references."""

    path = Path(path).expanduser().resolve()
    report = EpubIntegrityReport(path=str(path))
    if not path.is_file():
        report.issues.append("EPUB file does not exist")
        return report
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names_list = [info.filename for info in infos]
            names = set(names_list)
            report.member_count = len(infos)
            report.total_uncompressed_size = sum(info.file_size for info in infos)
            if len(names) != len(names_list):
                report.issues.append("ZIP contains duplicate member names")
            if report.member_count > MAX_MEMBER_COUNT:
                report.issues.append(f"ZIP member count exceeds limit: {report.member_count}")
            if report.total_uncompressed_size > MAX_TOTAL_UNCOMPRESSED_SIZE:
                report.issues.append(
                    f"ZIP uncompressed size exceeds limit: {report.total_uncompressed_size}"
                )
            oversized = [info.filename for info in infos if info.file_size > MAX_MEMBER_SIZE]
            if oversized:
                report.issues.append(f"ZIP member exceeds size limit: {oversized[0]}")
            unsafe = [name for name in names_list if not _safe_member_name(name)]
            if unsafe:
                report.issues.append(f"ZIP contains unsafe member path: {unsafe[0]}")
            if report.issues:
                return report

            if names_list[:1] != ["mimetype"]:
                report.issues.append("mimetype is not the first ZIP member")
            if "mimetype" not in names:
                report.issues.append("mimetype member is missing")
            else:
                mimetype_info = archive.getinfo("mimetype")
                if mimetype_info.compress_type != zipfile.ZIP_STORED:
                    report.issues.append("mimetype member is compressed")
                if archive.read("mimetype") != EPUB_MIMETYPE:
                    report.issues.append("mimetype value is invalid")
            bad_member = archive.testzip()
            if bad_member:
                report.issues.append(f"ZIP CRC failed: {bad_member}")
            if "META-INF/container.xml" not in names:
                report.issues.append("META-INF/container.xml is missing")
                return report

            try:
                container = safe_fromstring(archive.read("META-INF/container.xml"))
            except Exception as exc:
                report.issues.append(f"container.xml cannot be parsed safely: {exc}")
                return report
            rootfile = container.find(".//{*}rootfile")
            rootfile_path = str(rootfile.attrib.get("full-path") or "").strip() if rootfile is not None else ""
            if not _safe_member_name(rootfile_path):
                report.issues.append("container.xml has an invalid rootfile path")
                return report
            report.rootfile = rootfile_path
            if rootfile_path not in names:
                report.issues.append(f"package document is missing: {rootfile_path}")
                return report
            try:
                package = safe_fromstring(archive.read(rootfile_path))
            except Exception as exc:
                report.issues.append(f"package document cannot be parsed safely: {exc}")
                return report

            manifest_elements = package.findall(".//{*}manifest/{*}item")
            manifest = {
                str(item.attrib.get("id") or "").strip(): item
                for item in manifest_elements
                if str(item.attrib.get("id") or "").strip()
            }
            report.manifest_items = len(manifest)
            declared_manifest_ids = [
                str(item.attrib.get("id") or "").strip()
                for item in manifest_elements
                if str(item.attrib.get("id") or "").strip()
            ]
            if len(declared_manifest_ids) != len(set(declared_manifest_ids)):
                report.issues.append("package manifest contains duplicate IDs")
            id_cache: dict[str, set[str]] = {}
            resolved_manifest: dict[str, str] = {}
            for item_id, item in manifest.items():
                href = str(item.attrib.get("href") or "").strip()
                if not href:
                    _add_unique(report.issues, f"manifest item {item_id}: href is missing")
                    continue
                member, _fragment, external, error = _resolve_reference(rootfile_path, href)
                if error:
                    _add_unique(report.issues, f"manifest item {item_id}: {error}")
                elif external:
                    properties = str(item.attrib.get("properties") or "").split()
                    if "remote-resources" not in properties:
                        _add_unique(
                            report.warnings,
                            f"manifest item {item_id} uses an unmarked remote resource",
                        )
                elif member not in names:
                    _add_unique(report.issues, f"manifest item {item_id}: missing target {member}")
                else:
                    resolved_manifest[item_id] = member

            spine = package.find(".//{*}spine")
            itemrefs = spine.findall("{*}itemref") if spine is not None else []
            report.spine_items = len(itemrefs)
            if not itemrefs:
                report.issues.append("package spine is empty")
            for itemref in itemrefs:
                item_id = str(itemref.attrib.get("idref") or "").strip()
                if item_id not in manifest:
                    _add_unique(report.issues, f"spine references unknown manifest id: {item_id}")
                elif item_id not in resolved_manifest:
                    _add_unique(report.issues, f"spine target is unavailable: {item_id}")

            nav_items = [
                (item_id, item)
                for item_id, item in manifest.items()
                if "nav" in str(item.attrib.get("properties") or "").split()
            ]
            if require_nav and not nav_items:
                report.issues.append("EPUB navigation document is missing")
            for item_id, _item in nav_items:
                nav_member = resolved_manifest.get(item_id, "")
                if not nav_member:
                    continue
                try:
                    nav_root = safe_fromstring(archive.read(nav_member))
                except Exception as exc:
                    _add_unique(report.issues, f"navigation document cannot be parsed: {exc}")
                    continue
                for anchor in nav_root.findall(".//{*}a"):
                    href = str(anchor.attrib.get("href") or "").strip()
                    if not href:
                        continue
                    report.nav_links += 1
                    _validate_reference(
                        archive,
                        names,
                        base_member=nav_member,
                        reference=href,
                        label="navigation link",
                        report=report,
                        id_cache=id_cache,
                    )
            if require_nav and report.nav_links <= 0:
                report.issues.append("EPUB navigation document contains no links")

            ncx_ids: list[str] = []
            spine_toc = str(spine.attrib.get("toc") or "").strip() if spine is not None else ""
            if spine_toc:
                ncx_ids.append(spine_toc)
            ncx_ids.extend(
                item_id
                for item_id, item in manifest.items()
                if str(item.attrib.get("media-type") or "") == "application/x-dtbncx+xml"
                and item_id not in ncx_ids
            )
            if require_ncx and not ncx_ids:
                report.issues.append("EPUB NCX document is missing")
            for item_id in ncx_ids:
                ncx_member = resolved_manifest.get(item_id, "")
                if not ncx_member:
                    _add_unique(report.issues, f"NCX target is unavailable: {item_id}")
                    continue
                try:
                    ncx_root = safe_fromstring(archive.read(ncx_member))
                except Exception as exc:
                    _add_unique(report.issues, f"NCX document cannot be parsed: {exc}")
                    continue
                for content in ncx_root.findall(".//{*}content"):
                    source = str(content.attrib.get("src") or "").strip()
                    if not source:
                        continue
                    report.ncx_links += 1
                    _validate_reference(
                        archive,
                        names,
                        base_member=ncx_member,
                        reference=source,
                        label="NCX link",
                        report=report,
                        id_cache=id_cache,
                    )
            if require_ncx and report.ncx_links <= 0:
                report.issues.append("EPUB NCX document contains no links")

            cover_ids = {
                item_id
                for item_id, item in manifest.items()
                if "cover-image" in str(item.attrib.get("properties") or "").split()
            }
            for meta in package.findall(".//{*}metadata/{*}meta"):
                if str(meta.attrib.get("name") or "").lower() == "cover":
                    cover_id = str(meta.attrib.get("content") or "").strip()
                    if cover_id:
                        cover_ids.add(cover_id)
            for cover_id in cover_ids:
                item = manifest.get(cover_id)
                if item is None:
                    _add_unique(report.issues, f"cover metadata references unknown id: {cover_id}")
                    continue
                if cover_id not in resolved_manifest:
                    _add_unique(report.issues, f"cover image target is unavailable: {cover_id}")
                    continue
                media_type = str(item.attrib.get("media-type") or "")
                if not media_type.startswith("image/"):
                    _add_unique(report.issues, f"cover item is not an image: {cover_id}")
                    continue
                if archive.getinfo(resolved_manifest[cover_id]).file_size <= 0:
                    _add_unique(report.issues, f"cover image is empty: {cover_id}")
                    continue
                report.cover_images += 1
            if require_cover and report.cover_images <= 0:
                report.issues.append("EPUB cover image metadata is missing")
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        report.issues.append(f"EPUB cannot be validated: {exc}")
    return report
