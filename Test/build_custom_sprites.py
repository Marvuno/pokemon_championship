"""
Turn the hand-drawn custom Pokemon artwork into game sprites.

Assets/pokemon/custom holds one 1024x1024 JPEG per custom Pokemon: pixel art
standing on a near-white ground. The game wants a small GIF with real
transparency, facing each way. This does that conversion:

    white ground -> transparent   (flood-filled from the border, so white
                                   *inside* the art -- eyes, highlights,
                                   bandages -- is kept)
    crop to content               (no wasted canvas, so the sprite sits where
                                   the arena puts it rather than floating)
    fit into 256x256              (the arena draws a Pokemon around 215px
                                   tall, so anything smaller is being
                                   *upscaled* on screen -- which is what made
                                   the hand-drawn Pokemon look soft next to
                                   the downloaded ones. At 256 the game is
                                   always scaling down.)
    save as GIF                   (binary transparency, one reserved index)

Names come from the filename and go through GUI/bridge.py's sprite_key(), the
same mapping the game uses to find a sprite, so "Krusadian Flygon.jpg" lands
on flygon-krusades-right.gif. Whatever is replaced is copied into
Assets/pokemon/_replaced first.

    python Test/build_custom_sprites.py              # convert everything
    python Test/build_custom_sprites.py --sheet      # preview, writes no
                                                     # game files
    python Test/build_custom_sprites.py --size 96    # a different canvas
    python Test/build_custom_sprites.py --flip       # art as drawn faces left
"""

import argparse
import csv
import os
import shutil
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from GUI.bridge import sprite_key                          # noqa: E402

SOURCE = os.path.join(ROOT, "Assets", "pokemon", "custom")
LEFT = os.path.join(ROOT, "Assets", "pokemon", "left")
RIGHT = os.path.join(ROOT, "Assets", "pokemon", "right")
BACKUP = os.path.join(ROOT, "Assets", "pokemon", "_replaced")

#: How close to white counts as background. The art is drawn on 254,254,254
#: and JPEG ringing smears that by a few levels around the outline, so this
#: has to be loose enough to catch the halo but tight enough to keep pale
#: art -- Snowchild and Twinktwin are nearly white themselves, which is why
#: the fill starts from the border instead of keying every white pixel.
WHITE_FLOOR = 236
#: GIF transparency is all-or-nothing, so soft edges have to land one side
#: or the other.
ALPHA_CUTOFF = 128

#: Artwork filename -> the name in Data/pokemon.csv, where the two disagree.
#: Without this the sprite is written under a key the game never asks for, so
#: the Pokemon silently shows up as a text fallback.
ALIASES = {
    "Chamorin": "Charmorin",
}


def load_names():
    """Pokemon names the game knows, for checking the filenames resolve."""
    path = os.path.join(ROOT, "Data", "pokemon.csv")
    with open(path, encoding="ISO-8859-1") as handle:
        return {row["Name"] for row in csv.DictReader(handle)}


