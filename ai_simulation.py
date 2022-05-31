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

GameSystem.stage = 5
repeat = 1

side1_victory, side2_victory = 0, 0
side1_score, side2_score = 0, 0

for i in range(repeat):
    side1 = deepcopy(list_of_competitors["World Champion Marvin"])
    side2 = deepcopy(list_of_competitors["Demon Muzan"])
    side1.team = team_generation(side1)
    side2.team = team_generation(side2)
    battleground = Battleground()
    # for ai simulation
    battleground.verbose = True

    with suppress(RecursionError):
        battle_setup(side1, side2, side1.team, side2.team, battleground)

    if side1.score > side2.score:
        side1_victory += 1
    elif side2.score > side1.score:
        side2_victory += 1

    side1_score += side1.result
    side2_score += side2.result
    side1.score, side2.score = 0, 0

    print(f"\n\nVictories:\n{side1.name}: {side1_victory} || {side2.name}: {side2_victory}\nTotal Kills:\n{side1.name}: {side1_score} || {side2.name}: {side2_score}")
