"""修蚂蚁：后四格（lookUp / hop / sideRun / flop）跟前面五格不是同一只，
用母版重出后按 265×332 回填雪碧图，前五格原样保留。

归一规则：内容高 298；若因此宽度超过 258，则改为按宽 258 缩（横躺帧会走这条）。
底边统一落在基线（取原五格的最大内容底边），水平居中。
"""
import json
import os
import subprocess
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
RAW = os.path.join(ASSETS, "_raw_ant2")
MATTED = os.path.join(ASSETS, "_matted_ant2")
SHEET = os.path.join(ASSETS, "ant_walk.png")
CW, CH = 265, 332
TARGET_H = 298
MAX_W = 258

REPL = {
    5: ("lookUp", "https://aka.doubaocdn.com/s/fMZzUsBvcK"),
    6: ("hop", "https://aka.doubaocdn.com/s/L2ZN31iay0"),
    7: ("sideRun", "https://aka.doubaocdn.com/s/n7BOmOu6gP"),
    8: ("flop", "https://aka.doubaocdn.com/s/6VqGejWiC5"),
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
    for d in (RAW, MATTED):
        os.makedirs(d, exist_ok=True)
    sheet = Image.open(SHEET).convert("RGBA")
    cells = [sheet.crop((i * CW, 0, (i + 1) * CW, CH)) for i in range(sheet.size[0] // CW)]

    # 基线：原五格内容底边的最大值
    base_y = max(c.split()[3].getbbox()[3] for c in cells[:5])
    print("原五格基线:", base_y)

    for idx, (key, url) in REPL.items():
        rp = os.path.join(RAW, f"{key}.png")
        mp = os.path.join(MATTED, f"{key}.png")
        if not os.path.exists(mp):
            if not os.path.exists(rp):
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=60) as r, open(rp, "wb") as fh:
                    fh.write(r.read())
            u = matte(rp)
            if not u:
                print(f"[skip] {key}")
                continue
            urllib.request.urlretrieve(u, mp)
        im = Image.open(mp).convert("RGBA")
        im = im.crop(im.split()[3].getbbox())
        k = TARGET_H / im.size[1]
        if im.size[0] * k > MAX_W:
            k = MAX_W / im.size[0]
        im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k)), ), Image.LANCZOS)
        if im.size[1] > CH - 8:
            im = im.resize((round(im.size[0] * (CH - 8) / im.size[1]), CH - 8), Image.LANCZOS)
        cell = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        cell.paste(im, ((CW - im.size[0]) // 2, base_y - im.size[1]), im)
        cells[idx] = cell
        nb = cell.split()[3].getbbox()
        print(f"[ok] {key}: {im.size[0]}×{im.size[1]} 顶边{nb[1]} 底边{nb[3]}")

    out = Image.new("RGBA", (CW * len(cells), CH), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        out.paste(c, (i * CW, 0), c)
    out.save(SHEET, "PNG", optimize=True)
    print("写入", SHEET, out.size)

    preview = Image.new("RGBA", (CW * 9, CH), (246, 246, 248, 255))
    for i, c in enumerate(cells):
        preview.paste(c, (i * CW, 0), c)
    preview.save(os.path.join(ASSETS, "_preview", "蚂蚁九格_修后.png"))


if __name__ == "__main__":
    main()
