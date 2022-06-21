import random
import math
from contextlib import suppress
from copy import deepcopy
import os

from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Data.pokemon import *
from Scripts.Data.competitors import *
from Scripts.Battle.weather import *
from Scripts.Battle.move_additional_effect import *
from Scripts.Battle.constants import *
from Scripts.Game.game_system import *
from Scripts.Game.single_elimination_bracket import *


def check_win_or_lose(protagonist, competitor, player_team, opponent_team, battleground):
    player_side = True if len(player_team) == sum(1 for pokemon in player_team if pokemon.status == "Fainted") else False
    opponent_side = True if len(opponent_team) == sum(1 for pokemon in opponent_team if pokemon.status == "Fainted") else False

    if player_side and opponent_side:
        battleground.battle_continuation = False
        # tiebreaks
        if protagonist.strength > competitor.strength:
            print("Opponent emerges victorious. You have lost.")
            competitor.stage += 1
        else:
            protagonist.stage += 1
            print("Congratulations! You have won.")
            music(audio='Assets/music/victory.mp3', loop=False)
    elif player_side:
        battleground.battle_continuation = False
        print("Opponent emerges victorious. You have lost.")
        competitor.stage += 1
    elif opponent_side:
        battleground.battle_continuation = False
        print("Congratulations! You have won.")
        music(audio='Assets/music/victory.mp3', loop=False)
        protagonist.stage += 1

    if not battleground.battle_continuation:
        protagonist.result = sum(1 for pokemon in opponent_team if pokemon.status == "Fainted")
        competitor.result = sum(1 for pokemon in player_team if pokemon.status == "Fainted")
        protagonist.score += protagonist.result - competitor.result
        competitor.score += competitor.result - protagonist.result
        print(weather_del[battleground.weather_effect])
        choose_pokemon(protagonist, competitor, battleground)
        end_battle(protagonist, competitor, player_team, opponent_team, battleground)


# battle ended
# reset every in-battle state
def end_battle(protagonist, competitor, player_team, opponent_team, battleground):
    if battleground.verbose:
        for pokemon in player_team:
            pokemon.modifier = [0] * 9
            pokemon.status = "Normal"
            pokemon.volatile_status = dict.fromkeys(pokemon.volatile_status.keys(), 0)
            pokemon.protection = [0, 0]
            pokemon.charging = ["", "", 0]
            pokemon.moveset = pokemon.moveset[1:5]
            pokemon.move_order = []
            pokemon.previous_move = None
            pokemon.disabled_moves = {}
            pokemon.disguise, pokemon.transform = False, False
            pokemon.name, pokemon.ability, pokemon.type = pokemon.default_name, pokemon.default_ability, pokemon.default_type

        for pokemon in opponent_team:
            pokemon.modifier = [0] * 9
            pokemon.status = "Normal"
            pokemon.volatile_status = dict.fromkeys(pokemon.volatile_status.keys(), 0)
            pokemon.protection = [0, 0]
            pokemon.charging = ["", "", 0]
            pokemon.moveset = pokemon.moveset[1:5]
            pokemon.move_order = []
            pokemon.previous_move = None
            pokemon.disabled_moves = {}
            pokemon.disguise, pokemon.transform = False, False
            pokemon.name, pokemon.ability, pokemon.type = pokemon.default_name, pokemon.default_ability, pokemon.default_type

        protagonist.entry_hazard = dict.fromkeys(protagonist.entry_hazard.keys(), 0)
        protagonist.in_battle_effects = dict.fromkeys(protagonist.in_battle_effects.keys(), 0)
        competitor.entry_hazard = dict.fromkeys(competitor.entry_hazard.keys(), 0)
        competitor.in_battle_effects = dict.fromkeys(competitor.in_battle_effects.keys(), 0)
    else:
        for pokemon in player_team:
            pokemon.modifier = [0] * 9
            pokemon.status = "Normal"
            pokemon.volatile_status = dict.fromkeys(pokemon.volatile_status.keys(), 0)
            protagonist.entry_hazard = dict.fromkeys(protagonist.entry_hazard.keys(), 0)
            protagonist.in_battle_effects = dict.fromkeys(protagonist.in_battle_effects.keys(), 0)
            pokemon.protection = [0, 0]
            pokemon.charging = ["", "", 0]
            pokemon.moveset = pokemon.moveset[1:5]
            pokemon.move_order = []
            pokemon.previous_move = None
            pokemon.disabled_moves = {}
            pokemon.disguise, pokemon.transform = False, False
            with suppress(AttributeError):
                pokemon.name, pokemon.ability, pokemon.type = pokemon.default_name, pokemon.default_ability, pokemon.default_type

        for mon in protagonist.unused_team:
            protagonist.team.append(mon)
        protagonist.unused_team = []

        input("Press any key to continue.")
        os.system('cls' if os.name == 'nt' else 'clear')
        round_end(GameSystem.stage)
        GameSystem.stage += 1


