# -*- coding: utf-8 -*-
"""Net speed monitor pinned to the Windows 11 taskbar, one widget per monitor.

Down/up throughput in Mbps, transparent background. Tray icon gives the settings
panel (font, size, colour), enable/disable, and start-with-Windows.
"""
import ctypes
import ctypes.wintypes as w
import json
import os
import sys
import threading
import time

VERSION = "1.1.2"

SCRIPT = os.path.abspath(__file__)
BASE = os.path.dirname(SCRIPT)
if getattr(sys, "frozen", False):
    # bundled by PyInstaller: keep config next to the .exe, never in the temp bundle
    BASE = os.path.dirname(os.path.abspath(sys.executable))
CFG_PATH = os.path.join(BASE, "config.json")

DEFAULT = {
    "enabled": True,
    "font": "Segoe UI",
    "size": 13,
    "color": "#FFFFFF",
    "refresh_ms": 1000,
    "layout_ms": 2000,
}

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
iphlp = ctypes.WinDLL("iphlpapi")

try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
except Exception:
    pass

LRESULT = ctypes.c_longlong
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong)

POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_TRANSPARENT = \
    0x80000, 0x8000000, 0x80, 0x8, 0x20
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x10, 0x40
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
ULW_ALPHA = 2
AC_SRC_OVER, AC_SRC_ALPHA = 0, 1
BI_RGB = 0
DIB_RGB_COLORS = 0
ANTIALIASED_QUALITY = 4
TRANSPARENT = 1
DT_CENTER, DT_VCENTER, DT_SINGLELINE, DT_NOCLIP = 0x1, 0x4, 0x20, 0x100
WM_DESTROY, WM_TIMER, WM_NULL = 0x2, 0x113, 0x0
WM_DISPLAYCHANGE = 0x7E      # resolution / monitor layout changed
WM_SETTINGCHANGE = 0x1A
WM_LBUTTONUP, WM_RBUTTONUP, WM_CONTEXTMENU = 0x202, 0x205, 0x7B
MF_STRING, MF_CHECKED, MF_SEPARATOR = 0x0, 0x8, 0x800
TPM_RETURNCMD, TPM_RIGHTBUTTON, TPM_NONOTIFY = 0x100, 0x2, 0x80
NIM_ADD, NIM_DELETE, NIM_SETVERSION = 0, 2, 4
NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
NOTIFYICON_VERSION_4 = 4
IDI_APPLICATION = 32512
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
WM_APPLY = WM_APP + 2
WM_QUITAPP = WM_APP + 3
TIMER_PAINT, TIMER_LAYOUT = 1, 2
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "NetSpeedMonitor"


# ---------------- config ----------------
def load_cfg():
    cfg = dict(DEFAULT)
    try:
        with open(CFG_PATH, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    tmp = CFG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({k: cfg[k] for k in DEFAULT}, fh, indent=2)
    os.replace(tmp, CFG_PATH)


def autostart_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return bool(winreg.QueryValueEx(k, AUTOSTART_NAME)[0])
    except OSError:
        return False


def autostart_command():
    if getattr(sys, "frozen", False):
        return '"%s"' % os.path.abspath(sys.executable)
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        cand = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(cand):
            exe = cand
    return '"%s" "%s"' % (exe, SCRIPT)


def set_autostart(on):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        if on:
            winreg.SetValueEx(k, AUTOSTART_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, AUTOSTART_NAME)
            except FileNotFoundError:
                pass


# ---------------- ctypes signatures ----------------
user32.CreateWindowExW.restype = w.HWND
user32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, ctypes.c_void_p]
user32.FindWindowExW.restype = w.HWND
user32.FindWindowExW.argtypes = [w.HWND, w.HWND, w.LPCWSTR, w.LPCWSTR]
user32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_uint]
user32.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
user32.IsWindowVisible.argtypes = [w.HWND]
user32.IsWindow.argtypes = [w.HWND]
user32.DestroyWindow.argtypes = [w.HWND]
user32.GetDC.restype = w.HDC
user32.GetDC.argtypes = [w.HWND]
user32.ReleaseDC.argtypes = [w.HWND, w.HDC]
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [w.HWND, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong]
user32.DrawTextW.argtypes = [w.HDC, w.LPCWSTR, ctypes.c_int, ctypes.POINTER(w.RECT), ctypes.c_uint]
user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.RegisterWindowMessageW.restype = ctypes.c_uint
user32.RegisterWindowMessageW.argtypes = [w.LPCWSTR]
user32.CreatePopupMenu.restype = w.HMENU
user32.AppendMenuW.argtypes = [w.HMENU, ctypes.c_uint, w.WPARAM, w.LPCWSTR]
user32.TrackPopupMenu.argtypes = [w.HMENU, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  w.HWND, ctypes.c_void_p]
user32.SetForegroundWindow.argtypes = [w.HWND]
user32.PostMessageW.argtypes = [w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM]
user32.GetCursorPos.argtypes = [ctypes.POINTER(w.POINT)]
user32.LoadIconW.restype = w.HICON
user32.LoadIconW.argtypes = [w.HINSTANCE, w.LPCWSTR]
user32.CreateIconIndirect.restype = w.HICON
user32.CreateIconIndirect.argtypes = [ctypes.c_void_p]
user32.DestroyIcon.argtypes = [w.HICON]
user32.SetTimer.argtypes = [w.HWND, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
user32.GetMessageW.argtypes = [ctypes.c_void_p, w.HWND, ctypes.c_uint, ctypes.c_uint]
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.DestroyMenu.argtypes = [w.HMENU]
user32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
gdi32.CreateDIBSection.restype = ctypes.c_void_p
gdi32.CreateDIBSection.argtypes = [w.HDC, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p),
                                   w.HANDLE, w.DWORD]
