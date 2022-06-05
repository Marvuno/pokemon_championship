from abilities import *
import random
import math


# damage calculation
def damage_calculation(user_side, target_side, user, target, battleground, move):
    # no damage for status moves
    if move.attack_type == "Status":
        return 0

    attack = check_attack_power(user, target, move)
    defense = check_defense_strength(user, target, move)
    critical = check_crit(user, move)
    STAB = check_STAB(user, move)
    rand_factor = random.uniform(0.85, 1)  # random
    type_effectiveness = check_type_effectiveness(target_side, target, move)
    weather = check_if_weather_affect_moves(battleground, move)
    other = check_other_factor(user_side, target_side, user, target, move)
    power = check_power_modifier(user_side, target_side, user, target, move)

    damage = math.floor((((((2 * 100 / 5) + 2) * power * attack / defense) / 50) + 2) * weather * critical * (
            rand_factor * STAB * type_effectiveness * other * move.abilitymodifier))

    return damage


# check whether Atk or SpA is used
def check_attack_power(user, target, move):
    if move.attack_type == "Physical":  # physical
        return (target.battle_stats[1] * 0.5 if target.status == "Burn" else target.battle_stats[1]) if move.targetAtk else \
            (user.battle_stats[1] * 0.5 if user.status == "Burn" else user.battle_stats[1])
    elif move.attack_type == "Special":  # special
        return target.battle_stats[3] if move.targetAtk else user.battle_stats[3]


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


def check_power_modifier(user_side, target_side, user, target, move):
    power = move.power
    if "after_hand" in move.effect_type:
        # this means target should move first to double power
        if target_side.faster:
            power *= 2
    elif "before_hand" in move.effect_type:
        # this means user should move first to double power
        if user_side.faster:
            power *= 2
    elif "modifier_dependent" in move.effect_type:
        positive_modifier = sum([i if i > 0 else 0 for i in user.modifier])
        power += positive_modifier * 20
    # activate flash fire
    if "Fire" in move.type and user.volatile_status['Flash Fire'] > 0:
        power *= 1.5
    # custom retaliate move
    # the more pokemon fainted the stronger
    if "retaliation" in move.effect_type:
        power *= sum(1 for pokemon in user_side.team if pokemon.status == "Fainted")
    return power


# check whether weather will affect certain types of moves
def check_if_weather_affect_moves(battleground, move):
    if (battleground.weather_effect == 1 and move.type == "Water") or (battleground.weather_effect == 2 and move.type == "Fire"):
        return 0.5
    elif (battleground.weather_effect == 1 and move.type == "Fire") or (battleground.weather_effect == 2 and move.type == "Water"):
        return 2
    return 1


# determine crit
def check_crit(user, move):
    if random.random() <= modifierChart[8][user.modifier[8] + move.critRatio]:
        move.critical_hit = True
        print("Crit!")
        return 1.5
    return 1


# determine STAB
def check_STAB(user, move):
    if move.type in user.type:
        print("STAB!")
        return 1.5
    return 1


# determine type effectiveness
def check_type_effectiveness(target_side, target, move):
    initial_type_effectiveness = [2 if target.type[x] in move.ignoreType else typeChart[move.type][target.type[x]] for x in range(len(target.type))]
    extra_type_effectiveness = [typeChart[move.multiType[y]][target.type[x]] for x in range(len(target.type)) for y in range(len(move.multiType))]

    # special condition to override type chart (e.g. mold breaker, lock-on, grounded etc)
    if move.type == "Ground":
        # grounded
        if target.volatile_status['Grounded'] == 1:
            initial_type_effectiveness = [1 if effective == 0 else effective for effective in initial_type_effectiveness]
            extra_type_effectiveness = [1 if effective == 0 else effective for effective in extra_type_effectiveness]
        # ungrounded
        elif target.volatile_status['Grounded'] == 0 and "Flying" not in target.type:
            initial_type_effectiveness += [0]
            extra_type_effectiveness += [0]

    for type in move.ignoreImmunity:
        if type in target.type:
            initial_type_effectiveness = [1 if effective == 0 else effective for effective in initial_type_effectiveness]
            extra_type_effectiveness = [1 if effective == 0 else effective for effective in extra_type_effectiveness]

    interchange_type_effectiveness = max(0, math.prod(initial_type_effectiveness))
    for y in range(len(move.interchangeType)):
        new_type_effectiveness = math.prod([typeChart[move.interchangeType[y]][target.type[x]] for x in range(len(target.type))])
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
        target_side.in_battle_effects = dict.fromkeys(target_side.in_battle_effects.keys(), 0)
    # wonder guard
    move.super_effective = True if type_effectiveness >= 2 else False
    # tinted lens
    move.not_effective = True if type_effectiveness <= 0.5 else False
    print(effectiveness_description.get(type_effectiveness))
    return type_effectiveness


def check_other_factor(user_side, target_side, user, target, move):
    other = 1
    # reflect, light screen & aurora veil does not stack
    if not move.ignoreBarrier:
        if move.attack_type == "Physical":
            if target_side.in_battle_effects['Reflect'] > 0 or target_side.in_battle_effects['Aurora Veil'] > 0:
                other *= 0.5
        elif move.attack_type == "Special":
            if target_side.in_battle_effects['Light Screen'] > 0 or target_side.in_battle_effects['Aurora Veil'] > 0:
                other *= 0.5
    return other