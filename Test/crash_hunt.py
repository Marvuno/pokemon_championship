"""Play a lot of battles and report anything that raises.

The simulation harnesses suppress RecursionError and run inside
`redirect_stdout`, so a crash there is invisible or silent. This one catches
*everything*, keeps the traceback and the matchup, and groups identical
faults so a hundred battles produce a short report.

    python Test/crash_hunt.py                 200 battles across the roster
    python Test/crash_hunt.py 500             more
    python Test/crash_hunt.py 200 "Champion Marvin"   one competitor, always
    python Test/crash_hunt.py 200 "" human            the path a player is on

`human` is the branch `move_selection` takes when somebody is at the
keyboard: the opponent goes through `smart_ai_select_move` while the player's
side is driven by auto battle. It is a different branch from the AI-vs-AI one
every simulation harness here uses, and since difficulty rather than rating
now decides the AI, it is the branch that 16 more competitors reach than
before.
"""
import collections
import io
import os
import random
import sys
import traceback
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

# battle_cycle first -- Scripts/ star-imports itself into a web and the game
# always enters through here.
import Scripts.Battle.battle_cycle as CYCLE                     # noqa: E402
from copy import deepcopy                                       # noqa: E402
from Scripts.Data.battlefield import Battleground               # noqa: E402
from Scripts.Data.competitors import list_of_competitors        # noqa: E402
from Scripts.Game.game_procedure import team_generation         # noqa: E402
from Scripts.Game.game_system import GameSystem                 # noqa: E402
from Scripts.Game import auto_run                               # noqa: E402

BATTLES = int(sys.argv[1]) if len(sys.argv) > 1 else 200
ALWAYS = (sys.argv[2] or None) if len(sys.argv) > 2 else None
HUMAN = len(sys.argv) > 3 and sys.argv[3] == "human"

GameSystem.stage = 5
# The human path asks real questions at the end of a battle -- "press any
# key", "do you want to swap" -- and a harness with no stdin dies on the
# first of them with EOFError, which is the harness failing rather than the
# game. Auto Run already knows the answers, so it drives the keyboard here.
if HUMAN:
    auto_run.start(1)
    # `end_battle` on the player's own battle calls `round_end`, which walks
    # all 32 bracket slots -- so a bare battle cannot be played on this path
    # without a tournament behind it. A real game always has one by here.
    from Scripts.Game.start_interface import draw_bracket
    with redirect_stdout(io.StringIO()):
        draw_bracket()
names = [n for n in list_of_competitors if n != "Protagonist"]
faults = collections.defaultdict(list)
played = 0
turns = []

for index in range(BATTLES):
    random.seed(9000 + index)
    # `round_end` advances the tournament, so replaying battles in one
    # process walks GameSystem.stage past the last round and team_generation
    # then has no ROUND_LIMIT for it. A real career stops at 6; this puts the
    # stage back for each battle instead.
    GameSystem.stage = 5
    one_name = ALWAYS or names[index % len(names)]
    two_name = names[(index * 7 + 3) % len(names)]
    if two_name == one_name:
        two_name = names[(index * 7 + 4) % len(names)]
    one = deepcopy(list_of_competitors[one_name])
    two = deepcopy(list_of_competitors[two_name])
    spoken = io.StringIO()
    try:
        with redirect_stdout(spoken):
            one.team, two.team = team_generation(one), team_generation(two)
            ground = Battleground()
            if HUMAN:
                # the player's own branch: nobody is verbose, and the player's
                # side is picked by auto battle instead of by input()
                ground.verbose = False
                ground.auto_battle = True
                one.main = True
            else:
                ground.verbose = True
            CYCLE.battle_setup(one, two, one.team, two.team, ground)
        played += 1
        turns.append((ground.turn, one_name, two_name, 9000 + index))
    except Exception:
        trace = traceback.format_exc()
        # the last frame is what actually failed; group on it so a hundred
        # copies of one fault read as one line
        lines = [line for line in trace.splitlines() if line.startswith("  File")]
        key = (lines[-1].strip() if lines else "?") + " | " + trace.splitlines()[-1]
        faults[key].append((one_name, two_name, index, trace))

if HUMAN:
    auto_run.stop()
print("%d battles attempted (%s path), %d finished, %d distinct faults"
      % (BATTLES, "human" if HUMAN else "AI-vs-AI", played, len(faults)))
if turns:
    turns.sort(reverse=True)
    print("longest battles (a stalling one dies by RecursionError, not by ending):")
    for count, one_name, two_name, seed in turns[:5]:
        print("   %4d turns   %s vs %s (seed %d)" % (count, one_name, two_name, seed))
if not faults:
    print("no crashes")
    sys.exit(0)
print()
for key, hits in sorted(faults.items(), key=lambda kv: -len(kv[1])):
    one_name, two_name, index, trace = hits[0]
    print("=" * 74)
    print("%d hit(s)   first: %s vs %s (seed %d)"
          % (len(hits), one_name, two_name, 9000 + index))
    print(trace[-1400:])
sys.exit(1)
