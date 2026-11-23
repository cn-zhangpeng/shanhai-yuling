"""用 MediaKit 语义抠图重做小蚂蚁 6 帧（替代手工阈值，避免吃掉眼白）。
调用 mediakit-cli image remove-image-background --scene general，结果落盘到 assets/_matted/。
"""
import json
import os
import subprocess
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ROOT = str(_ROOT)
TMP = os.path.join(ROOT, "desktop-shell", "assets", "_tmp_frames")
OUT = os.path.join(ROOT, "desktop-shell", "assets", "_matted")

ORDER = ["idle", "walkA", "walkB", "run", "sit", "look"]


def call(path):
    cmd = ["mediakit-cli", "image", "remove-image-background",
           "--image-url", path, "--scene", "general"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout)[:300]
    try:
        data = json.loads(p.stdout)
    except Exception as e:
        return None, f"parse fail: {e} :: {p.stdout[:200]}"
    for key in ("image_url", "data"):
        v = data.get(key)
        if isinstance(v, str):
            return v, None
        if isinstance(v, dict) and isinstance(v.get("image_url"), str):
            return v["image_url"], None
    return None, json.dumps(data, ensure_ascii=False)[:300]


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, name in enumerate(ORDER):
        src = os.path.join(TMP, f"ant_{i}_{name}.png")
        url, err = call(src)
        if not url:
            print(f"[{name}] FAIL {err}")
            continue
        dst = os.path.join(OUT, f"ant_{i}_{name}.png")
        urllib.request.urlretrieve(url, dst)
        print(f"[{name}] ok -> {dst} {os.path.getsize(dst)/1024:.0f}KB")


if __name__ == "__main__":
    main()
