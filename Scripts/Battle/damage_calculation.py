from Scripts.Data.abilities import *
from Scripts.Battle.context import Side, Turn
import random
import math
from Scripts.Art import narrator
from Scripts.Battle import terrain


# damage calculation
def damage_calculation(turn, move):
    """What this move takes off the target.

    `turn` carries the two sides and the field -- see
    Scripts/Battle/context.py. check_attack_power, check_defense_strength and
    check_if_weather_affect_moves keep their narrow signatures on purpose:
    the AI's estimator imports those three so it cannot drift from the engine,
    and they never needed the whole context.
    """
    # no damage for status moves
    if move.attack_type == "Status":
        return 0

    attack = check_attack_power(turn.user.active, turn.foe.active, move)
    defense = check_defense_strength(turn.user.active, turn.foe.active, move)
    critical = check_crit(turn.user.active, move)
    STAB = check_STAB(turn.user.active, move)
    rand_factor = random.uniform(0.85, 1)  # random
    type_effectiveness = check_type_effectiveness(turn, move)
    weather = check_if_weather_affect_moves(turn.ground, move)
    # terrain is its own factor, not part of the weather one: both can be up
    # at once. See Scripts/Battle/terrain.py.
    ground = terrain.move_multiplier(turn.ground, turn.user.active,
                                     turn.foe.active, move)
    other = check_other_factor(turn, move)
    power = check_power_modifier(turn, move)

    damage = math.floor((((((2 * 100 / 5) + 2) * power * attack / defense) / 50) + 2) * weather * ground * critical * (
            rand_factor * STAB * type_effectiveness * other * move.abilitymodifier))

    return damage


# check whether Atk or SpA is used
def check_attack_power(user, target, move):
    attack = 0
    if move.attack_type == "Physical":  # physical
        attack = (target.battle_stats[1] * 0.5 if target.status == "Burn" else target.battle_stats[1]) if move.targetAtk else \
            (user.battle_stats[2] * 0.5 if user.status == "Burn" else user.battle_stats[2]) if move.DefAsAtk else \
                user.battle_stats[1] * 0.5 if user.status == "Burn" else user.battle_stats[1]
    elif move.attack_type == "Special":  # special
        attack = target.battle_stats[3] if move.targetAtk else user.battle_stats[4] if move.DefAsAtk else user.battle_stats[3]
    return attack


# check whether Def or SpDef is used
def check_defense_strength(user, target, move):
    if move.ignoreDef:
        Def, SpDef = math.floor(0.01 * 2 * target.nominal_base_stats[2] * modifierChart[2][0] * 100 + 5), \
                     math.floor(0.01 * 2 * target.nominal_base_stats[4] * modifierChart[4][0] * 100 + 5)
    else:
        Def, SpDef = target.battle_stats[2], target.battle_stats[4]
    if move.attack_type == "Physical":  # physical
        return SpDef if move.inverseDef else Def
    elif move.attack_type == "Special":  # special
        return Def if move.inverseDef else SpDef


def check_power_modifier(turn, move):
    power = move.power
    if "after_hand" in move.effect_type:
        # this means the target should move first to double power
        if turn.foe.trainer.faster:
            power *= 2
    elif "before_hand" in move.effect_type:
        # this means the user should move first to double power
        if turn.user.trainer.faster:
            power *= 2
    elif "modifier_dependent" in move.effect_type:
        positive_modifier = sum([i if i > 0 else 0 for i in turn.user.active.modifier])
        power += positive_modifier * 20
    # activate flash fire
    if "Fire" in move.type and turn.user.active.volatile_status['FlashFire'] > 0:
        power *= 1.5
    # custom retaliate move
    # the more pokemon fainted the stronger -- but at least its own power.
    # This was a bare multiply by the count, so with nobody fainted the move
    # was multiplied by zero and did nothing at all.
    if "retaliation" in move.effect_type:
        power *= max(1, sum(1 for pokemon in turn.user.trainer.team
                            if pokemon.status == "Fainted"))
    return power


# check whether weather will affect certain types of moves
def check_if_weather_affect_moves(battleground, move):
    if (battleground.weather_effect == 'Sunny' and move.type == "Water") or (battleground.weather_effect == 'Rain' and move.type == "Fire"):
        return 0.5
    elif (battleground.weather_effect == 'Sunny' and move.type == "Fire") or (battleground.weather_effect == 'Rain' and move.type == "Water"):
        return 2
    return 1