def cut_background(image):
    """RGBA copy with the white ground made transparent.

    ImageDraw.floodfill from every border pixel, rather than a straight
    "is it white" test: it follows the ground in from the edge and stops at
    the artwork, so white *within* the sprite survives.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    # Work on a mask rather than the picture: fill a scratch copy with a
    # colour that cannot occur in the art, then read back which pixels moved.
    scratch = rgb.copy()
    marker = (255, 0, 255)
    seen = set()
    for x in range(width):
        for y in (0, height - 1):
            seen.add((x, y))
    for y in range(height):
        for x in (0, width - 1):
            seen.add((x, y))
    for point in seen:
        pixel = scratch.getpixel(point)
        if pixel == marker:
            continue
        if min(pixel) >= WHITE_FLOOR:
            ImageDraw.floodfill(scratch, point, marker,
                                thresh=255 - WHITE_FLOOR)

    out = image.convert("RGBA")
    pixels = out.load()
    filled = scratch.load()
    for y in range(height):
        for x in range(width):
            if filled[x, y] == marker:
                pixels[x, y] = (0, 0, 0, 0)
    return out


def fit(image, size):
    """Crop to the artwork and centre it on a transparent size x size canvas."""
    box = image.getbbox()
    if box:
        image = image.crop(box)
    image.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(image,
                 ((size - image.width) // 2, (size - image.height) // 2))
    return canvas


def to_gif_frame(image):
    """Palette image plus the transparent index, ready for GIF."""
    alpha = image.getchannel("A").point(
        lambda value: 255 if value >= ALPHA_CUTOFF else 0)
    flat = Image.new("RGBA", image.size, (0, 0, 0, 0))
    flat.paste(image, mask=alpha)
    # 255 colours, leaving index 255 free to mean "transparent"
    quantised = flat.convert("RGB").quantize(colors=255, method=Image.MEDIANCUT)
    quantised.paste(255, mask=alpha.point(lambda v: 255 - v))
    return quantised


def save_gif(image, path):
    frame = to_gif_frame(image)
    frame.save(path, "GIF", transparency=255, optimize=False, disposal=2)


def backup(path):
    if not os.path.exists(path):
        return
    os.makedirs(BACKUP, exist_ok=True)
    shutil.copy2(path, os.path.join(BACKUP, os.path.basename(path)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=256,
                        help="sprite canvas, square (default 256)")
    parser.add_argument("--sheet", action="store_true",
                        help="write a preview sheet and no game files")
    parser.add_argument("--flip", action="store_true",
                        help="the art as drawn faces left, not right")
    args = parser.parse_args()

    known = load_names()
    sources = sorted(f for f in os.listdir(SOURCE)
                     if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if not sources:
        raise SystemExit("no artwork in %s" % SOURCE)

    os.makedirs(LEFT, exist_ok=True)
    os.makedirs(RIGHT, exist_ok=True)

    done, unknown, previews = 0, [], []
    for filename in sources:
        name = ALIASES.get(os.path.splitext(filename)[0],
                           os.path.splitext(filename)[0])
        if name not in known:
            unknown.append(os.path.splitext(filename)[0])
        key = sprite_key(name)
        art = cut_background(Image.open(os.path.join(SOURCE, filename)))
        sprite = fit(art, args.size)
        previews.append((name, sprite))

        if args.sheet:
            continue
        drawn, mirrored = ((LEFT, "left"), (RIGHT, "right")) if args.flip \
            else ((RIGHT, "right"), (LEFT, "left"))
        for folder, side, picture in (
                (drawn[0], drawn[1], sprite),
                (mirrored[0], mirrored[1],
                 sprite.transpose(Image.FLIP_LEFT_RIGHT))):
            path = os.path.join(folder, "%s-%s.gif" % (key, side))
            backup(path)
            save_gif(picture, path)
        done += 1
        print("%-28s -> %s-{left,right}.gif" % (name, key))

    if args.sheet:
        columns = 8
        rows = (len(previews) + columns - 1) // columns
        cell = args.size + 8
        sheet = Image.new("RGBA", (columns * cell, rows * cell),
                          (24, 32, 46, 255))
        for index, (_, picture) in enumerate(previews):
            sheet.alpha_composite(
                picture, ((index % columns) * cell + 4,
                          (index // columns) * cell + 4))
        out = os.path.join(ROOT, "Test", "custom_sprite_sheet.png")
        sheet.save(out)
        print("preview written to %s (%d sprites, no game files touched)"
              % (out, len(previews)))
    else:
        print("\n%d Pokemon written at %dx%d; replaced files copied to %s"
              % (done, args.size, args.size, BACKUP))

    if unknown:
        print("\nNOT in Data/pokemon.csv -- check the spelling, these will "
              "never be looked up:")
        for name in unknown:
            print("   %s" % name)


if __name__ == "__main__":
    main()
