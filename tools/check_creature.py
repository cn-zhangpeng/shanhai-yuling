"""生灵包自检：别人交一套图之前先跑这个，跑不过就别丢进目录。

它检查的是"程序能不能用这套图"，不是"画得好不好看"：
  · 有没有 base（没有 base 等于没法显示）
  · 文件名能不能被认领成 25 个规范帧名里的某几个（认领规则跟 creature-pack.js 一致）
  · 是不是透明底 PNG（四角 alpha=0）
  · 同一套图宽高是不是一致
  · 脚底基线偏差（站/走帧脚底不齐，切帧时人会上下跳）
  · 每帧内容顶边（气泡锚点），可 --write-anchor 直接写回 creature.json

用法：
  python tools/check_creature.py "C:\\Users\\me\\AppData\\Roaming\\山海遇灵\\creatures\\小兔"
  python tools/check_creature.py --scan                     # 扫内置 + 我的生灵，逐个体检
  python tools/check_creature.py --init "...\\creatures\\小兔"  # 生成一套骨架
  python tools/check_creature.py <dir> --write-anchor      # 把量出来的 headTop 写进 creature.json
  python tools/check_creature.py <dir> --json               # 机器可读
退出码：0 可用（可能有警告）；1 有错误；2 参数/环境问题。
"""
import argparse
import json
import os
import re
import sys

try:
    from PIL import Image
except ImportError:
    print("需要 Pillow：pip install pillow", file=sys.stderr)
    sys.exit(2)

CANONICAL = [
    "base", "blink", "talk", "smile", "turn", "turnL", "wave", "noant",
    "stand", "walkA", "walkB", "walkP1", "walkP2",
    "phone", "ropeAir", "ropeLand",
    "ntTurn", "ntTurnL", "ntSmile", "ntWave", "ntBlink",
    "footSwing", "handEar", "ntFootSwing", "ntHandEar",
]
STANDING = {"stand", "walkA", "walkB", "walkP1", "walkP2", "phone", "ropeAir", "ropeLand"}
IMG_EXT = {".png", ".webp", ".jpg", ".jpeg"}

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTIN_ROOT = os.path.join(APP_ROOT, "desktop-shell", "assets")
USER_ROOT = os.path.join(os.environ.get("APPDATA", ""), "山海遇灵", "creatures")

RED, YEL, GRN, DIM, END = "\033[31m", "\033[33m", "\033[32m", "\033[2m", "\033[0m"
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    RED = YEL = GRN = DIM = END = ""


def tokens(stem):
    return [t for t in re.split(r"[^A-Za-z0-9]+", stem.lower()) if t]


def collect_images(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        depth = os.path.relpath(dirpath, root).count(os.sep) if dirpath != root else 0
        if depth > 1:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith("_") and not d.startswith(".")]
        for f in filenames:
            if f.startswith("_") or f.startswith("."):
                continue
            if os.path.splitext(f)[1].lower() in IMG_EXT:
                out.append(os.path.join(dirpath, f))
    return out


def score_of(root, path):
    rel = os.path.relpath(path, root).split(os.sep)
    s = 0
    if len(rel) > 1 and rel[0].lower() == "frames":
        s += 10
    if "2x" in tokens(os.path.splitext(os.path.basename(path))[0]):
        s += 5
    return s


def resolve_frames(root, manifest, images):
    index = {}
    for p in images:
        for t in tokens(os.path.splitext(os.path.basename(p))[0]):
            index.setdefault(t, []).append(p)
    frames = {}
    for name in CANONICAL:
        explicit = None
        spec = (manifest.get("frames") or {}).get(name)
        if isinstance(spec, str):
            explicit = spec
        elif isinstance(spec, dict):
            explicit = spec.get("file")
        if explicit:
            p = os.path.abspath(os.path.join(root, explicit))
            if os.path.exists(p):
                frames[name] = p
                continue
        cands = index.get(name.lower(), [])
        if cands:
            cands = sorted(cands, key=lambda p: -score_of(root, p))
            frames[name] = cands[0]
    return frames


def measure(path):
    """返回 (w, h, 顶边像素, 底边像素, 模式, 四角是否透明)"""
    with Image.open(path) as im:
        im.load()
        w, h = im.size
        mode = im.mode
        has_alpha = "A" in im.getbands()
        if not has_alpha:
            return w, h, None, None, mode, False
        a = im.getchannel("A")
        bbox = a.getbbox()          # 非零像素的外接框
        corners = [a.getpixel((0, 0)), a.getpixel((w - 1, 0)),
                   a.getpixel((0, h - 1)), a.getpixel((w - 1, h - 1))]
        return w, h, (bbox[1] if bbox else None), (bbox[3] - 1 if bbox else None), mode, all(c == 0 for c in corners)


