"""发一次 Ctrl+Alt+N（默认 5 = 锁定开关），验证快捷键链路。用法：python sim_hotkey.py [n]"""
import ctypes
import sys
import time

user32 = ctypes.windll.user32
VK_CONTROL, VK_MENU = 0x11, 0x12
KEYEVENTF_KEYUP = 0x0002


def tap(vk):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)


n = sys.argv[1] if len(sys.argv) > 1 else "5"
vk = 0x30 + int(n)          # '1'..'9' 的虚拟键码是 0x31..0x39
user32.keybd_event(VK_CONTROL, 0, 0, 0)
user32.keybd_event(VK_MENU, 0, 0, 0)
tap(vk)
user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
print(f"sent ctrl+alt+{n}")
