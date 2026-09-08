"""The battleground must not move. Walk every kind of screen -- move select,
switch-in, a long menu, auto battle's single Continue -- and assert the arena
rect and both sprite rects are byte-identical throughout."""
import os
import sys
import threading

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication                          # noqa: E402

from GUI import bridge as B                                         # noqa: E402
B.Bridge.start = lambda self: None

from GUI_qt.main_window import MainWindow                           # noqa: E402

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


def mon(name, key):
    return {"name": name, "sprite": key, "types": ["Normal"], "tier": "High",
            "ability": ["Levitate"], "status": "Normal", "hp": 100,
            "max_hp": 100, "stats": [], "nominal": [90] * 6, "iv": [10] * 6,
            "total": 500, "total_iv": 60, "modifier": [0] * 9, "volatile": {},
            "moveset": ["Switching", "Thunderbolt", "Surf"],
            "moves": {}, "disabled": {}, "charging": ["", "", 0],
            "protecting": False, "fainted": False, "active": True}


TEAM = [{"name": "P%d" % i, "sprite": "pikachu", "types": ["Electric"],
         "status": "Normal", "hp": 90, "max_hp": 100, "fainted": False,
         "active": i == 0} for i in range(6)]

SCREENS = [
    ("move select", Req("What is the move for Yours?\n0: Switching\n"
                        "1: Thunderbolt\n2: Surf\n"
                        "Input 100 to activate auto battle\n--> ", "move")),
    ("switch-in", Req("Which pokemon would you like to switch in?\n"
                      "[(0, 'A'), (1, 'B'), (2, 'C'), (3, 'D'), (4, 'E'), "
                      "(5, 'F')]\n8 to inspect your team\n--> ", "switch")),
    ("a plain continue (auto battle)", Req("Press any key to continue.")),
    ("a long menu", Req("What do you want to do?\n"
                        + "\n".join("%d: Option %d" % (i, i)
                                    for i in range(12)) + "\n--> ")),
    ("confirm", Req("Input Y if you want to swap, and N otherwise. ")),
]

# The difficulty this looped over is no longer a window setting, so the
# passes were identical. One is what it was always measuring.
for size in (("normal", "Normal", ""),):
    w = MainWindow(ROOT)
    w.show()
    w._apply_state({
        "phase": "battle", "player": mon("Yours", "poseidon"),
        "opponent": mon("Theirs", "milotic"),
        "player_team": TEAM, "opponent_team": TEAM,
        "player_side": {"nickname": "Marvin", "strength": 421, "buffs": {},
                        "hazards": {}},
        "opponent_side": {"nickname": "Rival", "strength": 300, "buffs": {},
                          "hazards": {}},
        "field": {"turn": 3, "weather": "Rain", "field": {}},
    })
    for _ in range(8):
        app.processEvents()

    def rects():
        return (w.arena.geometry().getRect(),
                w.player_sprite.geometry().getRect(),
                w.opponent_sprite.geometry().getRect(),
                w.opponent_card.geometry().getRect(),
                w.player_card.geometry().getRect())

    baseline = rects()
    print("\n== %s (%dx%d) ==  arena %s  player sprite %s"
          % (size[0], w.width(), w.height(), baseline[0], baseline[1]))
    for label, req in SCREENS:
        w._show_request(req)
        for _ in range(6):
            app.processEvents()
        check("%-32s leaves the battleground put" % label, rects(), baseline)
    # and auto battle flipping on/off, which is what the player reported
    w.game_state["field"] = {"auto_battle": True, "turn": 3,
                             "weather": "Rain", "field": {}}
    w._apply_state(dict(w.game_state))
    for _ in range(6):
        app.processEvents()
    check("auto battle ON leaves the battleground put", rects(), baseline)
    w.game_state["field"]["auto_battle"] = False
    w._apply_state(dict(w.game_state))
    for _ in range(6):
        app.processEvents()
    check("auto battle OFF leaves the battleground put", rects(), baseline)
    check("the arena is the fixed height", w.arena.height(), w.arena_height)
    w.grab().save(os.path.join(OUT, "stable_%s.png" % size[0]))
    w.close()

print("\n%s" % ("ALL PASS" if not failures
                else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
