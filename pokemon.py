from random import randint
import math
import operator
from moves import *
import csv


class Pokemon:
    def __init__(self, id, name, base_stats, type, ability, moveset, tier):
        self.id = id
        self.name = name
        self.type = type
        self.base_stats = base_stats
        self.iv, self.nominal_base_stats = 0, 0
        self.previous_move = ""
        self.modifier = [0] * 9
        self.applied_modifier = [0] * 9
        self.status = "Normal"
        self.moveset = moveset
        # tier list for pokemon selection
        self.tier = tier
        self.ability = ability
        self.volatile_status = {
            "NonVolatile": 0,
            "Flinched": 0,
            "Confused": 0,
            "Curse": 0,
            "Destiny Bond": 0,
            "Perish Song": 0,
            "Torment": 0,
            "Binding": 0,
            "Trapped": 0,
            "Leech Seed": 0,
            "Ingrain": 0,
            "Aqua Ring": 0,
            "Octolock": 0,
            "Total Concentration": 0,
            "Yawn": 0,
            "Flash Fire": 0,
            "Take Aim": 0,
            "Grounded": 0,
            "Turn": 0,
        }
        self.protection = [0, 0]
        # move name, move efect (charging / semi-invulnerable / consecutive), number of turn to end
        self.charging = ["", "", 0]
        # disabled moves
        self.disabled_moves = {}
        # other individual factors
        self.disguise, self.transform = False, False


with open('csv/pokemon.csv', encoding="ISO-8859-1") as f:
    reader = csv.DictReader(f)
    list_of_pokemon = {}
    for row in reader:
        base_stats = [int(row['HP']), int(row['Atk']), int(row['Def']), int(row['SpA']), int(row['SpDef']), int(row['Spd'])]
        typing = [row['Type']] if row['SType'] == '' else [row['Type'], row['SType']]
        abilities = [row['Ability']] if row['SAbility'] == '' else [row['Ability'], row['SAbility']]
        moveset = []
        for i in range(1, 7):
            if row[f'Move{i}'] != '':
                moveset.append(row[f'Move{i}'])
        list_of_pokemon[row['Name']] = Pokemon(row['ID'], row['Name'], base_stats, typing, abilities, moveset, row['Tier'])
