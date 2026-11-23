"""把新生成的动作帧归一化到母版的画幅与基线，避免换帧时人物"跳大小 / 跳位置"。
做法：白底转透明 → 取内容框 → 按内容高度缩放到母版内容高度 → 底边居中贴回母版画布。
"""
import os
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

MASTER = str(_ROOT / "art" / "source" / "master" / "00_身份母版_玩偶服抱蚂蚁.png")
OUT = str(_ROOT / "desktop-shell" / "assets")
TMP = os.path.join(OUT, "_tmp_frames")
HARD, SOFT = 246, 222

NEW_FRAMES = [
    ("https://aka.doubaocdn.com/s/em9YwJLer9", "ranran_wave_hi.png"),
    ("https://aka.doubaocdn.com/s/R6mSE9nwaY", "ranran_turnL_hi.png"),
    ("https://aka.doubaocdn.com/s/nXN9RsOEXP", "ranran_noant_hi.png"),  # 空手（放下蚂蚁用）
]

ANT_FRAMES = [
    ("https://aka.doubaocdn.com/s/xxGEwAeWax", "ant_0_idle.png"),   # 待机
    ("https://aka.doubaocdn.com/s/27fNxFekNQ", "ant_1_walkA.png"),  # 迈左脚
    ("https://aka.doubaocdn.com/s/LefHahuRbd", "ant_2_walkB.png"),  # 迈右脚
    ("https://aka.doubaocdn.com/s/k5gg5yZxmm", "ant_3_run.png"),    # 快走
    ("https://aka.doubaocdn.com/s/wXR4kF37GQ", "ant_4_sit.png"),    # 蹲坐
    ("https://aka.doubaocdn.com/s/eQqVxWtgcj", "ant_5_look.png"),   # 仰头
]
ANT_TARGET_H = 620
ANT_PAD = 26


def luma(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def key_white(im):
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            s = max(r, g, b) - min(r, g, b)
            l = luma(r, g, b)
            if s < 14 and l >= HARD:
                px[x, y] = (r, g, b, 0)
            elif s < 30 and l >= SOFT:
                px[x, y] = (r, g, b, int(a * (HARD - l) / (HARD - SOFT)))
    return im


def fetch(url, name):
    os.makedirs(TMP, exist_ok=True)
    p = os.path.join(TMP, name)
    if not os.path.exists(p):
        urllib.request.urlretrieve(url, p)
    return p


def build_her():
    master = key_white(Image.open(MASTER))
    mb = master.split()[3].getbbox()
    print("母版画幅:", master.size, "内容框:", mb)
    base_h = mb[3] - mb[1]
    center_x = (mb[0] + mb[2]) // 2

    for url, out_name in NEW_FRAMES:
        p = fetch(url, out_name)
        im = key_white(Image.open(p))
        b = im.split()[3].getbbox()
        im = im.crop(b)
        scale = base_h / im.size[1]
        im = im.resize((round(im.size[0] * scale), base_h), Image.LANCZOS)
        canvas = Image.new("RGBA", master.size, (0, 0, 0, 0))
        x = center_x - im.size[0] // 2
        y = mb[3] - im.size[1]
        canvas.paste(im, (x, y), im)
        canvas.save(os.path.join(OUT, out_name), "PNG", optimize=True)
        print(f"{out_name}: 原始框 {b} -> 贴到 ({x},{y}) 高 {base_h}")


def build_ant():
    frames = []
    for url, name in ANT_FRAMES:
        p = fetch(url, name)
        im = key_white(Image.open(p))
        im = im.crop(im.split()[3].getbbox())
        scale = ANT_TARGET_H / im.size[1]
        im = im.resize((max(1, round(im.size[0] * scale)), ANT_TARGET_H), Image.LANCZOS)
        frames.append(im)

    cell_w = max(f.size[0] for f in frames) + ANT_PAD * 2
    cell_h = ANT_TARGET_H + ANT_PAD * 2
    strip = Image.new("RGBA", (cell_w * len(frames), cell_h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f, (i * cell_w + (cell_w - f.size[0]) // 2, cell_h - ANT_PAD - f.size[1]), f)

    out = os.path.join(OUT, "ant_walk.png")
    strip.save(out, "PNG", optimize=True)
    print(f"ant_walk.png: {strip.size}  格位 {cell_w}x{cell_h}  {os.path.getsize(out)/1024:.0f}KB")
    import json
    meta = {"frames": len(frames), "cellW": cell_w, "cellH": cell_h}
    json.dump(meta, open(os.path.join(OUT, "ant_walk.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    build_her()
    build_ant()
