#!/usr/bin/env python3
"""The versus select's three discs (menu.c MENU_VS_SEL: Bluetooth, LAN, server), drawn in the
style of the arcade's mode discs: menu_p_mode_icon_tg's lettering (a narrow bold face, white
with a dark edge) and its white picture box with a black pictogram, and menu_p_mode_txt_tg's
band with the line under the picture. Writes tools/vsdisc/icon_<k>.png (256x256) and
txt_<k>.png (512x64), which tools/menupack.py packs as VS_ICON_BASE + k, VS_TXT_BASE + k.

    python3 tools/vsdiscs.py <arcade data/sprite dir> [font.otf]

The font: Nimbus Sans Narrow Bold (urw-base35) by default."""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/urw-base35/NimbusSansNarrow-Bold.otf"
DISCS = [("Bluetooth", "versus", "Race an iPad or iPhone beside you over Bluetooth."),
         ("LAN", "versus", "Race players on the same Wi-Fi network."),
         ("Server", "versus", "Race through a versus server on the internet.")]
# menu_p_mode_icon_tg: the title's middle line, the "mode" line, the picture box
TITLE_Y, SUB_Y = 87, 110
BOX = (62, 121, 192, 193)
# menu_p_mode_txt_tg: a column of its band before the words, where they start, their room
BAND_X, LINE_X, LINE_W = 100, 113, 300
SS = 4  # drawn this many times over, then scaled down


def text_edge(img, xy, text, font, fill=(255, 255, 255, 255), edge=(0, 0, 0, 230), width=2):
    d = ImageDraw.Draw(img)
    d.text(xy, text, font=font, fill=fill, anchor="mm", stroke_width=width, stroke_fill=edge)


def fit_font(path, text, size, max_w):
    while size > 10:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 1
    return ImageFont.truetype(path, size)


def device(d, cx, cy, w, h, lw):
    """a phone or pad: a rounded outline with a screen and a button"""
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=w * 0.18, outline=0, width=lw)
    d.rectangle((cx - w / 2 + lw * 2, cy - h / 2 + lw * 3, cx + w / 2 - lw * 2, cy + h / 2 - lw * 3.5), fill=0)
    r = lw * 0.9
    d.ellipse((cx - r, cy + h / 2 - lw * 2.2 - r, cx + r, cy + h / 2 - lw * 2.2 + r), fill=0)


def arcs(d, cx, cy, r0, step, n, a0, a1, lw):
    for i in range(n):
        r = r0 + step * i
        d.arc((cx - r, cy - r, cx + r, cy + r), a0, a1, fill=0, width=lw)


def picto(kind, w, h):
    """the black pictogram on white, w x h (already SS times over)"""
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    lw = int(3.2 * SS)
    cy = h / 2
    if kind == 0:
        # the Bluetooth rune between two devices
        s = h * 0.36
        cx = w / 2
        top, bot = (cx, cy - s), (cx, cy + s)
        d.line([top, bot], fill=0, width=lw)
        d.line([(cx - s * 0.5, cy - s * 0.5), (cx + s * 0.5, cy + s * 0.5), bot], fill=0, width=lw, joint="curve")
        d.line([(cx - s * 0.5, cy + s * 0.5), (cx + s * 0.5, cy - s * 0.5), top], fill=0, width=lw, joint="curve")
        for side in (-1, 1):
            device(d, cx + side * w * 0.36, cy, w * 0.13, h * 0.62, int(2.2 * SS))
    elif kind == 1:
        # Wi-Fi's fan over two devices joined by a line
        cx = w / 2
        fy = cy + h * 0.05
        arcs(d, cx, fy, h * 0.14, h * 0.13, 3, 225, 315, lw)
        r = h * 0.055
        d.ellipse((cx - r, fy - r, cx + r, fy + r), fill=0)
        for side in (-1, 1):
            device(d, cx + side * w * 0.36, cy, w * 0.13, h * 0.62, int(2.2 * SS))
        y = cy + h * 0.30
        d.line([(cx - w * 0.30, y), (cx + w * 0.30, y)], fill=0, width=int(2.2 * SS))
    else:
        # a globe, a line to a server's rack
        gx, r = w * 0.30, h * 0.36
        d.ellipse((gx - r, cy - r, gx + r, cy + r), outline=0, width=lw)
        d.ellipse((gx - r * 0.45, cy - r, gx + r * 0.45, cy + r), outline=0, width=int(2.2 * SS))
        d.line([(gx, cy - r), (gx, cy + r)], fill=0, width=int(2.2 * SS))
        for k in (-0.5, 0, 0.5):
            hw = r * math.sqrt(1 - k * k)
            d.line([(gx - hw, cy + k * r), (gx + hw, cy + k * r)], fill=0, width=int(2.2 * SS))
        sx, sw, sh = w * 0.72, w * 0.20, h * 0.20
        for i in range(3):
            y0 = cy - sh * 1.6 + i * sh * 1.1
            d.rounded_rectangle((sx - sw / 2, y0, sx + sw / 2, y0 + sh), radius=sh * 0.2, fill=0)
            dr = sh * 0.14
            d.ellipse((sx + sw / 2 - sh * 0.5 - dr, y0 + sh / 2 - dr, sx + sw / 2 - sh * 0.5 + dr, y0 + sh / 2 + dr), fill=255)
            d.line([(sx - sw / 2 + sh * 0.35, y0 + sh / 2), (sx, y0 + sh / 2)], fill=255, width=int(1.6 * SS))
        d.line([(gx + r, cy), (sx - sw / 2, cy)], fill=0, width=int(2.2 * SS))
    return im


def icon(tg, kind, title, sub, font):
    out = Image.new("RGBA", tg.size, (0, 0, 0, 0))
    # the picture box as the arcade's (white, a dark edge, round corners), the pictogram in it
    x0, y0, x1, y1 = BOX
    big = Image.new("RGBA", (tg.size[0] * SS, tg.size[1] * SS), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle((x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1), radius=6 * SS,
                                          fill=(255, 255, 255, 255), outline=(40, 40, 40, 255), width=2 * SS)
    out.alpha_composite(big.resize(tg.size, Image.LANCZOS))
    inner = (x0 + 4, y0 + 4, x1 - 4, y1 - 4)
    w, h = inner[2] - inner[0], inner[3] - inner[1]
    p = picto(kind, w * SS, h * SS).resize((w, h), Image.LANCZOS)
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    out.paste(black, inner[:2], Image.eval(p, lambda v: 255 - v))
    big = Image.new("RGBA", (tg.size[0] * SS, tg.size[1] * SS), (0, 0, 0, 0))
    text_edge(big, (128 * SS, TITLE_Y * SS), title, fit_font(font, title, 36 * SS, 170 * SS), width=2 * SS)
    text_edge(big, (128 * SS, SUB_Y * SS), sub, ImageFont.truetype(font, 21 * SS), width=int(1.5 * SS))
    out.alpha_composite(big.resize(tg.size, Image.LANCZOS))
    return out


def txt(band, line, f):
    """menu_p_mode_txt_tg's band without its words: its rows' dark (column BAND_X, before the
    words) times its columns' (row 2, above them), the line on it where the arcade's starts"""
    w, h = band.size
    a = band.getchannel("A")
    rows = [a.getpixel((BAND_X, y)) for y in range(h)]
    cols = [a.getpixel((x, 2)) / 64.0 for x in range(w)]
    out = Image.new("RGBA", (w, h))
    px = out.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (0, 0, 0, min(255, round(rows[y] * cols[x])))
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(big).text((LINE_X * SS, 34 * SS), line, font=f, fill=(255, 255, 255, 255), anchor="lm")
    out.alpha_composite(big.resize((w, h), Image.LANCZOS))
    return out


def main():
    src = sys.argv[1]
    font = sys.argv[2] if len(sys.argv) > 2 else FONT
    tg = Image.open(os.path.join(src, "menu_p_mode_icon_tg.png")).convert("RGBA")
    band = Image.open(os.path.join(src, "menu_p_mode_txt_tg.png")).convert("RGBA")
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vsdisc")
    os.makedirs(dst, exist_ok=True)
    # the lines all at the size the longest fits
    f = min((fit_font(font, line, 18 * SS, LINE_W * SS) for _, _, line in DISCS), key=lambda f: f.size)
    for k, (title, sub, line) in enumerate(DISCS):
        icon(tg, k, title, sub, font).save(os.path.join(dst, f"icon_{k}.png"))
        txt(band, line, f).save(os.path.join(dst, f"txt_{k}.png"))
    print("vsdisc:", len(DISCS), "discs in", dst)


if __name__ == "__main__":
    main()
