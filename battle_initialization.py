from abilities import *


def switched_in_initialization(user_side, opponent_side, user, opponent, battleground):
    # grounded
    if not ("Flying" in user.type or user.ability == "Levitate"):
        user.volatile_status['Grounded'] = 1
    # switched in ability
    UseAbility(user_side, opponent_side, user, opponent, battleground, "", abilityphase=1)


def multi_strike_move(move):
    # variable multi-strike move
    if move.multi[0]:
        return random.choice([2] * 35 + [3] * 35 + [4] * 15 + [5] * 15)
    elif move.multi[2]:  # for move like triple axel
        return random.choice([1] * 90 + [2] * 81 + [3] * 729)
    return 1


def pre_move_adjustment(user_side, opponent_side, user, opponent, battleground, move):
    if move.name != "Switching":
        if move.name == "Metronome":
            print(f"{user.name} used Metronome.")
            metronome_move_list = list(set(list_of_moves.keys()) - {"Baneful Bunker", "Counter", "Protect", "King's Shield", "Mirror Coat", "Metronome"})
            move = list_of_moves[random.choice(metronome_move_list)]
        # variable multi-strike move
        if move.multi[0]:
            move.multi[1] = random.choice([2] * 35 + [3] * 35 + [4] * 15 + [5] * 15)
        UseAbility(user_side, opponent_side, user, opponent, battleground, move, abilityphase=2)
    return move
