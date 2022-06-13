import random
from constants import *


def Flinch(effect_accuracy):
    return ["Flinch", 1] if random.random() <= effect_accuracy else ["", 0]


def Confused(effect_accuracy):
    return ["Confused", random.randint(2, 5)] if random.random() <= effect_accuracy else ["", 0]


def Frighten(effect_accuracy):
    return ["Frighten", 3] if random.random() <= effect_accuracy else ["", 0]


def Poison(effect_accuracy):
    return ["Poison", 0] if random.random() <= effect_accuracy else ["Normal", 0]


def BadPoison(effect_accuracy):
    return ["BadPoison", 0] if random.random() <= effect_accuracy else ["Normal", 0]


def Paralysis(effect_accuracy):
    return ["Paralysis", 0] if random.random() <= effect_accuracy else ["Normal", 0]


def Burn(effect_accuracy):
    return ["Burn", 0] if random.random() <= effect_accuracy else ["Normal", 0]


def Sleep(effect_accuracy):
    return ["Sleep", random.randint(1, 3)] if random.random() <= effect_accuracy else ["Normal", 0]


def Freeze(effect_accuracy):
    return ["Freeze", 0] if random.random() <= effect_accuracy else ["Normal", 0]


def Tri(effect_accuracy):  # tri attack
    return [random.choice(["Burn", "Paralysis", "Freeze"]), 0] if random.random() <= effect_accuracy else ["Normal", 0]


def Binding(effect_accuracy):
    return ["Binding", random.randint(4, 5)] if random.random() <= effect_accuracy else ["", 0]


def Trapped(effect_accuracy):
    return ["Trapped", 1] if random.random() <= effect_accuracy else ["", 0]


def Octolock(effect_accuracy):
    return ["Octolock", 1] if random.random() <= effect_accuracy else ["", 0]


def DestinyBond(effect_accuracy):
    return ["DestinyBond", 1] if random.random() <= effect_accuracy else ["", 0]


def PerishSong(effect_accuracy):
    return ["PerishSong", 1] if random.random() <= effect_accuracy else ["", 0]


def Torment(effect_accuracy):
    return ["Torment", 5] if random.random() <= effect_accuracy else ["", 0]


def Yawn(effect_accuracy):
    return ["Yawn", 3] if random.random() <= effect_accuracy else ["", 0]


def Grounded(effect_accuracy):
    return ["Grounded", 1] if random.random() <= effect_accuracy else ["", 0]


def Ungrounded(effect_accuracy):
    return ["Grounded", 0] if random.random() <= effect_accuracy else ["", 0]


def TotalConcentration(effect_accuracy):
    return ["TotalConcentration", 1] if random.random() <= effect_accuracy else ["", 0]


def LeechSeed(effect_accuracy):
    return ["LeechSeed", 1] if random.random() <= effect_accuracy else ["", 0]


def Ingrain(effect_accuracy):
    return ["Ingrain", 1] if random.random() <= effect_accuracy else ["", 0]


def AquaRing(effect_accuracy):
    return ["AquaRing", 1] if random.random() <= effect_accuracy else ["", 0]


def TakeAim(effect_accuracy):
    return ["TakeAim", 2] if random.random() <= effect_accuracy else ["", 0]