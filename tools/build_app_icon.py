"""把生成的头肩插画做成应用/托盘图标：语义抠图 → 裁内容 → 正方形留白 → 多尺寸导出。"""
import json
import os
import subprocess
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
ICON_DIR = os.path.join(ASSETS, "icon")
RAW = os.path.join(ASSETS, "_raw_icon")
URL = "https://aka.doubaocdn.com/s/aZBWRWK6Up"


def matte(path):
    p = subprocess.run(
        ["mediakit-cli", "image", "remove-image-background", "--image-url", path, "--scene", "general"],
        capture_output=True, text=True, encoding="utf-8", timeout=240)
    if p.returncode != 0:
        print(p.stdout[-400:], p.stderr[-400:])
        return None
    d = json.loads(p.stdout)
    return d.get("image_url") or (d.get("data") or {}).get("image_url")


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(ICON_DIR, exist_ok=True)
    rp = os.path.join(RAW, "icon_src.png")
    mp = os.path.join(RAW, "icon_matted.png")
    if not os.path.exists(rp):
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(rp, "wb") as fh:
            fh.write(r.read())
    if not os.path.exists(mp):
        u = matte(rp)
        urllib.request.urlretrieve(u, mp)

    im = Image.open(mp).convert("RGBA")
    im = im.crop(im.split()[3].getbbox())

    # 正方形画布：主体占 88%，四边等留白
    side = int(max(im.size) / 0.88)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2), im)

    for size in (512, 256, 128, 64, 48, 32, 16):
        out = os.path.join(ICON_DIR, f"ranran_icon_{size}.png")
        sq.resize((size, size), Image.LANCZOS).save(out)
        print("写出", out)

    sq.resize((256, 256), Image.LANCZOS).save(os.path.join(ICON_DIR, "ranran_icon.png"))
    # Windows .ico（多尺寸内嵌）
    sq.save(os.path.join(ICON_DIR, "ranran.ico"),
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ico ok")


if __name__ == "__main__":
    main()
