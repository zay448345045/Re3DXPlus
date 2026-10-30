"""Pack one of the arcade's other cities for a time zone, the way the arcade loads it.

The arcade picks the scene file by stage (a table of {day, night} lua paths per EStage at
0x9330524): data/<city>/daytime/daytime.lua or data/<city>/night/night.lua, for Osaka
(oosaka), Hakone, Nagoya and Fukuoka. Each one names
  GroundModel                         -> the ground group
  ShortRangeBuildModel                -> the short-range buildings
  LongRangeBuildModel and FlareModel  -> the long-range group (the glowing signs at night,
                                         as pack_tokyo.sh does for Tokyo's)
  SkyBoxModel                         -> sky_<city>[_night].wpk
  CourseArrow                         -> arrows_<city>[_night].wpk + .names (the junction
                                         arrow boards, one object per junction block)
all with the map's own textures.igb. Tokyo keeps its own script (pack_tokyo.sh).

Writes <out>/<city>.wpk or <city>_night.wpk and the two small files beside it.

usage: pack_city.py <arcade data dir> <oosaka|hakone|nagoya|fukuoka> <daytime|night> <out dir>
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def lua_lists(path):
    """The scene file's model lists and file names: {Name: [igb, ...]} and {Name: "file"}."""
    text = open(path, encoding="utf-8", errors="replace").read()
    text = re.sub(r"--\[\[.*?\]\]", "", text, flags=re.S)
    text = re.sub(r"--[^\n]*", "", text)
    lists = {}
    for m in re.finditer(r"\b(\w+)\s*=\s*\{([^{}]*)\}", text):
        files = re.findall(r'"([^"]+\.igb)"', m.group(2))
        if files or m.group(2).strip() == "":
            lists[m.group(1)] = files
    names = dict(re.findall(r'\b(\w+)\s*=\s*"([^"]*)"', text))
    return lists, names


def main():
    data, city, time, out = sys.argv[1:5]
    scene = os.path.join(data, city, time, time + ".lua")
    lists, names = lua_lists(scene)
    here = os.path.join(data, city, time)
    suffix = "" if time == "daytime" else "_night"
    textures = os.path.join(here, "textures.igb")

    def files(name):
        return [os.path.join(here, f) for f in lists.get(name, [])]

    ground = files("GroundModel")
    short = files("ShortRangeBuildModel")
    long_ = files("LongRangeBuildModel") + files("FlareModel")
    pack = [sys.executable, os.path.join(HERE, "pack.py")]
    # the buildings' textures at the arcade's own size, as Tokyo's (pack_tokyo.sh)
    cmd = pack + [os.path.join(out, city + suffix + ".wpk"), "--textures", textures,
                  "--max-tex-build", "1024"] + ground
    if short:
        cmd += ["--short"] + short
    if long_:
        cmd += ["--long"] + long_
    print(" ".join(os.path.basename(c) for c in cmd), flush=True)
    subprocess.check_call(cmd)
    arrow = names.get("CourseArrow", "")
    if arrow:
        # "data/coursearrow/..." in the arcade's own paths
        subprocess.check_call(pack + [os.path.join(out, "arrows_" + city + suffix + ".wpk"),
                                      "--textures", textures, "--objects",
                                      os.path.join(data, arrow.split("data/", 1)[1])])
    sky = files("SkyBoxModel")
    if sky:
        subprocess.check_call(pack + [os.path.join(out, "sky_" + city + suffix + ".wpk"),
                                      "--textures", textures, "--chunk", "1000000", "--max-tex", "1024"] + sky)


if __name__ == "__main__":
    main()
