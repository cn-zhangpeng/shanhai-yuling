"""读取 Electron 主窗口矩形，确认桌面窗口尺寸与位置（判断是否被裁）。"""
import ctypes
from ctypes import wintypes

u = ctypes.windll.user32


def enum_windows():
    out = []

    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        n = u.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        if "山海遇灵" in buf.value:
            r = wintypes.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            out.append((buf.value, r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return out


for t, x, y, w, h in enum_windows():
    print(f"{t} | pos=({x},{y}) size={w}x{h}")
