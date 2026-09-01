"""The AI must stop throwing priority moves at something they cannot reach.

Queenly Majesty, Dazzling and Psychic Terrain all refuse a priority move by
setting its accuracy to 0. The two abilities used to do that *inside* a
`call.ground.reality` guard -- and `reality` is False while the AI scores its
candidates, so the move looked perfectly usable during evaluation and was
refused on the real turn. The AI picked it, lost the turn, and picked it
again, for the whole battle.

Two things are checked: that the refusal is visible while scoring (the cause),
and that the AI's choices actually change because of it (the effect).

    python Test/gui/test_priority_immunity.py <root> <out>
"""
import os
import random
import sys
from contextlib import redirect_stdout, suppress
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                            # noqa: F401,E402
import Scripts.Battle.ability_effects as AE                   # noqa: E402
from Scripts.Battle.battle_cycle import battle_setup          # noqa: E402
from Scripts.Data.battlefield import Battleground             # noqa: E402
from Scripts.Data.competitors import list_of_competitors      # noqa: E402
from Scripts.Data.moves import list_of_moves                  # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon              # noqa: E402
from Scripts.Game.game_procedure import team_generation       # noqa: E402
from Scripts.Game.game_system import GameSystem               # noqa: E402

fails = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(what)


# -- the cause: the refusal has to happen whether or not this is a real turn
class _Ground:
    def __init__(self, real):
        self.reality = real


class _Call:
    def __init__(self, real, priority=1):
        self.ground = _Ground(real)
        self.move = deepcopy(list_of_moves["Bullet Punch"])
        self.move.priority = priority
        self.target = deepcopy(list_of_pokemon["Pikachu"])
        self.user = self.target


print("-- the refusal is not hidden from the scorer --")
for name, effect in (("Queenly Majesty", AE.queenlymajesty),
                     ("Dazzling", AE.dazzling)):
    for real in (True, False):
        call = _Call(real)
        with redirect_stdout(open(os.devnull, "w")):
            effect(call)
        check("%s refuses a priority move (reality=%s)" % (name, real),
              call.move.accuracy, 0)
    # and leaves an ordinary move alone
    call = _Call(False, priority=0)
    effect(call)
    check("%s leaves a non-priority move alone" % name,
          call.move.accuracy > 0, True)

# -- the effect: a move that cannot land must not win the ranking
print()
print("-- and the AI ranks it last --")
import Scripts.Battle.ai as AI                                 # noqa: E402

# A scored row is [priority, damage, effect, composite]. The blocked move is
# the one the AI liked best on every count until the penalty was applied --
# which is exactly the case that kept being re-picked.
# BLENDED prices one point of priority at PRIORITY_WORTH, so a priority move
# wins while it gives up less score than that -- which is the whole point of
# pricing it rather than ranking it first.
PRIORITY_MOVE, ORDINARY = 0, 1
scores = {PRIORITY_MOVE: [1, 20, 0, 20], ORDINARY: [0, 30, 0, 30]}
order = sorted(scores, key=lambda i: AI.move_ranking(scores, i, AI.BLENDED))
check("a priority move still wins when it can land",
      order[0], PRIORITY_MOVE)

# ...and once the scorer has docked it for accuracy 0 it cannot win at all.
# The damage half is zeroed on the same line, because damage score is already
# multiplied by accuracy.
BLOCKED = PRIORITY_MOVE
scores[BLOCKED] = [1 - AI.UNUSABLE_MOVE_PENALTY, 0, 0, 0]
order = sorted(scores, key=lambda i: AI.move_ranking(scores, i, AI.BLENDED))
check("a blocked one loses to an ordinary move", order[0], ORDINARY)
check("...and is ranked last", order[-1], BLOCKED)

# The penalty has to stay wired to accuracy. Docking a single point was not
# enough before: BLENDED prices one priority point at 25, so a priority move
# scored 0 for damage still outranked everything that could actually land.
source = open(os.path.join(ROOT, "Scripts", "Battle", "ai.py"),
              encoding="utf-8").read()
check("ai.py penalises a move that cannot reach",
      "if move.accuracy <= 0:" in source
      and "UNUSABLE_MOVE_PENALTY" in source.split("if move.accuracy <= 0:")[1][:200],
      True)

print()
print("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(fails))
sys.exit(1 if fails else 0)
