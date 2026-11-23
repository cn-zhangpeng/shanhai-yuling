"""把 dist/山海遇灵 打成一个带"选择安装位置"页的 Windows 安装包（NSIS）。

和 build_portable.py 的分工：
  build_portable.py → 绿色目录 + zip（解压即用）
  build_installer.py → 安装程序 exe（用户自选目录、写卸载项、建快捷方式）

产物：dist/山海遇灵-安装程序-win-x64.exe

依赖：makensis。脚本会自己去 tools/_build_deps 找；找不到就从 npmmirror 的
electron-builder-binaries 镜像拉一份 nsis-3.0.4.1.7z 解开（不装全局 NSIS，
不污染机器，和 build_portable.py 手工组装运行时的思路一致）。
"""
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

ROOT = str(_ROOT)
TOOLS = os.path.join(ROOT, "tools")
DEPS = os.path.join(TOOLS, "_build_deps")
DIST = os.path.join(ROOT, "dist")
NAME = "山海遇灵"
SRC = os.path.join(DIST, NAME)                       # 绿色版目录（输入）
OUTFILE = os.path.join(DIST, NAME + "-安装程序-win-x64.exe")
ICO = os.path.join(ROOT, "desktop-shell", "assets", "icon", "ranran.ico")
WORK = os.path.join(TOOLS, "_installer")             # .nsi 与使用说明的落地处
NSI = os.path.join(WORK, NAME + ".nsi")
README_SRC = os.path.join(WORK, "使用说明.txt")

NSIS_URL = "https://npmmirror.com/mirrors/electron-builder-binaries/nsis-3.0.4.1/nsis-3.0.4.1.7z"
NSIS_DIR = os.path.join(DEPS, "nsis-3.0.4.1")
MAKENSIS = os.path.join(NSIS_DIR, "makensis.exe")

APP_LABEL = "山海遇灵"          # 应用名。冉冉是当前这只生灵的名字，不进应用名，
                                # 以后加别的桌宠时应用还叫山海遇灵
PET_NAME = "冉冉"
APP_EXE = NAME + ".exe"
APP_VER = "0.1.0"
PUBLISHER = "山海紫穹"


# ---------------------------------------------------------------- NSIS 准备
def ensure_nsis():
    """返回可用的 makensis 路径；没有就下载便携版解开。"""
    if os.path.exists(MAKENSIS):
        return MAKENSIS
    on_path = None
    for p in os.environ.get("PATH", "").split(os.pathsep):
        cand = os.path.join(p, "makensis.exe")
        if os.path.exists(cand):
            on_path = cand
            break
    if on_path:
        return on_path

    sevenz = os.path.join(DEPS, "nsis-3.0.4.1.7z")
    os.makedirs(DEPS, exist_ok=True)
    if not os.path.exists(sevenz):
        print("下载 NSIS：", NSIS_URL)
        with urllib.request.urlopen(NSIS_URL, timeout=180) as resp, open(sevenz, "wb") as fh:
            fh.write(resp.read())
    # Windows 自带 bsdtar 能直接解 7z，不用另装 7-Zip
    os.makedirs(NSIS_DIR, exist_ok=True)
    subprocess.run([r"C:\Windows\System32\tar.exe", "-xf", sevenz, "-C", NSIS_DIR], check=True)
    if not os.path.exists(MAKENSIS):
        raise SystemExit("NSIS 解压后没找到 makensis.exe：" + MAKENSIS)
    return MAKENSIS


# ---------------------------------------------------------------- 源目录
def ensure_portable():
    """安装包的输入是绿色版目录；没有就现打一份，别让用户先手动跑另一个脚本。"""
    exe = os.path.join(SRC, APP_EXE)
    app = os.path.join(SRC, "resources", "app", "main.js")
    if os.path.exists(exe) and os.path.exists(app):
        return
    print("没有现成的绿色版目录，先跑 build_portable.py")
    subprocess.run([sys.executable, os.path.join(TOOLS, "build_portable.py")], check=True)


