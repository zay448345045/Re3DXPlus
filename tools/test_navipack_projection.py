"""Offline minimap projection check with original road assets; never runs the game.

usage: python test_navipack_projection.py <arcade-data-dir> <directory-containing-navi-files>
The observed test points are road vertices, not recorded race-start telemetry.
"""
import struct
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ports/ipad/tools/stage"))
import scene

VERTEX = np.dtype([("pos", "<f4", 3), ("uv", "<f4", 2), ("rgba", "u1", 4)])
CASES = (
    ("oosaka", "ok_area03_michi_m.igb", (7488.9067, -3305.6367), 5),
    ("nagoya", "nk_area01_michi_m.igb", (-4215.29, -11032.27), 64),
)


def check(data, packed, city, ground_name, point, active):
    _, road = scene.meshes(str(data / city / "daytime" / ground_name))
    ground = np.concatenate([(np.c_[m["verts"]["pos"], np.ones(len(m["verts"]["pos"]), np.float32)] @ m["matrix"])[:, (0, 2)] for m in road])
    distance = float(np.linalg.norm(ground - point, axis=1).min())
    assert distance < 2.0, (city, "ground point not found", distance)
    blob = (packed / ("navi_" + city + ".bin")).read_bytes()
    assert blob[:4] == b"WNV1"
    w, h, iw, ih, count = struct.unpack_from("<5I", blob, 4)
    tex = np.frombuffer(blob, np.uint8, w * h * 4, 24).reshape(-1, 4)
    assert np.all(tex[:, 3] == 255), city
    off = 24 + 4 * (w * h + iw * ih)
    visible = 0
    for _ in range(count):
        area, on, blend, nv, ni = struct.unpack_from("<hBBII", blob, off)
        off += 12
        vertices = np.frombuffer(blob, VERTEX, nv, off)
        off += nv * 24
        index = np.frombuffer(blob, "<u2", ni, off).reshape(-1, 3)
        off += ni * 2
        # r->next_area is assumed equal to the current area; 64 normalizes to 62.
        selected = 62 if 62 <= active <= 69 else active
        if area >= 0 and (area == selected) != bool(on):
            continue
        center = vertices["pos"][index].mean(axis=1)
        dx, dz = center[:, 0] - point[0], center[:, 2] - point[1]
        # angle=0: up=(0,0,-1); ortho x=-2000..2000, y=-1200..2800.
        in_view = (np.abs(dx) <= 2000) & (dz >= -2800) & (dz <= 1200)
        in_depth = (center[:, 1] <= 1995) & (center[:, 1] >= -8000)
        visible += int(np.count_nonzero(in_view & in_depth))
    assert off == len(blob) and visible > 0, (city, visible)
    print(city, "ground distance", round(distance, 4), "visible triangle centers", visible)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    for args in CASES:
        check(Path(sys.argv[1]), Path(sys.argv[2]), *args)
