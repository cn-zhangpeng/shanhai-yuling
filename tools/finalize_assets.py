"""最终素材管线：所有素材按"显示尺寸 × 2"预先用 LANCZOS 缩放，避免浏览器做 4~6 倍双线性降采样。
- 她的立绘：1330×1773 母版 → 686×912（CSS 显示 343×456，dpr 1.5 下 1:1.33，仍走降采样但只 2 倍）
- 小蚂蚁：内容高 240px（CSS 显示 120px），格位按最大宽统一，底边对齐
原始 1330 帧归档到 art/source/frames/，assets 里只留 2 倍图。
"""
import glob
import json
import os
import shutil

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ROOT = str(_ROOT)
ASSETS = os.path.join(ROOT, "desktop-shell", "assets")
FRAME_ARCHIVE = os.path.join(ROOT, "art", "source", "frames")
TMP = os.path.join(ASSETS, "_tmp_frames")

HER_W, HER_H = 686, 912          # = 343×456 的 2 倍
ANT_CONTENT_H = 240              # = 显示 120px 的 2 倍
ANT_PAD = 12

HER_FRAMES = ["base", "blink", "talk", "smile", "turn", "turnL", "wave", "noant"]


def resize_her():
    os.makedirs(FRAME_ARCHIVE, exist_ok=True)
    for key in HER_FRAMES:
        src = os.path.join(ASSETS, f"ranran_{key}_hi.png")
        if not os.path.exists(src):
            print("缺帧:", src)
            continue
        im = Image.open(src).convert("RGBA")
        dst = im.resize((HER_W, HER_H), Image.LANCZOS)
        dst.save(os.path.join(ASSETS, f"ranran_{key}_2x.png"), "PNG", optimize=True)
        arch = os.path.join(FRAME_ARCHIVE, f"ranran_{key}_master.png")
        if not os.path.exists(arch):
            shutil.copy2(src, arch)
        print(f"ranran_{key}_2x.png  {dst.size}  {os.path.getsize(os.path.join(ASSETS, f'ranran_{key}_2x.png'))/1024:.0f}KB")


def luma(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def key_white(im):
    """边缘泛洪去底：只删连到边框的白，保留眼里的白色高光"""
    from PIL import ImageChops, ImageDraw
    hsv = im.convert("RGB").convert("HSV")
    s, v = hsv.split()[1], hsv.split()[2]
    cand = ImageChops.multiply(
        s.point(lambda x: 255 if x < 26 else 0),
        v.point(lambda x: 255 if x >= 228 else 0),
    )
    w, h = im.size
    pmask = Image.new("L", (w + 2, h + 2), 255)
    pmask.paste(cand, (1, 1))
    ImageDraw.floodfill(pmask, (0, 0), 128, thresh=0)
    bg = pmask.crop((1, 1, w + 1, h + 1)).point(lambda x: 255 if x == 128 else 0)
    ramp = v.point(lambda x: max(0, min(255, int((246 - x) / 18 * 255))))
    alpha = Image.new("L", im.size, 255)
    alpha.paste(ramp, (0, 0), bg)
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out


def build_ant():
    files = sorted(glob.glob(os.path.join(TMP, "ant_*.png")))
    order = ["idle", "walkA", "walkB", "run", "sit", "look"]
    files = [os.path.join(TMP, f"ant_{i}_{n}.png") for i, n in enumerate(order)]
    frames = []
    for p in files:
        im = key_white(Image.open(p))
        im = im.crop(im.split()[3].getbbox())
        k = ANT_CONTENT_H / im.size[1]
        im = im.resize((max(1, round(im.size[0] * k)), ANT_CONTENT_H), Image.LANCZOS)
        frames.append(im)

    cell_w = max(f.size[0] for f in frames) + ANT_PAD * 2
    cell_h = ANT_CONTENT_H + ANT_PAD * 2
    strip = Image.new("RGBA", (cell_w * len(frames), cell_h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f, (i * cell_w + (cell_w - f.size[0]) // 2, cell_h - ANT_PAD - f.size[1]), f)
    out = os.path.join(ASSETS, "ant_walk.png")
    strip.save(out, "PNG", optimize=True)
    meta = {"frames": len(frames), "cellW": cell_w, "cellH": cell_h, "displayH": 120}
    with open(os.path.join(ASSETS, "ant_walk.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
    print(f"ant_walk.png {strip.size} cell {cell_w}x{cell_h} {os.path.getsize(out)/1024:.0f}KB")
    print(json.dumps(meta))


if __name__ == "__main__":
    resize_her()
    build_ant()
