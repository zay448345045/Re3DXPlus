#!/bin/sh
# Build the Android port (build/WMMT3DX-android.apk: arm64-v8a, Android 9+, Vulkan (src/vkgl.c;
# VK=0 for OpenGL ES 3) + AAudio) with the SDK's build-tools and the NDK, no Gradle. Usage:
#   ./build_android.sh            the apk
# Input resources and generated code are deliberately excluded; see README.md.
# No automatic device installation or data transfer.
set -e
[ "$#" -eq 0 ] || { echo 'No arguments supported; device operations are not provided.' >&2; exit 1; }
cd "$(dirname "$0")"
: "${ANDROID_HOME:?Set ANDROID_HOME to your Android SDK}"
: "${JAVA_HOME:?Set JAVA_HOME to your JDK}"
: "${SIGNING_KEYSTORE:?Set SIGNING_KEYSTORE to your private keystore}"
[ -f "$SIGNING_KEYSTORE" ] || { echo 'Signing keystore missing' >&2; exit 1; }
SDK="$ANDROID_HOME"
export JAVA_HOME
BT="$SDK/build-tools/$(ls "$SDK/build-tools" | sort -V | tail -1)"
PLAT="$SDK/platforms/$(ls "$SDK/platforms" | sort -V | tail -1)"
NDK="$SDK/ndk/$(ls "$SDK/ndk" | sort -V | tail -1)"
HOST=$(ls "$NDK/toolchains/llvm/prebuilt" | head -1)
API=28
CC="$NDK/toolchains/llvm/prebuilt/$HOST/bin/aarch64-linux-android$API-clang"
OUT="${BUILD_OUT:-build/android}"
APK_OUT="${APK_OUT:-build/WMMT3DX-android.apk}"
[ ! -e "$OUT" ] || { echo "Refusing to overwrite existing build directory: $OUT" >&2; exit 1; }
mkdir -p "$OUT/apk/lib/arm64-v8a" "$OUT/classes" "$OUT/obj"

# the programs' SPIR-V for Vulkan (tools/vkglsl.py) from their sources (tools/vkprogs: a new
# one the game meets is written to the phone's save folder, <key>.txt, to put there), by the
# NDK's glslc unless there is a glslangValidator
VK="${VK:-1}"
if [ "$VK" = 1 ]; then
  GLSLC="$NDK/shader-tools/$HOST/glslc"
  if ! command -v glslangValidator >/dev/null 2>&1 && [ -x "$GLSLC" ]; then export VKGLSL_CC="$GLSLC"; fi
  if [ ! -f src/vkgl_spv.c ] || [ -n "$(find tools/vkprogs tools/vkglsl.py -newer src/vkgl_spv.c | head -1)" ]; then
    echo "the programs to SPIR-V..."
    python3 tools/vkglsl.py table tools/vkprogs src/vkgl_spv.c
  fi
  GFX="-DWMMT_VK src/vkgl.c src/vkgl_spv.c"
  GFX_LIBS="-lvulkan"
else
  GFX=""
  GFX_LIBS="-lEGL -lGLESv2"
fi

# the native library: the game as on iOS, with main_android.c for main.m and sound_ios.m
# The generated physics is kept locally; clamp its one unbounded section walk each build
# (idempotent, and a no-op once guarded) so an older copy cannot bring the crash back.
if [ -f src/phys/phys_rc.c ]; then python3 tools/recomp/guard_sections.py src/phys/phys_rc.c; fi
if [ ! -f "$OUT/obj/phys_rc.o" ] || [ src/phys/phys_rc.c -nt "$OUT/obj/phys_rc.o" ]; then
  echo "compiling the arcade physics (takes a minute)..."
  $CC -O2 -fPIC -ffp-contract=off -DRC_FPT=double -w -c src/phys/phys_rc.c -o "$OUT/obj/phys_rc.o"
fi
$CC -O2 -fPIC -shared -std=gnu99 -Wall -Wno-unused-function -DRC_FPT=double -DWMMT_EGL $GFX \
  -mcpu=cortex-a73 \
  src/main_android.c src/app.c src/story_evidence.c src/render.c src/hud.c src/car.c src/collide.c src/sound.c src/anm.c src/menu.c \
  src/lights.c src/spark.c src/backfire.c src/backfire_wpk.c src/net.c src/vs_host.c src/title.c src/gk.c \
  src/phys/rc_runtime.c "$OUT/obj/phys_rc.o" \
  -o "$OUT/apk/lib/arm64-v8a/libwmmt.so" \
  -landroid $GFX_LIBS -laaudio -llog -lz -lm -Wl,-z,max-page-size=16384

# the Java side
"$JAVA_HOME/bin/javac" -source 8 -target 8 -nowarn -classpath "$PLAT/android.jar" -d "$OUT/classes" \
  android/java/com/wmmt/port/MainActivity.java android/java/com/wmmt/port/CardResources.java
"$BT/d8" --min-api $API --lib "$PLAT/android.jar" --output "$OUT/apk" $(find "$OUT/classes" -name '*.class')

