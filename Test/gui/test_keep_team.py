"""How many Pokemon the end-of-run screen lets you keep.

The engine states the number in its own prompt -- "keep at most 6 Pokemon" --
computed from the real team. The window used to take that number and clamp it
to `player_roster`, which is a *different* snapshot and lags: during a round
with a 4v4 or 5v5 limit the Pokemon you benched live in `unused_team`, so the
published roster holds four or five while the team holds six. `end_battle`
folds them home, but nothing republishes the roster between that and
`save_game` -- so the clamp turned "keep at most 6" into 5, and a Pokemon you
owned could not be kept.

Clamping to the *options on the screen* instead fixes it without giving up
the guard it was there for: the sentinel ("enter 9 when you are done") must
not be counted as a Pokemon and inflate the limit to seven.
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
                  tag="keep_team")

from PySide6.QtWidgets import QApplication                          # noqa: E402

app = QApplication.instance() or QApplication([])

from GUI import bridge as B                                         # noqa: E402
from GUI_qt.main_window import MainWindow                           # noqa: E402
from GUI_qt.widgets import ActionButton                             # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


w = MainWindow(ROOT)
w.bridge.stop()
import builtins                                                     # noqa: E402
builtins.print = w.bridge._real_print
w.show()

TEAM = ["Pikachu", "Gyarados", "Alakazam", "Ferrothorn", "Slowbro",
        "Glimmora"]


def keep_screen(limit, offered, roster_size):
    """Drive the keep screen the way the engine drives it.

    `offered` is how many Pokemon the engine lists; `roster_size` is how many
    the *published snapshot* happens to hold, which is the thing that used to
    win the argument.
    """
    listing = str([(index, name)
                   for index, name in enumerate(TEAM[:offered])])
    said = ("%s\nYou can keep at most %d Pokemon for your next run. Pick "
            "them one at a time, then enter 9 when you are done: "
            % (listing, limit))
    w.game_state = dict(w.game_state or {}, phase="manage", player_roster=[
        {"name": name, "types": ["Normal"], "hp": 10, "max_hp": 10}
        for name in TEAM[:roster_size]])
    w._keep_state.clear()
    # the action bar is not cleared by _render_team_multiselect -- the real
    # flow goes through _show_request, which clears first -- so without this
    # the tiles from the previous call are still there and get counted
    w._clear_actions()
    app.processEvents()
    request = B.InputRequest(said, "team_keep")
    prompt = w.memory.parse(request.prompt, request.recent)
    w.request = request
    w._render_team_multiselect(prompt, request, exact=False)
    tiles = [b for b in w.actions_body.findChildren(ActionButton)
             if b.title in TEAM]
    return w._keep_state["target"], len(tiles)


print("-- the engine's number wins --")
target, tiles = keep_screen(limit=6, offered=6, roster_size=6)
check("a full team offers all six", (target, tiles), (6, 6))

# the bug: the snapshot lags behind the fold
target, tiles = keep_screen(limit=6, offered=6, roster_size=5)
check("a stale five-entry roster does not cost you a Pokemon",
      target, 6)
check("...and all six tiles are still drawn", tiles, 6)

target, tiles = keep_screen(limit=6, offered=6, roster_size=4)
check("nor does a four-entry one", (target, tiles), (6, 6))

target, _ = keep_screen(limit=6, offered=6, roster_size=0)
check("nor an empty one", target, 6)

print()
print("-- and the guard it replaced still holds --")
# the sentinel must never be counted as a Pokemon
target, tiles = keep_screen(limit=6, offered=6, roster_size=6)
check("six offered means six, not seven", target, 6)
check("...and the 'I am done' sentinel is not a tile", tiles, 6)

# a genuinely short team really does offer fewer
target, tiles = keep_screen(limit=3, offered=3, roster_size=6)
check("a team of three offers three", (target, tiles), (3, 3))
target, tiles = keep_screen(limit=6, offered=4, roster_size=6)
check("the engine listing four caps it at four", target, 4)

print()
print("-- the engine's own limit --")
from Scripts.Battle.constants import MAX_POKEMON                    # noqa: E402
import inspect                                                      # noqa: E402
from Scripts.Game import game_procedure                             # noqa: E402

source = inspect.getsource(game_procedure.save_game)
check("save_game offers min(MAX_POKEMON, team size)",
      "min(MAX_POKEMON, len(" in source)
check("...and MAX_POKEMON is six", MAX_POKEMON, 6)

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
