"""新增 5 张「空手坐下」表情帧：转头 / 转头 / 笑眼 / 挥手 / 闭眼。

她在地上陪蚂蚁时必须换成空手帧，否则怀里那只和地上那只同时出现；
但原来只有一张空手帧，于是"转头看她""笑""挥手"全都演不出来——陪蚂蚁玩就变成坐着不动。

归一规则：表情帧只改脸和手，姿势/坐凳在同一位置，所以**按内容高统一到 1072px**
（与坐姿家族缩放 0.895 后的值一致），底边落在基线 1340。
不用头宽：挥手会抬高轮廓、闭眼会改变帽子投影，按头宽逐帧算反而会让她一张大一张小。
"""
import json
import os
import subprocess
import urllib.request

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
RAW = os.path.join(ASSETS, "_raw_noant2")
MATTED = os.path.join(ASSETS, "_matted_noant2")
CANVAS = (900, 1360)
BASELINE = 1340
TARGET_H = 1072

NEW = {
    "ntTurn":  "https://aka.doubaocdn.com/s/1d23uapuW0",
    "ntTurnL": "https://aka.doubaocdn.com/s/KzoliDUsCt",
    "ntSmile": "https://aka.doubaocdn.com/s/oYfntXDl1D",
    "ntWave":  "https://aka.doubaocdn.com/s/0ZpZWVAVuP",
    "ntBlink": "https://aka.doubaocdn.com/s/zBlvOB2Smg",
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
                print(f"[skip] {key} 抠图失败")
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
        print(f"[ok] {key}: 原内容高{old_h} 缩放{k:.3f} 新宽{im.size[0]} 顶边{tops[key]}")

    print("\nHEAD_TOP 新增:", json.dumps(tops, ensure_ascii=False))


if __name__ == "__main__":
    main()
