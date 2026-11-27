# -*- coding: utf-8 -*-
"""Probe: report every taskbar band and every widget window, with geometry."""
import ctypes
import ctypes.wintypes as w

u = ctypes.WinDLL("user32")
u.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
u.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
u.IsWindowVisible.argtypes = [w.HWND]
u.GetClassNameW.restype = ctypes.c_int
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
u.EnumWindows.argtypes = [CB, w.LPARAM]


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def rct(h):
    r = w.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


wins = []
u.EnumWindows(CB(lambda h, l: (wins.append(h), True)[1]), 0)

bands = [h for h in wins if cls(h) in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")]
print("BAND (%d):" % len(bands))
for h in bands:
    L, T, R, B = rct(h)
    print("  %-24s (%d,%d,%d,%d)" % (cls(h), L, T, R, B))

widgets = [h for h in wins if cls(h) == "EntNetSpeedWidget"]
print("WIDGET (%d):" % len(widgets))
for h in widgets:
    L, T, R, B = rct(h)
    print("  (%d,%d,%d,%d) w=%d h=%d vis=%s"
          % (L, T, R, B, R - L, B - T, bool(u.IsWindowVisible(h))))

print("HOST:", "ada" if any(cls(h) == "EntNetSpeedHost" for h in wins) else "TIDAK ADA")
