#!/usr/bin/env python3
"""Asset-free regression for safe WCP1 finish repair."""
import importlib.util
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from PIL import Image, ImageDraw

spec = importlib.util.spec_from_file_location("finish_pack", Path(__file__).resolve().parents[1] / "tools" / "finish_pack.py")
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


def fixtures():
    glyphs = []
    for i, sid in enumerate(f.MENU_DIGITS):
        im = Image.new("RGBA", (32, 32))
        ImageDraw.Draw(im).rectangle((2+i, 4, 3+i, 25), fill=(240,240,240,255))
        glyphs.append(f.encode_image(sid, im))
    menu = b"WMN3" + struct.pack("<I", len(glyphs)) + b"".join(glyphs) + struct.pack("<I", 0)
    blank = Image.new("RGBA", (44, 44), (1,2,3,4))
    sprites = [f.encode_image(i, blank) for i in f.DIGITS]
    metre = Image.new("RGBA", (44,44))
    d = ImageDraw.Draw(metre)
    d.rectangle((0,0,43,43), outline=(230,0,0,255))
    d.text((15,15), "m", fill=(240,240,240,255))
    sprites += [f.encode_image(f.METRE, metre), f.encode_image(17, blank)]
    anim = struct.pack("<48sII", b"example", 1, 1) + struct.pack("<II", 0, 1) + f.RECORD.pack(17, 0, *([0.0]*6), *([0]*8))
    card = struct.pack("<4sIII", b"WCP1", 1, len(sprites), 1) + b"".join(sprites) + anim
    return menu, card


class RepairTest(unittest.TestCase):
    def test_repair_and_unchanged_records(self):
        menu, card = fixtures()
        with tempfile.TemporaryDirectory() as tmp:
            m, src, dst = (Path(tmp)/n for n in ("menu", "input", "output"))
            m.write_bytes(menu); src.write_bytes(card)
            f.repair(m, src, dst)
            before = f.bank(card, True); after = f.bank(dst.read_bytes(), True)
            self.assertEqual(card[:16], dst.read_bytes()[:16])
            self.assertEqual(before[3], after[3]); self.assertEqual(before[2][-1], after[2][-1])
            self.assertEqual(len(set(f.image_record(r)[1].tobytes() for r in after[2][:10])), 10)
            old = f.image_record(before[2][10])[1]; new = f.image_record(after[2][10])[1]
            for y in range(44):
                for x in range(44):
                    p, q = old.getpixel((x,y)), new.getpixel((x,y))
                    if x in (0,43) or y in (0,43): self.assertEqual(q, (0,0,0,0))
                    else: self.assertEqual(p,q)
            with self.assertRaises(FileExistsError): f.repair(m, src, dst)
            self.assertEqual(src.read_bytes(), card)

    def test_bad_zlib_and_missing_ids(self):
        menu, card = fixtures(); corrupt = bytearray(card); corrupt[28] ^= 255
        with self.assertRaises((ValueError, zlib.error)): f.bank(bytes(corrupt), True)
        _, _, glyphs, _ = f.bank(menu, False); _, _, sprites, _ = f.bank(card, True)
        with self.assertRaises(ValueError): f.replacements(glyphs[:-1], sprites)
        with self.assertRaises(ValueError): f.replacements(glyphs, sprites[:-2] + sprites[-1:])
        corrupt = bytearray(card); corrupt[0] ^= 1
        with self.assertRaises(ValueError): f.bank(bytes(corrupt), True)


if __name__ == "__main__": unittest.main()
