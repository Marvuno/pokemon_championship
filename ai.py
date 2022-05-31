import random
from contextlib import suppress
from text_color import *
from weather import *
from pokemon import *
from abilities import *
from battlefield import *
from entry_hazard import *
from volatile_status_condition import *
from type_chart import *
from moves import *
from start_interface import *
from competitors import *
from game_procedure import *
from constants import *
from battle_cycle import *
from damage_calculation import *
from move_additional_effect import *
import battle_checklist
import battle_move_execution
import battle_win_condition
from music import *
from switching import *
from copy import deepcopy


def estimated_damage_calculation(attacker_side, defender_side, attacker, defender, move):
    attack = attacker.battle_stats[1] if move.attack_type == "Physical" else attacker.battle_stats[3]
    defense = defender.battle_stats[2] if move.attack_type == "Physical" else defender.battle_stats[4]
    STAB = 1.5 if move.type in attacker.type else 1
    type_effectiveness = math.prod([typeChart[move.type][defender.type[x]] for x in range(len(defender.type))])
    other = check_other_factor(attacker_side, defender_side, attacker, defender, move)
    power = check_power_modifier(attacker_side, defender_side, attacker, defender, move)
    return (42 * power * attack / defense) // 50 * STAB * type_effectiveness * other


def dumb_ai_select_move(battleground, protagonist, ai):
    # low-level ai behavior
    # it will only consider the move with highest dmg against player
    # it never uses status moves
    # it switches if player pokemon has *4 effective move
    protagonist_pokemon, ai_pokemon = deepcopy(protagonist.team[0]), deepcopy(ai.team[0])

    if ai_pokemon.charging[0] != "":
        return list_of_moves[ai_pokemon.charging[0]]

    move_damage, protagonist_move_damage, incoming_move = [0] * len(ai_pokemon.moveset), 0, list_of_moves[protagonist_pokemon.moveset[1]]
    for move in protagonist_pokemon.moveset:
        move = list_of_moves[move]
        damage = estimated_damage_calculation(protagonist, ai, protagonist_pokemon, ai_pokemon, move)
        protagonist_move_damage = max(damage, protagonist_move_damage)
        if damage == protagonist_move_damage:
            incoming_move = move

    for index, move in enumerate(ai_pokemon.moveset):
        move = deepcopy(list_of_moves[move])
        move.damage = estimated_damage_calculation(ai, protagonist, ai_pokemon, protagonist_pokemon, move)

        UseAbility(ai, protagonist, ai_pokemon, protagonist_pokemon, battleground, move, abilityphase=2)
        UseAbility(protagonist, ai, protagonist_pokemon, ai_pokemon, battleground, move, abilityphase=3)

        move_damage[index] = move.damage

        # failed moves
        with suppress(KeyError):
            if ai_pokemon.disabled_moves[move.name] > 0:
                move_damage[index] = INFINITY * -1
        if 'j' in move.flags and ai_pokemon.volatile_status["Turn"] > 1:
            move_damage[index] = INFINITY * -1

    print("")
    for index, move in enumerate(ai_pokemon.moveset):
        print(f"{list_of_moves[move].name} || Damage: {move_damage[index]}")
    print("")

    if math.prod([typeChart[incoming_move.type][ai_pokemon.type[x]] for x in range(len(ai_pokemon.type))]) == 4 or max(move_damage) == 0:
        ai.position_change = ai_switching_mechanism(protagonist, ai, battleground, True)
        # if confirmed switched, then use Switching
        if ai.position_change != 0:
            return list_of_moves[ai.team[0].moveset[0]]  # switching
        else:
            if list_of_moves[ai_pokemon.moveset[move_damage.index(max(move_damage))]] == 0:
                return list_of_moves[ai_pokemon.moveset[random.randint(1, len(ai_pokemon.moveset) - 1)]]
    return list_of_moves[ai_pokemon.moveset[move_damage.index(max(move_damage))]]


