import random
import math
import os
from contextlib import suppress
from copy import deepcopy

from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Data.pokemon import *
from Scripts.Data.abilities import *
from Scripts.Data.character_abilities import *
from Scripts.Data.battlefield import *
from Scripts.Data.moves import *
from Scripts.Data.competitors import *
from Scripts.Battle.volatile_status_condition import *
from Scripts.Battle.damage_calculation import *
from Scripts.Battle.move_additional_effect import *
from Scripts.Battle.constants import *
from Scripts.Battle.ai import *
from Scripts.Battle.switching import *
from Scripts.Battle.battle_move_execution import *
from Scripts.Battle.battle_win_condition import *
from Scripts.Battle.battle_initialization import *


def hp_bar_display(pokemon):
    health_bar = 20
    percent = int(pokemon.battle_stats[0] / pokemon.hp * 100)
    current_health_bar = int(pokemon.battle_stats[0] / pokemon.hp * health_bar)
    return f"\n|{'█' * current_health_bar}{' ' * (health_bar - current_health_bar)}| {percent}%"


def speed_adjustment(user_side, user, battleground):
    # check if paralysis exists to slow pokemon
    def check_paralysis(pokemon):
        if pokemon.status == "Paralysis":
            return pokemon.battle_stats[5] // 2
        return pokemon.battle_stats[5]

    user.battle_stats[5] = check_paralysis(user)
    user.battle_stats[5] *= 2 if user_side.in_battle_effects['Tailwind'] > 0 else 1
    user.battle_stats[5] *= -1 if battleground.field_effect["Trick Room"] > 0 else 1
    return user.battle_stats[5]


def select_move(pokemon, target, battleground):
    # comprehensive type effectiveness indicator
    move_effectiveness = []
    for move in pokemon.moveset:
        move = list_of_moves[move]
        if move.attack_type == "Status":
            move_effectiveness.append('Status')
            continue

        initial_type_effectiveness = [2 if target.type[x] in move.ignoreType else typeChart[move.type][target.type[x]] for x in range(len(target.type))]
        extra_type_effectiveness = [typeChart[move.multiType[y]][target.type[x]] for x in range(len(target.type)) for y in range(len(move.multiType))]

        # special condition to override type chart (e.g. mold breaker, lock-on, grounded etc)
        if target.volatile_status['Grounded'] == 1 and move.type == "Ground":
            initial_type_effectiveness = [1 if effective == 0 else effective for effective in initial_type_effectiveness]
            extra_type_effectiveness = [1 if effective == 0 else effective for effective in extra_type_effectiveness]

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

        type_effectiveness = interchange_type_effectiveness if len(move.interchangeType) > 0 else math.prod(initial_type_effectiveness) * math.prod(
            extra_type_effectiveness)
        move_effectiveness.append(type_effectiveness)

    pokemon_move = None
    # charging move
    if pokemon.charging[0] != "":
        pokemon_move = pokemon.charging[0]
        input(f"{CVIOLET2}{CBOLD}{pokemon.name} continues using {pokemon_move}. Enter any key to proceed.{CEND}")

    # very clumsily indicate move type and effect for noobs
    print(CBOLD, end='')
    for index, move in enumerate(pokemon.moveset):
        if move == "Switching":
            print(f"{index}: {move}")
        else:
            try:
                print(f"{index}: {move} ({list_of_moves[move].type}) "
                      f"[{'No Effect' if move_effectiveness[index] == 0 else '' if move_effectiveness[index] == 1 else 'Super Effective' if move_effectiveness[index] > 1 else 'Not Effective'}]")
            except TypeError:
                print(f"{index}: {move} ({list_of_moves[move].type}) [Status]")
    print("100: Turn on/off Auto Battle")
    print(CEND, end='')

    while pokemon_move not in pokemon.moveset:  # avoid making a non-move option
        with suppress(ValueError, IndexError):
            while True:
                move_choice = int(input(f"What is the move for {pokemon.name}?\n--> "))

                if move_choice == 100:
                    battleground.auto_battle = True if not battleground.auto_battle else False
                    print(f"Auto battle is", end=' ')
                    print('activated.\nNote: You still have to make a move on this turn. You will NOT be able to switch it off until the end of this battle.' if battleground.auto_battle else 'deactivated.')
                try:
                    if pokemon.disabled_moves[pokemon.moveset[move_choice]] <= 0:
                        pokemon_move = pokemon.moveset[move_choice]
                        break
                    else:
                        print("The move is disabled.")
                except KeyError:
                    pokemon_move = pokemon.moveset[move_choice]
                    break

    print(list_of_moves[pokemon_move].name)
    sound(audio="Assets/music/confirm.mp3")
    return list_of_moves[pokemon_move]


