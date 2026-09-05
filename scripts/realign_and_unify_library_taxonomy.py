#!/usr/bin/env python3
"""scripts/realign_and_unify_library_taxonomy.py

Realigns and unifies the entire library taxonomy across all 4 standard editions
([k], [k-e], [study], [e-s]) and [e] according to AGENTS.md & LIBRARY_CLASSIFICATION_STANDARD.md.

Rules:
1. Root dedicated author collections:
   - #Freida McFadden
   - #Pam Godwin
   - #Leigh Rivers
   - #Top 10 dark romance
   - #Paulo Coelho
   - #Patrick Süskind

2. All other authors/books must reside under their canonical Genre Subdirectory:
   - Fiction_Literary_Historical/#Author/
   - Mystery_Thriller_Crime/#Author/
   - Fantasy_Science_Fiction/#Author/
   - Romance_Contemporary/#Author/
   - Historical_Fiction/#Author/
   - Dark_Romance/#Author/
   - Biography_Memoir/#Author/
   - Nonfiction_History_Politics/#Author/
   - Business_Economics/#Author/
   - Young_Adult_Children/#Author/
   - Science_Nature_Technology/#Author/
   - Psychology_Self_Help/#Author/
   - Literary_General_Fiction/#Author/

3. 100% 1:1 Mirroring:
   Every book must have the EXACT SAME relative directory path across [k], [k-e], [study], [e-s], and [e].
"""

import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
EDITIONS = ["[k]", "[k-e]", "[study]", "[e-s]", "[e]"]

