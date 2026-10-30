# -*- coding: utf-8 -*-
"""The SAVE DATA screen's "i" page (menu.c MENU_INFO): Allan's text (10-27, word for word)
in a CJK system font, pre-rendered as one sprite (its panel too), and the "i" key.
The arcade's fonts have no simplified Chinese, so a font of the machine's: macOS's first,
then Linux's."""
import glob
import os

from PIL import Image, ImageDraw, ImageFont

# (style, text): h1 / h3 headings, b bold lines, p paragraphs (a paragraph a list of
# (bold, text) runs); the page's words exactly as Allan wrote them
INFO = [
    ("h1", "关于本移植版"),
    ("b", "WANGAN MIDNIGHT MAXIMUM TUNE 3DX+"),
    ("b", "非官方移植研究项目"),
    ("b", "移植制作：高橋涼介のFC"),
    ("p", [(0, "本项目由 Bilibili UP 主「高橋涼介のFC」独立制作，旨在研究和展示原街机游戏在旧款设备上的原生运行、跨平台移植及硬件性能优化技术。")]),
    ("h3", "非官方声明"),
    ("p", [(0, "本移植版为第三方个人研究项目，"), (1, "并非万代南梦宫娱乐（Bandai Namco Entertainment）官方发行的游戏版本"), (0, "。")]),
    ("h3", "知识产权声明"),
    ("p", [(0, "《湾岸 MIDNIGHT》原作、原版街机游戏及其中涉及的名称、商标、人物、美术、音乐、音效、车辆品牌与其他受保护内容，其相关知识产权均归各自权利人所有。")]),
    ("p", [(0, "本移植项目不主张拥有上述原作知识产权。")]),
]

# the page in the menus' 640 x 480: its size there; drawn at SCALE for the iPad's screen
PAGE_W, SCALE = 600, 1.6
FONTS = ["/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
         "/System/Library/Fonts/STHeiti Light.ttc", "/System/Library/Fonts/PingFang.ttc",
         "/Library/Fonts/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
         "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
CLOSING = set("，。、）」》：；！？)")
ORANGE, WHITE = (255, 140, 26, 255), (255, 255, 255, 255)


def font_path():
    for p in FONTS + sorted(glob.glob("/System/Library/AssetsV2/*/*/AssetData/PingFang.ttc")):
        if os.path.exists(p):
            return p
    raise SystemExit("infopage.py: no CJK font found (tried %s)" % ", ".join(FONTS))


def _font(size):
    return ImageFont.truetype(font_path(), int(round(size * SCALE)))


def _lines(runs, font, width):
    """the runs wrapped at width, a character at a time (a Latin word kept whole): lines of runs"""
    tokens = []
    for bold, text in runs:
        word = ""
        for c in text:
            if c.isascii() and c not in " ":
                word += c
                continue
            if word:
                tokens.append((bold, word))
                word = ""
            tokens.append((bold, c))
        if word:
            tokens.append((bold, word))
    lines, line, x = [], [], 0.0
    for bold, t in tokens:
        w = font.getlength(t)
        # (no closing mark starts a line: it hangs past the edge)
        if x + w > width and line and t != " " and t not in CLOSING:
            lines.append(line)
            line, x = [], 0.0
            if t == " ":
                continue
        line.append((bold, t))
        x += w
    if line:
        lines.append(line)
    return lines


def render_page():
    pad, w = 18 * SCALE, PAGE_W * SCALE
    inner = w - 2 * pad
    f_h1, f_h3, f_b, f_p = _font(22), _font(17), _font(15), _font(13.5)
    y = pad
    ops = []  # (y, runs, font, colour: None by the run's boldness)
    for i, (style, body) in enumerate(INFO):
        prev = INFO[i - 1][0] if i else None
        if style in ("h1", "h3", "b"):
            font = {"h1": f_h1, "h3": f_h3, "b": f_b}[style]
            size = font.size
            if style == "h3":
                y += 0.6 * size
            ops.append((y, [(1, body)], font, ORANGE if style != "b" else WHITE))
            y += size * (1.5 if style == "h1" else 1.35)
        else:
            size = f_p.size
            if prev == "b":
                y += 0.5 * size  # (the title lines apart from the text)
            for line in _lines(body, f_p, inner):
                ops.append((y, line, f_p, None))
                y += size * 1.45
            y += 0.25 * size
    h = int(y + pad)
    img = Image.new("RGBA", (int(w), h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, int(w) - 1, h - 1), radius=int(14 * SCALE), fill=(0, 0, 0, 190),
                        outline=(255, 140, 26, 200), width=max(1, int(2 * SCALE)))
    for y0, runs, font, colour in ops:
        x = pad
        for bold, t in runs:
            c = colour or (ORANGE if bold else WHITE)
            d.text((x, y0), t, font=font, fill=c, stroke_width=1 if bold else 0, stroke_fill=c)
            x += font.getlength(t)
    return img


def render_key():
    """the "i" key: an orange ring with an i, 40 x 40 in the menus' space"""
    s = int(40 * SCALE)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(2, int(3 * SCALE))
    d.ellipse((lw // 2, lw // 2, s - 1 - lw // 2, s - 1 - lw // 2), fill=(0, 0, 0, 150), outline=ORANGE, width=lw)
    f = ImageFont.truetype(font_path(), int(s * 0.62))
    tw = f.getlength("i")
    d.text(((s - tw) / 2, s * 0.14), "i", font=f, fill=WHITE, stroke_width=1, stroke_fill=WHITE)
    return img


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "info_page.png"
    render_page().save(out)
    render_key().save(os.path.splitext(out)[0] + "_key.png")
    print(font_path(), Image.open(out).size)
