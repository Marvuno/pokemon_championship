import random
import math
from contextlib import suppress
from text_color import *
from weather import *
from pokemon import *
from abilities import *
from battlefield import *
from entry_hazard import *
from volatile_status_condition import *
from type_chart import *
from moves import *
from start_interface import *
from competitors import *
from damage_calculation import *
from move_additional_effect import *
from text_color import *
from game_procedure import *
from ai import *
from music import *
from constants import *
from game_system import *
from battle_initialization import *
from copy import deepcopy


# switching
def switching_criteria(protagonist, competitor, user_team, opponent_team, battleground, forced_switch=False, transfer=False):
    if not forced_switch and user_team[0].status != "Fainted":
        if user_team[0].volatile_status['Binding'] > 0 or user_team[0].volatile_status['Trapped'] > 0:
            if 'Ghost' not in user_team[0].type:
                print("The pokemon cannot be switched out!")
                return user_team[0]

    position_change = 0
    while not (1 <= position_change < len(user_team)):
        for index, pokemon in enumerate(user_team):
            print(f"{CWHITE2}{index}: {pokemon.name}{CEND}")
        with suppress(ValueError, IndexError):
            position_change = int(input(f'Which pokemon would you like to switch in?\n8: View your pokemon\n9: Return to battle\n--> '))
            if not forced_switch and position_change == 9:
                if user_team[0].status == "Fainted":
                    print("The pokemon in battle has fainted. Choose one.")
                else:
                    return user_team[0]
            elif position_change == 8:
                for i, pokemon in enumerate(user_team):
                    if i % 2 == 0:
                        print(CBEIGE, end='')
                    print(f"ID: {pokemon.id} || Name: {pokemon.name} || Type: {pokemon.type}")
                    print(f"Ability: {pokemon.ability}")
                    print("Battle Stats:", [f"{STATISTICS[x]}: {pokemon.battle_stats[x]}" for x in range(len(pokemon.battle_stats))])
                    print("Status:", pokemon.status)
                    print(f"Moveset: {pokemon.moveset}{CEND}\n")
                print(CBOLD + "Entry Hazard on Field:", protagonist.entry_hazard)
                print("Team Buff on Field:", protagonist.in_battle_effects, "\n" + CEND)

            elif user_team[position_change].status == "Fainted":
                print("The pokemon you select has fainted. Choose another one.")
                position_change = 0

    return switching_mechanism(protagonist, competitor, battleground, user_team, opponent_team, position_change, transfer)


def switching_mechanism(user, opponent, battleground, user_team, opponent_team, position_change, transfer):
    # only happen in baton pass
    if transfer:
        user_team[position_change].modifier = user_team[0].modifier
        user_team[position_change].volatile_status = user_team[0].volatile_status
    # reset modifier upon switching
    user_team[0].modifier = [0] * 9
    user_team[0].protection = [0, 0]
    user_team[0].charging = ["", "", 0]
    user_team[0].disabled_moves = {}
    user_team[0].previous_move = ""
    # reset volatile status except sleeping turns
    sleeping_turn = user_team[0].volatile_status["NonVolatile"] if user_team[0].status == "Sleep" else 0
    user_team[0].volatile_status = dict.fromkeys(user_team[0].volatile_status.keys(), 0)
    user_team[0].volatile_status["NonVolatile"] = sleeping_turn
    # reset trapping
    opponent_team[0].volatile_status['Trapped'], opponent_team[0].volatile_status['Binding'], opponent_team[0].volatile_status['Octolock'] = 0, 0, 0

    # triggering abilities when switched out
    UseAbility(user, opponent, user_team[0], opponent_team[0], battleground, "", abilityphase=9)

    user_team[0], user_team[position_change] = user_team[position_change], user_team[0]  # switch pokemon
    print(f"{CVIOLET2}{CBOLD}{user_team[0].name} is switched in!{CEND}")

    # triggering entry hazard
    entry_hazard_effect(user, user_team[0])

    switched_in_initialization(user, opponent, user_team[0], opponent_team[0], battleground)

    if user.main:
        sound(audio="music/confirm.mp3")
    elif not user.main:
        if sum(1 for pokemon in user.team if pokemon.status != "Fainted") == 1:
            colors = {"": CWHITE2, "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}
            print(f"{colors[user.color]}{CBOLD}{user.name}: {user.quote}{CEND}")  # will add quotes on competitor
            music(audio=user.ace_music, loop=True)

    return user_team[0]
