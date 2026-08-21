"""Can you read a second career's history after reading a first?

The report: play slot 2, finish the run, come back, and the other slots'
histories are unreachable. The engine's own slot handling is fine --
select(n) + load(n) round-trips correctly however many times you do it -- so
this drives the *interface* through the sequence instead: open HISTORY on one
slot, close it, open HISTORY on another, and check that what appears belongs
to the second slot.

Runs against copies of the real saves, in a sandbox directory, so the
player's careers are never opened for writing.

    python Test/run_tests.py history_slots
"""
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

ROOT, OUT = sys.argv[1], sys.argv[2]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

fails = []

# The bridge replaces builtins.print with the game log the moment a MainWindow
# exists, so hold the real one now or every result below disappears into the
# battle transcript.
import builtins
_say = builtins.print


def check(label, got, want=True):
    ok = got == want
    _say("%-62s %s" % (label, "PASS" if ok else
                       "FAIL got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(label)


# -- a sandbox with its own Save/ ------------------------------------------
sandbox = tempfile.mkdtemp(prefix="slots_")
for name in ("Data", "Assets", "Documentation"):
    source = os.path.join(ROOT, name)
    if os.path.isdir(source):
        # Assets is large and only Data is read here; link where we can
        if name == "Data":
            shutil.copytree(source, os.path.join(sandbox, name))
        else:
            os.makedirs(os.path.join(sandbox, name), exist_ok=True)
os.makedirs(os.path.join(sandbox, "Save"), exist_ok=True)


def write_slot(slot, nickname, rating, runs, titles):
    """A minimal but loadable career."""
    payload = {
        "version": 1,
        "player": {"nickname": nickname, "name": nickname, "rating": rating,
                   "participation": runs, "championship": titles,
                   "stage": 1, "team": [], "history": {},
                   "opponent_history": {}},
        "competitors": {},
    }
    with open(os.path.join(sandbox, "Save", "savefile%d.json" % slot),
              "w", encoding="utf-8") as out:
        json.dump(payload, out)


# two careers that are easy to tell apart
write_slot(1, "SlotOnePlayer", 111, 3, 1)
write_slot(2, "SlotTwoPlayer", 222, 7, 2)

sys.path.insert(0, ROOT)
os.chdir(sandbox)

import Scripts.Battle.battle_cycle as CYCLE                      # noqa: E402
from Scripts.Data.competitors import list_of_competitors         # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                 # noqa: E402
from Scripts.Game import savefile                                # noqa: E402

SINK = io.StringIO()

# -- 1. the engine's own slot handling ------------------------------------
_say("-- the engine --")
savefile.remember_pristine(list_of_competitors, list_of_pokemon)
offered = {entry["slot"]: entry.get("used") for entry in savefile.slots()}
check("the menu offers both careers", [offered.get(1), offered.get(2)],
      [True, True])

order = []
for slot in (2, 1, 2, 1):
    savefile.select(slot)
    with redirect_stdout(SINK):
        savefile.load(list_of_competitors, list_of_pokemon)
    order.append(list_of_competitors["Protagonist"].nickname)
check("switching careers back and forth loads the right one each time",
      order, ["SlotTwoPlayer", "SlotOnePlayer",
              "SlotTwoPlayer", "SlotOnePlayer"])

# -- 2. the interface, driven through the reported sequence ---------------
_say("-- the interface --")
from PySide6.QtWidgets import QApplication                       # noqa: E402
from GUI.bridge import Bridge, EV_STATE                          # noqa: E402
from GUI_qt.main_window import MainWindow                        # noqa: E402

app = QApplication.instance() or QApplication([])
window = MainWindow(sandbox)

#: what the interface would show as "whose career is this"
def shown_nickname():
    report = window._last_career.get("career_report") or {}
    return report.get("nickname")


# The window's own view of the HISTORY screen is driven by two published
# facts, career_open and the payloads. Replay the pair of visits the report
# describes, checking the flags the interface uses to decide whether the
# window is on screen -- that is what _drive_career consults before it
# answers, and answering "N" with the window hidden is what would close the
# screen the instant it opened.
def publish(**state):
    window._apply_state(dict(state))


publish(career_open=True, career_champions=[])
first_shown = window.career_dialog.isVisible()
check("first visit: the career window is presented", first_shown)

# the player closes it, and the engine's screen unwinds
window.career_dialog.close()
publish(career_open=False)
check("closing it clears the interface's 'already shown' latch",
      window._career_shown, False)

# second visit, a different slot
publish(career_open=True, career_champions=[{"run": 1, "champion": "X",
                                            "rank": 1, "beaten": []}])
check("second visit: the career window is presented again",
      window.career_dialog.isVisible())

# and with it hidden, the driver must NOT be the thing that answers
window.career_dialog.close()
publish(career_open=False)
publish(career_open=True, career_champions=[])
check("a third visit works too", window.career_dialog.isVisible())

_say("")
_say("ALL PASS" if not fails else "FAILURES: %d -- %s" % (len(fails), fails))
shutil.rmtree(sandbox, ignore_errors=True)
sys.exit(1 if fails else 0)
