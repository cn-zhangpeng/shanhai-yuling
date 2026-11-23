"""跳绳两帧按头宽统一大小（原来一大一小在变）。

绳子的弧线会横穿头部所在的横带，所以这里不用"整行像素数"，改用**最长连续不透明段**
（帽子最宽处是一条连续的毛绒边，绳线只有几像素宽，单独一段，不会干扰）。
统一到站立帧头宽 468px，底边落在基线（脚踩地/落地一致）。
"""
import os

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
CANVAS = (900, 1360)
BASELINE = 1340
BACKUP = os.path.join(ASSETS, "_before_ropefix")
TARGET_HEAD = 468
KEYS = ["ropeAir", "ropeLand"]


def head_run(im):
    """内容顶部 40% 行内，最长连续不透明段的宽度。"""
    alpha = im.split()[3]
    b = alpha.getbbox()
    px = alpha.load()
    band = max(1, int((b[3] - b[1]) * 0.40))
    best = 0
    for y in range(b[1], b[1] + band):
        run = 0
        for x in range(b[0], b[2]):
            if px[x, y] > 40:
                run += 1
                best = max(best, run)
            else:
                run = 0
    return best


def main():
    os.makedirs(BACKUP, exist_ok=True)
    print(f"{'帧':<10}{'原头宽':>8}{'原内容高':>10}  ->  {'缩放':>6}{'新内容高':>10}{'新顶边(CSS)':>14}")
    for key in KEYS:
        p = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        src = Image.open(p).convert("RGBA")
        keep = os.path.join(BACKUP, f"ranran_{key}_2x.png")
        if not os.path.exists(keep):
            src.save(keep, "PNG")
        hw = head_run(src)
        b = src.split()[3].getbbox()
        old_h = b[3] - b[1]
        k = TARGET_HEAD / hw
        im = src.crop(b)
        im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))), Image.LANCZOS)
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, BASELINE - im.size[1]), im)
        canvas.save(p, "PNG", optimize=True)
        nb = canvas.split()[3].getbbox()
        print(f"{key:<10}{hw:>8}{old_h:>10}  ->  {k:>6.3f}{im.size[1]:>10}{nb[1]//2:>14}")

    print("\nHEAD_TOP 更新值:")
    for key in KEYS:
        im = Image.open(os.path.join(ASSETS, f"ranran_{key}_2x.png"))
        print(f"  {key}: {im.convert('RGBA').split()[3].getbbox()[1]//2}")


if __name__ == "__main__":
    main()
