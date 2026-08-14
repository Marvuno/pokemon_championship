"""How often is artwork re-decoded, and what does it cost?"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtGui import QPixmap                                  # noqa: E402
from PySide6.QtWidgets import QApplication                         # noqa: E402
import GUI_qt.panels as PANELS                                     # noqa: E402
import GUI_qt.pokedex as PDEX                                      # noqa: E402

app = QApplication.instance() or QApplication([])

DECODES = []
_real = QPixmap


class Counting(QPixmap):
    def __init__(self, *a, **kw):
        if a and isinstance(a[0], str) and a[0]:
            t = time.perf_counter()
            super().__init__(*a, **kw)
            DECODES.append((a[0], time.perf_counter() - t))
        else:
            super().__init__(*a, **kw)


PANELS.QPixmap = Counting
PDEX.QPixmap = Counting

from GUI import bridge as B                                        # noqa: E402
from GUI_qt.fonts import Fonts                                     # noqa: E402
from Scripts.Data.competitors import list_of_competitors           # noqa: E402
from Scripts.Data.moves import list_of_moves                       # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                   # noqa: E402
from GUI import codex                                              # noqa: E402

fonts = Fonts()
DATA = codex.build(list_of_pokemon, list_of_moves, list_of_competitors,
                   art_for=B.character_art)
dex = PDEX.PokedexDialog(fonts, DATA, ROOT)
dex.present("opponents")
app.processEvents()
base = len(DECODES)
print("opening the Pokedex on Opponents: %d decodes" % base)

# type a name one character at a time, as a player would
DECODES.clear()
for i in range(1, len("cynthia") + 1):
    dex.entry.setText("cynthia"[:i])
    dex._filter()
    app.processEvents()
print("typing 'cynthia' (7 keystrokes):   %d decodes, %.0f ms"
      % (len(DECODES), sum(d for _, d in DECODES) * 1000))

# click through several competitors
DECODES.clear()
people = dex.sections["opponents"]
names = [e["nickname"] for e in DATA["opponents"][:8]]
for name in names:
    dex.entry.setText(name)
    dex._filter()
    app.processEvents()
uniq = len(set(p for p, _ in DECODES))
print("viewing 8 competitors:             %d decodes of %d distinct files, "
      "%.0f ms" % (len(DECODES), uniq, sum(d for _, d in DECODES) * 1000))

# re-view the same one repeatedly: pure waste if uncached
DECODES.clear()
for _ in range(6):
    dex.entry.setText(names[0])
    dex._filter()
    app.processEvents()
    dex.entry.setText(names[1])
    dex._filter()
    app.processEvents()
print("alternating between 2 of them x6:  %d decodes of %d distinct files, "
      "%.0f ms" % (len(DECODES), len(set(p for p, _ in DECODES)),
                   sum(d for _, d in DECODES) * 1000))
if DECODES:
    worst = max(DECODES, key=lambda d: d[1])
    print("slowest single decode: %.0f ms  %s"
          % (worst[1] * 1000, os.path.basename(worst[0])))
