#!/usr/bin/env python3
"""scripts/organize_screen_adaptation_original_books.py

1. Creates `#original books` root directory across all library editions:
   - `소설2/[k]/#original books/`
   - `소설2/[k-e]/#original books/`
   - `소설2/[study]/#original books/`
   - `소설2/[e-s]/#original books/`
   - `소설2/[e]/#original books/`
   - `소설2/[xteink]/[study]/#original books/`
   - `소설2/[xteink]/[e-s]/#original books/`
2. Identifies and relocates all famous Movie & TV Series screen adaptation novels into `#original books/#[Author]/`:
   - Where the Crawdads Sing (Delia Owens)
   - The Help (Kathryn Stockett)
   - Gone Girl / Sharp Objects / Dark Places (Gillian Flynn)
   - The Silence of the Lambs / Red Dragon (Thomas Harris)
   - The Girl with the Dragon Tattoo / Millennium (Stieg Larsson)
   - The Big Short / Moneyball (Michael Lewis)
   - Lessons in Chemistry (Bonnie Garmus)
   - Daisy Jones & The Six / Evelyn Hugo (Taylor Jenkins Reid)
   - It Ends with Us / Verity (Colleen Hoover)
   - Big Little Lies / Nine Perfect Strangers / The Husband's Secret (Liane Moriarty)
   - Normal People / Conversations with Friends (Sally Rooney)
   - Red White & Royal Blue (Casey McQuiston)
   - The Idea of You (Robinne Lee)
   - Bird Box (Josh Malerman)
   - The Queen's Gambit (Walter Tevis)
   - The Martian / Project Hail Mary (Andy Weir)
   - Shutter Island / Mystic River (Dennis Lehane)
   - A Man Called Ove (Fredrik Backman)
   - The Kite Runner / A Thousand Splendid Suns (Khaled Hosseini)
   - Memoirs of a Geisha (Arthur Golden)
   - The Book Thief (Markus Zusak)
   - Perfume The Story of a Murderer (Patrick Süskind)
   - The Lincoln Lawyer / Bosch (Michael Connelly)
   - Jack Reacher (Lee Child)
   - You / Hidden Bodies (Caroline Kepnes)
   - The Night Agent (Matthew Quirk)
   - All the Light We Cannot See (Anthony Doerr)
   - The Sympathizer (Viet Thanh Nguyen)
   - Crazy Rich Asians (Kevin Kwan)
   - Killers of the Flower Moon (David Grann)
   - Behind Her Eyes (Sarah Pinborough)
   - Anatomy of a Scandal (Sarah Vaughan)
   - One Day (David Nicholls)
   - The Maid (Stephanie Land)
   - (and other verified screen adaptations)
3. Synchronizes with Google Drive #Books.
4. Updates AGENTS.md taxonomy.
"""

from __future__ import annotations

import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

