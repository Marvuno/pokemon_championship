"""Sylvan Sprout plants a Sylvan seed on whatever the opponent brings in.

Sylvan Sprout is the character ability; a Sylvan seed is the status it
plants. They are not the same thing and the wording matters in the log,
the condition chip and Elowen's write-up.

A Sylvan seed is not a Leech Seed. It is half strength -- 1/16 of maximum HP
a turn each way rather than 1/8 -- because the ability plants one on every
arrival for free, where the move spends a turn on each. The engine tells them
apart by the value stored in `volatile_status['LeechSeed']`: SYLVAN_SEED for
this one, 1 for the move. Only the two draining lines in battle_checklist read
that number; everything else asks whether it is above zero.

At full strength this was worth +32.4 points of win rate and put a rating-188
competitor 6th of 72 with team calibre held equal. Half strength is +19.0.

    python Test/gui/test_sylvan_sprout.py <root> <out>
"""
import io
import os
import sys
from contextlib import redirect_stdout
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                            # noqa: F401,E402
from Scripts.Battle.constants import (DEFAULT_SEED_SHARE,     # noqa: E402
                                      FOE_ARRIVAL_PHASE, SEED_SHARE,
                                      SYLVAN_SEED)
from Scripts.Battle.context import Side, Turn                 # noqa: E402
from Scripts.Data.battlefield import Battleground             # noqa: E402
import Scripts.Data.character_abilities as CA                 # noqa: E402
from Scripts.Data.character_abilities import UseCharacterAbility  # noqa: E402
from Scripts.Data.competitors import (list_of_competitors,    # noqa: E402
                                      ability_text)
from Scripts.Data.pokemon import list_of_pokemon              # noqa: E402

fails = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(what)


field = [c for c in list_of_competitors.values() if not c.main]


def arrival(foe_name):
    """Side A brings `foe_name` in; side B holds Sylvan Sprout."""
    a, b = deepcopy(field[0]), deepcopy(field[1])
    a.ability = b.ability = "Sylvan Sprout"     # both, to prove it is one-way
    arriving = deepcopy(list_of_pokemon[foe_name])
    standing = deepcopy(list_of_pokemon["Pikachu"])
    for p in (arriving, standing):
        p.hp = 160
        p.battle_stats = [160, 60, 60, 60, 60, 60]
        p.status = "Normal"
        p.volatile_status["Grounded"] = 1
    turn = Turn(Battleground(), Side(a, [arriving], arriving),
                Side(b, [standing], standing))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn.flip(), "", abilityphase=FOE_ARRIVAL_PHASE)
    return arriving, standing


print("-- it fires on the opponent's arrival, and only on theirs --")
seeded, mine = arrival("Scrafty")
# the phase map is built inside the dispatcher on its first call, so it is
# read after one rather than imported
check("it is registered on the foe-arrival phase only",
      CA._CHARACTER_PHASES.get("Sylvan Sprout"), (FOE_ARRIVAL_PHASE,))
check("a grounded non-Grass arrival is seeded",
      seeded.volatile_status["LeechSeed"], SYLVAN_SEED)
check("...and the holder's own Pokemon never is",
      mine.volatile_status["LeechSeed"], 0)

print()
print("-- Leech Seed's own rules still apply --")
who, _ = arrival("Venusaur")
check("  a Grass type is not seeded", who.volatile_status["LeechSeed"], 0)
# Being off the ground is no defence. Leech Seed is not a hazard like
# Spikes -- it reaches a Flying type or a Levitate holder in the real games,
# and both seeds reach them here.
for label, name in (("a Flying type", "Crobat"),
                    ("a Levitate holder", "Chimecho"),
                    ("a Fire/Flying type", "Charizard")):
    who, _ = arrival(name)
    check("  %s IS seeded -- seeds are not a ground hazard" % label,
          who.volatile_status["LeechSeed"], SYLVAN_SEED)

print()
print("-- it is a Sylvan seed, worth half a Leech Seed --")
check("the marker is not the move's", SYLVAN_SEED != 1, True)
check("a Sylvan seed drains a sixteenth",
      SEED_SHARE.get(SYLVAN_SEED), 16)
check("...where the move drains an eighth", DEFAULT_SEED_SHARE, 8)
check("on a 160 HP Pokemon that is %d against %d"
      % (160 // SEED_SHARE[SYLVAN_SEED], 160 // DEFAULT_SEED_SHARE),
      160 // SEED_SHARE[SYLVAN_SEED] * 2, 160 // DEFAULT_SEED_SHARE)

# the two draining lines are the only readers of the number; if anything else
# starts reading it, the marker stops being free to carry strength
source = open(os.path.join(ROOT, "Scripts", "Battle", "battle_checklist.py"),
              encoding="utf-8").read()
check("the drain reads the seed's kind", "SEED_SHARE.get(" in source)

print()
print("-- and the Leech Seed move obeys the same rule --")
# It used to obey neither: it would seed a Venusaur, a Crobat, or something
# half-way through Fly, while the ability that copies it refused all three.
from Scripts.Battle.move_additional_effect import (              # noqa: E402
    check_move_target_volatile_status_effect)
from Scripts.Data.moves import list_of_moves                     # noqa: E402

_seed = list_of_moves["Leech Seed"]
_effect = _seed.special_effect
_effect = _effect[0] if isinstance(_effect, list) else _effect


def cast_leech_seed(target_name, ungrounded=False):
    a, b = deepcopy(field[0]), deepcopy(field[1])
    a.ability = b.ability = ""
    user = deepcopy(list_of_pokemon["Pikachu"])
    target = deepcopy(list_of_pokemon[target_name])
    for p in (user, target):
        p.hp = 160
        p.battle_stats = [160, 60, 60, 60, 60, 60]
        p.status = "Normal"
        p.volatile_status["Grounded"] = 1
    if ungrounded:
        target.volatile_status["Grounded"] = 0
    turn = Turn(Battleground(), Side(a, [user], user),
                Side(b, [target], target))
    with redirect_stdout(io.StringIO()):
        check_move_target_volatile_status_effect(turn, deepcopy(_seed),
                                                 _effect)
    return target.volatile_status["LeechSeed"]


check("the move seeds an ordinary target", cast_leech_seed("Scrafty"), 1)
check("...refuses a Grass type", cast_leech_seed("Venusaur"), 0)
check("...but reaches a Flying type", cast_leech_seed("Crobat"), 1)
check("...and something off the ground",
      cast_leech_seed("Scrafty", ungrounded=True), 1)
check("the move plants a full-strength seed, not a Sylvan one",
      cast_leech_seed("Scrafty") != SYLVAN_SEED, True)

print()
print("-- and the player is told which seed it is --")
from GUI_qt.widgets import live_conditions                     # noqa: E402
check("a Sylvan seed reads as its own condition",
      live_conditions({"LeechSeed": SYLVAN_SEED}), ["SYLVAN SEED"])
check("...and the move's still reads as SEEDED",
      live_conditions({"LeechSeed": 1}), ["SEEDED"])
text = ability_text(list_of_competitors["Elowen"]).lower()
check("Elowen's write-up calls it a Sylvan seed", "sylvan seed" in text)
check("...and says what it is worth", "1/16" in text)

print()
print("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(fails))
sys.exit(1 if fails else 0)
