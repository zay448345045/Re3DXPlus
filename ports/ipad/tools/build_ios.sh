#!/bin/sh
# Compile only; never install, sign, package, or deploy.
set -eu
if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "Usage: sh tools/build_ios.sh NEW_OUTPUT_DIRECTORY" >&2; exit 2
fi
out=$1
if [ -e "$out" ] || [ -L "$out" ]; then
  echo "Output path already exists: $out" >&2; exit 1
fi
if ! command -v xcrun >/dev/null 2>&1; then
  echo "Missing xcrun; install/select Xcode and its iPhoneOS SDK." >&2; exit 1
fi
sdk=$(xcrun --sdk iphoneos --show-sdk-path) || { echo "Cannot locate iPhoneOS SDK" >&2; exit 1; }
clang=$(xcrun --sdk iphoneos --find clang) || { echo "Cannot locate iPhoneOS clang" >&2; exit 1; }
[ -d "$sdk" ] && [ -x "$clang" ] || { echo "Invalid iPhoneOS SDK or clang" >&2; exit 1; }
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
missing=0
for file in \
  src/main.m src/sound_ios.m src/app.c src/story_evidence.c src/render.c src/hud.c \
  src/car.c src/collide.c src/sound.c src/anm.c src/menu.c src/lights.c src/spark.c src/backfire.c src/backfire_wpk.c \
  src/net.c src/vs_host.c src/title.c src/gk_ios.m src/phys/rc_runtime.c src/phys/phys_rc.c \
  src/cardb.h src/carwheel.h src/rivaldb.h src/tendb.h src/storycity.h src/storymovie.h \
  src/storyinfo.h src/minicourse.h src/meterdb.h src/meterdb_v2.h src/meter_pack.h \
  src/racing_lamp_data.h src/storydemo.h src/story_cutin_data.h src/time_texture.h \
  src/battle.h src/storypre.h src/storysel.h src/sttune.h src/steff.h src/dressdb.h \
  src/namedb.h src/neondb.h src/tenline.h src/sounddb.h src/sparkdb.h src/titledb.h
do
  if [ ! -f "$project/$file" ]; then echo "Missing input: $file" >&2; missing=1; fi
done
[ "$missing" -eq 0 ] || { echo "Prepare missing inputs separately; see tools/BUILD_IOS.md." >&2; exit 1; }
# Atomic creation prevents overwriting a path created after the initial check.
mkdir "$out" || { echo "Cannot create new output directory: $out" >&2; exit 1; }
out=$(CDPATH= cd -- "$out" && pwd -P)
printf 'BUILD_DIR=%s\n' "$out"
cd "$project"
# clamp the one unbounded section walk of the generated physics (idempotent)
python3 tools/recomp/guard_sections.py src/phys/phys_rc.c
"$clang" -arch arm64 -isysroot "$sdk" -miphoneos-version-min=16.0 -O2 -DRC_FPT=double \
  -ffp-contract=off -w -c src/phys/phys_rc.c -o "$out/phys_rc.o"
"$clang" -arch arm64 -isysroot "$sdk" -miphoneos-version-min=16.0 -O2 -DRC_FPT=double \
  -std=gnu99 -Wall -Wno-unused-function \
  src/main.m src/sound_ios.m src/app.c src/story_evidence.c src/render.c src/hud.c \
  src/car.c src/collide.c src/sound.c src/anm.c src/menu.c src/lights.c src/spark.c src/backfire.c src/backfire_wpk.c \
  src/net.c src/vs_host.c src/title.c src/gk_ios.m src/phys/rc_runtime.c "$out/phys_rc.o" \
  -o "$out/WMMT" -framework UIKit -framework Foundation -framework OpenGLES -framework QuartzCore \
  -framework AVFoundation -framework AudioToolbox -framework CoreMedia -framework CoreMotion -framework GameKit -lz
printf 'BUILT_EXECUTABLE=%s/WMMT\n' "$out"
