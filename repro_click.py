# -*- coding: utf-8 -*-
"""Real click on the taskbar, then measure whether the widget text survives.

Uses SendInput so the click is indistinguishable from a user click. Clicks an empty
part of the primary taskbar (right of the clock is risky, so it aims at a blank
stretch left of the tray), which normally opens nothing.
"""
import ctypes
import ctypes.wintypes as w
import struct
import sys
import time

u = ctypes.WinDLL("user32", use_last_error=True)
g = ctypes.WinDLL("gdi32")

u.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
u.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
u.IsWindow.argtypes = [w.HWND]
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


def above(h):
    n, cur = 0, h
    while n < 5000:
        cur = u.GetWindow(cur, GW_HWNDPREV)
        if not cur:
            break
        n += 1
    return n


def widgets():
    wins = []
    u.EnumWindows(CB(lambda h, l: (wins.append(h), True)[1]), 0)
    return [h for h in wins if cls(h) == "EntNetMonitorSimpleWidget"]


class BIH(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG),
                ("biPlanes", w.WORD), ("biBitCount", w.WORD), ("biCompression", w.DWORD),
                ("biSizeImage", w.DWORD), ("biXPelsPerMeter", w.LONG),
                ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                ("biClrImportant", w.DWORD)]


def white_px(x, y, ww, hh):
    srcdc = u.GetDC(None)
    memdc = g.CreateCompatibleDC(srcdc)
    bmp = g.CreateCompatibleBitmap(srcdc, ww, hh)
    g.SelectObject(memdc, bmp)
    g.BitBlt(memdc, 0, 0, ww, hh, srcdc, x, y, 0x00CC0020)
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = ww
    bi.biHeight = -hh
    bi.biPlanes = 1
    bi.biBitCount = 24
    row = ww * 3
    pad = (4 - row % 4) % 4
    stride = row + pad
    buf = ctypes.create_string_buffer(stride * hh)
    g.GetDIBits(memdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    g.DeleteObject(bmp)
    g.DeleteDC(memdc)
    u.ReleaseDC(None, srcdc)
    raw, n = buf.raw, 0
    for yy in range(hh):
        line = raw[yy * stride: yy * stride + row]
        for i in range(0, row, 3):
            if line[i] > 200 and line[i + 1] > 200 and line[i + 2] > 200:
                n += 1
    return n


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD),
                ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 8)]


def click(x, y):
    u.SetCursorPos(x, y)
    time.sleep(0.05)
    for flag in (0x0002, 0x0004):      # LEFTDOWN, LEFTUP
        inp = INPUT(0, MOUSEINPUT(x, y, 0, flag, 0, None), (ctypes.c_byte * 8)())
        u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def measure(tag, hs):
    out = []
    for h in hs:
        if not u.IsWindow(h):
            out.append((tag, "MATI", None, None))
            continue
        L, T, R, B = rect(h)
        px = white_px(L + 3, T, max(10, R - L - 6), max(10, B - T))
        out.append((tag, above(h), px, (L, T, R, B)))
    return out


def main():
    hs = widgets()
    print("widget: %d" % len(hs))
    if len(hs) < 2:
        print("perlu minimal 2 widget untuk uji ini")
        return 1

    print("\n--- sebelum klik ---")
    for tag, z, px, r in measure("before", hs):
        print("  z_above=%-3s teks=%-5s %s" % (z, px, r))

    # click an empty stretch of the primary taskbar
    click(1100, 1056)
    time.sleep(1.2)

    print("\n--- sesudah klik taskbar ---")
    for tag, z, px, r in measure("after", hs):
        print("  z_above=%-3s teks=%-5s %s" % (z, px, r))
    return 0


if __name__ == "__main__":
    sys.exit(main())