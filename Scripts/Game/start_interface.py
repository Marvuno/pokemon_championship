import sys
sys.path.insert(1, '/.../Pokemon Arena/Scripts/')

import random
import os.path
import sys
import re
from contextlib import suppress
from copy import deepcopy

from Scripts.Art.art import *
from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Data.competitors import *
from Scripts.Data.pokemon import *
from Scripts.Game.game_system import *
from Scripts.Game.game_procedure import *
from Scripts.Game import savefile


#: The main menu's HISTORY screen, pulled out of main_screen() so each piece
#: is a function with a name. That is what lets the interface hook them and
#: show one window instead of leaving a whole career as paragraphs in the log
#: -- the same way About Opponent and Check History work. The text printed is
#: unchanged, so the terminal version reads exactly as before.
def history_screen(protagonist):
    """The HISTORY screen: the champion roll, then a competitor at a time.

    Deliberately not wrapped around main_screen() the way it used to be --
    the recursive call back to the title screen now happens in the caller,
    so the interface can quiet this screen's output without also silencing
    the menu it returns to.
    """
    champion_roll(protagonist)
    while True:
        first_confirmation = input("\nWanna read the stats of a selected character? (Very Long) Enter 'Y' to confirm: ").upper()
        if first_confirmation != 'Y':
            break
        char_dict = participant_list()
        with suppress(IndexError, KeyError, TypeError, ValueError):
            choice = int(input("Choose the participant you are interested in (Enter 0 to return to home screen): "))
            if choice == 0:
                break
            op = list_of_competitors[char_dict[choice]]
            if not competitor_report(op):
                continue
            second_confirmation = input("\nWanna know his/her match history against individuals? (Very Long) Enter 'Y' to confirm: ").upper()
            if second_confirmation == 'Y':
                individual_records(op)


def participant_list():
    """The numbered roster, and the {number: name} it is picked by."""
    char_dict = {}
    for index, competitor in enumerate(list_of_competitors):
        competitor = list_of_competitors[competitor]
        print(f"{index + 1}: {competitor.nickname}")
        char_dict[index + 1] = competitor.name
    return char_dict


def champion_roll(protagonist):
    """Who won each championship, oldest run first."""
    print(f"\n{CBOLD}The Champion of the Pokemon Championship: ")
    for parti, hist in (protagonist.history or {}).items():
        print(f"#{parti + 1}: {hist[0]}")
    print(CEND)


def career_totals(op):
    """(wins, losses) across every opponent on record."""
    history = getattr(op, "opponent_history", None) or {}
    return (sum(value[0] for value in history.values()),
            sum(value[1] for value in history.values()))


def competitor_report(op):
    """One competitor's career. False if there is nothing on record yet."""
    total_win, total_lose = career_totals(op)
    print(f"\n{CBOLD}{op.nickname}\n\nDescription: {op.desc}") if not op.main else print(f"\n{CBOLD}{op.nickname}\n\nDescription: {op.desc.format(10 + len(op.history))}")
    print(f"\n{op.nickname} has participated the Pokemon Championship for {op.participation} time(s), with {op.championship} World Champion title(s).")
    # Someone drawn into the bracket for the first time has played nobody, so
    # there is no win rate to compute -- dividing by their zero matches raised
    # ZeroDivisionError, which is not one of the errors suppressed around the
    # caller, so looking them up crashed the game. Say there is nothing on
    # record and skip the sections that would all be empty.
    if total_win + total_lose == 0:
        print(f"There is no match history on record for "
              f"{op.nickname} yet.{CEND}")
        return False
    print(f"Total Wins: {total_win} | Total Lose: {total_lose} | Win Rate: {round(total_win / (total_win + total_lose) * 100, 2)}%{CEND}")
    print(f"\n{op.nickname}'s Pokemon Championship history: ")
    for parti, hist in op.history.items():
        print(f"#{parti + 1}: Rank {hist[1]}")
    # favourite opponent
    battle_list = dict(sorted(op.opponent_history.items(), key=lambda x: (x[1][0]+x[1][1], x[1][0]), reverse=True)[:5])
    print("\nFavorite Opponent:")
    for i, (name, record) in enumerate(battle_list.items()):
        print(f"#{i+1}. {list_of_competitors[name].nickname}: {record[0]} Win {record[1]} Lose")
    return True