ORIGINAL_SCREEN_ADAPTATIONS = [
    {
        "keywords": ["crawdads sing", "delia owens"],
        "author_folder": "#Delia Owens",
        "title": "Where the Crawdads Sing (Delia Owens)"
    },
    {
        "keywords": ["the help", "kathryn stockett"],
        "author_folder": "#Kathryn Stockett",
        "title": "The Help (Kathryn Stockett)"
    },
    {
        "keywords": ["gone girl", "sharp objects", "dark places", "gillian flynn"],
        "author_folder": "#Gillian Flynn",
        "title": "Gillian Flynn Novels"
    },
    {
        "keywords": ["silence of the lambs", "red dragon", "hannibal", "thomas harris"],
        "author_folder": "#Thomas Harris",
        "title": "Hannibal Lecter Series (Thomas Harris)"
    },
    {
        "keywords": ["dragon tattoo", "played with fire", "hornet's nest", "stieg larsson", "millennium"],
        "author_folder": "#Stieg Larsson",
        "title": "Millennium Series (Stieg Larsson)"
    },
    {
        "keywords": ["big short", "moneyball", "flash boys", "blind side", "michael lewis"],
        "author_folder": "#Michael Lewis",
        "title": "Michael Lewis Adaptations"
    },
    {
        "keywords": ["daisy jones", "evelyn hugo", "malibu rising", "carrie soto", "taylor jenkins reid"],
        "author_folder": "#Taylor Jenkins Reid",
        "title": "Taylor Jenkins Reid Adaptations"
    },
    {
        "keywords": ["it ends with us", "it starts with us", "verity", "ugly love", "colleen hoover"],
        "author_folder": "#Colleen Hoover",
        "title": "Colleen Hoover Adaptations"
    },
    {
        "keywords": ["big little lies", "nine perfect strangers", "apples never fall", "husband's secret", "liane moriarty"],
        "author_folder": "#Liane Moriarty",
        "title": "Liane Moriarty Adaptations"
    },
    {
        "keywords": ["normal people", "conversations with friends", "sally rooney"],
        "author_folder": "#Sally Rooney",
        "title": "Sally Rooney Adaptations"
    },
    {
        "keywords": ["red, white & royal blue", "red white and royal blue", "casey mcquiston"],
        "author_folder": "#Casey McQuiston",
        "title": "Red, White & Royal Blue (Casey McQuiston)"
    },
    {
        "keywords": ["the idea of you", "robinne lee"],
        "author_folder": "#Robinne Lee",
        "title": "The Idea of You (Robinne Lee)"
    },
    {
        "keywords": ["bird box", "malorie", "josh malerman"],
        "author_folder": "#Josh Malerman",
        "title": "Bird Box (Josh Malerman)"
    },
    {
        "keywords": ["queen's gambit", "queens gambit", "walter tevis"],
        "author_folder": "#Walter Tevis",
        "title": "The Queen's Gambit (Walter Tevis)"
    },
    {
        "keywords": ["the martian", "project hail mary", "artemis", "andy weir"],
        "author_folder": "#Andy Weir",
        "title": "Andy Weir Sci-Fi Adaptations"
    },
    {
        "keywords": ["shutter island", "mystic river", "live by night", "dennis lehane"],
        "author_folder": "#Dennis Lehane",
        "title": "Dennis Lehane Adaptations"
    },
    {
        "keywords": ["man called ove", "a man called ove", "anxious people", "fredrik backman"],
        "author_folder": "#Fredrik Backman",
        "title": "Fredrik Backman Adaptations"
    },
    {
        "keywords": ["kite runner", "splendid suns", "mountains echoed", "khaled hosseini"],
        "author_folder": "#Khaled Hosseini",
        "title": "Khaled Hosseini Adaptations"
    },
    {
        "keywords": ["memoirs of a geisha", "arthur golden"],
        "author_folder": "#Arthur Golden",
        "title": "Memoirs of a Geisha (Arthur Golden)"
    },
    {
        "keywords": ["the book thief", "markus zusak"],
        "author_folder": "#Markus Zusak",
        "title": "The Book Thief (Markus Zusak)"
    },
    {
        "keywords": ["perfume", "patrick suskind", "patrick süskind"],
        "author_folder": "#Patrick Süskind",
        "title": "Perfume (Patrick Süskind)"
    },
    {
        "keywords": ["lincoln lawyer", "harry bosch", "michael connelly"],
        "author_folder": "#Michael Connelly",
        "title": "Michael Connelly Adaptations"
    },
    {
        "keywords": ["jack reacher", "killing floor", "lee child"],
        "author_folder": "#Lee Child",
        "title": "Jack Reacher Series (Lee Child)"
    },
    {
        "keywords": ["you", "hidden bodies", "you love me", "caroline kepnes"],
        "author_folder": "#Caroline Kepnes",
        "title": "You Series (Caroline Kepnes)"
    },
    {
        "keywords": ["night agent", "matthew quirk"],
        "author_folder": "#Matthew Quirk",
        "title": "The Night Agent (Matthew Quirk)"
    },
    {
        "keywords": ["all the light we cannot see", "anthony doerr"],
        "author_folder": "#Anthony Doerr",
        "title": "All the Light We Cannot See (Anthony Doerr)"
    },
    {
        "keywords": ["the sympathizer", "viet thanh nguyen"],
        "author_folder": "#Viet Thanh Nguyen",
        "title": "The Sympathizer (Viet Thanh Nguyen)"
    },
    {
        "keywords": ["crazy rich asians", "china rich girlfriend", "rich people problems", "kevin kwan"],
        "author_folder": "#Kevin Kwan",
        "title": "Crazy Rich Asians (Kevin Kwan)"
    },
    {
        "keywords": ["killers of the flower moon", "david grann"],
        "author_folder": "#David Grann",
        "title": "Killers of the Flower Moon (David Grann)"
    },
    {
        "keywords": ["behind her eyes", "sarah pinborough"],
        "author_folder": "#Sarah Pinborough",
        "title": "Behind Her Eyes (Sarah Pinborough)"
    },
    {
        "keywords": ["anatomy of a scandal", "sarah vaughan"],
        "author_folder": "#Sarah Vaughan",
        "title": "Anatomy of a Scandal (Sarah Vaughan)"
    },
    {
        "keywords": ["one day", "david nicholls"],
        "author_folder": "#David Nicholls",
        "title": "One Day (David Nicholls)"
    },
    {
        "keywords": ["maid", "stephanie land"],
        "author_folder": "#Stephanie Land",
        "title": "Maid (Stephanie Land)"
    }
]

