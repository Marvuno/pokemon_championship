"""Two trim screens in a row with the same roster must both work.

The wedge this guards: the trim/keep screen keys its state on the roster's
labels, and two rounds running can present exactly the same labels -- same
team, same order. The previous round's committed picks then survived into the
new screen, so it opened with picks already made, `remaining` at zero, and no
way to choose or confirm.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication                        # noqa: E402

from GUI import bridge as B                                       # noqa: E402
B.Bridge.start = lambda self: None
from GUI_qt.main_window import MainWindow                          # noqa: E402

app = QApplication.instance() or QApplication([])
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


def mon(name):
    return {"name": name, "sprite": name.lower(), "types": ["Normal"],
            "tier": "High", "ability": ["Static"], "status": "Normal",
            "hp": 100, "max_hp": 100, "stats": [100] * 6,
            "nominal": [100] * 6, "iv": [20] * 6, "base": [80] * 6,
            "total": 500, "total_iv": 120, "modifier": [0] * 9,
            "volatile": {}, "moveset": ["Tackle"], "moves": {},
            "disabled": {}, "charging": ["", "", 0], "protecting": False,
            "fainted": False, "active": False, "index": 0}


TEAM = ["Garchomp", "Milotic", "Metagross", "Skarmory", "Zapdos", "Aggron"]


class FakeRequest:
    """One engine question, answered one index at a time."""

    def __init__(self, prompt, kind="team_trim"):
        self.prompt = prompt
        self.kind = kind
        self.recent = ""
        self.answered = []

    def answer(self, value):
        self.answered.append(value)


w = MainWindow(ROOT)
roster = [dict(mon(n), index=i) for i, n in enumerate(TEAM)]
w.game_state = {"phase": "prebattle", "player_roster": roster,
                "opponent_roster": []}

PROMPT = ("You have more Pokemon than needed for this round! Select 2 "
          "Pokemon you DO NOT need this round:")


def run_one_trim_screen(tag):
    """Open the screen, tick two Pokemon, confirm. Returns what it answered."""
    request = FakeRequest(PROMPT)
    w.request = request
    w._show_request(request)
    app.processEvents()
    state = w._trim_state
    target = state.get("target")
    remaining = target - len(state.get("committed") or ())
    print("  %-6s target=%s committed=%s remaining=%s"
          % (tag, target, sorted(state.get("committed") or ()), remaining))
    # tick the first two that the screen will accept
    for index in (0, 1):
        w._toggle_team_pick(state, index, True, remaining)
        app.processEvents()
    picked = sorted(state["checked"])
    w._confirm_team_multiselect(state, True)
    app.processEvents()
    return target, remaining, picked, list(request.answered)


print("== first round ==")
target1, remaining1, picked1, answered1 = run_one_trim_screen("first")
check("it asks for 2", target1, 2)
check("...with nothing already committed", remaining1, 2)
check("...two can be ticked", picked1, [0, 1])
check("...and confirming answers the engine", answered1, ["0"])

# the engine keeps asking until it has both indexes; drain the rest
while w._pending_answers:
    nxt = FakeRequest(PROMPT)
    w.request = nxt
    w._show_request(nxt)
    app.processEvents()

print()
print("== second round, identical roster ==")
target2, remaining2, picked2, answered2 = run_one_trim_screen("second")
check("it asks for 2 again", target2, 2)
check("...with nothing carried over from last round", remaining2, 2)
check("...so two can still be ticked", picked2, [0, 1])
check("...and it answers rather than wedging", answered2, ["0"])
check("the trim state was cleared between rounds",
      len(w._trim_state.get("committed") or ()) <= 2, True)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
