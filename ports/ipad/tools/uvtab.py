"""Dump the arcade's sprite UV table, the one clSpriteAnime::setImageReplaceUV(template, n)
draws entry n of: the static constructor 0x8a10cc8 (into 0x8a0ab00) fills 0x9803c80 with
276 entries of 36 bytes (+0 sprite id, +4 u0, v0, u1, v1, then w, h, as fractions of 1024).
It runs the constructor under Unicorn (tools/recomp/x86emu.py) and writes tools/uvtab.txt:
one line per entry, "n sprite x0 y0 x1 y1" in 1024ths (menupack.py crops them).

usage: WMMT_MAIN=<main> uvtab.py"""
import os
import struct
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "recomp"))
import x86emu  # noqa: E402

UV_TABLE, UV_N, UV_SIZE = 0x9803c80, 276, 36
e = x86emu.Emu(trace_unknown=False)
e.call(0x8a10cc8)
b = bytes(e.rd(UV_TABLE, UV_N * UV_SIZE))
with open(os.path.join(here, "uvtab.txt"), "w") as f:
    for n in range(UV_N):
        sid, u0, v0, u1, v1 = struct.unpack_from("<I4f", b, n * UV_SIZE)
        f.write("%d %d %d %d %d %d\n" % (n, sid, *(round(u * 1024) for u in (u0, v0, u1, v1))))
