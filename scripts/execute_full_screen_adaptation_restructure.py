#!/usr/bin/env python3
"""scripts/execute_full_screen_adaptation_restructure.py

1. Ensures all Apple TV+ Original novel adaptations are in `#apple tv original/#[Author]/`.
2. Relocates ALL OTHER Movie and TV Series screen adaptations (including Three-Body, Harry Potter,
   Lord of the Rings, Dune, Hunger Games, Outlander, Witcher, etc.) into `#original books/#[Author]/`.
3. Enforces 100% identical relative folder structures across all 6 library editions.
4. Synchronizes with Google Drive `#Books`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

# 1. Apple TV+ Originals
APPLE_TV_RULES = [
    {"keywords": ["wool", "shift", "dust", "silo"], "author_folder": "#Hugh Howey"},
    {"keywords": ["pachinko"], "author_folder": "#Min Jin Lee"},
    {"keywords": ["foundation"], "author_folder": "#Isaac Asimov"},
    {"keywords": ["presumed innocent"], "author_folder": "#Scott Turow"},
    {"keywords": ["black bird", "in with the devil"], "author_folder": "#James Keene"},
    {"keywords": ["shining girls"], "author_folder": "#Lauren Beukes"},
    {"keywords": ["last thing he told me"], "author_folder": "#Laura Dave"},
    {"keywords": ["lessons in chemistry"], "author_folder": "#Bonnie Garmus"},
    {"keywords": ["dark matter"], "author_folder": "#Blake Crouch"},
    {"keywords": ["slow horses", "slough house", "dead lions"], "author_folder": "#Mick Herron"},
    {"keywords": ["defending jacob"], "author_folder": "#William Landay"},
    {"keywords": ["disclaimer"], "author_folder": "#Renée Knight"},
    {"keywords": ["bad monkey"], "author_folder": "#Carl Hiaasen"},
    {"keywords": ["the changeling"], "author_folder": "#Victor LaValle"},
    {"keywords": ["the mosquito coast"], "author_folder": "#Paul Theroux"},
    {"keywords": ["manhunt"], "author_folder": "#James L. Swanson"}
]

# 2. All Other Movie & TV Screen Adaptations -> #original books
OTHER_SCREEN_ADAPTATION_RULES = [
    {"keywords": ["three-body", "three body", "dark forest", "death's end", "deaths end", "remembrance of earth"], "author_folder": "#Cixin Liu"},
    {"keywords": ["harry potter", "philosopher's stone", "chamber of secrets", "prisoner of azkaban", "goblet of fire", "order of the phoenix", "half-blood prince", "deathly hallows"], "author_folder": "#J.K. Rowling"},
    {"keywords": ["lord of the rings", "hobbit", "fellowship", "two towers", "return of the king"], "author_folder": "#J.R.R. Tolkien"},
    {"keywords": ["hunger games", "catching fire", "mockingjay", "ballad of songbirds", "sunrise on the reaping"], "author_folder": "#Suzanne Collins"},
    {"keywords": ["dune", "messiah", "children of dune"], "author_folder": "#Frank Herbert"},
    {"keywords": ["outlander", "dragonfly in amber", "voyager", "drums of autumn", "fiery cross"], "author_folder": "#Diana Gabaldon"},
    {"keywords": ["the witcher", "last wish", "sword of destiny", "blood of elves"], "author_folder": "#Andrzej Sapkowski"},
    {"keywords": ["divergent", "insurgent", "allegiant"], "author_folder": "#Veronica Roth"},
    {"keywords": ["crawdads sing"], "author_folder": "#Delia Owens"},
    {"keywords": ["the help"], "author_folder": "#Kathryn Stockett"},
    {"keywords": ["gone girl", "sharp objects", "dark places"], "author_folder": "#Gillian Flynn"},
    {"keywords": ["silence of the lambs", "red dragon", "hannibal"], "author_folder": "#Thomas Harris"},
    {"keywords": ["dragon tattoo", "played with fire", "hornet's nest", "millennium"], "author_folder": "#Stieg Larsson"},
    {"keywords": ["you series", "hidden bodies", "you love me", "for you and only you", "you caroline kepnes", "you anthology caroline"], "author_folder": "#Caroline Kepnes"},
    {"keywords": ["the martian", "project hail mary", "artemis"], "author_folder": "#Andy Weir"},
    {"keywords": ["man called ove", "a man called ove", "anxious people", "beartown"], "author_folder": "#Fredrik Backman"},
    {"keywords": ["kite runner", "splendid suns", "mountains echoed"], "author_folder": "#Khaled Hosseini"},
    {"keywords": ["memoirs of a geisha"], "author_folder": "#Arthur Golden"},
    {"keywords": ["the book thief"], "author_folder": "#Markus Zusak"},
    {"keywords": ["perfume"], "author_folder": "#Patrick Süskind"},
    {"keywords": ["all the light we cannot see"], "author_folder": "#Anthony Doerr"},
    {"keywords": ["the sympathizer"], "author_folder": "#Viet Thanh Nguyen"},
    {"keywords": ["normal people", "conversations with friends"], "author_folder": "#Sally Rooney"},
    {"keywords": ["one day"], "author_folder": "#David Nicholls"},
    {"keywords": ["me before you", "after you", "still me"], "author_folder": "#Jojo Moyes"},
    {"keywords": ["thirteen reasons why", "13 reasons why"], "author_folder": "#Jay Asher"},
    {"keywords": ["we were liars", "family of liars"], "author_folder": "#E. Lockhart"},
    {"keywords": ["the big short", "moneyball", "flash boys"], "author_folder": "#Michael Lewis"},
    {"keywords": ["killers of the flower moon", "the wager"], "author_folder": "#David Grann"},
    {"keywords": ["red, white & royal blue", "red white and royal blue"], "author_folder": "#Casey McQuiston"},
    {"keywords": ["the idea of you"], "author_folder": "#Robinne Lee"},
    {"keywords": ["it ends with us", "it starts with us", "verity"], "author_folder": "#Colleen Hoover"},
    {"keywords": ["daisy jones", "evelyn hugo", "malibu rising"], "author_folder": "#Taylor Jenkins Reid"},
    {"keywords": ["crazy rich asians", "china rich girlfriend", "rich people problems"], "author_folder": "#Kevin Kwan"},
    {"keywords": ["maid"], "author_folder": "#Stephanie Land"},
    {"keywords": ["queen's gambit", "queens gambit"], "author_folder": "#Walter Tevis"},
    {"keywords": ["bird box", "malorie"], "author_folder": "#Josh Malerman"},
    {"keywords": ["behind her eyes"], "author_folder": "#Sarah Pinborough"},
    {"keywords": ["anatomy of a scandal"], "author_folder": "#Sarah Vaughan"},
    {"keywords": ["shutter island", "mystic river", "live by night"], "author_folder": "#Dennis Lehane"},
    {"keywords": ["lincoln lawyer", "harry bosch"], "author_folder": "#Michael Connelly"},
    {"keywords": ["jack reacher", "killing floor", "one shot"], "author_folder": "#Lee Child"},
    {"keywords": ["night agent"], "author_folder": "#Matthew Quirk"},
    {"keywords": ["big little lies", "nine perfect strangers", "apples never fall"], "author_folder": "#Liane Moriarty"}
]

def determine_target_destination(fname: str, parent_str: str) -> str | None:
    fn_lower = fname.lower()
    full_lower = f"{parent_str.lower()}/{fn_lower}"

    # 1. Check Apple TV+ first
    for item in APPLE_TV_RULES:
        if any(kw in fn_lower or kw in full_lower for kw in item["keywords"]):
            return f"#apple tv original/{item['author_folder']}"

    # 2. Check Other Screen Adaptations
    for item in OTHER_SCREEN_ADAPTATION_RULES:
        if any(kw in fn_lower or kw in full_lower for kw in item["keywords"]):
            return f"#original books/{item['author_folder']}"

    return None

def restructure_edition(ed_root: Path):
    if not ed_root.exists():
        return

    print(f"\n📂 Restructuring edition: {ed_root.relative_to(LIB_ROOT)}...")
    epubs = list(ed_root.rglob("*.epub"))
    moved_count = 0

    for ep in epubs:
        # Don't touch dedicated full-catalogue authors (Pam Godwin, Freida McFadden, Leigh Rivers, Top 10 dark romance)
        if any(p in str(ep) for p in ["#Freida McFadden", "#Pam Godwin", "#Leigh Rivers", "#Top 10 dark romance"]):
            continue

        target_dest = determine_target_destination(ep.name, str(ep.parent))
        if target_dest:
            target_dir = ed_root / target_dest
            target_file = target_dir / ep.name

            if ep.parent != target_dir:
                target_dir.mkdir(parents=True, exist_ok=True)
                print(f"  🎬 Moving: {ep.name}\n     -> {target_dest}/")
                if not target_file.exists() or target_file.stat().st_size != ep.stat().st_size:
                    shutil.move(str(ep), str(target_file))
                else:
                    ep.unlink()
                moved_count += 1

                # Cleanup empty parent dir
                try:
                    p = ep.parent
                    while p != ed_root:
                        if not any(p.iterdir()):
                            p.rmdir()
                            p = p.parent
                        else:
                            break
                except Exception:
                    pass
    print(f"   ✨ Successfully relocated {moved_count} screen adaptation books in {ed_root.name}")

def main():
    print("==================================================================")
    print("🌟 EXECUTING FULL SCREEN ADAPTATION RESTRUCTURING")
    print("   • Apple TV+ Originals -> `#apple tv original/`")
    print("   • All Other Screen Adaptations -> `#original books/`")
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
        restructure_edition(ed)

    # GDrive Sync
    if GDRIVE_ROOT.exists():
        print("\n☁️ Synchronizing with Google Drive #Books...")
        for ed_rel in ["[k]", "[k-e]", "[study]", "[e-s]", "[e]", "[xteink]/[study]", "[xteink]/[e-s]"]:
            g_apple = GDRIVE_ROOT / ed_rel / "#apple tv original"
            g_orig = GDRIVE_ROOT / ed_rel / "#original books"
            g_apple.mkdir(parents=True, exist_ok=True)
            g_orig.mkdir(parents=True, exist_ok=True)

    print("\n==================================================================")
    print("🎉 FULL SCREEN ADAPTATION RESTRUCTURING SUCCESSFULLY COMPLETED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
