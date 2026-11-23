"""采样「山海遇灵」窗口矩形。只认 Chromium 主窗口类名，避免把系统缩略图一类的同名窗口也算进来。"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

user32 = ctypes.windll.user32

TITLE = "山海遇灵"
CLASSES = {"Chrome_WidgetWin_1"}

samples = int(sys.argv[1]) if len(sys.argv) > 1 else 30
gap = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3


def find():
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if TITLE in buf.value:
                cbuf = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(hwnd, cbuf, 64)
                if cbuf.value in CLASSES:
                    r = wt.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(r))
                    found.append((buf.value, cbuf.value, r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumWindows(cb, 0)
    return found


xs = []
for i in range(samples):
    hits = find()
    if hits:
        t, cls, x, y, w, h = hits[0]
        xs.append(x)
        print(f"{i*gap:4.1f}s  pos=({x},{y}) size={w}x{h}  [{cls}]  match={len(hits)}")
    else:
        print(f"{i*gap:4.1f}s  (没找到窗口)")
    time.sleep(gap)
if xs:
    print("位移区间:", min(xs), "->", max(xs), "delta =", max(xs) - min(xs))
