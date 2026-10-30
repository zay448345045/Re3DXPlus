"""Minimal reader for Alchemy IGB (v8, little-endian) as used by WMMT3DX+.

Layout follows the layout documented by the community `alchemy` project
(header of 12 u32, name pool, meta-field buffer, alignment buffer,
meta-object buffer, external/pool-name buffers, entry buffer, index buffer,
object buffer, memory buffer).
"""
import struct
import sys
from collections import Counter

MAGIC = 0xFADA


class Field:
    __slots__ = ("type", "slot", "size", "raw")

    def __init__(self, ftype, slot, size, raw):
        self.type, self.slot, self.size, self.raw = ftype, slot, size, raw

    @property
    def i32(self):
        return struct.unpack_from("<i", self.raw.ljust(4, b"\0"))[0]

    @property
    def f32(self):
        return struct.unpack_from("<f", self.raw)[0]


class Obj:
    def __init__(self, index, type_name):
        self.index = index
        self.type = type_name
        self.fields = {}  # slot -> Field
        self.mem = None   # bytes for memory blocks

    def __getitem__(self, slot):
        return self.fields.get(slot)


class IGB:
    def __init__(self, path):
        with open(path, "rb") as fp:
            self.buf = buf = fp.read()
        h = struct.unpack_from("<12I", buf, 0)
        if h[10] != MAGIC:
            raise ValueError("not a little-endian IGB")
        flags = h[11]
        self.version = flags & 0xFFFF
        has_info = (flags >> 31) & 1
        has_external = (flags >> 30) & 1
        has_pool_names = (flags >> 28) & 1
        entry_buf, entry_count, mo_buf, mo_count, obj_buf = h[0], h[1], h[2], h[3], h[4]
        mf_buf, mf_count = h[8], h[9]
        so = 1 if self.version <= 5 else 0
        self.slot_offset = so

        pos = 48
        self.names = []
        if self.version >= 8:
            size, count = struct.unpack_from("<2I", buf, pos)
            p = pos + 8
            for _ in range(count):
                (n,) = struct.unpack_from("<I", buf, p)
                self.names.append(buf[p + 4:p + 4 + n].split(b"\0")[0].decode("latin1"))
                p += 4 + n
            pos += size

        # meta fields
        self.meta_fields = []
        dyn = pos + mf_count * 12
        for i in range(mf_count):
            (n,) = struct.unpack_from("<I", buf, pos + i * 12)
            self.meta_fields.append(_short(buf[dyn:dyn + n].split(b"\0")[0].decode("latin1")))
            dyn += n
        pos += mf_buf

        (align,) = struct.unpack_from("<I", buf, pos)
        pos += align

        # meta objects
        self.meta_objs = []
        dyn = pos + mo_count * 24
        for i in range(mo_count):
            n, _, _, nf, parent, _ = struct.unpack_from("<IIIIiI", buf, pos + i * 24)
            name = buf[dyn:dyn + n].split(b"\0")[0].decode("latin1")
            dyn += n
            fields = [struct.unpack_from("<3H", buf, dyn + 6 * j) for j in range(nf)]
            dyn += 6 * nf
            self.meta_objs.append((name, parent, fields))
        pos += mo_buf

        self.external_dirs = []
        if has_external:
            size, count = struct.unpack_from("<2I", buf, pos)
            p = pos + 8
            for _ in range(count):
                (n,) = struct.unpack_from("<I", buf, p)
                self.external_dirs.append(buf[p + 4:p + 4 + n].split(b"\0")[0].decode("latin1"))
                p += 4 + n
            pos += size
        if has_pool_names:
            pos += struct.unpack_from("<I", buf, pos)[0]

        # directory entries
        entries = []
        p = pos
        for _ in range(entry_count):
            etype, esize = struct.unpack_from("<2I", buf, p)
            entries.append((etype, p + 8, esize))
            p += esize
        ip = pos + entry_buf
        idx_size, num_idx = struct.unpack_from("<2I", buf, ip)
        index_map = struct.unpack_from("<%dH" % num_idx, buf, ip + 8)
        ip += idx_size
        if self.version >= 6 and has_info:
            ip += 4

        is_mem = [False] * num_idx
        is_ext = [False] * num_idx
        self.externals = {}
        mem_size = [0] * num_idx
        mem_type = [0] * num_idx
        for i, ei in enumerate(index_map):
            etype, epos, esize = entries[ei]
            name, _, fields = self.meta_objs[etype]
            if name.startswith("igExternal"):
                is_ext[i] = True
                vals = {}
                d = 0
                for ftype, slot, size in fields:
                    if d + size > esize:
                        break
                    vals[slot] = Field(self.meta_fields[ftype], slot, size, buf[epos + d:epos + d + size])
                    d += (size + 3) & ~3
                self.externals[i] = (name, vals)
                continue
            if name != "igMemoryDirEntry":
                continue
            is_mem[i] = True
            d = 0
            for _, slot, size in fields:
                if d + 4 > esize:
                    break
                (v,) = struct.unpack_from("<I", buf, epos + d)
                if slot == 7 + so:
                    mem_size[i] = v
                elif slot == 10 + so:
                    mem_type[i] = v
                d += (size + 3) & ~3

        self.objects = [None] * num_idx
        op = ip
        for i in range(num_idx):
            if is_mem[i] or is_ext[i]:
                continue
            otype, osize = struct.unpack_from("<2I", buf, op)
            name, _, fields = self.meta_objs[otype]
            o = Obj(i, name)
            d = op + 8
            end = op + osize
            for ftype, slot, size in fields:
                if d + 4 > end:
                    break
                o.fields[slot] = Field(self.meta_fields[ftype], slot, size, buf[d:d + size])
                d += (size + 3) & ~3
            self.objects[i] = o
            op += osize

        mp = ip + obj_buf
        for i in range(num_idx):
            if not is_mem[i]:
                continue
            n = mem_size[i]
            o = Obj(i, self.meta_objs[mem_type[i]][0] if mem_type[i] < mo_count else "igMemoryBlock")
            o.mem = buf[mp:mp + n]
            self.objects[i] = o
            mp += (n + 3) & ~3

    def ref(self, field):
        if field is None:
            return None
        i = field.i32
        return self.objects[i] if 0 <= i < len(self.objects) else None

    def string(self, field):
        if field is None:
            return None
        i = field.i32
        return self.names[i] if 0 <= i < len(self.names) else None

    def of_type(self, name):
        return [o for o in self.objects if o is not None and o.mem is None and o.type == name]

    def images(self):
        so = self.slot_offset
        out = []
        for o in self.of_type("igImage"):
            data = self.ref(o[13 + so])
            out.append({
                "name": self.string(o[22 + so]),
                "width": o[2 + so].i32,
                "height": o[3 + so].i32,
                "format": o[11 + so].i32,
                "size": o[12 + so].i32 if o[12 + so] else 0,
                "data": data.mem if data is not None else None,
            })
        return out


def _short(name):
    if name.startswith("ig"):
        name = name[2:]
    if name.endswith("MetaField"):
        name = name[:-9]
    return name


if __name__ == "__main__":
    f = IGB(sys.argv[1])
    print("version", f.version, "objects", len(f.objects))
    print(Counter(o.type for o in f.objects if o is not None).most_common(40))
    for im in f.images():
        print(im["name"], im["width"], im["height"], "fmt", im["format"],
              "bytes", len(im["data"]) if im["data"] else None)