def choose_pokemon(protagonist, opponent, battleground):
    choice, obtained_pokemon, thrown_pokemon = None, -1, -1
    current_pokemon = [pokemon.name for pokemon in protagonist.team]
    if not battleground.verbose:
        if (len(protagonist.team) + len(protagonist.unused_team)) < ROUND_LIMIT[GameSystem.stage + 1] or len(protagonist.team) == MAX_POKEMON:
            # win the round
            if protagonist.stage > opponent.stage:
                print(f"{CGREEN2}{CBOLD}Your Team: {[pokemon.name for pokemon in protagonist.team]}\n"
                      f"{CRED2}Opponent Team: {[pokemon.name for pokemon in opponent.team]}{CEND}")
                # not yet full team, can get extra pokemon
                if (len(protagonist.team) + len(protagonist.unused_team)) != MAX_POKEMON:
                    while choice != "Y" and choice != "N":
                        choice = input(f"Input Y if you want to take from the opponent, and N to get a random pokemon from the organizer (No going back when "
                                       f"you have chosen). ").upper()

                        if choice == "Y":
                            # pokemon info
                            print()
                            for i, pokemon in enumerate(opponent.team):
                                print(f"{CBOLD}ID: {pokemon.id} || Name: {pokemon.name} || Type: {pokemon.type}")
                                print(f"Ability: {pokemon.ability} || Total Stats: {pokemon.total_stats}({pokemon.total_iv})")
                                print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}" for x in range(len(pokemon.nominal_base_stats))])
                                print(f"Moveset: {pokemon.moveset}{CEND}\n")
                            while not (0 <= obtained_pokemon < len(opponent.team)):
                                with suppress(IndexError, ValueError):
                                    obtained_pokemon = int(input(f"You may take one pokemon from the opponent:\n"
                                                                 f"{CRED2}{CBOLD}{[(index, pokemon.name) for index, pokemon in enumerate(opponent.team)]}{CEND}\n"
                                                                 f"--> "))
                                    protagonist.team.append(opponent.team[obtained_pokemon])
                        elif choice == "N":
                            defeating_tier_list = {'Low': 'Medium', 'Intermediate': 'Medium', 'Advanced': 'High', 'Elite': 'Very High', 'Champion': 'Ultra High'}
                            pokemon_availability_list = [pokemon for pokemon in list_of_pokemon if
                                                         list_of_pokemon[pokemon].tier == defeating_tier_list[opponent.level] and pokemon not in current_pokemon]
                            obtained_pokemon = random.choice(pokemon_availability_list)
                            obtained_pokemon = deepcopy(list_of_pokemon[obtained_pokemon])
                            obtained_pokemon.iv = [random.randint(min(31, int(protagonist.strength / 250 * 31)), 31) for _ in range(6)]
                            obtained_pokemon.total_iv = sum(obtained_pokemon.iv)
                            obtained_pokemon.nominal_base_stats = list(map(operator.add, obtained_pokemon.base_stats, obtained_pokemon.iv))
                            obtained_pokemon.total_base_stats = sum(obtained_pokemon.base_stats)
                            obtained_pokemon.ability = [random.choice(obtained_pokemon.ability)]
                            obtained_pokemon.moveset = random.sample(obtained_pokemon.moveset, min(4, len(obtained_pokemon.moveset)))
                            obtained_pokemon.moveset = ["Switching"] + obtained_pokemon.moveset
                            print(f"You have obtained {CVIOLET2}{CBOLD}{obtained_pokemon.name}{CEND} from the organizer.")
                            protagonist.team.append(obtained_pokemon)
                # swap pokemon
                else:
                    # when full team
                    while choice != "Y" and choice != "N":
                        choice = input(f"Input Y if you want to swap, and N otherwise (No going back when you have chosen). ").upper()

                        if choice == "Y":
                            # pokemon info
                            print()
                            # player team
                            for i, pokemon in enumerate(protagonist.team):
                                print(f"{CGREEN2+CBOLD}ID: {pokemon.id} || Name: {pokemon.name} || Type: {pokemon.type}")
                                print(f"Ability: {pokemon.ability} || Total Stats: {pokemon.total_stats}({pokemon.total_iv})")
                                print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}" for x in range(len(pokemon.nominal_base_stats))])
                                print(f"Moveset: {pokemon.moveset}{CEND}\n")
                            # enemy team
                            for i, pokemon in enumerate(opponent.team):
                                print(f"{CRED2+CBOLD}ID: {pokemon.id} || Name: {pokemon.name} || Type: {pokemon.type}")
                                print(f"Ability: {pokemon.ability} || Total Stats: {pokemon.total_stats}({pokemon.total_iv})")
                                print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}" for x in range(len(pokemon.nominal_base_stats))])
                                print(f"Moveset: {pokemon.moveset}{CEND}\n")
                            while not (0 <= obtained_pokemon < len(opponent.team) and (0 <= thrown_pokemon < len(protagonist.team))):
                                with suppress(IndexError, ValueError):
                                    thrown_pokemon = int(input(f"Choose the pokemon you don't want on your team:\n"
                                                               f"{CGREEN2}{CBOLD}{[(index, pokemon.name) for index, pokemon in enumerate(protagonist.team)]}{CEND}\n"
                                                               f"--> "))
                                    obtained_pokemon = int(input(f"Take the pokemon you want on the other team:\n"
                                                                 f"{CRED2}{CBOLD}{[(index, pokemon.name) for index, pokemon in enumerate(opponent.team)]}{CEND}\n"
                                                                 f"--> "))
                                    protagonist.team[thrown_pokemon] = opponent.team[obtained_pokemon]
            # lose the round
            else:
                # when lost
                if len(protagonist.team) != MAX_POKEMON:
                    pokemon_availability_list = [pokemon for pokemon in list_of_pokemon if
                                                 list_of_pokemon[pokemon].tier in ['Very Low', 'Low', 'Medium'] and pokemon not in current_pokemon]
                    obtained_pokemon = random.choice(pokemon_availability_list)
                    obtained_pokemon = deepcopy(list_of_pokemon[obtained_pokemon])
                    obtained_pokemon.iv = [random.randint(min(31, int(protagonist.strength / 250 * 31)), 31) for _ in range(6)]
                    obtained_pokemon.total_iv = sum(obtained_pokemon.iv)
                    obtained_pokemon.nominal_base_stats = list(map(operator.add, obtained_pokemon.base_stats, obtained_pokemon.iv))
                    obtained_pokemon.ability = [random.choice(obtained_pokemon.ability)]
                    obtained_pokemon.moveset = random.sample(obtained_pokemon.moveset, min(4, len(obtained_pokemon.moveset)))
                    obtained_pokemon.moveset = ["Switching"] + obtained_pokemon.moveset
                    print(f"You have obtained {CVIOLET2}{CBOLD}{obtained_pokemon.name}{CEND} from the organizer.")
                    protagonist.team.append(obtained_pokemon)