def smart_ai_select_move(battleground, protagonist, ai):
    # non-low-level character ai behavior
    # consider all kinds of effects with scoring system to determine best move
    # switches when no moves are considered good
    # the ai knows the moves of the player but not his pokemon team

    # maximum number of entry hazards that can be placed
    entry_hazard_maximum_usage = {"Stealth Rock": 1, "Spikes": 3, "Toxic Spikes": 2, "Sticky Web": 1}
    protagonist_pokemon, ai_pokemon = deepcopy(protagonist.team[0]), deepcopy(ai.team[0])
    protagonist_stats, ai_stats = protagonist_pokemon.battle_stats, ai_pokemon.battle_stats

    # charging moves
    if ai_pokemon.charging[0] != "":
        return list_of_moves[ai_pokemon.charging[0]]

    move_score, move_damage, defeating_turns, makeshift_moveset = [0] * len(ai_pokemon.moveset), [0] * len(ai_pokemon.moveset), [0] * len(ai_pokemon.moveset), []
    protagonist_move_score, incoming_move, incoming_move_max_damage, best_pokemon_index = [0] * len(protagonist_pokemon.moveset), "", INFINITY, 0

    for index, move in enumerate(protagonist_pokemon.moveset):
        move = deepcopy(list_of_moves[move])
        move.accuracy = min(move.accuracy * modifierChart[7][protagonist_pokemon.modifier[7]] * (1 / (modifierChart[6][ai_pokemon.modifier[6]] * move.evasion)), 1)
        move.accuracy, move.effect_accuracy = min(move.accuracy, 1), min(move.effect_accuracy, 1) if move.effect_type != "no_effect" else 0
        battle_move_execution.onWeatherCheck(battleground, move)

        UseAbility(protagonist, ai, protagonist_pokemon, ai_pokemon, battleground, move, abilityphase=2)
        UseAbility(ai, protagonist, ai_pokemon, protagonist_pokemon, battleground, move, abilityphase=3)

        move.damage = estimated_damage_calculation(protagonist, ai, protagonist_pokemon, ai_pokemon, move)
        # expected damage
        protagonist_move_score[index] = move.damage * move.accuracy

    incoming_move = list_of_moves[protagonist_pokemon.moveset[protagonist_move_score.index(max(protagonist_move_score))]]
    # count how many turns it takes for protagonist to faint ai
    surviving_turns = math.ceil(ai_pokemon.battle_stats[0] / max(1, max(protagonist_move_score)))  # upper bound
    # consider speed
    protagonist_speed = protagonist_pokemon.battle_stats[5] * 0.5 if protagonist_pokemon.status == "Paralysis" else protagonist_pokemon.battle_stats[5]
    ai_speed = ai_pokemon.battle_stats[5] * 0.5 if ai_pokemon.status == "Paralysis" else ai_pokemon.battle_stats[5]

    for index, move in enumerate(ai_pokemon.moveset):
        ai_pokemon.battle_stats = deepcopy(ai_stats)
        move = deepcopy(list_of_moves[move])
        makeshift_moveset.append(move)

        UseAbility(ai, protagonist, ai_pokemon, protagonist_pokemon, battleground, move, abilityphase=2)
        UseAbility(protagonist, ai, protagonist_pokemon, ai_pokemon, battleground, move, abilityphase=3)

        move.damage = estimated_damage_calculation(ai, protagonist, ai_pokemon, protagonist_pokemon, move)
        move.accuracy = min(move.accuracy * modifierChart[7][ai_pokemon.modifier[7]] * (1 / modifierChart[6][protagonist_pokemon.modifier[6]]), 1)

        move.accuracy, move.effect_accuracy = min(move.accuracy, 1), min(move.effect_accuracy, 1)
        move_damage[index] = move.damage

        try:
            turns = math.ceil(protagonist_pokemon.battle_stats[0] / move.damage)  # upper bound
        except ZeroDivisionError:
            turns = INFINITY
        turns = turns - 0.5 if ai_speed >= protagonist_speed else turns + 0.5
        if move.special_effect == "Charging":
            turns += move.charging
        defeating_turns[index] = turns

        # failed moves
        with suppress(KeyError):
            if ai_pokemon.disabled_moves[move.name] > 0:
                move_score[index], move_damage[index] = NEG_INF, NEG_INF
        if 'j' in move.flags and ai_pokemon.volatile_status["Turn"] > 1:
            move_score[index], move_damage[index] = NEG_INF, NEG_INF

        # first-turn priority moves must use (e.g. first impression / fake out)
        if 'j' in move.flags and ai_pokemon.volatile_status["Turn"] <= 1:
            # in case of type immunity
            if move.damage >= 0:
                return move

    least_defeating_turns = min(defeating_turns) if min(defeating_turns) != 0 else INFINITY
    if least_defeating_turns < surviving_turns:
        for index, move in enumerate(makeshift_moveset):
            if defeating_turns[index] == least_defeating_turns:
                # status condition move
                if "target_non_volatile" in move.effect_type and protagonist_pokemon.status == "Normal":
                    # ground and electric type immune to paralysis status moves
                    if move.special_effect == Paralysis:
                        if not ("Ground" in protagonist_pokemon.type or "Electric" in protagonist_pokemon.type):
                            move_score[index] += 7.5 * move.effect_accuracy * move.accuracy
                    # poison and steel type immune to poison
                    elif move.special_effect == Poison or move.special_effect == BadPoison:
                        if not ("Poison" in protagonist_pokemon.type or "Steel" in protagonist_pokemon.type):
                            move_score[index] += 5 * move.effect_accuracy * move.accuracy
                    elif move.special_effect == Burn:
                        move_score[index] += 10 * move.effect_accuracy if sum(
                            1 for moves in protagonist_pokemon.moveset if list_of_moves[moves].attack_type == "Physical") >= \
                                                                          sum(1 for moves in protagonist_pokemon.moveset if
                                                                              list_of_moves[moves].attack_type == "Special") \
                            else 5 * move.effect_accuracy
                    else:
                        move_score[index] += 10 * move.effect_accuracy * move.accuracy
                # volatile condition move
                elif "target_volatile" in move.effect_type:
                    if move.special_effect == Confused:
                        if protagonist_pokemon.volatile_status["Confused"] != 0:
                            move_score[index] += 7.5 * move.effect_accuracy * move.accuracy
                    elif move.special_effect == Flinch:
                        move_score[index] += 10 * move.effect_accuracy * move.accuracy if ai_speed > protagonist_speed else 0
                    else:
                        move_score[index] += 5 * move.effect_accuracy * move.accuracy
                # self buff move
                elif "self_modifier" in move.effect_type:
                    for i in range(len(ai_pokemon.modifier)):
                        special_effect = move.special_effect[move.effect_type.index("self_modifier")] if type(move.effect_type) is list else move.special_effect
                        move_score[index] += (6 - ai_pokemon.modifier[i]) * special_effect[i] * (5 / 6 if special_effect[i] > 0 else 1 / 3) \
                                             * move.effect_accuracy * move.accuracy
                # debuff move
                elif "opponent_modifier" in move.effect_type:
                    special_effect = move.special_effect[move.effect_type.index("opponent_modifier")] if type(move.effect_type) is list else move.special_effect
                    move_score[index] += sum(special_effect) * -5 * move.effect_accuracy * move.accuracy

                move_score[index] += 100 if move.priority > 0 else 0
                move_score[index] += (10 * (min(protagonist_pokemon.battle_stats[0], move_damage[index]) / protagonist_pokemon.hp) ** 2) * move.accuracy
                move_score[index] += 2 if move_damage[index] == max(move_damage) else 0


    # if it takes more turns for ai to defeat protagonist, then ai should switch unless there are better moves
    #  e.g. considering additional effects or status moves
    elif least_defeating_turns >= surviving_turns:
        for index, move in enumerate(makeshift_moveset):
            # always protect
            if "user_protection" in move.effect_type and ai_pokemon.protection[1] <= 0:
                move_score[index] += 50
            # recovery moves
            elif "self_heal" in move.effect_type:
                if math.floor(ai_pokemon.hp * move.special_effect > max(protagonist_move_score)):
                    move_score[index] += 50  # avoid recursionerror in ai simulation
            # team buff moves
            if "self_team_buff" in move.effect_type:
                if ai.in_battle_effects[move.name] <= 0:
                    move_score[index] += 10 * sum(1 for pokemon in protagonist.team if pokemon.status != "Fainted")
            # entry hazard
            elif "entry_hazard" in move.effect_type:
                if protagonist.entry_hazard[move.special_effect] < entry_hazard_maximum_usage[move.special_effect]:
                    move_score[index] += 10 * sum(1 for pokemon in protagonist.team if pokemon.status != "Fainted")  # max 50
            # clear entry hazard
            elif "clear_entry_hazard" in move.effect_type:
                move_score[index] += 20 * sum(1 for hazard in ai.entry_hazard.values() if hazard > 0)  # max 50
            # status condition move
            elif "target_non_volatile" in move.effect_type and protagonist_pokemon.status == "Normal":
                # ground and electric type immune to paralysis status moves
                if move.special_effect == Paralysis:
                    if not ("Ground" in protagonist_pokemon.type or "Electric" in protagonist_pokemon.type):
                        move_score[index] += 10 * move.effect_accuracy * move.accuracy
                # poison and steel type immune to poison
                elif move.special_effect == Poison or move.special_effect == BadPoison:
                    if not ("Poison" in protagonist_pokemon.type or "Steel" in protagonist_pokemon.type):
                        move_score[index] += 10 * move.effect_accuracy * move.accuracy
                elif move.special_effect == Burn:
                    move_score[index] += 5 * move.effect_accuracy if sum(
                        1 for moves in protagonist_pokemon.moveset if list_of_moves[moves].attack_type == "Physical") >= \
                                                                     sum(1 for moves in protagonist_pokemon.moveset if
                                                                         list_of_moves[moves].attack_type == "Special") \
                        else 2 * move.effect_accuracy
                else:
                    move_score[index] += 20 * move.effect_accuracy * move.accuracy
            # volatile condition move
            elif "target_volatile" in move.effect_type:
                if move.special_effect == Confused:
                    if protagonist_pokemon.volatile_status["Confused"] != 0:
                        move_score[index] += 10 * move.effect_accuracy * move.accuracy
                elif move.special_effect == Flinch:
                    move_score[index] += 20 * move.effect_accuracy * move.accuracy if ai_speed > protagonist_speed else 0
                else:
                    move_score[index] += 10 * move.effect_accuracy * move.accuracy
            # self buff move
            elif "self_modifier" in move.effect_type:
                special_effect = move.special_effect[move.effect_type.index("self_modifier")] if type(move.effect_type) is list else move.special_effect
                for i in range(len(ai_pokemon.modifier)):
                    move_score[index] += (6 - ai_pokemon.modifier[i]) * special_effect[i] * (1 / 2 if special_effect[i] > 0 else 1 / 6) \
                                         * move.effect_accuracy * move.accuracy
            # debuff move
            elif "opponent_modifier" in move.effect_type:
                special_effect = move.special_effect[move.effect_type.index("opponent_modifier")] if type(move.effect_type) is list else move.special_effect
                move_score[index] += sum(special_effect) * -5 * move.effect_accuracy * move.accuracy

            # damage calculation
            move_score[index] += pow(7 * min(1, min(protagonist_pokemon.battle_stats[0], move_damage[index]) / protagonist_pokemon.hp), 1.7) * move.accuracy
            move_score[index] += sum(ai_pokemon.modifier) * 2
            move_score[index] -= sum(1 for status in ai_pokemon.volatile_status if ai_pokemon.volatile_status[status] > 0) * 5
            move_score[index] -= pow(5 * min(1, min(ai_pokemon.battle_stats[0], max(protagonist_move_score)) / ai_pokemon.hp), 1.7)
            move_score[index] -= pow(3 * ((move_damage[index] * move.recoil + ai_pokemon.hp * move.deduct) / protagonist_pokemon.hp), 2)

        if max(move_score) < 0 or move_score.index(max(move_score)) == 0:
            if sum(1 for pokemon in ai.team if pokemon.status != "Fainted") != 1:
                # check if anyone in the team takes less damage
                for index, pokemon in enumerate(ai.team):
                    if pokemon.status == "Fainted":
                        continue
                    type_effectiveness = 0
                    for y in range(len(protagonist_pokemon.type)):
                        type_effectiveness = max(math.prod(typeChart[protagonist_pokemon.type[y]][pokemon.type[x]] for x in range(len(pokemon.type))), type_effectiveness)
                    if pokemon != ai.team[0]:
                        incoming_move.damage = estimated_damage_calculation(protagonist, ai, protagonist_pokemon, pokemon,
                                                                            incoming_move) * incoming_move.accuracy * type_effectiveness
                        if incoming_move.damage < incoming_move_max_damage:
                            incoming_move_max_damage = incoming_move.damage
                            best_pokemon_index = index
                    print(f"{CBOLD}{pokemon.name}: {incoming_move_max_damage}{CEND}")

                # if a better pokemon is found, consider switching
                if incoming_move_max_damage < max(protagonist_move_score):

                    print("")
                    for index, move in enumerate(makeshift_moveset):
                        print(f"{move.name} || Score: {move_score[index]} / Damage: {move_damage[index]}")
                    print("")

                    ai.position_change = ai_switching_mechanism(protagonist, ai, battleground, True, False, candidate=best_pokemon_index)
                    # if confirmed switched, then use Switching
                    # prioritize switching moves
                    for index, move in enumerate(makeshift_moveset):
                        if "switching" in move.effect_type and move.name != "Baton Pass":
                            return list_of_moves[ai.team[0].moveset[index]]

                    if ai.position_change != 0:
                        return list_of_moves[ai.team[0].moveset[0]]  # switching
    print("")
    for index, move in enumerate(makeshift_moveset):
        print(f"{move.name} || Score: {move_score[index]} / Damage: {move_damage[index]}")
    print("")

    # if there are moves worse than 0 (literally do nothing), then consider moves with damage (even if they are worse moves)
    # if literlly nothing can be done or switched, then random (equivalent to surrender)
    if move_score.index(max(move_score)) == 0:
        return list_of_moves[ai.team[0].moveset[move_damage.index(max(move_damage))]] if max(move_damage) != 0 else list_of_moves[
            ai.team[0].moveset[random.randint(1, len(ai.team[0].moveset) - 1)]]
    return list_of_moves[ai.team[0].moveset[move_score.index(max(move_score))]]


