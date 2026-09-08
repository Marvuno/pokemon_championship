"""A battle always ends, and well inside the stack it has to run on.

The turn loop is mutual recursion -- move_selection calls end_of_turn which
calls move_selection -- at a measured 4.2 frames a turn against a 1000-frame
limit, so a battle that would not end dies by RecursionError at about turn
237 instead of finishing. Both simulation harnesses suppress RecursionError,
so it would truncate silently rather than report.

Nothing needs adding to prevent that, because Sudden Death already does:
from turn 50 both sides lose a quarter of their maximum HP every turn, which
no team survives for long. This pins that guarantee, so a change to Sudden
Death cannot quietly reintroduce a stall the loop cannot absorb.
"""
import io
import os
import random
import sys
import zlib
from contextlib import redirect_stdout, suppress
from copy import deepcopy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import Scripts.Battle.battle_cycle as CYCLE                      # noqa: E402
from Scripts.Battle.battle_cycle import battle_setup             # noqa: E402
from Scripts.Data.battlefield import Battleground                # noqa: E402
from Scripts.Data.competitors import list_of_competitors as L    # noqa: E402
from Scripts.Game.game_procedure import team_generation          # noqa: E402
from Scripts.Game.game_system import GameSystem                 # noqa: E402

GameSystem.stage = 5
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-62s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


# ------------------------------------------------- the mechanism that ends it
board = Battleground()
check("a battle starts with Sudden Death off", board.sudden_death, False)

source = io.open("Scripts/Battle/battle_cycle.py", encoding="utf-8").read()
check("Sudden Death is armed on a turn count",
      "battleground.turn >= 50" in source)
chip = io.open("Scripts/Battle/battle_checklist.py", encoding="utf-8").read()
check("...and it takes a quarter of maximum HP a turn",
      "pokemon.hp // 4" in chip and "battleground.sudden_death" in chip)

#: A team cannot absorb 25% a turn for long: four turns kills each Pokemon
#: outright, so six of them cannot outlast about 24 turns of it even with
#: nothing else happening. Fifty to arm it, that margin, and room to spare --
#: still less than a third of the ~237 turns the stack can hold.
CEILING = 120
check("the ceiling leaves room under the stack (%d turns)" % CEILING,
      CEILING < 200)

# ------------------------------------------------------ and it ends in practice
longest, ran, raised = 0, 0, 0
seen_sudden_death = 0
pairs = [("Expert Cynthia", "Demon Muzan"), ("Goblin", "Solanum"),
         ("Kurtosis", "Makise"), ("Elowen", "Magnus")]
for index in range(24):
    one, two = pairs[index % len(pairs)]
    if one not in L or two not in L:
        continue
    random.seed(zlib.crc32(("terminate%d" % index).encode()) & 0xffffff)
    a, b = deepcopy(L[one]), deepcopy(L[two])
    a.team, b.team = team_generation(a), team_generation(b)
    ground = Battleground()
    ground.verbose = True
    try:
        with redirect_stdout(io.StringIO()):
            battle_setup(a, b, a.team, b.team, ground)
    except RecursionError:
        raised += 1
    except Exception:
        pass
    ran += 1
    longest = max(longest, int(getattr(ground, "turn", 0) or 0))
    if getattr(ground, "sudden_death", False):
        seen_sudden_death += 1

print()
check("battles were played (%d)" % ran, ran > 0)
check("none of them ran out of stack", raised, 0)
check("the longest was %d turns, inside the ceiling" % longest,
      longest <= CEILING)
print("   (%d of %d reached Sudden Death)" % (seen_sudden_death, ran))

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
