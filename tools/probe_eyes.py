"""数值核对：母版（原始白底）与已抠图版本的"眼白"区域像素颜色/透明度对比。
眼白大约在母版相对坐标 (0.42,0.335) 与 (0.545,0.335) 附近。
"""
import os

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

MASTER = str(_ROOT / "art" / "source" / "master" / "00_身份母版_玩偶服抱蚂蚁.png")
KEYED = str(_ROOT / "desktop-shell" / "assets" / "ranran_base_hi.png")
ANT_RAW = str(_ROOT / "desktop-shell" / "assets" / "_tmp_frames" / "ant_0_idle.png")
ANT_CELL = str(_ROOT / "desktop-shell" / "assets" / "ant_walk.png")

PTS = [(0.415, 0.335), (0.435, 0.325), (0.545, 0.335), (0.565, 0.325)]


def probe(path, pts, cell=None):
    im = Image.open(path).convert("RGBA")
    if cell:
        im = im.crop(cell)
    w, h = im.size
    out = []
    for rx, ry in pts:
        px = im.getpixel((int(w * rx), int(h * ry)))
        out.append(px)
    return out


print("母版  ", probe(MASTER, PTS))
print("抠图后", probe(KEYED, PTS))

# 小蚂蚁：原始 vs 雪碧图第 1 格（格位 210x264）
ant_pts = [(0.28, 0.36), (0.26, 0.34), (0.62, 0.36), (0.60, 0.34)]
print("蚂蚁原图", probe(ANT_RAW, ant_pts))
print("蚂蚁雪碧", probe(ANT_CELL, ant_pts, cell=(0, 0, 210, 264)))
