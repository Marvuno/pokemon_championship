"""A "TURN n" rule belongs in a battle and nowhere else.

The reported symptom was stray lines in the play area once all the matchups
had ended. Nothing was being left behind -- something new was being drawn at
the wrong time. `_track_feed_worthy_changes` emits a turn divider whenever
the turn number differs from the last one it saw, and it runs on *every*
state publish. The engine keeps a turn number on record after a match is
over, so the moment it changed on a management screen a rule was drawn
across the feed among the run-summary entries.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

sys.path.insert(0, os.path.join(ROOT, "Test", "gui"))
import saveguard                                                   # noqa: E402
saveguard.install(ROOT, os.path.join(ROOT, "Test", "gui", "_out"),
                  tag="feed_dividers")

from PySide6.QtWidgets import QApplication                          # noqa: E402

app = QApplication.instance() or QApplication([])

from GUI_qt.main_window import MainWindow, BATTLE_PHASES            # noqa: E402
from GUI_qt.widgets import TurnDivider                              # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


w = MainWindow(ROOT)
w.show()


def dividers():
    return len(w.feed_scroll.findChildren(TurnDivider))


def feed(turn, phase):
    w._track_feed_worthy_changes({"turn": turn}, phase)


print("-- inside a battle --")
w._clear_feed()
start = dividers()
feed(1, "battle")
check("turn 1 draws a rule", dividers() - start, 1)
feed(2, "battle")
check("turn 2 draws another", dividers() - start, 2)
feed(2, "battle")
check("the same turn twice draws nothing more", dividers() - start, 2)
feed(3, "result")
check("the result phase is still the battle, so it counts",
      dividers() - start, 3)

print()
print("-- once the matchups have ended --")
for phase in ("manage", "menu", "prebattle", "leaderboard", None):
    w._clear_feed()
    was = dividers()
    # a turn number that differs from the last one seen: exactly the case
    # that used to draw a line across the management screens
    feed(9, phase)
    feed(11, phase)
    check("phase %r draws no rule" % phase, dividers() - was, 0)

print()
print("-- the guard is the phase, not the turn number --")
w._clear_feed()
was = dividers()
feed(4, "manage")
check("a fresh turn on a management screen is ignored",
      dividers() - was, 0)
feed(4, "battle")
check("...and the very same turn in a battle is drawn",
      dividers() - was, 1)
check("BATTLE_PHASES is what the guard tests",
      sorted(BATTLE_PHASES), ["battle", "result"])

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
