import random
import math
from contextlib import suppress
from copy import deepcopy

from Scripts.Art.text_color import *
from Scripts.Data.pokemon import *
from Scripts.Data.abilities import *
from Scripts.Data.moves import *
from Scripts.Data.competitors import *
from Scripts.Game.game_procedure import *
from Scripts.Battle.weather import *
from Scripts.Battle.entry_hazard import *
from Scripts.Battle.type_chart import *
from Scripts.Battle.damage_calculation import *
from Scripts.Battle.constants import *
from Scripts.Battle.type_immunity import *
from Scripts.Battle.battle_checklist import *
from Scripts.Battle.switching import *
from Scripts.Battle.ai import *


# check if the modifier reaches +6/-6
def check_modifier_limit(pokemon):
    pokemon.modifier = [6 if x > 6 else x for x in pokemon.modifier]
    pokemon.modifier = [-6 if x < -6 else x for x in pokemon.modifier]
    return pokemon.modifier


def move_special_effect(user_side, target_side, user, target, battleground, user_team, target_team, move):
    move_additional_effect = {
        "target_non_volatile": check_move_target_non_volatile_status_effect,
        "target_volatile": check_move_target_volatile_status_effect,
        "user_volatile": check_move_user_volatile_status_effect,
        "opponent_modifier": check_move_target_modifier,
        "self_modifier": check_move_user_modifier,
        "self_heal": check_move_user_heal,
        "team_status_heal": check_move_heal_team_status,
        "hp_draining": check_move_hp_draining,
        "user_protection": check_move_user_protection,
        "self_team_buff": check_move_user_team_buff,
        "weather_effect": check_move_battleground_weather_effect,
        "field_effect": check_move_battleground_field_effect,
        "apply_entry_hazard": check_move_entry_hazard_effect,
        "clear_entry_hazard": check_move_clear_entry_hazard,
        "switching": check_move_self_switching_effect,
        "cursing": check_move_cursing,
        "hp_split": check_move_hp_split,
        "target_disable": check_move_disable,
        "reset_target_modifier": check_move_reset_target_modifier,
        "reset_user_modifier": check_move_reset_user_modifier,
        "swap_barrier": check_move_swap_barrier,
        "add_target_type": check_move_add_target_type,
        "countering": check_move_countering,
    }
    vartype = type(move.effect_type)
    # only one effect
    if vartype is str:
        if move.effect_type in move_additional_effect.keys():
            move_additional_effect[move.effect_type](user_side, target_side, user, target, battleground, user_team, target_team, move, move.special_effect)
    # more than one effect
    elif vartype is list:
        for i in range(len(move.effect_type)):
            special_effect = move.special_effect[i]
            move_additional_effect[move.effect_type[i]](user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect)


