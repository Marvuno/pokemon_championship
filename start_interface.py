import random
from contextlib import suppress
from art import *
from single_elimination_bracket import *
from text_color import *
from competitors import *
from pokemon import *
from copy import deepcopy
from game_system import *
from battlefield import *
from game_procedure import *
from music import *
import math
import pickle
import sys
import re


def start_game():
    print(cover_art)
    music(audio=f'music/intro.mp3', loop=True)
    main_screen()


def main_screen():
    def load_data():
        with open('savefile.dat', 'rb') as f:
            data = pickle.load(f)
            for competitor in data:
                # # debug
                # print(competitor.__dict__)
                op = list_of_competitors['Protagonist'] if competitor.main else list_of_competitors[competitor.name]
                if competitor.main:
                    op.team = competitor.team
                    op.name = competitor.name
                    op.strength = competitor.strength
                op.history = competitor.history
                op.opponent_history = competitor.opponent_history
                op.participation = competitor.participation
                op.championship = competitor.championship

    print(f"┏------------┓\n"
          f"| 0 NEW GAME |\n"
          f"|------------|\n"
          f"| 1 CONTINUE |\n"
          f"|------------|\n"
          f"| 2 OPTIONS  |\n"
          f"|------------|\n"
          f"| 3 HISTORY  |\n"
          f"|------------|\n"
          f"| 4 QUIT     |\n"
          f"┗------------┛")

    option = -1
    while not 0 <= option <= 4:
        with suppress(ValueError):
            option = int(input(f"Your Option: "))

    # new game
    if option == 0:
        backstory()
        rules()
        # name input
        name_list = [list_of_competitors[competitor].name for competitor in list_of_competitors]
        list_of_competitors['Protagonist'].name = input("\nWhat is your name? (within 21 char.) ")
        while re.search("^\s*$", list_of_competitors['Protagonist'].name) or len(list_of_competitors['Protagonist'].name) > 21 or list_of_competitors['Protagonist'].name in name_list:
            print("Sorry. Your name is either too long or too short, or it has already been taken.")
            list_of_competitors['Protagonist'].name = input("What is your name? (within 21 char.) ")
    # continue
    elif option == 1:
        try:
            load_data()
        except FileNotFoundError:
            print("No save file!")
            main_screen()
    # options
    elif option == 2:
        print("Sorry, feature not available yet. TBD")
        main_screen()
    # history record for savefile
    elif option == 3:
        # read savefile
        try:
            load_data()

            print(f"\n{CBOLD}The Champion of the Pokemon Championship: ")
            for parti, hist in list_of_competitors['Protagonist'].history.items():
                print(f"#{parti + 1}: {hist[0]}")
            print(CEND)

            char_dict = {}
            for index, competitor in enumerate(list_of_competitors):
                print(f"{index + 1}: {competitor}")
                char_dict[index + 1] = competitor
            while True:
                with suppress(IndexError, KeyError, TypeError, ValueError):
                    choice = int(input("Choose the participant you are interested in (Enter 0 to return to home screen): "))
                    if choice == 0:
                        break
                    op = list_of_competitors[char_dict[choice]]
                    print(f"\n{CBOLD}{op.name}\n\nDescription: {op.desc}") if not op.main else print(f"\n{CBOLD}{op.name}\n\nDescription: {op.desc.format(10 + len(op.history))}")
                    print(
                        f"\n{op.name} has participated the Pokemon Championship for {op.participation} time(s), with {op.championship} World Champion title(s).{CEND}")
                    confirmation = input("\nWanna know his/her match history? Press Y to confirm: ").upper()
                    if confirmation == 'Y':
                        print(f"\n{op.name}'s Pokemon Championship history: ")
                        for parti, hist in op.history.items():
                            print(f"#{parti + 1}: Rank {hist[1]}")
                        print(f"\n{op.name}'s match history against individuals:\n")
                        print(f"{CURL}{CBOLD}{' ' * 10}NAME{' ' * 10} || {' ' * 4}RECORD{' ' * 4} || {' ' * 4}WR{' ' * 4}{CEND}")
                        for i, (opponent, record) in enumerate(op.opponent_history.items()):
                            if opponent != op.name:
                                win_rate = "N/A"
                                with suppress(ZeroDivisionError):
                                    win_rate = str(int(record[0] / (record[0] + record[1]) * 100)) + '%'
                                print(f"{CBOLD}{opponent}{' ' * (24 - len(opponent))} || {record[0]}{' ' * (2 - len(str(record[0])))} Win {record[1]}{' ' * (2 - len(str(record[1])))} Lose || {win_rate} ({record[0] + record[1]}){CEND}") if i % 2 == 0 else \
                                print(f"{CBEIGE+CBOLD}{opponent}{' ' * (24 - len(opponent))} || {record[0]}{' ' * (2 - len(str(record[0])))} Win {record[1]}{' ' * (2 - len(str(record[1])))} Lose || {win_rate} ({record[0] + record[1]}){CEND}")
            main_screen()
        # no savefile
        except FileNotFoundError:
            print("No save file!")
            main_screen()
    else:
        sys.exit()

    if 0 <= option <= 1:
        list_of_competitors['Protagonist'].team = team_generation(list_of_competitors['Protagonist'])
        GameSystem.participants += random.sample(GameSystem.competitor_list,
                                                 32 - len(GameSystem.participants))  # elite four, champion and protagonist are seeded
        random.shuffle(GameSystem.participants)

        # # debug reseeding
        # # activation: set that character to be Champion
        # index = GameSystem.participants.index('Protagonist')
        # opponent = index + 1 if index % 2 == 0 else index - 1
        # for i in range(len(GameSystem.participants)):
        #     if GameSystem.participants[i] == "Shuka":
        #         GameSystem.participants[i], GameSystem.participants[opponent] = GameSystem.participants[opponent], GameSystem.participants[i]
        #         break

        for i, name in enumerate(GameSystem.participants):
            name = list_of_competitors[name]
            name.id = i + 1


