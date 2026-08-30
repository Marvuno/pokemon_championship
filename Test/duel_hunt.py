"""Battle two named Pokemon over and over and report anything that raises.

`crash_hunt.py` plays whole competitors' teams; this pins the two Pokemon and
varies only the seed, which is what you want once a player has said "it
crashes when X meets Y".

    python Test/duel_hunt.py "Faker-Greninja" "Scrafty"
    python Test/duel_hunt.py "Faker-Greninja" "Scrafty" 400
"""
import collections
import io
import operator
import os
import random
import sys
import traceback
from contextlib import redirect_stdout
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle as CYCLE                     # noqa: E402
from Scripts.Data.battlefield import Battleground               # noqa: E402
from Scripts.Data.competitors import list_of_competitors        # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                # noqa: E402
from Scripts.Game.game_system import GameSystem                 # noqa: E402

ONE = sys.argv[1] if len(sys.argv) > 1 else "Faker-Greninja"
TWO = sys.argv[2] if len(sys.argv) > 2 else "Scrafty"
ROUNDS = int(sys.argv[3]) if len(sys.argv) > 3 else 300
#: moves that must be on the given side, so an interaction a player named can
#: actually be reached instead of waiting for a random sample to include it
PIN_ONE = [m for m in (sys.argv[4].split("|") if len(sys.argv) > 4 else []) if m]
PIN_TWO = [m for m in (sys.argv[5].split("|") if len(sys.argv) > 5 else []) if m]

GameSystem.stage = 5


def build(name, iv=31, pinned=()):
    """The three steps team_generation does (game_procedure.py:125)."""
    if name not in list_of_pokemon:
        raise SystemExit("no Pokemon called %r" % name)
    mon = deepcopy(list_of_pokemon[name])
    mon.iv = [iv] * 6
    mon.total_iv = sum(mon.iv)
    mon.nominal_base_stats = list(map(operator.add, mon.base_stats, mon.iv))
    mon.ability = [random.choice(mon.ability)]
    pool = [m for m in mon.moveset if m]
    keep = [m for m in pinned if m in pool]
    rest = [m for m in pool if m not in keep]
    random.shuffle(rest)
    mon.moveset = (keep + rest)[:max(4, len(keep))]
    return mon


faults = collections.defaultdict(list)
played = 0
turns = []
for index in range(ROUNDS):
    seed = 4000 + index
    random.seed(seed)
    one = deepcopy(list_of_competitors["Champion Marvin"])
    two = deepcopy(list_of_competitors["Emperor Marvuno"])
    one.name = one.nickname = "A"
    two.name = two.nickname = "B"
    # character abilities LEFT ON: a player meets them, and clearing them is
    # how the first pass over this missed everything
    one.team = [build(ONE, pinned=PIN_ONE)]
    two.team = [build(TWO, pinned=PIN_TWO)]
    try:
        with redirect_stdout(io.StringIO()):
            ground = Battleground()
            ground.verbose = True
            CYCLE.battle_setup(one, two, one.team, two.team, ground)
        played += 1
        turns.append(ground.turn)
    except Exception:
        trace = traceback.format_exc()
        frames = [line for line in trace.splitlines() if line.startswith("  File")]
        key = (frames[-1].strip() if frames else "?") + " | " + trace.splitlines()[-1]
        faults[key].append((seed, one.team[0].ability, two.team[0].ability,
                            list(one.team[0].moveset), list(two.team[0].moveset),
                            trace))

print("%s vs %s: %d duels, %d finished, %d distinct faults"
      % (ONE, TWO, ROUNDS, played, len(faults)))
if turns:
    print("turns: min %d, median %d, max %d"
          % (min(turns), sorted(turns)[len(turns) // 2], max(turns)))
if not faults:
    print("no crashes")
    sys.exit(0)
print()
for key, hits in sorted(faults.items(), key=lambda kv: -len(kv[1])):
    seed, ability_one, ability_two, moves_one, moves_two, trace = hits[0]
    print("=" * 74)
    print("%d hit(s) of %d duels" % (len(hits), ROUNDS))
    print("first at seed %d" % seed)
    print("   %s: %s  %s" % (ONE, ability_one, moves_one))
    print("   %s: %s  %s" % (TWO, ability_two, moves_two))
    print(trace[-1600:])
sys.exit(1)
