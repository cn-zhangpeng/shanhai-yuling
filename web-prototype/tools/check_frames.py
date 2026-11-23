"""逐帧检查原型用图的不透明覆盖率，定位"某一帧画出来是空的"问题。"""
import os
from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

D = str(_ROOT / "web-prototype" / "assets")

for f in sorted(os.listdir(D)):
    if not f.endswith("_s.png"):
        continue
    im = Image.open(os.path.join(D, f)).convert("RGBA")
    alpha = im.split()[3]
    hist = alpha.histogram()
    total = im.size[0] * im.size[1]
    opaque = sum(hist[16:]) / total
    mid = sum(hist[1:16]) / total
    bbox = alpha.getbbox()
    print(f"{f:22s} 不透明 {opaque:6.1%}  半透明 {mid:5.1%}  内容框 {bbox}")
