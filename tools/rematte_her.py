"""她 8 张帧重做：
1) 先量化当前素材"眼区"的透明度（确认是不是被抠成半透明）
2) 从原始白底图取回（旧 5 帧用原始生成 URL；新 3 帧用本地原始下载）
3) 逐张走 MediaKit 语义抠图
4) 按母版内容框归一化（同高度、底边居中）后输出 900×1200
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
TMP = os.path.join(ASSETS, "_tmp_frames")
RAW = os.path.join(ASSETS, "_raw_her")
MATTED = os.path.join(ASSETS, "_matted_her")
FRAMES_SRC = os.path.join(ROOT, "art", "source", "frames")
MASTER = os.path.join(ROOT, "art", "source", "master", "00_身份母版_玩偶服抱蚂蚁.png")

HER_W, HER_H = 900, 1200

# 旧 5 帧的原始生成图（白底），新 3 帧用本地原件
URLS = {
    "base": "https://aka.doubaocdn.com/s/LiBdvXbzyU",
    "blink": "https://aka.doubaocdn.com/s/sCKaMPq7s0",
    "talk": "https://aka.doubaocdn.com/s/SEzwW3tDRJ",
    "smile": "https://aka.doubaocdn.com/s/OIUZW6RZSu",
    "turn": "https://aka.doubaocdn.com/s/ZEcNV5S0fv",
}
LOCAL = {
    "wave": os.path.join(TMP, "ranran_wave_hi.png"),
    "turnL": os.path.join(TMP, "ranran_turnL_hi.png"),
    "noant": os.path.join(TMP, "ranran_noant_hi.png"),
}


def probe_alpha():
    p = os.path.join(ASSETS, "ranran_base_2x.png")
    im = Image.open(p).convert("RGBA")
    w, h = im.size
    box = (int(w * 0.34), int(h * 0.30), int(w * 0.68), int(h * 0.40))
    c = im.crop(box)
    px = list(c.getdata())
    total = len(px)
    semi = sum(1 for t in px if 0 < t[3] < 250)
    zero = sum(1 for t in px if t[3] == 0)
    print(f"[眼区透明度] 总 {total}  半透明 {semi}  全透明 {zero}  占比 {(semi+zero)/total:.1%}")


def fetch_raw():
    os.makedirs(RAW, exist_ok=True)
    for key, url in URLS.items():
        dst = os.path.join(RAW, f"{key}.png")
        if os.path.exists(dst):
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r, open(dst, "wb") as f:
                f.write(r.read())
            print(f"[raw] {key} {os.path.getsize(dst)/1024:.0f}KB")
        except Exception as e:
            print(f"[raw][FAIL] {key}: {e}")
    for key, src in LOCAL.items():
        dst = os.path.join(RAW, f"{key}.png")
        if os.path.exists(dst) or not os.path.exists(src):
            continue
        Image.open(src).convert("RGB").save(dst)
        print(f"[raw] {key} (本地原件)")


def call(path):
    cmd = ["mediakit-cli", "image", "remove-image-background", "--image-url", path, "--scene", "general"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=240)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout)[:200]
    try:
        d = json.loads(p.stdout)
    except Exception as e:
        return None, f"parse: {e} :: {p.stdout[:150]}"
    if isinstance(d.get("image_url"), str):
        return d["image_url"], None
    if isinstance(d.get("data"), dict) and isinstance(d["data"].get("image_url"), str):
        return d["data"]["image_url"], None
    return None, json.dumps(d, ensure_ascii=False)[:200]


def matte_and_normalize():
    os.makedirs(MATTED, exist_ok=True)
    master = Image.open(MASTER).convert("RGBA")
    mb = master.split()[3].getbbox() if master.split()[3].getextrema()[0] < 255 else None
    if mb is None:
        # 白底母版没有 alpha，用白底泛洪拿内容框
        rgb = master.convert("RGB")
        diff = Image.new("L", rgb.size, 255)
        import PIL.ImageChops as IC
        lum = rgb.convert("L")
        mb = lum.point(lambda v: 255 if v < 245 else 0).getbbox()
    base_h = mb[3] - mb[1]
    cx = (mb[0] + mb[2]) // 2
    print("母版内容框:", mb, "高", base_h)

    for key in ["base", "blink", "talk", "smile", "turn", "wave", "turnL", "noant"]:
        src = os.path.join(RAW, f"{key}.png")
        if not os.path.exists(src):
            print(f"[跳过] {key} 无原图")
            continue
        url, err = call(src)
        if not url:
            print(f"[抠图失败] {key}: {err}")
            continue
        dst = os.path.join(MATTED, f"{key}.png")
        urllib.request.urlretrieve(url, dst)
        im = Image.open(dst).convert("RGBA")
        b = im.split()[3].getbbox()
        im = im.crop(b)
        k = base_h / im.size[1]
        im = im.resize((round(im.size[0] * k), base_h), Image.LANCZOS)
        canvas = Image.new("RGBA", master.size, (0, 0, 0, 0))
        canvas.paste(im, (cx - im.size[0] // 2, mb[3] - im.size[1]), im)
        canvas = canvas.resize((HER_W, HER_H), Image.LANCZOS)
        out = os.path.join(ASSETS, f"ranran_{key}_2x.png")
        canvas.save(out, "PNG", optimize=True)
        os.makedirs(FRAMES_SRC, exist_ok=True)
        canvas.save(os.path.join(FRAMES_SRC, f"ranran_{key}_master.png"), "PNG")
        print(f"[ok] ranran_{key}_2x.png {os.path.getsize(out)/1024:.0f}KB")


if __name__ == "__main__":
    probe_alpha()
    fetch_raw()
    matte_and_normalize()
    print("---- 重抠后复检 ----")
    probe_alpha()
