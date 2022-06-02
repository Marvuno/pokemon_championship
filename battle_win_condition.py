import random
import math
from contextlib import suppress
from copy import deepcopy
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
from damage_calculation import *
from move_additional_effect import *
from constants import *
from ai import *
from switching import *
from music import *
from game_system import *
import game_procedure
from moves import *
import battle_checklist
import os


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
            music(audio='music/victory.mp3', loop=False)
    elif player_side:
        battleground.battle_continuation = False
        print("Opponent emerges victorious. You have lost.")
        competitor.stage += 1
    elif opponent_side:
        battleground.battle_continuation = False
        print("Congratulations! You have won.")
        music(audio='music/victory.mp3', loop=False)
        protagonist.stage += 1

    if not battleground.battle_continuation:
        protagonist.result = sum(1 for pokemon in opponent_team if pokemon.status == "Fainted")
        competitor.result = sum(1 for pokemon in player_team if pokemon.status == "Fainted")
        protagonist.score += protagonist.result - competitor.result
        competitor.score += competitor.result - protagonist.result
        choose_pokemon(protagonist, competitor, battleground)
        end_battle(protagonist, competitor, player_team, opponent_team, battleground)


# battle ended
# reset every in-battle state
def end_battle(protagonist, competitor, player_team, opponent_team, battleground):
    for pokemon in player_team:
        pokemon.modifier = [0] * 9
        if pokemon.status == "Fainted":
            pokemon.name = pokemon.name.removesuffix(" (Fainted)")
        pokemon.status = "Normal"
        pokemon.volatile_status = dict.fromkeys(pokemon.volatile_status.keys(), 0)
        protagonist.entry_hazard = dict.fromkeys(protagonist.entry_hazard.keys(), 0)
        protagonist.in_battle_effects = dict.fromkeys(protagonist.in_battle_effects.keys(), 0)
        pokemon.protection = [0, 0]
        pokemon.charging = ["", "", 0]
        pokemon.moveset = pokemon.moveset[1:5]
        pokemon.previous_move = ""
        pokemon.disabled_moves = {}
        pokemon.disguise, pokemon.transform = False, False

    if battleground.verbose:
        print(f"{protagonist.name}: {protagonist.result} || {competitor.name}: {competitor.result}")
    else:
        game_procedure.round_end(GameSystem.stage)
        GameSystem.stage += 1


def choose_pokemon(protagonist, opponent, battleground):
    choice, obtained_pokemon, thrown_pokemon = None, -1, -1
    current_pokemon = [pokemon.name.removesuffix(' (Fainted)') for pokemon in protagonist.team]
    if not battleground.verbose:
        if (len(protagonist.team) + len(protagonist.unused_team)) < ROUND_LIMIT[GameSystem.stage + 1] or len(protagonist.team) == MAX_POKEMON:
            # win the round
            if protagonist.stage > opponent.stage:
                print(f"{CGREEN2}{CBOLD}Your Team: {[pokemon.name.removesuffix(' (Fainted)') for pokemon in protagonist.team]}\n"
                      f"{CRED2}Opponent Team: {[pokemon.name.removesuffix(' (Fainted)') for pokemon in opponent.team]}{CEND}")
                # not yet full team, can get extra pokemon
                if (len(protagonist.team) + len(protagonist.unused_team)) != MAX_POKEMON:
                    while choice != "Y" and choice != "N":
                        choice = input(f"Input Y if you want to take from the opponent, and N to get a random pokemon from the organizer (No going back when "
                                       f"you have chosen). ").upper()

                        if choice == "Y":
                            while not (0 <= obtained_pokemon < len(opponent.team)):
                                with suppress(IndexError, ValueError):
                                    obtained_pokemon = int(input(f"You may take one pokemon from the opponent:\n"
                                                                 f"{CRED2}{CBOLD}{[(index, pokemon.name.removesuffix(' (Fainted)')) for index, pokemon in enumerate(opponent.team)]}{CEND}\n"
                                                                 f"--> "))
                                    protagonist.team.append(opponent.team[obtained_pokemon])
                        elif choice == "N":
                            defeating_tier_list = {'Low': 'Medium', 'Intermediate': 'Medium', 'Advanced': 'High', 'Elite': 'Very High', 'Champion': 'Custom'}
                            pokemon_availability_list = [pokemon for pokemon in list_of_pokemon if
                                                         list_of_pokemon[pokemon].tier == defeating_tier_list[opponent.level] and pokemon not in current_pokemon]
                            obtained_pokemon = random.choice(pokemon_availability_list)
                            obtained_pokemon = deepcopy(list_of_pokemon[obtained_pokemon])
                            obtained_pokemon.iv = [random.randint(0, 31) for _ in range(6)]
                            obtained_pokemon.nominal_base_stats = list(map(operator.add, obtained_pokemon.base_stats, obtained_pokemon.iv))
                            obtained_pokemon.ability = random.choice(obtained_pokemon.ability)
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
                            while not (0 <= obtained_pokemon < len(opponent.team) and (0 <= thrown_pokemon < len(protagonist.team))):
                                with suppress(IndexError, ValueError):
                                    thrown_pokemon = int(input(f"Choose the pokemon you don't want on your team:\n"
                                                               f"{CGREEN2}{CBOLD}{[(index, pokemon.name.removesuffix(' (Fainted)')) for index, pokemon in enumerate(protagonist.team)]}{CEND}\n"
                                                               f"--> "))
                                    obtained_pokemon = int(input(f"Take the pokemon you want on the other team:\n"
                                                                 f"{CRED2}{CBOLD}{[(index, pokemon.name.removesuffix(' (Fainted)')) for index, pokemon in enumerate(opponent.team)]}{CEND}\n"
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
                    obtained_pokemon.iv = [random.randint(0, 31) for _ in range(6)]
                    obtained_pokemon.nominal_base_stats = list(map(operator.add, obtained_pokemon.base_stats, obtained_pokemon.iv))
                    obtained_pokemon.ability = random.choice(obtained_pokemon.ability)
                    obtained_pokemon.moveset = random.sample(obtained_pokemon.moveset, min(4, len(obtained_pokemon.moveset)))
                    obtained_pokemon.moveset = ["Switching"] + obtained_pokemon.moveset
                    print(f"You have obtained {CVIOLET2}{CBOLD}{obtained_pokemon.name}{CEND} from the organizer.")
                    protagonist.team.append(obtained_pokemon)
        else:
            if (len(protagonist.team) + len(protagonist.unused_team)) < MAX_POKEMON:
                print("You have enough Pokemon for the next round. No free gift for you.")
            for mon in protagonist.unused_team:
                protagonist.team.append(mon)
            protagonist.unused_team = []
        input("Press any key to continue.")
        os.system('cls')
