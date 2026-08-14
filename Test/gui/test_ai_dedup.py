"""The three helpers the AI now shares with the engine must return exactly
what its own removed copies did, for every Pokemon and move in the game."""
import math
import os
import sys

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from Scripts.Battle.ai import *                                # noqa: E402,F403
from Scripts.Battle.damage_calculation import (                # noqa: E402
    check_attack_power, check_defense_strength,
    check_if_weather_affect_moves)
from Scripts.Data.moves import list_of_moves                   # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon               # noqa: E402
from Scripts.Data.battlefield import Battleground              # noqa: E402

fails = []


# --- verbatim copies of what was removed from ai.py ------------------------
def old_attack_power(user, target, move):
    attack = 0
    if move.attack_type == "Physical":
        attack = (target.battle_stats[1] * 0.5 if target.status == "Burn" else target.battle_stats[1]) if move.targetAtk else \
            (user.battle_stats[2] * 0.5 if user.status == "Burn" else user.battle_stats[2]) if move.DefAsAtk else \
                user.battle_stats[1] * 0.5 if user.status == "Burn" else user.battle_stats[1]
    elif move.attack_type == "Special":
        attack = target.battle_stats[3] if move.targetAtk else user.battle_stats[4] if move.DefAsAtk else user.battle_stats[3]
    return attack


def old_defense_strength(user, target, move):
    if move.ignoreDef:
        Def, SpDef = math.floor(0.01 * 2 * target.nominal_base_stats[2] * modifierChart[2][0] * 100 + 5), \
                     math.floor(0.01 * 2 * target.nominal_base_stats[4] * modifierChart[4][0] * 100 + 5)
    else:
        Def, SpDef = target.battle_stats[2], target.battle_stats[4]
    if move.attack_type == "Physical":
        return SpDef if move.inverseDef else Def
    elif move.attack_type == "Special":
        return Def if move.inverseDef else SpDef


def old_weather(battleground, move):
    if (battleground.weather_effect == 'Sunny' and move.type == "Water") or (battleground.weather_effect == 'Rain' and move.type == "Fire"):
        return 0.5
    elif (battleground.weather_effect == 'Sunny' and move.type == "Fire") or (battleground.weather_effect == 'Rain' and move.type == "Water"):
        return 2
    return 1


mons = list(list_of_pokemon.values())
moves = list(list_of_moves.values())
# templates carry base_stats; nominal_base_stats and iv stay 0 until a
# Pokemon is actually rolled, so stand in for a rolled one here
for index, mon in enumerate(mons):
    base = list(mon.base_stats)
    mon.nominal_base_stats = [v + (index % 7) for v in base]
    mon.battle_stats = [v + (index % 5) for v in mon.nominal_base_stats]

pairs = 0
for i, user in enumerate(mons):
    target = mons[(i + 7) % len(mons)]
    for status in ("Normal", "Burn"):
        user.status = status
        target.status = status
        for move in moves[:: max(1, len(moves) // 90)]:
            pairs += 1
            a, b = old_attack_power(user, target, move), \
                check_attack_power(user, target, move)
            if a != b:
                fails.append("attack %s/%s: %r != %r" % (mon.name, move.name, a, b))
            a, b = old_defense_strength(user, target, move), \
                check_defense_strength(user, target, move)
            if a != b:
                fails.append("defense %s/%s: %r != %r" % (mon.name, move.name, a, b))

ground = Battleground()
weathers = 0
for weather in ("Clear", "Sunny", "Rain", "Sandstorm", "Hail"):
    ground.weather_effect = weather
    for move in moves:
        weathers += 1
        a, b = old_weather(ground, move), check_if_weather_affect_moves(ground, move)
        if a != b:
            fails.append("weather %s/%s: %r != %r" % (weather, move.name, a, b))

print("attack/defense compared over %d (pokemon, status, move) cases" % pairs)
print("weather compared over %d (weather, move) cases" % weathers)
print()
if fails:
    print("%d MISMATCHES:" % len(fails))
    for f in fails[:10]:
        print("  " + f)
else:
    print("ALL PASS -- the shared helpers are exactly equivalent")
sys.exit(1 if fails else 0)
