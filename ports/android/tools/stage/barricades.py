"""Extract the guardrail barricades that close off junctions from the arcade binary.

clGraphicFrame::setBarricade(int id) (0x089521b4) reads a table at 0x094209e0 of
(entry pointer, count) per id and puts data/stage_common/gurdrail_*.igb at every entry:
  i32 model (0 daytime, 1 night)  f32 scale_x  f32 pos[3]  f32 rot_x rot_y rot_z
clRaceThread::init calls it with id 1-3; the three lists are identical (126 pieces,
three per closed junction, Tokyo map coordinates).

usage: barricades.py main_binary > barricades.txt   (lines for pack.py --place)
"""
import struct
import sys

TABLE = 0x094209e0


def main():
    buf = open(sys.argv[1], "rb").read()
    shoff, = struct.unpack_from("<I", buf, 0x20)
    shentsize, shnum = struct.unpack_from("<HH", buf, 0x2e)
    secs = [struct.unpack_from("<6I", buf, shoff + i * shentsize)[3:6] for i in range(shnum)]

    def read(addr, n):
        for a, off, size in secs:
            if a and a <= addr < a + size:
                return buf[off + addr - a:off + addr - a + n]
        raise ValueError("address %#x not in the file" % addr)

    ptr, count = struct.unpack("<2I", read(TABLE + 8, 8))  # id 1
    print("# scale_x x y z rot_x rot_y rot_z  (from clGraphicFrame::setBarricade, %d pieces)" % count)
    for j in range(count):
        _, *v = struct.unpack("<i7f", read(ptr + 32 * j, 32))
        print(" ".join("%.4f" % x for x in v))


if __name__ == "__main__":
    main()
