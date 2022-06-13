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
import os.path
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
        noob_confirmation = input("Are you a first-timer? Please enter 'Y' if you are new to the game (backstory, rules and tutorial): ").upper()
        if noob_confirmation == 'Y':
            backstory()
            input("Enter any key to continue...")
            rules()
            input("Enter any key to continue...")
            tutorial()
        # name input
        name_list = [list_of_competitors[competitor].name for competitor in list_of_competitors]
        list_of_competitors['Protagonist'].name = input("\nWhat is your name? (within 18 char.) ")
        while re.search("^\s*$", list_of_competitors['Protagonist'].name) or len(list_of_competitors['Protagonist'].name) > 18 or list_of_competitors['Protagonist'].name in name_list:
            print("Sorry. Your name is either too long or too short, or it has already been taken.")
            list_of_competitors['Protagonist'].name = input("What is your name? (within 18 char.) ")
    # continue
    elif option == 1:
        if os.path.exists('savefile.dat'):
            load_data()
        else:
            print("No save file!")
            main_screen()
    # options
    elif option == 2:
        print("Sorry, feature not available yet. TBD")
        main_screen()
    # history record for savefile
    elif option == 3:
        # read savefile
        if os.path.exists('savefile.dat'):
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
                    print(f"\n{op.name} has participated the Pokemon Championship for {op.participation} time(s), with {op.championship} World Champion title(s).{CEND}")
                    print(f"\n{op.name}'s Pokemon Championship history: ")
                    for parti, hist in op.history.items():
                        print(f"#{parti + 1}: Rank {hist[1]}")
                    # favourite opponent
                    battle_list = dict(sorted(op.opponent_history.items(), key=lambda x: (x[1][0]+x[1][1], x[1][0]), reverse=True)[:5])
                    print("\nFavorite Opponent:")
                    for i, (name, record) in enumerate(battle_list.items()):
                        print(f"#{i+1}. {name}: {record[0]} Win {record[1]} Lose")

                    confirmation = input("\nWanna know his/her match history against individuals? (Quite Long!) Enter 'Y' to confirm: ").upper()
                    if confirmation == 'Y':
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
        else:
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
          "There are 8 particularly strong participants, otherwise known as the Elite Eight. They are further divided into Lower Elite Four 四小天王 and\n"
          "Upper Elite Four 四大天王, where the Upper ones each obtains an honor title. This is in accordance with the World Pokemon Rankings Table and will be\n"
          "updated every few years. \n\n" 
          "You have been renowned as one of the most talented trainers in recent decades. You are highly respected as one of the rising prodigies in the\n"
          "Pokemon Competitive Environment. Most recently, you have been the youngest winner of the U15 Pokemon Amateur Tournament in the history.\n"
          "Hence, the organizer generously granted you the wildcard, allowing you to directly seed into the Playoffs.\n"
          "You will start off with your starter pokemon -- Psyduck.\n")


def rules():
    print("\nRules:\n"
          "The Pokemon Championship is a swiss-system tournament. It will be a 5-round robin with 32 participants.\n"
          "When the team is not full (6 pokemon), winner can either take 1 pokemon from the loser or receive a random pokemon from the organizer while\n"
          "loser can only receive a random inferior pokemon from the organizer.\n"
          "When the team is full (6 pokemon), winner has the option to swap 1 pokemon with the loser, while loser can do nothing.\n"
          "You will play 5 rounds, but you may quit early. \n"
          "The tournament will start with 4vs4, then 5vs5, and the remaining 3 rounds will be 6vs6 full battle.\n"
          "Player who won all 5 rounds will be the World Champion for the year.\n"
          "Initially, you will receive 4 random pokemon. You have the option to keep at most 3 pokemon when you lose and all 6 pokemon when you "
          "won the Championship. Good luck!\n")


