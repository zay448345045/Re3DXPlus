"""Pack the arcade race HUD sprites the port uses into hud.bin, and every car's meters
into meters.bin (raw RGBA).

usage: hudpack.py <arcade data/sprite dir> <main> <out dir>

hud.bin: "WHD1", u32 count, then per sprite: name[32], u32 w, u32 h, w*h*4 bytes.
meters.bin (tools/meters.json from meterdb.py, by CARDB_PACKS index like src/meterdb.h):
  "WMT1", u32 cars, u32 sprites; cars x 2 (morning, night) x 9 u16 sprite numbers in
  meterdb's part order (0xffff past the last); sprites x {u32 w, h, file offset}; pixels.
  hud.c loads only the chosen car's."""
import json
import os
import struct
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import menupack  # noqa: E402

SPRITES = [
    # shift indicator: the 4/5/6-speed H-patterns, MT/AT tag, gear balls (red = MT, blue = AT; 0 = blank)
    "cons_p_mis_4", "cons_p_mis_5", "cons_p_mis_6", "cons_p_mis_mt", "cons_p_mis_at"] + \
    [f"cons_p_mis_m{i}" for i in range(7)] + [f"cons_p_mis_a{i}" for i in range(7)] + [
    # the own plate under the meters (cons_g_speed.anm): box, class pill, N, 級, km/h, 馬力/,
    # the handling grades (GetHandling's order: DG, D, B, G, HG)
    "cons_p_speed_waku", "cons_p_rank_waku", "cons_p_rank_N", "cons_p_rank_Q", "cons_p_speed_km",
    "cons_p_bariki_bariki", "cons_p_bariki_DG", "cons_p_bariki_D", "cons_p_bariki_B", "cons_p_bariki_G",
    "cons_p_bariki_HG"]

# The plate's digits live in the atlas cons_p_01.png (the per-sprite PNGs for digits are
# placeholders; the atlas has English labels, so the Japanese ones above come from their
# own PNGs). Rects measured off the atlas: name, x, y, w, h.
ATLAS = "cons_p_01"
ATLAS_CROPS = [(f"big_{i}", 96 + 40 * i, 6, 40, 36) for i in range(10)] + \
              [(f"big_shadow_{i}", 96 + 40 * i, 41, 40, 36) for i in range(10)] + \
              [(f"small_{i}", 96 + 12 * i, 77, 12, 16) for i in range(10)]

# A player without a card: the title (font 0) and the name (font 1), as clSpriteFont draws them.
TEXTS = [("title", 0, "湾岸の新人"),  # 湾岸の新人
         ("name", 1, "ＧＵＥＳＴ")]  # ＧＵＥＳＴ

