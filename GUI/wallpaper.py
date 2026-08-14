"""
A generated title-screen backdrop.

This is original, abstract stadium-at-night artwork -- floodlights, a crowd
silhouette, a bracket-shaped skyline -- built with plain drawing primitives.
It deliberately depicts no Pokemon, no franchise logos and no licensed
character art; the game's own sprites and cover art already cover that, and
this only needs to set a mood behind the welcome panel.

Rendered once to disk on first run and reused after that. If Pillow is not
installed, callers get None and fall back to the flat panel colour --
the same graceful-degradation rule the sprite loader follows.
"""

import math
import os
import random

try:
    from PIL import Image, ImageDraw, ImageFilter
    HAVE_PILLOW = True
except Exception:                                        # pragma: no cover
    HAVE_PILLOW = False

WIDTH, HEIGHT = 1920, 1080
CACHE_REL = os.path.join("Assets", "generated", "title_wallpaper.png")

SKY_TOP = (7, 10, 20)
SKY_MID = (12, 20, 42)
SKY_LOW = (20, 32, 58)
GLOW = (245, 185, 66)
GLOW_SOFT = (94, 200, 229)
CROWD = (10, 15, 27)
SILHOUETTE = (5, 8, 15)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _sky(draw):
    for y in range(HEIGHT):
        t = y / HEIGHT
        if t < 0.55:
            color = _lerp(SKY_TOP, SKY_MID, t / 0.55)
        else:
            color = _lerp(SKY_MID, SKY_LOW, (t - 0.55) / 0.45)
        draw.line([(0, y), (WIDTH, y)], fill=color)


def _stars(draw, rng):
    for _ in range(220):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, int(HEIGHT * 0.5))
        b = rng.randint(60, 180)
        r = rng.choice((1, 1, 1, 2))
        draw.ellipse([x, y, x + r, y + r], fill=(b, b, b + 20))


def _spotlights(base):
    """A few soft light cones, drawn on their own layer and blurred."""
    layer = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(layer)
    beams = [
        (WIDTH * 0.18, HEIGHT * 1.05, 230, GLOW),
        (WIDTH * 0.5, HEIGHT * 1.1, 300, GLOW_SOFT),
        (WIDTH * 0.85, HEIGHT * 1.05, 230, GLOW),
    ]
    for cx, cy, spread, color in beams:
        for i in range(40, 0, -1):
            t = i / 40
            w = spread * t
            top_y = cy - HEIGHT * 1.35 * t
            draw.polygon(
                [(cx - w * 0.05, cy), (cx + w * 0.05, cy),
                 (cx + w, top_y), (cx - w, top_y)],
                fill=tuple(int(c * (1 - t) * 0.35) for c in color))
    return layer.filter(ImageFilter.GaussianBlur(40))


def _skyline(draw, rng):
    """A bracket/podium-inspired silhouette, not any specific building."""
    base_y = int(HEIGHT * 0.78)
    x = -40
    while x < WIDTH + 40:
        w = rng.randint(70, 160)
        h = rng.randint(int(HEIGHT * 0.05), int(HEIGHT * 0.22))
        draw.rectangle([x, base_y - h, x + w, base_y + 40], fill=SILHOUETTE)
        # a lit window or two, echoing a scoreboard without being one
        if rng.random() < 0.5:
            wx = x + rng.randint(10, max(11, w - 24))
            wy = base_y - rng.randint(10, max(11, h - 10))
            draw.rectangle([wx, wy, wx + 10, wy + 16],
                           fill=(70, 90, 60) if rng.random() < 0.3
                           else (60, 70, 100))
        x += w + rng.randint(4, 18)

    # foreground crowd bowl: a simple curved silhouette across the bottom
    bowl_top = int(HEIGHT * 0.86)
    points = [(0, HEIGHT)]
    for i in range(0, WIDTH + 1, 40):
        wobble = 10 * math.sin(i / 90) + rng.randint(-4, 4)
        points.append((i, bowl_top + wobble))
    points.append((WIDTH, HEIGHT))
    draw.polygon(points, fill=CROWD)


def _particles(draw, rng):
    for _ in range(90):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(int(HEIGHT * 0.3), int(HEIGHT * 0.85))
        r = rng.choice((1, 1, 2))
        a = rng.randint(40, 130)
        color = GLOW if rng.random() < 0.5 else GLOW_SOFT
        draw.ellipse([x, y, x + r, y + r],
                     fill=tuple(int(c * a / 255) for c in color))


def generate(path):
    rng = random.Random(20260805)   # fixed seed: same mood every launch
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    _sky(draw)
    _stars(draw, rng)
    beams = _spotlights(image)
    image = Image.blend(image, Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0)),
                        0.0)
    image = Image.composite(
        Image.blend(image, beams, 1.0), image,
        Image.new("L", (WIDTH, HEIGHT), 255))
    # simpler, robust compositing: just screen-add the beam layer
    import PIL.ImageChops as ImageChops
    image = ImageChops.add(image, beams, scale=1.4)
    draw = ImageDraw.Draw(image)
    _skyline(draw, rng)
    _particles(draw, rng)
    # gentle vignette so panel text stays legible over any part of it
    vignette = Image.new("L", (WIDTH, HEIGHT), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.rectangle([0, 0, WIDTH, HEIGHT], fill=90)
    vignette = vignette.filter(ImageFilter.GaussianBlur(2))
    dark = Image.new("RGB", (WIDTH, HEIGHT), (5, 8, 14))
    image = Image.composite(dark, image, vignette.point(lambda p: int(p * 0.35)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image.save(path, "PNG")


def title_wallpaper_path(project_root):
    """Return an absolute path to a generated wallpaper, or None.

    Generates once and caches on disk; safe to call every launch.
    """
    if not HAVE_PILLOW:
        return None
    path = os.path.join(project_root, CACHE_REL)
    try:
        if not os.path.exists(path):
            generate(path)
        return path
    except Exception:
        return None
