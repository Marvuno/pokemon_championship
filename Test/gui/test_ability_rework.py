"""Do the reworked character abilities actually do anything?

Twelve character abilities were rebalanced at once, and three of them were
rewritten rather than retuned -- Primordial, Light Speed and Infiltration.

Every one of these has the shape that has been silently inert here before --
a phase that fires too late, a granted ability that cancels the other half,
a guard that can never be true. So each is checked for its *mechanism*, in a
real battle where possible, not for the designer's number.
"""
import io
import math
import os
import random
import sys
from contextlib import redirect_stdout
from copy import deepcopy

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

OUT = sys.stdout
FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(label)
    OUT.write("%-58s %s%s" % (label, "PASS" if ok else
                              "FAIL got=%r want=%r" % (got, want), chr(10)))
    OUT.flush()


import Scripts.Battle.battle_cycle as CYCLE                         # noqa: E402
from Scripts.Battle import terrain                                  # noqa: E402
from Scripts.Battle.context import Side, Turn                        # noqa: E402
from Scripts.Data.battlefield import Battleground                    # noqa: E402
from Scripts.Data.character_abilities import UseCharacterAbility      # noqa: E402
from Scripts.Battle.constants import ORDER_PHASE                      # noqa: E402
from Scripts.Data.competitors import list_of_competitors as C         # noqa: E402
from Scripts.Data.moves import list_of_moves                          # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                      # noqa: E402
from Scripts.Game.game_procedure import team_generation               # noqa: E402
from Scripts.Game.game_system import GameSystem                       # noqa: E402

GameSystem.stage = 5


def fire(who, phase, move_name, mine, theirs, ground=None):
    """Run one competitor's character ability at one phase."""
    ground = ground or Battleground()
    ground.reality = True
    one, two = deepcopy(C[who]), deepcopy(C["Jason"])
    turn = Turn(ground, Side(one, [mine], mine), Side(two, [theirs], theirs))
    move = deepcopy(list_of_moves[move_name]) if move_name else ""
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, move, abilityphase=phase)
    return ground, move, mine


_STOCK = {}


def built(name=None, owner="Jason"):
    """A Pokemon with its battle state initialised.

    `list_of_pokemon` holds uninitialised templates -- no `hp`, no
    `battle_stats` -- so a Pokemon has to come out of `team_generation` and
    then through the engine's own per-battle stat build to be usable here.
    """
    if owner not in _STOCK:
        one = deepcopy(C[owner])
        one.team = team_generation(one)
        # the same build `battle_setup` does inline -- there is no separate
        # function for it, so it is repeated rather than called
        for p in one.team:
            p.hp = math.floor(0.01 * 2 * p.nominal_base_stats[0] * 100) + 110
            p.battle_stats = [p.hp] + [
                math.floor(0.01 * 2 * p.nominal_base_stats[x] * 100 + 5)
                for x in range(1, 6)]
            p.default_type = list(p.type)
            p.default_ability = list(p.ability)
        _STOCK[owner] = one.team
    pool = _STOCK[owner]
    mon = deepcopy(pool[0] if name is None else
                   next((p for p in pool if p.name == name), pool[0]))
    # a flat, known Speed so a multiplier is unambiguous
    mon.battle_stats = [mon.battle_stats[0]] + [100, 100, 100, 100, 100]
    mon.volatile_status = dict(getattr(mon, "volatile_status", {}) or {})
    mon.volatile_status["Grounded"] = 1   # as switching-in sets it
    return mon


OUT.write("-- Primordial: x1.5 Speed, and only while it rains --" + chr(10))
mon = built(owner="Emperor Marvuno")
wet = Battleground(); wet.weather_effect = "Rain"
fire("Emperor Marvuno", ORDER_PHASE, "Quick Attack", mon, built(owner="Jason"), wet)
check("speed x1.5 in rain", mon.battle_stats[5], 150)

dry = Battleground(); dry.weather_effect = "Clear"
mon2 = built(owner="Emperor Marvuno")
fire("Emperor Marvuno", ORDER_PHASE, "Quick Attack", mon2, built(owner="Jason"), dry)
check("...and untouched when it is not raining", mon2.battle_stats[5], 100)

