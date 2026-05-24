#!/usr/bin/env python3

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document


BASE_DIR = Path("/Users/hyeokjunkong/Desktop/1차 시험/#STD/260416")
BACKUP_DIR = BASE_DIR / "backup"
TARGETS = [
    BASE_DIR / "[doc] labor_law_OX_integrated_2026_v1.docx",
    BASE_DIR / "[doc] social_insurance_law_OX_integrated_2026_v1.docx",
    BASE_DIR / "[doc] civil_law_OX_integrated_2026_v1.docx",
    BASE_DIR / "[doc] management_OX_integrated_2026_v1.docx",
]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def extract_explanation_parts(text: str) -> tuple[str, str, str | None] | None:
    if not text.startswith("해설:") or "핵심:" not in text:
        return None
    body = text[len("해설:") :].strip()
    prefix, tail = body.split("핵심:", 1)
    mnemonic_match = re.search(r"두문자:\s*(#[^\s]+)", tail)
    mnemonic = mnemonic_match.group(1) if mnemonic_match else None
    return normalize(prefix), normalize("핵심: " + tail), mnemonic


def shorten_repeated_explanations(docx_path: Path) -> tuple[int, Path]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{docx_path.stem}_backup_before_trim_{timestamp()}{docx_path.suffix}"
    shutil.copy2(docx_path, backup_path)

    doc = Document(docx_path)
    changed = 0
    last_tail = None

    for para in doc.paragraphs:
        text = para.text.strip()
        parsed = extract_explanation_parts(text)
        if parsed is None:
            continue
        prefix, tail, mnemonic = parsed
        if last_tail == tail:
            short = f"해설: {prefix} 같은 묶음 쟁점은 바로 앞 문항과 동일하다."
            if mnemonic:
                short += f" {mnemonic}만 다시 확인하면 된다."
            para.text = short
            changed += 1
        else:
            last_tail = tail

    doc.save(docx_path)
    return changed, backup_path


def main() -> int:
    for path in TARGETS:
        if not path.exists():
            raise SystemExit(f"파일을 찾지 못했습니다: {path}")

    for path in TARGETS:
        changed, backup_path = shorten_repeated_explanations(path)
        print(f"{path}")
        print(f"changed={changed}")
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
