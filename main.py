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
from Scripts.Game import auto_run


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    # Two loops, and the nesting is the whole point. The outer one is the
    # start menu; the inner one plays another career without going back to
    # it. An Auto Run has to repeat *inside* start_game(), because the menu
    # is the one thing it deliberately never answers -- a single loop with a
    # `continue` lands on start_game() again, and the run stops dead there.
    while True:
        start_game()
        while True:
            play_career()
            # An Auto Run cannot go through restart(): that is os.execl,
            # which replaces the process and would take the run's own
            # counter with it.
            if auto_run.state.active and auto_run.finished_one():
                print(f"\nAuto Run: career {auto_run.state.done + 1} "
                      f"of {auto_run.state.total}")
                draw_bracket()          # a fresh tournament, same career
                continue
            break
        if auto_run.state.active:
            total = auto_run.state.total
            auto_run.stop()
            print(f"\nAuto Run finished after {total} "
                  f"career{'' if total == 1 else 's'}. Back to the menu.")
            continue
        restart()


def play_career():
    """One career, from the first round to the final scoreboard."""
    while True:
        # Whatever Assets/music holds, not a range written down here:
        # randint(1, 6) meant a seventh track would never have played,
        # and a missing one would have been a crash mid-career.
        music(audio=start_track(), loop=True)
        # win the tournament
        if list_of_competitors['Protagonist'].stage == 6:
            print("Congratulations! You have won the Pokemon World Championship!!!")
            print(f"You have obtained {list_of_competitors['Protagonist'].championship + 1} World Champion Title(s) in your career!\n")
            music(audio='Assets/music/credits.mp3', loop=False)
            with open('Documentation/credits.md', 'r') as f:
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
    competitor_form()
    save_game()
    input("Press any key to confirm the results.")


if __name__ == "__main__":
    main()
