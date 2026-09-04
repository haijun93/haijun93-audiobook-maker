#!/usr/bin/env python3
import io
import re
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

p = Path("/Users/hyeokjunkong/Desktop/소설2/[study]/Mystery_Thriller_Crime/#Jesse Q. Sutanto/[study] Vera Wong's Guide to Snooping (on a Dead Man) Jesse Q. Sutanto (4.19).epub")

data = {}
with zipfile.ZipFile(p, "r") as z:
    for it in z.infolist():
        data[it.filename] = z.read(it.filename)

for fname in list(data.keys()):
    if fname.endswith((".xhtml", ".html")):
        txt = data[fname].decode("utf-8", "ignore")

        # Clean broken rt tags
        soup = BeautifulSoup(txt, "html.parser")
        for rt in soup.find_all("rt"):
            # Clean weird attributes in rt
            rt.attrs = {"class": "wordwise-hint"}
            t = rt.get_text().strip()
            # If text has truncation dots
            if t.endswith("...") or t.endswith("…"):
                rt.string = t.rstrip(".").rstrip("…").strip()

        for tag in soup.find_all(True):
            clean_attrs = {}
            for k, v in list(tag.attrs.items()):
                k_clean = re.sub(r"[^a-zA-Z0-9_\-:]", "", k)
                if k_clean and not any(bad in k_clean.lower() for bad in ["careful", "everything", "wordwise-hint"]):
                    clean_attrs[k_clean] = v
            tag.attrs = clean_attrs

        # Output clean XML
        data[fname] = str(soup).encode("utf-8")

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
    for f_name, c_data in data.items():
        if f_name == "mimetype":
            dst.writestr(f_name, c_data, compress_type=zipfile.ZIP_STORED)
        else:
            dst.writestr(f_name, c_data)

p.write_bytes(buf.getvalue())
print("Repaired all broken rt tags in Vera Wong!")
