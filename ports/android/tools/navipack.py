"""Pack the arcade's minimap (clMiniMap) for the race HUD into navi.bin.

usage: navipack.py <arcade data dir> <main> <out dir> [<minimap igb> <out name>]
(another city's: its scene file's MiniMap, e.g. OsNavi.igb navi_oosaka.bin; Hakone's, Nagoya's
and Fukuoka's areas share one ON and one OFF road each, kept under the city's first area)

The minimap is a 3D model seen from above: data/minimap/SkNavi.igb holds every road of the
Tokyo map twice, <area>_ON (orange, y ~1000) and <area>_OFF (blue grey, y ~0), and the rest
of the network blended; clMiniMap::update shows the ON road of the areas being driven and the
OFF one of the others. The player is the red arrow of data/effect/car_icon.igb (ICON_RED).
Area names by EAreaId come from main's table at AREA_NAMES ({ON name, OFF name, index}).

navi.bin: "WNV1", u32 tex_w, tex_h, icon_w, icon_h, n_mesh; then the road texture and the
icon texture (RGBA, rows bottom up as the IGB stores them, so its UVs map them in GL as they
are); then per mesh: i16 area (EAreaId, -1 = always shown), u8 on, u8 blend, u32 n_vert,
u32 n_index, the vertices (f32 pos[3], f32 uv[2], u8 rgba[4]) and u16 triangle indices.
The icon quad is +-ICON_HALF display units in x and z with ICON_RED's UVs (hud.c)."""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stage"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene  # noqa: E402
import tex  # noqa: E402

AREA_NAMES = 0x93d9f84
AREAS = 75
VERTEX = np.dtype([("pos", "<f4", 3), ("uv", "<f4", 2), ("rgba", "u1", 4)])


class Elf:
    """Read file-backed addresses from a little-endian ELF32; never execute it."""

    def __init__(self, path):
        with open(path, "rb") as f:
            self.d = f.read()
        if len(self.d) < 52 or self.d[:7] != b"\x7fELF\x01\x01\x01":
            raise ValueError("expected little-endian ELF32")
        phoff = struct.unpack_from("<I", self.d, 28)[0]
        entsize, count = struct.unpack_from("<HH", self.d, 42)
        if entsize < 32 or phoff > len(self.d) or count > (len(self.d) - phoff) // entsize:
            raise ValueError("invalid ELF program header table")
        self.segs = []
        for i in range(count):
            typ, off, va, _, size, memsize, _, _ = struct.unpack_from("<8I", self.d, phoff + i * entsize)
            if typ == 1:
                if size > memsize or off > len(self.d) or size > len(self.d) - off or va + size > 0x100000000:
                    raise ValueError("invalid ELF load segment")
                self.segs.append((va, off, size))

    def _range(self, va, size):
        matches = [(o + va - v, o + n) for v, o, n in self.segs
                   if v <= va and va + size <= v + n and va < v + n]
        if len(matches) != 1:
            raise ValueError("unmapped or ambiguous ELF address: %#x" % va)
        return matches[0]

    def u32(self, va):
        off, _ = self._range(va, 4)
        return struct.unpack_from("<I", self.d, off)[0]

    def cstr(self, va):
        off, end = self._range(va, 1)
        terminator = self.d.find(b"\0", off, end)
        if terminator < 0:
            raise ValueError("unterminated ELF string at %#x" % va)
        return self.d[off:terminator].decode("latin1")


def image_rgba(f, img, bgr=False):
    """An igImage's pixels as RGBA bytes in the IGB's row order (bottom up); bgr: the image
    holds blue where red belongs and the other way round (car_icon's ICON_RED is blue)."""
    im = tex.to_pil(img, f.ref(img[13]).mem).convert("RGBA")
    if bgr:
        r, g, b, a = im.split()
        im = Image.merge("RGBA", (b, g, r, a))
    return im.size, im.tobytes()


def pack(data_dir, main, out, navi="SkNavi.igb"):
    elf = Elf(main)
    area_of = {}
    for a in range(1, AREAS):
        on, off = elf.u32(AREA_NAMES + 12 * a), elf.u32(AREA_NAMES + 12 * a + 4)
        for ptr, lit in ((on, 1), (off, 0)):
            if ptr and elf.cstr(ptr):
                area_of.setdefault(elf.cstr(ptr), (a, lit))
    f, meshes = scene.meshes(f"{data_dir}/minimap/{navi}")
    road = None
    parts = []
    for m in meshes:
        name = m["path"][-1] if m["path"] else ""
        area, on = area_of.get(name, (-1, 0))
        v = m["verts"]
        vert = np.zeros(len(v["pos"]), VERTEX)
        vert["pos"] = (np.c_[v["pos"], np.ones(len(v["pos"]), np.float32)] @ m["matrix"])[:, :3]
        vert["uv"] = v["uv"][:, :2]
        vert["rgba"] = v["color"][:, [2, 1, 0, 3]] if "color" in v else 255  # BGRA -> RGBA
        if road is None:
            road = image_rgba(f, m["image"])
        parts.append((area, on, 1 if m["state"]["blend"] else 0, vert, m["tris"].astype("<u2")))
    fi, icons = scene.meshes(f"{data_dir}/effect/car_icon.igb")
    icon = image_rgba(fi, icons[0]["image"], bgr=True)
    with open(out, "wb") as o:
        o.write(b"WNV1" + struct.pack("<5I", *road[0], *icon[0], len(parts)))
        o.write(road[1] + icon[1])
        for area, on, blend, vert, tris in parts:
            o.write(struct.pack("<hBBII", area, on, blend, len(vert), tris.size))
            o.write(vert.tobytes() + tris.tobytes())
    print("%s: %d meshes, %d areas, %.1f KB" % (os.path.basename(out), len(parts), len({p[0] for p in parts}), os.path.getsize(out) / 1e3))


if __name__ == "__main__":
    if len(sys.argv) > 5:
        pack(sys.argv[1], sys.argv[2], f"{sys.argv[3]}/{sys.argv[5]}", sys.argv[4])
    else:
        pack(sys.argv[1], sys.argv[2], f"{sys.argv[3]}/navi.bin")