# Canonical Author -> Genre Mapping
CANONICAL_GENRES = {
    # Fiction_Literary_Historical
    "Hanya Yanagihara": "Fiction_Literary_Historical/#Hanya Yanagihara",
    "Gabrielle Zevin": "Fiction_Literary_Historical/#Gabrielle Zevin",
    "Barbara Kingsolver": "Fiction_Literary_Historical/#Barbara Kingsolver",
    "Fredrik Backman": "Fiction_Literary_Historical/#Fredrik Backman",
    "Khaled Hosseini": "Fiction_Literary_Historical/#Khaled Hosseini",
    "Ursula Rani Sarma": "Fiction_Literary_Historical/#Ursula Rani Sarma",
    "Arthur Golden": "Fiction_Literary_Historical/#Arthur Golden",
    "Ken Follett": "Fiction_Literary_Historical/#Ken Follett",
    "Markus Zusak": "Fiction_Literary_Historical/#Markus Zusak",
    "Paulo Coelho": "Fiction_Literary_Historical/#Paulo Coelho",
    "Patrick Süskind": "Fiction_Literary_Historical/#Patrick Süskind",
    "Patrick Suskind": "Fiction_Literary_Historical/#Patrick Süskind",

    # Mystery_Thriller_Crime
    "Alex Michaelides": "Mystery_Thriller_Crime/#Alex Michaelides",
    "Agatha Christie": "Mystery_Thriller_Crime/#Agatha Christie",
    "Keigo Higashino": "Mystery_Thriller_Crime/#Keigo Higashino",
    "Lisa Jewell": "Mystery_Thriller_Crime/#Lisa Jewell",
    "Stieg Larsson": "Mystery_Thriller_Crime/#Stieg Larsson",
    "Holly Jackson": "Mystery_Thriller_Crime/#Holly Jackson",
    "Harper Lee": "Mystery_Thriller_Crime/#Harper Lee",
    "Haper Lee": "Mystery_Thriller_Crime/#Harper Lee",
    "Gillian Flynn": "Mystery_Thriller_Crime/#Gillian Flynn",
    "Mike Omer": "Mystery_Thriller_Crime/#Mike Omer",
    "Paula Hawkins": "Mystery_Thriller_Crime/#Paula Hawkins",
    "Caroline Kepnes": "Mystery_Thriller_Crime/#Caroline Kepnes",
    "Patricia Cornwell": "Mystery_Thriller_Crime/#Patricia Cornwell",

    # Fantasy_Science_Fiction
    "Brandon Sanderson": "Fantasy_Science_Fiction/#Brandon Sanderson",
    "Suzanne Collins": "Fantasy_Science_Fiction/#Suzanne Collins",
    "Isaac Asimov": "Fantasy_Science_Fiction/#Isaac Asimov",
    "Guy Gavriel Kay": "Fantasy_Science_Fiction/#Guy Gavriel Kay",
    "Andy Weir": "Fantasy_Science_Fiction/#Andy Weir",
    "Matt Haig": "Fantasy_Science_Fiction/#Matt Haig",
    "JRR Tolkien": "Fantasy_Science_Fiction/#JRR Tolkien",
    "J.R.R. Tolkien": "Fantasy_Science_Fiction/#JRR Tolkien",
    "Kate DiCamillo": "Fantasy_Science_Fiction/#Kate DiCamillo",
    "Kristen Ciccarelli": "Fantasy_Science_Fiction/#Kristen Ciccarelli",

    # Romance_Contemporary & Romance
    "Abby Jimenez": "Romance_Contemporary/#Abby Jimenez",
    "Casey McQuiston": "Romance_Contemporary/#Casey McQuiston",
    "Ali Hazelwood": "Romance_Contemporary/#Ali Hazelwood",
    "Rebecca Yarros": "Romance_Contemporary/#Rebecca Yarros",
    "Elle Kennedy": "Romance_Contemporary/#Elle Kennedy",
    "Carley Fortune": "Romance_Contemporary/#Carley Fortune",
    "Rachel Winters": "Romance_Contemporary/#Rachel Winters",
    "Emily Henry": "Romance_Contemporary/#Emily Henry",

    # Historical_Fiction
    "Mark Sullivan": "Historical_Fiction/#Mark Sullivan",
    "Kristin Hannah": "Historical_Fiction/#Kristin Hannah",
    "Diana Gabaldon": "Historical_Fiction/#Diana Gabaldon",
    "Yael van der Wouden": "Historical_Fiction/#Yael van der Wouden",
    "Sarah Pinborough": "Historical_Fiction/#Sarah Pinborough",

    # Young_Adult_Children
    "R J Palacio": "Young_Adult_Children/#R J Palacio",
    "R. J. Palacio": "Young_Adult_Children/#R J Palacio",

    # Biography_Memoir
    "Jennette McCurdy": "Biography_Memoir/#Jennette McCurdy",
    "Jeannette Walls": "Biography_Memoir/#Jeannette Walls",
    "Matthew McConaughey": "Biography_Memoir/#Matthew McConaughey",
    "Elie Wiesel": "Biography_Memoir/#Elie Wiesel",
    "Tara Westover": "Biography_Memoir/#Tara Westover",
    "Viktor Frankl": "Biography_Memoir/#Viktor Frankl",
    "Frankl, Viktor": "Biography_Memoir/#Viktor Frankl",

    # Nonfiction_History_Politics & Business
    "Malcolm Gladwell": "Business_Economics/#Malcolm Gladwell",
    "Steven D. Levitt": "Business_Economics/#Steven D. Levitt",
    "Peter Thiel": "Business_Economics/#Peter Thiel",
    "Michael J. Sandel": "Nonfiction_History_Politics/#Michael J. Sandel",
    "John Berger": "Nonfiction_History_Politics/#John Berger",
    "Brian Kilmeade": "Nonfiction_History_Politics/#Brian Kilmeade",
    "Walter Isaacson": "Nonfiction_History_Politics/#Walter Isaacson",
    "Susan Cain": "Psychology_Self_Help/#Susan Cain",
    "Angela Duckworth": "Psychology_Self_Help/#Angela Duckworth",
    "Carl Sagan": "Science_Nature_Technology/#Carl Sagan",
    "Carl Edward Sagan": "Science_Nature_Technology/#Carl Sagan",

    # Dark_Romance
    "H D Carlton": "Dark_Romance/#H D Carlton",
    "H. D. Carlton": "Dark_Romance/#H D Carlton",
    "E L James": "Dark_Romance/#E L James",
    "Penelope Douglas": "Dark_Romance/#Penelope Douglas",
    "Navessa Allen": "Dark_Romance/#Navessa Allen",
    "Callie Hart": "Dark_Romance/#Callie Hart",
    "Lizzie B Brown": "Dark_Romance/#Lizzie B Brown",
    "L.J. Shen": "Dark_Romance/#L.J. Shen",
    "LJ Shen": "Dark_Romance/#L.J. Shen",
    "J.T. Geissinger": "Dark_Romance/#J.T. Geissinger",
    "JT Geissinger": "Dark_Romance/#J.T. Geissinger",

    # Dedicated Full-Catalogue Root Authors
    "Freida McFadden": "#Freida McFadden",
    "Pam Godwin": "#Pam Godwin",
    "Leigh Rivers": "#Leigh Rivers",
    "Top 10 dark romance": "#Top 10 dark romance",
}

ROOT_EXCEPTIONS = {
    "#Freida McFadden",
    "#Pam Godwin",
    "#Leigh Rivers",
    "#Top 10 dark romance",
}


def clean_book_key(name: str) -> str:
    clean = re.sub(r"^\[.*?\]\s*", "", name)
    clean = re.sub(r"\.epub$", "", clean, flags=re.IGNORECASE).strip().lower()
    return re.sub(r"[^a-zA-Z0-9가-힣]", "", clean)


def extract_author_from_filename(name: str) -> str | None:
    clean = re.sub(r"^\[.*?\]\s*", "", name)
    clean = re.sub(r"\.epub$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\(\d+\.\d+\)", "", clean).strip()

    # 1. Check known authors
    for auth in list(ROOT_EXCEPTIONS) + list(CANONICAL_GENRES.keys()):
        raw_auth = auth[1:] if auth.startswith("#") else auth
        if raw_auth.lower() in clean.lower():
            return raw_auth

    # 2. Check "by Author" or " - Author"
    if " by " in clean:
        return clean.split(" by ")[-1].strip()
    if " - " in clean:
        return clean.split(" - ")[-1].strip()

    return None

