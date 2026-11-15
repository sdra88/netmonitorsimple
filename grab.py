"""Grab a screen region to a PNG-less BMP, for visual verification."""
import ctypes, ctypes.wintypes as w, sys, struct

u = ctypes.WinDLL("user32")
g = ctypes.WinDLL("gdi32")
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass

# untyped ctypes defaults HDC/HANDLE/c_uint args to c_int, which corrupts the
# heap inside GetDIBits once a dim/pixel count exceeds 2^31 layout assumptions.
u.GetDC.restype = w.HDC
u.GetDC.argtypes = [w.HWND]
u.ReleaseDC.argtypes = [w.HWND, w.HDC]
g.CreateCompatibleDC.restype = w.HDC
g.CreateCompatibleDC.argtypes = [w.HDC]
g.CreateCompatibleBitmap.restype = w.HANDLE
g.CreateCompatibleBitmap.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]
g.SelectObject.restype = w.HANDLE
g.SelectObject.argtypes = [w.HDC, w.HANDLE]
g.BitBlt.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC,
                     ctypes.c_int, ctypes.c_int, w.DWORD]
g.GetDIBits.argtypes = [w.HDC, w.HANDLE, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
                        ctypes.c_void_p, ctypes.c_uint]
g.DeleteObject.argtypes = [w.HANDLE]
g.DeleteDC.argtypes = [w.HDC]

x, y, ww, hh = (int(v) for v in sys.argv[1:5])
out = sys.argv[5]
row = ww * 3
pad = (4 - row % 4) % 4
stride = row + pad

srcdc = u.GetDC(None)
memdc = g.CreateCompatibleDC(srcdc)
bmp = g.CreateCompatibleBitmap(srcdc, ww, hh)
old = g.SelectObject(memdc, bmp)
g.BitBlt(memdc, 0, 0, ww, hh, srcdc, x, y, 0x00CC0020)


class BIH(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                ("biClrImportant", w.DWORD)]


bi = BIH()
bi.biSize = ctypes.sizeof(BIH)
bi.biWidth = ww
bi.biHeight = -hh
bi.biPlanes = 1
bi.biBitCount = 24
bi.biCompression = 0
buf = ctypes.create_string_buffer(stride * hh)
g.GetDIBits(memdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
g.SelectObject(memdc, old)
g.DeleteObject(bmp)
g.DeleteDC(memdc)
u.ReleaseDC(None, srcdc)

pixels = buf.raw[:stride * hh]
hdr = struct.pack("<2sIHHI", b"BM", 14 + 40 + len(pixels), 0, 0, 54)
dib = struct.pack("<IiiHHIIiiII", 40, ww, -hh, 1, 24, 0, len(pixels), 2835, 2835, 0, 0)
open(out, "wb").write(hdr + dib + pixels)
print("wrote", out, ww, hh)
