"""放大最新截图的脸与蚂蚁（坐标来自页面实测）。"""
import os

from PIL import Image
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

SHOT = os.path.join(tempfile.gettempdir(), "aha_bua.png")
OUT = str(_ROOT / "desktop-shell" / "assets" / "_preview")

CROPS = [
    ("脸_新尺寸", (395, 430, 570, 605), 3),
    ("蚂蚁_新尺寸", (8, 700, 150, 870), 4),
]

os.makedirs(OUT, exist_ok=True)
im = Image.open(SHOT).convert("RGB")
for tag, box, k in CROPS:
    c = im.crop(box).resize(((box[2] - box[0]) * k, (box[3] - box[1]) * k), Image.LANCZOS)
    p = os.path.join(OUT, f"{tag}.png")
    c.save(p)
    print(p, c.size)
