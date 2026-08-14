import random
import sys
from contextlib import suppress
from copy import deepcopy

from Scripts.Game.game_procedure import *
from Scripts.Art.text_color import *
from Scripts.Data.competitors import *
from Scripts.Battle.constants import *



#: pre-battle menu: value -> (handler name, label). Quit Game is gone -- the
#: window has a close button and Escape, and the old option quietly committed
#: the run (it called elo_rating() and save_game() on the way out), which is
#: not what "quit" implies.
MENU = ((0, "proceed_to_battle", "Battle"),
        (1, "view_pokemon", "View My Pokemon"),
        (2, "switch_order", "Switch Pokemon Order"),
        (3, "about_opponent", "Scout Opponent"),
        (4, "check_history", "Check History"))


def before_battle_option(protagonist, opponent):
    """The pre-battle menu, until the player picks Battle.

    Errors are handled per case rather than by wrapping the whole thing in
    suppress(ValueError, KeyError). That blanket used to swallow anything a
    handler raised, so a real bug in one of these screens looked exactly like
    a menu option that did nothing -- which is how a KeyError in Check
    History went unnoticed. A bad number is now answered, and anything
    unexpected is reported instead of vanishing.
    """
    handlers = {value: globals()[name] for value, name, _ in MENU}
    text = ("What do you want to do?\n"
            + " || ".join("%d: %s" % (value, label)
                          for value, _, label in MENU)
            + "\n--> ")
    while True:
        print("")
        answer = input(text).strip()
        print("")
        if not answer.lstrip("-").isdigit():
            print(f"{CGREY}Please enter one of the numbers above.{CEND}")
            continue
        option = int(answer)
        if option not in handlers:
            print(f"{CGREY}There is no option {option}. "
                  f"Pick one of the numbers above.{CEND}")
            continue
        try:
            handlers[option](protagonist, opponent)
        except Exception as error:
            # Report and carry on. Losing a run to a crash in an optional
            # information screen would be far worse than showing less of it.
            print(f"{CRED}Sorry -- that screen could not be shown "
                  f"({type(error).__name__}). Nothing has been lost; "
                  f"pick another option.{CEND}")
            continue
        if option == 0:
            return


def proceed_to_battle(protagonist, opponent):
    print(f"{CBOLD}Round {GameSystem.stage}{CEND}")
    print(f"{CWHITE2}{CBOLD}{protagonist.nickname} [{protagonist.strength}] VS {opponent.nickname} [{opponent.strength}]{CEND}")
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


def scout_chance(protagonist, opponent):
    """Odds of learning anything about this opponent.

    Your rating against theirs, multiplied by Illuminate (x10) or Pressure
    (x100) on any Pokemon you brought -- stackable, as before.
    """
    prob = protagonist.strength / (opponent.strength + protagonist.strength)
    special_ability = {"Illuminate": 10, "Pressure": 100}
    for pokemon in protagonist.team:
        for ability in pokemon.ability:
            if ability in special_ability:
                prob *= special_ability[ability]
    return prob


def scout_result(protagonist, opponent):
    """Whether the scouting worked, rolled once per round and remembered.

    Scout Opponent can now be opened as often as you like, so the roll can't
    happen per visit -- that would let you re-roll a failure by clicking
    again. It is taken on the first visit of the round and kept on the
    opponent, tagged with the round it belongs to so the next match rolls
    fresh.
    """
    stamp = getattr(opponent, "scouted", None)
    if isinstance(stamp, tuple) and stamp[0] == GameSystem.stage:
        return stamp[1]
    outcome = random.random() <= scout_chance(protagonist, opponent)
    opponent.scouted = (GameSystem.stage, outcome)
    return outcome


def about_opponent(protagonist, opponent):
    print(f"{CBOLD}{opponent.nickname} | Tier: {opponent.level}\n{CYELLOW}{opponent.desc}{CEND}\n")
    print(f"Before the match begins, you approach your opponent {opponent.nickname} and introduce yourself.\nAfter a delightful chitchat...")
    if scout_result(protagonist, opponent):
        # A success now opens up their whole team rather than naming their
        # lead: the interface has a team viewer that can show it properly,
        # which is a far better prize than one name and a maybe-moveset.
        print(f"You have sized up {CVIOLET2}{CBOLD}{opponent.nickname}{CEND}'s entire team:")
        for index, pokemon in enumerate(opponent.team):
            print(f"  {index}: {CVIOLET2}{CBOLD}{pokemon.name}{CEND}")
        print(f"\n{CBEIGE2 + CBOLD}{opponent.strategy}{CEND}")
    else:
        print("Unfortunately, you fail to obtain any useful information.")


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


def head_to_head(protagonist, opponent):
    """Your record against this competitor, as [wins, losses].

    opponent_history is keyed by competitor *name*, while almost everything
    else in the game identifies a competitor by nickname -- and a saved copy
    of the dict only covers the roster as it stood when that save was
    written. Looking the record up by either key and falling back to a
    clean slate is what stops "someone you have never faced" from being an
    error: renaming a competitor in Data/competitors.csv used to make Check
    History raise KeyError against every older save.
    """
    history = getattr(protagonist, "opponent_history", None) or {}
    record = history.get(getattr(opponent, "name", None))
    if record is None:
        record = history.get(getattr(opponent, "nickname", None))
    return record if record else [0, 0]


def check_history(protagonist, opponent):
    """Your record against this opponent, and how each meeting went.

    Deliberately just that. It used to print both competitors' whole
    tournament journeys and then offer another page of career history, none
    of which is about the match you are seconds away from -- and all of which
    is still on the main menu's HISTORY screen.
    """
    wins, losses = head_to_head(protagonist, opponent)
    played = wins + losses
    print(f"{CBOLD}{protagonist.nickname}  {wins} - {losses}  {opponent.nickname}{CEND}")
    if not played:
        print(f"{CGREY}You have never faced {opponent.nickname} before.{CEND}")
        return

    print(f"\nYou have met {played} time{'' if played == 1 else 's'}.")
    scores = (getattr(protagonist, "opponent_scores", None) or {}).get(
        getattr(opponent, "name", None)) or []
    if not scores:
        return
    print(f"\n{CBOLD}Every meeting:{CEND}")
    for index, pair in enumerate(scores, start=1):
        mine, theirs = (list(pair) + [0, 0])[:2]
        # Three-way, not won/lost: the tournament settles a level match on
        # rating, so the recorded scoreline should never be equal -- but
        # labelling an equal one "lost" would be simply untrue.
        colour = CGREEN2 if mine > theirs else CGREY if mine == theirs else CRED
        outcome = "won" if mine > theirs else "drew" if mine == theirs \
            else "lost"
        print(f"  #{index}: {colour}{mine} - {theirs}{CEND} "
              f"({outcome})")
