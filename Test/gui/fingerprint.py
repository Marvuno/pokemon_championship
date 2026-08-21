"""A deterministic fingerprint of the engine's behaviour.

Plays a fixed set of battles from a fixed seed and writes a hash of
everything they printed, plus every scoreline. Two runs of the same engine
produce the same file; a run that changes what a battle *does* produces a
different one.

This is the instrument that makes it safe to touch the engine. It only works
because a seed replays a battle now -- see test_engine_integrity.py, and
`multi_strike_move` for why it did not before.

    python Test/gui/fingerprint.py <root> <out>              write it
    python Test/gui/fingerprint.py <root> <out> --compare    compare to it

`--compare` exits non-zero if the engine now behaves differently, and prints
the first battle that diverged.
"""
import hashlib
import io
import json
import os
import random
import sys
from contextlib import redirect_stdout, suppress
from copy import deepcopy

ROOT, OUT = sys.argv[1], sys.argv[2]
COMPARE = "--compare" in sys.argv
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

# battle_cycle first: Scripts.Battle.ai and battle_move_execution star-import
# each other, and the game always comes through battle_cycle
import Scripts.Battle.battle_cycle as CYCLE                     # noqa: E402
from Scripts.Data.battlefield import Battleground               # noqa: E402
from Scripts.Data.competitors import list_of_competitors        # noqa: E402
from Scripts.Game.game_procedure import team_generation         # noqa: E402
from Scripts.Game.game_system import GameSystem                 # noqa: E402

#: enough battles to exercise switching, weather, hazards and status, few
#: enough to run in seconds
BATTLES = 40
SEED = 20260819
PATH = os.path.join(OUT, "fingerprint.json")


def play():
    GameSystem.stage = 5
    names = list(list_of_competitors.keys())[1:]
    random.seed(SEED)
    rows = []
    for index in range(BATTLES):
        one = deepcopy(list_of_competitors[names[index % len(names)]])
        two = deepcopy(list_of_competitors[names[(index * 7 + 2) % len(names)]])
        # the designed ace teams are kept -- see ai_rating_simulation.play
        spoken = io.StringIO()
        with redirect_stdout(spoken):
            one.team, two.team = team_generation(one), team_generation(two)
            ground = Battleground()
            ground.verbose = True
            with suppress(RecursionError):
                CYCLE.battle_setup(one, two, one.team, two.team, ground)
        rows.append({
            "battle": index,
            "sides": [one.name, two.name],
            "score": [int(one.score), int(two.score)],
            "turns": int(ground.turn),
            # the whole transcript, hashed: every damage roll, every status
            # message, every switch, in order
            "log": hashlib.sha256(
                spoken.getvalue().encode("utf-8", "replace")).hexdigest()[:16],
        })
    return rows


rows = play()

if not COMPARE:
    with open(PATH, "w", encoding="utf-8") as out:
        json.dump(rows, out, indent=1)
    print("wrote %s (%d battles, seed %d)" % (PATH, len(rows), SEED))
    print("turns: min %d, median %d, max %d"
          % (min(r["turns"] for r in rows),
             sorted(r["turns"] for r in rows)[len(rows) // 2],
             max(r["turns"] for r in rows)))
    raise SystemExit(0)

if not os.path.exists(PATH):
    print("no baseline at %s -- run without --compare first" % PATH)
    raise SystemExit(1)

with open(PATH, encoding="utf-8") as source:
    baseline = json.load(source)

if baseline == rows:
    print("IDENTICAL: %d battles, same scorelines and same transcripts"
          % len(rows))
    raise SystemExit(0)

print("DIVERGED from the baseline")
for old, new in zip(baseline, rows):
    if old != new:
        print("  first difference, battle %d (%s vs %s):"
              % (old["battle"], *old["sides"]))
        for key in ("score", "turns", "log"):
            if old[key] != new[key]:
                print("      %-6s %r -> %r" % (key, old[key], new[key]))
        break
same = sum(1 for old, new in zip(baseline, rows) if old == new)
print("  %d of %d battles unchanged" % (same, len(rows)))
raise SystemExit(1)
