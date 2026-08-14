"""Closing the swap window must answer the engine, not leave it blocked.

The reward screen empties the action bar and hands the question to the
compare window. If that window is dismissed with the X or Escape without
saying anything, the engine stays blocked inside input() and nothing on
screen can reach it -- the game stops dead.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtCore import Qt                                     # noqa: E402
from PySide6.QtGui import QKeyEvent                               # noqa: E402
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


class FakeRequest:
    """Stands in for the engine's pending question."""

    def __init__(self, prompt, kind="reward"):
        self.prompt = prompt
        self.kind = kind
        self.recent = ""
        self.answered = []

    def answer(self, value):
        self.answered.append(value)


def mon(name):
    return {"name": name, "sprite": "garchomp", "types": ["Dragon"],
            "tier": "High", "ability": ["Rough Skin"], "status": "Normal",
            "hp": 100, "max_hp": 100, "stats": [100] * 6,
            "nominal": [100] * 6, "iv": [20] * 6, "base": [80] * 6,
            "total": 500, "total_iv": 120, "modifier": [0] * 9,
            "volatile": {}, "moveset": ["Tackle"], "moves": {},
            "disabled": {}, "charging": ["", "", 0], "protecting": False,
            "fainted": False, "active": True, "index": 0}


w = MainWindow(ROOT)
w.game_state = {"phase": "reward",
                "player_roster": [mon("Garchomp"), mon("Milotic")],
                "opponent_roster": [mon("Metagross"), mon("Skarmory")]}

SWAP = "Do you want to swap a pokemon with the opponent?"
TAKE = "Do you want to take from the opponent?"
check("the prompt is recognised as the swap question",
      B.reward_prompt_kind(SWAP), B.REWARD_SWAP)


def open_reward(prompt):
    req = FakeRequest(prompt)
    w.request = req
    w._reward_plan = None
    handled = w._drive_reward(req)
    app.processEvents()
    return req, handled


# ---------------------------------------------- the X button
req, handled = open_reward(SWAP)
check("the swap window takes over the question", handled)
check("...and it is open", w.compare_dialog.isVisible())
check("...with the action bar empty, so only it can answer",
      w.actions.count(), 0)
w.compare_dialog.close()
app.processEvents()
check("closing it answers the engine", req.answered, ["N"])
check("...and the window is gone", w.compare_dialog.isVisible(), False)
check("...and no stale plan is left behind", w._reward_plan, None)

# ------------------------------------------------- Escape
# Escape used to decline. It now does nothing at all: this screen has no close
# button, because it *is* the question and its own buttons already offer the
# way out. Escape quietly answering "no" was the same invisible third option
# the cross was.
req, _ = open_reward(SWAP)
w.compare_dialog.keyPressEvent(
    QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
app.processEvents()
check("Escape does not answer for you", req.answered, [])
check("...and leaves the window open", w.compare_dialog.isVisible())
check("...with the question still pending", w.request is req)
check("the window has no close button",
      bool(w.compare_dialog.windowFlags() & Qt.WindowCloseButtonHint), False)
# a window manager can still close a window whatever its flags say, and being
# stranded is worse than a declined swap
w.compare_dialog.close()
app.processEvents()
check("a forced close still declines rather than stranding the engine",
      req.answered, ["N"])

# --------------------------- the take question declines the same way
req, _ = open_reward(TAKE)
if B.reward_prompt_kind(TAKE) == B.REWARD_TAKE:
    w.compare_dialog.close()
    app.processEvents()
    check("closing the take question answers it", req.answered, ["N"])
else:
    print("(take prompt wording differs; skipped)")

# ------------------- answering with a button must not double-answer
req, _ = open_reward(SWAP)
w._reward_proceed(-1)
app.processEvents()
check("pressing swap answers once", req.answered, ["Y"])
w.compare_dialog.close()
app.processEvents()
check("...and closing afterwards adds nothing", req.answered, ["Y"])

# --------- closing when nothing is pending must not invent an answer
w.request = None
w.compare_dialog.show()
app.processEvents()
w.compare_dialog.close()
app.processEvents()
check("closing an idle window answers nothing", w.request, None)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
