<p align="center"><img src="docs/logo.png" alt="Re3DX+" width="480"></p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-lightgrey?style=for-the-badge" alt="简体中文"></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/Language-English-brightgreen?style=for-the-badge" alt="English"></a>
</p>

# Re3DX+: an unofficial port of WANGAN MIDNIGHT MAXIMUM TUNE 3DX+ (iOS / Android)

> This fork keeps the Android and iPad adaptations in separate [ports/android](ports/android/) and [ports/ipad](ports/ipad/) trees. The repository root retains the upstream fork baseline; do not overwrite one platform tree with the other. Original game data, generated game-derived tables and signing materials are not distributed. Read each port's notes before building. New features have host-side tests but have not been validated on the target devices.

A research project that ports the arcade game *WANGAN MIDNIGHT MAXIMUM TUNE 3DX+* natively to old mobile devices:

- **iPad 3** (iOS 6.1.3, jailbroken, OpenGL ES 2.0, 1024×768 at 60 fps)
- **iPhone 4** (iOS 6, same code base, 3:2 screen)
- **Android** (arm64, Android 9+, Vulkan renderer with an OpenGL ES 3 fallback; developed on a Xiaomi Mi 6)

This is not an emulator. The arcade's car physics and race logic are statically recompiled from the original i386 executable to C by `tools/recomp/` (bit-for-bit identical behaviour). Everything else (rendering, menus, HUD, sound, versus) is rewritten from reverse engineering of the original. Art, sound and other assets are converted at build time from your own copy of the original data.

## About this port

