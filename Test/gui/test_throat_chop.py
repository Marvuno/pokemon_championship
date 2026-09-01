"""Throat Chop must not crash the battle it is used in.

`check_move_disable`'s "Sound" branch read `previous_move.name` inside a
`try` that catches KeyError only. `previous_move` is "" -- a string, with no
`.name` -- until the Pokemon has taken a turn, so the read raised
AttributeError and killed the battle. It needed three things at once, which
is why it looked random: the target owns a sound move, that move was already
disabled by an earlier Throat Chop, and the target had not moved yet.

Scrafty knows Throat Chop, which is where this was first seen.

    python Test/gui/test_throat_chop.py <root> <out>
"""
import os
import sys
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                            # noqa: F401,E402
from Scripts.Battle.context import Side, Turn                 # noqa: E402
from Scripts.Battle.move_additional_effect import (           # noqa: E402
    move_special_effect)
from Scripts.Data.battlefield import Battleground             # noqa: E402
from Scripts.Data.competitors import list_of_competitors      # noqa: E402
from Scripts.Data.moves import list_of_moves                  # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon              # noqa: E402

fails = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(what)


SOUND = [n for n, m in list_of_moves.items() if "f" in (m.flags or "")]
owners = [n for n, m in list_of_pokemon.items()
          if any(x in SOUND for x in (m.moveset or []))]
check("some Pokemon own a sound move (%d)" % len(owners), bool(owners))
check("Scrafty still knows Throat Chop",
      "Throat Chop" in (list_of_pokemon["Scrafty"].moveset or []))

field = [c for c in list_of_competitors.values() if not c.main]


def throat_chop(target_name, already_disabled, moved):
    a, b = deepcopy(field[0]), deepcopy(field[1])
    user = deepcopy(list_of_pokemon["Scrafty"])
    target = deepcopy(list_of_pokemon[target_name])
    for p in (user, target):
        p.hp = 200
        p.battle_stats = [200, 80, 80, 80, 80, 80]
        p.status = "Normal"
        p.disabled_moves = {}
    if already_disabled:
        for name in target.moveset:
            if name in SOUND:
                target.disabled_moves[name] = 2
    if moved:
        target.previous_move = deepcopy(list_of_moves["Throat Chop"])
    turn = Turn(Battleground(), Side(a, [user], user),
                Side(b, [target], target))
    move_special_effect(turn, deepcopy(list_of_moves["Throat Chop"]))
    return target


victim = next(n for n in owners
              if len([x for x in list_of_pokemon[n].moveset
                      if x in SOUND]) >= 1)
print("using %r as the target" % victim)

# the exact state that crashed: owns a sound move, already disabled, and the
# target has not taken a turn, so previous_move is still ""
for label, disabled, moved in (
        ("first Throat Chop, target has not moved", False, False),
        ("second one, target still has not moved", True, False),
        ("second one, target has moved", True, True)):
    try:
        target = throat_chop(victim, disabled, moved)
        check("  %s" % label, True)
    except AttributeError as error:
        check("  %s" % label, "AttributeError: %s" % error)

# and it actually does its job
target = throat_chop(victim, False, False)
disabled = [n for n in target.moveset if target.disabled_moves.get(n)]
check("Throat Chop disables the target's sound moves (%s)" % disabled,
      bool(disabled))
check("...and leaves the non-sound ones alone",
      all(n in SOUND for n in disabled), True)

print()
print("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(fails))
sys.exit(1 if fails else 0)
