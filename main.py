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


os.system('cls')
start_game()

while True:
    music(audio=f'music/start{random.randint(1, 4)}.wav', loop=True)

    # win the tournament
    if list_of_competitors['Protagonist'].stage == 6:
        print("Congratulations! You have won the Pokemon World Championship!!!")
        print(f"You have obtained {list_of_competitors['Protagonist'].championship + 1} World Champion Title(s) in your career!\n")
        music(audio='music/credits.mp3', loop=False)
        with open('credits.txt', 'r') as f:
            for line in f:
                print(line.rstrip())
        input("\nPress any key to proceed.")

    # game end
    if GameSystem.stage == 6:
        break

    opponent = next_battle()
    before_battle_option(list_of_competitors['Protagonist'], opponent)
    list_of_competitors['Protagonist'].team = team_selection(list_of_competitors['Protagonist'])
    battleground = Battleground()
    battle_setup(list_of_competitors['Protagonist'], opponent, list_of_competitors['Protagonist'].team, opponent.team, battleground)

scoreboard()
elo_rating()
save_game()
input("Press any key to confirm the results.")
restart()
