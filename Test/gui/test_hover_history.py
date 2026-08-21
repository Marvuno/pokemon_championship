"""The Check History window, and the hover readout for a Pokemon in battle."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtCore import QEvent, QPoint, Qt                    # noqa: E402
from PySide6.QtGui import QHoverEvent                            # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel               # noqa: E402

from GUI_qt.main_window import MainWindow                        # noqa: E402
from GUI_qt.widgets import Chip, RoundedPanel                    # noqa: E402

app = QApplication.instance() or QApplication([])
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


def texts(widget):
    return [w.text() for w in widget.findChildren(QLabel) if w.text()]


w = MainWindow(ROOT)
w.bridge.stop()                      # no game thread; states are fed by hand
# the bridge redirects builtins.print into its event queue, and a stopped
# bridge raises Shutdown from it -- put the real one back so this file can
# report its own results
import builtins                                                  # noqa: E402
builtins.print = w.bridge._real_print
w.show()
app.processEvents()

# --------------------------------------------------------------- history
print("== check history ==")
first = {"you": "Marvin", "opponent": "Goblin", "wins": 2, "losses": 1,
         "meetings": [[4, 1], [6, 5], [2, 6]]}
w._apply_state(dict(w.game_state or {}, history_info=first))
app.processEvents()
d = w.history_dialog
check("one dialog, owned by the window", len(w.findChildren(type(d))), 1)
check("it is visible", d.isVisible())
joined = " | ".join(texts(d))
check("shows the record", "2  –  1" in joined)
check("shows every scoreline",
      all(s in joined for s in ("4  –  1", "6  –  5", "2  –  6")))
check("a Close button is offered", any(t == "Close" for t in texts(d)))

# a second look at someone else reuses the same window
d.close()
second = {"you": "Marvin", "opponent": "Rudolf", "wins": 0, "losses": 0,
          "meetings": []}
w._apply_state(dict(w.game_state or {}, history_info=second))
app.processEvents()
check("still exactly one dialog", len(w.findChildren(type(d))), 1)
check("re-shown for the next opponent", d.isVisible())
joined = " | ".join(texts(d))
check("switched to the new opponent", "Rudolf" in joined)
check("says you have never faced them", "never faced Rudolf" in joined)
check("last opponent's scorelines are gone", "6  –  5" not in joined)
check("no meetings list when there are none", not d.scroll.isVisible())
d.close()

# ----------------------------------------------------------- hover readout
print("\n== hover readout ==")


def mon(name, iv=None, moves=("Thunderbolt", "Surf"), tier="High"):
    return {
        "name": name, "sprite": name.lower(), "types": ["Electric"],
        "tier": tier, "ability": ["Static"], "status": "Normal",
        "hp": 100, "max_hp": 100, "iv": list(iv or [31, 20, 10, 5, 25, 30]),
        "nominal": [120, 110, 100, 130, 105, 140], "total_iv": 121,
        "moveset": ["Switching"] + list(moves),
        "moves": {m: {"name": m, "type": "Electric", "category": "Special",
                      "power": 90, "accuracy": 1.0} for m in moves},
        "modifier": [0] * 9, "volatile": {}, "disabled": {},
        "charging": ["", "", 0], "fainted": False, "active": False,
    }


THEIRS = [mon("Raichu"), mon("Jolteon", iv=[31] * 6, moves=("Thunder",)),
          mon("Zapdos", tier="Very High")]
MINE = [mon("Pikachu"), mon("Magnezone")]

state = dict(w.game_state or {})
state.update({
    "phase": "battle", "battle_seq": 1,
    "player": THEIRS and MINE[0], "opponent": THEIRS[0],
    "player_team": [{"name": m["name"], "hp": 100, "max_hp": 100,
                     "fainted": False} for m in MINE],
    "opponent_team": [{"name": m["name"], "hp": 100, "max_hp": 100,
                       "fainted": False} for m in THEIRS],
    "player_roster": MINE,
    "opponent_roster": None,
    "opponent_known": False,
})
w._apply_state(state)
app.processEvents()

card = w.scout_card
check("the card starts hidden", not card.isVisible())


def hover_sprite(label):
    event = QHoverEvent(QEvent.HoverEnter, QPoint(4, 4), QPoint(-1, -1))
    app.sendEvent(label, event)
    app.processEvents()


def leave_sprite(label):
    app.sendEvent(label, QHoverEvent(QEvent.HoverLeave, QPoint(-1, -1),
                                     QPoint(4, 4)))
    app.processEvents()


# -- their side, not scouted
hover_sprite(w.opponent_sprite)
check("hovering their sprite opens the card", card.isVisible())
joined = " | ".join(texts(card))
check("it names the Pokemon on the field", "Raichu" in joined)
check("but not its moves", "Thunderbolt" not in joined)
check("and not its IVs", "31" not in joined)
check("it says how to earn that", "Scout Opponent" in joined)
leave_sprite(w.opponent_sprite)
check("leaving closes it", not card.isVisible())

# -- your own side is never gated
hover_sprite(w.player_sprite)
joined = " | ".join(texts(card))
check("your own sprite shows your moves", "Thunderbolt" in joined)
check("...and your IVs", "31" in joined)
check("...and the stat each IV produced", "120" in joined)
check("...and the ability", "Static" in joined)
check("...and the IV total", any("total 121" in t for t in texts(card)))
check("a move row per move",
      len([p for p in card.findChildren(RoundedPanel)
           if any(l.text() in ("Thunderbolt", "Surf")
                  for l in p.findChildren(QLabel))]), 2)
check("type chips are drawn", any(c.text() == "ELECTRIC"
                                 for c in card.findChildren(Chip)))
leave_sprite(w.player_sprite)

# -- scouted: their whole team, bench included, via the pips
state["opponent_known"] = True
state["opponent_roster"] = THEIRS
w._apply_state(state)
app.processEvents()
hover_sprite(w.opponent_sprite)
joined = " | ".join(texts(card))
check("once scouted their moves show", "Thunderbolt" in joined)
check("...and their IVs", "31" in joined)
check("no locked note any more", "About Opponent" not in joined)

w._hover_pip("opponent", 1)
app.processEvents()
joined = " | ".join(texts(card))
check("a pip reaches the bench", "Jolteon" in joined)
check("...with that one's own moves", "Thunder" in joined)
check("...and its own IVs (six perfect)",
      len([t for t in texts(card) if t == "31"]), 6)
w._hover_pip("opponent", 2)
app.processEvents()
check("the next pip switches Pokemon", "Zapdos" in " | ".join(texts(card)))
w._hover_pip("opponent", -1)
app.processEvents()
check("leaving the pips closes it", not card.isVisible())

# -- pip hit testing
pips = w.opponent_card.pips
check("pip 0 is hit at its left edge", pips.pip_at(2), 0)
check("pip 1 is hit after the gap", pips.pip_at(2 + pips.PIP_D + pips.PIP_GAP),
      1)
check("past the last pip is nothing", pips.pip_at(9999), -1)
check("before the first is nothing", pips.pip_at(-5), -1)

# -- out of battle it stays shut
# No processEvents between setting the state and reading the result.
#
# `w.bridge.stop()` at the top does not empty the event queue: the worker was
# alive for the moment between MainWindow.__init__ starting it and the stop,
# and it queued its own EV_STATE for the title screen. `_pump` -- driven by
# the window's own 20ms timer -- drains those on any later event-loop turn
# and hands them to _apply_state, so `w.game_state` reverts to phase=None
# with no teams, and _show_scout closes the card. That is what the
# diagnosis below caught, and why this only failed under load: the busier
# the machine, the longer the worker ran before being stopped.
#
# Hovering is synchronous, so nothing here needs the event loop at all.
w._apply_state(state)
w._hover_pip("opponent", 0)
if not card.isVisible():
    # one-off diagnosis: which branch of _show_scout dropped the card
    import io as _io
    live = w.game_state or {}
    _io.open("Test/gui/_out/hover_why.txt", "w", encoding="utf-8").write(
        "\n".join([
            "phase=%r" % live.get("phase"),
            "known=%r" % live.get("opponent_known"),
            "opp_team=%d" % len(live.get("opponent_team") or []),
            "opp_roster=%s" % type(live.get("opponent_roster")).__name__,
            "entry=%r" % (w._scout_entry("opponent", 0),),
        ]) + "\n")
check("open again for the next check", card.isVisible())
w._apply_state(dict(state, phase="prebattle"))
app.processEvents()
check("leaving the battle closes it", not card.isVisible())
hover_sprite(w.opponent_sprite)
check("and it will not open outside a battle", not card.isVisible())

# -- it stays inside the window
w._apply_state(state)
app.processEvents()
w._hover_pip("opponent", 0)
app.processEvents()
bounds = w._scout_bounds()
check("the card sits inside the window",
      bounds.contains(card.geometry()) or not card.isVisible(),
      True)

try:
    w.bridge.stop()
except Exception:
    pass
print("\n" + ("ALL PASS" if not fails else "%d FAILURES: %s"
                                           % (len(fails), fails)))
sys.exit(1 if fails else 0)


# --------------------------------------------------------------------------
# The hover card must refresh when the stages change, not just when a
# different Pokemon is hovered. Its token used to be (side, index, known,
# name), so landing a stat boost and hovering the same Pokemon again showed
# the stages it had the first time.
def mon_with(mod, vol):
    return {"name": "Garchomp", "sprite": "garchomp", "types": ["Dragon"],
            "tier": "V", "ability": ["Rough Skin"], "status": "Normal",
            "hp": 100, "max_hp": 100, "stats": [100] * 6,
            "nominal": [100] * 6, "iv": [20] * 6, "base": [80] * 6,
            "total": 600, "total_iv": 120, "modifier": mod, "volatile": vol,
            "moveset": ["Earthquake"], "moves": {}, "disabled": {},
            "charging": ["", "", 0], "protecting": False, "fainted": False,
            "active": True, "index": 0}


def battle_with(mod, vol):
    entry = mon_with(mod, vol)
    return {"phase": "battle", "battle_seq": 1, "stage": 3,
            "opponent_known": True,
            "player_side": {"nickname": "M", "strength": 507},
            "opponent_side": {"nickname": "C", "strength": 300},
            "player": entry, "opponent": mon_with([0] * 9, {}),
            "player_team": [entry], "opponent_team": [mon_with([0] * 9, {})]}


def hovered():
    w._show_scout("player", 0)
    app.processEvents()
    return [l.text() for l in w.scout_card.findChildren(QLabel) if l.text()]


w._apply_state(battle_with([0] * 9, {}))
app.processEvents()
before = hovered()
check("nothing boosted yet", "STAT STAGES" not in before)
w._apply_state(battle_with([0, 2, 0, 0, 0, 0, 0, 0, 0], {"Confused": 3}))
app.processEvents()
after = hovered()
check("a new boost refreshes the same card", "STAT STAGES" in after)
check("...showing the exact stage", "+2" in after)
check("...and the condition", "CONFUSED" in after)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
