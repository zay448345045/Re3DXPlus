"""The course selects' 3D miniature of Tokyo (clMiniatureCourse), for data/minicourse.wpk
and src/minicourse.h.

clThread_6_2_CourseSelect::run (the time attack's) and clThread_7_1_CourseSelect::run (the
10-in-a-row's) hand clMiniatureCourse::init a table of stMiniatureCourseData (0x68 bytes a
course: the time attack's 12 at 0x93e3bc0, the 10-in-a-row's 10 at 0x940ccc0, the versus area
vote's 9 at 0x93fa400 (clseqJoCourseSelectThread::run; card 0 omakase): +0 the map,
+4 the course (the roads and their shadow), +8 the course's marks (macula), +0xc its
gradation (an LED strip along the route whose texture runs: an igTransformSequence on the
texture matrix, u 0 -> 1 in 3 s), +0x10 the run light (a glow riding the route: a
sequence of the node's place, 181 keys in 3 s), +0x14 the camera set, +0x18 / +0x1c the
names of the camera's and its aim's transforms there (data/menu3d/course/ + the name).
Only Tokyo's ("sk") cards show it (mapChange: the other cities show a picture instead).

The pack: one object per IGB (out.names), the run light's quad in its own frame (the
renderer places it at the sequence's key, facing the camera). The header: by card, the
objects of its marks, gradation and run light, its camera and aim, and the sequences
sampled at 60 Hz.

usage: pack_mini.py <arcade root (has main, data/)> out.wpk out.h
"""
import os
import struct
import sys

import numpy as np

import pack
import scene
from igb import IGB

TABLES = (("TA", 0x93e3bc0, 12), ("TEN", 0x940ccc0, 10), ("VS", 0x93fa400, 9))
TOKYO_MAP = "sk/cs_sk_map.igb"  # the 3D Tokyo: the cards on it (TA 0-5, 10, 11; ten 0-5) get the miniature,
# the others (Nagoya, Osaka, Fukuoka, Hakone) mapChange's 2D city picture
FRAMES = 180  # 3 s at 60 Hz


class Elf:
    def __init__(self, path):
        self.d = open(path, "rb").read()
        ph, n = struct.unpack_from("<I", self.d, 0x1c)[0], struct.unpack_from("<H", self.d, 0x2c)[0]
        self.segs = [struct.unpack_from("<8I", self.d, ph + 32 * i) for i in range(n)]

    def read(self, a, k):
        for t, off, va, pa, fs, ms, fl, al in self.segs:
            if t == 1 and va <= a < va + fs:
                return self.d[off + a - va:off + a - va + k]
        return None

    def string(self, a):
        b = self.read(a, 128) if a else None
        return b.split(b"\0")[0].decode("latin1") if b else ""


def course_data(elf, base, n):
    out = []
    for i in range(n):
        w = struct.unpack("<26I", elf.read(base + i * 0x68, 0x68))
        out.append([elf.string(w[k]) for k in range(8)])
    return out


def sequences(path):
    """name of each igTransform with an igTransformSequence1_5 -> (times s, T, R)"""
    f = IGB(path)

    def lst(o, fmt, k):
        n = o[2].i32
        m = f.ref(o[4]).mem
        return np.array([struct.unpack_from("<" + fmt, m, i * k) for i in range(n)], np.float64)

    out = {}
    for o in f.objects:
        if o is None or o.type != "igTransform" or o[11] is None:
            continue
        sq = f.ref(o[11])
        if sq is None or sq.type != "igTransformSequence1_5":
            continue
        t = lst(f.ref(sq[11]), "q", 8)[:, 0] / 1e9
        out[f.string(o[2]) if o[2] is not None else ""] = (t, lst(f.ref(sq[2]), "3f", 12), lst(f.ref(sq[3]), "4f", 16))
    return out


def sample(t, v):
    """v at 60 Hz over 3 s (looped: the keys run 0..3 s), linear between keys"""
    s = np.arange(FRAMES) / 60.0
    return np.stack([np.interp(s, t, v[:, k]) for k in range(v.shape[1])], axis=1)


def camera(path, name):
    f = IGB(path)
    for o in f.of_type("igTransform"):
        if o[2] is not None and f.string(o[2]) == name:
            return np.frombuffer(o[8].raw, "<f4").reshape(4, 4)[3, :3]
    raise KeyError(name)


