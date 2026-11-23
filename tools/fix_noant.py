"""把空手坐姿帧也归一到同一条内容高度（1200px/900画幅），避免切到空手时她整体缩小 10%。"""
import os

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
CANVAS = (900, 1360)
BASELINE = 1340
CONTENT_H = 1200

for key in ["noant"]:
    p = os.path.join(ASSETS, f"ranran_{key}_2x.png")
    im = Image.open(p).convert("RGBA")
    im = im.crop(im.split()[3].getbbox())
    k = CONTENT_H / im.size[1]
    im = im.resize((round(im.size[0] * k), CONTENT_H), Image.LANCZOS)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, BASELINE - CONTENT_H), im)
    canvas.save(p, "PNG", optimize=True)
    bb = canvas.split()[3].getbbox()
    print(f"{key}: 内容高=1200 顶边(CSS)={bb[1]//2}px")
