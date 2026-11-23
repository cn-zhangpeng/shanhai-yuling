"""新增两组坐姿手脚小动作：晃脚 / 抚帽边，各带"抱着蚂蚁"和"空手"两个版本。

归一：与坐姿家族一致 —— 内容高 1072px、底边 1340、水平居中。
（晃脚只抬小腿，抬起的脚尖不会低于着地的另一只脚，所以内容框顶/底不变，按内容高归一安全）
"""
import json
import os
import subprocess
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
RAW = os.path.join(ASSETS, "_raw_gesture")
MATTED = os.path.join(ASSETS, "_matted_gesture")
CANVAS = (900, 1360)
BASELINE = 1340
TARGET_H = 1072

NEW = {
    "footSwing":   "https://aka.doubaocdn.com/s/dYZg8AZ5r2",
    "handEar":     "https://aka.doubaocdn.com/s/ZMxkgb04kN",
    "ntFootSwing": "https://aka.doubaocdn.com/s/t5ydZVV4kR",
    "ntHandEar":   "https://aka.doubaocdn.com/s/6y3sGbIdr1",
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
    os.makedirs(MATTED, exist_ok=True)
    tops = {}
    for key, url in NEW.items():
        rp = os.path.join(RAW, f"{key}.png")
        mp = os.path.join(MATTED, f"{key}.png")
        if not os.path.exists(mp):
            if not os.path.exists(rp):
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=45) as r, open(rp, "wb") as fh:
                    fh.write(r.read())
            u = matte(rp)
            if not u:
                print(f"[skip] {key}")
                continue
            urllib.request.urlretrieve(u, mp)
        im = Image.open(mp).convert("RGBA")
        b = im.split()[3].getbbox()
        old_h = b[3] - b[1]
        im = im.crop(b)
        k = TARGET_H / im.size[1]
        im = im.resize((max(1, round(im.size[0] * k)), TARGET_H), Image.LANCZOS)
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, BASELINE - TARGET_H), im)
        canvas.save(os.path.join(ASSETS, f"ranran_{key}_2x.png"), "PNG", optimize=True)
        nb = canvas.split()[3].getbbox()
        tops[key] = nb[1] // 2
        print(f"[ok] {key}: 原内容高{old_h} 缩放{k:.3f} 宽{im.size[0]} 顶边{tops[key]}")

    print("\nHEAD_TOP 新增:", json.dumps(tops, ensure_ascii=False))


if __name__ == "__main__":
    main()