def round_end(stage):
    colors = {"": CWHITE2, "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}

    def result_announcement(victor, loser, main):
        level_order = {"Low": 1, "Intermediate": 2, "Advanced": 3, "Elite": 4, "Champion": 5, "Protagonist": 6}
        victor_crown, loser_crown = f' |{victor.championship}|' if victor.championship > 0 else '', f' |{loser.championship}|' if loser.championship > 0 else ''
        victor_bold, loser_bold = CBOLD if victor.championship > 0 else '', CBOLD if loser.championship > 0 else ''
        print(colors[victor.color] + victor_bold + EntryBox(victor.id, f"{victor.nickname} [{victor.strength}]{victor_crown}{' !!' if level_order[victor.level] < level_order[loser.level] else ''}", victor.stage - 1, ROUND_LIMIT[stage]).structure + CEND)
        if main:  # the protagonist battle
            print(CGREY + loser_bold + EntryBox(loser.id, f"{loser.nickname} [{loser.strength}]{loser_crown}",
                                   loser.stage - 1, loser.result).structure, "\n" + CEND)
        else:  # others' battle
            result = ROUND_LIMIT[stage] * loser.strength / (victor.strength + loser.strength)
            result = int(min(round(result * random.uniform(1.25, 1.75), 0), ROUND_LIMIT[stage] - 1))
            victor.score += ROUND_LIMIT[stage] - result
            loser.score += result - ROUND_LIMIT[stage]
            print(CGREY + loser_bold + EntryBox(loser.id, f"{loser.nickname} [{loser.strength}]{loser_crown}", loser.stage - 1, result).structure, "\n" + CEND)

    for i in range(0, int(math.pow(2, 5)), 2):
        one, two = list_of_competitors[GameSystem.participants[i]], list_of_competitors[GameSystem.participants[i + 1]]
        main = True
        victor = i if one.result > two.result else i + 1
        loser = i + 1 if victor == i else i
        if not (one.main or two.main):
            victor = i if random.random() < one.strength / (one.strength + two.strength) else i + 1
            loser = i + 1 if victor == i else i

            list_of_competitors[GameSystem.participants[victor]].stage += 1
            main = False
        result_announcement(list_of_competitors[GameSystem.participants[victor]],
                            list_of_competitors[GameSystem.participants[loser]], main)

        # save opponent in-game record
        list_of_competitors[GameSystem.participants[victor]].opponent.append(list_of_competitors[GameSystem.participants[loser]])
        list_of_competitors[GameSystem.participants[loser]].opponent.append(list_of_competitors[GameSystem.participants[victor]])
        list_of_competitors[GameSystem.participants[victor]].win_order.append(1)
        list_of_competitors[GameSystem.participants[loser]].win_order.append(0)
        # save opponent match history record
        list_of_competitors[GameSystem.participants[victor]].opponent_history[GameSystem.participants[loser]][0] += 1
        list_of_competitors[GameSystem.participants[loser]].opponent_history[GameSystem.participants[victor]][1] += 1