def determine_canonical_rel_dir(file_path: Path, current_rel_dir: Path) -> Path:
    """Determines the standard canonical destination folder for a book."""
    name = file_path.name
    str_path = str(file_path)

    # 1. Dedicated Full-Catalogue Root Authors (Strict Priority)
    for root_auth in ROOT_EXCEPTIONS:
        raw_name = root_auth[1:].lower()
        if root_auth in str_path or raw_name in name.lower():
            return Path(root_auth)

    # 2. Known Author to Canonical Genre Mapping
    for author, target_genre_folder in CANONICAL_GENRES.items():
        if author.lower() in name.lower() or f"#{author}".lower() in str_path.lower():
            return Path(target_genre_folder)

    # 3. Clean up dirty folders (#Author, Uncategorized)
    parts = list(current_rel_dir.parts)
    if parts:
        top = parts[0]
        if top in ["#Author", "Uncategorized", "General Authors"] or (len(parts) > 1 and parts[1] == "#Author"):
            extracted = extract_author_from_filename(name)
            if extracted and extracted in CANONICAL_GENRES:
                return Path(CANONICAL_GENRES[extracted])
            elif extracted:
                return Path("Literary_General_Fiction") / f"#{extracted}"

        # If top is a stray root author folder that was misplaced
        if top.startswith("#") and top not in ROOT_EXCEPTIONS:
            author_clean = top[1:].strip()
            if author_clean in CANONICAL_GENRES:
                return Path(CANONICAL_GENRES[author_clean])
            else:
                return Path("Literary_General_Fiction") / top

        # Normalize Romance -> Romance_Contemporary
        if top == "Romance":
            sub = parts[1:]
            return Path("Romance_Contemporary", *sub)

        # Normalize Non_Fiction_Memoir -> Biography_Memoir
        if top in ["Non_Fiction_Memoir", "Nonfiction_Memoir"]:
            sub = parts[1:]
            return Path("Biography_Memoir", *sub)

        # Ensure author subfolder has '#' prefix
        if len(parts) >= 2:
            genre = parts[0]
            auth_sub = parts[1]
            if not auth_sub.startswith("#"):
                return Path(genre) / f"#{auth_sub}"
            return current_rel_dir

        return current_rel_dir

    return Path("Literary_General_Fiction")


def realign_library(dry_run: bool = False):
    print("==================================================================")
    print(f"🌟 RE-ALIGNING & UNIFYING LIBRARY TAXONOMY (Dry Run: {dry_run})")
    print("==================================================================")

    # 1. Step 1: Scan all books across all editions to establish universal master directory for each book
    canonical_book_rel_dir = {}

    for ed in EDITIONS:
        ed_p = LIB_ROOT / ed
        if not ed_p.exists():
            continue
        for f in ed_p.rglob("*.epub"):
            if any(x.startswith(".") for x in f.parts) or "[backup_data]" in str(f):
                continue
            key = clean_book_key(f.name)
            current_rel = f.parent.relative_to(ed_p)
            canon_dir = determine_canonical_rel_dir(f, current_rel)
            if key not in canonical_book_rel_dir:
                canonical_book_rel_dir[key] = canon_dir

    print(f"Discovered {len(canonical_book_rel_dir)} unique book titles across library.")

    # 2. Step 2: Execute Re-alignment and 1:1 Mirroring in every edition
    moves_count = 0

    for ed in EDITIONS:
        ed_p = LIB_ROOT / ed
        if not ed_p.exists():
            continue
        print(f"\n📂 Processing Edition: {ed} ...")

        for f in list(ed_p.rglob("*.epub")):
            if any(x.startswith(".") for x in f.parts) or "[backup_data]" in str(f):
                continue
            key = clean_book_key(f.name)
            target_rel_dir = canonical_book_rel_dir.get(key)
            if not target_rel_dir:
                target_rel_dir = determine_canonical_rel_dir(f, f.parent.relative_to(ed_p))

            target_dir = ed_p / target_rel_dir
            target_path = target_dir / f.name

            if f != target_path:
                moves_count += 1
                if not dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(target_path))
                print(f"  🚚 [{ed:7s}] {f.relative_to(ed_p)}  ==>  {target_path.relative_to(ed_p)}")

    # 3. Step 3: Clean up empty directories
    if not dry_run:
        print("\n🧹 Cleaning up empty legacy directories...")
        for ed in EDITIONS:
            ed_p = LIB_ROOT / ed
            if not ed_p.exists():
                continue
            for p in sorted(ed_p.rglob("*"), reverse=True):
                if p.is_dir() and not any(p.iterdir()):
                    try:
                        p.rmdir()
                    except Exception:
                        pass

    print("\n==================================================================")
    print(f"🎉 Taxonomy Re-alignment Completed! Total Moves: {moves_count}")
    print("==================================================================")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    realign_library(dry_run=args.dry_run)
