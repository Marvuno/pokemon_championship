"""
Pre-scale the downloaded Pokemon sprites so the game stops enlarging them.

The arena draws a Pokemon around 215px tall. The sprites pulled from
projectpokemon.org are 34-217px (about 90 on average), so most were being
blown up 2-3x at runtime -- and Qt scales a QMovie smoothly, which turns
crisp pixel art into mush. That is the blur.

Scaling here instead fixes it twice over: nearest-neighbour keeps every pixel
a hard square the way pixel art is meant to enlarge, and the result is close
enough to the on-screen size that Qt is left doing a small downscale rather
than a large upscale.

Only sprites that would still be enlarged get touched, and never past
MAX_EDGE. Frame timings, looping and transparency are all preserved, so
animated sprites keep animating. Originals are copied to
Assets/pokemon/_presharpen first.

    python Test/sharpen_sprites.py --dry-run    # report, change nothing
    python Test/sharpen_sprites.py              # do it
"""

import argparse
import math
import os
import shutil

from PIL import Image, ImageSequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDES = ("left", "right")
BACKUP = os.path.join(ROOT, "Assets", "pokemon", "_presharpen")

#: the biggest box the arena fits a Pokemon into -- the player's side in
#: borderless mode, with a little headroom
TARGET_EDGE = 215
#: never produce a sprite bigger than this -- a few of the downloaded ones are
#: already large and do not need help
MAX_EDGE = 320


def factor_for(size):
    """Whole-number scale that gets this sprite up near TARGET_EDGE.

    Whole numbers only: a fractional nearest-neighbour scale gives some rows
    two pixels and others one, which reads as a wobble along every edge.
    """
    longest = max(size)
    if longest <= 0 or longest >= TARGET_EDGE:
        return 1
    # Round *up*, not to nearest: rounding to nearest left anything from
    # roughly 144px to 214px on a factor of 1, so those sprites were still
    # being enlarged at runtime -- the whole point of this pass.
    factor = max(1, int(math.ceil(TARGET_EDGE / float(longest))))
    while factor > 1 and longest * factor > MAX_EDGE:
        factor -= 1
    return factor


def rescale(path, factor):
    """Rewrite the GIF at factor x, nearest-neighbour, frames intact."""
    original = Image.open(path)
    durations, frames = [], []
    for frame in ImageSequence.Iterator(original):
        durations.append(frame.info.get("duration", original.info.get(
            "duration", 100)))
        rgba = frame.convert("RGBA")
        big = rgba.resize((rgba.width * factor, rgba.height * factor),
                          Image.NEAREST)
        # Rebuild the palette per frame with index 255 held back for
        # transparency, the same shape the custom-sprite builder writes.
        alpha = big.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
        flat = Image.new("RGBA", big.size, (0, 0, 0, 0))
        flat.paste(big, mask=alpha)
        quantised = flat.convert("RGB").quantize(colors=255,
                                                 method=Image.MEDIANCUT)
        quantised.paste(255, mask=alpha.point(lambda v: 255 - v))
        frames.append(quantised)

    loop = original.info.get("loop", 0)
    frames[0].save(path, "GIF", save_all=True, append_images=frames[1:],
                   duration=durations, loop=loop, transparency=255,
                   disposal=2, optimize=False)
    return len(frames)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change and stop")
    args = parser.parse_args()

    todo = []
    for side in SIDES:
        folder = os.path.join(ROOT, "Assets", "pokemon", side)
        for name in sorted(os.listdir(folder)):
            if not name.lower().endswith(".gif"):
                continue
            path = os.path.join(folder, name)
            with Image.open(path) as image:
                size, frames = image.size, getattr(image, "n_frames", 1)
            factor = factor_for(size)
            if factor > 1:
                todo.append((path, size, factor, frames))

    print("%d sprite files would be enlarged at runtime" % len(todo))
    if todo:
        biggest = max(f for _, _, f, _ in todo)
        print("scale factors in use: %s"
              % sorted({f for _, _, f, _ in todo}))
        print("largest factor: %dx" % biggest)
    if args.dry_run:
        for path, size, factor, frames in todo[:8]:
            print("   %-46s %sx%s -> %dx  (%d frames)"
                  % (os.path.basename(path), size[0], size[1], factor, frames))
        print("\n--dry-run: nothing written")
        return

    os.makedirs(BACKUP, exist_ok=True)
    done = 0
    for path, size, factor, _ in todo:
        keep = os.path.join(BACKUP, os.path.basename(path))
        if not os.path.exists(keep):
            shutil.copy2(path, keep)
        try:
            rescale(path, factor)
            done += 1
        except Exception as exc:
            # put the original back rather than leave a broken sprite
            shutil.copy2(keep, path)
            print("   FAILED %s: %s" % (os.path.basename(path), exc))
    print("\n%d of %d rewritten; originals in %s" % (done, len(todo), BACKUP))


if __name__ == "__main__":
    main()
