"""Read the arcade's car select data out of `main` by running its own lookup functions
(under the unicorn x86 emulator) and write tools/cars.json and src/cardb.h.

usage: cardb.py <main> <arcade data/car dir>

- get_car_from_maker(maker, -1) (0x88ec0e0): the cars on each maker's page (car ids index
  the car table at 0x9417720: {folder name, id}).
- nsCarParts' table at 0x9419ea0 {car, first model, last model, ...}: the models of a car.
  A model is one paint: the colour select steps through them (a few belong to another
  car id, e.g. the Evo IV RS is the GSR's white).
- GetCarData(model) (0x8568754) +0x20: the car's stock horsepower (GetHorsePower at power 0).
- get_car_model_data(model) (0x88dc0c8): +0 and +4 the car's name in two lines (the card's
  Type, clSeqCardDisp1), +8 colour name (UTF-8), +0xc colour swatch,
  +0x14 car logo, +0x18 drive layout, +0x1c gears (menu_p_carsel_speed_4..6), +0x24 the
  background logo, +0x2c the car's name plate.
- nsCarParts::CarIDGetFromModelID (0x893dd48), BNGCarIDGetFromCarID (0x893cd6c): the car of
  a model and its ECarType for yt::CSetting::GetSettingPt.
- the hidden cars (get_car_from_maker(maker, k), k 0..7: the maker's list with one car swapped
  for the k-th hidden one) as a seventh maker, HIDDEN, after the six (the port's own page,
  menu.c's "Maybe......Hidden Cars?"); their models after the others' in CARDB_PACKS, so the
  others keep their places. The taxis and the driving school car have no colour name: the
  port names their one colour (HIDDEN_COLOR); the Aristo taxi has no ECarType of its own
  (0): it drives as the Aristo.
- car.lua and wheel_list.lua: yt::STireDimension, the hubs (TireLocation.normal), the tyre
  radius (every tyre model is 3.14 across the hub, times TireStatus.scale's scale_zy) and the
  wheel's spoke count, all in mm.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stage"))
import lualite  # noqa: E402

from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP

TYRE_RADIUS = 3.14  # dm, the tyre models' half height
MAKERS = ["GEMBALLA", "MAZDA", "MITSUBISHI", "NISSAN", "SUBARU", "TOYOTA"]
SPEED_GEARS = {3824: 4, 3825: 5, 3826: 6}
HIDDEN_MAKERS = [5, 5, 4, 5, 5, 1, 5, 3]  # the maker each hidden car swaps into
HIDDEN_COLOR = {43: "個人タクシー", 52: "個人タクシー", 51: "教習車"}
HIDDEN_TYPE = {43: 32}  # the Aristo taxi: the Aristo's
# labels the saves tell apart (src/app.c car_by_label) from the cars they share a name with
HIDDEN_LABEL = {50: "TOYOTA HIACE HIGH LIFT", 51: "Mazda Mazdaspeed Atenza [GG3P]（教習車仕様）"}
TEXT_FIRST = 100002  # menupack.py: TEXT_BASE + 2 fixed texts, then the colour names


class Main:
    def __init__(self, path):
        self.b = open(path, "rb").read()
        shoff, = struct.unpack_from("<I", self.b, 0x20)
        se, sn = struct.unpack_from("<HH", self.b, 0x2E)
        self.secs = [struct.unpack_from("<10I", self.b, shoff + i * se) for i in range(sn)]
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        lo = min(s[3] for s in self.secs if s[3]) & ~0xFFF
        hi = (max(s[3] + s[5] for s in self.secs if s[3]) + 0xFFF) & ~0xFFF
        mu.mem_map(lo, hi - lo)
        for s in self.secs:
            if s[3] and s[1] != 8:  # not NOBITS
                mu.mem_write(s[3], self.b[s[4]:s[4] + s[5]])
        mu.mem_map(0x1FF00000, 0x100000)
        mu.mem_map(0x10000000, 0x1000)
        self.w32(0x97ED890, 1)  # teSingleton<clMain>: get_car_from_maker builds it when missing

    def w32(self, a, v):
        self.mu.mem_write(a, struct.pack("<I", v & 0xFFFFFFFF))

    def r32(self, a):
        return struct.unpack("<i", self.mu.mem_read(a, 4))[0]

    def call(self, fn, *args):
        sp = 0x1FFFF000 - 4 * len(args) - 4
        self.w32(sp, 0x10000000)
        for i, a in enumerate(args):
            self.w32(sp + 4 + 4 * i, a)
        self.mu.reg_write(UC_X86_REG_ESP, sp)
        self.mu.emu_start(fn, 0x10000000, count=1000000)
        return struct.unpack("<i", struct.pack("<I", self.mu.reg_read(UC_X86_REG_EAX)))[0]

    def cstr(self, va):
        data = bytes(self.mu.mem_read(va, 256))
        return data[:data.index(b"\0")].decode("utf8")


def main():
    m = Main(sys.argv[1])
    car_dir = sys.argv[2]
    folders = [m.cstr(m.r32(0x9417720 + 8 * k)) for k in range(56)]
    ranges = {}
    for i in range(0x79):
        e = struct.unpack("<5i", m.mu.mem_read(0x9419EA0 + 20 * i, 20))
        ranges.setdefault(e[0], e[1:3])
    texts, packs, makers = [], {}, []
    on_disk = {f.lower(): f for f in os.listdir(car_dir)}
    lists = []
    for mk in range(6):
        p = m.call(0x88EC0E0, mk, -1)
        lists.append([m.r32(p + 4 + 4 * i) for i in range(m.r32(p))])
    hidden = []
    for h, mk in enumerate(HIDDEN_MAKERS):
        p = m.call(0x88EC0E0, mk, h)
        swapped = [m.r32(p + 4 + 4 * i) for i in range(m.r32(p))]
        hidden += [k for k in swapped if k not in lists[mk]]
    for mk, ids in enumerate(lists + [hidden]):
        cars = []
        for k in ids:
            if mk == 6:  # the hidden cars' folders as on disk (toy_UCF10_TAXI is toy_UCF10_taxi)
                folders[k] = on_disk.get(folders[k].lower(), folders[k])
            colors = []
            for model in range(ranges[k][0], ranges[k][1] + 1):
                d = m.call(0x88DC0C8, model)
                v = [m.r32(d + 4 * i) for i in range(12)]
                name = m.cstr(v[2]) or (HIDDEN_COLOR.get(k, "") if mk == 6 else "")
                if not name:  # a hidden car (the Aristo taxi): no colour of its own
                    continue
                car = m.call(0x893DD48, model, 1)
                base = m.call(0x893DD48, model, 0)
                # the car folder that paints this model: the variant's own (the Evo IV RS),
                # else the base car's (the Bathurst FD3S is the FD3S in its first colour)
                owner = car if os.path.isdir(f"{car_dir}/{folders[car]}") else base
                paint = len(packs.setdefault(folders[owner], []))
                ctype = m.call(0x893CD6C, car) or m.call(0x893CD6C, base) or HIDDEN_TYPE[car]
                if name not in texts:
                    texts.append(name)
                packs[folders[owner]].append(model)
                colors.append(dict(model=model, name=name, text=TEXT_FIRST + texts.index(name), swatch=v[3],
                                   folder=folders[owner], paint=paint, type=ctype, gears=SPEED_GEARS[v[7]]))
            d = m.call(0x88DC0C8, ranges[k][0])
            v = [m.r32(d + 4 * i) for i in range(12)]
            hp = m.r32(m.call(0x8568754, ranges[k][0]) + 0x20)
            label = HIDDEN_LABEL.get(k, "%s %s" % (m.cstr(v[0]).strip(), m.cstr(v[1]))) if mk == 6 else \
                "%s %s" % (m.cstr(v[0]).strip(), m.cstr(v[1]))
            cars.append(dict(car=k, folder=folders[k], label=label,
                             lines=[m.cstr(v[0]), m.cstr(v[1])],
                             logo=v[5], drive=v[6], speed=v[7], bglogo=v[9], plate=v[11], hp=hp, colors=colors))
        makers.append(dict(name=(MAKERS + ["HIDDEN"])[mk], cars=cars))
    hidden_packs = [c["folder"] for c in makers[6]["cars"]]
    folder_list = sorted(f for f in packs if f not in hidden_packs) + hidden_packs
    wheel_list = lualite.load(f"{car_dir}/../wheel_list.lua", {"AbsPath": "data/"})["WheelList"]
    tyres = {}
    for f in folder_list:
        car = lualite.load(f"{car_dir}/{f}/car.lua")
        loc, sc = car["TireLocation"]["normal"], car["TireStatus"]["scale"][0]
        wheel = next((w for w in wheel_list if w.get("name") == car["TireStatus"].get("wheel_name")), {})
        tyres[f] = [round(v, 1) for k in (0, 1) for v in (loc[k][0] * 100, TYRE_RADIUS * sc[k]["scale_zy"] * 100,
                                                          loc[k][1] * 100)] + [wheel.get("spoke", wheel.get("soke", 5))]
    out = dict(makers=makers, texts=texts, packs={f: len(packs[f]) for f in folder_list})
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(out, open(f"{here}/cars.json", "w"), ensure_ascii=False, indent=1)

    h = ["/* Generated by tools/cardb.py from the arcade's car select data: do not edit. */",
         "#ifndef CARDB_H", "#define CARDB_H", "",
         "typedef struct {",
         "  int swatch, name;  /* colour swatch sprite, colour name text sprite (menu.bin) */",
         "  int pack, paint;   /* the car model file (CARDB_PACKS) and its paint */",
         "  int type, gears;   /* ECarType for the physics, forward gears */",
         "} cardb_color;", "",
         "typedef struct {",
         "  const char *label;",
         "  int logo, drive, speed, bglogo, plate; /* menu sprites (get_car_model_data) */",
         "  int hp;            /* stock horsepower (GetCarData +0x20) */",
         "  int ncolors;",
         "  cardb_color colors[8];",
         "} cardb_car;", "",
         "#define CARDB_MAKERS 6  /* the maker select's */",
         "#define CARDB_HIDDEN 6  /* the hidden cars' page, after them */",
         "#define CARDB_ALL 7",
         "#define CARDB_MAX_CARS 12", ""]
    h.append("static const char *const CARDB_PACKS[%d] = {" % len(folder_list))
    h += ['  "%s",' % f for f in folder_list]
    h.append("};")
    h.append("#define CARDB_NPACKS %d" % len(folder_list))
    h.append("")
    h.append("/* yt::STireDimension: front hub x, tyre radius, hub z, the same at the rear (mm), spokes */")
    h.append("static const float CARDB_TYRES[CARDB_NPACKS][7] = {")
    h += ["  { %s }, /* %s */" % (", ".join("%.1ff" % v for v in tyres[f]), f) for f in folder_list]
    h.append("};")
    h.append("")
    h.append("static const int CARDB_NCARS[CARDB_ALL] = { %s };" % ", ".join(str(len(mk["cars"])) for mk in makers))
    h.append("static const cardb_car CARDB_CARS[CARDB_ALL][CARDB_MAX_CARS] = {")
    for mk in makers:
        h.append("  { /* %s */" % mk["name"])
        for c in mk["cars"]:
            cols = ", ".join("{ %d, %d, %d, %d, %d, %d }" % (x["swatch"], x["text"], folder_list.index(x["folder"]),
                                                             x["paint"], x["type"], x["gears"]) for x in c["colors"])
            h.append('    { "%s", %d, %d, %d, %d, %d, %d, %d, { %s } },' % (
                c["label"].replace('"', "'"), c["logo"], c["drive"], c["speed"], c["bglogo"], c["plate"], c["hp"],
                len(c["colors"]), cols))
        h.append("  },")
    h.append("};")
    h += ["", "#endif", ""]
    open(f"{here}/../src/cardb.h", "w", encoding="utf8").write("\n".join(h))
    print("%d cars, %d packs, %d colour names" % (sum(len(mk["cars"]) for mk in makers), len(folder_list), len(texts)))


if __name__ == "__main__":
    main()
