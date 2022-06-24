from Scripts.Data.abilities import *
from Scripts.Data.character_abilities import *
import numpy as np


def switched_in_initialization(user_side, opponent_side, user, opponent, battleground):
    # grounded
    if not ("Flying" in user.type or user.ability == "Levitate"):
        user.volatile_status['Grounded'] = 1
    user.volatile_status['Turn'] += 1
    # switched in ability
    UseCharacterAbility(user_side, opponent_side, user, opponent, battleground, "", abilityphase=1)
    UseAbility(user_side, opponent_side, user, opponent, battleground, "", abilityphase=1)


def multi_strike_move(move):
    # variable multi-strike move
    if move.multi[0] == 1:
        return np.random.choice([2, 3, 4, 5], p=[0.35, 0.35, 0.15, 0.15])
    elif move.multi[0] == 2:  # for move like triple axel
        strikes = np.random.choice([0, 1, 2, 3], p=[(1 - move.accuracy), (1 - move.accuracy) * move.accuracy, (1 - move.accuracy) * (move.accuracy ** 2), move.accuracy ** 3])
        move.accuracy = 1
        return strikes
    return move.multi[1]


def pre_move_adjustment(user_side, opponent_side, user, opponent, battleground, move):
    if move.name != "Switching":
        if move.name == "Metronome":
            print(f"{user.name} used Metronome.")
            metronome_move_list = list(set(list_of_moves.keys()) - {"Baneful Bunker", "Counter", "Protect", "King's Shield", "Mirror Coat", "Metronome"})
            move = list_of_moves[random.choice(metronome_move_list)]
        UseAbility(user_side, opponent_side, user, opponent, battleground, move, abilityphase=2)
        UseCharacterAbility(user_side, opponent_side, user, opponent, battleground, move, abilityphase=2)
    user.move_order.append(move.name)
    return move
