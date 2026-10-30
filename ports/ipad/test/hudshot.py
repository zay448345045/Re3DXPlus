"""Rasterise hudshot.c's log over a 1024x768 background: hudshot.py log bg.png out.png"""
import sys
from PIL import Image, ImageDraw

def main(log, bg, out):
    img = Image.open(bg).convert("RGBA").resize((1024, 768))
    tex, cur_tex, prog, col = {}, 0, 1, (1, 1, 1, 1)
    lines = open(log).read().split("\n")
    i = 0
    S = 2  # supersample
    while i < len(lines):
        t = lines[i].split(); i += 1
        if not t: continue
        if t[0] == "P": prog = int(t[1])
        elif t[0] == "C": col = tuple(float(x) for x in t[1:])
        elif t[0] == "T": cur_tex = int(t[1])
        elif t[0] == "X":
            w, h = int(t[2]), int(t[3])
            tex[int(t[1])] = Image.frombytes("RGBA", (w, h), open(t[4], "rb").read())
        elif t[0] == "D":
            n = int(t[1]); vs = [tuple(map(float, lines[i + k].split())) for k in range(n * 3)]; i += n * 3
            if prog == 1:
                layer = Image.new("RGBA", (1024 * S, 768 * S)); d = ImageDraw.Draw(layer)
                c = tuple(int(255 * max(0, min(1, x))) for x in col)
                for k in range(n):
                    d.polygon([(v[0] * S, v[1] * S) for v in vs[k * 3:k * 3 + 3]], fill=c)
                img.alpha_composite(layer.resize((1024, 768), Image.LANCZOS))
            else:
                # textured quad drawn as a strip of 2 triangles: map with an affine transform
                src = tex[cur_tex]; w, h = src.size
                (x0, y0, u0, v0), (x1, y1, u1, v1), (x2, y2, u2, v2) = vs[0], vs[1], vs[2]
                # solve screen = A*[u*w, v*h, 1]; PIL wants inverse (screen -> source)
                import numpy as np
                U = np.array([[u0 * w, v0 * h, 1], [u1 * w, v1 * h, 1], [u2 * w, v2 * h, 1]])
                X = np.array([[x0, y0], [x1, y1], [x2, y2]])
                A = np.linalg.solve(U, X).T  # 2x3: screen from source
                M = np.vstack([A, [0, 0, 1]]); inv = np.linalg.inv(M)
                layer = src.transform((1024, 768), Image.AFFINE, tuple(inv[:2].flatten()), resample=Image.BICUBIC)
                img.alpha_composite(layer)
    img.convert("RGB").save(out)

main(*sys.argv[1:4])
