#!/bin/sh
# Pack the player's FD3S the way car.lua dresses it: body.igb carries a plain white body
# (BaseTexture) that the arcade swaps for the chosen paint (BodyColorTexture, colA01-06:
# yellow, blue, red, white, silver, black), plus sky light baked from the normals.
# Usage: tools/stage/pack_car.sh [paint 1-6] [out.wpk]
set -e
cd "$(dirname "$0")"
C="../../../Wangan Midnight Maximum Tune 3DX+ (Japan)/data/car/maz_FD3S"
PAINT="${1:-1}"
OUT="${2:-../../data/fd3s.wpk}"
python3 pack.py "$OUT" --chunk 100000 "$C/normal/body.igb" "$C/tire.igb" --shade \
  --swap "fd3s_body01_white=$C/normal/color/fd3s_body01_colA0$PAINT.tga"
