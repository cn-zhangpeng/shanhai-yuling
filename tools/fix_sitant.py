"""重抠 7 张抱蚁帧（怀里蚂蚁统一为活物外形），归一化到 900×1360，
并输出每帧内容顶边（用于把讲话气泡贴到她头顶，而不是飘在窗口最上方）。
"""
import json
import os
import subprocess
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ROOT = str(_ROOT)
ASSETS = os.path.join(ROOT, "desktop-shell", "assets")
RAW = os.path.join(ASSETS, "_raw_sitant")
MATTED = os.path.join(ASSETS, "_matted_sitant")

CANVAS = (900, 1360)
BASELINE = 1340
CONTENT_H = 1200

FIX = {
    "base":  "https://aka.doubaocdn.com/s/GsBigvVFic",
    "blink": "https://aka.doubaocdn.com/s/bBOHIoPUny",
    "talk":  "https://aka.doubaocdn.com/s/fdP88m5o9H",
    "smile": "https://aka.doubaocdn.com/s/f7MIC17Ls9",
    "turn":  "https://aka.doubaocdn.com/s/O4G5WZQ3Tv",
    "turnL": "https://aka.doubaocdn.com/s/P90wdyp1wL",
    "wave":  "https://aka.doubaocdn.com/s/vl3wErU9rg",
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
    for key, url in FIX.items():
        mp = os.path.join(MATTED, f"{key}.png")
        if not os.path.exists(mp):
            rp = os.path.join(RAW, f"{key}.png")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r, open(rp, "wb") as fh:
                fh.write(r.read())
            u, err = matte(rp)
            if not u:
                print(f"[FAIL] {key}: {err}")
                continue
            urllib.request.urlretrieve(u, mp)
        im = Image.open(mp).convert("RGBA")
        b = im.split()[3].getbbox()
        im = im.crop(b)
        k = CONTENT_H / im.size[1]
        im = im.resize((round(im.size[0] * k), CONTENT_H), Image.LANCZOS)
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, BASELINE - CONTENT_H), im)
        canvas.save(os.path.join(ASSETS, f"ranran_{key}_2x.png"), "PNG", optimize=True)
        print(f"[ok] {key}")

    print("\n=== 每帧内容顶边（CSS px，画布高 680）===")
    tops = {}
    for key in ["base", "blink", "talk", "smile", "turn", "turnL", "wave", "noant",
                "stand", "walkA", "walkB", "walkP1", "walkP2", "phone", "ropeAir", "ropeLand"]:
        p = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        im = Image.open(p).convert("RGBA")
        bb = im.split()[3].getbbox()
        tops[key] = round(bb[1] / 2)
        print(f"  {key:<9} 顶边={tops[key]:>4}px")
    print("\nHEAD_TOP =", json.dumps(tops, ensure_ascii=False))


if __name__ == "__main__":
    main()
