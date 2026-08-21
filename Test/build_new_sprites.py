"""Turn the artwork in Assets/pokemon/to_add into game sprites.

    python Test/build_new_sprites.py            convert everything
    python Test/build_new_sprites.py --dry-run  say what it would write
    python Test/build_new_sprites.py --size 256 a different canvas

Separate from build_custom_sprites.py because the input is different in a way
that matters. That script takes 1024px JPEGs of pixel art standing on a
near-white ground and has to flood-fill the background away; these are already
256px RGBA PNGs with real transparency, so flood-filling would be at best
pointless and at worst would eat pixels that are meant to be there. What is
left is the part both need: crop to content, fit the canvas, mirror for the
other side, and save a GIF with one transparent index.

Sizing follows the same reasoning as the other script. The arena draws a
Pokemon around 215px tall, so a 256px source is always being scaled *down* on
screen, which is what keeps it sharp -- see the DPR note in GUI_qt/sprites.py.
Names go through GUI/bridge.py's sprite_key(), the same mapping the game uses
to find a sprite, so the file lands where show_sprite() will look for it.
"""
import argparse
import os
import shutil
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SOURCE = os.path.join(ROOT, "Assets", "pokemon", "to_add")
LEFT = os.path.join(ROOT, "Assets", "pokemon", "left")
RIGHT = os.path.join(ROOT, "Assets", "pokemon", "right")
REPLACED = os.path.join(ROOT, "Assets", "pokemon", "_replaced")
#: the index GIF frames reserve for "see through this" -- what the existing
#: sprites use, so the game's loader needs no special case
TRANSPARENT_INDEX = 255


def crop_to_content(art):
    """Drop empty margin, so the sprite sits where the arena puts it rather
    than floating inside its own padding."""
    if art.mode != "RGBA":
        art = art.convert("RGBA")
    box = art.split()[-1].getbbox()          # bounding box of the alpha
    return art.crop(box) if box else art


def fit(art, size):
    """Longest edge to `size`, aspect kept, centred on a clear canvas.

    Never enlarged: a source smaller than the canvas is left at its own size,
    because upscaling pixel art is the one thing that turns it to mush.
    """
    scale = min(1.0, float(size) / max(art.size))
    if scale < 1.0:
        art = art.resize((max(1, round(art.width * scale)),
                          max(1, round(art.height * scale))),
                         Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(art, ((size - art.width) // 2, (size - art.height) // 2))
    return canvas


def to_gif_frame(art):
    """RGBA -> palette image with one fully transparent index.

    The alpha is thresholded rather than dithered: GIF has no partial
    transparency, so a soft edge has to become either drawn or not, and
    guessing halfway leaves a grey fringe against the arena.
    """
    opaque = art.split()[-1].point(lambda value: 255 if value > 127 else 0)
    flat = Image.new("RGB", art.size, (0, 0, 0))
    flat.paste(art.convert("RGB"), mask=opaque)
    palette = flat.convert("P", palette=Image.ADAPTIVE, colors=255)
    # every see-through pixel moves to the reserved index
    palette.paste(TRANSPARENT_INDEX,
                  mask=opaque.point(lambda value: 255 - value))
    return palette


def save(art, path, dry_run):
    if dry_run:
        print("    would write %s" % os.path.relpath(path, ROOT))
        return
    if os.path.exists(path):
        os.makedirs(REPLACED, exist_ok=True)
        shutil.copy2(path, os.path.join(REPLACED, os.path.basename(path)))
    art.save(path, "GIF", transparency=TRANSPARENT_INDEX, optimize=False)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Assets/pokemon/to_add into left/right sprites.")
    parser.add_argument("--size", type=int, default=256,
                        help="canvas edge in pixels (default 256)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report without writing anything")
    parser.add_argument("--flip", action="store_true",
                        help="the art as drawn faces left, not right")
    args = parser.parse_args()

    from GUI import codex                                      # noqa: E402

    if not os.path.isdir(SOURCE):
        raise SystemExit("no such folder: %s" % SOURCE)
    names = sorted(f for f in os.listdir(SOURCE)
                   if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
    if not names:
        raise SystemExit("no artwork in %s" % SOURCE)

    for folder in (LEFT, RIGHT):
        if not args.dry_run:
            os.makedirs(folder, exist_ok=True)

    written = 0
    for filename in names:
        stem = os.path.splitext(filename)[0]
        key = codex.sprite_key(stem)
        art = fit(crop_to_content(Image.open(os.path.join(SOURCE, filename))),
                  args.size)
        # The arena's "left" sprite is your own, seen from behind-ish, and
        # "right" is the opponent's. One of them is the art as drawn and the
        # other is its mirror; --flip says which way round that is.
        facing = {"right": art, "left": art.transpose(Image.FLIP_LEFT_RIGHT)}
        if args.flip:
            facing = {"left": art, "right": art.transpose(Image.FLIP_LEFT_RIGHT)}
        print("%-18s -> %s" % (filename, key))
        for side, picture in facing.items():
            target = os.path.join(LEFT if side == "left" else RIGHT,
                                  "%s-%s.gif" % (key, side))
            save(to_gif_frame(picture), target, args.dry_run)
            written += 0 if args.dry_run else 1

    print()
    print("%d sprite file(s) %s"
          % (written if not args.dry_run else len(names) * 2,
             "written" if not args.dry_run else "would be written"))


if __name__ == "__main__":
    main()