# the whole move execution order and procedure
def move_order_and_execution(user_side, target_side, user_team, target_team, user, target, battleground, move, target_move):
    user_turn_in_battle_stats(user_side, user)
    # status condition
    user_health_condition = check_volatile_status(user, move)
    fail, immune = True, False

    if not user_health_condition and move.name != "Switching":
        print(f"{user_side.side_color}{user.name} used {move.name}{CEND}.")

        onWeatherCheck(battleground, move)
        onParticularMoveChange(user, target, move)
        UseAbility(target_side, user_side, target, user, battleground, move, abilityphase=3)
        UseCharacterAbility(target_side, user_side, target, user, battleground, move, abilityphase=3)
        move.accuracy = move.accuracy * modifierChart[7][user.modifier[7]] * (1 / (modifierChart[6][0]) * move.evasion) if move.ignoreEvasion else \
            move.accuracy * modifierChart[7][user.modifier[7]] * (1 / (modifierChart[6][target.modifier[6]] * move.evasion))

        if not move_fail_checklist_before_execution(user, target, move, target_move):  # check if move fail before using
            if random.random() <= move.accuracy:  # accuracy check
                for _ in range(move.multi[1]):  # number of multi strikes
                    if not move_fail_checklist_during_execution(user, target, move, target_move):  # check if move fail to attack
                        move.damage = damage_calculation(user_side, target_side, user, target, battleground, move)

                        # check if the charging move double counts the special effect
                        doublecount = onChargingMove(user, target, move)

                        UseAbility(user_side, target_side, user, target, battleground, move, abilityphase=4)
                        UseAbility(target_side, user_side, target, user, battleground, move, abilityphase=5)
                        UseCharacterAbility(user_side, target_side, user, target, battleground, move, abilityphase=4)
                        UseCharacterAbility(target_side, user_side, target, user, battleground, move, abilityphase=5)

                        # no effect move and not a charging move
                        if move.damage <= 0 and move.attack_type != "Status" and move.charging not in ("Charging", "Semi-invulnerable"):
                            immune = True

                        # trigger effects when using move
                        other_effect_when_use_move(user, target, battleground, move)
                        # damaging moves
                        move.damage = int(move.damage)
                        move.recoil = math.ceil(min(target.battle_stats[0], move.damage) * move.recoil)
                        target.battle_stats[0] -= move.damage
                        # recoil moves
                        user.battle_stats[0] -= move.recoil
                        # explosive / deduct HP moves
                        user.battle_stats[0] -= math.ceil(user.hp * move.deduct)

                        print(f"{CBEIGE}{CBOLD}{move.damage} damage is dealt to {target.name} with {target.battle_stats[0]} HP left.\n"
                              f"{user.name} took {move.recoil + math.ceil(user.hp * move.deduct)} recoil damage.\n{CEND}")

                        # moves that directly cause fainted condition
                        if target.battle_stats[0] <= 0 and move.damage > 0:
                            fainting_blow_move_effect(user, target, move)

                        # check if any pokemon fainted
                        check_fainted(user, target)
                        # check if the game can end here
                        if max(sum(1 for pokemon in user_team if pokemon.status == "Fainted"),
                               sum(1 for pokemon in target_team if pokemon.status == "Fainted")) == ROUND_LIMIT[GameSystem.stage]:
                            fail = False
                            break

                        # excluding no effect moves, trigger move additional effect
                        if not immune:
                            if not doublecount:
                                move_special_effect(user_side, target_side, user, target, battleground, user_team, target_team, move)
                            # trigger ability when target is being hit
                            UseAbility(user_side, target_side, user, target, battleground, move, abilityphase=6)
                            UseAbility(target_side, user_side, target, user, battleground, move, abilityphase=7)
                            UseCharacterAbility(user_side, target_side, user, target, battleground, move, abilityphase=6)
                            UseCharacterAbility(target_side, user_side, target, user, battleground, move, abilityphase=7)
                            fail = False
            # the move is dodged
            else:
                print(f"\nOpponent Pokemon avoided the attack!\n")

        if fail:
            move_fail_consequence_upon_execution(user, target, move)

    else:
        print(f"{target.name} is still {target.status}.")

    user.previous_move = move
    user.modifier, target.modifier = check_modifier_limit(user), check_modifier_limit(target)
    print("")


