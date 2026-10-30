#!/bin/sh
# Regenerate everything this repository leaves out because it comes straight from the arcade's
# files: the src/*.h tables, the tools' lists (tools/*.json, tools/*_texts.txt, uvtab.txt,
# stage/barricades.txt) and, with --phys, the recompiled physics (src/phys/phys_rc.c,
# data/phys.img). Needs python3 with capstone, unicorn and Pillow (pip install capstone unicorn
# pillow) and c++filt.
# Usage: tools/gen_from_original.sh [arcade root] [--phys]
#   arcade root: the folder that has `main` and data/ (default: the folder next to this
#   repository, "../Wangan Midnight Maximum Tune 3DX+ (Japan)")
set -e
cd "$(dirname "$0")/.."
ORIG="../Wangan Midnight Maximum Tune 3DX+ (Japan)"
PHYS=
for a in "$@"; do
  case "$a" in
    --phys) PHYS=1 ;;
    *) ORIG="$a" ;;
  esac
done
ORIG="$(cd "$ORIG" && pwd)"
MAIN="$ORIG/main"
D="$ORIG/data"
[ -f "$MAIN" ] || { echo "no arcade main at $MAIN" >&2; exit 1; }
export WMMT_MAIN="$MAIN"
run() { echo "  $*"; "$@"; }

echo "the car select, lamps and meters..."
run python3 tools/cardb.py "$MAIN" "$D/car"            # tools/cars.json, src/cardb.h
run python3 tools/brakelampdb.py "$MAIN"               # tools/brakelamps.json
run python3 tools/meterdb.py "$MAIN"                   # tools/meters.json, src/meterdb.h
run python3 tools/neondb.py "$MAIN"                    # src/neondb.h
run python3 tools/stage/pack_cars.py "$ORIG" --wheel-table   # src/carwheel.h
echo "dress-up, names, sounds, sparks, titles..."
run python3 tools/dressdb.py "$MAIN"                   # src/dressdb.h
run python3 tools/weartexts.py "$MAIN"                 # tools/wear_texts.txt
run python3 tools/sounddb.py "$MAIN"                   # src/sounddb.h
run python3 tools/sparkdb.py "$MAIN"                   # src/sparkdb.h
run python3 tools/titledb.py "$MAIN"                   # src/titledb.h
run python3 tools/uvtab.py                             # tools/uvtab.txt
echo "story and 10-in-a-row..."
run python3 tools/rivaldb.py "$MAIN" "$D/characar"     # src/rivaldb.h
run python3 tools/storysel.py "$MAIN"                  # src/storysel.h, tools/storysel_texts.txt
run python3 tools/storyinfo.py "$MAIN"                 # src/storyinfo.h
run python3 tools/storymovie.py "$MAIN"                # src/storymovie.h
run python3 tools/storypre.py "$MAIN"                  # src/storypre.h
run python3 tools/storydemo.py "$MAIN"                 # src/storydemo.h, tools/storydemo_texts.txt
run python3 tools/storycity.py "$MAIN" "$D/carconfig/ytConfigStory.txt"   # src/storycity.h
run python3 tools/sttune.py "$MAIN"                    # src/sttune.h, tools/sttune_texts.txt
run python3 tools/steff.py "$MAIN"                     # src/steff.h, tools/steff_texts.txt
# (namedb.py and tendb.py import menupack.py, which reads the story headers above)
run python3 tools/tendb.py "$MAIN" "$D/carconfig/ytConfigTenFight.txt"    # src/tendb.h
run python3 tools/namedb.py "$MAIN"                    # src/namedb.h
echo "3D bits..."
mkdir -p data
run python3 tools/stage/pack_battle.py "$ORIG" src/battle.h
run python3 tools/stage/pack_tenline.py "$D" src/tenline.h
[ -d "$D/menu3d/course" ] && run python3 tools/stage/pack_mini.py "$ORIG" data/minicourse.wpk src/minicourse.h
echo "  python3 tools/stage/barricades.py main > tools/stage/barricades.txt"
python3 tools/stage/barricades.py "$MAIN" > tools/stage/barricades.txt
if [ -n "$PHYS" ]; then
  echo "the recompiled physics (a few minutes)..."
  run sh tools/recomp/build_phys.sh "$MAIN"            # src/phys/phys_rc.c, data/phys.img
fi
echo "done"