def ai_switching_mechanism(protagonist, ai, battleground, recall=False, forced_switch=False, candidate=0):
    if (not forced_switch) and recall:
        if ai.team[0].volatile_status['Binding'] > 0 or ai.team[0].volatile_status['Trapped'] > 0:
            if 'Ghost' not in ai.team[0].type:
                print("The pokemon cannot be switched out!")
                return 0

    if ai.team[0].status == "Fainted" or recall:
        if candidate != 0:
            return candidate

        with suppress(IndexError):
            net_damage = []
            pokemon_index = [x for x in range(len(ai.team)) if ai.team[x].status != "Fainted"]
            available_pokemon = [mon for mon in ai.team if mon.status != "Fainted"]
            # AI will consider your moveset and its pokemon moveset, calculate the net damage and select the best pokemon
            for pokemon in available_pokemon:
                print(f"{CRED2}{CBOLD}{pokemon.name} {pokemon.nominal_base_stats} {pokemon.iv} {pokemon.moveset}{CEND}")
            for pokemon in available_pokemon:
                estimated_incoming_damage, estimated_outgoing_damage = 0, 0
                for protagonist_move in protagonist.team[0].moveset:
                    protagonist_move = list_of_moves[protagonist_move]
                    estimated_incoming_damage = max(estimated_damage_calculation(protagonist, ai, protagonist.team[0], pokemon, protagonist_move),
                                                    estimated_incoming_damage)

                for ai_move in pokemon.moveset:
                    ai_move = list_of_moves[ai_move]
                    damage = estimated_damage_calculation(ai, protagonist, pokemon, protagonist.team[0], ai_move)
                    estimated_outgoing_damage = max(damage, estimated_outgoing_damage)
                    if ai_move.priority > 0 and damage >= protagonist.team[0].battle_stats[0]:
                        estimated_outgoing_damage += 200
                    elif pokemon.battle_stats[5] > protagonist.team[0].battle_stats[5] and damage >= protagonist.team[0].battle_stats[0]:
                        estimated_outgoing_damage += 50

                # sticky web
                estimated_speed = pokemon.battle_stats[5] * 2 / 3 if ai.entry_hazard['Sticky Web'] > 0 else pokemon.battle_stats[5]
                # stealth rock & spikes
                stealth_rock_damage = math.prod([typeChart["Rock"][x] for x in pokemon.type]) * pokemon.hp * 0.125
                spikes_damage = {0: 0, 1: 1 / 8, 2: 1 / 6, 3: 1 / 4}
                estimated_incoming_damage += stealth_rock_damage * ai.entry_hazard["Stealth Rock"] + pokemon.hp * spikes_damage[
                    ai.entry_hazard["Spikes"]]
                net_damage.append(estimated_outgoing_damage - estimated_incoming_damage)

            try:
                switched_pokemon = pokemon_index[net_damage.index(max(net_damage))]
            except:
                battle_win_condition.check_win_or_lose(protagonist, ai, protagonist.team, ai.team, battleground)

            else:
                # second best pokemon
                if forced_switch and switched_pokemon == 0:
                    switched_pokemon = pokemon_index[net_damage.index(max(net_damage[1:5]))]
                print(f"Estimated Net Damage: {net_damage}, Switched Pokemon: {switched_pokemon}")

                return switched_pokemon
    return 0
