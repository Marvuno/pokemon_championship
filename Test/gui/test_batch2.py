"""This batch: matchup reset, scout reveals the team, auto battle off,
no UPSET on your own defeat, and the About Opponent layout."""
import os
import sys
import threading

ROOT, OUT = sys.argv[1], sys.argv[2]
HEADED = os.environ.get("QT_QPA_PLATFORM") != "offscreen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel                  # noqa: E402

from GUI import bridge as B, prompt_parser as P                     # noqa: E402
B.Bridge.start = lambda self: None

from GUI_qt import main_window as MW                                # noqa: E402
from GUI_qt.panels import OpponentInfoDialog, StandingsDialog       # noqa: E402
from GUI_qt.widgets import ActionButton, Chip                       # noqa: E402

app = QApplication.instance() or QApplication([])
w = MW.MainWindow(ROOT)
w.show()
failures = []


def check(label, got, want):
    if got == want:
        print("%-56s PASS" % label)
    else:
        print("%-56s FAIL got=%r want=%r" % (label, got, want))
        failures.append(label)


def buttons():
    found = {}
    for b in w.actions_body.findChildren(ActionButton):
        for lab in b.findChildren(QLabel):
            if (lab.text() or "").strip():
                found.setdefault(lab.text().strip(), b)
                break
    return found


class Req:
    def __init__(self, prompt, kind="generic", recent=""):
        self.prompt, self.kind, self.recent = prompt, kind, recent
        self.value = None
        self.event = threading.Event()

    def answer(self, value):
        self.value = value
        self.event.set()


# --------------------------------------- 1+2. entitlement is per matchup
class FakeGround:
    def __init__(self):
        self.auto_battle = True
        self.turn = 1
        self.weather_effect = "Clear"
        self.artificial_weather = False
        self.weather_turn = 0
        self.field_effect = {}
        self.sudden_death = False


bridge = w.bridge
bridge.ctx = {"battleground": FakeGround()}
bridge.state = {}
check("entitlement starts off", bridge.state.get("opponent_known"), None)
bridge.state["opponent_known"] = True          # as a win would leave it
# a new matchup begins: before_battle_option resets it
check("a win leaves it set", bridge.state["opponent_known"], True)

# --------------------------------------------- 3. auto battle switches off
published = {}
bridge.publish = lambda **f: published.update(f)
check("auto battle starts on", bridge.ctx["battleground"].auto_battle, True)
check("set_auto_battle reports success", bridge.set_auto_battle(False), True)
check("...and the flag is down", bridge.ctx["battleground"].auto_battle, False)
check("...and it republished the field",
      published.get("field", {}).get("auto_battle"), False)
check("it can be switched back on", bridge.set_auto_battle(True)
      and bridge.ctx["battleground"].auto_battle, True)
bridge.ctx = {}
check("no battleground is handled", bridge.set_auto_battle(False), False)

# the move screen offers the switch both ways
w.game_state = {"field": {"auto_battle": True}}
move_prompt = ("What is the move for Pikachu?\n"
               "0: Switching\n1: Thunderbolt\n"
               "Input 100 to activate auto battle\n--> ")
req = Req(move_prompt, kind="move")
w.game_state["player"] = {"moveset": ["Switching", "Thunderbolt"], "moves": {},
                          "disabled": {}}
w._show_request(req)
app.processEvents()
labels = buttons()
check("auto battle ON is offered as a live button",
      "Auto battle: ON" in labels, True)
check("...and it is clickable now",
      labels.get("Auto battle: ON") is not None
      and labels["Auto battle: ON"].on_click is not None, True)

w.game_state["field"] = {"auto_battle": False}
w._show_request(Req(move_prompt, kind="move"))
app.processEvents()
check("auto battle off is offered when it is off",
      "Auto battle: off" in buttons(), True)

# --------------------------------------------- 6. no UPSET on your defeat
standings = StandingsDialog(w.fonts)
standings.resize(980, 620)
standings.show()
app.processEvents()


def round_with(player_won, upset):
    winner = {"nickname": "Rival", "strength": 200, "points": 2, "score": 6,
              "is_player": False, "upset": upset}
    loser = {"nickname": "Marvin", "strength": 421, "points": 1, "score": 4,
             "is_player": True}
    if player_won:
        winner, loser = ({"nickname": "Marvin", "strength": 421, "points": 2,
                          "score": 6, "is_player": True, "upset": upset},
                         {"nickname": "Rival", "strength": 200, "points": 1,
                          "score": 4, "is_player": False})
    return [{"round": 1, "pairs": [[winner, loser]]}]


def count_upsets(rounds):
    """A fresh dialog per case: _clear defers its deletes to the event loop,
    so reusing one dialog counts the previous case's chips as well."""
    dialog = StandingsDialog(w.fonts)
    dialog.resize(980, 620)
    dialog.show()
    dialog.refresh(None, [], [], False, round_results=rounds)
    dialog.select("Round 1")
    app.processEvents()
    total = len([c for c in dialog.findChildren(Chip)
                 if (c.text() or "").upper() == "UPSET"])
    dialog.close()
    return total


check("no UPSET badge when you are the one beaten",
      count_upsets(round_with(False, True)), 0)
check("UPSET still shown when you cause it",
      count_upsets(round_with(True, True)), 1)
other = [{"round": 1, "pairs": [[
    {"nickname": "A", "strength": 100, "points": 2, "score": 6,
     "is_player": False, "upset": True},
    {"nickname": "B", "strength": 400, "points": 1, "score": 4,
     "is_player": False}]]}]
check("UPSET still shown between other competitors",
      count_upsets(other), 1)
check("no badge when there was no upset at all",
      count_upsets(round_with(True, False)), 0)
standings.close()

# --------------------------------------------- 7. About Opponent layout
info = {"nickname": "Magnus Carlsen", "tier": "Elite",
        "art": os.path.join("Assets", "characters", "Magnus Carlsen.jpg"),
        "description": "One of the Lower Elite Four, and a chess player.",
        "strategy_revealed": True, "strategy": "Blunders.",
        "scouted_text": "You have sized up their entire team.",
        "scout_failed": False}
dialog = OpponentInfoDialog(info, w.fonts, ROOT)
dialog.resize(1080, 700)
dialog.show()
app.processEvents()
check("the report window is large", dialog.width() >= 1000, True)
art_labels = [l for l in dialog.findChildren(QLabel)
              if l.pixmap() is not None and not l.pixmap().isNull()]
check("the art is shown", len(art_labels) >= 1, True)
check("the art is on the left",
      art_labels[0].mapTo(dialog, art_labels[0].rect().center()).x()
      < dialog.width() // 2, True)
texts = [l.text() for l in dialog.findChildren(QLabel) if l.text()]
check("the flavour description is gone",
      any("Lower Elite Four" in t for t in texts), False)
check("the name is still there",
      any("Magnus Carlsen" == t for t in texts), True)
check("the report is still there",
      any("SCOUTING REPORT" in t for t in texts), True)
if HEADED:
    dialog.grab().save(os.path.join(OUT, "about_opponent2.png"))
dialog.close()

print("\n%s" % ("ALL PASS" if not failures
                else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