def individual_records(op):
    """Their record against every competitor, one row each."""
    print(f"\n{op.nickname}'s match history against individuals:\n")
    print(f"{CURL}{CBOLD}{' ' * 10}NAME{' ' * 10} || {' ' * 4}RECORD{' ' * 4} || {' ' * 4}WR{' ' * 4}{CEND}")
    for i, (opponent, record) in enumerate(op.opponent_history.items()):
        if opponent != op.name:
            opponent = list_of_competitors[opponent].nickname
            win_rate = "N/A"
            with suppress(ZeroDivisionError):
                win_rate = str(int(record[0] / (record[0] + record[1]) * 100)) + '%'
            print(f"{CBOLD}{opponent}{' ' * (24 - len(opponent))} || {record[0]}{' ' * (2 - len(str(record[0])))} Win {record[1]}{' ' * (2 - len(str(record[1])))} Lose || {win_rate} ({record[0] + record[1]}){CEND}") if i % 2 == 0 else \
            print(f"{CBEIGE+CBOLD}{opponent}{' ' * (24 - len(opponent))} || {record[0]}{' ' * (2 - len(str(record[0])))} Win {record[1]}{' ' * (2 - len(str(record[1])))} Lose || {win_rate} ({record[0] + record[1]}){CEND}")


def start_game():
    print(cover_art)
    music(audio=f'Assets/music/intro.mp3', loop=True)
    main_screen()


