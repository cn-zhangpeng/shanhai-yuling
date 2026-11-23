"""放大最新睁眼帧的脸部，核对眼白是否干净。"""
import os

from PIL import Image
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

SHOT = os.path.join(tempfile.gettempdir(), "aha_bua.png")
OUT = str(_ROOT / "desktop-shell" / "assets" / "_preview")

c = Image.open(SHOT).convert("RGB").crop((380, 450, 520, 580))
c = c.resize((c.width * 4, c.height * 4), Image.LANCZOS)
p = os.path.join(OUT, "眼白_重抠后.png")
c.save(p)
print(p, c.size)
