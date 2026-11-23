"""重出走路四帧（接触/过渡/接触/过渡），先落到 _new_walk 备查，不覆盖正式素材。

归一与现有走路家族一致：内容高 1120px、内容顶边 110、画幅 900×1360。
"""
import json
import os
import subprocess
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
RAW = os.path.join(ASSETS, "_raw_walk2")
MATTED = os.path.join(ASSETS, "_matted_walk2")
OUT = os.path.join(ASSETS, "_new_walk")
CANVAS = (900, 1360)
TOP = 110
TARGET_H = 1120

NEW = {
    "walkA":  "https://aka.doubaocdn.com/s/q1cg21I4Ev",
    "walkP1": "https://aka.doubaocdn.com/s/czPSnbNyvE",
    "walkB":  "https://aka.doubaocdn.com/s/lTzm89fHyG",
    "walkP2": "https://aka.doubaocdn.com/s/oDEHaol3pV",
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
    for d in (RAW, MATTED, OUT):
        os.makedirs(d, exist_ok=True)
    info = {}
    for key, url in NEW.items():
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
        b = im.split()[3].getbbox()
        im = im.crop(b)
        k = TARGET_H / im.size[1]
        im = im.resize((max(1, round(im.size[0] * k)), TARGET_H), Image.LANCZOS)
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, TOP), im)
        canvas.save(os.path.join(OUT, f"ranran_{key}_2x.png"), "PNG", optimize=True)
        info[key] = {"w": im.size[0]}
        print(f"[ok] {key}: 宽{im.size[0]} 高{TARGET_H} 顶边{TOP}")

    # 拼对照：整身 + 腿脚细节
    keys = list(NEW.keys())
    ims = [Image.open(os.path.join(OUT, f"ranran_{k}_2x.png")).convert("RGBA") for k in keys]
    bbs = [i.split()[3].getbbox() for i in ims]
    h = max(b[3] - b[1] for b in bbs)
    cols = [i.crop(b) for i, b in zip(ims, bbs)]
    w = sum(c.size[0] for c in cols)
    sheet = Image.new("RGBA", (w, h), (246, 246, 248, 255))
    x = 0
    for c in cols:
        sheet.paste(c, (x, 0), c)
        x += c.size[0]
    sheet.save(os.path.join(ASSETS, "_preview", "走路四帧_重出.png"))

    # 腿脚区放大（取全身下 45%）
    legs = []
    for i, b in zip(ims, bbs):
        c0 = i.crop((b[0], b[1] + int((b[3] - b[1]) * 0.52), b[2], b[3]))
        legs.append(c0)
    lh = max(c.size[1] for c in legs)
    legs = [c.resize((round(c.size[0] * 620 / lh), 620), Image.LANCZOS) for c in legs]
    lw = sum(c.size[0] for c in legs)
    ls = Image.new("RGBA", (lw, 620), (246, 246, 248, 255))
    x = 0
    for c in legs:
        ls.paste(c, (x, 0), c)
        x += c.size[0]
    ls.save(os.path.join(ASSETS, "_preview", "走路腿脚_重出.png"))
    print("preview ok", info)


if __name__ == "__main__":
    main()