def check(root, write_anchor=False, as_json=False):
    problems, warns, notes = [], [], []
    rows = []
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return {"ok": False, "error": "不是目录: " + root}

    manifest_path = os.path.join(root, "creature.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        except Exception as e:
            problems.append("creature.json 解析失败：%s" % e)
    else:
        notes.append("没有 creature.json：按目录名当 ID，靠文件名认帧（也能用）")

    images = collect_images(root)
    if not images:
        return {"ok": False, "error": "目录里一张图都没有（要看 frames/ 或本层）"}

    frames = resolve_frames(root, manifest, images)
    missing = [n for n in CANONICAL if n not in frames]

    if "base" not in frames:
        problems.append("没有 base 帧：程序没法显示这个生灵")
    else:
        ref_w, ref_h, ref_top, ref_bottom, ref_mode, ref_clear = measure(frames["base"])
        if not ref_clear:
            problems.append("base 不是透明底（四角 alpha 不为 0）或没有 alpha 通道（当前 %s）" % ref_mode)

        rows = []
        for name in CANONICAL:
            p = frames.get(name)
            if not p:
                continue
            w, h, top, bottom, mode, clear = measure(p)
            anchor = None
            if top is not None and h:
                anchor_px = top
                anchor = {"headTop": anchor_px}
            delta_base = (bottom - ref_bottom) if (bottom is not None and ref_bottom is not None) else None
            rows.append({
                "frame": name, "file": os.path.relpath(p, root).replace("\\", "/"),
                "size": "%dx%d" % (w, h), "mode": mode, "clear": clear,
                "top": top, "bottom": bottom, "foot_delta": delta_base,
                "anchor": anchor,
            })
            if (w, h) != (ref_w, ref_h):
                warns.append("%s 尺寸 %dx%d 与 base 的 %dx%d 不一致（换帧会跳尺寸）" % (name, w, h, ref_w, ref_h))
            if not clear:
                warns.append("%s 不是透明底（四角有像素），贴到桌面上会带一块底" % name)
            if delta_base is not None and abs(delta_base) > max(6, ref_h * 0.02):
                warns.append("%s 脚底比 base 高/低 %d px（站姿/走姿会看着悬空或陷进去）" % (name, delta_base))

        if write_anchor:
            fm = manifest.setdefault("frames", {})
            for r in rows:
                if r["anchor"] is None:
                    continue
                spec = fm.get(r["frame"])
                if isinstance(spec, str):
                    spec = {"file": spec}
                spec = dict(spec or {})
                spec["headTop"] = r["anchor"]["headTop"]
                fm[r["frame"]] = spec
            try:
                with open(manifest_path, "w", encoding="utf-8") as fh:
                    json.dump(manifest, fh, ensure_ascii=False, indent=2)
                notes.append("已把 headTop 写进 creature.json")
            except Exception as e:
                problems.append("写 creature.json 失败：%s" % e)

    status = "broken" if "base" not in frames else (
        "full" if all(n in frames for n in ("stand", "walkA", "walkB", "walkP1", "walkP2")) else "static")

    companion = None
    spec = (manifest.get("companion") or {}).get("file")
    cand = os.path.join(root, spec) if spec else None
    if not (cand and os.path.exists(cand)):
        hits = [p for p in images if set(tokens(os.path.splitext(os.path.basename(p))[0])) & {"ant", "companion", "pet"}]
        cand = hits[0] if hits else None
    if cand:
        with Image.open(cand) as im:
            cw, ch = im.size
        n = int((manifest.get("companion") or {}).get("frames") or (9 if cw % 9 == 0 else 1))
        if n and cw % n:
            warns.append("伴生灵宽度 %d 不能被帧数 %d 整除，切帧会错位" % (cw, n))
        companion = {"file": os.path.relpath(cand, root).replace("\\", "/"), "size": "%dx%d" % (cw, ch),
                     "frames": n, "cellW": cw // n if n else cw, "cellH": ch}

    result = {
        "ok": not problems,
        "dir": root,
        "id": manifest.get("id") or os.path.basename(root),
        "status": status,
        "frames_found": len(frames),
        "missing": missing,
        "rows": rows,
        "companion": companion,
        "problems": problems,
        "warnings": warns,
        "notes": notes,
    }
    return result


def print_report(r, as_json=False):
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    if r.get("error"):
        print(RED + "✗ " + r["error"] + END)
        return
    head = "%s  %s  [%s]  %d/%d 帧" % (r["id"], r["dir"], r["status"], r["frames_found"], len(CANONICAL))
    print(("✓ " if r["ok"] and not r["warnings"] else ("! " if r["ok"] else "✗ ")) + head)
    if r["rows"]:
        print(DIM + "  %-11s %-30s %-10s %-6s %s" % ("帧名", "文件", "尺寸", "顶边", "脚底偏差") + END)
        for row in r["rows"]:
            print("  %-11s %-30s %-10s %-6s %s" % (
                row["frame"], row["file"], row["size"],
                row["top"] if row["top"] is not None else "-",
                ("%+d" % row["foot_delta"]) if row["foot_delta"] is not None else "-"))
    if r["companion"]:
        c = r["companion"]
        print("  伴生灵: %s  %s  %d 帧  单格 %dx%d" % (c["file"], c["size"], c["frames"], c["cellW"], c["cellH"]))
    if r["missing"]:
        print(YEL + "  缺帧: " + "、".join(r["missing"]) + END)
        if r["status"] == "static":
            print(YEL + "  → 这套图只能当静态形象：走动/跳绳/看手机会在菜单里禁用（不是 bug，是降级）" + END)
    for m in r["problems"]:
        print(RED + "  ✗ " + m + END)
    for w in r["warnings"]:
        print(YEL + "  ! " + w + END)
    for n in r["notes"]:
        print(DIM + "  · " + n + END)


def scan_all():
    targets = []
    if os.path.isdir(BUILTIN_ROOT):
        targets.append(BUILTIN_ROOT)
    if os.path.isdir(USER_ROOT):
        for name in sorted(os.listdir(USER_ROOT)):
            p = os.path.join(USER_ROOT, name)
            if os.path.isdir(p) and not name.startswith("_"):
                targets.append(p)
    return targets


def init_skeleton(path):
    path = os.path.abspath(path)
    os.makedirs(os.path.join(path, "frames"), exist_ok=True)
    cfg = {
        "schemaVersion": 1,
        "id": os.path.basename(path),
        "displayName": os.path.basename(path),
        "window": {"petHeight": 600},
        "_说明": "把透明底 PNG 放进 frames/，文件名用规范帧名（base.png / blink.png / walkA.png …）。"
                 "运行 python tools/check_creature.py \"这个目录\" --write-anchor 会自动把气泡锚点写进来。"
    }
    cp = os.path.join(path, "creature.json")
    if not os.path.exists(cp):
        with open(cp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    guide = os.path.join(path, "放图说明.txt")
    with open(guide, "w", encoding="utf-8") as fh:
        fh.write(
            "把图放进 frames/，文件名就是帧名：\n" + "、".join(CANONICAL) + "\n\n"
            "最少一张 base.png 就能显示（动作会自动降级）。\n"
            "要能走动，至少补 stand.png + walkA/B/P1/P2.png。\n"
            "透明底、同一套图宽高一致、脚底对齐。\n"
            "放完运行：python tools/check_creature.py \"" + path + "\"\n"
        )
    print("已生成骨架：", path)
    print("  frames/  creature.json  放图说明.txt")


def main():
    ap = argparse.ArgumentParser(description="生灵包自检 / 生成骨架")
    ap.add_argument("dir", nargs="?", help="生灵目录（不填配合 --scan）")
    ap.add_argument("--scan", action="store_true", help="扫内置与「我的生灵」目录，逐个体检")
    ap.add_argument("--init", metavar="DIR", help="生成一套空骨架")
    ap.add_argument("--write-anchor", action="store_true", help="把量出来的 headTop 写回 creature.json")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.init:
        init_skeleton(args.init)
        return 0

    if args.scan:
        targets = scan_all()
        if not targets:
            print("没找到任何生灵目录")
            return 2
        worst = 0
        for t in targets:
            r = check(t, args.write_anchor)
            print_report(r, args.json)
            print()
            if not r.get("ok", False):
                worst = 1
        return worst

    if not args.dir:
        ap.print_help()
        return 2
    r = check(args.dir, args.write_anchor)
    print_report(r, args.json)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