# The time attack's column (clTimeAttackConsole, clTotalTimeConsole, clSectionTimeConsole,
# clTimeConsole). Its labels "till goal" and "TIME" are sprites of their own; the rest comes
# from the atlas the way the consoles set it, clSpriteAnime::setImageReplaceUV(slot, n):
# entry n of the UV table that the static constructor 0x8a10cc8 builds at 0x9803c80, here
# as pixel rects (x, y, w, h) of cons_p_01.png.
TA_SPRITES = ["cons_p_finish_made", "cons_p_ltime_time"]
_FINISH = [(4, 260), (60, 260), (116, 260), (172, 260), (228, 260), (324, 260), (380, 260), (436, 260), (4, 308), (60, 308)]
TA_CROPS = [("ta_total", 4, 232, 96, 20),        # 21 TOTAL TIME
            ("ta_quote1", 300, 232, 20, 20),     # 32 '
            ("ta_quote2", 320, 232, 20, 20),     # 33 "
            ("ta_section", 244, 136, 92, 16),    # 114 SECTION TIME
            ("ta_pill", 4, 928, 160, 32),        # 182 the red strip under TOTAL TIME
            ("map_waku", 4, 4, 92, 140),         # 75 the minimap's frame
            ("time_extend", 508, 48, 256, 32),   # 211 TIME EXTEND
            ("goal_dot", 156, 308, 40, 48),      # 131
            ("goal_km", 112, 308, 40, 48),       # 132
            ("goal_m", 284, 260, 40, 48)] + \
    [(f"ta_{i}", 100 + 20 * i, 232, 20, 20) for i in range(10)] + \
    [(f"ltime_{i}", 4 + 24 * i, 144, 24, 24) for i in range(10)] + \
    [(f"ltime_s_{i}", 4 + 24 * (i % 5), 168 + 24 * (i // 5), 24, 24) for i in range(10)] + \
    [(f"goal_{i}", x, y, 56, 48) for i, (x, y) in enumerate(_FINISH)] + \
    [(f"map_name_{k}", x, y, 128, 16) for k, (x, y) in enumerate(  # setMapNameTa, by car.c course (card)
        [(256, 384), (256, 400), (384, 528), (384, 544), (384, 592), (384, 608),  # ids 0..4, 6: UV 185 186 202 203 206 207
         # ids 8, 9, 14, 10, 12, 13: UV 209 199 210 208 204 205
         (384, 480), (256, 608), (384, 464), (384, 624), (384, 560), (384, 576)])] + \
    [("rec_your", 240, 104, 104, 16),   # 116 YOUR RECORD (clTimeAttackConsoleInfos)
     ("rec_time", 240, 120, 104, 16),   # 117 RECORD TIME
     ("rec_dash", 328, 168, 16, 20),    # 119 - for each digit of a record not set
     ("buyin_refuse", 508, 80, 104, 36)] + \
    [(f"sign_{k + 1}", x, y, 64, 64) for k, (x, y) in enumerate(  # clSignConsole's E2DSign 1..14 (UV table 0x93ceea0)
        [(892, 48), (892, 112), (892, 176), (892, 240),   # red: hairpin left/right, S left/right
         (828, 48), (828, 112), (828, 176), (828, 240),   # orange: curve left/right, S left/right
         (764, 48), (764, 112),                           # blue: keep left/right at a fork
         (956, 48), (956, 112), (956, 240), (956, 176)])]  # ! caution, green: straight, left, right
# clTimeConsole::setMapName(EMapText) (any mode but the time attack's): EMapText 1..19 ->
# UV ids at 0x93ceda0 -> rects of the UV table (0 is blank)
_MAP_TEXT_UV = [185, 186, 187, 188, 189, 190, 191, 194, 193, 192, 197, 195, 196, 200, 201, 199, 198, 209, 210]
_UV_RECT = {**{n: (256, 384 + 16 * (n - 185)) for n in range(185, 200)},
            **{n: (384, 496 + 16 * (n - 200)) for n in range(200, 209)}, 209: (384, 480), 210: (384, 464)}
TA_CROPS += [(f"map_text_{k + 1}", *_UV_RECT[n], 128, 16) for k, n in enumerate(_MAP_TEXT_UV)]
# the class on the plate (clMeterConsole::setClass): its letters and digits, UV 37..51 of
# the table above (N A B C at y 76, S and 0..9 at y 92, 12 x 16 each)
TA_CROPS += [(f"rank_{c}", 360 + 12 * k, 76, 12, 16) for k, c in enumerate("NABC")] + [("rank_S", 360, 92, 12, 16)] + \
    [(f"rank_{d}", 372 + 12 * d, 92, 12, 16) for d in range(10)]

MAX_PARTS = 9


def drop_guide_frame(im):
    """Some sprites carry an opaque 1px red layout frame that the game never shows."""
    w, h = im.size
    edge = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + \
           [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    if all(im.getpixel(p) == (255, 0, 0, 255) for p in edge):
        for p in edge:
            im.putpixel(p, (0, 0, 0, 0))
    return im


def pack_hud(sprite_dir, main, out):
    elf = menupack.Elf(main)
    names = menupack.sprite_names(elf)
    root = os.path.dirname(os.path.dirname(os.path.abspath(sprite_dir)))  # names are data/sprite/x.png
    with open(out, "wb") as f:
        f.write(b"WHD1" + struct.pack("<I", len(SPRITES) + len(ATLAS_CROPS) + len(TEXTS) + len(TA_SPRITES) + len(TA_CROPS)))

        def put(name, im):
            f.write(name.encode().ljust(32, b"\0") + struct.pack("<II", *im.size) + im.tobytes())
        for n in SPRITES:
            put(n, drop_guide_frame(Image.open(f"{sprite_dir}/{n}.png").convert("RGBA")))
        atlas = Image.open(f"{sprite_dir}/{ATLAS}.png").convert("RGBA")
        for n, x, y, w, h in ATLAS_CROPS:
            put(n, atlas.crop((x, y, x + w, y + h)))
        for n, font, text in TEXTS:
            put(n, menupack.render_text(elf, names, root, font, text))
        for n in TA_SPRITES:
            put(n, drop_guide_frame(Image.open(f"{sprite_dir}/{n}.png").convert("RGBA")))
        for n, x, y, w, h in TA_CROPS:
            put(n, atlas.crop((x, y, x + w, y + h)))


def pack_meters(sprite_dir, out):
    here = os.path.dirname(os.path.abspath(__file__))
    meters = json.load(open(f"{here}/meters.json"))["cars"]
    packs = list(json.load(open(f"{here}/cars.json"))["packs"])  # CARDB_PACKS' order
    order, index = [], []
    for folder in packs:
        for zone in meters[folder]:
            assert len(zone) <= MAX_PARTS, folder
            for n in zone:
                if n not in order:
                    order.append(n)
            index += [order.index(n) for n in zone] + [0xFFFF] * (MAX_PARTS - len(zone))
    ims = [Image.open(f"{sprite_dir}/{n}.png").convert("RGBA") for n in order]
    off = 12 + 2 * len(index) + 12 * len(ims)
    table = b""
    for im in ims:
        table += struct.pack("<3I", *im.size, off)
        off += im.size[0] * im.size[1] * 4
    with open(out, "wb") as f:
        f.write(b"WMT1" + struct.pack("<2I", len(packs), len(ims)))
        f.write(struct.pack(f"<{len(index)}H", *index) + table)
        for im in ims:
            f.write(im.tobytes())
    print("meters.bin: %d cars, %d sprites, %.1f MB" % (len(packs), len(ims), off / 1e6))


if __name__ == "__main__":
    pack_hud(sys.argv[1], sys.argv[2], f"{sys.argv[3]}/hud.bin")
    pack_meters(sys.argv[1], f"{sys.argv[3]}/meters.bin")
