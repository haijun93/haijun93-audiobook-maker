#!/usr/bin/env python3
"""Hardened XML parsing helpers for EPUB and Office documents."""

from __future__ import annotations

import html
import re
from os import PathLike
from typing import BinaryIO, TextIO
from xml.etree.ElementTree import Element, ElementTree
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException

XmlSource = str | bytes | PathLike[str] | PathLike[bytes] | BinaryIO | TextIO

HTML_ENTITY_RE = re.compile(r"&([a-zA-Z]+);")
ENTITY_DECL_RE = re.compile(r"<!ENTITY\b", re.IGNORECASE)

def _replace_entities(text: str) -> str:
    # Preserve standard XML entities
    def _sub(m: re.Match) -> str:
        ent = m.group(1)
        if ent in {"amp", "lt", "gt", "quot", "apos"}:
            return m.group(0)
        # Convert named HTML entity to numeric character entity
        val = html.entities.name2codepoint.get(ent)
        if val is not None:
            return f"&#{val};"
        return m.group(0)

    # First clean stray control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return HTML_ENTITY_RE.sub(_sub, text)

def safe_fromstring(data: str | bytes) -> Element:
    """Parse XML without expanding entities or loading external resources, with resilient fallback."""
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="ignore")

    # Never normalize or recover through an internal entity declaration.  Doing
    # so would let the permissive fallback hide the very payload this helper is
    # intended to reject.  External DTD declarations remain allowed for legacy
    # EPUB files; they are blocked from loading by defusedxml below.
    if ENTITY_DECL_RE.search(data):
        raise DefusedXmlException("XML entity declarations are forbidden")

    data = _replace_entities(data)

    try:
        return DefusedElementTree.fromstring(
            data.encode("utf-8"),
            forbid_dtd=False,
            forbid_entities=True,
            forbid_external=True,
        )
    except DefusedXmlException:
        raise
    except Exception:
        try:
            # Fallback 1: Strip XML declaration and try standard ElementTree
            cleaned = re.sub(r'^\s*<\?xml[^>]*\?>\s*', '', data)
            return ET.fromstring(cleaned.encode("utf-8"))
        except Exception:
            try:
                # Fallback 2: Parse via BeautifulSoup and serialize clean XML
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(data, "html.parser")
                clean_xml = str(soup)
                return ET.fromstring(clean_xml.encode("utf-8"))
            except Exception:
                # Ultimate fallback
                return ET.fromstring("<root></root>")

def safe_parse(source: XmlSource) -> ElementTree:
    """Parse an XML file with the same protections as :func:`safe_fromstring`."""
    if isinstance(source, (str, PathLike)):
        with open(source, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        root = safe_fromstring(content)
        return ElementTree(root)
    elif hasattr(source, "read"):
        content = source.read()
        root = safe_fromstring(content)
        return ElementTree(root)
    return DefusedElementTree.parse(
        source,
        forbid_dtd=False,
        forbid_entities=True,
        forbid_external=True,
    )
