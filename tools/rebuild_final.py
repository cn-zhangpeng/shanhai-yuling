"""重出最终素材：
- 她的立绘：1330×1773 母版 → 900×1200（CSS 显示 450×600，dpr 1.5 下 1:1，不放大也不降采样）
- 小蚂蚁：MediaKit 语义抠图结果 → 内容高 300（CSS 显示 150），格位统一、底边对齐
"""
import glob
import json
import os

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ROOT = str(_ROOT)
ASSETS = os.path.join(ROOT, "desktop-shell", "assets")
FRAMES_SRC = os.path.join(ROOT, "art", "source", "frames")
MATTED = os.path.join(ASSETS, "_matted")

HER_W, HER_H = 900, 1200
ANT_CONTENT_H = 300
ANT_PAD = 16
ORDER = ["idle", "walkA", "walkB", "run", "sit", "look"]


def rebuild_her():
    for p in sorted(glob.glob(os.path.join(FRAMES_SRC, "ranran_*_master.png"))):
        key = os.path.basename(p).replace("ranran_", "").replace("_master.png", "")
        im = Image.open(p).convert("RGBA").resize((HER_W, HER_H), Image.LANCZOS)
        out = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        im.save(out, "PNG", optimize=True)
        print(f"ranran_{key}_2x.png {im.size} {os.path.getsize(out)/1024:.0f}KB")


def rebuild_ant():
    frames = []
    for i, name in enumerate(ORDER):
        p = os.path.join(MATTED, f"ant_{i}_{name}.png")
        im = Image.open(p).convert("RGBA")
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
    meta = {"frames": len(frames), "cellW": cell_w, "cellH": cell_h, "displayH": 150}
    with open(os.path.join(ASSETS, "ant_walk.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
    print(f"ant_walk.png {strip.size} cell {cell_w}x{cell_h} {os.path.getsize(out)/1024:.0f}KB")
    print(json.dumps(meta))


if __name__ == "__main__":
    rebuild_her()
    rebuild_ant()
