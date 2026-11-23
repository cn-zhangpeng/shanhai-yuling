"""把桌面壳打成可分发目录 + zip：Electron 运行时 + 我们的 app 资源，不改一行业务代码。

产物：dist/山海遇灵/山海遇灵.exe（可直接双击，绿色免安装）
      dist/山海遇灵-win-x64.zip
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ROOT = str(_ROOT)
APP = os.path.join(ROOT, "desktop-shell")
DIST = os.path.join(ROOT, "dist")
NAME = "山海遇灵"
OUT = os.path.join(DIST, NAME)
ZIP = os.path.join(DIST, NAME + "-win-x64.zip")
RCEDIT = os.path.join(ROOT, "tools", "_build_deps", "node_modules", "rcedit", "bin", "rcedit-x64.exe")

KEEP_LOCALES = {"zh-CN.pak", "en-US.pak"}


def fresh(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def copy_runtime():
    src = os.path.join(APP, "node_modules", "electron", "dist")
    dst = OUT
    fresh(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            if item == "locales":
                os.makedirs(d, exist_ok=True)
                for f in os.listdir(s):
                    if f in KEEP_LOCALES:
                        shutil.copy2(os.path.join(s, f), os.path.join(d, f))
            else:
                shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    # 默认 app 必须删掉，否则 Electron 会去跑它自带的 default_app
    da = os.path.join(dst, "resources", "default_app.asar")
    if os.path.exists(da):
        os.remove(da)


def build_app():
    resources = os.path.join(OUT, "resources")
    appdir = os.path.join(resources, "app")
    os.makedirs(appdir, exist_ok=True)
    # 运行时代码：桌宠本体 + 生灵包注册表 + 设置页
    for f in ("main.js", "preload.js", "desk-pet.html",
              "creature-pack.js", "settings-store.js",
              "settings.html", "settings-preload.js"):
        shutil.copy2(os.path.join(APP, f), os.path.join(appdir, f))

    # 只带运行时要用的素材：25 张人物帧 + 蚂蚁雪碧图 + 图标 + 生灵清单/台词
    assets = os.path.join(appdir, "assets")
    os.makedirs(assets, exist_ok=True)
    for f in os.listdir(os.path.join(APP, "assets")):
        if f.endswith("_2x.png") or f in ("ant_walk.png", "ant_walk.json", "creature.json", "lines.json"):
            shutil.copy2(os.path.join(APP, "assets", f), os.path.join(assets, f))
    shutil.copytree(os.path.join(APP, "assets", "icon"), os.path.join(assets, "icon"))

    pkg = {
        "name": "shanhai-yuling",
        "productName": NAME,
        "version": "0.1.0",
        "description": "山海遇灵 · 桌面生灵（当前：冉冉）",
        "main": "main.js",
        "author": "山海紫穹",
    }
    with open(os.path.join(appdir, "package.json"), "w", encoding="utf-8") as fh:
        json.dump(pkg, fh, ensure_ascii=False, indent=2)

    return appdir


def rename_and_brand():
    old = os.path.join(OUT, "electron.exe")
    new = os.path.join(OUT, NAME + ".exe")
    if os.path.exists(new):
        os.remove(new)
    os.rename(old, new)
    if os.path.exists(RCEDIT):
        subprocess.run([
            RCEDIT, new,
            "--set-icon", os.path.join(OUT, "resources", "app", "assets", "icon", "ranran.ico"),
            "--set-file-version", "0.1.0.0",
            "--set-product-version", "0.1.0.0",
            "--set-version-string", "ProductName", NAME,
            "--set-version-string", "FileDescription", NAME + " · 桌面生灵",
            "--set-version-string", "CompanyName", "山海紫穹",
            "--set-version-string", "LegalCopyright", "MIT License",
        ], check=True, capture_output=True)
        print("已写入图标与版本信息")
    else:
        print("警告：没有 rcedit，exe 图标仍是 Electron 默认", file=sys.stderr)
    return new


def make_readme():
    txt = f"""山海遇灵（Windows 绿色版）

现在这一只是「冉冉」，以后还会加别的桌面生灵，应用名一直叫山海遇灵。

怎么用
  1. 双击 {NAME}.exe，她（和地上的小珊瑚粉蚂蚁）会出现在屏幕右下角，默认就"钉"在那儿。
  2. 右键她：让她走两步 / 跳个绳 / 躲角落玩手机 / 陪小蚂蚁玩 / 大小 / 钉在这个位置 / 锁定。
  3. 右键 →「设置…」：换形象（选生灵）、改常用语，保存即生效，不用重启。
     加生灵：打开 %APPDATA%\\山海遇灵\\creatures（那里的 说明.txt 写了尺寸和透明底要求），
     新建一个文件夹、把图按帧名丢进 frames\\，回设置页点「重新扫描」就多一项。
  4. 托盘图标（任务栏右下角）里是同一套菜单。
  5. 左键按住可以拖动她；单击她会说话。
  6. 快捷键：Ctrl+Alt+1 走两步、2 跳绳、3 玩手机、4 陪蚂蚁、5 锁定开关。

注意
  · 她是透明置顶的，空白处点鼠标会直接落到你下面的窗口，不会挡操作。
  · 尺寸默认 80%，觉得小了/大了就右键改（50% / 80% / 100% / 120% / 140%）。
  · 默认是"钉在右下角"状态：只在这个地方活动，不会走开。想让她满桌面走动，右键把"钉在这个位置"取消勾选。
  · 勾上"锁定"后鼠标完全点不到她，点击会穿到底下的窗口（和 QQ 音乐桌面歌词锁一样）；解锁用托盘菜单或 Ctrl+Alt+5。
  · 这是过渡预览壳（Electron）。首次启动 Windows 可能提示"未知开发者"，选"更多信息 → 仍要运行"即可。
  · 这是过渡预览壳（Electron）。首次启动 Windows 可能提示"未知开发者"，选"更多信息 → 仍要运行"即可。

卸载
  直接删掉整个文件夹即可，不写注册表、不装服务。
"""
    with open(os.path.join(OUT, "使用说明.txt"), "w", encoding="utf-8") as fh:
        fh.write(txt)


def main():
    os.makedirs(DIST, exist_ok=True)
    copy_runtime()
    build_app()
    exe = rename_and_brand()
    make_readme()
    if os.path.exists(ZIP):
        os.remove(ZIP)
    shutil.make_archive(ZIP[:-4], "zip", DIST, NAME)
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    print("目录:", OUT, f"{total / 1024 / 1024:.1f} MB")
    print("exe :", exe)
    print("zip :", ZIP, f"{os.path.getsize(ZIP) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
