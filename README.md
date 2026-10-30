<p align="center"><img src="docs/logo.png" alt="Re3DX+" width="480"></p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-brightgreen?style=for-the-badge" alt="简体中文"></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/Language-English-lightgrey?style=for-the-badge" alt="English"></a>
</p>

# Re3DX+：湾岸 MIDNIGHT MAXIMUM TUNE 3DX+ 非官方移植（iOS / Android）

> 本 fork 的平台适配代码分别位于 [ports/android](ports/android/) 和 [ports/ipad](ports/ipad/)。仓库根目录保留 fork 的上游基线；两个平台目录是各自的开发源码，不应互相覆盖。原版游戏数据、生成表和签名材料不随仓库分发，构建前请阅读各平台目录的说明。新增功能已进行主机测试，未完成本次版本的真机验证。

把街机《湾岸 MIDNIGHT MAXIMUM TUNE 3DX+》原生移植到旧款移动设备上的研究项目：

- **iPad 3**（iOS 6.1.3，越狱，OpenGL ES 2.0，1024×768 60fps）
- **iPhone 4**（iOS 6，同一套代码，3:2 画面）
- **Android**（arm64，Android 9+，Vulkan 渲染器，也可切回 OpenGL ES 3；在小米 6 上开发）

这不是模拟器。街机的赛车物理和比赛逻辑由 `tools/recomp/` 把原版 i386 程序静态重编译成 C（逐位一致），其余部分（渲染、菜单、HUD、声音、对战）照着原版逆向结果重写，美术、声音等素材在构建时从你自己的原版数据转换出来。

## 关于本移植版

