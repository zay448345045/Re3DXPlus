#!/usr/bin/env python3
"""Generate a header from a user-supplied 64x32 PNG.

Usage: python3 time_texture.py INPUT.png OUTPUT.h
Requires Pillow. The output must not already exist.
"""
import argparse
import sys
import zlib
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png", type=Path, help="local 64x32 PNG supplied by the user")
    parser.add_argument("header", type=Path, help="new output header (never overwritten)")
    args = parser.parse_args()
    try:
        with Image.open(args.png) as image:
            if image.format != "PNG" or image.size != (64, 32):
                raise ValueError("input must be a 64x32 PNG")
            rgba = image.convert("RGBA").tobytes()
        compressed = zlib.compress(rgba, 9)
        rows = ["  " + ", ".join(f"0x{value:02x}" for value in compressed[i:i + 12]) + ",\n"
                for i in range(0, len(compressed), 12)]
        header = (
            "/* Generated from a user-supplied 64x32 PNG. */\n"
            "#ifndef WMMT_TIME_TEXTURE_H\n#define WMMT_TIME_TEXTURE_H\n"
            "#include <string.h>\n#include <zlib.h>\n"
            "static const unsigned char time_texture_z[] = {\n"
            + "".join(rows) +
            "};\n"
            "/* Decode separately so failure leaves the loaded texture untouched. */\n"
            "static void time_texture_fix(int id, int width, int height, unsigned char *pixels) {\n"
            "  if (id != 1573 || width != 64 || height != 32 || !pixels) return;\n"
            "  unsigned char decoded[64 * 32 * 4];\n"
            "  uLongf length = sizeof decoded;\n"
            "  if (uncompress(decoded, &length, time_texture_z, sizeof time_texture_z) == Z_OK && length == sizeof decoded)\n"
            "    memcpy(pixels, decoded, sizeof decoded);\n"
            "}\n#endif\n"
        )
        with args.header.open("x", encoding="ascii", newline="\n") as output:
            output.write(header)
    except (OSError, ValueError) as error:
        print(f"{parser.prog}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
