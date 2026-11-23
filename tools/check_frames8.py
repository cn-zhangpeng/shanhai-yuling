"""把 8 张帧拼成对照表，并逐张量化：
- 内容框（判断"底边是否对齐、身体比例是否一致"）
- 眼区透明度（判断是否还有半透明残影）
- 头部宽度（用头部横向宽度判断各帧是否被等比缩得不一样）
"""
import os

from PIL import Image, ImageDraw
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
OUT = os.path.join(ASSETS, "_preview", "八帧对照.png")

FRAMES = [("base", "正面·抱蚁"), ("blink", "闭眼"), ("talk", "张嘴"), ("smile", "笑眼"),
          ("turn", "右转20°"), ("turnL", "左转20°"), ("wave", "挥手"), ("noant", "空手")]

CELL = (300, 400)
COLS = 4


def head_width(im):
    """取上 18%~34% 高度带的非透明横向跨度，作为"头宽"的代理指标"""
    w, h = im.size
    band = im.crop((0, int(h * 0.18), w, int(h * 0.34)))
    a = band.split()[3]
    xs = []
    for y in range(band.size[1]):
        for x in range(band.size[0]):
            if a.getpixel((x, y)) > 90:
                xs.append(x)
                break
    if not xs:
        return 0
    left = min(xs)
    right = 0
    for y in range(band.size[1]):
        for x in range(band.size[0] - 1, -1, -1):
            if a.getpixel((x, y)) > 90:
                right = max(right, x)
                break
    return right - left


def eye_alpha(im):
    w, h = im.size
    box = (int(w * 0.34), int(h * 0.30), int(w * 0.68), int(h * 0.40))
    px = list(im.crop(box).getdata())
    bad = sum(1 for t in px if t[3] < 250)
    return bad, len(px)


rows = (len(FRAMES) + COLS - 1) // COLS
sheet = Image.new("RGBA", (CELL[0] * COLS, CELL[1] * rows + 30), (250, 248, 246, 255))
d = ImageDraw.Draw(sheet)

print(f"{'帧':<8}{'内容框':<28}{'框高':<7}{'头宽':<7}{'眼区<250alpha'}")
for i, (key, label) in enumerate(FRAMES):
        im = Image.open(os.path.join(ASSETS, f"ranran_{key}_2x.png")).convert("RGBA")
        b = im.split()[3].getbbox()
        hw = head_width(im)
        bad, tot = eye_alpha(im)
        print(f"{key:<8}{str(b):<28}{b[3]-b[1]:<7}{hw:<7}{bad}/{tot}  ({bad/tot:.1%})")
        thumb = im.copy()
        thumb.thumbnail((CELL[0] - 10, CELL[1] - 34), Image.LANCZOS)
        x = (i % COLS) * CELL[0] + (CELL[0] - thumb.width) // 2
        y = (i // COLS) * CELL[1] + 26
        sheet.alpha_composite(thumb, (x, y))
        d.text(((i % COLS) * CELL[0] + 8, (i // COLS) * CELL[1] + 6), f"{key}  {label}", fill=(40, 40, 40))

sheet.convert("RGB").save(OUT)
print("SHEET:", OUT)
