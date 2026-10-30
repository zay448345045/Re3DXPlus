"""The 10-in-a-row's blue line across the road at the rival (clTenRivalLine) for the iPad port.

clTenRivalLine loads effect/rival_line_blue.igb (one additive mesh, x -0.5..0.5 across, y up
from the model's own 0.355 drop) and clStageEffectManager::update poses it each frame from
yt::CSeq::GetInfoTenRivalLine's two road-edge points; its texture, 10rival_line.dds, goes
into lights.wpk (pack_lights.py). This writes the mesh as src/tenline.h: the triangles'
corners with that drop applied, their uv and colour.

usage: pack_tenline.py data_dir out.h
"""
import os
import sys

import numpy as np

import scene

LINE = "effect/rival_line_blue.igb"


def main():
    data, out = sys.argv[1], sys.argv[2]
    _, meshes = scene.meshes(os.path.join(data, LINE))
    rows = []
    for m in meshes:
        v = m["verts"]
        pos = np.c_[np.asarray(v["pos"], dtype=np.float32), np.ones(len(v["pos"]), np.float32)] @ m["matrix"]
        tris = np.asarray(m["tris"]).reshape(-1)
        for i in tris:
            rows.append((pos[i, :3], v["uv"][i], v["color"][i]))
    with open(out, "w") as h:
        h.write("/* tools/stage/pack_tenline.py: %s's mesh, %d triangles (corner: x y z, u v, rgba) */\n"
                % (LINE, len(rows) // 3))
        h.write("#define TENLINE_VERTS %d\n" % len(rows))
        h.write("static const float TENLINE_POS[TENLINE_VERTS][5] = {\n")
        for p, uv, _ in rows:
            h.write("  { %.5ff, %.5ff, %.5ff, %.5ff, %.5ff },\n" % (p[0], p[1], p[2], uv[0], uv[1]))
        h.write("};\nstatic const unsigned char TENLINE_RGBA[TENLINE_VERTS][4] = {\n")
        for _, _, c in rows:
            h.write("  { %d, %d, %d, %d },\n" % tuple(int(x) for x in c))
        h.write("};\n")


if __name__ == "__main__":
    main()
