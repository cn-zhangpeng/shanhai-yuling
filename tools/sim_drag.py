"""模拟一次拖拽：按住她的头部、慢慢移动、中途停住，检查窗口是否跟着光标走且不漂。

用 SendInput 发真实鼠标事件，走的是和用户一样的 OS 路径。
"""
import ctypes
import time
from ctypes import wintypes

from PIL import ImageGrab  # noqa: F401  (仅保证 Pillow 可用)

user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("i",)
    _fields_ = [("type", wintypes.DWORD), ("i", _I)]


def send(flags, x=None, y=None):
    inp = INPUT()
    inp.type = 0
    inp.mi.dwFlags = flags
    if x is not None:
        inp.mi.dx = x
        inp.mi.dy = y
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def move_to(x, y):
    user32.SetCursorPos(int(x), int(y))


def window_rect(title="山海遇灵"):
    r = wintypes.RECT()
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        return r.left, r.top, r.right - r.left, r.bottom - r.top
    return None


def main():
    x, y, w, h = window_rect()
    print("起点窗口:", x, y, w, h)
    # 她头部大致位置：窗口右侧偏中，靠下 40% 处
    px, py = (x + w * 0.62, y + h * 0.42)
    move_to(px, py)
    time.sleep(0.35)
    send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.3)
    print("按下后:", window_rect())
    for i in range(1, 9):
        move_to(px + i * 6, py + i * 4)
        time.sleep(0.09)
    print("拖动后:", window_rect())
    # 停住不动 1.5 秒，看会不会自己继续漂
    time.sleep(1.5)
    print("停手 1.5s:", window_rect())
    time.sleep(1.5)
    print("停手 3.0s:", window_rect())
    send(MOUSEEVENTF_LEFTUP)
    time.sleep(0.2)
    print("松开后:", window_rect())


if __name__ == "__main__":
    main()
