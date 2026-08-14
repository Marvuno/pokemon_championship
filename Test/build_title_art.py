"""
Draw the title screen's backdrop: a championship battleground.

Assets/generated/title_wallpaper.png was a dim stadium interior that the
interface then had to darken further to keep text readable, so the title
screen read as a grey box. This paints the arena the matches actually
happen in -- a sunlit field, the marked-out battle circles, banked stands
and a bank of stadium lights -- in the series' own bright palette.

The flags are *not* painted here. They're drawn live by GUI_qt/title.py so
they can actually wave; this only paints their poles, so the two line up.

    python Test/build_title_art.py
"""

import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SIZE = (1366, 768)
OUT = os.path.join(ROOT, "Assets", "generated", "title_wallpaper.png")

#: where the flagpoles stand, as fractions of the image -- GUI_qt/title.py
#: reads the same numbers so the cloth appears on top of these poles
# POLES = (0.085, 0.215, 0.785, 0.915)
# POLE_TOP = 0.085
# POLE_BASE = 0.545


# def lerp(a, b, t):
#     return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# def sky(draw, w, h):
#     top, bottom = (0x3D, 0x8B, 0xE8), (0xA9, 0xDC, 0xF7)
#     for y in range(int(h * 0.58)):
#         t = y / (h * 0.58)
#         draw.line([(0, y), (w, y)], fill=lerp(top, bottom, t))


# def clouds(image, w, h):
#     layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
#     draw = ImageDraw.Draw(layer)
#     rng = random.Random(4242)
#     for _ in range(14):
#         cx = rng.uniform(0, w)
#         cy = rng.uniform(h * 0.05, h * 0.34)
#         scale = rng.uniform(0.6, 1.5)
#         for dx, dy, r in ((-60, 6, 42), (0, -10, 56), (58, 8, 44),
#                           (-20, 14, 38), (26, 16, 40)):
#             draw.ellipse([cx + dx * scale - r * scale,
#                           cy + dy * scale - r * scale,
#                           cx + dx * scale + r * scale,
#                           cy + dy * scale + r * scale],
#                          fill=(255, 255, 255, 150))
#     image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(6)))


# def stands(draw, w, h):
#     horizon = h * 0.50
#     # far stand block
#     draw.rectangle([0, horizon - h * 0.13, w, horizon], fill=(0x24, 0x3C, 0x86))
#     # tiered seating, brightest at the back so the field reads as lit
#     rows = 7
#     for i in range(rows):
#         t = i / (rows - 1.0)
#         y0 = horizon - h * 0.13 + t * h * 0.115
#         shade = lerp((0x35, 0x59, 0xC0), (0x1B, 0x2E, 0x6B), t)
#         draw.rectangle([0, y0, w, y0 + h * 0.019], fill=shade)
#         # crowd speckle
#         for x in range(0, w, 7):
#             if (x * 7 + i * 13) % 5:
#                 c = ((0xFF, 0xCB, 0x05), (0xFF, 0x3B, 0x3B), (0xFF, 0xFF, 0xFF),
#                      (0x3F, 0xD6, 0x6B), (0x2F, 0xC3, 0xFF))[(x + i) % 5]
#                 draw.rectangle([x, y0 + 3, x + 3, y0 + 7], fill=c)
#     # barrier wall
#     draw.rectangle([0, horizon, w, horizon + h * 0.028],
#                    fill=(0xEF, 0xF3, 0xFF))
#     draw.rectangle([0, horizon + h * 0.028, w, horizon + h * 0.036],
#                    fill=(0x2E, 0x4F, 0xA3))


# def field(draw, w, h):
#     horizon = h * 0.536
#     # grass, lighter toward the camera
#     for y in range(int(horizon), h):
#         t = (y - horizon) / max(1.0, h - horizon)
#         draw.line([(0, y), (w, y)],
#                   fill=lerp((0x3E, 0x9E, 0x4B), (0x76, 0xD1, 0x63), t))
#     # mown stripes, fanning out in perspective
#     for i in range(-9, 10):
#         top_x = w * 0.5 + i * w * 0.035
#         bottom_x = w * 0.5 + i * w * 0.14
#         if i % 2:
#             continue
#         draw.polygon([(top_x, horizon), (top_x + w * 0.035, horizon),
#                       (bottom_x + w * 0.14, h), (bottom_x, h)],
#                      fill=(0x55, 0xB4, 0x55))
#     # the two battle circles
#     for cx, cy, rx in ((0.31, 0.80, 0.185), (0.70, 0.645, 0.125)):
#         box = [w * (cx - rx), h * cy - h * rx * 0.34,
#                w * (cx + rx), h * cy + h * rx * 0.34]
#         draw.ellipse(box, outline=(0xF2, 0xF6, 0xFF), width=6)
#         draw.ellipse([box[0] + 14, box[1] + 8, box[2] - 14, box[3] - 8],
#                      outline=(0xC9, 0xDC, 0xFF), width=3)
#     # centre line
#     draw.line([(0, horizon + h * 0.10), (w, horizon + h * 0.10)],
#               fill=(0xE8, 0xEF, 0xFF), width=3)


# def lights(draw, w, h):
#     for fx in (0.30, 0.70):
#         x = w * fx
#         draw.rectangle([x - 4, h * 0.10, x + 4, h * 0.40],
#                        fill=(0x1B, 0x2E, 0x6B))
#         head = [x - 74, h * 0.055, x + 74, h * 0.115]
#         draw.rounded_rectangle(head, radius=10, fill=(0x22, 0x3A, 0x80))
#         for i in range(4):
#             for j in range(2):
#                 lx = head[0] + 14 + i * 34
#                 ly = head[1] + 12 + j * 22
#                 draw.ellipse([lx, ly, lx + 22, ly + 16],
#                              fill=(0xFF, 0xF4, 0xC2))


# def poles(draw, w, h):
#     for fx in POLES:
#         x = w * fx
#         draw.rectangle([x - 3, h * POLE_TOP, x + 3, h * POLE_BASE],
#                        fill=(0xE7, 0xED, 0xFB))
#         draw.ellipse([x - 9, h * POLE_TOP - 9, x + 9, h * POLE_TOP + 9],
#                      fill=(0xFF, 0xCB, 0x05))


# def glow(image, w, h):
#     layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
#     draw = ImageDraw.Draw(layer)
#     draw.ellipse([w * 0.18, -h * 0.22, w * 0.82, h * 0.36],
#                  fill=(255, 240, 190, 70))
#     image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(70)))


def main():
    w, h = SIZE
    image = Image.new("RGBA", SIZE, (0, 0, 0, 255))
    # draw = ImageDraw.Draw(image)
    # sky(draw, w, h)
    # clouds(image, w, h)
    # draw = ImageDraw.Draw(image)
    # lights(draw, w, h)
    # stands(draw, w, h)
    # field(draw, w, h)
    # poles(draw, w, h)
    # glow(image, w, h)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    image.convert("RGB").save(OUT)
    print("wrote %s (%dx%d)" % (OUT, w, h))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
