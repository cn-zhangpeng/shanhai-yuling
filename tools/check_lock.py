"""验证"锁定"是否真的让鼠标穿过去。

做法：把光标移到她身上，等主进程轮询翻转完，读窗口扩展样式里的
WS_EX_TRANSPARENT(0x20) 与 WS_EX_LAYERED(0x80000) —— 透传态必须有这两位。
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
TITLE = "山海遇灵"
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000


def hwnd():
    h = user32.FindWindowW(None, TITLE)
    return h or 0


def rect(h):
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def style(h):
    v = user32.GetWindowLongW(h, GWL_EXSTYLE)
    return {
        "transparent": bool(v & WS_EX_TRANSPARENT),
        "layered": bool(v & WS_EX_LAYERED),
        "raw": hex(v & 0xFFFFFFFF),
    }


def main():
    h = hwnd()
    if not h:
        print("没找到窗口")
        return 1
    l, t, r, b = rect(h)
    # 精灵本体大概在窗口中间偏下，取窗口水平中线、竖直 60% 处
    cx = (l + r) // 2
    cy = int(t + (b - t) * 0.6)
    user32.SetCursorPos(cx, cy)
    time.sleep(0.6)
    s = style(h)
    print(f"光标压在 ({cx},{cy}) 上 → exstyle {s}")
    print("穿透=" + ("是" if s["transparent"] else "否"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
