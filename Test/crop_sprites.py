"""Trim the transparent padding off battle sprites.

`show_sprite` fits a sprite's **canvas** into the arena's box, but what a
player sees is the **content**. Measured across all 248 sprites, the creature
fills between 55% and 100% of its canvas -- so two Pokemon given the same box
draw at very different sizes for no reason anybody chose:

    arcanine    canvas 222x246  content 207x246  ->  draws 180x215
    glimmora    canvas 256x256  content 142x106  ->  draws 119x89

That is the "some look larger" part. Cropping the padding makes canvas equal
content, so the existing rule produces consistent sizes -- and it does it
*without enlarging anything*, which matters because smooth enlargement is
what turns pixel art to mush (see sharpen_sprites.py, which exists for the
other half of the same problem).

The crop box is the union across every frame, not per frame: cropping each
frame to its own content would make an animation jitter as the creature's
outline changes.

    python Test/crop_sprites.py --dry-run          report, change nothing
    python Test/crop_sprites.py                    crop everything
    python Test/crop_sprites.py glimmora slowbro   crop just these

Originals are copied to Assets/pokemon/_precrop first. Frame timings, looping
and transparency are preserved.
"""
import os
import shutil
import sys

from PIL import Image, ImageSequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDES = ("left", "right")
BACKUP = os.path.join(ROOT, "Assets", "pokemon", "_precrop")
#: leave a little air so nothing touches the very edge of its box
MARGIN = 2
#: do not bother rewriting a file that is already this tight
ENOUGH = 0.97

DRY_RUN = "--dry-run" in sys.argv
WANTED = {a.lower() for a in sys.argv[1:] if not a.startswith("--")}


def frames_of(image):
    """Every frame as RGBA, plus the durations."""
    out, durations = [], []
    for frame in ImageSequence.Iterator(image):
        out.append(frame.convert("RGBA"))
        durations.append(frame.info.get("duration", image.info.get("duration",
                                                                   100)))
    return out, durations


def union_box(frames):
    """The smallest box holding the creature in *every* frame."""
    box = None
    for frame in frames:
        here = frame.getchannel("A").getbbox()
        if here is None:
            continue
        box = here if box is None else (min(box[0], here[0]),
                                        min(box[1], here[1]),
                                        max(box[2], here[2]),
                                        max(box[3], here[3]))
    return box


def as_gif(frames, durations, path):
    """Write frames back as a GIF, keeping one colour transparent."""
    flattened = []
    for frame in frames:
        flat = frame.convert("RGB").quantize(colors=255,
                                             method=Image.MEDIANCUT)
        clear = frame.getchannel("A").point(lambda v: 255 if v <= 128 else 0)
        flat.paste(255, clear)
        flat.info["transparency"] = 255
        flattened.append(flat)
    first, rest = flattened[0], flattened[1:]
    first.save(path, save_all=True, append_images=rest, loop=0,
               duration=durations, transparency=255, disposal=2,
               optimize=False)


def main():
    reports, changed = [], 0
    for side in SIDES:
        folder = os.path.join(ROOT, "Assets", "pokemon", side)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            suffix = "-%s.gif" % side
            if not name.endswith(suffix):
                continue
            key = name[:-len(suffix)]
            if WANTED and key.lower() not in WANTED:
                continue
            path = os.path.join(folder, name)
            try:
                image = Image.open(path)
                frames, durations = frames_of(image)
            except Exception as problem:
                reports.append("  %-26s unreadable (%s)" % (key, problem))
                continue
            if not frames:
                continue
            box = union_box(frames)
            if box is None:
                continue
            canvas = frames[0].size
            wide = box[2] - box[0]
            tall = box[3] - box[1]
            tightness = max(wide, tall) / float(max(canvas))
            if tightness >= ENOUGH:
                continue
            grown = (max(0, box[0] - MARGIN), max(0, box[1] - MARGIN),
                     min(canvas[0], box[2] + MARGIN),
                     min(canvas[1], box[3] + MARGIN))
            reports.append("  %-26s %-11s -> %-11s (%.0f%% full)"
                           % (key, "%dx%d" % canvas,
                              "%dx%d" % (grown[2] - grown[0],
                                         grown[3] - grown[1]),
                              tightness * 100))
            changed += 1
            if DRY_RUN:
                continue
            os.makedirs(BACKUP, exist_ok=True)
            keep = os.path.join(BACKUP, name)
            if not os.path.exists(keep):
                shutil.copy2(path, keep)
            as_gif([frame.crop(grown) for frame in frames], durations, path)

    print("\n".join(reports[:40]))
    if len(reports) > 40:
        print("  ... and %d more" % (len(reports) - 40))
    print()
    print("%d sprite(s) %s" % (changed,
                               "would be cropped" if DRY_RUN else "cropped"))
    if not DRY_RUN and changed:
        print("originals kept in Assets/pokemon/_precrop")


if __name__ == "__main__":
    main()
