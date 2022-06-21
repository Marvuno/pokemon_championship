import random
import math
from contextlib import suppress
from copy import deepcopy

from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Data.abilities import *
from Scripts.Data.character_abilities import *
from Scripts.Data.moves import *
from Scripts.Data.competitors import *
from Scripts.Battle.entry_hazard import *
from Scripts.Battle.type_chart import *
from Scripts.Battle.ai import *
from Scripts.Battle.constants import *
from Scripts.Battle.battle_initialization import *


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
            print(f"{CWHITE2}{index}: {pokemon.name}{' (Fainted)' if pokemon.status == 'Fainted' else ''}{CEND}")
        with suppress(ValueError, IndexError):
            position_change = int(input(f'Which pokemon would you like to switch in?\n8: View your pokemon\n9: Return to battle\n--> '))
            if not forced_switch and position_change == 9:
                if user_team[0].status == "Fainted":
                    print("The pokemon in battle has fainted. Choose one.")
                else:
                    return user_team[0]
            elif position_change == 8:
                for i, pokemon in enumerate(user_team):
                    print(f"{CBEIGE+CBOLD if i % 2 == 0 else CBOLD}ID: {pokemon.id} || Name: {pokemon.name}{' (Fainted)' if pokemon.status == 'Fainted' else ''} || Type: {pokemon.type}")
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
    # reset opponent trapping
    opponent_team[0].volatile_status['Trapped'], opponent_team[0].volatile_status['Binding'], opponent_team[0].volatile_status['Octolock'] = 0, 0, 0
    # reset typing & abilities
    user_team[0].name, user_team[0].ability, user_team[0].type = user_team[0].default_name, user_team[0].default_ability, user_team[0].default_type
    user_team[0].nominal_base_stats = user_team[0].default_nominal_base_stats
    # reset move history
    user_team[0].move_order = []

    # triggering abilities when switched out
    UseAbility(user, opponent, user_team[0], opponent_team[0], battleground, "", abilityphase=9)
    UseCharacterAbility(user, opponent, user_team[0], opponent_team[0], battleground, "", abilityphase=9)
    user_team[0], user_team[position_change] = user_team[position_change], user_team[0]  # switch pokemon

    # grounded
    if not ("Flying" in user_team[0].type or user_team[0].ability == "Levitate"):
        user_team[0].volatile_status['Grounded'] = 1

    # triggering entry hazard
    entry_hazard_effect(user, user_team[0])

    if user.main:
        sound(audio="Assets/music/confirm.mp3")
    elif not user.main:
        if sum(1 for pokemon in user.team if pokemon.status != "Fainted") == 1:
            colors = {"": CWHITE2, "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}
            print(f"\n{colors[user.color]}{CBOLD}{user.nickname}: {user.quote}{CEND}")  # will add quotes on competitor
            music(audio=f"Assets/music/{user.ace_music}", loop=True)

    return user_team[0]