gdi32.CreateFontW.restype = w.HANDLE
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 13 + [w.LPCWSTR]
gdi32.CreateCompatibleDC.restype = w.HDC
gdi32.CreateCompatibleDC.argtypes = [w.HDC]
gdi32.SelectObject.argtypes = [w.HDC, w.HANDLE]
gdi32.SetTextColor.argtypes = [w.HDC, w.COLORREF]
gdi32.SetBkMode.argtypes = [w.HDC, ctypes.c_int]
gdi32.DeleteObject.argtypes = [w.HANDLE]
gdi32.DeleteDC.argtypes = [w.HDC]
gdi32.CreateBitmap.restype = w.HANDLE
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_char_p]
shell32.Shell_NotifyIconW.argtypes = [w.DWORD, ctypes.c_void_p]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                ("biClrImportant", w.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


user32.UpdateLayeredWindow.restype = ctypes.c_bool
user32.UpdateLayeredWindow.argtypes = [w.HWND, w.HDC, ctypes.POINTER(w.POINT), ctypes.POINTER(w.SIZE),
                                       w.HDC, ctypes.POINTER(w.POINT), w.DWORD,
                                       ctypes.POINTER(BLENDFUNCTION), w.DWORD]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", w.BOOL), ("xHotspot", w.DWORD), ("yHotspot", w.DWORD),
                ("hbmMask", w.HANDLE), ("hbmColor", w.HANDLE)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                ("hCursor", w.HANDLE), ("hbrBackground", w.HANDLE), ("lpszMenuName", w.LPCWSTR),
                ("lpszClassName", w.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint), ("uCallbackMessage", ctypes.c_uint), ("hIcon", w.HICON),
                ("szTip", w.WCHAR * 128), ("dwState", w.DWORD), ("dwStateMask", w.DWORD),
                ("szInfo", w.WCHAR * 256), ("uVersion", ctypes.c_uint), ("szInfoTitle", w.WCHAR * 64),
                ("dwInfoFlags", w.DWORD), ("guidItem", ctypes.c_ubyte * 16), ("hBalloonIcon", w.HICON)]


# ---------------- network counters ----------------
class LUID(ctypes.Structure):
    _fields_ = [("Value", ctypes.c_uint64)]


class GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16),
                ("d4", ctypes.c_ubyte * 8)]


