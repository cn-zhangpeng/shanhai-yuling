"""把 4 张走路帧整体下移，让脚踩回站姿的同一条基线（1340）。

背景：build_walk_cycle2.py 二次归一化时把内容贴到了 BASELINE - TARGET_H 以上 110px 的位置，
脚底停在 1229/1228，而站姿 1340、坐姿 1339 —— 于是走路时整只浮空 48px（显示尺寸），
气泡锚点也跟着错。这里只做整体平移，不重采样、不改尺寸，帧与帧的起伏关系原样保留。

跑法：python tools\fix_walk_baseline.py
"""
import os
import shutil

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
CANVAS = (900, 1360)
BASELINE = 1340          # 站姿脚底（base 坐姿是 1339，差 1px 可忽略）
KEYS = ["walkA", "walkB", "walkP1", "walkP2"]
BACKUP = os.path.join(ASSETS, "_before_walkfix2")


def main():
    os.makedirs(BACKUP, exist_ok=True)

    # 统一位移量：四帧底边取最大值，下移到 BASELINE，保留它们之间 1px 的天然起伏
    bottoms = []
    for key in KEYS:
        p = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        b = Image.open(p).convert("RGBA").getchannel("A").getbbox()
        bottoms.append(b[3])
    shift = BASELINE - max(bottoms)
    print(f"统一下移 {shift}px（底边 {max(bottoms)} -> {BASELINE}）\n")

    for key in KEYS:
        p = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        src = Image.open(p).convert("RGBA")
        old = src.getchannel("A").getbbox()
        keep = os.path.join(BACKUP, f"ranran_{key}_2x.png")
        if not os.path.exists(keep):
            shutil.copy2(p, keep)

        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        canvas.paste(src.crop(old), (old[0], old[1] + shift))
        canvas.save(p, "PNG", optimize=True)

        nb = canvas.getchannel("A").getbbox()
        print(f"{key:<8} top {old[1]:>4} -> {nb[1]:>4}    bottom {old[3]:>4} -> {nb[3]:>4}   高 {nb[3]-nb[1]}")


if __name__ == "__main__":
    main()