def tutorial():
    print(f"\nTutorial #1: Receiving Pokemon\n\n"
          f"If your team has less than 4 Pokemon at the start, you will receive random Pokemon from the organizer.\n"
          f"When you have won, you are usually allowed to take 1 Pokemon from the opponent or receive a random Pokemon instead.\n"
          f"However, if you have more Pokemon than needed for the next round, you will not receive any Pokemon or grant the opportunity to\n"
          f"take 1 Pokemon from the opponent upon victory.\n"
          f"If you lost the battle, unfortunately you will automatically receive a random Pokemon only.\n"
          f"If you already have a team of six (full team), You can swap 1 Pokemon if you won the battle, and nothing to do if you lost.\n"
          f"(NOTE: the Pokemon you receive initially depends on your ratings. The higher your ratings, the better Pokemon you will get!\n"
          f"       the Pokemon you randomly obtains when you WON the battle depends on the opponent. The stronger the opponent, the better Pokemon you will get!\n"
          f"       the Pokemon you randomly obtains when you LOST the battle will always be much inferior.\n")
    input("Enter any key to continue...")
    print(f"\nTutorial #2: Before Battle\n\n"
          f"The system will randomly pair 32 participants. The individual match-up will then be shown. You should see 32 of these boxes:\n"
          f"╔====╦======╦========╦=======╗\n"
          f"║ ID ║ NAME ║ POINTS ║ SCORE ║\n" 
          f"╚====╩======╩========╩=======╝\n"
          f"Points: each win scores 1 point, and each defeat scores 0 point.\n"
          f"Score: the number of Pokemon defeated in that match. It will thus only display after the round. The purpose of it is for tiebreaks.\n\n"
          f"As the Player, you may do 5 things before entering the battle:\n"
          f"View My Pokemon: have a solid understanding of your team. You want to do this at least once at the start, since you will obtain new Pokemon.\n"
          f"Switch Pokemon Order: you may switch a Pokemon to be the starting Pokemon.\n"
          f"About Opponent: know about your next opponent. It will show his/her Character Ability and Signature Pokemon.\n"
          f"                If your ratings are high, you can even know about the starting Pokemon of the opponent, sometimes including its moveset!\n"
          f"                (TIPS: Pokemon with the ability Illuminate can increase the probability of this by 10 times.)\n"
          f"Check History: check your match history against him/her. You may also know the opponent journey.\n"
          f"Quit Game: you will withdraw early from the game, and you may only keep at most 3 Pokemon for the next round.\n"
          f"If your team has more Pokemon than the round requires, you will have to select some Pokemon that you DO NOT need for this round.\n")
    input("Enter any key to continue...")
    print(f"\nTutorial #3: In Battle\n\n"
          f"I will assume that you are a Pokemon expert when you play this game. Hence, I cannot give you much tips for the battle.\n"
          f"But I would like to remind you that the weather for each battle may have changed. Observe carefully.\n"
          f"For opponent with ratings <20, they are usually more stupid and only rely on attacking moves. Any opponent higher than that ratings can be\n"
          f"a prominent opponent that requires special attention.\n"
          f"However, if you think that your Pokemon is vastly better than your opponent, you may activate Auto Battle with '100'. Sometimes, the AI may\n"
          f"even perform better than you. ^_^\n"
          f"You may receive or swap Pokemon after the battle, depends on the situation.\n")
    input("Enter any key to continue...")
    print(f"\nTutorial #4: End Game\n\n"
          f"Very soon you will play all 5 rounds and receive the result. A large scoreboard will be displayed. However, usually only the Champion matters.\n"
          f"The ranking is based on 3 factors: Points, Net Kill Score and Ratings.\n"
          f"Points: first deciding factor. The higher the points, the higher the ranking.\n"
          f"Net Kill Score (NKS): second deciding factor. It's equivalent to how many Pokemon you fainted in total - how many Pokemon your opponent fainted yours in total.\n"
          f"                      The higher the NKS, the higher the ranking.\n"
          f"Ratings: third deciding factor. The lower the ratings, the higher the ranking.\n"
          f"You will also see how many ratings you gain in this Tournament.\n"
          f"(NOTE: Initially, you may find it difficult to gain ratings. No worries. After some time, you will grasp some win by having a mediocre team.\n"
          f"       When you slowly build up your ratings, it will trigger a snowball effect and you will start having better performance.)\n\n"
          f"That's all for the tutorial! Please enjoy the game for now!\n")
    input("Enter any key to continue...")