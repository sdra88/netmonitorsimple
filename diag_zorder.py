# -*- coding: utf-8 -*-
"""Compare z-order of each widget against its own taskbar band.

Lower GW_HWNDPREV count = higher on screen. If the band has a lower count than the
widget that sits on it, the band is covering the widget. That is the 'net speed
hilang saat taskbar diklik' symptom.
"""
import ctypes
import ctypes.wintypes as w

u = ctypes.WinDLL("user32", use_last_error=True)
u.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
u.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
u.GetWindow.argtypes = [w.HWND, ctypes.c_uint]
u.GetWindow.restype = w.HWND
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
u.EnumWindows.argtypes = [CB, w.LPARAM]
GW_HWNDPREV = 3


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def rect(h):
    r = w.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def zpos(h):
    n, cur = 0, h
    while n < 5000:
        cur = u.GetWindow(cur, GW_HWNDPREV)
        if not cur:
            break
        n += 1
    return n


wins = []
u.EnumWindows(CB(lambda h, l: (wins.append(h), True)[1]), 0)
bands = [h for h in wins if cls(h) in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")]
widg = [h for h in wins if cls(h) == "EntNetMonitorSimpleWidget"]

print("BAND")
for b in bands:
    print("  %-24s z=%-3d %s" % (cls(b), zpos(b), rect(b)))

print("WIDGET")
for h in widg:
    L, T, R, B = rect(h)
    # which band does it sit on?
    own = None
    for b in bands:
        bl, bt, br, bb = rect(b)
        if abs(bt - T) <= 8 and L >= bl - 8 and R <= br + 8:
            own = b
    print("  z=%-3d w=%-4d (%-6d,%d) band=%s (z=%s) -> %s"
          % (zpos(h), R - L, L, T,
             cls(own) if own else "?",
             zpos(own) if own else "-",
             "TERTUTUP taskbar" if own and zpos(own) < zpos(h) else "di atas taskbar"))