# the manifest and icon, then the apk, aligned and signed with a key of its own
mkdir -p "$OUT/res/mipmap"
: "${APP_ICON:?Set APP_ICON to a locally supplied icon}"
[ -f "$APP_ICON" ] || { echo 'Missing application icon' >&2; exit 1; }
cp "$APP_ICON" "$OUT/res/mipmap/icon.png"
"$BT/aapt2" compile --dir "$OUT/res" -o "$OUT/res.zip"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$PLAT/android.jar" --manifest android/AndroidManifest.xml \
  --min-sdk-version $API --target-sdk-version 33 --version-code "${VERSION_CODE:-2}" --version-name "${VERSION_NAME:-1.1}" "$OUT/res.zip"
# (the library stored, not deflated, and page-aligned: it is mapped from the apk as it is)
(cd "$OUT/apk" && zip -q ../base.apk classes.dex && zip -q -0 -r ../base.apk lib)
if [ -n "${GAME_DATA_ZIP:-}" ]; then
  [ -f "$GAME_DATA_ZIP" ] || { echo "Missing game data archive" >&2; exit 1; }
  mkdir -p "$OUT/apk/assets"
  cp "$GAME_DATA_ZIP" "$OUT/apk/assets/re3dxplus-data.zip"
  (cd "$OUT/apk" && zip -q -0 ../base.apk assets/re3dxplus-data.zip)
fi
# Optional independent cut-in sprites; never rewrite or regenerate GAME_DATA_ZIP.
# A specified path is mandatory; otherwise include the generated data file when present.
if [ "${STORY_CUTIN_BIN+x}" = x ]; then
  [ -f "$STORY_CUTIN_BIN" ] || { echo "Missing story cut-in asset: $STORY_CUTIN_BIN" >&2; exit 1; }
elif [ -f data/story-cutin.bin ]; then
  STORY_CUTIN_BIN=data/story-cutin.bin
fi
if [ -n "${STORY_CUTIN_BIN:-}" ]; then
  mkdir -p "$OUT/apk/assets"
  cp "$STORY_CUTIN_BIN" "$OUT/apk/assets/story-cutin.bin"
  (cd "$OUT/apk" && zip -q -0 ../base.apk assets/story-cutin.bin)
fi
# Independent, pinned sidecar. Never touch the game-data archive.
: "${CARD_RESOURCES:?Set CARD_RESOURCES to the locally supplied sidecar archive}"
[ -f "$CARD_RESOURCES" ] || { echo "Missing card resources sidecar" >&2; exit 1; }
[ "$(shasum -a 256 "$CARD_RESOURCES" | awk '{print $1}')" = "89e1092cfd6a4d758bf7eb4987dc9b8895fa61b5d459d3107b160545464faf81" ] || { echo "Incorrect card resources SHA-256" >&2; exit 1; }
mkdir -p "$OUT/apk/assets"
cp "$CARD_RESOURCES" "$OUT/apk/assets/card-resources-v1.zip"
[ "$(shasum -a 256 "$OUT/apk/assets/card-resources-v1.zip" | awk '{print $1}')" = "89e1092cfd6a4d758bf7eb4987dc9b8895fa61b5d459d3107b160545464faf81" ] || { echo "Copied card resources SHA-256 mismatch" >&2; exit 1; }
(cd "$OUT/apk" && zip -q -0 ../base.apk assets/card-resources-v1.zip)

# Independently released card-page assets; never change the game data ZIP.
if [ "${CARD_PAGES_BIN+x}" = x ]; then
  [ -f "$CARD_PAGES_BIN" ] || { echo "Missing card pages asset: $CARD_PAGES_BIN" >&2; exit 1; }
elif [ -f data/card-pages.bin ]; then
  CARD_PAGES_BIN=data/card-pages.bin
fi
if [ -n "${CARD_PAGES_BIN:-}" ]; then
  mkdir -p "$OUT/apk/assets"
  cp "$CARD_PAGES_BIN" "$OUT/apk/assets/card-pages.bin"
  (cd "$OUT/apk" && zip -q -0 ../base.apk assets/card-pages.bin)
fi
# Optional backfire sidecars are a matched pair, never part of GAME_DATA_ZIP.
if [ -n "${BACKFIRE_WPK:-}" ] || [ -n "${BACKFIRE_BFX:-}" ]; then
  [ -n "${BACKFIRE_WPK:-}" ] && [ -n "${BACKFIRE_BFX:-}" ] &&
    [ -f "$BACKFIRE_WPK" ] && [ -f "$BACKFIRE_BFX" ] || { echo 'BACKFIRE_WPK and BACKFIRE_BFX must both be existing files' >&2; exit 1; }
  mkdir -p "$OUT/apk/assets"
  [ ! -e "$OUT/apk/assets/backfire.wpk" ] && [ ! -e "$OUT/apk/assets/backfire.bfx" ] || { echo 'Backfire asset destination already exists' >&2; exit 1; }
  cp "$BACKFIRE_WPK" "$OUT/apk/assets/backfire.wpk"
  cp "$BACKFIRE_BFX" "$OUT/apk/assets/backfire.bfx"
  (cd "$OUT/apk" && zip -q -0 ../base.apk assets/backfire.wpk assets/backfire.bfx)
fi
"$BT/zipalign" -f -P 16 4 "$OUT/base.apk" "$OUT/aligned.apk"
[ ! -e "$APK_OUT" ] || { echo "Refusing to overwrite existing APK: $APK_OUT" >&2; exit 1; }
# apksigner prompts interactively for required passwords; never embed them in the script.
"$BT/apksigner" sign --ks "$SIGNING_KEYSTORE" --out "$APK_OUT" "$OUT/aligned.apk"
echo "built $APK_OUT"
