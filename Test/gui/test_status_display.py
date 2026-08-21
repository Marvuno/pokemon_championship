"""Where each kind of information about a Pokemon is shown.

Two rules, and the split between them is the point:

  * the **status card**, always on screen, carries what you have to react to
    this turn -- typing, HP, a status condition, and the volatile conditions
    (Confused, Bound, Seeded). Those used to be in the hover card only, so
    the one class of thing that changes what you do *now* was the one thing
    you had to go hunting for with the mouse.
  * the **hover card**, opened deliberately, carries what you go looking for
    -- the moveset, the IVs, and the stat stages.

Stat stages are six dots rather than a signed number. Six because six is the
range, grey for a stage that is not there, green up and red down.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

from PySide6.QtWidgets import QApplication                          # noqa: E402

app = QApplication.instance() or QApplication([])

from GUI import theme as T                                          # noqa: E402
from GUI_qt import widgets as W                                     # noqa: E402
from GUI_qt.fonts import Fonts                                      # noqa: E402

FAILURES = []
fonts = Fonts()


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


def chips(widget):
    return [c.text() for c in widget.findChildren(W.Chip)]


print("-- stat stages, as dots --")
dots = W.StageDots()
check("six dots, because six is the range", dots.MAX, 6)
for stage, want in ((0, 0), (2, 2), (-1, -1), (6, 6), (-6, -6),
                    (9, 6), (-9, -6)):
    dots.set_stage(stage)
    check("a stage of %+d shows %+d" % (stage, want), dots._stage, want)

print()
print("-- the hover card --")
scout = W.ScoutCard(fonts)
scout.set_mon({"name": "Pikachu", "types": ["Electric"], "hp": 50,
               "max_hp": 100,
               "modifier": [0, -1, 0, 2, 0, -3, 0, 0, 0],
               "volatile": {"Confused": 3, "Binding": 2}},
              known=True, side="player")
rows = scout.findChildren(W.StageDots)
check("every stat gets a row, moved or not", len(rows), len(W.STAGE_LABELS))
check("and each shows that stat's stage",
      [d._stage for d in rows], [-1, 0, 2, 0, -3, 0, 0, 0])
check("no conditions are listed here any more",
      [c for c in chips(scout) if c in ("CONFUSED", "BOUND")], [])

scout.set_mon({"name": "Pikachu", "types": ["Electric"], "hp": 50,
               "max_hp": 100, "modifier": [0] * 9, "volatile": {}},
              known=True, side="player")
check("an untouched Pokemon still lists every stat",
      len(scout.findChildren(W.StageDots)), len(W.STAGE_LABELS))
check("...all of them at zero",
      {d._stage for d in scout.findChildren(W.StageDots)}, {0})

print()
print("-- the status card --")
card = W.CombatantCard("player", fonts)
base = {"name": "Pikachu", "types": ["Electric"], "hp": 50, "max_hp": 100,
        "status": "Normal", "ability": ["Static"], "volatile": {}}
def typing(widget):
    return [widget.chips.itemAt(i).widget().text()
            for i in range(widget.chips.count())
            if widget.chips.itemAt(i).widget() is not None]


def condition(widget):
    return [widget.status_row.itemAt(i).widget().text()
            for i in range(widget.status_row.count())
            if widget.status_row.itemAt(i).widget() is not None]


card.set_mon(dict(base), animate=False)
check("nothing to warn about, nothing shown", chips(card), ["ELECTRIC"])

# the non-volatile status has a row of its own under the typing
two_types = dict(base, types=["Electric", "Steel"])
card.set_mon(dict(two_types, status="Poison"), animate=False)
check("the typing row holds only the typing",
      typing(card), ["ELECTRIC", "STEEL"])
check("...and the status sits on its own row below",
      condition(card), ["PSN"])
card.set_mon(dict(two_types, status="Fainted", fainted=True, hp=0),
             animate=False)
check("fainted goes on that row too, spelled out",
      (typing(card), condition(card)),
      (["ELECTRIC", "STEEL"], ["FAINTED"]))
card.set_mon(dict(two_types), animate=False)
check("and the row empties when it lapses", condition(card), [])

card.set_mon(dict(base, volatile={"Confused": 3}), animate=False)
check("a volatile condition appears", chips(card), ["ELECTRIC", "CONFUSED"])

card.set_mon(dict(base, status="Poison",
                  volatile={"Confused": 3, "Binding": 2}), animate=False)
check("alongside the status condition and the typing",
      chips(card), ["ELECTRIC", "PSN", "BOUND", "CONFUSED"])

card.set_mon(dict(base, volatile={"Confused": 1, "Binding": 1,
                                  "LeechSeed": 1, "Torment": 1,
                                  "Curse": 1}), animate=False)
shown = chips(card)
check("a card's width is respected -- the rest become a count",
      shown, ["ELECTRIC", "BOUND", "CONFUSED", "CURSED", "+2"])
overflow = [c for c in card.findChildren(W.Chip) if c.text() == "+2"]
check("and the count says what it is hiding",
      "SEEDED" in (overflow[0].toolTip() if overflow else ""))

card.set_mon(dict(base), animate=False)
check("conditions clear when they lapse", chips(card), ["ELECTRIC"])

# the churn guard has to know about conditions, or the row never updates
card.set_mon(dict(base, volatile={"Confused": 2}), animate=False)
first = card._chip_state
card.set_mon(dict(base, volatile={"Confused": 2}), animate=False)
check("an unchanged card is not rebuilt", card._chip_state, first)
card.set_mon(dict(base, volatile={"Frighten": 2}), animate=False)
check("a changed condition is", chips(card), ["ELECTRIC", "FRIGHTENED"])

print()
print("-- the two cards agree on what things are called --")
check("both read the same label table",
      W.CONDITION_LABELS["Binding"], "BOUND")
check("and the engine's bookkeeping is never shown",
      W.live_conditions({"Turn": 4, "Grounded": 1, "NonVolatile": 2}), [])

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
