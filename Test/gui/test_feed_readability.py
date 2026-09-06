"""The battle feed: side columns, and events filed under the right turn.

Two faults, and the second is the subtler one:

  columns   every event went into one undifferentiated column, so a turn read
            as a list rather than as "what you did / what they did"
  ordering  knockouts and switches are found by diffing the published state,
            so they arrive on the *same* publish that carries the new turn
            number. With the turn divider drawn first, everything that
            happened at the end of a turn was filed under the next one -- a
            Pokemon sent out during turn 3 appeared beneath the TURN 4 rule.

A third piece was built and removed: a one-line summary of each turn under its
divider. It read as a second, competing account of events the feed had already
given in full a few lines above.

    python Test/gui/test_feed_readability.py <root> <out>
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import inspect                                                        # noqa

from PySide6.QtWidgets import QApplication                            # noqa

from GUI_qt.fonts import Fonts                                        # noqa
from GUI_qt.main_window import MainWindow                             # noqa
from GUI_qt.widgets import FeedEntry, FeedRow                         # noqa

fails = []


def check(label, got, want):
    ok = got == want
    print("%-58s %s%s" % (label, "PASS" if ok else "FAIL",
                          "" if ok else "  got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(label)


app = QApplication.instance() or QApplication([])
fonts = Fonts()

# ------------------------------------------------------------- the columns
print("-- an entry is held to the column of its side --")
for side, stretch_first in (("player", False), ("opponent", True),
                            (None, False)):
    entry = FeedEntry("move", "Earthquake!", fonts, actor="Garchomp",
                      side=side)
    row = FeedRow(entry, side=side)
    layout = row.layout()
    check("%-9s entry sits %s" % (side or "neutral",
                                  "right" if stretch_first else "left"),
          layout.itemAt(0).widget() is None, stretch_first)
    if side is None:
        check("...and a neutral entry spans the width", layout.count(), 1)

# The gutter has to be the *remainder* of the ratio. Given 82 against a
# stretch of 1 the entry takes 98.8% of the row and the column is invisible,
# which is exactly how this shipped the first time.
row = FeedRow(FeedEntry("move", "x", fonts, side="player"), side="player")
share = row.layout().stretch(0)
gutter = row.layout().stretch(1)
check("the gutter is a real share of the width (%d:%d)" % (share, gutter),
      0 < gutter and share + gutter == 100, True)

# ------------------------------------------------------------- the ordering
print("")
print("-- a turn's events are filed under that turn --")
# Read off the source rather than by driving a battle: the claim is about the
# order three calls are made in, which is what the bug was.
body = inspect.getsource(MainWindow._apply_state)
order = {}
for name in ("_track_knockouts", "_sync_field", "_track_feed_worthy_changes"):
    order[name] = body.index(name) if name in body else -1
check("knockouts are recorded before the divider is drawn",
      order["_track_knockouts"] < order["_track_feed_worthy_changes"], True)
check("switches are recorded before the divider is drawn",
      order["_sync_field"] < order["_track_feed_worthy_changes"], True)

# ------------------------------------------------------- and it still runs
print("")
print("-- the feed takes traffic without a summary to fill in --")


class Layout:
    """Enough QVBoxLayout for the feed bookkeeping to run against."""

    def __init__(self):
        self.items = []

    def count(self):
        return len(self.items) + 1          # the trailing stretch

    def insertWidget(self, index, widget):
        self.items.insert(index, widget)


window = MainWindow.__new__(MainWindow)
window.fonts = fonts
window.feed_layout = Layout()
broke = ""
try:
    MainWindow._feed_divider(window, 1)
    MainWindow._feed_add(window, "move", "Earthquake!", actor="Garchomp",
                         side="player")
    MainWindow._feed_divider(window, 2)
    MainWindow._feed_add(window, "faint", "Sunkern fainted!", actor="Sunkern",
                         side="opponent")
except Exception as error:              # noqa: BLE001 -- the point is "any"
    broke = "%s: %s" % (type(error).__name__, error)
check("a divider needs no bookkeeping to be built", broke, "")
check("...and four events produced four rows", len(window.feed_layout.items),
      4)

print("")
print("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(fails))
sys.exit(1 if fails else 0)