class MIB_IF_ROW2(ctypes.Structure):
    _fields_ = [
        ("InterfaceLuid", LUID), ("InterfaceIndex", ctypes.c_uint32), ("InterfaceGuid", GUID),
        ("Alias", ctypes.c_wchar * 257), ("Description", ctypes.c_wchar * 257),
        ("PhysicalAddressLength", ctypes.c_uint32), ("PhysicalAddress", ctypes.c_ubyte * 32),
        ("PermanentPhysicalAddress", ctypes.c_ubyte * 32), ("Mtu", ctypes.c_uint32),
        ("Type", ctypes.c_uint32), ("TunnelType", ctypes.c_uint32), ("MediaType", ctypes.c_uint32),
        ("PhysicalMediumType", ctypes.c_uint32), ("AccessType", ctypes.c_uint32),
        ("DirectionType", ctypes.c_uint32), ("_flags", ctypes.c_uint32), ("OperStatus", ctypes.c_uint32),
        ("AdminStatus", ctypes.c_uint32), ("MediaConnectState", ctypes.c_uint32), ("NetworkGuid", GUID),
        ("ConnectionType", ctypes.c_uint32), ("TransmitLinkSpeed", ctypes.c_uint64),
        ("ReceiveLinkSpeed", ctypes.c_uint64), ("InOctets", ctypes.c_uint64), ("InUcastPkts", ctypes.c_uint64),
        ("InNUcastPkts", ctypes.c_uint64), ("InDiscards", ctypes.c_uint64), ("InErrors", ctypes.c_uint64),
        ("InUnknownProtos", ctypes.c_uint64), ("InUcastOctets", ctypes.c_uint64),
        ("InMulticastOctets", ctypes.c_uint64), ("InBroadcastOctets", ctypes.c_uint64),
        ("OutOctets", ctypes.c_uint64), ("OutUcastPkts", ctypes.c_uint64), ("OutNUcastPkts", ctypes.c_uint64),
        ("OutDiscards", ctypes.c_uint64), ("OutErrors", ctypes.c_uint64), ("OutUcastOctets", ctypes.c_uint64),
        ("OutMulticastOctets", ctypes.c_uint64), ("OutBroadcastOctets", ctypes.c_uint64),
        ("OutQLen", ctypes.c_uint64)]


class MIB_IF_TABLE2(ctypes.Structure):
    _fields_ = [("NumEntries", ctypes.c_uint32), ("Table", MIB_IF_ROW2 * 1)]


iphlp.GetIfTable2.argtypes = [ctypes.POINTER(ctypes.POINTER(MIB_IF_TABLE2))]
iphlp.GetIfTable2.restype = ctypes.c_ulong
iphlp.FreeMibTable.argtypes = [ctypes.c_void_p]
assert ctypes.sizeof(MIB_IF_ROW2) == 1352


def counters():
    """Total (in, out) octets over distinct active physical interfaces."""
    p = ctypes.POINTER(MIB_IF_TABLE2)()
    if iphlp.GetIfTable2(ctypes.byref(p)) != 0:
        return None
    n = p.contents.NumEntries
    rows = ctypes.cast(ctypes.addressof(p.contents) + 8, ctypes.POINTER(MIB_IF_ROW2))
    seen, tin, tout = set(), 0, 0
    for i in range(n):
        r = rows[i]
        if r.OperStatus != 1 or r.Type not in (6, 71):
            continue
        mac = bytes(r.PhysicalAddress[:max(r.PhysicalAddressLength, 0)])
        if r.PhysicalAddressLength < 6 or mac in seen:
            continue
        seen.add(mac)
        tin += r.InOctets
        tout += r.OutOctets
    iphlp.FreeMibTable(p)
    return tin, tout


# ---------------- taskbar geometry ----------------
CLASS_NAME = "EntNetSpeedWidget"
MSG_CLASS = "EntNetSpeedHost"
SKIP = {"Windows.UI.Composition.DesktopWindowContentBridge", "Windows.UI.Core.CoreWindow",
        "TrayDummySearchControl"}


