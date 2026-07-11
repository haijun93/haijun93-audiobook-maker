#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


SOURCE_DIR = Path("/Users/hyeokjunkong/Desktop/소설2")
BACKUP_DIR = SOURCE_DIR / "_manual_backups"

REPLACEMENTS = [
    ("“내 미래에 대해 이야기하러 왔어요.”", "“제 미래에 대해 이야기하러 왔어요.”"),
    ("내가 여기 있는 시간이나 당신이 집에 있는 시간이나 비슷하잖아.", "제가 여기 있는 시간이나 당신이 집에 있는 시간이나 비슷하잖아요."),
    ("“나는 프로 선수야.”", "“저는 프로 선수예요.”"),
    ("당신보다 잡지에 더 많이 나왔을걸.", "당신보다 잡지에 더 많이 나왔을걸요."),
    ("내 경력은 빛을 잃어요.", "제 경력은 빛을 잃어요."),
    ("“내가 어느 정도 해낼 수 있는지 시험해 보게 해줘요.”", "“제가 어느 정도 해낼 수 있는지 시험해 보게 해 주세요.”"),
    ("당신이 관심 있는 것들로 내가 뭘 할 수 있는지 보죠.", "당신이 관심 있는 것들로 제가 뭘 할 수 있는지 보죠."),
    ("내가 뭘 할 수 있는지 보자는 거죠.", "제가 뭘 할 수 있는지 보자는 거죠."),
    ("그러니까 당신한테 내가 필요하다는 거네요.", "그러니까 당신한테 제가 필요하다는 거네요."),
    ("“하지만 나는 당신 아들이야.”", "“하지만 저는 당신 아들이에요.”"),
    ("그게 당신을 두렵게 한다는 걸 알아.", "그게 당신을 두렵게 한다는 걸 알아요."),
    ("당신이 나를 통제할 수 없으니까.", "당신이 저를 통제할 수 없으니까요."),
    ("그런데 왜 그런지 알아?", "그런데 왜 그런지 아세요?"),
    ("우리가 똑같기 때문이야.", "우리가 똑같기 때문이에요."),
    ("당신이 내 안에서 싫어하는 바로 그 성향들을", "당신이 제 안에서 싫어하는 바로 그 성향들을"),
    ("당신은 스스로에게서는 가치 있다고 여기잖아.", "당신은 스스로에게서는 가치 있다고 여기잖아요."),
    ("당신은 트레버보다 나를 훨씬 더 존중해.", "당신은 트레버보다 저를 훨씬 더 존중해요."),
    ("“나는 아무것도 가져가지 않을 거예요.", "“저는 아무것도 가져가지 않을 거예요."),
    ("내가 관리하게 해줘요.", "제가 관리하게 해 주세요."),
    ("그리고 내가 잘해내면", "그리고 제가 잘해내면"),
    ("“왜 내가 아니죠?”", "“왜 저는 안 되죠?”"),
]


def rewrite_epub(path: Path, *, dry_run: bool = False) -> dict[str, object]:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{path.stem}.before_corrupt_honorifics_{timestamp}{path.suffix}"

    chapter_name = "OEBPS/chapter12.xhtml"
    counts: dict[str, int] = {}

    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        if chapter_name not in names:
            raise RuntimeError(f"{chapter_name} not found in {path}")
        chapter = archive.read(chapter_name).decode("utf-8")
        updated = chapter
        for old, new in REPLACEMENTS:
            count = updated.count(old)
            if count:
                updated = updated.replace(old, new)
            counts[old] = count
        changed = updated != chapter

        if dry_run or not changed:
            return {
                "path": str(path),
                "changed": changed,
                "backup": "",
                "replacement_hits": counts,
            }

        shutil.copy2(path, backup)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            with zipfile.ZipFile(tmp_path, "w") as output:
                for name in names:
                    data = updated.encode("utf-8") if name == chapter_name else archive.read(name)
                    info = archive.getinfo(name)
                    compress_type = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
                    new_info = zipfile.ZipInfo(name, date_time=info.date_time)
                    new_info.comment = info.comment
                    new_info.extra = info.extra
                    new_info.internal_attr = info.internal_attr
                    new_info.external_attr = info.external_attr
                    new_info.create_system = info.create_system
                    output.writestr(new_info, data, compress_type=compress_type)
            shutil.move(str(tmp_path), path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    return {
        "path": str(path),
        "changed": changed,
        "backup": str(backup),
        "replacement_hits": counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refine Corrupt chapter 12 father/son honorific consistency.")
    parser.add_argument("epubs", nargs="+", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import json

    results = [rewrite_epub(path, dry_run=args.dry_run) for path in args.epubs]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
