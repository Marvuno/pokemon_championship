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
from Scripts.Battle.context import Side, Turn
from Scripts.Battle.battle_initialization import *
import Scripts.Battle.battle_move_execution as battle_move_execution
from Scripts.Art import narrator


# switching
#: Character abilities that hold both sides in place for as long as their owner
#: is in the match. Checked directly rather than trusted to the Trapped
#: volatile: that flag is set once when a Pokemon is switched in, and the
#: switch itself then wipes the incoming Pokemon's volatile status (see the
#: reset below) while only the *switching* side's switch-in abilities re-fire.
#: So the opposing Naive never re-applied, and every switch after the first was
#: free -- which is why Pudding could be switched away from at will.
TRAPPING_CHARACTER_ABILITIES = ("Naive",)


def switching_criteria(protagonist, competitor, user_team, opponent_team, battleground, forced_switch=False, transfer=False):
    if not forced_switch and user_team[0].status != "Fainted":
        # `competitor` is always the other side, whichever side is switching
        held = str(getattr(competitor, 'ability', '') or '') in TRAPPING_CHARACTER_ABILITIES
        if (user_team[0].volatile_status['Binding'] > 0
                or user_team[0].volatile_status['Trapped'] > 0
                or held):
            if 'Ghost' not in user_team[0].type:
                narrator.say("The pokemon cannot be switched out!", "fail")
                return user_team[0]

    position_change = 0
    while not (1 <= position_change < len(user_team)):
        for index, pokemon in enumerate(user_team):
            narrator.say(f"{CWHITE2}{index}: {pokemon.name}{' (Fainted)' if pokemon.status == 'Fainted' else ''}{CEND}")
        with suppress(ValueError, IndexError):
            position_change = int(input(f'Which pokemon would you like to switch in?\n8: View your pokemon\n9: Return to battle\n--> '))
            if not forced_switch and position_change == 9:
                if user_team[0].status == "Fainted":
                    narrator.say("The pokemon in battle has fainted. Choose one.")
                else:
                    return user_team[0]
            elif position_change == 8:
                for i, pokemon in enumerate(user_team):
                    narrator.say(f"{CBEIGE+CBOLD if i % 2 == 0 else CBOLD}ID: {pokemon.id} || Name: {pokemon.name}{' (Fainted)' if pokemon.status == 'Fainted' else ''} || Type: {pokemon.type}")
                    narrator.say(f"Ability: {pokemon.ability}")
                    print("Battle Stats:", [f"{STATISTICS[x]}: {pokemon.battle_stats[x]}" for x in range(len(pokemon.battle_stats))])
                    print("Status:", pokemon.status)
                    narrator.say(f"Moveset: {pokemon.moveset}{CEND}\n")
                print(CBOLD + "Entry Hazard on Field:", protagonist.entry_hazard)
                print("Team Buff on Field:", protagonist.in_battle_effects, "\n" + CEND)

            elif user_team[position_change].status == "Fainted":
                narrator.say("The pokemon you select has fainted. Choose another one.")
                position_change = 0

    return switching_mechanism(protagonist, competitor, battleground, user_team, opponent_team, position_change, transfer)


def switching_mechanism(user, opponent, battleground, user_team, opponent_team, position_change, transfer):
    battle_move_execution.check_fainted(user_team[0], opponent_team[0])
    # only happen in baton pass
    if transfer:
        user_team[position_change].modifier = user_team[0].modifier
        user_team[position_change].volatile_status = user_team[0].volatile_status
    # reset modifier upon switching
    user_team[0].modifier = [0] * 9
    user_team[0].protection = [0, 0]
    user_team[0].charging = ["", "", 0]
    # A move locked away is locked for the Pokemon standing there, not for
    # the rest of the battle -- leaving the field clears every source of a
    # lock at once (Disable, Cursed Body, the Torment character ability),
    # because they all write to this one dict.
    user_team[0].disabled_moves = {}
    user_team[0].previous_move = ""
    # reset volatile status except sleeping turns
    sleeping_turn = user_team[0].volatile_status["NonVolatile"] if user_team[0].status == "Sleep" else 0
    user_team[0].volatile_status = dict.fromkeys(user_team[0].volatile_status.keys(), 0)
    user_team[0].volatile_status["NonVolatile"] = sleeping_turn
    # reset opponent trapping
    opponent_team[0].volatile_status['Trapped'], opponent_team[0].volatile_status['Binding'], opponent_team[0].volatile_status['Octolock'] = 0, 0, 0
    # reset typing & abilities -- as copies, because the live typing is what
    # add_target_type moves extend, and sharing the list with the default
    # meant the "reset" restored an already-rewritten default
    user_team[0].name = user_team[0].default_name
    user_team[0].ability = list(user_team[0].default_ability)
    user_team[0].type = list(user_team[0].default_type)
    user_team[0].nominal_base_stats = list(user_team[0].default_nominal_base_stats)
    # reset move history
    user_team[0].move_order = []
    # and what it learned about the Pokemon it was facing: a fresh Pokemon has
    # not tried anything yet, and the verdicts were about a matchup that is
    # over
    user_team[0].ineffective_moves = {}

    # triggering abilities when switched out
    # built here rather than earlier: these read user_team[0] at the moment
    # they fire, and the switch below is about to change it
    leaving = Turn(battleground,
                   Side(user, user_team, user_team[0]),
                   Side(opponent, opponent_team, opponent_team[0]))
    UseAbility(leaving, "", abilityphase=9)
    UseCharacterAbility(leaving, "", abilityphase=9)
    user_team[0], user_team[position_change] = user_team[position_change], user_team[0]  # switch pokemon

    switched_in_initialization(user, opponent, user_team[0], opponent_team[0], battleground)
    narrator.switched_in(user.side_color, user.team[0].name)

    # triggering entry hazard
    entry_hazard_effect(user, user_team[0])

    if user.main:
        sound(audio="Assets/music/confirm.mp3")
    elif not user.main:
        if sum(1 for pokemon in user.team if pokemon.status != "Fainted") == 1:
            narrator.say(f"\n{CWHITE2}{CBOLD}{user.nickname}: {user.quote}{CEND}")  # will add quotes on competitor
            music(audio=f"Assets/music/{user.ace_music}", loop=True)

    return user_team[0]