def main_screen():
    def load_data():
        """Restore the save. JSON, or an old pickle migrated on the way in.

        Both paths default every competitor to a clean head-to-head and skip
        records for anyone the roster no longer has, so renaming a competitor
        in Data/competitors.csv cannot make an older save unloadable.
        """
        return savefile.load(list_of_competitors, list_of_pokemon)

    # A loop, not recursion. Every "back to the menu" here used to be a fresh
    # call to main_screen() from inside the old one, so each visit to OPTIONS
    # or HISTORY left a frame on the stack for good -- open HISTORY enough
    # times in one sitting and the interpreter runs out of C stack and the
    # process dies with an access violation and no traceback. It showed up as
    # three crashes in twelve automated runs of that screen.
    def pick_slot(purpose, need_used):
        """Which of the four careers. None if there is nothing to pick from.

        `need_used` filters to slots that have something in them, for
        continuing and for reading a history; starting a new game offers all
        four and says what it would overwrite.
        """
        entries = [entry for entry in savefile.slots()
                   if entry.get("used") or not need_used]
        if not entries:
            return None
        print(f"\n{purpose}")
        for entry in entries:
            print(f"{entry['slot']}: {savefile.describe(entry)}")
        print("0: back")
        while True:
            with suppress(ValueError):
                choice = int(input("Which save slot? "))
                if choice == 0:
                    return None
                if any(entry["slot"] == choice for entry in entries):
                    return choice

    # OPTIONS and QUIT are gone from here. OPTIONS never did anything but
    # print "feature not available yet" -- the window's Settings panel is the
    # real thing, and it is reachable at any time rather than only from this
    # screen. QUIT is what the window's own close button is for, and having it
    # on the menu meant one mis-click could end a run.
    # Taken before any career is read, because load() writes into these dicts
    # in place. Without it there is no way back to "as the CSV describes them",
    # which is what a new game needs. See savefile.start_fresh.
    savefile.remember_pristine(list_of_competitors, list_of_pokemon)

    while True:
        # A career from before there were slots becomes slot 1, by copy, so
        # the original file is still there afterwards. Done here rather than
        # on import so it happens once the game is actually being played.
        savefile.adopt_single_save()
        print(f"┏------------┓\n"
              f"| 0 NEW GAME |\n"
              f"|------------|\n"
              f"| 1 CONTINUE |\n"
              f"|------------|\n"
              f"| 2 HISTORY  |\n"
              f"┗------------┛")

        option = -1
        while not 0 <= option <= 2:
            with suppress(ValueError):
                option = int(input(f"Your Option: "))

        # the one that comes back to this menu rather than starting a game
        if option == 2:
            slot = pick_slot("Whose history?", need_used=True)
            if slot is None:
                print("No save file!") if not savefile.any_exists() else None
                continue
            savefile.select(slot)
            load_data()
            history_screen(list_of_competitors['Protagonist'])
            continue
        if option == 1:
            slot = pick_slot("Continue which career?", need_used=True)
            if slot is None:
                print("No save file!") if not savefile.any_exists() else None
                continue
            savefile.select(slot)
            break
        slot = pick_slot("Start a new career in which slot? "
                         "(anything already there is replaced)",
                         need_used=False)
        if slot is None:
            continue
        savefile.select(slot)
        # Wipe whatever a previous CONTINUE or HISTORY on this menu left in the
        # shared rosters. Without this a "new" career started with the runs,
        # titles, championship history and head-to-head record of whichever
        # save had last been looked at -- so a new game in slot 3 saved another
        # player's career under it.
        savefile.start_fresh(list_of_competitors, list_of_pokemon)
        break

    # new game
    if option == 0:
        noob_confirmation = input("Are you a first-timer? Please enter 'Y' if you are new to the game (backstory, rules and tutorial): ").upper()
        if noob_confirmation == 'Y':
            backstory()
            input("Enter any key to continue...")
            tutorial()
        # name input
        # Both fields, not just the nickname, and compared case-insensitively.
        # A competitor has a nickname ("Lady Evonne") and an internal name
        # ("Evonne"), and taking either one causes real trouble: the save keys
        # head-to-head records by *name*, so a player called the same thing as
        # a competitor shares their record. The old check only looked at
        # nicknames and only matched exactly, so "evonne" went straight through.
        taken = set()
        for competitor in list_of_competitors.values():
            for field in ("nickname", "name"):
                value = str(getattr(competitor, field, "") or "").strip()
                if value:
                    taken.add(value.casefold())

        def unacceptable(chosen):
            chosen = (chosen or "").strip()
            if not chosen:
                return "Your name cannot be blank."
            if len(chosen) > 18:
                return "That is longer than 18 characters."
            if chosen.casefold() in taken:
                return ("Somebody in the championship already goes by that. "
                        "Pick something else.")
            return None

        list_of_competitors['Protagonist'].nickname = input("\nWhat is your name? (within 18 char.) ")
        complaint = unacceptable(list_of_competitors['Protagonist'].nickname)
        while complaint:
            print(complaint)
            list_of_competitors['Protagonist'].nickname = input("What is your name? (within 18 char.) ")
            complaint = unacceptable(list_of_competitors['Protagonist'].nickname)
        list_of_competitors['Protagonist'].nickname = \
            list_of_competitors['Protagonist'].nickname.strip()
        # After the name, and outside the first-timer branch above, so it
        # happens whether the tutorial was taken or skipped. Before
        # team_generation below, which fills the rest of the team around it.
        choose_starter(list_of_competitors['Protagonist'])
    # continue -- the loop above already sent you back if there was no save,
    # so getting here means there is one
    elif option == 1:
        load_data()

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
        #     if GameSystem.participants[i] == "Emperor Marvuno":
        #         GameSystem.participants[i], GameSystem.participants[opponent] = GameSystem.participants[opponent], GameSystem.participants[i]
        #         break

        for i, name in enumerate(GameSystem.participants):
            name = list_of_competitors[name]
            name.id = i + 1
            # A fresh run means a fresh list of who you got through. Cleared
            # here, at the point the bracket is drawn, rather than when a
            # championship ends -- so a run abandoned partway still leaves its
            # record behind for the standings to read.
            name.run_defeated = []
            name.run_lost_to = []


#: which tiers a starter is drawn from. Medium and High only -- above the
#: junk a rating of 5 would otherwise roll, below the tier that would carry a
#: whole run on its own.
STARTER_TIERS = ("Medium", "High")
#: the largest base stat total a starter may have, per tier. A tier that is
#: not listed here is not capped.
#:
#: Only High is capped, and the asymmetry is the point: High tier is where
#: the 600-total legendaries live, and one of those decides a career in round
#: one. Medium never gets near that, so capping it would only shrink the
#: offer for nothing.
STARTER_MAX_BASE_STATS = {"High": 500}
#: how many to offer
STARTER_CHOICES = 3


def _may_start(mon):
    """Is this Pokemon allowed in the starter offer?"""
    tier = getattr(mon, "tier", None)
    if tier not in STARTER_TIERS:
        return False
    cap = STARTER_MAX_BASE_STATS.get(tier)
    return cap is None or getattr(mon, "total_stats", 0) <= cap


