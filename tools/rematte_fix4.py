"""重出 4 张不一致的帧：右转 / 左转 / 挥手 / 空手。
流程同前：下载原始白底图 → MediaKit 语义抠图 → 按母版内容框归一化 → 900×1200。
"""
import json
import os
import shutil
import subprocess
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ROOT = str(_ROOT)
ASSETS = os.path.join(ROOT, "desktop-shell", "assets")
RAW = os.path.join(ASSETS, "_raw_her")
MATTED = os.path.join(ASSETS, "_matted_her")
FRAMES_SRC = os.path.join(ROOT, "art", "source", "frames")
MASTER = os.path.join(ROOT, "art", "source", "master", "00_身份母版_玩偶服抱蚂蚁.png")

HER_W, HER_H = 900, 1200

FIX = {
    "turn": "https://aka.doubaocdn.com/s/jpdqPpBPpV",
    "turnL": "https://aka.doubaocdn.com/s/8ryD2j1v7z",
    "wave": "https://aka.doubaocdn.com/s/GtvIQ2AMcG",
    "noant": "https://aka.doubaocdn.com/s/h1BfW3aYAN",
}


def matte(path):
    cmd = ["mediakit-cli", "image", "remove-image-background", "--image-url", path, "--scene", "general"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=240)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout)[:200]
    d = json.loads(p.stdout)
    if isinstance(d.get("image_url"), str):
        return d["image_url"], None
    if isinstance(d.get("data"), dict) and isinstance(d["data"].get("image_url"), str):
        return d["data"]["image_url"], None
    return None, "no url"


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(MATTED, exist_ok=True)
    os.makedirs(FRAMES_SRC, exist_ok=True)

    master = Image.open(MASTER).convert("RGB")
    lum = master.convert("L")
    mb = lum.point(lambda v: 255 if v < 245 else 0).getbbox()
    base_h = mb[3] - mb[1]
    cx = (mb[0] + mb[2]) // 2
    print("母版内容框:", mb, "高", base_h)

    for key, url in FIX.items():
        src = os.path.join(RAW, f"{key}.png")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as r, open(src, "wb") as f:
            f.write(r.read())
        u, err = matte(src)
        if not u:
            print(f"[FAIL] {key}: {err}")
            continue
        dst = os.path.join(MATTED, f"{key}.png")
        urllib.request.urlretrieve(u, dst)
        im = Image.open(dst).convert("RGBA").crop(Image.open(dst).convert("RGBA").split()[3].getbbox())
        k = base_h / im.size[1]
        im = im.resize((round(im.size[0] * k), base_h), Image.LANCZOS)
        canvas = Image.new("RGBA", master.size, (0, 0, 0, 0))
        canvas.paste(im, (cx - im.size[0] // 2, mb[3] - im.size[1]), im)
        canvas.resize((HER_W, HER_H), Image.LANCZOS).save(os.path.join(ASSETS, f"ranran_{key}_2x.png"), "PNG", optimize=True)
        shutil.copy2(os.path.join(ASSETS, f"ranran_{key}_2x.png"), os.path.join(FRAMES_SRC, f"ranran_{key}_master.png"))
        print(f"[ok] {key}")


if __name__ == "__main__":
    main()
