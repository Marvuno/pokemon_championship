"""
Install hand-drawn custom-Pokemon sprites from a zip (or a folder of GIFs).

The zip holds one GIF per custom Pokemon, named exactly as in
Data/pokemon.csv ("Krusadian Flygon.gif"). The game wants two copies of each,
keyed by GUI/bridge.py's sprite_key():

    Assets/pokemon/right/<key>-right.gif   the opponent's side
    Assets/pokemon/left/<key>-left.gif     your side, mirrored

which is the same split the original download tool made for the downloaded
Pokemon: the artwork as drawn goes to right/, and left/ is its mirror, so the
two sides face each other across the arena.

Whatever these replace is copied to Assets/pokemon/_replaced/ first, so a
bad import can be undone.

    python Test/import_custom_sprites.py                     # default zip
    python Test/import_custom_sprites.py path/to/sprites.zip
    python Test/import_custom_sprites.py path/to/folder --flip
"""

import os
import shutil
import sys
import tempfile
import zipfile

from PIL import Image, ImageSequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from GUI.bridge import sprite_key                # noqa: E402

DEFAULT_SOURCE = os.path.join(ROOT, "Assets", "custom-pokemon-sprites.zip")
LEFT_DIR = os.path.join(ROOT, "Assets", "pokemon", "left")
RIGHT_DIR = os.path.join(ROOT, "Assets", "pokemon", "right")
BACKUP_DIR = os.path.join(ROOT, "Assets", "pokemon", "_replaced")


def load_frames(path):
    """Every frame as RGBA, plus each frame's duration."""
    source = Image.open(path)
    frames, durations = [], []
    for frame in ImageSequence.Iterator(source):
        durations.append(frame.info.get("duration",
                                        source.info.get("duration", 120)))
        frames.append(frame.convert("RGBA"))
    return frames, durations


def save_gif(frames, durations, path):
    """Write a palette GIF, keeping full transparency.

    Index 0 is reserved for transparent and the artwork is quantised into
    the remaining 255, so a sprite can never lose a colour to the
    transparency slot or come out with a boxed background.
    """
    flats, masks = [], []
    for frame in frames:
        alpha = frame.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
        masks.append(alpha)
        flats.append(frame.convert("RGB"))

    montage = Image.new("RGB", (flats[0].width, flats[0].height * len(flats)))
    for i, flat in enumerate(flats):
        montage.paste(flat, (0, i * flats[0].height))
    palette = montage.quantize(colors=255, method=Image.MEDIANCUT)

    converted = []
    for flat, mask in zip(flats, masks):
        indexed = flat.quantize(palette=palette, dither=Image.NONE)
        # shift every real colour up by one so index 0 means "transparent"
        indexed = indexed.point(lambda v: min(255, v + 1))
        table = palette.getpalette()[:255 * 3]
        indexed.putpalette([0, 0, 0] + table)
        indexed.paste(0, (0, 0), Image.eval(mask, lambda v: 255 - v))
        converted.append(indexed)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    converted[0].save(path, save_all=True, append_images=converted[1:],
                      duration=durations, loop=0, transparency=0,
                      disposal=2, optimize=False)


def collect(source):
    """Return {name: path} for a zip or a folder of GIFs, unpacking if needed."""
    if os.path.isdir(source):
        return {os.path.splitext(f)[0]: os.path.join(source, f)
                for f in sorted(os.listdir(source))
                if f.lower().endswith(".gif")}, None
    scratch = tempfile.mkdtemp(prefix="sprites-")
    with zipfile.ZipFile(source) as archive:
        archive.extractall(scratch)
    found = {}
    for base, _, files in os.walk(scratch):
        for name in sorted(files):
            if name.lower().endswith(".gif"):
                found[os.path.splitext(name)[0]] = os.path.join(base, name)
    return found, scratch


def backup(path):
    if not os.path.exists(path):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(path, os.path.join(BACKUP_DIR, os.path.basename(path)))


def main(argv):
    flip = "--flip" in argv
    args = [a for a in argv if not a.startswith("-")]
    source = args[0] if args else DEFAULT_SOURCE
    if not os.path.exists(source):
        print("No such source: %s" % source)
        return 1

    sprites, scratch = collect(source)
    if not sprites:
        print("No GIFs found in %s" % source)
        return 1

    print("Installing %d sprite(s) from %s" % (len(sprites),
                                               os.path.basename(source)))
    for name in sorted(sprites):
        key = sprite_key(name)
        frames, durations = load_frames(sprites[name])
        mirrored = [f.transpose(Image.FLIP_LEFT_RIGHT) for f in frames]
        # as-drawn on the opponent's side, mirrored on yours -- unless
        # --flip says the artwork faces the other way
        facing_right, facing_left = (frames, mirrored) if flip \
            else (mirrored, frames)

        left = os.path.join(LEFT_DIR, "%s-left.gif" % key)
        right = os.path.join(RIGHT_DIR, "%s-right.gif" % key)
        backup(left)
        backup(right)
        save_gif(facing_right, durations, left)
        save_gif(facing_left, durations, right)
        print("  %-22s -> %s  (%d frames, %dx%d)"
              % (name, key, len(frames), frames[0].width, frames[0].height))

    if scratch:
        shutil.rmtree(scratch, ignore_errors=True)
    print("Done. Replaced files were copied to Assets/pokemon/_replaced/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