**WANGAN MIDNIGHT MAXIMUM TUNE 3DX+**
**Unofficial port research project**
**Port by: 高橋涼介のFC** (GitHub: [Allannn-sudo](https://github.com/Allannn-sudo))

This project was made independently by the Bilibili creator 「高橋涼介のFC」. Its aim is to study and demonstrate running the original arcade game natively on older devices, cross-platform porting, and hardware performance optimisation.

### Unofficial notice

This port is a third-party personal research project. **It is not a version of the game released by Bandai Namco Entertainment.**

### Intellectual property notice

All intellectual property rights in the original *Wangan Midnight* work, the original arcade game, and the names, trademarks, characters, art, music, sound effects, vehicle brands and other protected content in them belong to their respective owners.

This port project claims no ownership of the intellectual property of the original work.

*(The Chinese wording in [README.md](README.md) is the authoritative text of these notices.)*

## No original content in this repository

This repository contains only the port's code and conversion tools. It does **not** contain the original arcade executable or data, any asset extracted or converted from them (models, textures, animations, fonts, music, sound effects, movies, text), code or data tables generated from the original executable, or prebuilt ipa / apk packages.

To build and run it you must supply your own **legally obtained** copy of the original *WANGAN MIDNIGHT MAXIMUM TUNE 3DX+* (Japan) arcade data. Please do not upload original files or converted assets in issues or pull requests.

## Layout

```
src/            the game (C / Objective-C)
  main.m, sound_ios.m, gk_ios.m   iOS entry point, audio, Bluetooth versus (GameKit)
  main_android.c                   Android entry point (native thread, AAudio)
  vkgl.c / vkgl.h                  GLES-to-Vulkan layer used on Android
  phys/rc_runtime.*                runtime for the recompiled physics (generate phys_rc.c yourself)
android/        Android's Java shell and AndroidManifest.xml
tools/          tools that generate code tables and assets from the original data (Python)
  gen_from_original.sh             generates every file derived from the original in one go
  recomp/                          i386-to-C static recompiler (physics)
  stage/                           packers for IGB scenes, cars, lights, stickers and more
  upscale/                         helpers for Android HD textures (Real-ESRGAN + ASTC)
  vkprogs/                         the port's own shader sources (compiled to SPIR-V for Vulkan)
  vs_server.py                     online versus server
test/           desktop tests and screenshot programs
docs/logo.png   project logo
build.sh        iOS build (ipa, or deploy straight to a device)
build_android.sh  Android build (apk, no Gradle)
prepare_*.sh    convert sound effects, BGM and movies from the original data
```

The iOS platform code is Objective-C and compiles together with the C sources, so it lives in `src/`; iOS's Info.plist is written by `build.sh`. Android needs a Java shell and a manifest, which is why it has its own `android/` folder.

## Setup

Put the original data folder **next to** this repository and name it `Wangan Midnight Maximum Tune 3DX+ (Japan)` (it should contain `main` and `data/`):

```
some folder/
  Wangan Midnight Maximum Tune 3DX+ (Japan)/   <- your own original data
  this repository/
```

Tools you need:

- Python 3 with `pip install capstone unicorn pillow`
- `c++filt` (binutils)
- ffmpeg with the Bink decoder (for the movies)
- iOS: macOS + Xcode (clang), a patched `iPhoneOS9.3-armv7.sdk` from [theos](https://theos.dev) (in `~/theos/sdks/`), and `ldid`
- Android: the Android SDK (build-tools, platform) and NDK, and a JDK (the one bundled with Android Studio works)

## Step 1: generate the code tables and the physics

```sh
sh tools/gen_from_original.sh --phys
# if the original is somewhere else: sh tools/gen_from_original.sh /path/to/original --phys
```

This runs the original executable's own lookup functions (under the unicorn emulator) and writes the 22 headers such as `src/*db.h` and `src/story*.h`, the list files in `tools/`, the recompiled physics `src/phys/phys_rc.c` and its memory image `data/phys.img`. The output is deterministic for a given copy of the original.

## Step 2: convert the assets (into `data/`)

Run these from the repository root. `<orig>` is the original data folder.

| Output | Command |
|---|---|
| Tokyo map (day / night), road signs, sky | `sh tools/stage/pack_tokyo.sh daytime`, `sh tools/stage/pack_tokyo.sh night` |
| Other cities | `python3 tools/stage/pack_city.py <orig>/data <oosaka\|hakone\|nagoya\|fukuoka> <daytime\|night> data` |
| Street and building lights | `python3 tools/stage/pack_lights.py <orig>/data data` |
| Under neons | `python3 tools/stage/pack_neon.py <orig>/data data/neon.wpk` |
| Cars (aero kits, wheels, story rivals' cars) | `python3 tools/stage/pack_cars.py <orig> data/cars`, then with `--aero a\|b\|c`, `--wheels` (into `data/wheels`) and `--chara` (into `data/chara`) |
| Car ambient occlusion bake (optional) | `cc -O2 -o bake_ao tools/stage/bake_ao.c -lm`, `./bake_ao data/cars/X.wpk data/cars/X.ao` |
| Stickers | `python3 tools/stage/pack_vinyl.py <orig> data/vinyl` |
| Traffic | `sh tools/stage/pack_traffic.sh` (into `data/traffic`) |
| Starter car (FD3S) | `sh tools/stage/pack_car.sh` (writes `data/fd3s.wpk`) |
| Race HUD and meters | `python3 tools/hudpack.py <orig>/data/sprite <orig>/main data` |
| Minimap | `python3 tools/navipack.py <orig>/data <orig>/main data` |
| Menus (animations, pictures, text) | `python3 tools/vsdiscs.py <orig>/data/sprite`, then `python3 tools/menupack.py <orig> data/menu.bin` (the "i" info page is rendered by `tools/infopage.py` with a system CJK font; menupack calls it) |
| Sound effects, BGM, movies | `sh prepare_sound.sh`, `sh prepare_bgm.sh` (macOS, uses afconvert), `sh prepare_movie.sh` |

For HD textures on Android, upscale the map textures with Real-ESRGAN (`tools/upscale/mix.py`), then run the packers with `WPK_TEX_ASTC=6 WPK_ASTCENC=<path to astcenc>` to write ASTC maps (see the notes at the top of `tools/stage/pack.py`). `tools/upscale/check.py` checks the result.

## Step 3: app icon

`tools/make_icon.py` makes iOS 6 style icons from `data/icon/logo_allan2.jpg` (518×386). No picture is included; put one you have the rights to use at that path.

## Build for iOS (iPad 3 / iPhone 4)

```sh
./build.sh ipa            # iPad: build/WMMT3DX-1.0.ipa (data inside the app)
PHONE=1 ./build.sh ipa    # iPhone 4: build/WMMT3DX-1.0-iPhone4.ipa
./build.sh deploy         # deploy to a jailbroken iPad with OpenSSH over the ssh host alias `ipad`
```

The ipa is fake-signed with ldid, so it needs a jailbroken device with AppSync. `deploy` needs a host named `ipad` in your `~/.ssh/config` (for example over USB with `iproxy 2222:22`).

## Build for Android

```sh
./build_android.sh           # build/WMMT3DX-android.apk (Vulkan)
VK=0 ./build_android.sh      # OpenGL ES 3 build
./build_android.sh install   # and install it with adb
./build_android.sh data      # and push data/ to /sdcard/Android/data/com.wmmt.port/files/wmmt
```

The default SDK location is `~/Library/Android/sdk`; override it with `ANDROID_HOME` and `JAVA_HOME`. The apk is signed with a local key generated at build time (`build/android/wmmt.keystore`). The shaders' SPIR-V (`src/vkgl_spv.c`) is generated by `tools/vkglsl.py` from `tools/vkprogs/`.

## Online versus

```sh
python3 tools/vs_server.py [port]    # UDP 27015 by default, up to 4 players
```

Enter this computer's IP address on each device's VERSUS screen. iOS devices can also race over Bluetooth, and on a LAN one device can host.

## License

MIT, see [LICENSE](LICENSE). The license covers only the port's code and tools in this repository, not the original game or any of its content.
