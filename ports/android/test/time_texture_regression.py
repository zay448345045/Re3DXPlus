#!/usr/bin/env python3
"""Usage: python3 test/time_texture_regression.py ORIGINAL.png menu.bin"""
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib
from PIL import Image

if len(sys.argv) != 3:
    raise SystemExit(__doc__)
png, menu = map(Path, sys.argv[1:])
root = Path(__file__).resolve().parent.parent
if not png.is_file() or not menu.is_file():
    raise SystemExit("missing PNG or menu.bin; no files modified")
im = Image.open(png).convert("RGBA")
assert im.size == (64, 32)
source = im.tobytes()
assert hashlib.sha256(source).hexdigest() == "ddd1d2f1ef8ff320e88bbc52daf92a43723f5ddfebe49416bc263c2641340224"
with menu.open("rb") as f:
    assert f.read(4) == b"WMN3"
    n, = struct.unpack("<I", f.read(4))
    matches = []
    for i in range(n):
        ident, w, h, size = struct.unpack("<iHHI", f.read(12))
        raw = f.read(size or w*h*4)
        if ident == 1573:
            raw = zlib.decompress(raw) if size else raw
            matches.append((i, w, h, raw))
assert len(matches) == 1
index, w, h, packed = matches[0]
assert (w, h, len(packed)) == (64, 32, len(source))
assert any(0 < source[i] < 255 for i in range(3, len(source), 4)), "no semitransparent source pixels"
print("sprite index", index, "source alpha differences", sum(source[i] != packed[i] for i in range(3,len(source),4)))
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "source.rgba").write_bytes(source)
    (td / "packed.rgba").write_bytes(packed)
    exe = td / "test"
    subprocess.run(["clang", "-U__APPLE__", "-I" + str(root / "test"), "-ffunction-sections", "-fdata-sections", str(root / "test/time_texture_upload_test.c"), "-Wl,-dead_strip", "-lz", "-o", str(exe)], check=True)
    subprocess.run([str(exe), str(td / "source.rgba"), str(td / "packed.rgba")], check=True)
