import random
from copy import deepcopy

from Scripts.Data.abilities import *
from Scripts.Data.character_abilities import *
from Scripts.Battle.constants import has_ability
from Scripts.Battle.context import Side, Turn
from Scripts.Battle.fastcopy import fast_copy
from Scripts.Art import narrator


def switched_in_initialization(user_side, opponent_side, user, opponent, battleground):
    # grounded
    # has_ability, not `user.ability == "Levitate"`: ability is a list, and a
    # list never equals a string, so every Levitate holder was being grounded
    # -- hit by Ground moves, Spikes, Toxic Spikes and Sticky Web alike.
    if not ("Flying" in user.type or has_ability(user, "Levitate")):
        user.volatile_status['Grounded'] = 1
    user.volatile_status['Turn'] += 1
    # switched in ability
    arriving = Turn(battleground,
                    Side(user_side, getattr(user_side, 'team', []), user),
                    Side(opponent_side, getattr(opponent_side, 'team', []),
                         opponent))
    UseCharacterAbility(arriving, "", abilityphase=1)
    UseAbility(arriving, "", abilityphase=1)


def multi_strike_move(move):
    """How many times this move connects.

    random.choices, not np.random.choice. numpy carries its own random
    number generator, and `random.seed()` does not touch it -- so the engine
    was drawing from two independent streams and seeding only one. A battle
    could not be replayed from a seed, which meant no engine change could be
    checked by running the same battle before and after. One generator, and
    a seed now reproduces a battle exactly.
    """
    # variable multi-strike move
    if move.multi[0] == 1:
        return random.choices([2, 3, 4, 5], weights=[0.35, 0.35, 0.15, 0.15])[0]
    elif move.multi[0] == 2:  # for move like triple axel
        # Clamped, because these weights are built out of the move's accuracy
        # and a negative weight is an error rather than an unlikely outcome.
        # Accuracy is a probability everywhere else; GUARANTEE_ACCURACY (9)
        # is a sentinel meaning "cannot miss", so read it as certainty.
        accuracy = min(1.0, max(0.0, move.accuracy))
        strikes = random.choices(
            [0, 1, 2, 3],
            weights=[(1 - accuracy), (1 - accuracy) * accuracy,
                     (1 - accuracy) * (accuracy ** 2), accuracy ** 3])[0]
        move.accuracy = 1
        return strikes
    return move.multi[1]


def pre_move_adjustment(user_side, opponent_side, user, opponent, battleground, move):
    """Settled before the turn runs: how many strikes, and what Metronome
    turned into.

    Deliberately no longer fires ability phase 2. compare_speed calls this for
    *both* sides before either move executes, so a Protean or Libero user had
    already changed type before it had moved -- and if the other side moved
    first, its attack was worked out against the new type instead of the one
    the Pokemon was still wearing. Phase 2 now fires in
    on_move_used(), at the moment that Pokemon's own move goes off.
    """
    if move.name != "Switching":
        if move.name == "Metronome":
            narrator.say(f"{user.name} used Metronome.")
            metronome_move_list = sorted(set(list_of_moves.keys()) - {"Baneful Bunker", "Counter", "Protect", "King's Shield", "Mirror Coat", "Metronome"})
            # deepcopy: everything downstream writes its per-use working
            # state onto the move it is given (damage, accuracy, whether it
            # was super effective), and the entries of list_of_moves are
            # shared by every Pokemon in the game. sorted(), too -- set
            # iteration order is not stable across runs, so an unsorted list
            # made Metronome unreproducible even from a fixed seed.
            move = fast_copy(list_of_moves[random.choice(metronome_move_list)])
    user.move_order.append(move.name)
    return move


def on_move_used(user_side, opponent_side, user, opponent, battleground, move):
    """The abilities that fire as a Pokemon uses a move -- Protean and Libero
    changing type to match it. Called when the move actually executes, so the
    change lands in move order rather than before the turn."""
    if move.name != "Switching":
        acting = Turn(battleground,
                      Side(user_side, getattr(user_side, 'team', []), user),
                      Side(opponent_side, getattr(opponent_side, 'team', []),
                           opponent))
        UseAbility(acting, move, abilityphase=2)
        UseCharacterAbility(acting, move, abilityphase=2)
