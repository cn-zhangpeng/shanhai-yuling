"""采样桌面窗口位置，算出走路场景的实际滑行速度（px/s）。"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
TITLE = "山海遇灵"


def pos():
    h = user32.FindWindowW(None, TITLE)
    if not h:
        return None
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return r.left


def main(seconds=9.0, step=0.2):
    t0 = time.time()
    samples = []
    while time.time() - t0 < seconds:
        p = pos()
        samples.append((round(time.time() - t0, 2), p))
        time.sleep(step)
    xs = [p for _, p in samples if p is not None]
    if not xs:
        print("没找到窗口")
        return
    print("采样:", " ".join(f"{t}s:{p}" for t, p in samples[:12]))
    moving = [p for p in xs if p != xs[0]]
    if moving:
        span = max(xs) - min(xs)
        print(f"位移区间 {min(xs)} -> {max(xs)}  span={span}px")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 9.0)
