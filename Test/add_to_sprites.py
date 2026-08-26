"""Turn Assets/pokemon/to-add into the game's left/right sprite pairs.

Drop artwork into `Assets/pokemon/to-add` named after the Pokemon -- as it is
written in Data/pokemon.csv, or close enough that the name resolves -- and run
this. Each file becomes the two GIFs the arena wants:

    Assets/pokemon/right/<key>-right.gif   the artwork as drawn
    Assets/pokemon/left/<key>-left.gif     the mirror of it

which is the same split `image_builder.py` and `import_custom_sprites.py`
make, so the two sides face each other across the battlefield.

    python Test/add_to_sprites.py                 do it
    python Test/add_to_sprites.py --dry-run       say what it would do
    python Test/add_to_sprites.py --keep          leave to-add alone

Four steps per picture, and each is there for a reason:

**Key out a flat background.** A JPEG has no alpha, and pasting one into the
arena puts a white rectangle behind the Pokemon. The fill is flood-filled
*from the edges* rather than removed globally: a global "delete white"
punches holes through every white part of the sprite -- Mega Scizor's
highlights, a Pokemon that is mostly white -- whereas the flood only reaches
background actually connected to the border.

**Crop to the artwork.** Sources arrive padded to a square. The arena scales
a sprite to fill its slot, so a picture that is 60% padding is drawn 40%
smaller than its neighbours for no reason anyone can see. The bounding box of
the alpha channel is the real picture.

**Sharpen.** Everything here is scaled, and scaling softens. A mild unsharp
mask puts the edge back without the halo a stronger one leaves on pixel art.

**Save as a transparent GIF.** `quantize(colors=255)` leaves index 255 free,
which becomes the transparent one -- the same trick the rest of the sprites
use. Quantising to a full 256 and then declaring one of them transparent
punches a hole in whatever colour happened to land on that index.
"""
import argparse
import os
import shutil
import sys

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

SOURCE = os.path.join("Assets", "pokemon", "to-add")
RIGHT = os.path.join("Assets", "pokemon", "right")
LEFT = os.path.join("Assets", "pokemon", "left")
#: where a replaced sprite goes, so a bad import can be undone
BACKUP = os.path.join("Assets", "pokemon", "_replaced")

#: how tall a finished sprite is. The existing ones run 30..320 with a median
#: of 201, so this sits them among their neighbours rather than towering over
#: them or disappearing.
TARGET_HEIGHT = 200
#: nothing is scaled past this, so a small source is not blown up into mush
MAX_UPSCALE = 2.0
#: how far from the border colour still counts as background, per channel.
#: JPEG ringing means the white around the subject is not exactly 255.
BACKGROUND_TOLERANCE = 26
#: a mild unsharp mask -- enough to undo the softening from scaling, not
#: enough to ring
SHARPEN = dict(radius=1.4, percent=115, threshold=3)


def resolve(stem, roster, sprite_key):
    """Which Pokemon this filename is for, or None.

    Tolerant, because a downloaded file is named however the source named it:
    "scizor-mega.jpg" is Mega Scizor, whose key is "mega-scizor". Matching on
    the *set* of words rather than their order is what catches that without a
    table of special cases.
    """
    flat = stem.lower().replace("_", "-").replace(" ", "-")
    words = frozenset(part for part in flat.split("-") if part)
    for name in roster:
        key = sprite_key(name)
        if key == flat or name.lower() == stem.lower():
            return name, key
        if frozenset(part for part in key.split("-") if part) == words:
            return name, key
    return None, None


def key_out_background(picture):
    """Flood the flat border colour away, leaving the subject alone."""
    picture = picture.convert("RGBA")
    width, height = picture.size
    pixels = picture.load()
    corner = pixels[0, 0][:3]

    def is_background(spot):
        return all(abs(a - b) <= BACKGROUND_TOLERANCE
                   for a, b in zip(pixels[spot][:3], corner))

    seen = set()
    edge = ([(x, 0) for x in range(width)]
            + [(x, height - 1) for x in range(width)]
            + [(0, y) for y in range(height)]
            + [(width - 1, y) for y in range(height)])
    stack = [spot for spot in edge if is_background(spot)]
    seen.update(stack)
    while stack:
        x, y = stack.pop()
        pixels[x, y] = (0, 0, 0, 0)
        for spot in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (0 <= spot[0] < width and 0 <= spot[1] < height
                    and spot not in seen and is_background(spot)):
                seen.add(spot)
                stack.append(spot)
    return picture