def _cls(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value


def _rect(h):
    r = w.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def _children(h):
    out, c = [], None
    while True:
        c = user32.FindWindowExW(h, c, None, None)
        if not c:
            return out
        out.append(c)


def traybars():
    """Every taskbar band, one per monitor.

    Deliberately does NOT filter on IsWindowVisible: during a display switch, DPMS
    sleep or a monitor being re-detached, the band window still exists but reports
    invisible. Filtering it out made the widget vanish on that monitor until the
    user toggled enable/disable.
    """
    found = []
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    user32.EnumWindows.argtypes = [CB, w.LPARAM]

    def cb(h, lp):
        if _cls(h) in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            L, T, R, B = _rect(h)
            if R > L and B > T:      # must have real geometry
                found.append(h)
        return True

    user32.EnumWindows(CB(cb), 0)
    return found


def place(band, winw):
    """Return (x, y, w, h) screen rect inside taskbar `band`: left of Start, else widest gap."""
    L, T, R, B = _rect(band)
    h = B - T
    occupied, start_left = [], None
    for ch in _children(band):
        c = _cls(ch)
        if c in SKIP or c in (CLASS_NAME, MSG_CLASS):
            continue
        x1, y1, x2, y2 = _rect(ch)
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        if c == "Start" and start_left is None:
            start_left = x1  # anchor; the Start element itself may report invisible
            continue
        if not user32.IsWindowVisible(ch):
            continue
        occupied.append((max(x1, L), min(x2, R)))
    occupied = sorted(i for i in occupied if i[1] > L and i[0] < R)
    merged = []
    for a, b in occupied:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    gaps, cur = [], L
    for a, b in merged:
        if a - cur > 0:
            gaps.append((cur, a))
        cur = max(cur, b)
    if R - cur > 0:
        gaps.append((cur, R))
    if not gaps:
        gaps = [(L, R)]
        if R - L < winw:
            return L, T, min(winw, R - L), h

    if start_left is not None:
        x = start_left - winw
        if x >= L and any(x >= gl and start_left <= gr for gl, gr in gaps):
            return x, T, winw, h
    gl, gr = max(gaps, key=lambda g: g[1] - g[0])
    if gr - gl < winw:
        # No gap wide enough (crowded bar, tiny band). Never return None -- that left
        # the widget stuck at its previous, possibly stale coordinates. Clamp instead.
        return gl, T, max(1, min(winw, gr - gl)), h
    x = gl if (gl + gr) / 2 < (L + R) / 2 else gr - winw
    return x, T, winw, h


def hex_to_colorref(s):
    s = (s or "#FFFFFF").lstrip("#")
    if len(s) != 6:
        s = "FFFFFF"
    r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    return (b << 16) | (g << 8) | r


def text_width(cfg):
    return max(110, int(cfg["size"] * 10.2))


# ---------------- widget windows ----------------
class Widget:
    def __init__(self, band, cfg):
        self.band = band
        self.cfg = cfg
        self.hwnd = None
        self.last_text = None
        self.memdc = None
        self.bmp = None
        self.bits = None
        self.font = None
        self.pos = None
        self.w = text_width(cfg)
        self.h = 48
        self.cfg_key = (cfg["font"], cfg["size"], cfg["color"])

    def create(self):
        L, T, R, B = _rect(self.band)
        self.h = B - T
        r = place(self.band, self.w) or (L, T, self.w, self.h)
        x, y = r[0], r[1]
        self.w, self.h = max(1, r[2]), max(1, r[3])
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_TRANSPARENT,
            CLASS_NAME, "netspeed", POPUP, x, y, self.w, self.h, None, None, None, None)
        if not self.hwnd:
            print("CreateWindowExW failed:", ctypes.get_last_error(), file=sys.stderr, flush=True)
            return False
        self.pos = (x, y, self.w, self.h)
        self.build_surfaces()
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        return True

    def destroy(self):
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        self.destroy_surfaces()

    def build_surfaces(self):
        srcdc = user32.GetDC(None)
        self.memdc = gdi32.CreateCompatibleDC(srcdc)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.w
        bmi.bmiHeader.biHeight = -self.h  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        self.bmp = gdi32.CreateDIBSection(srcdc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        user32.ReleaseDC(None, srcdc)
        self.bits = bits
        gdi32.SelectObject(self.memdc, self.bmp)
        self.font = gdi32.CreateFontW(int(self.cfg["size"]), 0, 0, 0, 600, 0, 0, 0, 0, 0, 0,
                                      ANTIALIASED_QUALITY, 0, self.cfg["font"])
        gdi32.SelectObject(self.memdc, self.font)
        gdi32.SetBkMode(self.memdc, TRANSPARENT)
        gdi32.SetTextColor(self.memdc, hex_to_colorref(self.cfg["color"]))
        # GDI antialiases toward the black DIB, so each channel is colour*coverage.
        # Coverage is recovered against the colour's peak channel.
        c = hex_to_colorref(self.cfg["color"])
        self.peak = max(c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF) or 255
        self.last_text = None

    def reposition(self):
        if not self.hwnd or not user32.IsWindow(self.hwnd):
            return False
        if not user32.IsWindow(self.band):
            return False
        r = place(self.band, self.w)
        if not r:
            return True
        if r == self.pos:
            return True
        # geometry may have changed (size setting, DPI, band moved): surfaces are
        # tied to w/h, so rebuild them rather than blit a stale-sized buffer
        if r[2] != self.w or r[3] != self.h:
            self.destroy_surfaces()
            self.w, self.h = max(1, r[2]), max(1, r[3])
            self.build_surfaces()
        self.pos = r
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, r[0], r[1], r[2], r[3],
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)
        self.last_text = None
        return True

    def destroy_surfaces(self):
        for obj, dtor in ((self.bmp, gdi32.DeleteObject), (self.font, gdi32.DeleteObject),
                          (self.memdc, gdi32.DeleteDC)):
            if obj:
                dtor(obj)
        self.bmp = self.font = self.memdc = None
        self.bits = None

    def paint(self, text):
        if text == self.last_text:
            return
        self.last_text = text
        buf = (ctypes.c_ubyte * (self.w * self.h * 4)).from_address(self.bits.value)
        ctypes.memset(buf, 0, len(buf))
        rc = w.RECT(0, 0, self.w, self.h)
        user32.DrawTextW(self.memdc, text, len(text), ctypes.byref(rc),
                         DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOCLIP)
        rgb = hex_to_colorref(self.cfg["color"])
        cr, cg, cb = rgb & 0xFF, (rgb >> 8) & 0xFF, (rgb >> 16) & 0xFF
        peak = self.peak or 255
        for i in range(0, len(buf), 4):
            v = max(buf[i], buf[i + 1], buf[i + 2])
            a = v * 255 // peak
            if a > 255:
                a = 255
            buf[i] = cr * a // 255
            buf[i + 1] = cg * a // 255
            buf[i + 2] = cb * a // 255
            buf[i + 3] = a
        screen = user32.GetDC(None)
        pt_src = w.POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        r = w.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(r))
        pt_dst = w.POINT(r.left, r.top)
        size = w.SIZE(self.w, self.h)
        user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(pt_dst), ctypes.byref(size),
                                   self.memdc, ctypes.byref(pt_src), 0, ctypes.byref(blend), ULW_ALPHA)
        user32.ReleaseDC(None, screen)


