"""One-click auto-battle off, action rows inside the window, and the
About Opponent artwork actually filling its column."""
import os
import sys
import threading

ROOT, OUT = sys.argv[1], sys.argv[2]
HEADED = os.environ.get("QT_QPA_PLATFORM") != "offscreen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel                  # noqa: E402

from GUI import bridge as B                                         # noqa: E402
B.Bridge.start = lambda self: None

from GUI_qt import settings                                         # noqa: E402
from GUI_qt.main_window import MainWindow                           # noqa: E402
from GUI_qt.panels import OpponentInfoDialog                        # noqa: E402
from GUI_qt.widgets import ActionButton                             # noqa: E402

app = QApplication.instance() or QApplication([])
failures = []


def check(label, got, want):
    if got == want:
        print("%-58s PASS" % label)
    else:
        print("%-58s FAIL got=%r want=%r" % (label, got, want))
        failures.append(label)


class Req:
    def __init__(self, prompt, kind="generic", recent=""):
        self.prompt, self.kind, self.recent = prompt, kind, recent
        self.value = None
        self.event = threading.Event()

    def answer(self, value):
        self.value = value
        self.event.set()


class FakeGround:
    def __init__(self):
        self.auto_battle = True
        self.turn = 1
        self.weather_effect = "Clear"
        self.artificial_weather = False
        self.weather_turn = 0
        self.field_effect = {}
        self.sudden_death = False


MOVE_PROMPT = ("What is the move for Pikachu?\n0: Switching\n"
               "1: Thunderbolt\n2: Surf\n3: Ice Beam\n"
               "Input 100 to activate auto battle\n--> ")


def labelled(window):
    found = {}
    for b in window.actions_body.findChildren(ActionButton):
        for lab in b.findChildren(QLabel):
            if (lab.text() or "").strip():
                found.setdefault(lab.text().strip(), b)
                break
    return found


for mode in (settings.NORMAL, settings.BEGINNER):
    settings.set_difficulty(mode)
    w = MainWindow(ROOT)
    w.show()
    print("\n== %s (%dx%d) ==" % (mode, w.width(), w.height()))

    # ---------------------------------------- 1. one click turns it off
    w.bridge.ctx = {"battleground": FakeGround()}
    w.game_state = {"field": {"auto_battle": True},
                    "player": {"moveset": ["Switching", "Thunderbolt", "Surf",
                                           "Ice Beam"],
                               "moves": {}, "disabled": {}}}
    req = Req(MOVE_PROMPT, kind="move")
    w._show_request(req)
    app.processEvents()
    check("the button reads ON while it is on", "Auto battle: ON" in labelled(w),
          True)
    labelled(w)["Auto battle: ON"].on_click()
    app.processEvents()
    check("one click flips the engine flag",
          w.bridge.ctx["battleground"].auto_battle, False)
    check("...and the label with it, without a second click",
          "Auto battle: off" in labelled(w), True)
    check("...and no answer was sent to the engine", req.value, None)

    # ---------------------------------------- 2. nothing runs off the edge
    screens = [
        ("move select", Req(MOVE_PROMPT, kind="move")),
        ("switch-in", Req("Which pokemon would you like to switch in?\n"
                          "[(0, 'A'), (1, 'B'), (2, 'C'), (3, 'D'), "
                          "(4, 'E'), (5, 'F')]\n8 to inspect your team\n--> ",
                          "switch")),
        ("keep team", Req("You can keep at most 6 Pokemon for your next run. "
                          "Pick them one at a time, then enter 9 when you are "
                          "done: \n[(0, 'A'), (1, 'B'), (2, 'C'), (3, 'D'), "
                          "(4, 'E'), (5, 'F')]\n", "team_keep")),
        ("reward", Req("Take the pokemon you want on the other team, or 9 to "
                       "go back:\n[(0, 'A'), (1, 'B')]\n--> ", "reward")),
    ]
    w.game_state["player_roster"] = [
        {"name": "P%d" % i, "types": ["Normal"], "total": 400, "moveset": [],
         "moves": {}, "nominal": [90] * 6, "iv": [10] * 6, "ability": [],
         "sprite": "", "status": "Normal", "tier": "Low"} for i in range(6)]
    w.game_state["player_team"] = [
        {"name": "P%d" % i, "sprite": "", "types": ["Normal"],
         "status": "Normal", "hp": 90, "max_hp": 100, "fainted": False,
         "active": i == 0} for i in range(6)]
    for name, request in screens:
        w._show_request(request)
        for _ in range(4):
            app.processEvents()
        viewport = w.actions_scroll.viewport().width()
        widest = 0
        for button in w.actions_body.findChildren(ActionButton):
            right = button.mapTo(w.actions_body,
                                 button.rect().bottomRight()).x()
            widest = max(widest, right)
        check("%-18s stays inside the action area" % name,
              widest <= viewport, True)
        check("%-18s needs no sideways scrolling" % name,
              w.actions_scroll.horizontalScrollBar().isVisible(), False)
    if HEADED:
        w.grab().save(os.path.join(OUT, "rows_%s.png" % mode))
    w.close()

settings.set_difficulty(settings.NORMAL)

# ---------------------------------------- 3. the artwork fills its column
info = {"nickname": "Aphelios", "tier": "Intermediate",
        "art": os.path.join("Assets", "characters", "Aphelios.jpg"),
        "description": "", "strategy_revealed": True,
        "strategy": "Ace: Blacephalon", "scouted_text": "Sized up the team.",
        "scout_failed": False}
dialog = OpponentInfoDialog(info, MainWindow(ROOT).fonts, ROOT)
dialog.show()
for _ in range(6):
    app.processEvents()
box = dialog.art_label.size()
shown = dialog.art_label.pixmap()
source = dialog._picture
print("\n== about opponent ==")
print("   window %dx%d, art column %dx%d, source %dx%d, drawn %dx%d"
      % (dialog.width(), dialog.height(), box.width(), box.height(),
         source.width(), source.height(), shown.width(), shown.height()))
check("the art column takes most of the window",
      box.width() >= dialog.width() * 0.55, True)
check("the picture fills that column's shorter side",
      max(shown.width() / box.width(), shown.height() / box.height()) > 0.98,
      True)
# The column is 664px tall on a 1280x800 desktop and the source is 1024, so
# filling it is a downscale here; on a bigger screen the same code upscales.
# What matters either way is that it fills, which the check above asserts.
check("no wasted space on the filled axis",
      min(box.width() - shown.width(), box.height() - shown.height()) <= 1,
      True)
check("aspect ratio preserved (not stretched)",
      abs(shown.width() / shown.height()
          - source.width() / source.height()) < 0.01, True)
if HEADED:
    dialog.grab().save(os.path.join(OUT, "about_fill.png"))
dialog.close()

print("\n%s" % ("ALL PASS" if not failures
                else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
