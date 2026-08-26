import random
from Scripts.Battle.constants import *
from Scripts.Art import narrator


def check_volatile_status(pokemon, move):
    move_execution_inability = False
    volatile_status = {
        "Flinch": flinching,
        "Confused": confusing,
    }
    non_volatile_status = {
        "Fainted": fainting,
        "Sleep": sleeping,
        "Paralysis": paralyzing,
        "Freeze": freezing
    }
    if pokemon.status in non_volatile_status.keys():  # check non_volatile_status first
        move_execution_inability = non_volatile_status[pokemon.status](pokemon, move)
        if move_execution_inability:
            _interrupt_charge(pokemon)
            return move_execution_inability

    for status, consequence in volatile_status.items():  # then volatile status
        if pokemon.volatile_status[status] > 0:
            move_execution_inability = consequence(pokemon, move)
            if move_execution_inability:
                _interrupt_charge(pokemon)
                return move_execution_inability
    return move_execution_inability


def _interrupt_charge(pokemon):
    """Something stopped this Pokemon moving, so a two-turn move is over.

    A Pokemon half-way through Fly, Dig or Dive is *semi-invulnerable* --
    `battle_move_execution` reads `charging[1]` and makes almost everything
    miss it. Falling asleep, freezing or flinching left that state standing:
    the move never resolved, the charge never cleared, and the Pokemon
    stayed untouchable for the rest of the battle while doing nothing. Yawn
    into Fly was the reliable way to see it -- the target dozes off on the
    turn it should have come down, and is immune from then on.

    In the real games an interrupted two-turn move is simply cancelled and
    the Pokemon is back in reach, which is what this does. Charging moves
    (Solar Beam) are cancelled the same way; they were not *hiding* anything,
    but a charge that survives the turn it was supposed to fire on would
    resume out of nowhere later.
    """
    if pokemon.charging[0] != "":
        narrator.say(f"{pokemon.name} could not finish "
                     f"{pokemon.charging[0]}.", "fail")
        pokemon.charging = ["", "", 0]


def fainting(pokemon, move):
    if pokemon.status == "Fainted":
        return True


def sleeping(pokemon, move):
    pokemon.volatile_status["NonVolatile"] -= 1
    if pokemon.volatile_status["NonVolatile"] == 0:
        pokemon.status = "Normal"
        narrator.say(f"{pokemon.name} woke up.")
        return False
    narrator.say(f"{pokemon.name} is fast asleep.")
    return True


def paralyzing(pokemon, move):
    if random.random() <= 0.25:
        narrator.say(f"{pokemon.name} is paralyzed! It can't move!")
        return True
    return False


def freezing(pokemon, move):
    if random.random() <= 0.8:
        narrator.say(f"{pokemon.name} is frozen! It can't move!")
        return True
    pokemon.status = "Normal"
    narrator.say(f"{pokemon.name} has thawed out.")
    return False


def flinching(pokemon, move):
    narrator.say(f"{pokemon.name} flinched! It can't move!")
    return True


def confusing(pokemon, move):
    # typeless power 40 physical move
    if random.random() <= 1 / 3:
        damage = math.floor(
            (((((2 * 100 / 5) + 2) * 40 * pokemon.battle_stats[1] / pokemon.battle_stats[2]) / 50) + 2) * (random.randint(85, 100) / 100))
        pokemon.battle_stats[0] -= damage
        narrator.say(f"{pokemon.name} hurts itself, reducing {damage} HP.")
        return True
    return False