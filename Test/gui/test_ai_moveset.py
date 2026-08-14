"""The AI must never pick a move slot its Pokemon does not have.

smart_ai_select_move scored a fixed five slots regardless of how many moves
the Pokemon actually had, then used the winning *slot number* to index the
moveset -- so a Pokemon with fewer than four moves could send it out of
range. Found by Test/opponent_ladder.py at battle 1,900 of 7,700.
"""
import os
import random
import sys
from contextlib import redirect_stdout, suppress
from copy import deepcopy

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# battle_cycle first, deliberately: Scripts.Battle.ai and
# Scripts.Battle.battle_move_execution star-import each other, so importing ai
# first leaves battle_checklist without user_turn_in_battle_stats. The game
# always comes through battle_cycle, and so does the ladder.
from Scripts.Battle.battle_cycle import battle_setup             # noqa: E402
import Scripts.Battle.ai as AI                                   # noqa: E402
from Scripts.Data.battlefield import Battleground                # noqa: E402
from Scripts.Data.competitors import list_of_competitors         # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                 # noqa: E402
from Scripts.Game.game_procedure import team_generation          # noqa: E402
from Scripts.Game.game_system import GameSystem                  # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    sys.stderr.write("%-58s %s\n" % (label, "PASS" if ok else
                                     "FAIL got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(label)


# ------------------------------------------------ the score dict is sized
short = [name for name, mon in list_of_pokemon.items()
         if len([m for m in mon.moveset if m != "Switching"]) < 4]
check("Data/pokemon.csv really has short movesets (%d of them)" % len(short),
      bool(short))

# Every move's dict key and its own name have to agree: the AI compares a
# moveset entry (a key) against move.name in places, and the log prints
# move.name -- "Razor Shell" was keyed to a Move called "RazorShell", so both
# silently disagreed.
from Scripts.Data.moves import list_of_moves                     # noqa: E402
mismatched = {key: move.name for key, move in list_of_moves.items()
              if key != move.name}
check("every move's key matches its own name", mismatched, {})

seen = {}
original = AI.smart_ai_select_move


def spy(battleground, protagonist, ai, *a, **kw):
    """Record the moveset length against the chosen move for every call.

    Argument order matters: smart_ai_select_move(battleground, protagonist,
    ai) -- the side being decided for is the *third* one.
    """
    moveset = list(ai.team[0].moveset)
    move = original(battleground, protagonist, ai, *a, **kw)
    seen.setdefault(len(moveset), 0)
    seen[len(moveset)] += 1
    if move is not None and move.name not in moveset:
        fails.append("chose %r, not in %r" % (move.name, moveset))
    return move


# ------------------------------------------- and it survives real battles
GameSystem.stage = 5
random.seed(11)
AI.smart_ai_select_move = spy
import Scripts.Battle.battle_cycle as CYCLE                       # noqa: E402
CYCLE.smart_ai_select_move = spy
import Scripts.Battle.switching as SWITCH                         # noqa: E402
if hasattr(SWITCH, "smart_ai_select_move"):
    SWITCH.smart_ai_select_move = spy

field = [c for c in list_of_competitors.values() if not c.main]
crashes = []
BATTLES = 120
with open(os.devnull, "w", encoding="utf-8", errors="replace") as sink:
    with redirect_stdout(sink):
        for index in range(BATTLES):
            one = deepcopy(field[index % len(field)])
            two = deepcopy(field[(index * 7 + 3) % len(field)])
            one.team = team_generation(one)
            two.team = team_generation(two)
            # force a short moveset onto one side often enough to matter
            if index % 2 == 0 and short:
                victim = deepcopy(list_of_pokemon[short[index % len(short)]])
                victim.iv = [20] * 6
                victim.total_iv = 120
                victim.nominal_base_stats = [a + b for a, b in
                                             zip(victim.base_stats, victim.iv)]
                victim.ability = [victim.ability[0]]
                victim.moveset = [m for m in victim.moveset
                                  if m != "Switching"][:4]
                one.team[0] = victim
            ground = Battleground()
            ground.verbose = True
            try:
                with suppress(RecursionError):
                    battle_setup(one, two, one.team, two.team, ground)
            except Exception as error:
                crashes.append("%s: %s" % (type(error).__name__, error))

AI.smart_ai_select_move = original
CYCLE.smart_ai_select_move = original

check("%d battles ran with no engine crash" % BATTLES, crashes[:3], [])
check("the AI was asked to choose many times", sum(seen.values()) > 200,
      True)
check("including for short movesets (lengths seen: %s)"
      % sorted(seen), any(length < 5 for length in seen), True)
check("every chosen move belonged to the Pokemon",
      [f for f in fails if f.startswith("chose")], [])

sys.stderr.write("\n" + ("ALL PASS" if not fails else "%d FAILURES: %s\n"
                                                      % (len(fails), fails))
                 + "\n")
sys.exit(1 if fails else 0)
