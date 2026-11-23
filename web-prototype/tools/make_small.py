"""给原型用的轻量版：高度压到 1000px，保留 alpha，供 canvas 以 470px 显示（约 2x 余量）。
"""
import os
from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = str(_ROOT / "web-prototype" / "assets")
TARGET_H = 1000

for f in sorted(os.listdir(SRC_DIR)):
    if not f.endswith("_a.png"):
        continue
    p = os.path.join(SRC_DIR, f)
    im = Image.open(p).convert("RGBA")
    w, h = im.size
    nw = round(w * TARGET_H / h)
    im = im.resize((nw, TARGET_H), Image.LANCZOS)
    out = p.replace("_a.png", "_s.png")
    im.save(out, "PNG", optimize=True)
    print(f"{os.path.basename(out)}  {nw}x{TARGET_H}  {os.path.getsize(out)/1024:.0f} KB")
