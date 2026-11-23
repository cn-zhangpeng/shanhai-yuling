"""对照实验：旧抠图（全局亮度阈值去白） vs 新抠图（只删"连到画布边框"的白色）。
纯 Pillow 实现：用 HSV 通道 + ImageDraw.floodfill 做连通域泛洪，避免误删眼里的白色高光。
输出头部放大对照图，肉眼判断。
"""
import json
import os

from PIL import Image, ImageChops, ImageDraw
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

SRC_ANT = str(_ROOT / "desktop-shell" / "assets" / "_tmp_frames" / "ant_0_idle.png")
SRC_HER = str(_ROOT / "art" / "source" / "master" / "00_身份母版_玩偶服抱蚂蚁.png")
OUT = str(_ROOT / "desktop-shell" / "assets" / "_preview")

SAT_MAX = 26      # 认为"近灰"
VAL_MIN = 228     # 认为"很亮"


def old_key(im):
    """旧做法：亮度 >=246 且近灰 → 全透明；222~246 → 半透明渐变（会吃掉眼里的白色高光）"""
    hsv = im.convert("RGB").convert("HSV")
    s, v = hsv.split()[1], hsv.split()[2]
    cand = ImageChops.multiply(
        s.point(lambda x: 255 if x < 14 else 0),
        v.point(lambda x: 255 if x >= 222 else 0),
    )
    hard = ImageChops.multiply(cand, v.point(lambda x: 255 if x >= 246 else 0))
    ramp = v.point(lambda x: max(0, min(255, int((246 - x) / 24 * 255))))
    alpha = Image.new("L", im.size, 255)
    alpha.paste(ramp, (0, 0), cand)
    alpha.paste(Image.new("L", im.size, 0), (0, 0), hard)
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out


def new_key(im):
    """新做法：候选白底 + 从画布外泛洪，只有"连到边框"的白才透明，内部高光保留"""
    hsv = im.convert("RGB").convert("HSV")
    s, v = hsv.split()[1], hsv.split()[2]
    cand = ImageChops.multiply(
        s.point(lambda x: 255 if x < SAT_MAX else 0),
        v.point(lambda x: 255 if x >= VAL_MIN else 0),
    )

    # 外扩 1px 白边，保证"背景"一定连通；泛洪结果填成 128
    w, h = im.size
    pmask = Image.new("L", (w + 2, h + 2), 255)
    pmask.paste(cand, (1, 1))
    ImageDraw.floodfill(pmask, (0, 0), 128, thresh=0)
    bg = pmask.crop((1, 1, w + 1, h + 1)).point(lambda x: 255 if x == 128 else 0)

    ramp = v.point(lambda x: max(0, min(255, int((246 - x) / 18 * 255))))
    alpha = Image.new("L", im.size, 255)
    alpha.paste(ramp, (0, 0), bg)     # 背景区按亮度做羽化，其余保持不透明
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out


def crop_head(im, ratio, size):
    w, h = im.size
    box = (int(w * ratio[0]), int(h * ratio[1]), int(w * ratio[2]), int(h * ratio[3]))
    c = im.crop(box)
    c.thumbnail(size, Image.LANCZOS)
    flat = Image.new("RGBA", c.size, (246, 246, 246, 255))
    flat.alpha_composite(c)
    return flat


CASES = [
    ("蚂蚁", SRC_ANT, (0.30, 0.06, 0.85, 0.42), (560, 560)),
    ("她", SRC_HER, (0.30, 0.24, 0.72, 0.47), (560, 560)),
]


def run():
    os.makedirs(OUT, exist_ok=True)
    for tag, src, ratio, size in CASES:
        im = Image.open(src)
        a = crop_head(old_key(im), ratio, size)
        b = crop_head(new_key(im), ratio, size)
        pa = os.path.join(OUT, f"{tag}_旧抠图.png")
        pb = os.path.join(OUT, f"{tag}_新抠图.png")
        a.save(pa)
        b.save(pb)
        print(pa)
        print(pb)


if __name__ == "__main__":
    run()
