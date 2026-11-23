"""把小蚂蚁从 6 帧扩到 9 帧：原有 6 帧原样保留，新加 3 个动作（蹦起 / 侧面跑 / 四脚朝天）。

新帧按老帧的内容高度做归一（以老 6 格里内容高中位数为标尺），
每格仍是 265×332，底边留 12px 余量，保证拼成一条雪碧图后大小一致。
"""
import json
import os
import subprocess
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
CELL_W, CELL_H = 265, 332
STRIP = os.path.join(ASSETS, "ant_walk.png")
RAW = os.path.join(ASSETS, "_raw_ant")

NEW = {
    "hop":     "https://aka.doubaocdn.com/s/kP7wTXGoUh",
    "sideRun": "https://aka.doubaocdn.com/s/FbkyenIJUK",
    "flop":    "https://aka.doubaocdn.com/s/VjZMMrGE8f",
}


def matte(path):
    p = subprocess.run(
        ["mediakit-cli", "image", "remove-image-background", "--image-url", path, "--scene", "general"],
        capture_output=True, text=True, encoding="utf-8", timeout=240)
    if p.returncode != 0:
        return None
    try:
        d = json.loads(p.stdout)
    except Exception:
        return None
    return d.get("image_url") or (d.get("data") or {}).get("image_url")


def main():
    os.makedirs(RAW, exist_ok=True)
    strip = Image.open(STRIP).convert("RGBA")
    n_total = strip.size[0] // CELL_W
    base_n = 6                                     # 原始 6 格（idle/stepL/stepR/fast/sit/lookUp）
    print(f"当前雪碧图 {n_total} 格，取前 {base_n} 格作为原有帧")
    heights = []
    for i in range(base_n):
        cell = strip.crop((i * CELL_W, 0, (i + 1) * CELL_W, CELL_H))
        b = cell.split()[3].getbbox()
        heights.append(b[3] - b[1])
    heights.sort()
    target_h = heights[len(heights) // 2]
    print(f"老帧内容高={heights} 标尺={target_h}")

    canvases = [strip.crop((i * CELL_W, 0, (i + 1) * CELL_W, CELL_H)) for i in range(base_n)]

    for name, url in NEW.items():
        rp = os.path.join(RAW, f"{name}.png")
        if not os.path.exists(rp):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r, open(rp, "wb") as fh:
                fh.write(r.read())
        mp = os.path.join(RAW, f"{name}_nobg.png")
        if not os.path.exists(mp):
            u = matte(rp)
            if not u:
                print(f"[skip] {name}: 抠图失败")
                continue
            urllib.request.urlretrieve(u, mp)
        im = Image.open(mp).convert("RGBA")
        im = im.crop(im.split()[3].getbbox())
        # 高度对齐老帧，同时不能超出格子宽度（四脚朝天是横躺的，只按高度缩会两边被裁）
        k = min(target_h / im.size[1], (CELL_W - 8) / im.size[0])
        im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))), Image.LANCZOS)
        cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
        cell.paste(im, ((CELL_W - im.size[0]) // 2, CELL_H - 12 - im.size[1]), im)
        canvases.append(cell)
        print(f"[add] {name} 内容高={target_h} 宽={im.size[0]}")

    out = Image.new("RGBA", (CELL_W * len(canvases), CELL_H), (0, 0, 0, 0))
    for i, c in enumerate(canvases):
        out.paste(c, (i * CELL_W, 0), c)
    out.save(STRIP, "PNG", optimize=True)
    print(f"\n新雪碧图 {out.size[0]}×{out.size[1]}，共 {len(canvases)} 格")

    order = ["idle", "stepL", "stepR", "fast", "sit", "lookUp", "hop", "sideRun", "flop"]
    meta = {"cellW": CELL_W, "cellH": CELL_H, "frames": len(canvases), "order": order}
    with open(os.path.join(ASSETS, "ant_walk.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
