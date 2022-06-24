import random
import math
from contextlib import suppress
from copy import deepcopy
import os

from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Battle.entry_hazard import *
from Scripts.Battle.volatile_status_condition import *
from Scripts.Battle.type_chart import *
from Scripts.Battle.damage_calculation import *
from Scripts.Battle.constants import *
from Scripts.Battle.ai import *
from Scripts.Battle.switching import *
import Scripts.Battle.battle_checklist
from Scripts.Game.game_system import *
from Scripts.Data.pokemon import *
from Scripts.Data.abilities import *
from Scripts.Data.battlefield import *
from Scripts.Data.moves import *
from Scripts.Data.competitors import *
from Scripts.Data.moves import *


def user_turn_in_battle_stats(user_side, user):
    # decrease with turns
    diminishing_volatile_status = ['Confused', 'Frighten', 'DestinyBond', 'Torment', 'Binding', 'Yawn']
    # increase with turns
    increment_volatile_status = []
    for status in diminishing_volatile_status:
        user.volatile_status[status] -= 1 if user.volatile_status[status] > 0 else 0
    # for status in increment_volatile_status:
    #     user.volatile_status[status] += 1 if user.volatile_status[status] > 0 else 0
    with suppress(IndexError, TypeError, KeyError):
        for move_name in user.disabled_moves.copy():
            user.disabled_moves[move_name] -= 1
            if user.disabled_moves[move_name] <= 0:
                del user.disabled_moves[move_name]
        user.disabled_moves = {k: v for k, v in user.disabled_moves.items() if k > 0}
    for key, values in user_side.in_battle_effects.items():
        user_side.in_battle_effects[key] -= 1 if values > 0 else 0


# check if weather effect affects the move
def onWeatherCheck(battleground, move):
    if not move.ignoreWeather:
        if battleground.weather_effect == 'Hail':  # hail
            if move.name == "Blizzard":
                move.accuracy = GUARANTEE_ACCURACY
            elif move.name == "Solar Beam" or move.name == "Solar Blade":
                move.power /= 2
        elif battleground.weather_effect == 'Sunny':  # Sunny
            if move.name == "Solar Beam" or move.name == "Solar Blade":
                move.charging = ""
            elif move.name == "Thunder":
                move.accuracy /= 2
        elif battleground.weather_effect == 'Rain':  # rain
            if move.name == "Solar Beam" or move.name == "Solar Blade":
                move.power /= 2
            elif move.name == "Thunder" or move.name == "Hurricane" or move.name == "Thunderous Trident":
                move.accuracy = GUARANTEE_ACCURACY
        elif battleground.weather_effect == 'Sandstorm':  # sandstorm
            if move.name == "Solar Beam" or move.name == "Solar Blade":
                move.power /= 2


def onParticularMoveChange(user, target, move):
    if move.name == "Toxic" and "Poison" in user.type:
        move.accuracy = 1
    elif move.name == "Brine" and target.battle_stats[0] <= target.hp // 2:
        move.power *= 2
    elif move.name == "Venoshock" and (target.status == "Poison" or target.status == "BadPoison"):
        move.power *= 2
    elif move.name in ("Electro Ball", "Time Pressure"):
        relative_speed = target.battle_stats[5] / user.battle_stats[5]
        move.power = 40 if relative_speed > 1 else 60 if relative_speed > 0.5 else 80 if relative_speed > 0.3333 else 120 if relative_speed > 0.25 else 150
    elif move.name == "Facade" and user.status != "Normal":
        move.power *= 2
    elif move.name == "Hex" and target.status != "Normal":
        move.power *= 2
    elif move.name == "Acupressure":
        user.applied_modifier[random.randint(1, 7)] += 2
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
    if target.volatile_status['TakeAim'] > 0:
        move.accuracy = GUARANTEE_ACCURACY
    if move.charging in ("Charging", "Semi-invulnerable") and user.charging[0] == "":
        move.accuracy = GUARANTEE_ACCURACY


def onChargingMove(user, target, move):
    # charging moves
    # frenzy moves
    user.charging[2] -= 1 if user.charging[2] > 0 else 0

    if move.charging == "Frenzy" and user.charging[0] == "":
        user.charging = [move.name, move.charging, random.randint(1, 2)]
    # non-frenzy moves
    elif (move.charging == "Charging" or move.charging == "Semi-invulnerable") and user.charging[0] == "":
        user.charging = [move.name, move.charging, 1]
        print(f"{user.name} is charging power.")
        move.damage = 0
    # time to activate
    elif user.charging[0] != "" and user.charging[2] == 0:
        if user.charging[1] == "Frenzy":
            user.volatile_status["Confused"] = random.randint(2, 5)
        user.charging = ["", "", 0]
        return True
    return False