def choose_starter(protagonist):
    """Pick one of three Pokemon to start the career with.

    Name and typing only. Not the ability, not the IVs, not the moveset --
    the first decision of a career should be a read on the type chart and a
    guess, not a spreadsheet comparison, and the rest of the game already has
    plenty of places to inspect a Pokemon properly.

    The pick is appended to the protagonist's team as a *name*, which is
    exactly how every competitor's ace Pokemon is carried (see the `team`
    column in competitors.csv). team_generation then rolls the remaining five
    around it and gives it IVs on the same terms as the rest, so a starter is
    a better *tier* than a rating of 5 would otherwise draw, not a stronger
    individual.
    """
    pool = sorted(name for name, mon in list_of_pokemon.items()
                  if _may_start(mon))
    if len(pool) < STARTER_CHOICES:
        return None                       # nothing to offer; carry on quietly
    offered = random.sample(pool, STARTER_CHOICES)

    print(f"\n{CBOLD}{CYELLOW2}Please choose your starter Pokemon.{CEND}")
    print(f"{CBOLD}This is the one Pokemon you bring to the Championship "
          f"yourself; the other five are drawn around it.{CEND}")
    print(f"{CBOLD}You can see its name and its typing, and nothing else -- "
          f"its ability, its IVs and its moves you find out together.{CEND}")
    for index, name in enumerate(offered):
        typing = "/".join(list_of_pokemon[name].type)
        print(f"{CBOLD}{index}: {name} ({typing}){CEND}")

    chosen = None
    while chosen is None:
        with suppress(ValueError):
            answer = int(input("Please choose your starter "
                                "Pokemon: "))
            if 0 <= answer < len(offered):
                chosen = offered[answer]

    print(f"\n{CBOLD}{CGREEN2}{chosen} joins you. Good luck out there.{CEND}")
    protagonist.team.append(chosen)
    return chosen


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
          "Each trainer has his/her own character ability. Your character ability is the ability to copy one Pokemon of the opponent when emerging victorious.")


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
          f"As the Player, you may do 4 things before entering the battle:\n"
          f"View My Pokemon: have a solid understanding of your team. You want to do this at least once at the start, since you will obtain new Pokemon.\n"
          f"Switch Pokemon Order: you may switch a Pokemon to be the starting Pokemon.\n"
          f"Scout Opponent: know about your next opponent. It will show his/her Character Ability and Signature Pokemon.\n"
          f"                If your ratings are high, you can even know about the starting Pokemon of the opponent, sometimes including its moveset!\n"
          f"                (TIPS: Pokemon with the ability Illuminate can increase the probability of this by 10 times, for ability Pressure 100 times.)\n"
          f"Check History: your record against him/her, and the scoreline of every previous meeting.\n"
          f"If your team has more Pokemon than the round requires, you will have to select some Pokemon that you DO NOT need for this round.\n")
    input("Enter any key to continue...")
    print(f"\nTutorial #3: In Battle\n\n"
          f"I will assume that you are a Pokemon expert when you play this game. Hence, I cannot give you much tips for the battle.\n"
          f"But I would like to remind you that the weather for each battle may have changed. Observe carefully.\n"
          f"For opponent with ratings <30, they are usually more stupid and only rely on attacking moves. Any opponent higher than that ratings can be\n"
          f"a prominent opponent that requires special attention.\n"
          f"However, if you think that your Pokemon is vastly better than your opponent, you may activate Auto Battle with '100'. Sometimes, the AI may\n"
          f"even perform better than you. ^_^\n"
          f"You may receive or swap Pokemon after the battle, depends on the situation.\n")
    input("Enter any key to continue...")
    print(f"\nTutorial #4: End Game\n\n"
          f"Very soon you will play all 5 rounds and receive the result. A large scoreboard will be displayed. However, usually only the Champion matters.\n"
          f"The ranking is based on 3 factors: Points, Net Kill Score and Ratings.\n"
          f"Points: first deciding factor. The higher the points, the higher the ranking.\n"
          f"Opponent Score (OS): second deciding factor. It's the accumulated points of your defeated opponents. The higher the better."
          f"Net Kill Score (NKS): third deciding factor. net number of pokemon you fainted in total.  The higher the better.\n"
          f"Ratings: third deciding factor. The lower the ratings, the higher the ranking.\n"
          f"You will also see how many ratings you gain in this Tournament.\n"
          f"(NOTE: Initially, you may find it difficult to gain ratings. No worries. After some time, you will grasp some win by having a mediocre team.\n"
          f"       When you slowly build up your ratings, it will trigger a snowball effect and you will start having better performance.)\n\n"
          f"That's all for the tutorial! Please enjoy the game for now!\n")
    input("Enter any key to continue...")