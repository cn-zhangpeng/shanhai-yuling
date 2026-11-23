"""把白底立绘转成透明 PNG，供浏览器原型直接叠加到桌面上。
纯白背景（含抗锯齿边缘）按亮度做 alpha 渐变，避免锯齿。
"""
import os
import sys
from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = str(_ROOT / "web-prototype" / "assets")
HARD = 246      # 亮度 >= 这个值判定为背景，全透明
SOFT = 222      # 介于 SOFT..HARD 之间按线性过渡，保留抗锯齿边缘


def luma(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def convert(path):
    im = Image.open(path).convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            s = max(r, g, b) - min(r, g, b)
            l = luma(r, g, b)
            if l >= HARD and s < 14:
                alpha = 0
            elif l >= SOFT and s < 30:
                alpha = int(a * (HARD - l) / (HARD - SOFT))
            else:
                alpha = a
            px[x, y] = (r, g, b, alpha)
    out = path.replace(".png", "_a.png")
    im.save(out, "PNG")
    # 统计透明比例，便于确认抠图生效
    hist = im.split()[3].histogram()
    transparent = hist[0] / float(w * h)
    print(f"{os.path.basename(out)}  {w}x{h}  透明像素 {transparent:.1%}")


def main():
    if not os.path.isdir(SRC_DIR):
        sys.exit(f"目录不存在: {SRC_DIR}")
    files = [f for f in os.listdir(SRC_DIR) if f.endswith(".png") and not f.endswith("_a.png")]
    for f in sorted(files):
        convert(os.path.join(SRC_DIR, f))


if __name__ == "__main__":
    main()
