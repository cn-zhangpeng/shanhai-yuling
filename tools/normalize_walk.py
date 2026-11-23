"""走路 4 姿态 + 站立帧按"同一个内容高度"重新规整。

原来每帧内容高度不一（stand 1124 / walkA 1136 / walkB 1028 / walkP1 1068 / walkP2 1078，
2x 像素），底边又都对齐在 1340，于是走路时她一会儿 540px 高、一会儿 514px 高，
头顶每换一帧就上下跳 25px、身体还胖瘦变一轮 —— 肉眼看就是"一直在闪"。

这里统一按内容高 1120px 缩放（支撑脚在底边，缩放以底边为基准，脚始终踩在原基线），
再把内容顶边打出来核对。
"""
import os

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
CANVAS = (900, 1360)
BASELINE = 1340
TARGET_H = 1120
BACKUP = os.path.join(ASSETS, "_before_hfix")

KEYS = ["stand", "walkA", "walkB", "walkP1", "walkP2"]


def main():
    os.makedirs(BACKUP, exist_ok=True)
    print(f"{'帧':<8}{'原内容高':>10}{'原顶边(CSS)':>14}   ->   新内容高 {TARGET_H}  新顶边(CSS) 新宽(2x)")
    for key in KEYS:
        p = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        src = Image.open(p).convert("RGBA")
        b = src.split()[3].getbbox()
        old_h = b[3] - b[1]
        old_top_css = b[1] // 2
        keep = os.path.join(BACKUP, f"ranran_{key}_2x.png")
        if not os.path.exists(keep):
            src.save(keep, "PNG")

        im = src.crop(b)
        k = TARGET_H / im.size[1]
        im = im.resize((round(im.size[0] * k), TARGET_H), Image.LANCZOS)
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, BASELINE - TARGET_H), im)
        canvas.save(p, "PNG", optimize=True)
        nb = canvas.split()[3].getbbox()
        print(f"{key:<8}{old_h:>10}{old_top_css:>14}   ->   {TARGET_H:>4}          {nb[1]//2:>4}      {im.size[0]:>4}")


if __name__ == "__main__":
    main()
