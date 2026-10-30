"""Pack the arcade's street lights and building lights for the iPad port.

The arcade's clStreetLightManager reads every "locator" igTransform of the map's StreetLight
model (effect/streetlight_distribution_tk.igb) and sorts them by the colour group they sit in
(nsGameSceneUtil::StreetLightMemberGet: white, yellow, orange, blue); each light is a lamp
glint from sprite/streetlight.tga and a glow from sprite/streettube.tga. At night
clBuildingLightManager does the same for BuildingLight (effect/buildinglight_distribution_sk.igb:
red1, red2, red3 with sprite/buildinglight.tga, white1, white2 with sprite/bridge_light.tga).

The rows of lights across the road at the goal and at the checkpoints (clGoalLine) take
their glows and flashes from goal_light01.tga, inside effect/goal_light_yellow.igb; the
10-in-a-row's blue line at the rival (clTenRivalLine) its 10rival_line.dds from
effect/rival_line_blue.igb (its mesh: pack_tenline.py).

Writes
  lights.wpk  the nine sprites as a WPK2 with no chunks (render.h reads its textures),
              in the order streetlight, streettube, buildinglight, bridge_light,
              goal_light01, 10rival_line, car_lightspot_a3, car_spark03, car_spark04
  lights.bin  "LIT1" u32 n_street u32 n_building, then per light f32 x y z u32 type
              (street lights first, then building lights)

usage: pack_lights.py data_dir out_dir
       pack_lights.py data_dir out_dir city street.igb building.igb   (another city's lights
       into lights_<city>.bin, from its scene file's StreetLight and BuildingLight, "-" for none;
       the sprites stay lights.wpk's)
"""
import os
import struct
import sys

import numpy as np

from PIL import Image

from igb import IGB
from pack import encode16, load_image_file
from scene import obj_list
from tex import to_pil

STREET_TYPES = ["white", "yellow", "orange", "blue"]
BUILDING_TYPES = ["red1", "red2", "red3", "white1", "white2"]
SPRITES = ["streetlight.tga", "streettube.tga", "buildinglight.tga", "bridge_light.tga"]
GOAL = "effect/goal_light_yellow.igb"
TEN_LINE = "effect/rival_line_blue.igb"
SPOT = "car_lightspot_a3.tga"  # clCarSpotLight's image 1334
SPARKS = ["car_spark03.tga", "car_spark04.tga"]  # clCarSparkManager's images 0x11a, 0x11b


def goal_texture(data, igb=GOAL):
    """goal_light01.tga as the IGB holds it (rows bottom up, as its UVs want), with red and
    blue swapped back: it stores them the other way round, like car_icon.igb (as decoded, the
    goal's yellow quads would map the blue lights; the blue line would be red)"""
    f = IGB(os.path.join(data, igb))
    img = f.of_type("igImage")[0]
    r, g, b, a = to_pil(img, f.ref(img[13]).mem).split()
    return Image.merge("RGBA", (b, g, r, a))


def locators(path, types):
    """[(x, y, z, type)] the way nsGameSceneUtil::StreetLightMemberGet / BuildingLightMemberGet
    and their PositionGet count them: an igGroup named one of types sets the type of what is
    under it (another name keeps its parent's; the model's own root starts at 0, the first
    type, so Nagoya's "white1"/"white2" groups and Fukuoka's "bule" are white); an igTransform
    whose name is not below "locator" (strcmp >= 0: "locator", Fukuoka's "streetlight_null")
    is a light, its children left unvisited; anything else is walked into"""
    f = IGB(path)
    root = f.ref(f.of_type("igSceneInfo")[0][5])
    out = []

    def walk(node, mat, kind):
        if node is None or node.mem is not None:
            return
        name = f.string(node[2]) if node[2] is not None else ""
        if node.type == "igGroup" and name in types:
            kind = types.index(name)
        if node.type == "igTransform" and node[8] is not None:
            mat = np.frombuffer(node[8].raw, dtype="<f4").reshape(4, 4) @ mat
        if node.type == "igTransform" and name >= "locator":
            out.append((*mat[3, :3].tolist(), kind))
            return
        for c in obj_list(f, f.ref(node[7])):
            walk(c, mat, kind)

    walk(root, np.eye(4, dtype=np.float32), 0)
    return out


def main():
    data, out_dir = sys.argv[1], sys.argv[2]
    if len(sys.argv) > 3:
        city, street_f, building_f = sys.argv[3:6]
        street = locators(os.path.join(data, street_f), STREET_TYPES) if street_f != "-" else []
        building = locators(os.path.join(data, building_f), BUILDING_TYPES) if building_f != "-" else []
        write_bin(os.path.join(out_dir, "lights_%s.bin" % city), street, building)
        return
    street = locators(os.path.join(data, "effect/streetlight_distribution_tk.igb"), STREET_TYPES)
    building = locators(os.path.join(data, "effect/buildinglight_distribution_sk.igb"), BUILDING_TYPES)
    write_bin(os.path.join(out_dir, "lights.bin"), street, building)
    write_wpk(data, out_dir)


def write_bin(path, street, building):
    with open(path, "wb") as fp:
        fp.write(struct.pack("<4sII", b"LIT1", len(street), len(building)))
        for x, y, z, t in street + building:
            fp.write(struct.pack("<fffI", x, y, z, t))
    for name, ls, types in (("street", street, STREET_TYPES), ("building", building, BUILDING_TYPES)):
        print("%d %s lights: %s" % (len(ls), name,
              ", ".join("%s %d" % (t, sum(1 for l in ls if l[3] == i)) for i, t in enumerate(types))))


def write_wpk(data, out_dir):
    texs = [encode16(load_image_file(os.path.join(data, "sprite", n)), 256) for n in SPRITES]
    texs.append(encode16(goal_texture(data), 256))
    texs.append(encode16(goal_texture(data, TEN_LINE), 256))
    # clCarSpotLight's pool (v 0, the car's end, its bright edge)
    texs.append(encode16(load_image_file(os.path.join(data, "sprite", SPOT)), 256))
    # the wall sparks (clCarSparkPrimitive: v along the streak)
    texs += [encode16(load_image_file(os.path.join(data, "sprite", n)), 256) for n in SPARKS]
    names = SPRITES + ["goal_light01.tga", "10rival_line.dds", SPOT] + SPARKS
    tex_off = 32
    data_off = tex_off + 64 * len(texs)
    tbl, blob = bytearray(), bytearray()
    for n, (w, h, fmt, px) in zip(names, texs):
        tbl += struct.pack("<48sHHIII", n.encode(), w, h, fmt, data_off + len(blob), len(px))
        blob += px
        blob += b"\0" * (-len(blob) % 4)
    with open(os.path.join(out_dir, "lights.wpk"), "wb") as fp:
        fp.write(struct.pack("<4sIIIfIII", b"WPK2", len(texs), 0, 0, 4000.0, tex_off, data_off, data_off))
        fp.write(tbl)
        fp.write(blob)


if __name__ == "__main__":
    main()
