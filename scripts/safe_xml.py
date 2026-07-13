#!/usr/bin/env python3
"""Hardened XML parsing helpers for EPUB and Office documents."""

from __future__ import annotations

from os import PathLike
from typing import BinaryIO, TextIO
from xml.etree.ElementTree import Element, ElementTree

from defusedxml import ElementTree as DefusedElementTree


XmlSource = str | bytes | PathLike[str] | PathLike[bytes] | BinaryIO | TextIO


def safe_fromstring(data: str | bytes) -> Element:
    """Parse XML while rejecting entities, DTDs, and external references."""

    return DefusedElementTree.fromstring(
        data,
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )


def safe_parse(source: XmlSource) -> ElementTree:
    """Parse an XML file with the same protections as :func:`safe_fromstring`."""

    return DefusedElementTree.parse(
        source,
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )
