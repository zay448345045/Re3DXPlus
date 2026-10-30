#!/usr/bin/env python3
# App icons from Allan's 3DX+ artwork (data/icon/logo_allan2.jpg, 518x386) -> data/icon/Icon-*.png.
# The square is the art's left side at full height (the logo, the Hakosuka and CHALLENGE): no
# stretching and no bars. The icons come pre-rendered the way iOS 6 draws them: the rounded
# corners (transparent, antialiased, so no black edges) and the glossy shine over the top half.
# Info.plist sets UIPrerenderedIcon, so the springboard draws them as they are.
import os
from PIL import Image, ImageChops, ImageDraw

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "icon")
SIZES = {"Icon-72.png": 72, "Icon-72@2x.png": 144, "Icon-76.png": 76, "Icon-76@2x.png": 152,
         "Icon-Small-50.png": 50, "Icon-Small-50@2x.png": 100, "Icon-Small.png": 29, "Icon-Small@2x.png": 58}
SS = 4  # supersampling for the masks' edges


def mask(s):
    # iOS 6's icon shape: a rounded square, corner radius about 16% of the side (9 px at 57)
    big = Image.new("L", (s * SS, s * SS), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, s * SS - 1, s * SS - 1), radius=0.16 * s * SS, fill=255)
    return big.resize((s, s), Image.LANCZOS)


def shine(s):
    # the gloss: white over the top, fading down to a soft arc a little below the middle
    n = s * SS
    grad = Image.new("L", (1, n), 0)
    for y in range(n):
        t = y / (0.55 * n)
        grad.putpixel((0, y), int(255 * (0.50 - 0.32 * t)) if t < 1 else 0)
    grad = grad.resize((n, n))
    arc = Image.new("L", (n, n), 0)
    ImageDraw.Draw(arc).ellipse((-0.45 * n, -0.62 * n, 1.45 * n, 0.53 * n), fill=255)
    a = ImageChops.multiply(grad, arc).resize((s, s), Image.LANCZOS)
    layer = Image.new("RGBA", (s, s), (255, 255, 255, 0))
    layer.putalpha(a)
    return layer


def icon(square, s):
    img = square.resize((s, s), Image.LANCZOS).convert("RGBA")
    img = Image.alpha_composite(img, shine(s))
    img.putalpha(mask(s))
    return img


src = Image.open(os.path.join(HERE, "logo_allan2.jpg")).convert("RGB")
side = min(src.size)
square = src.crop((0, 0, side, side))
for name, s in SIZES.items():
    icon(square, s).save(os.path.join(HERE, name), optimize=True)
icon(square, 512).save(os.path.join(HERE, "preview.png"))
print("square", side, "->", sorted(SIZES))
