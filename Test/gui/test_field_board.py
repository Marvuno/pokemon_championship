"""The Field tab must be a live board: rows appear when an effect goes up,
count down each turn, and vanish when it ends. Nothing in the battle screen.
"""
import os
import sys

ROOT, OUT = sys.argv[1], sys.argv[2]
HEADED = os.environ.get("QT_QPA_PLATFORM") != "offscreen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel      # noqa: E402

from GUI import bridge as B                             # noqa: E402
B.Bridge.start = lambda self: None

from GUI_qt import main_window as MW                    # noqa: E402
from GUI_qt.widgets import RoundedPanel                 # noqa: E402

app = QApplication.instance() or QApplication([])
w = MW.MainWindow(ROOT)
w.show()

failures = []


def check(label, got, want):
    if got == want:
        print("%-54s PASS" % label)
    else:
        print("%-54s FAIL got=%r want=%r" % (label, got, want))
        failures.append(label)


def board_text():
    return [l.text() for l in w.field_board.findChildren(QLabel) if l.text()]


def rows():
    return len(w.field_board.findChildren(RoundedPanel))


def tab():
    return w.tabs.tabText(w._field_tab)


def state(you_buffs=None, you_haz=None, opp_buffs=None, opp_haz=None,
          field=None, weather="Clear", weather_turns=None, phase="battle"):
    return {
        "phase": phase,
        "player_side": {"nickname": "Marvin", "strength": 421,
                        "buffs": you_buffs or {}, "hazards": you_haz or {}},
        "opponent_side": {"nickname": "Magnus Carlsen", "strength": 288,
                          "buffs": opp_buffs or {}, "hazards": opp_haz or {}},
        "field": {"turn": 1, "weather": weather,
                  "weather_artificial": weather_turns is not None,
                  "weather_turns": weather_turns, "field": field or {}},
    }


# ---------------------------------------------------- nothing in the arena
check("no effect strip in the battle screen",
      hasattr(w, "effects"), False)
import GUI_qt.widgets as W                              # noqa: E402
check("EffectStrip class is gone", hasattr(W, "EffectStrip"), False)

# ---------------------------------------------------------- empty field
w._apply_state(state())
app.processEvents()
check("empty field says so", "Nothing on the field." in board_text(), True)
check("tab is unbadged when clear", tab(), "Field")

# ------------------------------------------------- a web goes up on you
w._apply_state(state(you_haz={"Sticky Web": 1}))
app.processEvents()
text = " | ".join(board_text())
check("sticky web appears", "Sticky Web" in text, True)
check("...credited to the opponent", "Magnus Carlsen set it" in text, True)
check("...counted as a layer", "layers" in text, True)
check("...under your side", "YOUR SIDE" in text, True)
check("tab badges one effect", tab(), "Field  1")

# ------------------------------------------- reflect, with a countdown
w._apply_state(state(you_buffs={"Reflect": 5}, you_haz={"Sticky Web": 1}))
app.processEvents()
text = " | ".join(board_text())
check("reflect appears", "Reflect" in text, True)
check("...credited to you", "you set it" in text, True)
check("...with its turn count", "5" in board_text(), True)
tips = [r.toolTip() for r in w.field_board.findChildren(RoundedPanel)]
check("...and what it does, on hover",
      any("halves physical damage" in t for t in tips), True)
check("tab badges two", tab(), "Field  2")

for left in (4, 3, 2, 1):
    w._apply_state(state(you_buffs={"Reflect": left},
                         you_haz={"Sticky Web": 1}))
    app.processEvents()
    if str(left) not in board_text():
        check("reflect counts down to %d" % left, board_text(), left)
        break
else:
    check("reflect counts itself down 5->1", True, True)

# ------------------------------------------------- it wears off, row goes
w._apply_state(state(you_haz={"Sticky Web": 1}))
app.processEvents()
text = " | ".join(board_text())
check("reflect removed when it expires", "Reflect" in text, False)
check("...web still there", "Sticky Web" in text, True)
check("tab back to one", tab(), "Field  1")

# ------------------------------------- the opponent clears the hazard
w._apply_state(state())
app.processEvents()
check("cleared hazard leaves the board",
      "Nothing on the field." in board_text(), True)