def prepare(path):
    """One source file -> the finished RGBA picture, facing as drawn."""
    picture = Image.open(path)
    if "A" not in picture.getbands():
        picture = key_out_background(picture)
    else:
        picture = picture.convert("RGBA")

    box = picture.getbbox()            # the alpha bounding box
    if box:
        picture = picture.crop(box)

    scale = TARGET_HEIGHT / float(picture.height)
    scale = min(scale, MAX_UPSCALE)
    if abs(scale - 1.0) > 0.01:
        picture = picture.resize(
            (max(1, int(round(picture.width * scale))),
             max(1, int(round(picture.height * scale)))),
            Image.LANCZOS)

    # Sharpen the colour, not the alpha: an unsharp mask on the alpha channel
    # frills the outline.
    alpha = picture.getchannel("A")
    body = picture.convert("RGB").filter(ImageFilter.UnsharpMask(**SHARPEN))
    picture = body.convert("RGBA")
    picture.putalpha(alpha)
    return picture


def save_gif(picture, path):
    """A transparent GIF, with index 255 reserved for the transparency."""
    # Hard-edge the alpha first. A GIF has one transparent index and no
    # partial transparency, so a soft edge would otherwise be quantised into
    # a fringe of near-background colour around the sprite.
    alpha = picture.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    flat = Image.new("RGBA", picture.size, (0, 0, 0, 0))
    flat.paste(picture, mask=alpha)
    quantised = flat.convert("RGB").quantize(colors=255)
    quantised.paste(255, mask=alpha.point(lambda v: 255 - v))
    quantised.info["transparency"] = 255
    os.makedirs(os.path.dirname(path), exist_ok=True)
    quantised.save(path, transparency=255, optimize=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would happen and change nothing")
    parser.add_argument("--keep", action="store_true",
                        help="leave the to-add folder as it is")
    args = parser.parse_args()

    import Scripts.Battle.battle_cycle                            # noqa: F401
    from GUI.codex import sprite_key
    from Scripts.Data.pokemon import list_of_pokemon

    if not os.path.isdir(SOURCE):
        print("nothing to do: %s does not exist" % SOURCE)
        return 0
    files = [f for f in sorted(os.listdir(SOURCE))
             if os.path.splitext(f)[1].lower() in
             (".png", ".jpg", ".jpeg", ".gif", ".webp")]
    if not files:
        print("nothing to do: %s is empty" % SOURCE)
        return 0

    done, unmatched = [], []
    for filename in files:
        stem = os.path.splitext(filename)[0]
        name, key = resolve(stem, list_of_pokemon, sprite_key)
        if name is None:
            unmatched.append(filename)
            print("  %-24s no Pokemon of that name -- left in place"
                  % filename)
            continue
        source = os.path.join(SOURCE, filename)
        right_path = os.path.join(RIGHT, "%s-right.gif" % key)
        left_path = os.path.join(LEFT, "%s-left.gif" % key)
        if args.dry_run:
            print("  %-24s -> %s / %s" % (filename, right_path, left_path))
            done.append(filename)
            continue

        for existing in (right_path, left_path):
            if os.path.exists(existing):
                os.makedirs(BACKUP, exist_ok=True)
                shutil.copy2(existing,
                             os.path.join(BACKUP, os.path.basename(existing)))

        picture = prepare(source)
        save_gif(picture, right_path)
        save_gif(picture.transpose(Image.FLIP_LEFT_RIGHT), left_path)
        print("  %-24s -> %-22s %dx%d" % (filename, name + ",",
                                          picture.width, picture.height))
        done.append(filename)

    if done and not args.dry_run and not args.keep and not unmatched:
        for filename in done:
            os.remove(os.path.join(SOURCE, filename))
        print("emptied %s" % SOURCE)
    elif unmatched:
        print("left %s alone: %d file(s) did not match a Pokemon"
              % (SOURCE, len(unmatched)))

    print("%d sprite pair(s) written" % len(done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