**WANGAN MIDNIGHT MAXIMUM TUNE 3DX+**
**非官方移植研究项目**
**移植制作：高橋涼介のFC**（GitHub：[Allannn-sudo](https://github.com/Allannn-sudo)）

本项目由 Bilibili UP 主「高橋涼介のFC」独立制作，旨在研究和展示原街机游戏在旧款设备上的原生运行、跨平台移植及硬件性能优化技术。

### 非官方声明

本移植版为第三方个人研究项目，**并非万代南梦宫娱乐（Bandai Namco Entertainment）官方发行的游戏版本**。

### 知识产权声明

《湾岸 MIDNIGHT》原作、原版街机游戏及其中涉及的名称、商标、人物、美术、音乐、音效、车辆品牌与其他受保护内容，其相关知识产权均归各自权利人所有。

本移植项目不主张拥有上述原作知识产权。

## 本仓库不包含任何原版内容

仓库里只有移植代码和转换工具。**不包含**：原版街机程序和数据、从中提取或转换出的任何素材（模型、贴图、动画、字体、音乐、音效、影片、文字）、由原版程序生成的代码和数据表，以及打包好的 ipa / apk。

要构建并运行，你必须自己准备**合法取得的**原版《湾岸 MIDNIGHT MAXIMUM TUNE 3DX+》（日版）街机数据。请不要在 issue 或 PR 里上传原版文件或转换后的素材。

## 目录

```
src/            游戏本体（C / Objective-C）
  main.m, sound_ios.m, gk_ios.m   iOS 入口、音频、蓝牙对战（GameKit）
  main_android.c                   Android 入口（NativeActivity 线程、AAudio）
  vkgl.c / vkgl.h                  Android 用的 GLES→Vulkan 转换层
  phys/rc_runtime.*                重编译物理的运行时（phys_rc.c 需自行生成）
android/        Android 的 Java 外壳和 AndroidManifest.xml
tools/          从原版数据生成代码表和素材的工具（Python）
  gen_from_original.sh             一键生成所有“由原版生成”的文件
  recomp/                          i386 → C 静态重编译器（物理）
  stage/                           IGB 场景、车辆、灯光、贴纸等打包工具
  upscale/                         Android 高清贴图（Real-ESRGAN + ASTC）辅助脚本
  vkprogs/                         移植版自己的着色器源码（转成 SPIR-V 给 Vulkan 用）
  vs_server.py                     联网对战服务器
test/           桌面上的测试和截图程序
docs/logo.png   项目 logo
build.sh        iOS 构建（ipa / 直接部署到设备）
build_android.sh  Android 构建（apk，不用 Gradle）
prepare_*.sh    从原版数据转换声音、BGM、影片
```

iOS 的系统代码是 Objective-C，能和 C 一起编译，所以直接放在 `src/` 里；iOS 的 Info.plist 由 `build.sh` 现写。Android 需要 Java 外壳和 manifest，所以单独有 `android/` 文件夹。

## 准备

把原版数据文件夹放在本仓库**旁边**，并命名为 `Wangan Midnight Maximum Tune 3DX+ (Japan)`（里面应有 `main` 和 `data/`）：

```
某个目录/
  Wangan Midnight Maximum Tune 3DX+ (Japan)/   ← 你自己的原版数据
  本仓库/
```

需要的工具：

- Python 3，以及 `pip install capstone unicorn pillow`
- `c++filt`（binutils）
- ffmpeg（需带 Bink 解码器，用于影片）
- iOS：macOS + Xcode（clang）、[theos](https://theos.dev) 里打过补丁的 `iPhoneOS9.3-armv7.sdk`（放在 `~/theos/sdks/`）、`ldid`
- Android：Android SDK（build-tools、platform）和 NDK，JDK（Android Studio 自带的即可）

## 第一步：生成代码表和物理

```sh
sh tools/gen_from_original.sh --phys
# 原版不在默认位置时：sh tools/gen_from_original.sh /path/to/原版 --phys
```

它会在原版程序上运行原版自己的查表函数（unicorn 模拟），生成 `src/*db.h`、`src/story*.h` 等 22 个头文件、`tools/` 下的列表文件，以及重编译出的物理代码 `src/phys/phys_rc.c` 和内存镜像 `data/phys.img`。从同一份原版生成的结果是固定的。

## 第二步：转换素材（输出到 `data/`）

以下命令都在仓库根目录运行，`<原版>` 指原版数据文件夹。

| 产物 | 命令 |
|---|---|
| 东京地图（早/晚）、路牌、天空 | `sh tools/stage/pack_tokyo.sh daytime`、`sh tools/stage/pack_tokyo.sh night` |
| 其他城市 | `python3 tools/stage/pack_city.py <原版>/data <oosaka\|hakone\|nagoya\|fukuoka> <daytime\|night> data` |
| 街灯、楼灯 | `python3 tools/stage/pack_lights.py <原版>/data data` |
| 霓虹灯 | `python3 tools/stage/pack_neon.py <原版>/data data/neon.wpk` |
| 车辆（含 aero、轮毂、剧情对手车） | `python3 tools/stage/pack_cars.py <原版> data/cars`，再加 `--aero a\|b\|c`、`--wheels`（输出到 `data/wheels`）、`--chara`（输出到 `data/chara`） |
| 车辆 AO 烘焙（可选） | `cc -O2 -o bake_ao tools/stage/bake_ao.c -lm`，`./bake_ao data/cars/X.wpk data/cars/X.ao` |
| 贴纸 | `python3 tools/stage/pack_vinyl.py <原版> data/vinyl` |
| 路上车流 | `sh tools/stage/pack_traffic.sh`（输出到 `data/traffic`） |
| 玩家初始车（FD3S） | `sh tools/stage/pack_car.sh`（输出 `data/fd3s.wpk`） |
| 比赛 HUD、仪表 | `python3 tools/hudpack.py <原版>/data/sprite <原版>/main data` |
| 小地图 | `python3 tools/navipack.py <原版>/data <原版>/main data` |
| 菜单（动画、图片、文字） | `python3 tools/vsdiscs.py <原版>/data/sprite`，然后 `python3 tools/menupack.py <原版> data/menu.bin`（“i”说明页由 `tools/infopage.py` 用系统中文字体渲染，menupack 会自动调用） |
| 音效、BGM、影片 | `sh prepare_sound.sh`、`sh prepare_bgm.sh`（macOS，用 afconvert）、`sh prepare_movie.sh` |

Android 想用高清贴图时，可以用 Real-ESRGAN 放大地图贴图（`tools/upscale/mix.py`），再用 `WPK_TEX_ASTC=6 WPK_ASTCENC=<astcenc 路径>` 运行打包工具输出 ASTC 版地图（见 `tools/stage/pack.py` 开头说明），`tools/upscale/check.py` 可检查结果。

## 第三步：图标

`tools/make_icon.py` 从 `data/icon/logo_allan2.jpg`（518×386）生成 iOS 6 风格的图标。仓库里没有附带图片，请放一张你自己有权使用的图片在这个位置。

## 构建 iOS（iPad 3 / iPhone 4）

```sh
./build.sh ipa            # iPad：build/WMMT3DX-1.0.ipa（数据打进 app 里）
PHONE=1 ./build.sh ipa    # iPhone 4：build/WMMT3DX-1.0-iPhone4.ipa
./build.sh deploy         # 通过 ssh 主机别名 `ipad` 直接部署到已越狱、装了 OpenSSH 的 iPad
```

ipa 是 ldid 伪签名，需要越狱设备装 AppSync 才能安装。`deploy` 需要你在 `~/.ssh/config` 里配好名为 `ipad` 的主机（例如 `iproxy 2222:22` 走 USB）。

## 构建 Android

```sh
./build_android.sh           # build/WMMT3DX-android.apk（Vulkan）
VK=0 ./build_android.sh      # OpenGL ES 3 版
./build_android.sh install   # 并用 adb 安装
./build_android.sh data      # 并把 data/ 推到 /sdcard/Android/data/com.wmmt.port/files/wmmt
```

默认 SDK 位置是 `~/Library/Android/sdk`，可以用 `ANDROID_HOME`、`JAVA_HOME` 改。apk 用构建时自动生成的本地密钥签名（`build/android/wmmt.keystore`）。着色器的 SPIR-V（`src/vkgl_spv.c`）由 `tools/vkglsl.py` 从 `tools/vkprogs/` 自动生成。

## 联网对战

```sh
python3 tools/vs_server.py [端口]    # 默认 UDP 27015，最多 4 人
```

在各设备的 VERSUS 画面输入这台电脑的 IP。iOS 之间也可以用蓝牙，局域网内也可以由一台设备当主机。

## 许可证

MIT 许可证，见 [LICENSE](LICENSE)。许可证只覆盖本仓库里的移植代码和工具，不覆盖原版游戏及其任何内容。
