"""让坐姿帧的"头"和站立帧一样大（统一缩放，避免转头帧被误判）。

问题：坐姿帧和站立帧都被规整成"内容同高"，但坐着的身体本来就比站着矮，
内容同高就等于把坐着的人整体放大 —— 坐姿看着人很大，一站就缩。

做法：取站立帧头宽 468px 与坐姿基准帧头宽 523px 的比值 0.895，作为**统一缩放**，
8 张坐姿帧全部按这一个比例缩（不用逐帧头宽：turn/turnL 转头时帽子投影变窄，
逐帧匹配会把转头帧放大，一转头人就胖一圈）。底边仍落在基线。
"""

import os

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
CANVAS = (900, 1360)
BASELINE = 1340
BACKUP = os.path.join(ASSETS, "_before_headfix")
UNIFORM = 0.895

SITS = ["base", "blink", "talk", "smile", "turn", "turnL", "wave", "noant"]


def main():
    print(f"{'帧':<8}{'原内容高':>10}{'新内容高':>10}{'新顶边(CSS)':>14}")
    tops = {}
    for key in SITS:
        p = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        src_path = os.path.join(BACKUP, f"ranran_{key}_2x.png")
        src = Image.open(src_path if os.path.exists(src_path) else p).convert("RGBA")
        b = src.split()[3].getbbox()
        old_h = b[3] - b[1]
        im = src.crop(b)
        im = im.resize((max(1, round(im.size[0] * UNIFORM)), max(1, round(im.size[1] * UNIFORM))), Image.LANCZOS)
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, BASELINE - im.size[1]), im)
        canvas.save(p, "PNG", optimize=True)
        nb = canvas.split()[3].getbbox()
        tops[key] = nb[1] // 2
        print(f"{key:<8}{old_h:>10}{im.size[1]:>10}{tops[key]:>14}")

    print("\n新 HEAD_TOP（坐姿部分）:")
    print(", ".join(f"{k}:{v}" for k, v in tops.items()))


if __name__ == "__main__":
    main()
