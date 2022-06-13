import random
from pokemon import *
from moves import *
from battlefield import *
from copy import deepcopy
from type_chart import *
from text_color import *
from battle_cycle import *
from music import *
from art import *
from start_interface import *
from competitors import *
from game_procedure import *
from abilities import *
import pickle
import os
import sys

# pre-AI Update
# Upper Elite
# By Strength: Marvuno > Muzan > Cynthia > Conan
# Marvuno[3] vs Muzan[97]
# Marvuno[43] vs Cynthia[49]
# Marvuno[33] vs Conan[67]
# Cynthia[20] vs Conan[67]
# Muzan[48] vs Conan[52]
# Muzan[70] vs Cynthia[20]
# Conan > Muzan > Cynthia > Marvuno

# Lower Elite
# By Strength: Mivy > Animenz > Magnus > Elias
# Mivy[42] vs Magnus[57]
# Mivy[25] vs Animenz[74]
# Mivy[51] vs Elias[47]
# Animenz[67] vs Elias[33]
# Magnus[49] vs Elias[50]
# Animenz[74] vs Magnus[26]
# Animenz > Mivy ~ Magnus ~ Elias

# post-AI Update
# Upper Elite
# By Strength: Marvuno > Muzan > Cynthia > Conan
# Marvuno[42] vs Muzan[58]
# Marvuno[26] vs Cynthia[74]
# Marvuno[83] vs Conan[17]
# Cynthia[54] vs Conan[46]
# Muzan[65] vs Conan[35]
# Muzan[38] vs Cynthia[62]
# Cynthia > Muzan > Marvuno > Conan

# Lower Elite
# By Strength: Mivy > Animenz > Magnus > Elias
# Mivy[46] vs Magnus[54]
# Mivy[33] vs Animenz[67]
# Mivy[55] vs Elias[45]
# Animenz[66] vs Elias[34]
# Magnus[52] vs Elias[48]
# Animenz[58] vs Magnus[42]
# Animenz > Magnus > Mivy > Elias

GameSystem.stage = 5
repeat = 100

side1_victory, side2_victory = 0, 0
side1_score, side2_score = 0, 0
side1_pokemon = {'Very Low': 0, 'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Ultra High': 0, 'Boss': 0, 'Secret': 0}
side2_pokemon = {'Very Low': 0, 'Low': 0, 'Medium': 0, 'High': 0, 'Very High': 0, 'Ultra High': 0, 'Boss': 0, 'Secret': 0}

for i in range(repeat):
    side1 = deepcopy(list_of_competitors["Magnus Carlsen"])
    side2 = deepcopy(list_of_competitors["Animenz"])
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

    if side1.score > side2.score:
        side1_victory += 1
    elif side2.score > side1.score:
        side2_victory += 1

    side1_score += side1.result
    side2_score += side2.result
    side1.score, side2.score = 0, 0

    print(f"\n\nVictories:\n{side1.name}: {side1_victory} || {side2.name}: {side2_victory}\n"
          f"Total Kills:\n{side1.name}: {side1_score} || {side2.name}: {side2_score}\n\n"
          f"Pokemon Tier:\n{side1.name}: {side1_pokemon}\n{side2.name}: {side2_pokemon}")
