"""把屏幕截图里的脸和蚂蚁放大，看真实像素（判断是"缩太小糊了"还是"素材里眼睛就变了"）。"""
import os

from PIL import Image
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

SHOT = os.path.join(tempfile.gettempdir(), "aha_bua.png")
OUT = str(_ROOT / "desktop-shell" / "assets" / "_preview")

CROPS = [
    ("屏幕_她的脸", (392, 528, 505, 640), 4),
    ("屏幕_蚂蚁", (30, 725, 115, 835), 5),
]

os.makedirs(OUT, exist_ok=True)
im = Image.open(SHOT).convert("RGB")
for tag, box, k in CROPS:
    c = im.crop(box)
    c = c.resize((c.width * k, c.height * k), Image.NEAREST)
    p = os.path.join(OUT, f"{tag}.png")
    c.save(p)
    print(p, c.size)
