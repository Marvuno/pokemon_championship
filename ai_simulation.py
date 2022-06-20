import random
import os
import sys
from copy import deepcopy

from Scripts.Art.text_color import *
from Scripts.Data.pokemon import *
from Scripts.Data.moves import *
from Scripts.Data.battlefield import *
from Scripts.Data.competitors import *
from Scripts.Battle.battle_cycle import *
from Scripts.Game.game_system import *


GameSystem.stage = 5
repeat = 1
mode = 2

side1_victory, side2_victory = 0, 0
side1_score, side2_score = 0, 0
side1_pokemon = {'Very Low': 0, 'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Ultra High': 0, 'Boss': 0, 'Secret': 0}
side2_pokemon = {'Very Low': 0, 'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Ultra High': 0, 'Boss': 0, 'Secret': 0}
pokemon_win = {}
pokemon_appearance = {}

all_participants = list(list_of_competitors.keys())[1:]

if mode == 0:  # all vs all
    side1_participants = all_participants
    side2_participants = all_participants
elif mode == 1:  # one vs all
    side1_participants = ['Animenz']
    side2_participants = all_participants
else:  # one vs one
    side1_participants = ['Trasher']
    side2_participants = ['Dulunga']

winner_name = []
winner_count = dict.fromkeys(all_participants, 0)

for k in side1_participants:
    for j in side2_participants:
        if all_participants.index(j) <= all_participants.index(k) and mode == 0:
            continue
        for i in range(repeat):
            side1 = deepcopy(list_of_competitors[k])
            side2 = deepcopy(list_of_competitors[j])
            side1.team = team_generation(side1)
            side2.team = team_generation(side2)
            battleground = Battleground()
            # for ai simulation
            battleground.verbose = True

            with suppress(RecursionError):
                battle_setup(side1, side2, side1.team, side2.team, battleground)

            for pokemon, pokemon2 in zip(side1.team, side2.team):
                side1_pokemon[pokemon.tier] += 1
                side2_pokemon[pokemon2.tier] += 1

            # which side win and which pokemon win
            if side1.score > side2.score:
                side1_victory += 1
                winner_count[side1.name] += 1
                for pokemon in side1.team:
                    try:
                        pokemon_win[pokemon.name] += 1
                    except KeyError:
                        pokemon_win.update({pokemon.name: 1})
            elif side2.score > side1.score:
                side2_victory += 1
                winner_count[side2.name] += 1
                for pokemon in side2.team:
                    try:
                        pokemon_win[pokemon.name] += 1
                    except KeyError:
                        pokemon_win.update({pokemon.name: 1})

            # how many rounds that pokemon appear
            for pokemon in side1.team:
                try:
                    pokemon_appearance[pokemon.name] += 1
                except KeyError:
                    pokemon_appearance.update({pokemon.name: 1})
            for pokemon in side2.team:
                try:
                    pokemon_appearance[pokemon.name] += 1
                except KeyError:
                    pokemon_appearance.update({pokemon.name: 1})

            side1_score += side1.result
            side2_score += side2.result
            side1.score, side2.score = 0, 0

print(f"\n\nVictories:\n{side1.name}: {side1_victory} || {side2.name}: {side2_victory}\n"
      f"Total Kills:\n{side1.name}: {side1_score} || {side2.name}: {side2_score}\n\n"
      f"Pokemon Tier:\n{side1.name}: {side1_pokemon}\n{side2.name}: {side2_pokemon}")

# win rate
print("\nWin Rate:")
pokemon_win_rate = deepcopy(pokemon_appearance)
for key, value in pokemon_appearance.items():
    try:
        pokemon_win_rate[key] = round(pokemon_win[key] / pokemon_appearance[key] * 100, 1)
    except:
        pokemon_win_rate[key] = 0
pokemon_win_rate = dict(sorted(pokemon_win_rate.items(), key=lambda item: -item[1]))
for key, value in pokemon_win_rate.items():
    try:
        print(f"{key}:{' ' * (25-len(key))}{value}% || Round: {pokemon_appearance[key]}{' ' * (3-len(str(pokemon_appearance[key])))} || Tier: {list_of_pokemon[key].tier}")
    except:
        continue

if mode == 0 or mode == 1:
    print()
    for name, win in winner_count.items():
        print(name, win)
