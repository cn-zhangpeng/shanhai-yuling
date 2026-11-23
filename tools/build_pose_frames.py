"""动作姿态帧管线 v2：按"头宽"锚定缩放，保证站/走/跳/蹲各姿态在她身上是同一个大小。
画幅统一 900×1360（CSS 450×680，dpr1.5 下超采样 1.33），内容底边统一落在同一条基线。
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
RAW = os.path.join(ASSETS, "_raw_pose")
MATTED = os.path.join(ASSETS, "_matted_pose")

CANVAS = (900, 1360)
BASELINE = 1340

POSE = {
    "stand":   "https://aka.doubaocdn.com/s/4nnZ26Fg0Y",
    "walkA":   "https://aka.doubaocdn.com/s/BxcNwFKE0G",
    "walkB":   "https://aka.doubaocdn.com/s/Zi9dk4IiTU",
    "phone":   "https://aka.doubaocdn.com/s/deUBU9KM2V",
    "ropeAir": "https://aka.doubaocdn.com/s/GqhVJPm1Ym",
    "ropeLand": "https://aka.doubaocdn.com/s/kdFQ9QGdNI",
    "walkP1":  "https://aka.doubaocdn.com/s/oJMCsYV8FZ",
    "walkP2":  "https://aka.doubaocdn.com/s/JTDgIVMv3P",
}
# 用于测头宽的帧（跳绳帧顶部有绳，不参与测量）
MEASURE = ["stand", "walkA", "walkB", "phone"]
SIT = ["base", "blink", "talk", "smile", "turn", "turnL", "wave", "noant"]


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


def head_width(im):
    """内容框上部 10%~22% 高度带的横向最大跨度，作为"帽子/头宽"代理，跨姿态可比"""
    b = im.split()[3].getbbox()
    w, h = im.size
    y0, y1 = b[1] + int((b[3] - b[1]) * 0.10), b[1] + int((b[3] - b[1]) * 0.22)
    a = im.crop((0, y0, w, y1)).split()[3]
    band_h = y1 - y0
    best = 0
    for y in range(band_h):
        row = [x for x in range(a.size[0]) if a.getpixel((x, y)) > 90]
        if row:
            best = max(best, row[-1] - row[0])
    return best


def place(im, f):
    im = im.crop(im.split()[3].getbbox())
    nh = round(im.size[1] * f)
    im = im.resize((round(im.size[0] * f), nh), Image.LANCZOS)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, BASELINE - nh), im)
    return canvas


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(MATTED, exist_ok=True)

    target_hw = head_width(Image.open(os.path.join(ASSETS, "ranran_base_2x.png")).convert("RGBA"))
    print("基准头宽(坐姿):", target_hw, "px")

    for key in SIT:
        src = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        im = Image.open(src).convert("RGBA")
        b = im.split()[3].getbbox()
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        canvas.paste(im, ((CANVAS[0] - im.size[0]) // 2, BASELINE - b[3]), im)
        canvas.save(src, "PNG", optimize=True)

    factors = {}
    for key, url in POSE.items():
        rp = os.path.join(RAW, f"{key}.png")
        mp = os.path.join(MATTED, f"{key}.png")
        if not os.path.exists(mp):                     # 已抠过就复用，别重复花钱
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r, open(rp, "wb") as fh:
                fh.write(r.read())
            u, err = matte(rp)
            if not u:
                print(f"[FAIL] {key}: {err}")
                continue
            urllib.request.urlretrieve(u, mp)
        im = Image.open(mp).convert("RGBA")
        hw = head_width(im)
        if key in MEASURE:
            factors[key] = target_hw / hw
            print(f"  {key}: 头宽={hw} -> 缩放 {target_hw / hw:.3f}")

    # 逐帧单测的头宽波动来自成图本身（±10%），单独按帧缩放会让走路时大小一跳一跳，
    # 所以取总平均做一个统一缩放，剩下的差异靠对照表肉眼兜底
    f_avg = sum(factors.values()) / len(factors)
    print("统一缩放:", round(f_avg, 3))

    for key in POSE:
        mp = os.path.join(MATTED, f"{key}.png")
        if not os.path.exists(mp):
            continue
        f = f_avg
        out = place(Image.open(mp).convert("RGBA"), f)
        dst = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        out.save(dst, "PNG", optimize=True)
        print(f"[pose] {key} scale={f:.3f} 内容高={out.split()[3].getbbox()[3]-out.split()[3].getbbox()[1]} {os.path.getsize(dst)/1024:.0f}KB")


if __name__ == "__main__":
    main()