# check if the move induces status condition on the target
def check_move_target_non_volatile_status_effect(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    # status condition
    temporary_status = special_effect(move.effect_accuracy)
    if target.status == "Normal" and temporary_status[0] != "Normal":  # change of non-volatile status
        target.status = status_effect_immunity_check(user, target, move, temporary_status[0])
        with suppress(IndexError, KeyError):
            if target.volatile_status["NonVolatile"] <= 0:
                target.volatile_status["NonVolatile"] = temporary_status[1]
                print(f"{target.name} is now {target.status}!")
    elif target.status != "Normal" and temporary_status[0] != "Normal":  # non-volatile status won't add up
        print(f"{target.name} is already {target.status}!")


# check if the move induces volatile status on the target
def check_move_target_volatile_status_effect(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    # status condition
    temporary_status = special_effect(move.effect_accuracy)
    # for yawn only
    if temporary_status[0] == "Yawn" and target.status != "Normal":
        print("The move failed.")
    else:
        with suppress(KeyError):
            if target.volatile_status[temporary_status[0]] <= 0:
                target.volatile_status[temporary_status[0]] = temporary_status[1]
                print(f"{target.name} is now {temporary_status[0]}!")
            else:
                print(f"The opponent is already {temporary_status[0]}!")


# check if the move induces volatile status on the user
def check_move_user_volatile_status_effect(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    # status condition
    temporary_status = special_effect(move.effect_accuracy)
    with suppress(KeyError):
        if user.volatile_status[temporary_status[0]] <= 0 or temporary_status[0] == "Grounded":
            user.volatile_status[temporary_status[0]] = temporary_status[1]
            print(f"You are already {temporary_status[0]}!")
        else:
            print(f"You are already {temporary_status[0]}!")


# check if the move affects the target (+ve/-ve)
def check_move_target_modifier(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    # increase/decrease stats on target
    target.applied_modifier = special_effect if random.random() <= move.effect_accuracy else [0] * 9
    target.modifier = list(map(operator.add, target.applied_modifier, target.modifier))
    target.modifier = check_modifier_limit(target)
    if sum(target.applied_modifier) > 0:
        print(target.name, end='')
        for index, stats in enumerate(target.applied_modifier):
            if stats != 0:
                print(f" | {MODIFIER[index]} {stats}", end='')
        print()


# check if the move affects the user (+ve/-ve)
def check_move_user_modifier(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    # increase/decrease stats on user
    user.applied_modifier = special_effect if random.random() <= move.effect_accuracy else [0] * 9
    user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
    user.modifier = check_modifier_limit(user)
    if sum(user.applied_modifier) > 0:
        print(user.name, end='')
        for index, stats in enumerate(user.applied_modifier):
            if stats != 0:
                print(f" | {MODIFIER[index]} {stats}", end='')
        print()


# check if the move heals the user
def check_move_user_heal(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    print(f"{user.name} heals {math.floor(user.hp * special_effect)} HP.")
    user.battle_stats[0] = min(user.hp, user.battle_stats[0] + math.floor(user.hp * special_effect))


# check if the move heals the status of the team
def check_move_heal_team_status(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    for pokemon in user_team:
        pokemon.status = "Normal"
    print(f"{user.name}'s team's status condition has been healed!")


# check if the move drains hp
def check_move_hp_draining(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    print(f"{user.name} drains {math.floor((move.damage + min(target.battle_stats[0], 0)) * special_effect)} HP.")
    user.battle_stats[0] += min(user.hp - user.battle_stats[0], math.floor((move.damage + min(target.battle_stats[0], 0)) * special_effect))


# protective move
def check_move_user_protection(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    protective_move_list = {"Protect": 1, "King's Shield": 2, "Baneful Bunker": 3}
    if random.random() <= (1 / pow(2, user.protection[1])):
        user.protection[0] = protective_move_list[move.name]
        user.protection[1] += 1
    else:
        print("The move failed!")


# check if the move buff the whole team
def check_move_user_team_buff(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    team_buff = special_effect
    if team_buff == "Aurora Veil" and battleground.weather_effect != 'Hail':  # hail
        print(f"Not hailing. {team_buff} failed.")
    else:
        if user_side.in_battle_effects[team_buff] > 0:
            print(f"{team_buff} is already there.")
        else:
            print(f"{team_buff} is set up.")
            user_side.in_battle_effects[team_buff] = TEAM_BUFF_TURNS


# check if the move affects the weather
def check_move_battleground_weather_effect(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    # weather effect
    battleground.weather_effect = special_effect
    battleground.artificial_weather = True
    print(f"The Weather is now {weather_desc[battleground.weather_effect]}.")


def check_move_battleground_field_effect(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    # field effect
    battleground.field_effect[special_effect] = 0 if battleground.field_effect[special_effect] > 0 else FIELD_EFFECT_TURNS


# check if the move applies entry hazard
def check_move_entry_hazard_effect(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    maximum_usage = {"Stealth Rock": 1, "Spikes": 3, "Toxic Spikes": 2, "Sticky Web": 1}  # maximum number of entry hazards that can be placed
    # entry hazard
    if target_side.entry_hazard[special_effect] < maximum_usage[special_effect]:
        print(f"{special_effect} has been set up.")
        target_side.entry_hazard[special_effect] += 1
    else:
        print("The entry hazard has already been placed!")


# clear entry hazard
def check_move_clear_entry_hazard(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    if move.name == "Rapid Spin":
        user_team[0].volatile_status['Binding'] = 0
        user_side.entry_hazard = dict.fromkeys(user_side.entry_hazard.keys(), 0)
    elif move.name == "Defog":
        user_side.entry_hazard = dict.fromkeys(user_side.entry_hazard.keys(), 0)
        target_side.entry_hazard = dict.fromkeys(target_side.entry_hazard.keys(), 0)
        target_side.in_battle_effects = dict.fromkeys(target_side.in_battle_effects.keys(), 0)


# switched out own pokemon when using this move
def check_move_self_switching_effect(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    number_of_pokemon = sum(1 for pokemon in user_team if pokemon.status != "Fainted")
    if number_of_pokemon > 1:
        if user_side.main:  # protagonist side
            if not battleground.auto_battle:
                if move.name == "Baton Pass":
                    user_team[0] = switching_criteria(user_side, target_side, user_team, target_team, battleground, True, True)
                else:
                    user_team[0] = switching_criteria(user_side, target_side, user_team, target_team, battleground, True)
            else:
                user_team[0] = switching_mechanism(user_side, target_side, battleground, user_team, target_team,
                                                   ai_switching_mechanism(target_side, user_side, battleground, True, True), False)
        else:
            user_team[0] = switching_mechanism(user_side, target_side, battleground, user_team, target_team,
                                               ai_switching_mechanism(target_side, user_side, battleground, True, True), False)


# exclusive for move curse only
def check_move_cursing(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    if "Ghost" in user.type:
        if target.volatile_status['Curse'] != 0:
            print("The opponent is already cursed!")
        else:
            user.battle_stats[0] -= user.hp // 2
            target.volatile_status['Curse'] = 1
    else:
        # increase/decrease stats on user
        user.applied_modifier = special_effect
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        print(user.modifier)


def check_move_hp_split(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    if special_effect == "Split":
        splited_hp = (user.battle_stats[0] + target.battle_stats[0]) // 2
        user.battle_stats[0], target.battle_stats[0] = min(user.hp, splited_hp), min(target.hp, splited_hp)
    elif special_effect == "Same":
        target.battle_stats[0] = min(user.battle_stats[0], target.battle_stats[0])


def check_move_disable(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    if special_effect == "Disable":
        with suppress(ValueError, AttributeError):
            try:
                if target.disabled_moves[target.previous_move.name] != 0 and target.previous_move.name != "Switching":
                    print("The move is already disabled!")
            except KeyError:
                target.disabled_moves[target.previous_move.name] = 5
    elif special_effect == "Taunt":
        for i in range(len(target.moveset)):
            move = list_of_moves[target.moveset[i]]
            if move.attack_type == "Status" and move.name != "Switching":
                try:
                    if target.disabled_moves[move.name] != 0:
                        print("The move is already disabled!")
                except KeyError:
                    target.disabled_moves[move.name] = 5
    elif special_effect == "Encore":
        for i in range(len(target.moveset)):
            move = list_of_moves[target.moveset[i]]
            try:
                if move.name != "Switching" and move.name != target.previous_move.name and target.previous_move.name != "Switching":
                    try:
                        if target.disabled_moves[move.name] != 0:
                            print("The move is already disabled!")
                    except KeyError:
                        target.disabled_moves[move.name] = 4
            except AttributeError:
                print("The move failed!")
    elif special_effect == "Sound":
        for i in range(len(target.moveset)):
            move = list_of_moves[target.moveset[i]]
            if 'f' in move.flags:
                try:
                    if target.disabled_moves[move.name] != 0 and target.previous_move.name != "Switching":
                        print("The move is already disabled!")
                except KeyError:
                    target.disabled_moves[move.name] = 2


def check_move_reset_target_modifier(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    target.modifier = [0] * 9
    print(f"{target.name}'s stat change has been reset!")


def check_move_reset_user_modifier(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    user.modifier = [0] * 9
    print(f"{user.name}'s stat change has been reset!")


def check_move_swap_barrier(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    user_side.in_battle_effects, target_side.in_battle_effects = target_side.in_battle_effects, user_side.in_battle_effects
    user_side.entry_hazard, target_side.entry_hazard = target_side.entry_hazard, user_side.entry_hazard
    print("Entry hazard and in-game barriers have been swapped!")


def check_move_add_target_type(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    for typing in special_effect:
        if typing not in target.type:
            target.type += [typing]
            print(f"{target.name} has been added {typing} type.")


def check_move_countering(user_side, target_side, user, target, battleground, user_team, target_team, move, special_effect):
    type_effectiveness = 0 if math.prod([typeChart[move.type][target.type[x]] for x in range(len(target.type))]) == 0 else 1
    if type(target.previous_move) is not str:
        target.previous_move.damage = getattr(target.previous_move, 'damage', 0)
        if move.name == "Counter" and target.previous_move.attack_type == "Physical":
            print(f"{target.name} has been counter-attacked, suffering {target.previous_move.damage * 2 * type_effectiveness} damage.")
            target.battle_stats[0] -= target.previous_move.damage * 2 * type_effectiveness
        elif move.name == "Mirror Coat" and target.previous_move.attack_type == "Special":
            print(f"{target.name} has been counter-attacked, suffering {target.previous_move.damage * 2 * type_effectiveness} damage.")
            target.battle_stats[0] -= target.previous_move.damage * 2 * type_effectiveness
        elif move.name == "Metal Burst":
            print(f"{target.name} has been counter-attacked, suffering {target.previous_move.damage * 1.5 * type_effectiveness} damage.")
            target.battle_stats[0] -= target.previous_move.damage * 1.5 * type_effectiveness
