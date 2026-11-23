"""按窗口标题用 PrintWindow(PW_RENDERFULLCONTENT) 截图，能抓到透明分层窗口的内容。

用途：cu 桌面通道在本会话不可用，核验桌宠真实渲染只能走这条。
"""
import ctypes
import sys
from ctypes import wintypes

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

TITLE = "山海遇灵"


def find_window(title):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _l):
        t = ctypes.create_unicode_buffer(300)
        user32.GetWindowTextW(h, t, 300)
        c = ctypes.create_unicode_buffer(200)
        user32.GetClassNameW(h, c, 200)
        if t.value == title and c.value == "Chrome_WidgetWin_1":
            found.append(h)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def grab(hwnd, out):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    # 进程是 DPI 不感知的：窗口矩形是虚拟坐标，实际渲染按 1.5 倍像素，抓图要放大才不会只拿到左上角
    try:
        k = user32.GetDpiForWindow(hwnd) / 96.0
    except Exception:
        k = 1.0
    w, h = int((r.right - r.left) * k), int((r.bottom - r.top) * k)
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hwnd, mem, 2)
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)

    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
    bg = Image.new("RGB", img.size, (40, 40, 40))
    bg.paste(img, (0, 0), img.split()[3])
    bg.save(out)
    print("PrintWindow", ok, "rect", r.left, r.top, w, h, "->", out)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)


if __name__ == "__main__":
    title = sys.argv[2] if len(sys.argv) > 2 else TITLE
    h = find_window(title)
    if not h:
        raise SystemExit("没找到窗口: " + title)
    grab(h, sys.argv[1])
