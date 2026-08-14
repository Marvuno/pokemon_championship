"""Protean must change type when the Pokemon moves, not before the turn.

compare_speed adjusted both sides before either move executed, and ability
phase 2 -- where Protean and Libero set the user's type to their move's type
-- fired there. So the change was visible before the Pokemon had moved, and
if the other side moved first (priority, or just faster) its attack was
worked out against the *new* type rather than the one still being worn.
"""
import os
import sys
from contextlib import redirect_stdout, suppress
from copy import deepcopy

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# battle_cycle first: Scripts.Battle.ai and battle_move_execution star-import
# each other, and the game always comes through battle_cycle
import Scripts.Battle.battle_cycle as CYCLE                      # noqa: E402
import Scripts.Battle.battle_checklist as CHECK                  # noqa: E402
import Scripts.Battle.battle_initialization as INIT              # noqa: E402
from Scripts.Data.battlefield import Battleground                # noqa: E402
from Scripts.Data.competitors import list_of_competitors         # noqa: E402
from Scripts.Data.moves import list_of_moves                     # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                 # noqa: E402
from Scripts.Game.game_procedure import team_generation          # noqa: E402
from Scripts.Game.game_system import GameSystem                  # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


# ------------------------------------------------- where the ability fires
import inspect                                                    # noqa: E402
pre = inspect.getsource(INIT.pre_move_adjustment)
check("the pre-turn adjustment no longer fires ability phase 2",
      "abilityphase=2" not in pre)
check("on_move_used does", "abilityphase=2"
      in inspect.getsource(INIT.on_move_used))
check("...and the move execution calls it",
      "on_move_used" in inspect.getsource(CHECK.move_order_and_execution))

# ------------------------------------------------ the order things happen in
# The precise regression: phase 2 used to fire for *both* sides back to back,
# before either move executed. Now each one fires as that Pokemon's own move
# goes off, so the events must alternate: fire, execute, fire, execute.
PROTEAN = [name for name, mon in list_of_pokemon.items()
           if "Protean" in (mon.ability or [])]
check("the roster has a Protean Pokemon (%s)" % PROTEAN[:2], bool(PROTEAN))

events = []
original_used = INIT.on_move_used
original_exec = CHECK.move_order_and_execution


def spy_used(user_side, opponent_side, user, opponent, battleground, move):
    if move.name != "Switching":
        events.append(("type-change", user.name, move.name))
    return original_used(user_side, opponent_side, user, opponent,
                         battleground, move)


def spy_exec(user_side, target_side, user_team, target_team, actor, target,
             battleground, move, target_move):
    if move.name != "Switching":
        events.append(("move", actor.name, move.name))
    # what the *defender* is wearing as the attack is worked out
    defending.append((actor.name, move.name, target.name, list(target.type)))
    return original_exec(user_side, target_side, user_team, target_team,
                         actor, target, battleground, move, target_move)


defending = []
GameSystem.stage = 5
INIT.on_move_used = spy_used
CHECK.on_move_used = spy_used
CHECK.move_order_and_execution = spy_exec
CYCLE.move_order_and_execution = spy_exec

field = [c for c in list_of_competitors.values() if not c.main]
crashes = []
with open(os.devnull, "w", encoding="utf-8", errors="replace") as sink:
    with redirect_stdout(sink):
        for index in range(10):
            one = deepcopy(field[index % len(field)])
            two = deepcopy(field[(index * 5 + 2) % len(field)])
            one.team = team_generation(one)
            two.team = team_generation(two)
            mon = deepcopy(list_of_pokemon[PROTEAN[0]])
            mon.iv = [25] * 6
            mon.total_iv = 150
            mon.nominal_base_stats = [a + b for a, b in
                                      zip(mon.base_stats, mon.iv)]
            mon.ability = ["Protean"]
            mon.moveset = [m for m in mon.moveset if m != "Switching"][:4]
            one.team[0] = mon
            ground = Battleground()
            ground.verbose = True
            try:
                with suppress(RecursionError):
                    CYCLE.battle_setup(one, two, one.team, two.team, ground)
            except Exception as error:
                crashes.append("%s: %s" % (type(error).__name__, error))

INIT.on_move_used = original_used
CHECK.on_move_used = original_used
CHECK.move_order_and_execution = original_exec
CYCLE.move_order_and_execution = original_exec

check("battles still run", crashes[:2], [])
check("plenty of moves were executed",
      len([e for e in events if e[0] == "move"]) > 40, True)

# The spy records "move" as execution is entered and "type-change" from
# inside it, so a correctly-ordered turn reads move-then-change for the *same*
# Pokemon and the same move. What the bug looked like was a change belonging
# to a Pokemon that had not moved yet.
pairs = list(zip(events, events[1:]))
misordered = [(a, b) for a, b in pairs
              if a[0] == "move"
              and not (b[0] == "type-change" and b[1] == a[1]
                       and b[2] == a[2])]
check("every move changes that same Pokemon's type, inside its own turn",
      misordered[:2], [])
orphaned = [(a, b) for a, b in pairs
            if b[0] == "type-change" and a[0] == "move" and b[1] != a[1]]
check("no type change belongs to a Pokemon that has not moved",
      orphaned[:2], [])

# and no two type-changes ever run back to back -- which is exactly what the
# old code did for the two sides before the turn began
back_to_back = [(a, b) for a, b in pairs
                if a[0] == "type-change" and b[0] == "type-change"]
check("no two type changes happen back to back", back_to_back[:2], [])

changes = [e for e in events if e[0] == "type-change"]
moves = [e for e in events if e[0] == "move"]
check("one type change per move, not two",
      len(changes), len(moves))

print()
print("%d moves, %d type-change points, interleaved correctly"
      % (len(moves), len(changes)))
print("the first six events: %s" % (events[:6],))

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