# ---------------- tray icon (drawn in code, no asset files) ----------------
def make_icon():
    size = 16
    px = bytearray(size * size * 4)

    def put(x, y, r, g, b):
        i = (y * size + x) * 4
        px[i], px[i + 1], px[i + 2], px[i + 3] = b, g, r, 255

    for x in range(7, 10):                       # down arrow (green)
        for y in range(1, 9):
            put(x, y, 0, 200, 90)
    for k in range(5):
        for x in range(5 + k, 12 - k):
            put(x, 8 + k, 0, 200, 90)
    for x in range(7, 10):                       # up arrow (blue)
        for y in range(8, 15):
            put(x, y, 90, 170, 255)
    for k in range(5):
        for x in range(5 + k, 12 - k):
            put(x, 14 - k, 90, 170, 255)

    srcdc = user32.GetDC(None)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = size
    bmi.bmiHeader.biHeight = -size
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    bits = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(srcdc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
    ctypes.memmove(bits.value, bytes(px), len(px))
    mask = gdi32.CreateBitmap(size, size, 1, 1, b"\x00" * (size * 2))
    ii = ICONINFO(1, 0, 0, mask, hbm)
    hicon = user32.CreateIconIndirect(ctypes.byref(ii))
    gdi32.DeleteObject(hbm)
    gdi32.DeleteObject(mask)
    user32.ReleaseDC(None, srcdc)
    return hicon or user32.LoadIconW(None, w.LPCWSTR(IDI_APPLICATION))


# ---------------- state ----------------
widgets = []
prev = None
prev_t = 0.0
last_paint = "\u2193 0.00  \u2191 0.00 Mbps"
msg_hwnd = None
hicon = None
TASKBAR_CREATED = None
_settings_open = threading.Event()


# ---------------- settings panel (tkinter, own thread) ----------------
def open_settings():
    if _settings_open.is_set():
        return
    _settings_open.set()

    def run():
        try:
            import tkinter as tk
            import tkinter.font as tkfont
            from tkinter import colorchooser, ttk

            cfg = load_cfg()
            root = tk.Tk()
            root.title("NetSpeed Monitor v%s" % VERSION)
            root.attributes("-topmost", True)
            root.resizable(False, False)
            root.configure(padx=14, pady=12)

            fam = tk.StringVar(value=cfg["font"])
            siz = tk.IntVar(value=cfg["size"])
            col = tk.StringVar(value=cfg["color"])
            ena = tk.BooleanVar(value=cfg["enabled"])
            aut = tk.BooleanVar(value=autostart_enabled())

            rows = ttk.Frame(root)
            rows.grid(row=0, column=0, sticky="w")
            ttk.Label(rows, text="Font").grid(row=0, column=0, sticky="w", pady=3)
            ttk.Combobox(rows, textvariable=fam, values=sorted(set(tkfont.families(root))),
                         width=28).grid(row=0, column=1, sticky="w", padx=8)
            ttk.Label(rows, text="Size").grid(row=1, column=0, sticky="w", pady=3)
            ttk.Spinbox(rows, from_=8, to=30, textvariable=siz, width=6).grid(
                row=1, column=1, sticky="w", padx=8)
            ttk.Label(rows, text="Colour").grid(row=2, column=0, sticky="w", pady=3)

            swatch = tk.Button(rows, text="      ", bg=col.get(), relief="groove", width=6)

            def pick():
                _rgb, hx = colorchooser.askcolor(color=col.get(), parent=root)
                if hx:
                    col.set(hx.upper())
                    swatch.configure(bg=col.get())

            swatch.configure(command=pick)
            swatch.grid(row=2, column=1, sticky="w", padx=8)

            preview = tk.Label(root, text="\u2193 12.34  \u2191 5.67 Mbps", bg="#1b1b1b",
                               fg=col.get(), font=(fam.get(), siz.get(), "bold"), pady=8)
            preview.grid(row=1, column=0, sticky="ew", pady=(10, 2))

            def refresh_preview(*_):
                preview.configure(fg=col.get(), font=(fam.get(), siz.get(), "bold"))

            for v in (fam, siz, col):
                v.trace_add("write", refresh_preview)

            ttk.Checkbutton(root, text="Enable monitor", variable=ena).grid(
                row=2, column=0, sticky="w", pady=(8, 0))
            ttk.Checkbutton(root, text="Start with Windows", variable=aut).grid(
                row=3, column=0, sticky="w")

            def apply():
                new = load_cfg()
                new.update({"font": fam.get(), "size": int(siz.get()), "color": col.get(),
                            "enabled": bool(ena.get())})
                save_cfg(new)
                set_autostart(bool(aut.get()))
                user32.PostMessageW(msg_hwnd, WM_APPLY, 0, 0)
                root.destroy()

            btns = ttk.Frame(root)
            btns.grid(row=4, column=0, sticky="e", pady=(12, 0))
            ttk.Button(btns, text="Apply", command=apply).grid(row=0, column=0, padx=4)
            ttk.Button(btns, text="Close", command=root.destroy).grid(row=0, column=1)

            root.mainloop()
        except Exception as exc:
            print("settings panel error:", exc, file=sys.stderr, flush=True)
        finally:
            _settings_open.clear()

    threading.Thread(target=run, daemon=True).start()


# ---------------- tray ----------------
def show_menu():
    cfg = load_cfg()
    menu = user32.CreatePopupMenu()
    user32.AppendMenuW(menu, MF_STRING, 1, "Settings...")
    user32.AppendMenuW(menu, MF_STRING, 5, "Refresh widgets")
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, MF_STRING | (MF_CHECKED if cfg["enabled"] else 0), 2, "Enable monitor")
    user32.AppendMenuW(menu, MF_STRING | (MF_CHECKED if autostart_enabled() else 0), 3,
                       "Start with Windows")
    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    user32.AppendMenuW(menu, MF_STRING, 4, "Exit")
    pt = w.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    user32.SetForegroundWindow(msg_hwnd)
    cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_NONOTIFY,
                                pt.x, pt.y, 0, msg_hwnd, None)
    user32.PostMessageW(msg_hwnd, WM_NULL, 0, 0)
    user32.DestroyMenu(menu)
    if cmd == 1:
        open_settings()
    elif cmd == 2:
        cfg["enabled"] = not cfg["enabled"]
        save_cfg(cfg)
        user32.PostMessageW(msg_hwnd, WM_APPLY, 0, 0)
    elif cmd == 3:
        set_autostart(not autostart_enabled())
    elif cmd == 5:
        user32.PostMessageW(msg_hwnd, WM_APPLY, 0, 0)
    elif cmd == 4:
        user32.PostMessageW(msg_hwnd, WM_QUITAPP, 0, 0)