# ---------------------------------------------------------------- 使用说明（安装版）
def write_readme():
    txt = f"""{APP_LABEL}（Windows 安装版）

现在这一只是「{PET_NAME}」，以后还会加别的桌面生灵，应用名一直就叫{APP_LABEL}。

怎么用
  1. 桌面上的「{APP_LABEL}」，双击打开，她（和地上的小珊瑚粉蚂蚁）会出现在屏幕右下角，默认就"钉"在那儿。
  2. 右键她：让她走两步 / 跳个绳 / 躲角落玩手机 / 陪小蚂蚁玩 / 设置 / 让她待着 / 回到右下角。
  3. 托盘图标（任务栏右下角）里是同一套菜单。
  4. 左键按住可以拖动她；单击她会说话。
  5. 快捷键：Ctrl+Alt+1 走两步、2 跳绳、3 玩手机、4 陪蚂蚁、5 锁定开关。

设置（右键她本人 或 托盘图标 → 设置）
  · 开机自启：勾上就随 Windows 登录自动出现，取消勾选就不再自启。自启项指向的是"当前正在跑的那个 exe"：换目录重装、或用另一个副本启动，只要新那份开着自启跑过一次，注册表项就会自动对齐过去，不用手动重勾。
  · 大小：50% / 80% / 100% / 120% / 140%，默认 80%。
  · 钉在这个位置：默认开启，只钉在右下角；取消后她会满桌面走动。
  · 锁定：鼠标完全点不到她，点击穿到底下的窗口（同 QQ 音乐桌面歌词锁），解锁用托盘菜单或 Ctrl+Alt+5。

注意
  · 她是透明置顶的，空白处点鼠标会直接落到你下面的窗口，不会挡操作。
  · 首次启动 Windows 可能提示"未知开发者"，选"更多信息 → 仍要运行"即可。

卸载
  开始菜单 → {APP_LABEL} → 卸载 {APP_LABEL}
  或 设置 → 应用 → 已安装的应用 → {APP_LABEL} → 卸载
  卸载会删除安装目录、桌面快捷方式、开始菜单项和注册表里的卸载项，不动你的个人文件。
"""
    os.makedirs(WORK, exist_ok=True)
    with open(README_SRC, "w", encoding="utf-8") as fh:
        fh.write(txt)


# ---------------------------------------------------------------- .nsi 模板
NSI_TEMPLATE = r"""Unicode true
SetCompressor /SOLID lzma
SetCompressorDictSize 64

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

!define APP_NAME "__NAME__"
!define APP_LABEL "__LABEL__"
!define APP_EXE "__EXE__"
!define APP_VER "__VER__"
!define PUBLISHER "__PUBLISHER__"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\__NAME__"

Name "${APP_LABEL}"
OutFile "__OUTFILE__"
; 默认装到当前用户目录：不需要管理员权限，也不弹 UAC。
; 想装到 D:\ 之类的位置，在这一页直接改就行。
InstallDir "$LOCALAPPDATA\Programs\__NAME__"
InstallDirRegKey HKCU "Software\__NAME__" "InstallLocation"
RequestExecutionLevel user
ShowInstDetails show
ShowUninstDetails show
BrandingText "${APP_LABEL} v${APP_VER}"

VIProductVersion "__VI4__"
VIAddVersionKey /LANG=2052 "ProductName" "${APP_LABEL}"
VIAddVersionKey /LANG=2052 "CompanyName" "${PUBLISHER}"
VIAddVersionKey /LANG=2052 "FileDescription" "${APP_LABEL} 安装程序"
VIAddVersionKey /LANG=2052 "FileVersion" "${APP_VER}"
VIAddVersionKey /LANG=2052 "LegalCopyright" "MIT License"

!define MUI_ICON "__ICO__"
!define MUI_UNICON "__ICO__"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "欢迎安装 ${APP_LABEL}"
!define MUI_WELCOMEPAGE_TEXT "她会成为桌面上的一只小生灵：坐在右下角眨眼、挥手、偶尔站起来陪地上的小蚂蚁玩。$\r$\n$\r$\n现在这一只是「__PET__」，以后还会有别的。$\r$\n$\r$\n下一步可以选择把她装在哪里。"

!define MUI_DIRECTORYPAGE_TEXT_TOP "选择 ${APP_LABEL} 的安装位置。$\r$\n默认装到当前用户目录，不需要管理员权限；也可以改到 D:\ 等任意可写目录（不建议直接选盘符根目录，卸载会清空整个安装目录，请挑一个专门的文件夹）。"
!define MUI_DIRECTORYPAGE_TEXT_DESTINATION "安装到"

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "现在就让她出来"
!define MUI_FINISHPAGE_TEXT "安装完成。$\r$\n$\r$\n右键她本人或托盘图标 → 设置，可以把「开机自启」勾上，下次登录 Windows 她就自己出现。"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

; 装到盘符根目录会害死卸载（RMDir /r 会把整盘清掉），这一页直接拦下来
Function .onVerifyInstDir
  StrLen $0 "$INSTDIR"
  ${If} $0 <= 3
    StrCpy $1 "$INSTDIR" 1 1
    ${If} $1 == ":"
      MessageBox MB_OK|MB_ICONSTOP "不能直接装到盘符根目录（如 D:\），请选一个专门的文件夹。"
      Abort
    ${EndIf}
  ${EndIf}
FunctionEnd

Function .onInit
  ; 目标目录里已经有她、而且 exe 被占用（正在跑），先问一句。
  ; 用"能不能以追加方式打开 exe"判断是否被占用，比抓 tasklist 的输出稳：中文进程名的编码在
  ; 不同代码页下会变，文件共享锁不会。
  ${If} ${FileExists} "$INSTDIR\${APP_EXE}"
    ClearErrors
    FileOpen $0 "$INSTDIR\${APP_EXE}" a
    ${If} ${Errors}
      MessageBox MB_YESNO|MB_ICONQUESTION "检测到 ${APP_LABEL} 正在运行。$\r$\n继续安装会先把她关掉（装完可以立刻重新打开），是否继续？" IDYES kill IDNO abort
      abort:
        Abort
      kill:
        nsExec::ExecToLog 'taskkill /F /T /IM ${APP_EXE}'
    ${Else}
      FileClose $0
    ${EndIf}
  ${EndIf}
FunctionEnd

Section "安装" SecMain
  SectionIn RO
  ; 兜底再杀一次：GUI 里点了"否"不会走到这里，但静默安装没有对话框
  nsExec::ExecToLog 'taskkill /F /T /IM ${APP_EXE}'

  SetOutPath "$INSTDIR"
  SetOverwrite on
  ; 绿色版自带的"使用说明.txt"是讲免安装的，换成安装版那份
  File /r /x "使用说明.txt" "__SRCDIR__\*.*"
  SetOutPath "$INSTDIR"
  File /oname=使用说明.txt "__README__"

  CreateDirectory "$SMPROGRAMS\${APP_LABEL}"
  CreateShortcut "$SMPROGRAMS\${APP_LABEL}\${APP_LABEL}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP_LABEL}\卸载 ${APP_LABEL}.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\${APP_LABEL}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; 记住这次选的目录：下次安装默认还是这里，卸载也从这里读
  WriteRegStr HKCU "Software\${APP_NAME}" "InstallLocation" "$INSTDIR"

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP_LABEL}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${APP_VER}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" "$0"
SectionEnd

Section "Uninstall"
  nsExec::ExecToLog 'taskkill /F /T /IM ${APP_EXE}'

  Delete "$DESKTOP\${APP_LABEL}.lnk"
  Delete "$SMPROGRAMS\${APP_LABEL}\${APP_LABEL}.lnk"
  Delete "$SMPROGRAMS\${APP_LABEL}\卸载 ${APP_LABEL}.lnk"
  RMDir "$SMPROGRAMS\${APP_LABEL}"

  ; 只在"这就是我们的安装目录"时才整目录删；否则只删空目录，免得误伤用户自己放进去的东西
  ${If} ${FileExists} "$INSTDIR\${APP_EXE}"
    StrLen $0 "$INSTDIR"
    ${If} $0 > 3
      RMDir /r "$INSTDIR"
    ${Else}
      Delete "$INSTDIR\${APP_EXE}"
    ${EndIf}
  ${Else}
    RMDir "$INSTDIR"
  ${EndIf}

  DeleteRegKey HKCU "${UNINST_KEY}"
  DeleteRegKey HKCU "Software\${APP_NAME}"
SectionEnd
"""


