#!/usr/bin/env python3
"""High-Fidelity CPFONT to XTF Font Converter for Xteink X4 E-Reader.

Converts .cpfont (CrossPoint Font) into native .xtf (XTF0) binary font format.
Matches reference specification from /Users/hyeokjunkong/Desktop/xteink/fonts/.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

def parse_cpfont(cpfont_path: Path):
    data = cpfont_path.read_bytes()
    if not data.startswith(b"CPFONT\x00\x00"):
        raise ValueError(f"Invalid CPFONT magic in {cpfont_path.name}")
        
    ver, subver, num_styles = struct.unpack("<HHH", data[8:14])
    
    styles = []
    pos = 0x20
    for s_idx in range(num_styles):
        s_id, s_pt, num_glyphs, s_v4, s_v5, s_v6, s_offset, s_reserved = struct.unpack("<8I", data[pos:pos+32])
        pos += 32
        
        # Read blocks for this style
        b_pos = s_offset
        blocks = []
        while True:
            u_start, u_end, g_idx = struct.unpack("<III", data[b_pos:b_pos+12])
            b_pos += 12
            if u_start == 0xFFFFFFFF or u_start > 0x10FFFF or len(blocks) > 4000:
                break
            blocks.append((u_start, u_end, g_idx))
            
        # Read glyph descriptors
        g_desc_start = b_pos
        glyphs = {}
        for g in range(num_glyphs):
            p = g_desc_start + g * 16
            b_off, w, h = struct.unpack("<IBB", data[p:p+6])
            yo, xo = struct.unpack("<bb", data[p+6:p+8])
            adv = struct.unpack("<H", data[p+8:p+10])[0]
            b_len = struct.unpack("<I", data[p+12:p+16])[0]
            
            # Read bitmap
            bm_base = g_desc_start + num_glyphs * 16
            bm_pos = bm_base + b_off
            bm_bytes = data[bm_pos : bm_pos + b_len]
            
            glyphs[g] = {
                "w": w,
                "h": h,
                "xo": xo,
                "yo": yo,
                "adv": adv & 0xFF,
                "bm": bm_bytes
            }
            
        styles.append({
            "style_id": s_id,
            "pt": s_pt,
            "num_glyphs": num_glyphs,
            "blocks": blocks,
            "glyphs": glyphs
        })
        
    return styles

def build_xtf(style_data, target_size: int = 28) -> bytes:
    # Use reference structure from 28_RIDIBatang-KleeOne-2px.xtf
    # Determine canvas dimensions based on size
    if target_size <= 28:
        line_h = 28
        h_max = 29
        pitch = 7  # 28 px / 4 = 7 bytes
        rec_size = 205  # 1 adv + 204 bm
    elif target_size <= 30:
        line_h = 30
        h_max = 32
        pitch = 8  # 32 px / 4 = 8 bytes
        rec_size = 258  # 1 adv + 257 bm (256 data + 1 pad)
    else:  # 32+
        line_h = 32
        h_max = 33
        pitch = 8  # 32 px / 4 = 8 bytes
        rec_size = 266  # 1 adv + 265 bm (264 data + 1 pad)
        
    blocks_in = style_data["blocks"]
    glyphs_in = style_data["glyphs"]
    
    # Convert blocks to XTF format (u_start, count, g_idx, flags)
    xtf_blocks = []
    total_xtf_glyphs = 0
    
    for u_start, u_end, g_idx in blocks_in:
        count = u_end - u_start + 1
        xtf_blocks.append((u_start, count, total_xtf_glyphs, 0))
        total_xtf_glyphs += count
        
    num_blocks = len(xtf_blocks)
    
    # Header fields
    # 0x00: Magic 'XTF0'
    # 0x04: v1=1, bpp=5, w_max=64, h_max=2
    # 0x08: ascent=3, descent=0, line_height=line_h, f4=line_h+1
    # 0x14: num_blocks, num_glyphs
    # 0x1C: off_blocks=0x40, off_widths=0, off_offsets=0x4400, off_bitmaps=rec_size
    off_blocks = 0x40
    off_offsets = 0x4400
    
    # Pack header (64 bytes)
    hdr = bytearray(64)
    hdr[0:4] = b"XTF0"
    hdr[4:8] = struct.pack("<BBBB", 1, 5, 64, 2)
    hdr[8:12] = struct.pack("<4b", 3, 0, line_h, line_h + 1)
    hdr[12:16] = struct.pack("<I", 0)
    hdr[16:20] = struct.pack("<I", 0xFFFA0017)
    hdr[20:24] = struct.pack("<I", num_blocks)
    hdr[24:28] = struct.pack("<I", total_xtf_glyphs)
    hdr[28:32] = struct.pack("<I", off_blocks)
    hdr[32:36] = struct.pack("<I", 0)
    hdr[36:40] = struct.pack("<I", off_offsets)
    hdr[40:44] = struct.pack("<I", rec_size)
    
    # Pack block index table (num_blocks * 16 bytes)
    block_bytes = bytearray()
    for u_start, count, g_idx, flags in xtf_blocks:
        block_bytes.extend(struct.pack("<IIII", u_start, count, g_idx, flags))
        
    # Pad up to 0x43A0 / 0x4400
    pre_glyph_pad = bytearray()
    current_len = len(hdr) + len(block_bytes)
    if current_len < off_offsets:
        pre_glyph_pad = bytearray(off_offsets - current_len)
        
    # Build glyph records
    glyph_records = bytearray()
    advance_table = bytearray()
    
    for b_idx, (u_start, count, g_start, _) in enumerate(xtf_blocks):
        src_g_start = blocks_in[b_idx][2]
        for offset in range(count):
            src_g_idx = src_g_start + offset
            g_info = glyphs_in.get(src_g_idx)
            
            rec = bytearray(rec_size)
            if g_info:
                adv = g_info["adv"]
                w = g_info["w"]
                h = g_info["h"]
                xo = g_info["xo"]
                yo = g_info["yo"]
                bm = g_info["bm"]
                
                rec[0] = adv
                advance_table.append(adv)
                
                # Render 2-bit bitmap onto fixed grid (pitch * h_max)
                # Align vertically
                y_baseline = line_h - 4
                y_start = max(0, min(h_max - h, y_baseline - h + yo))
                x_start = max(0, min(28 - w, xo))
                
                for r in range(h):
                    dest_y = y_start + r
                    if dest_y >= h_max:
                        break
                    for c in range(w):
                        dest_x = x_start + c
                        if dest_x >= 28:
                            break
                        # Source pixel
                        src_byte_idx = (r * w + c) // 4
                        if src_byte_idx < len(bm):
                            shift_src = 6 - (c % 4) * 2
                            pix = (bm[src_byte_idx] >> shift_src) & 0x03
                            if pix > 0:
                                dest_byte_idx = 1 + dest_y * pitch + (dest_x // 4)
                                shift_dest = 6 - (dest_x % 4) * 2
                                rec[dest_byte_idx] |= (pix << shift_dest)
            else:
                rec[0] = 0
                advance_table.append(0)
                
            glyph_records.extend(rec)
            
    # Assemble complete XTF binary
    total_size = len(hdr) + len(block_bytes) + len(pre_glyph_pad) + len(glyph_records)
    hdr[44:48] = struct.pack("<I", total_size)
    hdr[56:60] = struct.pack("<I", 0x43A0)
    hdr[60:64] = struct.pack("<I", num_blocks)
    
    return bytes(hdr) + bytes(block_bytes) + bytes(pre_glyph_pad) + bytes(glyph_records)

def convert_all_bookerly():
    bkr_dir = Path("/Users/hyeokjunkong/Desktop/xteink/Bookerly_KR")
    fonts_dir = Path("/Users/hyeokjunkong/Desktop/xteink/fonts")
    
    print("==================================================================")
    print("🌟 CONVERTING BOOKERLY_KR FONTS TO XTEINK X4 XTF FORMAT")
    print("==================================================================")
    
    cp_files = sorted(list(bkr_dir.glob("*.cpfont")))
    print(f"📦 Found {len(cp_files)} CPFONT files in {bkr_dir.name}\n")
    
    # Map CPFONT sizes to XTEINK XTF sizes
    size_map = {
        "Bookerly_KR_8.cpfont": 24,
        "Bookerly_KR_10.cpfont": 26,
        "Bookerly_KR_12.cpfont": 28,
        "Bookerly_KR_14.cpfont": 30,
        "Bookerly_KR_16.cpfont": 32,
        "Bookerly_KR_18.cpfont": 34,
    }
    
    for f in cp_files:
        target_sz = size_map.get(f.name, 28)
        print(f"🔄 Converting {f.name} (Size: {f.stat().st_size:,} bytes) -> {target_sz}px XTF...")
        
        styles = parse_cpfont(f)
        reg_style = styles[0]  # Regular
        
        xtf_bytes = build_xtf(reg_style, target_size=target_sz)
        
        # Save to Bookerly_KR folder
        out_name = f"{target_sz}_Bookerly_KR.xtf"
        out_path1 = bkr_dir / out_name
        out_path1.write_bytes(xtf_bytes)
        
        # Save copy to /Users/hyeokjunkong/Desktop/xteink/fonts/
        out_path2 = fonts_dir / out_name
        out_path2.write_bytes(xtf_bytes)
        
        print(f"   ✅ Created {out_name} ({len(xtf_bytes):,} bytes, {reg_style['num_glyphs']:,} glyphs)")
        
    print("\n==================================================================")
    print("🎉 ALL BOOKERLY_KR FONTS CONVERTED TO XTEINK X4 XTF FORMAT!")
    print("==================================================================")

if __name__ == "__main__":
    convert_all_bookerly()
