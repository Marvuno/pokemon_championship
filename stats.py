from pokemon import *
from moves import *
from abilities import *
from text_color import *
import numpy as np

TYPING = {0: 'Normal', 1: 'Fire', 2: 'Water', 3: 'Electric', 4: 'Grass', 5: 'Ice', 6: 'Fighting', 7: 'Poison', 8: 'Ground',
          9: 'Flying', 10: 'Psychic', 11: 'Bug', 12: 'Rock', 13: 'Ghost', 14: 'Dragon', 15: 'Dark', 16: 'Steel', 17: 'Fairy'}
TIER = {0: 'Very Low', 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Very High', 5: 'Ultra High'}
ATTACK_TYPE = {0: 'Physical', 1: 'Special', 2: 'Status'}

print(f"{CBOLD}Total Number of Pokemon: {len(list_of_pokemon)}{CEND}")
for index, type in TYPING.items():
    tier_list = {'Very Low': 0, 'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Ultra High': 0}
    tier_conversion = {'Very Low': 'VL', 'Low': 'L', 'Medium': 'M', 'High': 'H', 'Very High': 'VH', 'Ultra High': 'UH'}
    temp = []
    number = sum([1 for pokemon in list_of_pokemon if type in list_of_pokemon[pokemon].type])
    for tier, count in tier_list.items():
        tier_list[tier] = sum([1 for pokemon in list_of_pokemon if type in list_of_pokemon[pokemon].type and tier == list_of_pokemon[pokemon].tier])
        temp.append(tier_list[tier])
    # print(f"{CBEIGE2}{type}: {number} || {[(tier_conversion[key], value) for key, value in tier_list.items()]} {CEND}")
    print(f"{CBEIGE2}{type}: {number} || {temp} {CEND}")
print("")

for index, tier in TIER.items():
    number = sum([1 for pokemon in list_of_pokemon if tier == list_of_pokemon[pokemon].tier])
    print(f"{CGREEN2}{tier}: {number}{CEND}")

print(f"\n{CBOLD}Custom: {sum([1 for pokemon in list_of_pokemon if list_of_pokemon[pokemon].custom])}{CEND}")
for mon in list_of_pokemon.values():
    if mon.custom:
        print(f"{CYELLOW2}{mon.name} {mon.type}{CEND}")

print(f"\n{CBOLD}Total Number of Moves: {len(list_of_moves)}{CEND}")
for index, type in TYPING.items():
    number = sum([1 for moves in list_of_moves if list_of_moves[moves].type == type])
    print(f"{CBEIGE2}{type}: {number}{CEND}")

print(f"\n{CBOLD}By Attack Types:{CEND}")
for index, type in ATTACK_TYPE.items():
    number = sum([1 for moves in list_of_moves if list_of_moves[moves].attack_type == type])
    print(f"{CGREEN2}{type}: {number}{CEND}")

print(f"\n{CBOLD}Custom: {sum([1 for moves in list_of_moves if list_of_moves[moves].custom])}{CEND}")
for move in list_of_moves.values():
    if move.custom:
        print(f"{CYELLOW2}{move.name} ({move.type}): {move.power} power, {move.attack_type}{CEND}")

UseAbility('', '', '', '', '', verbose=True)

print(f"\n\n{CBOLD}Move Usage: {CEND}\n")
move_usage = True  # debug only
if move_usage:
    move_list = dict.fromkeys([move for move in list_of_moves], 0)
    for pokemon in list_of_pokemon:
        for move in list_of_pokemon[pokemon].moveset:
            move_list[move] += 1
    move_list = dict(sorted(move_list.items(), key=lambda item: item[1]))
    for move, usage in move_list.items():
        print(f"{move}: {usage}")
