"""The career tracks are found on disk, not listed in code.

main.py used to pick one with `random.randint(1, 6)`. The range was written
down in the source, so a seventh file would never have been played and a
missing one would have been a crash mid-career. These checks are what stops
that reappearing: the folder is the list.

    python Test/gui/test_music_tracks.py <root> <out>
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from Scripts.Art.music import (START_FALLBACK, MUSIC_DIR,      # noqa: E402
                               start_track, start_tracks)

fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


tracks = start_tracks()
names = [os.path.basename(path) for path in tracks]
print("found: %s" % ", ".join(names))

check("the shipped tracks are found", len(tracks) >= 1)
check("every one is a real file", all(os.path.exists(p) for p in tracks))
check("all are start<n>.mp3",
      all(n.startswith("start") and n.endswith(".mp3") for n in names))

# numeric order, not alphabetical: start10 must not sort between 1 and 2
numbers = [int(n[len("start"):-len(".mp3")]) for n in names]
check("sorted by number", numbers, sorted(numbers))

# a track is only ever picked from what is there
picks = {start_track() for _ in range(200)}
check("every pick is one of the files", picks <= set(tracks))
check("more than one gets picked", len(picks) > 1 if len(tracks) > 1 else True)

# an empty folder falls back rather than raising -- this runs mid-career
missing = os.path.join(ROOT, "Test", "gui", "_no_such_music_dir")
check("an empty folder gives the fallback",
      os.path.basename(start_track(missing)), START_FALLBACK)

# the discovery is what main.py uses, so nothing may hard-code the range again
source = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
# code lines only: the comment there explains what the range used to be, and
# matching on it would fail for saying so
code = [line.split("#")[0] for line in source.splitlines()]
check("main.py does not hard-code the count",
      not any("randint" in line for line in code))
check("main.py asks for a track by name", "start_track()" in source)

# the numbered files live where the loader looks
check("the folder the loader reads is the one they are in",
      os.path.isdir(os.path.join(ROOT, MUSIC_DIR)))

print("\n%s" % ("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(fails)))
sys.exit(1 if fails else 0)
