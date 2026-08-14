"""The log is a plain-text transcript: no drawn frames, no block letters,
and every ruled row rewritten as its columns."""
import os
import sys

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from GUI import bridge as B                                       # noqa: E402
from Scripts.Game.single_elimination_bracket import EntryBox      # noqa: E402

NL = chr(10)
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


box = EntryBox(1, "Expert Cynthia", "A", 346).structure
check("a bracket entry becomes one plain row",
      B.for_log(box), "1  Expert Cynthia  A  346")
check("...so its three drawn lines become one",
      len(B.for_log(box).split(NL)), 1)
check("an empty entry disappears entirely",
      B.for_log(EntryBox().structure).strip(), "")

# the block-letter title: every line is drawing characters, nothing survives
TITLE = (chr(9608) * 6 + "\u2554" + "\u2550" * 2 + chr(9608) * 2 + "\u2557" + NL
         + "\u255a" + "\u2550" * 5 + "\u255d" + NL)
check("the block-letter title goes", B.for_log(TITLE).strip(), "")
check("a bare rule goes", B.for_log("=" * 40).strip(), "")
check("...and so does a dashed one", B.for_log("-" * 30).strip(), "")

KEEP = ["Garchomp used Earthquake.", "Super effective!", "STAB!", "Turn 3",
        "Marvin sent out Milotic.", "The Sky is Clear. [Clear]",
        "Effective.", "1: Battle || 2: View My Pokemon"]
check("narration is untouched, byte for byte",
      [k for k in KEEP if B.for_log(k) != k], [])

mixed = "Round 2" + NL + box + NL + "Garchomp used Earthquake."
check("a mixed chunk keeps its order",
      B.for_log(mixed),
      "Round 2" + NL + "1  Expert Cynthia  A  346" + NL
      + "Garchomp used Earthquake.")

# colour must not defeat the detector
RED = "\x1b[31m"
END = "\x1b[0m"
check("a coloured frame is still a frame",
      B.for_log(RED + "\u2554" + "=" * 4 + "\u2557" + END).strip(), "")
check("a coloured row still flattens",
      B.for_log(RED + "\u2551 7 \u2551 Steven \u2551" + END),
      "7  Steven")

# capture() must still see the artwork -- the title screen renders it
bridge = B.Bridge.__new__(B.Bridge)
bridge._capture_stack = [[]]
bridge._quiet = False
bridge.stopping = False
buf = bridge._capture_stack[0]
try:
    bridge._write(box)
except Exception:
    pass
check("capture() still gets the drawn version",
      buf and "\u2554" in buf[0], True)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
