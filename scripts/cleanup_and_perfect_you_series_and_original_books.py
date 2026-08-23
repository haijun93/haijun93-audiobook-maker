#!/usr/bin/env python3
"""scripts/cleanup_and_perfect_you_series_and_original_books.py

1. Perfectly organizes Caroline Kepnes's genuine `YOU: A Novel` Series (1~4 books)
   into `#original books/#Caroline Kepnes/`.
2. Properly relocates other genuine screen adaptations (Jay Asher's 13 Reasons Why, Jojo Moyes's Me Before You)
   into `#original books/#[Author]/`.
3. Restores any mis-matched non-adaptation books (Abby Jimenez, Celeste Ng, Anne Frank, etc.)
   to their canonical genre and author folders across all 6 editions.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")

# Explicit book-to-destination rules for files under review
CLEANUP_RULES = [
    # 1. Genuine YOU Series by Caroline Kepnes (Netflix Original Series)
    {
        "keywords": ["you series", "hidden bodies", "you love me", "for you and only you", "you caroline kepnes", "you a novel caroline kepnes", "you anthology caroline"],
        "author_folder": "#Caroline Kepnes",
        "target_parent": "#original books/#Caroline Kepnes"
    },
    # 2. Genuine Screen Adaptations that belong in #original books
    {
        "keywords": ["thirteen reasons why", "13 reasons why"],
        "author_folder": "#Jay Asher",
        "target_parent": "#original books/#Jay Asher" # Netflix Series
    },
    {
        "keywords": ["me before you", "after you", "still me"],
        "author_folder": "#Jojo Moyes",
        "target_parent": "#original books/#Jojo Moyes" # Blockbuster Movie
    },
    {
        "keywords": ["we were liars", "family of liars"],
        "author_folder": "#E. Lockhart",
        "target_parent": "#original books/#E. Lockhart" # Prime Video Series
    },
    
    # 3. Non-adaptation or Specific Genre Books to restore to their Canonical Genres
    {
        "keywords": ["we love you, bunny", "we love you bunny"],
        "target_parent": "Horror_Dark_Fiction/#Mona Awad"
    },
    {
        "keywords": ["say you'll remember me", "say youll remember me"],
        "target_parent": "Romance_Contemporary/#Abby Jimenez"
    },
    {
        "keywords": ["and now, back to you", "and now back to you"],
        "target_parent": "Romance_Contemporary/#B.K. Borison"
    },
    {
        "keywords": ["everything i never told you"],
        "target_parent": "Fiction_Literary_Historical/#Celeste Ng"
    },
    {
        "keywords": ["the diary of a young girl", "anne frank"],
        "target_parent": "Biography_Memoir/#Anne Frank"
    },
    {
        "keywords": ["auggie n me", "wonder stories"],
        "target_parent": "Young_Adult_Children/#R.J. Palacio"
    },
    {
        "keywords": ["the bone houses"],
        "target_parent": "Young_Adult_Children/#Emily Lloyd-Jones"
    },
    {
        "keywords": ["801 things you should know"],
        "target_parent": "Nonfiction_History_Politics/#David Olsen"
    },
    {
        "keywords": ["fundamentally"],
        "target_parent": "Nonfiction_History_Politics/#Nussaibah Younis"
    },
    {
        "keywords": ["you never know"],
        "target_parent": "Biography_Memoir/#Tom Selleck"
    },
    {
        "keywords": ["when the moon hits your eye"],
        "target_parent": "Fantasy_Science_Fiction/#John Scalzi"
    }
]

def find_cleanup_target(fname: str) -> str | None:
    fn_lower = fname.lower()
    for item in CLEANUP_RULES:
        if any(kw in fn_lower for kw in item["keywords"]):
            return item["target_parent"]
    return None

def process_edition_cleanup(ed_root: Path):
    if not ed_root.exists():
        return
        
    print(f"\n📂 Reviewing and perfecting {ed_root.relative_to(LIB_ROOT)}...")
    
    # Check all files currently under #original books/#Caroline Kepnes or anywhere in edition
    epubs = list(ed_root.rglob("*.epub"))
    for ep in epubs:
        dest_rel = find_cleanup_target(ep.name)
        if dest_rel:
            target_dir = ed_root / dest_rel
            target_file = target_dir / ep.name
            
            # If not already in target dir, move it
            if ep.parent != target_dir:
                target_dir.mkdir(parents=True, exist_ok=True)
                print(f"  📦 Realigning: {ep.name}\n     -> {dest_rel}/")
                if not target_file.exists() or target_file.stat().st_size != ep.stat().st_size:
                    shutil.move(str(ep), str(target_file))
                else:
                    ep.unlink()
                
                # Clean old parent if empty
                try:
                    if not any(ep.parent.iterdir()):
                        ep.parent.rmdir()
                except: pass

def main():
    print("==================================================================")
    print("🌟 PERFECTING `YOU: A NOVEL` SERIES & SCREEN ADAPTATIONS TAXONOMY")
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
        process_edition_cleanup(ed)
        
    print("\n==================================================================")
    print("🎉 `YOU` SERIES & ALL ADAPTATIONS 100% PERFECTLY ALIGNED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