mon3 = built(owner="Emperor Marvuno")
was = list(mon3.ability or [])
fire("Emperor Marvuno", 1, "Quick Attack", mon3, built(owner="Jason"), wet)
# several of his Water types have Swift Swim naturally, so the test is that
# Primordial adds nothing -- not that the list comes back empty
check("Primordial grants no abilities now",
      sorted(mon3.ability or []), sorted(was))

OUT.write(chr(10) + "-- Light Speed: terrain, and Ground does not reach --" + chr(10))
g = Battleground(); g.turn = 1
fire("Albert Einstein", 1, "", built(owner="Albert Einstein"), built(owner="Jason"), g)
check("battle opens on Electric Terrain", terrain.current(g), "Electric")

target = built(owner="Albert Einstein")
_, mv, _ = fire("Albert Einstein", 3, "Earthquake", target, built(owner="Jason"), g)
check("a Ground move is refused", mv.abilitymodifier, 0)
_, mv2, _ = fire("Albert Einstein", 3, "Quick Attack", target, built(owner="Jason"), g)
check("...and a Normal move is not", mv2.abilitymodifier != 0, True)

# the trap: Levitate would have made them immune AND taken the terrain away
grounded_reason = ("Flying" if "Flying" in (target.type or [])
                   else "Levitate" if "Levitate" in (target.ability or [])
                   else "volatile" if (target.volatile_status or {}).get("Grounded", 1) <= 0
                   else "grounded")
check("they are still standing on their own terrain (%s, %s)"
      % (target.name, grounded_reason),
      terrain.is_grounded(target) or grounded_reason == "Flying", True)
check("...because they were never given Levitate",
      "Levitate" in (target.ability or []), False)
check("...and no Electric type was added",
      "Electric" in target.type, False)

OUT.write(chr(10) + "-- Infiltration: hazards do not stick --" + chr(10))
one, two = deepcopy(C["Velvet"]), deepcopy(C["Jason"])
ground = Battleground(); ground.reality = True
mine = built(owner="Velvet")
one.entry_hazard = {"Stealth Rock": 1, "Spikes": 3, "Toxic Spikes": 2,
                    "Sticky Web": 1}
two.entry_hazard = dict.fromkeys(one.entry_hazard, 0)
side = Side(one, [mine], mine)
foe = Side(two, [built(owner="Jason")], built(owner="Jason"))
with redirect_stdout(io.StringIO()):
    UseCharacterAbility(Turn(ground, side, foe), "", abilityphase=1)
check("every hazard on her side is gone", sum(one.entry_hazard.values()), 0)
check("...and she still gets Mold Breaker",
      "Mold Breaker" in (mine.ability or []), True)

OUT.write(chr(10) + "-- Monkey King has no character ability --" + chr(10))
check("his ability field is empty", C["Monkey King"].ability, "")
# the registry is local to UseCharacterAbility, so ask the derived phase map
import Scripts.Data.character_abilities as CA                        # noqa: E402
with redirect_stdout(io.StringIO()):
    _m = built(owner="Jason")
    UseCharacterAbility(Turn(Battleground(), Side(deepcopy(C["Jason"]), [_m], _m),
                             Side(deepcopy(C["Jason"]), [_m], _m)), "", abilityphase=1)
check("'Monkey' is out of the registry", "Monkey" in (CA._CHARACTER_PHASES or {}), False)
check("...and nobody in the roster still holds it",
      [n for n, c in C.items() if c.ability == "Monkey"], [])
# and a blank ability must not raise when the engine dispatches on it
try:
    with redirect_stdout(io.StringIO()):
        one2 = deepcopy(C["Monkey King"])
        m = built(owner="Monkey King")
        UseCharacterAbility(Turn(Battleground(), Side(one2, [m], m),
                                 Side(deepcopy(C["Jason"]), [m], m)),
                            "", abilityphase=1)
    check("dispatching on a blank ability is safe", True, True)