def tray_add():
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = msg_hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAY
    nid.hIcon = hicon
    nid.szTip = "NetSpeed Monitor v%s" % VERSION
    ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
    nid.uVersion = NOTIFYICON_VERSION_4
    shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(nid))
    return ok


def tray_remove():
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = msg_hwnd
    nid.uID = 1
    shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))


def rebuild():
    global last_paint
    for wd in widgets:
        wd.destroy()
    del widgets[:]
    last_paint = "\u2193 0.00  \u2191 0.00 Mbps"
    cfg = load_cfg()
    if not cfg["enabled"]:
        return
    sync_widgets()
    for wd in widgets:
        wd.paint(last_paint)


def sync_widgets():
    """Match the live widget set to the live taskbar set, every tick.

    The old code only rebuilt when a widget's window had been destroyed, so a monitor
    that appeared, disappeared or changed geometry left the set out of step -- the
    symptom was a widget missing on one monitor (or two stacked on another) until the
    user toggled enable/disable. Now the band list is the source of truth: attach a
    widget to every band that lacks one, drop widgets whose band is gone, and repaint
    anything that got re-created.
    """
    cfg = load_cfg()
    if not cfg["enabled"]:
        # disabled: drop everything, including widgets created before the toggle
        for wd in widgets:
            wd.destroy()
        del widgets[:]
        return
    band_list = traybars()
    live = {int(wd.band): wd for wd in widgets}

    # config may have changed (font, size, colour) since these widgets were built.
    # Their width comes from cfg, and their font/colour are baked into the surfaces,
    # so refresh in place -- without this a settings change only reached monitors
    # whose widget happened to be re-created, leaving the others at the old look.
    want_w = text_width(cfg)
    want_key = (cfg["font"], cfg["size"], cfg["color"])
    for wd in widgets:
        if getattr(wd, "cfg_key", None) != want_key:
            wd.cfg = dict(cfg)
            wd.cfg_key = want_key
            wd.destroy_surfaces()
            wd.w = want_w
            wd.h = max(1, _rect(wd.band)[3] - _rect(wd.band)[1]) if user32.IsWindow(wd.band) else wd.h
            wd.build_surfaces()
            wd.pos = None          # force a reposition with the new geometry
            wd.last_text = None
        elif wd.w != want_w:
            wd.w = want_w
            wd.pos = None

    # drop widgets whose band no longer exists
    for band in list(live):
        wd = live[band]
        if not user32.IsWindow(band):
            wd.destroy()
            widgets.remove(wd)
            del live[band]

    # add a widget for every band that has none
    for band in band_list:
        if int(band) in live:
            continue
        wd = Widget(band, cfg)
        if wd.create():
            wd.paint(last_paint)
            widgets.append(wd)
            live[int(band)] = wd


