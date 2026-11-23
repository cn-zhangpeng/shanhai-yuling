"""全姿态对照表：14 张同画幅帧按同一缩放并排，检查头身比例、脚底基线、造型是否统一。"""
import os

from PIL import Image, ImageDraw
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
OUT = os.path.join(ASSETS, "_preview", "全姿态对照.png")

FRAMES = [("base", "坐·抱蚁"), ("stand", "站立"), ("walkA", "迈左"), ("walkB", "迈右"),
          ("ropeAir", "跳腾空"), ("ropeLand", "跳落地"), ("phone", "蹲看手机"), ("noant", "空手坐"),
          ("blink", "闭眼"), ("talk", "张嘴"), ("smile", "笑眼"), ("turn", "右转"),
          ("turnL", "左转"), ("wave", "挥手")]

W, H = 225, 340
COLS = 7
rows = (len(FRAMES) + COLS - 1) // COLS
sheet = Image.new("RGB", (W * COLS, H * rows + 20), (248, 246, 244, 255))
d = ImageDraw.Draw(sheet)

for i, (key, label) in enumerate(FRAMES):
    p = os.path.join(ASSETS, f"ranran_{key}_2x.png")
    im = Image.open(p).convert("RGBA")
    im = im.resize((W, H), Image.LANCZOS)
    x = (i % COLS) * W
    y = (i // COLS) * H + 16
    sheet.paste(im, (x, y), im)
    d.text((x + 4, y - 14), f"{key}", fill=(30, 30, 30))

sheet.save(OUT)
print(OUT, sheet.size)
