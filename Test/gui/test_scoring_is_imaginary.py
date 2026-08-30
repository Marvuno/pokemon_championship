"""Scoring a move must not change the battle.

The AI scores its candidates by running the *real* ability code on the same
phases a real turn uses (`Scripts/Battle/ai.py`), with
`battleground.reality` set to False for the duration. Everything that only
*announces* already checks that flag. Anything that **writes state** has to
check it as well, and that is easy to forget because nothing complains: the
write lands on the real battleground and shows up later as something the
player did not do.

Mivy Wenceslas's Wizardry is the case this was written for. It queued its
extra move on `battleground.encore_move` while merely thinking about a move,
and `move_order_and_execution` hands that extra move to whoever finishes a
move next -- so a player using a priority move moved first, collected the
free move Mivy had queued, and Mivy's own turn then found the slot already
empty. It read exactly as "I gained the ability and the opponent lost it".

This plays the real scorer for every competitor on the roster and fails on
any battleground field that came back different.
"""
import io
import os
import random
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle as CYCLE                       # noqa: E402
import Scripts.Battle.ai as AI                                    # noqa: E402
from copy import deepcopy                                         # noqa: E402
from Scripts.Data.battlefield import Battleground                 # noqa: E402
from Scripts.Data.competitors import list_of_competitors          # noqa: E402
from Scripts.Game.game_procedure import team_generation           # noqa: E402
from Scripts.Game.game_system import GameSystem                   # noqa: E402

GameSystem.stage = 5
failures = []


def check(label, got, want=True):
    if got == want:
        print("%-58s PASS" % label)
    else:
        print("%-58s FAIL got=%r" % (label, got))
        failures.append(label)


#: what the battleground carries that a *thought* must never touch. Read off
#: the object rather than listed by hand, so a field added later is covered
#: without anybody remembering to add it here.
def snapshot(ground):
    out = {}
    for name, value in vars(ground).items():
        if name.startswith("_"):
            continue
        try:
            out[name] = deepcopy(value)
        except Exception:
            out[name] = repr(value)
    return out


def differences(before, after):
    changed = []
    for name, was in before.items():
        now = after.get(name)
        # the move object itself is rebuilt per candidate; compare by name
        if name == "encore_move":
            was = getattr(was, "name", was)
            now = getattr(now, "name", now)
        if repr(was) != repr(now):
            changed.append("%s: %r -> %r" % (name, was, now))
    return changed


print("-- scoring a move changes nothing on the battleground --")
leaked = {}
names = [n for n in list_of_competitors if n != "Protagonist"]
for index, name in enumerate(names):
    random.seed(1500 + index)
    one = deepcopy(list_of_competitors[name])
    two = deepcopy(list_of_competitors[names[(index + 5) % len(names)]])
    with redirect_stdout(io.StringIO()):
        one.team, two.team = team_generation(one), team_generation(two)
    ground = Battleground()
    mine, theirs = one.team[0], two.team[0]
    for mon in (mine, theirs):
        # battle_setup is what normally fills these in; this harness scores a
        # move without playing a battle, so it does that much by hand
        mon.moveset = ["Switching"] + [m for m in mon.moveset if m][:4]
        mon.battle_stats = list(mon.nominal_base_stats)
        mon.hp = mon.nominal_base_stats[0]

    ground.reality = False           # exactly what battle_cycle does
    before = snapshot(ground)
    scores = {k: [0, 0, 0, 0] for k in range(len(mine.moveset))}
    with redirect_stdout(io.StringIO()):
        try:
            AI.intelligent_move_selection(one, two, mine, theirs, ground,
                                          scores, mine.battle_stats)
        except Exception as problem:
            leaked.setdefault("raised %s (%s)"
                              % (type(problem).__name__, problem),
                              []).append(name)
            continue
    after = snapshot(ground)
    ground.reality = True
    for line in differences(before, after):
        leaked.setdefault(line.split(":")[0], []).append(
            "%s (%s)" % (name, getattr(one, "ability", "?")))

check("no competitor's ability writes to the battleground while thinking",
      len(leaked), 0)
for field, who in sorted(leaked.items()):
    print("    %-24s written by: %s" % (field, ", ".join(sorted(set(who))[:6])))

print()
# -- and the ability still works, for the right side ----------------------
# Guarding a leak is easy to overdo: an ability that never fires also never
# leaks. This plays Mivy and reads the follow-ups out of the log.
print()
print("-- Wizardry follows Mivy's own moves, and nobody else's --")
import collections                                                # noqa: E402
_follows = collections.Counter()
for _t in range(12):
    random.seed(6000 + _t)
    _mivy = deepcopy(list_of_competitors["Mivy Wenceslas"])
    _foe = deepcopy(list_of_competitors["Expert Cynthia"])
    _spoken = io.StringIO()
    with redirect_stdout(_spoken):
        _mivy.team, _foe.team = team_generation(_mivy), team_generation(_foe)
        _ground = Battleground()
        _ground.verbose = True
        CYCLE.battle_setup(_mivy, _foe, _mivy.team, _foe.team, _ground)
    for _line in _spoken.getvalue().splitlines():
        if "is not finished" in _line:
            _who = _line.split(" is not finished")[0].strip()
            _mine = any(p.name in _who for p in _mivy.team)
            _follows["mivy" if _mine else "opponent"] += 1
check("Wizardry fires at all", _follows["mivy"] > 0, True)
check("...and never for the other side", _follows["opponent"], 0)
print("    %d follow-ups, all on Mivy's Pokemon" % _follows["mivy"])

print("%s" % ("ALL PASS" if not failures
              else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
