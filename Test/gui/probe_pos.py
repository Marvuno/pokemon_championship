"""Direct geometry probe: build the window, show the arena, and render a
real move-select screen into the action area, then measure everything.

The bridge's game thread is stubbed out so nothing can touch savefile.dat.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtCore import QTimer                       # noqa: E402
from PySide6.QtWidgets import QApplication              # noqa: E402

from GUI import bridge as B                             # noqa: E402
B.Bridge.start = lambda self: None                      # never run the game

from GUI_qt import main_window as MW                    # noqa: E402
from GUI_qt.widgets import ActionButton, MoveCard       # noqa: E402
from GUI import theme as T                              # noqa: E402

app = QApplication.instance() or QApplication([])
w = MW.MainWindow(ROOT)
w.show()

MOVES = [
    {"name": "Thunderbolt", "type": "Electric", "category": "Special",
     "power": 90, "accuracy": 1.0, "priority": 0},
    {"name": "Volt Switch", "type": "Electric", "category": "Special",
     "power": 70, "accuracy": 1.0, "priority": 0},
    {"name": "Hidden Power Ice", "type": "Ice", "category": "Special",
     "power": 60, "accuracy": 1.0, "priority": 0},
    {"name": "Extreme Speed", "type": "Normal", "category": "Physical",
     "power": 80, "accuracy": 1.0, "priority": 2},
]


def build_move_screen():
    from PySide6.QtWidgets import QGridLayout, QHBoxLayout
    w._clear_actions() if hasattr(w, "_clear_actions") else None
    grid = QGridLayout()
    for i, m in enumerate(MOVES):
        grid.addWidget(MoveCard(m, str(i), w.fonts,
                                effectiveness="SUPER" if i == 0 else None,
                                on_click=lambda: None), i // 2, i % 2)
    w.actions.addLayout(grid)
    extras = QHBoxLayout()
    extras.addWidget(ActionButton("Switch Pokemon", w.fonts,
                                  sub="give up the turn to bring someone in",
                                  accent=T.CYAN, on_click=lambda: None))
    extras.addWidget(ActionButton("Auto Battle", w.fonts,
                                  sub="let the AI take this match",
                                  accent=T.VIOLET, on_click=lambda: None))
    w.actions.addLayout(extras)
    w._fit_actions()


def report():
    lines = []
    a, tabs, sc = w.arena, w.tabs, w.actions_scroll
    lines += [
        "window           %dx%d" % (w.width(), w.height()),
        "arena            %dx%d" % (a.width(), a.height()),
        "log column       %dx%d" % (tabs.width(), tabs.height()),
        "effects strip    %dx%d" % (w.effects.width(), w.effects.height()),
        "action area      %dx%d  (cap %d)"
        % (sc.width(), sc.height(), w.ACTIONS_MAX_HEIGHT),
        "action content   hint %dx%d"
        % (w.actions_body.sizeHint().width(),
           w.actions_body.sizeHint().height()),
        "action clipped?  %s"
        % ("YES" if w.actions_body.sizeHint().height() > sc.height()
           else "no"),
        "layout minimum   %dx%d" % (w.layout().minimumSize().width(),
                                    w.layout().minimumSize().height()),
        "fits in window?  %s"
        % ("YES" if (w.layout().minimumSize().width() <= w.width()
                     and w.layout().minimumSize().height() <= w.height())
           else "NO -- OVERFLOW"),
        "arena width share  %.1f%%" % (100.0 * a.width() / w.width()),
        "arena height share %.1f%%" % (100.0 * a.height() / w.height()),
    ]
    text = "\n".join(lines)
    print(text, flush=True)
    with open(os.path.join(OUT, "geometry_pos.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


def go():
    w.stage_views.setCurrentIndex(1)      # show the arena
    build_move_screen()
    QTimer.singleShot(250, lambda: (report(),
                                    None,
                                    app.quit()))


QTimer.singleShot(150, go)
app.exec()