def main():
    root, out_wpk, out_h = sys.argv[1:4]
    elf = Elf(os.path.join(root, "main"))
    cdir = os.path.join(root, "data/menu3d/course")
    tables = [(tag, course_data(elf, base, n)) for tag, base, n in TABLES]
    files = []  # object k: an IGB under data/menu3d/course
    for _, rows in tables:
        for r in rows:
            if r[0] != TOKYO_MAP:
                continue
            for f in (r[0], r[1], r[2], r[3], r[4]):
                if f not in files:
                    files.append(f)
    runlights = {r[4] for _, rows in tables for r in rows if r[0] == TOKYO_MAP}

    real_meshes = scene.meshes

    def meshes(path):
        f, ms = real_meshes(path)
        if os.path.relpath(path, cdir) in runlights:  # in its own frame: placed by its sequence
            # its texture is the igInterpretedShader's DiffuseTexture, out of scene.meshes' sight
            attr = f.of_type("igTextureAttr")
            for m in ms:
                m["matrix"] = np.eye(4, dtype=np.float32)
                if m["image"] is None and attr:
                    m["image"] = f.ref(attr[0][12])
        return f, ms

    scene.meshes = meshes
    pack.OBJECTS = -1  # groups 3 + k are given here, not taken from "ROOT_" groups
    paths = [(3 + k, os.path.join(cdir, f)) for k, f in enumerate(files)]
    textures, order, ms, _ = pack.collect(paths, None, (1024, 1024, 1024))
    # the run light glows (the arcade's shader adds it): additive
    run_groups = {3 + files.index(f) for f in runlights}
    ms = [(g, n, fl | (2 if g in run_groups else 0), v, t, m) for g, n, fl, v, t, m in ms]
    pack.write(out_wpk, textures, order, pack.split_by_chunk(ms, 0), 0)
    with open(out_wpk.rsplit(".", 1)[0] + ".names", "w") as fp:
        fp.write("".join(f + "\n" for f in files))

    with open(out_h, "w") as h:
        h.write("/* Generated by tools/stage/pack_mini.py from the arcade's main and data/menu3d/course: do not edit. */\n")
        h.write("#ifndef MINICOURSE_H\n#define MINICOURSE_H\n\n")
        h.write("/* data/minicourse.wpk's objects (data/minicourse.names) */\n")
        h.write("enum { MINI_MAP = %d, MINI_COURSE = %d, MINI_OBJECTS = %d };\n" % (
            files.index(tables[0][1][0][0]), files.index(tables[0][1][0][1]), len(files)))
        h.write("#define MINI_FRAMES %d /* the sequences' 3 s at 60 Hz */\n" % FRAMES)
        h.write("typedef struct {\n  unsigned char on;                /* a card on the 3D Tokyo (else all 0) */\n"
                "  unsigned char macula, gradation, runlight; /* objects */\n"
                "  float eye[3], at[3];\n  float uv[MINI_FRAMES];         /* the gradation's texture u */\n"
                "  float run[MINI_FRAMES][3];     /* the run light's place */\n} mini_course;\n\n")
        for tag, rows in tables:
            h.write("/* stMiniatureCourseData %s */\n" % {"TA": "0x93e3bc0, the time attack's",
                                                       "TEN": "0x940ccc0, the 10-in-a-row's",
                                                       "VS": "0x93fa400, the versus area vote's"}[tag])
            h.write("#define MINI_%s_CARDS %d\n" % (tag, len(rows)))
            h.write("static const mini_course MINI_%s[MINI_%s_CARDS] = {\n" % (tag, tag))
            for k, r in enumerate(rows):
                if r[0] != TOKYO_MAP:
                    h.write("  { 0 }, /* card %d: %s, the city picture */\n" % (k, r[0]))
                    continue
                cams = os.path.join(cdir, r[5])
                eye, at = camera(cams, r[6]), camera(cams, r[7])
                gra = list(sequences(os.path.join(cdir, r[3])).values())[0]
                run = list(sequences(os.path.join(cdir, r[4])).values())[0]
                uv = sample(gra[0], gra[1][:, :1])[:, 0]
                pos = sample(run[0], run[1])
                h.write("  { 1, %d, %d, %d, /* card %d: %s %s %s */\n" % (files.index(r[2]), files.index(r[3]), files.index(r[4]), k,
                                                            r[2], r[3], r[4]))
                h.write("    { %.4ff, %.4ff, %.4ff }, { %.4ff, %.4ff, %.4ff }, /* %s, %s */\n" % (*eye, *at, r[6], r[7]))
                h.write("    {" + ",".join(" %.4ff" % u for u in uv) + " },\n")
                h.write("    {" + ",".join(" { %.3ff, %.3ff, %.3ff }" % tuple(p) for p in pos) + " } },\n")
            h.write("};\n\n")
        h.write("#endif\n")


if __name__ == "__main__":
    main()
