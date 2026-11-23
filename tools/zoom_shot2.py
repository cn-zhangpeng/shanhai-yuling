"""按页面实测坐标裁切放大：她的脸 / 小蚂蚁，检查缩放后的清晰度。"""
import os

from PIL import Image
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

SHOT = os.path.join(tempfile.gettempdir(), "aha_bua.png")
OUT = str(_ROOT / "desktop-shell" / "assets" / "_preview")

# 页面实测（CSS px，与截图 1:1）：pet=(302.7,411.3,340.4,454) ant=(17.5,739.3,100.4,122.4)
CROPS = [
    ("屏幕_她的脸2", (400, 530, 530, 660), 4),
    ("屏幕_蚂蚁2", (10, 730, 130, 870), 5),
]

os.makedirs(OUT, exist_ok=True)
im = Image.open(SHOT).convert("RGB")
for tag, box, k in CROPS:
    c = im.crop(box).resize(((box[2] - box[0]) * k, (box[3] - box[1]) * k), Image.NEAREST)
    p = os.path.join(OUT, f"{tag}.png")
    c.save(p)
    print(p, c.size)
