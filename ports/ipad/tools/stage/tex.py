"""Decode igImage pixel data to RGBA via Pillow's DDS reader."""
import io
import struct

from PIL import Image

# igImage pixel formats seen so far -> DDS FourCC
FOURCC = {14: b"DXT1", 15: b"DXT3", 16: b"DXT5"}


def to_pil(img_obj, data):
    w, h, fmt = img_obj[2].i32, img_obj[3].i32, img_obj[11].i32
    if fmt == 0:  # 8-bit luminance (the miniature course's roads, base_road_Fix)
        return Image.frombytes("L", (w, h), bytes(data[:w * h])).convert("RGBA")
    if fmt == 5:  # 24-bit RGB
        return Image.frombytes("RGB", (w, h), bytes(data[:w * h * 3])).convert("RGBA")
    if fmt == 7:  # 32-bit RGBA
        return Image.frombytes("RGBA", (w, h), bytes(data[:w * h * 4]))
    if fmt not in FOURCC:
        raise ValueError("unsupported igImage format %d" % fmt)
    block = 8 if fmt == 14 else 16
    top = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block
    hdr = struct.pack("<4s7I44x", b"DDS ", 124, 0x1007 | 0x80000, h, w, top, 0, 1)
    pf = struct.pack("<2I4s5I", 32, 0x4, FOURCC[fmt], 0, 0, 0, 0, 0)
    caps = struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    return Image.open(io.BytesIO(hdr + pf + caps + data[:top])).convert("RGBA")
