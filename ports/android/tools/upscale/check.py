"""check.py pack.wpk...: every ASTC texture's size against its levels' block count"""
import collections
import struct
import sys

BLK = {3: 4, 4: 4, 5: 6, 6: 6, 7: 8, 8: 8}
for p in sys.argv[1:]:
    with open(p, "rb") as f:
        magic, ntex, nch, nb, cs, toff, coff, boff = struct.unpack("<4sIIIfIII", f.read(32))
        f.seek(toff)
        bad, fm, tot = 0, collections.Counter(), 0
        for i in range(ntex):
            name, w, h, fmt, off, size = struct.unpack("<48sHHIII", f.read(64))
            fm[fmt] += 1
            tot += size
            if fmt in BLK:
                b, n, lw, lh = BLK[fmt], 0, w, h
                pot = w & (w - 1) == 0 and h & (h - 1) == 0
                while True:
                    n += ((lw + b - 1) // b) * ((lh + b - 1) // b) * 16
                    if not pot or (lw == 1 and lh == 1):
                        break
                    lw, lh = max(1, lw // 2), max(1, lh // 2)
                bad += n != size
    print("%s: %s %d textures, formats %s, %.1f MB of textures, %d bad" % (p.rsplit("/", 1)[-1], magic.decode(), ntex,
          dict(sorted(fm.items())), tot / 1e6, bad))