# for player that choose new game aka option 0
def backstory():
    print("\nBackground:\n"
          "The most prosperous and prestigious region in the Pokemon World, known as Krusades, is organizing the World Pokemon Championship\n"
          "after a resounding success last year. the winner will be renowned as the Official World Champion\n"
          "With an astronomical amount of prize money (roughly 2M USD for the champion) and the fame of being the World's No.1 trainer among the world,\n"
          "the Championship successfully attracted thousands of trainers around the world to challenge the title. After several stages of\n"
          "Preliminaries and Wildcards chosen by the organizers, the Tournament filtered the remaining 32 elites in the Playoffs stage.\n"
          "Despite the fierce competition, there are a few Tournament favorites throughout. Before the Official Pokemon Championship,\n"
          "Krusades invited a few renowned trainers in an Unofficial match. Marvin is the Champion of the match and claimed himself as the World Champion,\n"
          "which given his prowess is relatively uncontested and even unanimously accepted.\n"
          "In the Unofficial World Pokemon Championship, he has defeated the opponent in all 5 rounds in domination almost effortlessly.\n"
          "This year, he is directly seeded into the Playoffs striving to be the reigning champion. Along with World Champion Marvin,\n"
          "There are 8 particularly strong participants, otherwise known as the Elite Eight. They are further divided into Lower Elite Four and\n"
          "Upper Elite Four, where the Upper ones each obtains an honor title. This is in accordance with the World Pokemon Rankings Table and will be\n"
          "updated every few years. \n\n"
          "You have been renowned as one of the most talented trainers in recent decades. You are highly respected as one of the rising prodigies in the\n"
          "Pokemon Competitive Environment. Most recently, you have been the youngest winner of the U15 Pokemon Amateur Tournament in the history.\n"
          "Hence, the organizer generously granted you the wildcard, allowing you to directly seed into the Playoffs.\n"
          "You will start off with your starter pokemon -- Psyduck.\n\n")


def rules():
    print("\nRules:\n"
          "The Pokemon Championship is a swiss-system tournament. It will be a 5-round robin with 32 participants.\n"
          "When the team is not full (6 pokemon), winner can either take 1 pokemon from the loser or receive a random pokemon from the organizer while\n"
          "loser can only receive a random inferior pokemon from the organizer.\n"
          "When the team is full (6 pokemon), winner has the option to swap 1 pokemon with the loser, while loser can do nothing.\n"
          "You will play 5 rounds, but you may quit early. \n"
          "The tournament will start with 4vs4, then 5vs5, and the remaining 3 rounds will be 6vs6 full battle.\n"
          "Player who won all 5 rounds will be the World Champion for the year.\n"
          "Initially, you will receive 4 random pokemon. You have the option to keep at most 2 pokemon when you lose and all 4 pokemon when you "
          "won the Championship. Good luck!")
