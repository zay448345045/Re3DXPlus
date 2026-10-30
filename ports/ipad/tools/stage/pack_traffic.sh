#!/bin/sh
# Pack the traffic's four models (data/othercar) into data/traffic/<name>.wpk: body_low,
# the one clCarDispManager loads for a race (body_low_2 otherwise, body_com for the oncoming
# cars of the courses that have them). Textures and vertex colours come with the IGBs, the
# textures with red and blue swapped (the namco liveries are yellow and red, the tail lamps red).
# The truck's IGB blends its whole (opaque) body: --solid-opaque draws it with the solid ones.
# --lit keeps the normals: the renderer lights them with car_light.lua's lights and material.
# One chunk each (--chunk 0): a car is drawn whole. Each keeps its shadow volume (shadow.igb).
# With each its lamps' glow, othercar/brakelamp/brakelamp_<model>_Other.igb (one group,
# "lamp", no switches: always lit).
# Usage: tools/stage/pack_traffic.sh [out dir]
set -e
cd "$(dirname "$0")"
D="../../../Wangan Midnight Maximum Tune 3DX+ (Japan)/data/othercar"
OUT="${1:-../../data/traffic}"
mkdir -p "$OUT"
for c in NZE121:toy_NZE121_Other KZH100G:toy_KZH100G_Other Truck:truck_other RC2:sub_RC2_Other; do
  m=${c%%:*}
  python3 pack.py "$OUT/$(echo $m | tr A-Z a-z).wpk" --chunk 0 --lit --bgr --solid-opaque "$D/LOD_$m/body_low.igb" \
    "$D/brakelamp/brakelamp_${c#*:}.igb" --shadow "$D/LOD_$m/shadow.igb"
done
