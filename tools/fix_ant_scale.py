"""蚂蚁第 9 格（四脚朝天）看着变小：它按"宽度上限"缩放，横躺只剩 138px 高，
而立着的画面是 298px 高 —— 视觉上就缩了一半。

改法：
1. 格宽 265 → 340，给横躺帧留出横向空间；
2. 横躺帧改按"高度 178px"缩放（≈ 站立帧头径 175），不再按宽度卡；
3. 九格统一水平居中、底边落在基线 315，保证换帧时脚不飘。
"""
import json
import os

from PIL import Image
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ASSETS = str(_ROOT / "desktop-shell" / "assets")
SHEET = os.path.join(ASSETS, "ant_walk.png")
CW_OLD, CW_NEW, CH = 265, 340, 332
BASELINE = 315
FLOP_H = 178


def main():
    sheet = Image.open(SHEET).convert("RGBA")
    cells = [sheet.crop((i * CW_OLD, 0, (i + 1) * CW_OLD, CH)) for i in range(sheet.size[0] // CW_OLD)]
    out_cells = []
    for i, c in enumerate(cells):
        b = c.split()[3].getbbox()
        content = c.crop(b)
        if i == 8:                                  # flop
            k = FLOP_H / content.size[1]
            content = content.resize((max(1, round(content.size[0] * k)), FLOP_H), Image.LANCZOS)
        if content.size[0] > CW_NEW - 4:
            content = content.resize((CW_NEW - 4, round(content.size[1] * (CW_NEW - 4) / content.size[0])), Image.LANCZOS)
        cell = Image.new("RGBA", (CW_NEW, CH), (0, 0, 0, 0))
        cell.paste(content, ((CW_NEW - content.size[0]) // 2, BASELINE - content.size[1]), content)
        out_cells.append(cell)
        nb = cell.split()[3].getbbox()
        print(f"格{i}: {content.size[0]}×{content.size[1]} 顶边{nb[1]} 底边{nb[3]}")

    out = Image.new("RGBA", (CW_NEW * len(out_cells), CH), (0, 0, 0, 0))
    for i, c in enumerate(out_cells):
        out.paste(c, (i * CW_NEW, 0), c)
    out.save(SHEET, "PNG", optimize=True)

    with open(os.path.join(ASSETS, "ant_walk.json"), "r", encoding="utf-8") as f:
        j = json.load(f)
    j["cellW"], j["cellH"] = CW_NEW, CH
    with open(os.path.join(ASSETS, "ant_walk.json"), "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, indent=2)

    preview = Image.new("RGBA", (CW_NEW * len(out_cells), CH), (246, 246, 248, 255))
    for i, c in enumerate(out_cells):
        preview.paste(c, (i * CW_NEW, 0), c)
    preview.save(os.path.join(ASSETS, "_preview", "蚂蚁九格_加宽.png"))
    print("新雪碧图", out.size, "cellW", CW_NEW)


if __name__ == "__main__":
    main()
