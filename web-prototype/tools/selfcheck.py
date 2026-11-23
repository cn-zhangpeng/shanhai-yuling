"""静态自检：抽出页面里的脚本做语法检查，并核对引用的素材文件是否都在。"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

ROOT = str(_ROOT / "web-prototype")
HTML = os.path.join(ROOT, "冉冉桌宠原型.html")

src = open(HTML, encoding="utf-8").read()

# 1. 抽出 <script> 段落
blocks = re.findall(r"<script>(.*?)</script>", src, re.S)
if not blocks:
    sys.exit("没找到 script 段")
js_path = os.path.join(ROOT, "tools", "_check_tmp.js")
open(js_path, "w", encoding="utf-8").write(blocks[-1])
r = subprocess.run(["node", "--check", js_path], capture_output=True, text=True)
print("脚本语法:", "OK" if r.returncode == 0 else r.stderr.strip())
os.remove(js_path)

# 2. 核对 assets 引用
refs = re.findall(r'src="assets/([^"]+)"', src)
missing = [f for f in refs if not os.path.exists(os.path.join(ROOT, "assets", f))]
print("素材引用:", len(refs), "个，缺失", len(missing), missing)

# 3. 关键元素 id 是否都在
for i in ["petCanvas", "maskCanvas", "antCanvas", "bubble", "panel", "ctxMenu", "linesList",
          "hudState", "hudFrame", "hudMode", "hudFps", "hudCount", "lineTotal", "lineAvail",
          "btnMode", "btnMask", "btnPanel", "btnHide", "segMode", "swGreet", "swDnd", "swSpeed"]:
    if ("id=\"" + i + "\"") not in src:
        print("缺元素:", i)

# 4. 台词条数与配置一致性
lines = json.load(open(os.path.join(ROOT, r"..\assets\creatures\ranran\lines.json"), encoding="utf-8"))
print("配置台词数:", len(lines["lines"]), "；页面内联数:", src.count("{i:'"))
print("页面大小:", round(os.path.getsize(HTML) / 1024, 1), "KB")