def wndproc(h, msg, wp, lp):
    global prev, prev_t, last_paint
    if msg == WM_TRAY:
        if (lp & 0xFFFF) in (WM_LBUTTONUP, WM_CONTEXTMENU, WM_RBUTTONUP):
            show_menu()
        return 0
    if msg == WM_TIMER:
        if wp == TIMER_PAINT:
            now = time.time()
            cur = counters()
            if cur and prev and now - prev_t > 0.2:
                dt = now - prev_t
                dn = (cur[0] - prev[0]) * 8 / 1e6 / dt
                up = (cur[1] - prev[1]) * 8 / 1e6 / dt
                prev, prev_t = cur, now
                if dn < 0 or up < 0:
                    dn = up = 0.0
                last_paint = "\u2193 %.2f  \u2191 %.2f Mbps" % (dn, up)
                for wd in widgets:
                    wd.paint(last_paint)
            elif cur:
                prev = cur
        elif wp == TIMER_LAYOUT:
            sync_widgets()
            for wd in list(widgets):
                if not wd.reposition():
                    # band died between sync and now: drop it and re-sync next tick
                    wd.destroy()
                    widgets.remove(wd)
        return 0
    if msg == WM_APPLY:
        rebuild()
        prev, prev_t = counters(), time.time()
        return 0
    if msg == WM_DISPLAYCHANGE or msg == WM_SETTINGCHANGE:
        # monitor added/removed/rearranged, or resolution/DPI changed: re-attach now
        # instead of waiting for the layout tick
        sync_widgets()
        for wd in list(widgets):
            wd.reposition()
        return 0
    if msg == WM_QUITAPP:
        user32.DestroyWindow(msg_hwnd)
        return 0
    if TASKBAR_CREATED and msg == TASKBAR_CREATED:
        tray_add()
        rebuild()
        return 0
    if msg == WM_DESTROY:
        tray_remove()
        ctypes.windll.kernel32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(h, msg, wp, lp)


