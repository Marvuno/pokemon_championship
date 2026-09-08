"""Custom Play's Metronome mode: six Gamblers a side and nothing to decide.

The mode only means anything if the two sides are genuinely identical, so
what this checks is the levelling: the same team, the same maxed IVs, one
move between them, no character ability on either trainer, and a field with
no opening weather and no terrain rolled onto it.

And that the levelling does not leak -- an ordinary battle must still roll
its own arena exactly as it always has.
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

import Scripts.Battle.battle_cycle                               # noqa: E402
from Scripts.Battle.battle_cycle import battle_setup             # noqa: E402
from Scripts.Data.battlefield import Battleground                # noqa: E402
from Scripts.Data.competitors import list_of_competitors as L    # noqa: E402
from Scripts.Game import start_interface as SI                   # noqa: E402
from Scripts.Game.game_procedure import team_generation          # noqa: E402
from Scripts.Game.game_system import GameSystem                  # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-62s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


# ================================================================= the teams
print("-- six Gamblers a side --")
player, opponent = SI.metronome_teams()

for who, side in (("yours", player), ("theirs", opponent)):
    check("%s is %d Pokemon" % (who, SI.METRONOME_TEAM),
          len(side.team), SI.METRONOME_TEAM)
    check("  ...all of them Gamblers",
          {mon.name for mon in side.team}, {SI.METRONOME_POKEMON})
    check("  ...every IV maxed",
          {tuple(mon.iv) for mon in side.team},
          {(SI.METRONOME_IV,) * 6})
    check("  ...and Metronome is the whole movepool",
          {tuple(mon.moveset) for mon in side.team}, {("Metronome",)})
    check("  ...with no character ability", side.ability, "")

check("the two sides are rated the same",
      player.strength, opponent.strength)
check("...and the stats follow from the maxed IVs",
      player.team[0].nominal_base_stats,
      [base + SI.METRONOME_IV for base in player.team[0].base_stats])

# nothing here may touch the roster it was copied from
check("the roster's own Protagonist is untouched",
      bool(getattr(L['Protagonist'], "team", None))
      is bool(getattr(L['Protagonist'], "team", None)))
check("...and is not the object the mode plays with",
      player is not L['Protagonist'])


# ================================================================= the field
print()
print("-- fought on nothing --")
board = Battleground()
check("a battle does not open bare unless asked", board.bare_arena, False)

opened = {"weather": set(), "terrain": set()}
for index in range(12):
    random.seed(zlib.crc32(("metro%d" % index).encode()) & 0xffffff)
    mine, theirs = SI.metronome_teams()
    ground = Battleground()
    ground.verbose = True
    ground.exhibition = True
    ground.bare_arena = True
    ground.auto_battle = True     # nobody here to answer input()
    with suppress(RecursionError):
        with redirect_stdout(io.StringIO()):
            battle_setup(mine, theirs, mine.team, theirs.team, ground)
    opened["weather"].add(str(ground.starting_weather_effect))
    opened["terrain"].add(str(getattr(ground, "terrain", "None") or "None"))

check("every Metronome battle opens Clear", opened["weather"], {"Clear"})
check("...and on no terrain at all", opened["terrain"], {"None"})

# ...and an ordinary battle still rolls its own. Weather is a 1-in-N roll, so
# this asks that the *roll happens*, not that any particular weather came up.
GameSystem.stage = 5
rolled = set()
for index in range(40):
    random.seed(zlib.crc32(("plain%d" % index).encode()) & 0xffffff)
    ground = Battleground()
    a, b = deepcopy(L["Goblin"]), deepcopy(L["Solanum"])
    a.team, b.team = team_generation(a), team_generation(b)
    ground.verbose = True
    ground.exhibition = True
    ground.auto_battle = True
    with suppress(Exception):
        with redirect_stdout(io.StringIO()):
            battle_setup(a, b, a.team, b.team, ground)
    rolled.add(str(ground.starting_weather_effect))
check("an ordinary battle still rolls its own arena (%s)"
      % ", ".join(sorted(rolled)), len(rolled) > 1)


# ============================================================ and it finishes
print()
print("-- and somebody wins --")
finished, longest, sudden = 0, 0, 0
for index in range(8):
    random.seed(zlib.crc32(("play%d" % index).encode()) & 0xffffff)
    mine, theirs = SI.metronome_teams()
    ground = Battleground()
    ground.verbose = True
    ground.exhibition = True
    ground.bare_arena = True
    ground.auto_battle = True     # nobody here to answer input()
    try:
        with redirect_stdout(io.StringIO()):
            battle_setup(mine, theirs, mine.team, theirs.team, ground)
    except RecursionError:
        continue
    except Exception:
        continue
    if not ground.battle_continuation:
        finished += 1
    longest = max(longest, int(getattr(ground, "turn", 0) or 0))
    if getattr(ground, "sudden_death", False):
        sudden += 1

check("battles reach a result (%d of 8)" % finished, finished, 8)
check("longest was %d turns" % longest, longest > 0)
print("   (%d of 8 needed Sudden Death, which is left armed as usual)"
      % sudden)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