# reducing hp at the end of each turn
def hp_decreasing_modifier(pokemon, target, battleground):
    if pokemon.ability != 'Magic Guard':
        # status condition
        if pokemon.status == "Poison":  # regular poison
            print(f"The Poison has eroded {pokemon.name} {max(1, pokemon.hp // 8)} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 8)
        elif pokemon.status == "BadPoison":  # bad poison
            pokemon.volatile_status["NonVolatile"] += 1
            print(f"The Bad Poison has eroded {pokemon.name} {max(1, pokemon.hp * pokemon.volatile_status['NonVolatile'] // 16)} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp * pokemon.volatile_status['NonVolatile'] // 16)
        elif pokemon.status == "Burn":  # burn
            print(f"The Burn has burned away {pokemon.name} {max(1, pokemon.hp // 16)} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 16)
        # sudden death
        if battleground.sudden_death:
            print(f"The dark energy has eroded {pokemon.name} {max(1, pokemon.hp // 4)} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 4)

        # weather effect
        if battleground.weather_effect == 'Sandstorm':  # sandstorm
            if "Ground" not in pokemon.type and "Steel" not in pokemon.type and "Rock" not in pokemon.type:  # ground, rock, steel type immune
                ability_list = ["Sand Veil", "Sand Rush"]
                if any(ability not in pokemon.ability for ability in ability_list):
                    print(f"The Sandstorm has hurt {pokemon.name} {pokemon.hp // 16} HP.")
                    pokemon.battle_stats[0] -= max(1, pokemon.hp // 16)
        elif battleground.weather_effect == 'Hail':  # hail
            if "Ice" not in pokemon.type:  # ice type immune
                ability_list = ["Snow Cloak"]
                if any(ability not in pokemon.ability for ability in ability_list):
                    print(f"The Hail has hurt {pokemon.name} {pokemon.hp // 16} HP.")
                    pokemon.battle_stats[0] -= max(1, pokemon.hp // 16)

        # binding effect
        if pokemon.volatile_status['Binding'] >= 1:
            print(f"The binding has damaged {pokemon.name} {pokemon.hp // 8} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 8)
        # cursed
        if pokemon.volatile_status['Curse'] >= 1:
            print(f"The curse has damaged {pokemon.name} {pokemon.hp // 4} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 4)
        # leech seed
        if pokemon.volatile_status['LeechSeed'] > 0:
            print(f"Leech seed has drained {pokemon.name} {pokemon.hp // 8} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 8)
        if target.volatile_status['LeechSeed'] > 0:
            pokemon.battle_stats[0] += max(1, min(target.hp // 8, pokemon.hp - pokemon.battle_stats[0]))
        # ingrain
        if pokemon.volatile_status['Ingrain'] > 0:
            print(f"Ingrain roots has regenerated {pokemon.name} {min(pokemon.hp // 16, pokemon.hp - pokemon.battle_stats[0])} HP.")
            pokemon.battle_stats[0] += max(1, min(pokemon.hp // 16, pokemon.hp - pokemon.battle_stats[0]))
        # aqua ring
        if pokemon.volatile_status['AquaRing'] > 0:
            print(f"Aqua ring has regenerated {pokemon.name} {min(pokemon.hp // 16, pokemon.hp - pokemon.battle_stats[0])} HP.")
            pokemon.battle_stats[0] += max(1, min(pokemon.hp // 16, pokemon.hp - pokemon.battle_stats[0]))

    return pokemon.battle_stats[0]


# check if weather effect stops
def check_weather_persist(battleground):
    if battleground.artificial_weather:
        if battleground.weather_turn == WEATHER_EFFECT_TURNS:
            battleground.artificial_weather = False
            return battleground.starting_weather_effect
        battleground.weather_turn += 1
    return battleground.weather_effect


def switch_fainted_pokemon_at_end_of_turn(user, opponent, user_team, opponent_team, battleground):
    if user_team[0].status == "Fainted" and battleground.battle_continuation:  # fainted
        if user.main:  # human
            user_team[0] = switching_criteria(user, opponent, user_team, opponent_team, battleground) if not battleground.auto_battle else \
                switching_mechanism(user, opponent, battleground, user_team, opponent_team, ai_switching_mechanism(opponent, user, battleground), False)
        else:  # ai
            user_team[0] = switching_mechanism(user, opponent, battleground, user_team, opponent_team,
                           ai_switching_mechanism(opponent, user, battleground), False)
    return user_team[0]