def write_nsi():
    txt = NSI_TEMPLATE
    for k, v in {
        "__NAME__": NAME,
        "__LABEL__": APP_LABEL,
        "__PET__": PET_NAME,
        "__EXE__": APP_EXE,
        "__VER__": APP_VER,
        "__PUBLISHER__": PUBLISHER,
        "__VI4__": "0.1.0.0",
        "__OUTFILE__": OUTFILE,   # NSIS 字符串里的反斜杠是普通字符，原样放进去即可
        "__SRCDIR__": SRC,
        "__README__": README_SRC,
        "__ICO__": ICO,
    }.items():
        txt = txt.replace(k, v)
    return txt


def main():
    os.makedirs(DIST, exist_ok=True)
    ensure_portable()
    makensis = ensure_nsis()
    write_readme()
    os.makedirs(WORK, exist_ok=True)
    # NSIS 3 通过 UTF-8 BOM 判定脚本是 Unicode，中文界面/中文路径都靠它
    with open(NSI, "w", encoding="utf-8-sig") as fh:
        fh.write(write_nsi())

    if os.path.exists(OUTFILE):
        os.remove(OUTFILE)
    r = subprocess.run([makensis, "/V2", "/WX", NSI], cwd=ROOT, capture_output=True, text=True,
                       encoding="mbcs", errors="replace")
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit("makensis 失败，退出码 %d" % r.returncode)
    if not os.path.exists(OUTFILE):
        raise SystemExit("没生成安装包：" + OUTFILE)
    print("安装包:", OUTFILE, "%.1f MB" % (os.path.getsize(OUTFILE) / 1024 / 1024))
    print("脚本  :", NSI)


if __name__ == "__main__":
    main()
