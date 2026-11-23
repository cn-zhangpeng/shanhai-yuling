"""给所有 ranran_*.png 的 img src 加版本号，绕开同名文件的磁盘缓存。"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

P = str(_ROOT / "desktop-shell" / "desk-pet.html")
VER = "?v=3"

with open(P, "r", encoding="utf-8") as f:
    t = f.read()

def add_ver(m):
    name = m.group(1)
    return f'src="assets/{name}{VER}"'

t2 = re.sub(r'src="assets/(ranran_[^"?]+\.png)"', add_ver, t)
n = len(re.findall(r'src="assets/ranran_[^"?]+\.png\?v=3"', t2))
with open(P, "w", encoding="utf-8") as f:
    f.write(t2)
print("带版本号的帧:", n)
