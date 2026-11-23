"""把小蚂蚁 4 帧动作合成为横向雪碧图，输出统一格位与基线，供 CSS 播放。
流程：下载 → 白底转透明 → 裁内容框 → 统一高度 → 底部居中排版 → 横向拼接。
"""
import json
import os
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

OUT_DIR = str(_ROOT / "desktop-shell" / "assets")
TMP_DIR = os.path.join(OUT_DIR, "_tmp_ant")
TARGET_H = 640          # 每格内容统一高度
CELL_PAD = 24           # 格内留白，避免相邻帧触碰
HARD, SOFT = 246, 222   # 与 make_alpha 同一套阈值

URLS = [
    "https://aka.doubaocdn.com/s/xxGEwAeWax",  # 1 待机
    "https://aka.doubaocdn.com/s/27fNxFekNQ",  # 2 迈左脚
    "https://aka.doubaocdn.com/s/LefHahuRbd",  # 3 迈右脚
    "https://aka.doubaocdn.com/s/eQqVxWtgcj",  # 4 仰头
]


def luma(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def key_white(im):
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if max(r, g, b) - min(r, g, b) < 14 and luma(r, g, b) >= HARD:
                px[x, y] = (r, g, b, 0)
            elif max(r, g, b) - min(r, g, b) < 30 and luma(r, g, b) >= SOFT:
                k = (HARD - luma(r, g, b)) / (HARD - SOFT)
                px[x, y] = (r, g, b, int(a * k))
    return im


def main():
    os.makedirs(TMP_DIR, exist_ok=True)
    frames = []
    for i, u in enumerate(URLS):
        p = os.path.join(TMP_DIR, f"ant_{i+1}.png")
        if not os.path.exists(p):
            urllib.request.urlretrieve(u, p)
        im = key_white(Image.open(p))
        bbox = im.split()[3].getbbox()
        im = im.crop(bbox)
        scale = TARGET_H / im.size[1]
        im = im.resize((max(1, round(im.size[0] * scale)), TARGET_H), Image.LANCZOS)
        frames.append(im)
        print(f"frame {i+1}: crop {bbox} -> {im.size}")

    cell_w = max(f.size[0] for f in frames) + CELL_PAD * 2
    cell_h = TARGET_H + CELL_PAD * 2
    strip = Image.new("RGBA", (cell_w * len(frames), cell_h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        x = i * cell_w + (cell_w - f.size[0]) // 2
        y = cell_h - CELL_PAD - f.size[1]      # 底边对齐，脚踩同一条基线
        strip.paste(f, (x, y), f)

    out = os.path.join(OUT_DIR, "ant_walk.png")
    strip.save(out, "PNG", optimize=True)
    meta = {"frames": len(frames), "cellW": cell_w, "cellH": cell_h,
            "file": "ant_walk.png", "size": list(strip.size),
            "kb": round(os.path.getsize(out) / 1024)}
    print(json.dumps(meta, ensure_ascii=False))
    with open(os.path.join(OUT_DIR, "ant_walk.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
