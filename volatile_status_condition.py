import random
import math
from constants import *
from contextlib import suppress


def check_volatile_status(pokemon, move):
    move_execution_inability = False
    volatile_status = {
        "Flinched": flinching,
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
            return move_execution_inability

    for status, consequence in volatile_status.items():  # then volatile status
        if pokemon.volatile_status[status] > 0:
            move_execution_inability = consequence(pokemon, move)
            if move_execution_inability:
                return move_execution_inability
    return move_execution_inability


def fainting(pokemon, move):
    if pokemon.status == "Fainted":
        return True


def sleeping(pokemon, move):
    if pokemon.volatile_status["NonVolatile"] == 0:
        pokemon.status = "Normal"
        print(f"{pokemon.name} woke up.")
        return False
    pokemon.volatile_status["NonVolatile"] -= 1
    print(f"{pokemon.name} is fast asleep.")
    return True


def paralyzing(pokemon, move):
    if random.random() <= 0.25:
        print(f"{pokemon.name} is paralyzed! It can't move!")
        return True
    return False


def freezing(pokemon, move):
    if random.random() <= 0.8:
        print(f"{pokemon.name} is frozen! It can't move!")
        return True
    pokemon.status = "Normal"
    print(f"{pokemon.name} has thawed out.")
    return False


def flinching(pokemon, move):
    print(f"{pokemon.name} flinched! It can't move!")
    return True


def confusing(pokemon, move):
    # typeless power 40 physical move
    if random.random() <= 1 / 3:
        damage = math.floor(
            (((((2 * 100 / 5) + 2) * 40 * pokemon.battle_stats[1] / pokemon.battle_stats[2]) / 50) + 2) * (random.randint(85, 100) / 100))
        pokemon.battle_stats[0] -= damage
        print(f"{pokemon.name} hurts itself, reducing {damage} HP.")
        return True
    return False