except Exception as error:
    check("dispatching on a blank ability is safe", repr(error), True)

OUT.write(chr(10) + "-- Blood Magic drains the damage actually dealt --" + chr(10))
from Scripts.Data.character_abilities import BLOOD_MAGIC_DRAIN         # noqa: E402

muzan = deepcopy(C["Demon Muzan"])
drainer, victim = built(owner="Demon Muzan"), built(owner="Jason")
for foe_hp, dmg in ((10, 300), (50, 300), (300, 300), (1000, 300)):
    hit = deepcopy(list_of_moves["Body Slam"])
    hit.damage = dmg
    # phase 6 fires after the hit has been taken off, so this is the state
    # the ability really sees -- negative HP and all
    victim.battle_stats[0] = foe_hp - dmg
    drainer.battle_stats[0] = drainer.hp // 2
    opening = drainer.battle_stats[0]
    ground = Battleground()
    ground.reality = True
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(Turn(ground, Side(muzan, [drainer], drainer),
                                 Side(deepcopy(C["Jason"]), [victim], victim)),
                            hit, abilityphase=6)
    dealt = min(foe_hp, dmg)
    check("foe on %4d, %d damage -> drains %d%% of %d"
          % (foe_hp, dmg, BLOOD_MAGIC_DRAIN * 100, dealt),
          drainer.battle_stats[0] - opening,
          math.floor(dealt * BLOOD_MAGIC_DRAIN))

OUT.write(chr(10) + "-- Synchronize: drops spread, gains are taken --" + chr(10))
holder = deepcopy(C["Titan"])
holder.ability = "Synchronize"
for label, mine_delta, foe_delta, want_mine, want_foe in (
        ("a drop on the holder reaches the foe",
         [0, -2, 0, 0, 0, 0, 0, 0, 0], [0] * 9, -2, -2),
        ("a gain on the foe reaches the holder",
         [0] * 9, [0, 3, 0, 0, 0, 0, 0, 0, 0], 3, 3),
        ("a gain on the holder is NOT shared",
         [0, 2, 0, 0, 0, 0, 0, 0, 0], [0] * 9, 2, 0),
        ("a drop on the foe is NOT shared",
         [0] * 9, [0, -2, 0, 0, 0, 0, 0, 0, 0], 0, -2)):
    mine, theirs = built(owner="Jason"), built(owner="Jason")
    mine.modifier, theirs.modifier = [0] * 9, [0] * 9
    mine.status = theirs.status = "Normal"
    ground = Battleground()
    ground.reality = True
    turn = Turn(ground, Side(holder, [mine], mine),
                Side(deepcopy(C["Jason"]), [theirs], theirs))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, "", abilityphase=ORDER_PHASE)
        mine.modifier = [a + b for a, b in zip(mine.modifier, mine_delta)]
        theirs.modifier = [a + b for a, b in zip(theirs.modifier, foe_delta)]
        UseCharacterAbility(turn, "", abilityphase=8)
    check(label, (mine.modifier[1], theirs.modifier[1]), (want_mine, want_foe))

OUT.write(chr(10) + "-- a real battle still runs for each of them --" + chr(10))
for who in ("Emperor Marvuno", "Albert Einstein", "Velvet", "Monkey King",
            "Ash Ketchum", "Auraia", "Demon Muzan", "King Bradley"):
    wins = 0
    crash = ""
    for repeat in range(4):
        random.seed(repeat)
        one, two = deepcopy(C[who]), deepcopy(C["Reaper Conan"])
        one.team, two.team = team_generation(one), team_generation(two)
        ground = Battleground(); ground.verbose = True
        try:
            with redirect_stdout(io.StringIO()):
                CYCLE.battle_setup(one, two, one.team, two.team, ground)
            wins += one.score > two.score
        except Exception as error:
            crash = repr(error)[:90]
            break
    check("%-18s 4 battles, no crash" % who, crash, "")

OUT.write(chr(10) + ("ALL PASS" if not FAILED
                     else "%d FAILURES: %s" % (len(FAILED), FAILED)) + chr(10))
sys.exit(1 if FAILED else 0)
