# -*- coding: utf-8 -*-
"""Dev tool: render the tray icon glyph into a multi-size .ico for the exe.

Usage: python make_ico.py app.ico
"""
import struct
import sys


def draw(size):
    """Return RGBA bytes for the down/up arrow glyph at `size` px."""
    # geometry defined on a 16x16 grid, scaled up
    s = size / 16.0
    px = bytearray(size * size * 4)
    for i in range(3, len(px), 4):
        px[i] = 0

    def put(x, y, r, g, b, a=255):
        ix, iy = int(x * s), int(y * s)
        for dy in range(int(s) or 1):
            for dx in range(int(s) or 1):
                j = ((iy + dy) * size + (ix + dx)) * 4
                if 0 <= j < len(px):
                    px[j], px[j + 1], px[j + 2], px[j + 3] = b, g, r, a

    # down arrow (green), then up arrow (blue) — same shape as make_icon()
    for x in range(7, 10):
        for y in range(1, 9):
            put(x, y, 0, 200, 90)
    for k in range(5):
        for x in range(5 + k, 12 - k):
            put(x, 8 + k, 0, 200, 90)
    for x in range(7, 10):
        for y in range(8, 15):
            put(x, y, 90, 170, 255)
    for k in range(5):
        for x in range(5 + k, 12 - k):
            put(x, 14 - k, 90, 170, 255)
    return bytes(px)


def bmp_for_ico(size, rgba):
    """ICO stores a bottom-up 32bpp DIB plus an AND mask."""
    header = struct.pack("<IiiHHIIiiII", 40, size, size, 1, 32, 0, 0, 0, 0, 0, 0)
    xor = bytearray()
    for y in range(size - 1, -1, -1):          # bottom-up
        xor += rgba[y * size * 4:(y + 1) * size * 4]
    mask_row = ((size + 31) // 32) * 4          # 1bpp, padded to 4 bytes
    and_mask = bytes(mask_row * size)
    return header + bytes(xor) + and_mask


def main(out):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [(n, bmp_for_ico(n, draw(n))) for n in sizes]
    parts, offset = [], 6 + 16 * len(images)
    for n, data in images:
        w = 0 if n == 256 else n                  # 0 means 256 in the ICO header
        parts.append(struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    blob = struct.pack("<HHH", 0, 1, len(images)) + b"".join(parts) + b"".join(d for _, d in images)
    with open(out, "wb") as fh:
        fh.write(blob)
    print("wrote", out, len(blob), "bytes,", len(images), "sizes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "app.ico")
