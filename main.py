import pickle
import os
import sys
import random
from copy import deepcopy

from Scripts.Game import *
from Scripts.Data.pokemon import *
from Scripts.Data.moves import *
from Scripts.Data.battlefield import *
from Scripts.Data.abilities import *
from Scripts.Data.competitors import *
from Scripts.Battle.type_chart import *
from Scripts.Battle.battle_cycle import *
from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Art.art import *
from Scripts.Game.start_interface import *
from Scripts.Game.game_system import *
from Scripts.Game.game_procedure import *
from Scripts.Game.before_battle import *


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    start_game()

    while True:
        music(audio=f'Assets/music/start{random.randint(1, 6)}.mp3', loop=True)
        # win the tournament
        if list_of_competitors['Protagonist'].stage == 6:
            print("Congratulations! You have won the Pokemon World Championship!!!")
            print(f"You have obtained {list_of_competitors['Protagonist'].championship + 1} World Champion Title(s) in your career!\n")
            music(audio='Assets/music/credits.mp3', loop=False)
            with open('Documentation/credits.txt', 'r') as f:
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


if __name__ == "__main__":
    main()