# determine crit
def check_crit(user, move):
    if random.random() <= modifierChart[8][min(3, user.modifier[8] + move.critRatio)]:
        move.critical_hit = True
        narrator.say("Crit!")
        return 1.5
    return 1


# determine STAB
def check_STAB(user, move):
    if move.type in user.type:
        narrator.say("STAB!")
        return 1.5
    return 1


# determine type effectiveness
def check_type_effectiveness(turn, move):
    initial_type_effectiveness = [2 if turn.foe.active.type[x] in move.ignoreType else typeChart[move.type][turn.foe.active.type[x]] for x in range(len(turn.foe.active.type))]
    extra_type_effectiveness = [typeChart[move.multiType[y]][turn.foe.active.type[x]] for x in range(len(turn.foe.active.type)) for y in range(len(move.multiType))]

    # special condition to override type chart (e.g. mold breaker, lock-on, grounded etc)
    # A move that names a type in `ignoreType` is saying it reaches
    # that type anyway, and the line above already gave it 2x for
    # doing so. This blanket rule then appended a 0 for anything
    # ungrounded, and prod([2, 0]) is 0 -- so Bodhisattva, a Ground
    # move written specifically to hit Flying types hard, did nothing
    # to them at all. The override is for ordinary Ground moves.
    _reaches_anyway = any(t in move.ignoreType
                          for t in turn.foe.active.type)
    if move.type == "Ground" and not _reaches_anyway:
        # grounded
        if turn.foe.active.volatile_status['Grounded'] >= 1:
            initial_type_effectiveness = [1 if effective == 0 else effective for effective in initial_type_effectiveness]
            extra_type_effectiveness = [1 if effective == 0 else effective for effective in extra_type_effectiveness]
        # ungrounded
        elif turn.foe.active.volatile_status['Grounded'] == 0 or "Flying" in turn.foe.active.type:
            initial_type_effectiveness += [0]
            extra_type_effectiveness += [0]

    for type in move.ignoreImmunity:
        if type in turn.foe.active.type:
            initial_type_effectiveness = [1 if effective == 0 else effective for effective in initial_type_effectiveness]
            extra_type_effectiveness = [1 if effective == 0 else effective for effective in extra_type_effectiveness]

    interchange_type_effectiveness = max(0, math.prod(initial_type_effectiveness))
    for y in range(len(move.interchangeType)):
        new_type_effectiveness = math.prod([typeChart[move.interchangeType[y]][turn.foe.active.type[x]] for x in range(len(turn.foe.active.type))])
        if new_type_effectiveness > interchange_type_effectiveness:
            interchange_type_effectiveness = new_type_effectiveness
            move.type = move.interchangeType[y]

    type_effectiveness = interchange_type_effectiveness if len(move.interchangeType) > 0 else math.prod(initial_type_effectiveness) * math.prod(extra_type_effectiveness)

    effectiveness_description = {
        0: "The move has no effect!",
        0.125: "Extraordinarily ineffective...",
        0.25: "Extremely ineffective...",
        0.5: "Not very effective...",
        1: "Effective.",
        2: "Super effective!",
        4: "Extremely effective!",
        8: "Extraordinarily effective!!"
    }
    # remove barrier before calculating actual damage
    if move.effect_type == "remove_team_buff" and type_effectiveness != 0:
        turn.foe.trainer.in_battle_effects = dict.fromkeys(turn.foe.trainer.in_battle_effects.keys(), 0)
    # wonder guard
    move.super_effective = True if type_effectiveness >= 2 else False
    # tinted lens
    move.not_effective = True if type_effectiveness <= 0.5 else False
    # The multiplier itself, not just "was it super effective". Anything that
    # wants to *undo* the type chart needs the number -- Blunders flattens a
    # hit to 1x, and it cannot divide by a boolean. Kept on the move beside
    # the two flags that were already derived from it, so there is one answer
    # rather than a second calculation somewhere else.
    move.type_effectiveness = type_effectiveness
    narrator.say(effectiveness_description.get(type_effectiveness))
    return type_effectiveness


def check_other_factor(turn, move):
    other = 1
    # reflect, light screen & aurora veil does not stack
    if not move.ignoreBarrier:
        if move.attack_type == "Physical":
            if turn.foe.trainer.in_battle_effects['Reflect'] > 0 or turn.foe.trainer.in_battle_effects['Aurora Veil'] > 0:
                other *= 0.5
        elif move.attack_type == "Special":
            if turn.foe.trainer.in_battle_effects['Light Screen'] > 0 or turn.foe.trainer.in_battle_effects['Aurora Veil'] > 0:
                other *= 0.5
    return other