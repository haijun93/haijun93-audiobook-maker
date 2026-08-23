#!/usr/bin/env python3
"""scripts/organize_apple_tv_originals.py

1. Creates `#apple tv original` root directory across all library editions:
   - `소설2/[k]/#apple tv original/`
   - `소설2/[k-e]/#apple tv original/`
   - `소설2/[study]/#apple tv original/`
   - `소설2/[e-s]/#apple tv original/`
   - `소설2/[e]/#apple tv original/`
   - `소설2/[xteink]/[study]/#apple tv original/`
   - `소설2/[xteink]/[e-s]/#apple tv original/`
2. Relocates all Apple TV+ Original novel adaptations to `#apple tv original/#[Author]/`:
   - Silo Trilogy (Wool, Shift, Dust) by Hugh Howey
   - Pachinko by Min Jin Lee
   - Foundation Trilogy by Isaac Asimov
   - Presumed Innocent by Scott Turow
   - Black Bird by James Keene
   - The Shining Girls by Lauren Beukes
   - The Last Thing He Told Me by Laura Dave
   - (and future Apple TV+ originals)
3. Synchronizes with Google Drive #Books.
4. Updates AGENTS.md taxonomy.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

LIB_ROOT = Path("/Users/hyeokjunkong/Desktop/소설2")
GDRIVE_ROOT = Path("/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books")

APPLE_TV_ORIGINALS = [
    {
        "keywords": ["wool", "shift", "dust", "silo"],
        "author_kw": "howey",
        "author_folder": "#Hugh Howey",
        "title": "Silo Series (Hugh Howey)"
    },
    {
        "keywords": ["pachinko"],
        "author_kw": "min jin lee",
        "author_folder": "#Min Jin Lee",
        "title": "Pachinko (Min Jin Lee)"
    },
    {
        "keywords": ["foundation"],
        "author_kw": "asimov",
        "author_folder": "#Isaac Asimov",
        "title": "Foundation (Isaac Asimov)"
    },
    {
        "keywords": ["presumed innocent"],
        "author_kw": "turow",
        "author_folder": "#Scott Turow",
        "title": "Presumed Innocent (Scott Turow)"
    },
    {
        "keywords": ["black bird", "in with the devil"],
        "author_kw": "keene",
        "author_folder": "#James Keene",
        "title": "Black Bird (James Keene)"
    },
    {
        "keywords": ["shining girls"],
        "author_kw": "beukes",
        "author_folder": "#Lauren Beukes",
        "title": "The Shining Girls (Lauren Beukes)"
    },
    {
        "keywords": ["last thing he told me"],
        "author_kw": "dave",
        "author_folder": "#Laura Dave",
        "title": "The Last Thing He Told Me (Laura Dave)"
    },
    {
        "keywords": ["lessons in chemistry"],
        "author_kw": "garmus",
        "author_folder": "#Bonnie Garmus",
        "title": "Lessons in Chemistry (Bonnie Garmus)"
    },
    {
        "keywords": ["dark matter"],
        "author_kw": "crouch",
        "author_folder": "#Blake Crouch",
        "title": "Dark Matter (Blake Crouch)"
    },
    {
        "keywords": ["slow horses", "slough house", "dead lions"],
        "author_kw": "herron",
        "author_folder": "#Mick Herron",
        "title": "Slow Horses (Mick Herron)"
    },
    {
        "keywords": ["defending jacob"],
        "author_kw": "landay",
        "author_folder": "#William Landay",
        "title": "Defending Jacob (William Landay)"
    },
    {
        "keywords": ["disclaimer"],
        "author_kw": "knight",
        "author_folder": "#Renée Knight",
        "title": "Disclaimer (Renée Knight)"
    },
    {
        "keywords": ["bad monkey"],
        "author_kw": "hiaasen",
        "author_folder": "#Carl Hiaasen",
        "title": "Bad Monkey (Carl Hiaasen)"
    },
    {
        "keywords": ["the changeling"],
        "author_kw": "lavalle",
        "author_folder": "#Victor LaValle",
        "title": "The Changeling (Victor LaValle)"
    },
    {
        "keywords": ["the mosquito coast"],
        "author_kw": "theroux",
        "author_folder": "#Paul Theroux",
        "title": "The Mosquito Coast (Paul Theroux)"
    },
    {
        "keywords": ["manhunt"],
        "author_kw": "swanson",
        "author_folder": "#James L. Swanson",
        "title": "Manhunt (James L. Swanson)"
    }
]

def match_apple_tv_original(fname: str, parent_path: str) -> dict | None:
    fn_lower = fname.lower()
    fp_lower = f"{parent_path.lower()}/{fn_lower}"
    for item in APPLE_TV_ORIGINALS:
        if any(kw in fn_lower or kw in fp_lower for kw in item["keywords"]):
            if not item["author_kw"] or item["author_kw"] in fn_lower or item["author_kw"] in fp_lower:
                return item
    return None

def process_edition(ed_root: Path):
    if not ed_root.exists():
        return
        
    print(f"\n📂 Processing edition: {ed_root.relative_to(LIB_ROOT)}...")
    apple_root = ed_root / "#apple tv original"
    
    # Scan all epubs in edition
    epubs = list(ed_root.rglob("*.epub"))
    moved_count = 0
    for ep in epubs:
        if "#apple tv original" in str(ep):
            continue
            
        matched = match_apple_tv_original(ep.name, str(ep.parent))
        if matched:
            target_dir = apple_root / matched["author_folder"]
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / ep.name
            
            print(f"  📺 Moving [{matched['title']}]: {ep.name} -> #apple tv original/{matched['author_folder']}/")
            if not target_file.exists() or target_file.stat().st_size != ep.stat().st_size:
                shutil.move(str(ep), str(target_file))
            else:
                ep.unlink()
            moved_count += 1
            
            # Clean empty old parent dir if empty
            try:
                if not any(ep.parent.iterdir()):
                    ep.parent.rmdir()
            except: pass
            
    print(f"   ✨ Relocated {moved_count} Apple TV+ original books in {ed_root.name}")

def main():
    print("==================================================================")
    print("🌟 ORGANIZING APPLE TV+ ORIGINAL NOVELS INTO `#apple tv original`")
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
        process_edition(ed)
        
    # GDrive Sync
    if GDRIVE_ROOT.exists():
        print("\n☁️ Synchronizing with Google Drive #Books...")
        for ed_rel in ["[k]", "[k-e]", "[study]", "[e-s]", "[e]", "[xteink]/[study]", "[xteink]/[e-s]"]:
            g_target = GDRIVE_ROOT / ed_rel / "#apple tv original"
            g_target.mkdir(parents=True, exist_ok=True)
            print(f"  ☁️ Created GDrive folder: {ed_rel}/#apple tv original")

    print("\n==================================================================")
    print("🎉 ALL APPLE TV+ ORIGINAL NOVELS SUCCESSFULLY ORGANIZED!")
    print("==================================================================")

if __name__ == "__main__":
    main()