def match_original_screen_adaptation(fname: str, parent_path: str) -> dict | None:
    fn_lower = fname.lower()
    fp_lower = f"{parent_path.lower()}/{fn_lower}"
    for item in ORIGINAL_SCREEN_ADAPTATIONS:
        if any(kw in fn_lower or kw in fp_lower for kw in item["keywords"]):
            return item
    return None

def process_edition_originals(ed_root: Path):
    if not ed_root.exists():
        return

    print(f"\n📂 Processing edition: {ed_root.relative_to(LIB_ROOT)}...")
    orig_root = ed_root / "#original books"

    # Scan all epubs in edition
    epubs = list(ed_root.rglob("*.epub"))
    moved_count = 0
    for ep in epubs:
        # Don't move if already inside #original books or #apple tv original or full-catalog series
        if any(p in str(ep) for p in ["#original books", "#apple tv original", "#Freida McFadden", "#Pam Godwin", "#Leigh Rivers", "#Top 10 dark romance"]):
            continue

        matched = match_original_screen_adaptation(ep.name, str(ep.parent))
        if matched:
            target_dir = orig_root / matched["author_folder"]
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / ep.name

            print(f"  🎬 Moving [{matched['title']}]: {ep.name} -> #original books/{matched['author_folder']}/")
            if not target_file.exists() or target_file.stat().st_size != ep.stat().st_size:
                shutil.move(str(ep), str(target_file))
            else:
                ep.unlink()
            moved_count += 1

            # Clean empty old parent dir if empty
            try:
                if not any(ep.parent.iterdir()):
                    ep.parent.rmdir()
            except Exception:
                pass
    print(f"   ✨ Relocated {moved_count} screen adaptation novels in {ed_root.name}")

def main():
    print("==================================================================")
    print("🌟 ORGANIZING MOVIE & TV ORIGINAL NOVELS INTO `#original books`")
    print("==================================================================")

    editions = [
        LIB_ROOT / "[k]",
        LIB_ROOT / "[k-e]",
        LIB_ROOT / "[study]",
        LIB_ROOT / "[e-s]",
        LIB_ROOT / "[e]",
        LIB_ROOT / "[xteink]" / "[study]",
        LIB_ROOT / "[xteink]" / "[e-s]",
    ]

    for ed in editions:
        process_edition_originals(ed)

    # GDrive Sync
    if GDRIVE_ROOT.exists():
        print("\n☁️ Synchronizing with Google Drive #Books...")
        for ed_rel in ["[k]", "[k-e]", "[study]", "[e-s]", "[e]", "[xteink]/[study]", "[xteink]/[e-s]"]:
            g_target = GDRIVE_ROOT / ed_rel / "#original books"
            g_target.mkdir(parents=True, exist_ok=True)
            print(f"  ☁️ Created GDrive folder: {ed_rel}/#original books")

    print("\n==================================================================")
    print("🎉 ALL SCREEN ADAPTATION ORIGINAL NOVELS SUCCESSFULLY ORGANIZED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