def main():
    global msg_hwnd, hicon, TASKBAR_CREATED, prev, prev_t
    save_cfg(load_cfg())  # create / normalise config.json

    # single instance: two copies would each attach a widget to every taskbar,
    # which looks exactly like 'duplicate/garbled widgets' on some monitors.
    # CreateMutexW sets last-error; read it immediately, before any other call.
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = w.HANDLE
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, w.BOOL, w.LPCWSTR]
    inst_mutex = k32.CreateMutexW(None, False, "Local\\EntNetSpeedMonitor")
    already = ctypes.get_last_error() == 183   # ERROR_ALREADY_EXISTS
    if already:
        print("another instance is already running", file=sys.stderr, flush=True)
        return 0

    inst = ctypes.windll.kernel32.GetModuleHandleW(None)
    host_proc = WNDPROC(wndproc)
    wc = WNDCLASS()
    wc.lpfnWndProc = host_proc
    wc.hInstance = inst
    wc.lpszClassName = MSG_CLASS
    user32.RegisterClassW(ctypes.byref(wc))

    wc2 = WNDCLASS()
    wc2.lpfnWndProc = WNDPROC(lambda h, m, a, b: user32.DefWindowProcW(h, m, a, b))
    wc2.hInstance = inst
    wc2.lpszClassName = CLASS_NAME
    user32.RegisterClassW(ctypes.byref(wc2))

    msg_hwnd = user32.CreateWindowExW(0, MSG_CLASS, "NetSpeedHost", POPUP, 0, 0, 0, 0,
                                      None, None, None, None)
    if not msg_hwnd:
        print("message window failed:", ctypes.get_last_error(), file=sys.stderr, flush=True)
        return 1

    hicon = make_icon()
    print("tray icon:", tray_add(), flush=True)
    TASKBAR_CREATED = user32.RegisterWindowMessageW("TaskbarCreated")

    rebuild()
    prev, prev_t = counters(), time.time()
    cfg = load_cfg()
    user32.SetTimer(msg_hwnd, TIMER_PAINT, int(cfg["refresh_ms"]), None)
    user32.SetTimer(msg_hwnd, TIMER_LAYOUT, int(cfg["layout_ms"]), None)
    print("widgets on %d taskbar(s), enabled=%s" % (len(widgets), cfg["enabled"]), flush=True)

    msg = w.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    for wd in widgets:
        wd.destroy()
    tray_remove()
    if hicon:
        user32.DestroyIcon(hicon)
    print("exited", flush=True)
    return 0


if __name__ == "__main__":
    if any(a in ("-V", "--version") for a in sys.argv[1:]):
        print("NetSpeed Monitor %s" % VERSION)
        sys.exit(0)
    sys.exit(main())
