import random
import pickle
from contextlib import suppress
from game_procedure import *
from game_system import *
from text_color import *
from competitors import *
from single_elimination_bracket import *
from copy import deepcopy
from custom_team import *
from constants import *
from ai import *
import sys


def before_battle_option(protagonist, opponent):
    option = None
    choices = {0: proceed_to_battle, 1: view_pokemon, 2: switch_order, 3: about_opponent, 4: check_history, 5: quit_game}
    text = "What do you want to do?\n" \
           "0: Battle || 1: View My Pokemon || 2: Switch Pokemon Order || 3: About Opponent || 4: Check History || 5: Quit Game\n" \
           "--> "
    while option != 0:
        with suppress(ValueError, KeyError):
            print("")
            option = int(input(text))
            print("")
            choices[option](protagonist, opponent)
            if option == 3:
                del choices[3]
                text = f"What do you want to do?\n" \
                       f"0: Battle || 1: View My Pokemon || 2: Switch Pokemon Order || {CGREY}3: About Opponent{CEND} || 4: Check History || 5: Quit Game\n" \
                       f"--> "


def proceed_to_battle(protagonist, opponent):
    print(f"{CBOLD}Round {GameSystem.stage}{CEND}")
    print(f"{CWHITE2}{CBOLD}{protagonist.name} [{protagonist.strength}] VS {opponent.name} [{opponent.strength}]{CEND}")
    print(f"{CWHITE2}{CBOLD}This is a {ROUND_LIMIT[GameSystem.stage]}vs{ROUND_LIMIT[GameSystem.stage]} battle.{CEND}")


def view_pokemon(protagonist, opponent):
    statistics = {0: "HP", 1: "Atk", 2: "Def", 3: "SpA", 4: "SpDef", 5: "Speed"}
    for i, pokemon in enumerate(protagonist.team):
        print(f"{CBEIGE+CBOLD if i % 2 == 0 else CBOLD}ID: {pokemon.id} || Name: {pokemon.name} || Type: {pokemon.type}")
        print(f"Ability: {pokemon.ability} || Total Stats: {pokemon.total_stats}({pokemon.total_iv})")
        print("Base Stats:", [f"{statistics[x]}: {pokemon.nominal_base_stats[x]}({pokemon.iv[x]})" for x in range(6)])
        print(f"Moveset: {pokemon.moveset}{CEND}\n")


def switch_order(protagonist, opponent):
    swap_pokemon_order = 0
    while not (1 <= swap_pokemon_order < len(protagonist.team)):
        with suppress(ValueError, IndexError):
            swap_pokemon_order = int(input(f'Which pokemon would you like to swap to be the first? Input 9 if you do not want to swap. '
                                           f'{[(index, pokemon.name) for index, pokemon in enumerate(protagonist.team)]} '))
            if swap_pokemon_order == 9:
                break
            else:
                protagonist.team[0], protagonist.team[swap_pokemon_order] = protagonist.team[swap_pokemon_order], protagonist.team[0]
                print(f'New Order: {CVIOLET2}{CBOLD}{[(index, pokemon.name) for index, pokemon in enumerate(protagonist.team)]}{CEND}\n')


def about_opponent(protagonist, opponent):
    print(f"{CBOLD}{opponent.name} | Tier: {opponent.level}\n{CYELLOW}{opponent.desc}\n{CEND}")
    print(f"Before the match begins, you approach your opponent {opponent.name} and introduce yourself.\nAfter a delightful chitchat...")
    # illuminate ability increases prob. ten-fold to obtain information
    prob = protagonist.strength / (opponent.strength + protagonist.strength)
    special_ability = {"Illuminate": 10, "Pressure": 100}
    for pokemon in protagonist.team:
        for ability in pokemon.ability:
            if ability in special_ability.keys():
                prob *= special_ability[ability]  # stackable
    if random.random() <= prob:
        revealed_pokemon = opponent.team[0]
        print(f"You have found that {opponent.name} will be using {CVIOLET2}{CBOLD}{revealed_pokemon.name}{CEND} as the 1st Pokemon for the next round!")
        if random.random() <= 0.5:
            print(f"Not only that, but you found that {CVIOLET2}{CBOLD}{revealed_pokemon.name}{CEND} has the moveset {CVIOLET2}{CBOLD}{revealed_pokemon.moveset}{CEND}!!")
    else:
        print("Unfortunately, you fail to obtain any useful information.")


def check_history(protagonist, opponent):
    colors = {"": "", "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}
    print(f"{CBOLD}{protagonist.name} {protagonist.opponent_history[opponent.name][0]} : {protagonist.opponent_history[opponent.name][1]} {opponent.name}{CEND}")
    print(f"\nYou have participated the Pokemon Championship for {protagonist.participation} time(s), with {protagonist.championship} World Champion title(s).")
    for i in range(len(protagonist.opponent)):
        print(f"{colors[protagonist.opponent[i].color]}{protagonist.opponent[i].name}: {'Win' if protagonist.win_order[i] == 1 else 'Lose'}{CEND}")
    print(f"\nYour opponent {opponent.name} has participated the Pokemon Championship for {opponent.participation} time(s), with {opponent.championship} World Champion title(s).")
    for i in range(len(opponent.opponent)):
        print(f"{colors[opponent.opponent[i].color]}{opponent.opponent[i].name}: {'Win' if opponent.win_order[i] == 1 else 'Lose'}{CEND}")
    confirmation = input("\nWanna know the Pokemon Championship history? Press Y to confirm: ").upper()
    if confirmation == 'Y':
        print(f"\nYour Pokemon Championship history: ")
        for parti, hist in protagonist.history.items():
            print(f"#{parti + 1}: Rank {hist[1]} | Ratings {hist[2]}")
        print(f"\nYour opponent's Pokemon Championship history: ")
        for parti, hist in opponent.history.items():
            print(f"#{parti + 1}: Rank {hist[1]}")
        print(f"\nThe Champion of the Pokemon Championship: ")
        for parti, hist in protagonist.history.items():
            print(f"#{parti + 1}: {hist[0]}")


def quit_game(protagonist, opponent):
    elo_rating()
    save_game()
    sys.exit()


def team_selection(protagonist):
    # exclusive to player
    # select pokemon when there is too many
    unused_list = set()
    if len(protagonist.team) - ROUND_LIMIT[GameSystem.stage] > 0:
        print(f"You have more Pokemon than needed for this round! Select {len(protagonist.team) - ROUND_LIMIT[GameSystem.stage]} "
              f"Pokemon you DO NOT need this round:")
        for pokemon in protagonist.team:
            print(f"\n{CBOLD}{pokemon.name}:")
            print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}({pokemon.iv[x]})" for x in range(6)])
            print(f"Ability: {pokemon.ability} || Moveset: {pokemon.moveset}{CEND}")
        while len(unused_list) != len(protagonist.team) - ROUND_LIMIT[GameSystem.stage]:
            print(f"\n{[(index, pokemon.name) for index, pokemon in enumerate(protagonist.team)]}")
            with suppress(KeyError, ValueError, IndexError):
                unused = int(input(f"Select the Pokemon you DO NOT need this round: "))
                unused_list.add(unused)
        unused_list = sorted(unused_list, reverse=True)
        for index in unused_list:
            protagonist.unused_team.append(protagonist.team[index])
            del protagonist.team[index]
    return protagonist.team