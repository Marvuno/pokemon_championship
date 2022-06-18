import csv
import random
from copy import deepcopy
from pokemon import *


def custom_team(participant):
    with open('csv/custom_team.csv', encoding="ISO-8859-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_id = row['ID']
            name = row['Name']
            pokemon = row['Pokemon']
            iv = int(row['IV'])
            ability = row['Ability']
            moveset = [row[f'Move{i}'] for i in range(1, 5)]

            if participant.raw_id == raw_id:
                pokemon = deepcopy(list_of_pokemon[pokemon])
                pokemon.iv = [random.randint(iv, max(31, iv)) for _ in range(6)]
                pokemon.ability = [ability]
                pokemon.moveset = moveset
                participant.team.append(pokemon)