#!/usr/bin/env python3
"""Generate or verify the embedded 64x64 RGBA sprites. Requires Pillow.
Usage: python3 tools/racing_lamp_data.py /path/to/data/sprite [--verify]
"""
from pathlib import Path
import hashlib, re, sys, zlib
from PIL import Image
root = Path(sys.argv[1]); target = Path(__file__).resolve().parents[1] / "src/racing_lamp_data.h"
names = ("off_m", "off_n", "on_m", "on_n")
items = []
for name in names:
    im = Image.open(root / ("racing_rev_" + name + ".png")).convert("RGBA")
    assert im.size == (64, 64)
    raw = im.tobytes()
    print(name, hashlib.sha256(raw).hexdigest())
    items.append((name, raw))
if len(sys.argv) > 2 and sys.argv[2] == "--verify":
    text = target.read_text()
    for name, raw in items:
        m = re.search(r"lamp_" + name + r"\[\] = \{(.*?)\};", text, re.S)
        assert m
        data = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-f]{2})", m.group(1)))
        assert zlib.decompress(data) == raw
    print("All embedded sprites match decoded source RGBA byte-for-byte")
else:
    out = ["/* Original racing lamp RGBA, zlib compressed. */\n#ifndef RACING_LAMP_DATA_H\n#define RACING_LAMP_DATA_H\n"]
    for name, raw in items:
        data = zlib.compress(raw, 9)
        out.append("static const unsigned char lamp_" + name + "[] = {\n")
        out.extend("  " + ",".join("0x%02x" % b for b in data[i:i+16]) + ",\n" for i in range(0, len(data), 16))
        out.append("};\n")
    out.append("#endif\n")
    target.write_text("".join(out))