check("tab unbadged again", tab(), "Field")

# ------------------------------------------------ a busy field, all sides
busy = state(you_buffs={"Reflect": 3, "Light Screen": 5},
             you_haz={"Sticky Web": 1, "Spikes": 2},
             opp_buffs={"Tailwind": 2},
             opp_haz={"Stealth Rock": 1, "Toxic Spikes": 1},
             field={"Trick Room": 4}, weather="Rain", weather_turns=3)
w._apply_state(busy)
app.processEvents()
text = " | ".join(board_text())
check("all three sections captioned",
      all(s in text for s in ("YOUR SIDE", "OPPONENT'S SIDE",
                              "THE BATTLEFIELD")), True)
check("hazards you laid are credited to you",
      text.count("you set it") >= 3, True)
check("trick room shown", "Trick Room" in text, True)
check("artificial weather counts down",
      "Rain" in text and "conjured" in text, True)
check("nine effects badged", tab(), "Field  9")
check("nine rows drawn", rows(), 9)
if HEADED:
    w.tabs.setCurrentIndex(w._field_tab)
    app.processEvents()
    w.grab().save(os.path.join(OUT, "field_board.png"))

# natural weather is permanent, so no countdown
w._apply_state(state(weather="Sandstorm"))
app.processEvents()
text = " | ".join(board_text())
check("arena weather has no countdown",
      "this arena's own" in text and "—" in board_text(), True)

# ------------------------------------------- a crowded field must scroll
w.tabs.setCurrentIndex(w._field_tab)
app.processEvents()
w._apply_state(state(
    you_buffs={"Reflect": 3, "Light Screen": 5, "Aurora Veil": 4,
               "Tailwind": 2},
    you_haz={"Sticky Web": 1, "Spikes": 3, "Stealth Rock": 1,
             "Toxic Spikes": 2},
    opp_buffs={"Reflect": 1, "Tailwind": 4},
    opp_haz={"Spikes": 3, "Stealth Rock": 1},
    field={"Trick Room": 4}, weather="Rain", weather_turns=2))
for _ in range(4):
    app.processEvents()
bar = w.field_scroll.verticalScrollBar()
check("fourteen effects badged", tab(), "Field  14")
check("the board is taller than its viewport",
      w.field_board.height() > w.field_scroll.viewport().height(), True)
check("so it scrolls rather than clipping", bar.maximum() > 0, True)
check("no horizontal scrollbar",
      w.field_scroll.horizontalScrollBar().isVisible(), False)
bar.setValue(bar.maximum())
app.processEvents()
check("the last row is reachable", "Rain" in board_text(), True)

# ------------------------------------------------- leaving the battle
w._apply_state(state(you_buffs={"Reflect": 3}, phase="manage"))
app.processEvents()
check("field clears when the match ends",
      "Nothing on the field." in board_text(), True)
check("tab unbadged out of battle", tab(), "Field")

# a new matchup flushes it along with the feed
w._apply_state(state(you_buffs={"Reflect": 3}))
app.processEvents()
check("board repopulates next match", tab(), "Field  1")
w._clear_feed()
app.processEvents()
check("_clear_feed wipes the board",
      "Nothing on the field." in board_text(), True)

# repeated identical states must not churn widgets
w._apply_state(busy)
app.processEvents()
before = rows()
sig = w.field_board._signature
for _ in range(5):
    w._apply_state(busy)
app.processEvents()
check("identical state does not rebuild", (rows(), w.field_board._signature),
      (before, sig))

# Terrain is its own field layer, and this board never listed it -- so the
# one screen devoted to "what is on the field" was the one place a player
# could not read it.
w.field_board.set_state({}, {}, {"weather": "Clear", "field": {},
                                 "terrain": "Misty", "terrain_turns": 3,
                                 "terrain_note": "Dragon moves are halved."})
app.processEvents()
_said = " | ".join(board_text())
check("the board lists the terrain", "Misty" in _said, True)
check("...with its countdown", "3" in _said, True)
check("...and says what it does, on the hover",
      any("halved" in panel.toolTip()
          for panel in w.field_board.findChildren(RoundedPanel)), True)

print("\n%s" % ("ALL PASS" if not failures
                else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