def move_fail_checklist_before_execution(user, target, move, target_move):
    # disabled move
    with suppress(ValueError, KeyError):
        if user.disabled_moves[move.name] > 0:
            print("The move failed.")
            return True
    # first turn priority move
    if 'j' in move.flags and user.volatile_status['Turn'] > 2:
        print("The move failed.")
        return True
    # sucker punch
    elif move.name == "Sucker Punch" and target_move.attack_type == "Status":
        print("The move failed.")
        return True
    # belly drum
    elif move.name == "Belly Drum" and (user.battle_stats[0] <= math.ceil(user.hp * move.deduct) or user.modifier[1] == 6):
        print("The move failed.")
        return True
    elif move.name == "Dream Eater" and target.status != "Sleep":
        print("The move failed.")
        return True
    elif move.name == "Snore" and user.status != "Sleep":
        print("The move failed.")
        return True
    # powder moves
    elif 'g' in move.flags and 'Grass' in target.type:
        print("The move failed.")
        return True
    # shell trap for turtonator
    elif move.name == "Shell Trap" and 'a' not in target_move.flags:
        print("The move failed.")
        return True

    return False


def move_fail_checklist_during_execution(user, target, move, target_move):
    if not move.ignoreInvulnerability:
        if target.charging[1] == "Semi-invulnerable":
            if target.charging[0] == "Fly" or target.charging[0] == "Bounce":
                if move.name == "Thunder" or move.name == "Hurricane" or move.name == "Smack Down":
                    target.charging = ["", "", 0]
                    return False
            elif target.charging[0] == "Dig":
                if move.name == "Earthquake" or move.name == "Magnitude":
                    move.power *= 2
                    target.charging = ["", "", 0]
                    return False
            elif target.charging[0] == "Dive":
                if move.name == "Whirlpool" or move.name == "Surf":
                    move.power *= 2
                    target.charging = ["", "", 0]
                    return False
            if 'b' in move.flags:
                return False
            return True
    if target.protection[0] > 0 and 'b' not in move.flags:  # being protected
        # hardcode protective effects
        if 'a' in move.flags:
            # king's shield
            if target.protection[0] == 2:
                user.applied_modifier = [0, -1, 0, 0, 0, 0, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            # baneful bunker
            elif target.protection[0] == 3:
                if user.status == "Normal":
                    if ("Poison" or "Steel") not in user.type:
                        print(f"{user.name} has been poisoned.")
                        user.status = "Poison"
        print("Opponent Pokemon protected the move.")
        return True
    elif target.status == "Fainted" and 'b' not in move.flags:  # fainted already
        print("Opponent Pokemon is already fainted!")
        return True
    return False


def other_effect_when_use_move(user, target, battleground, move):
    if user.volatile_status['Torment'] > 0:
        user.disabled_moves[move.name] = 1
    if user.volatile_status['Frighten'] > 0:
        move.damage //= 2
    if move.name == "Spectral Thief":
        user.applied_modifier = [modifier if modifier > 0 else 0 for modifier in target.modifier]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        target.modifier = [0 if modifier > 0 else modifier for modifier in target.modifier]
    # double power when hit
    if move.multi[0] == 2:
        move.power *= 2


def fainting_blow_move_effect(user, target, move):
    if target.volatile_status['DestinyBond'] > 0:
        user.battle_stats[0] = 0
        print(f"{user.name} is affected by destiny bond!")
    if move.name == "Fell Stinger":
        user.applied_modifier = [0, 3, 0, 0, 0, 0, 0, 0, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
    if move.name == "Cannibalism":
        print(f"{user.name} absorbs {target.name} and regenerates {math.floor((move.damage + min(target.battle_stats[0], 0)) * 0.5)} HP.")
        user.battle_stats[0] += min(user.hp - user.battle_stats[0], math.floor((move.damage + min(target.battle_stats[0], 0)) * 0.5))


def move_fail_consequence_upon_execution(user, target, move):
    # disrupting frenzy moves (e.g. outrage)
    if user.charging[0] != "":
        print("Failed")
        user.charging = ["", "", 0]
    elif move.crash > 0:
        user.battle_stats[0] -= math.floor(user.hp * move.crash)
        check_fainted(user, target)


# check if any pokemon fainted during or after the turn
def check_fainted(user, target):
    if target.status != "Fainted":  # check fainted or not
        if target.battle_stats[0] <= 0:  # out of HP
            print(f"{target.side_color}{target.name} fainted!{CEND}")
            target.status = "Fainted"
    if user.status != "Fainted":
        if user.battle_stats[0] <= 0:  # recoil damage trigger fainted
            print(f"{user.side_color}{user.name} fainted!{CEND}")
            user.status = "Fainted"