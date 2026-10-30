"""Pack the arcade's under neons for the iPad port.

clNeon::setup (0x895094c) loads neon n's model from the table at 0x9420960:
data/effect/car_neon_<colour>_race.igb for 1..6 (the straight neons) and
car_spotneon_<colour>_race.igb for 7..12 (the spot neons), the colours green, blue, purple,
red, yellow, darkpurple. Each is one quad, x and z -29..29 at y 0 (u along x, v along -z),
and a 256 x 256 glow drawn additive (igBlendFunctionAttr SRC_ALPHA, ONE); the IGBs keep red
and blue the other way round (as goal_light01.tga), so they are swapped back. The port draws
the quad itself (lights.c), so only the images are packed: with their alpha multiplied in
(SRC_ALPHA, ONE adds rgb * a), as RGB565.

Writes neon.wpk: a WPK2 with no chunks, its twelve textures in neon order.

usage: pack_neon.py data_dir out.wpk
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

from igb import IGB
from tex import to_pil

COLOURS = ["green", "blue", "purple", "red", "yellow", "darkpurple"]


def neon_image(data, path):
    f = IGB(os.path.join(data, path))
    img = f.of_type("igImage")[0]
    a = np.asarray(to_pil(img, f.ref(img[13]).mem), dtype=np.float32)
    rgb = a[..., 2::-1] * (a[..., 3:4] / 255.0)
    return rgb.round().clip(0, 255).astype(np.uint16), img[2].i32, img[3].i32


def main():
    data, out = sys.argv[1], sys.argv[2]
    paths = ["effect/car_%s_%s_race.igb" % (k, c) for k in ("neon", "spotneon") for c in COLOURS]
    tex_off = 32
    data_off = tex_off + 64 * len(paths)
    tbl, blob = bytearray(), bytearray()
    for p in paths:
        rgb, w, h = neon_image(data, p)
        px = ((rgb[..., 0] >> 3) << 11) | ((rgb[..., 1] >> 2) << 5) | (rgb[..., 2] >> 3)
        px = px.astype("<u2").tobytes()
        tbl += struct.pack("<48sHHIII", os.path.basename(p).encode(), w, h, 0, data_off + len(blob), len(px))
        blob += px
        blob += b"\0" * (-len(blob) % 4)
    with open(out, "wb") as fp:
        fp.write(struct.pack("<4sIIIfIII", b"WPK2", len(paths), 0, 0, 4000.0, tex_off, data_off, data_off))
        fp.write(tbl)
        fp.write(blob)


if __name__ == "__main__":
    main()
