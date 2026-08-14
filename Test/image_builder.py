from wand.image import Image
from copy import deepcopy
import os
import requests
import shutil

from Scripts.Data.pokemon import *



def image_name_list():
    available_image_name_list = []
    not_available_image_name_list = []
    pokemon_list = [mon for mon in list_of_pokemon]
    region_conversion = {'alolan': 'alola', 'galarian': 'galar', 'krusadian': 'krusades'}

    for name in pokemon_list:
        original_name = deepcopy(name)
        name = name.lower().replace("(", "").replace(")", "").replace("'", "-").replace(" ", "-").replace("forme", "")
        for key, value in region_conversion.items():
            if key in name:
                name = name.replace(key + '-', '') + '-' + value

        if not list_of_pokemon[original_name].custom and list_of_pokemon[original_name].name != "Spectrier":
            available_image_name_list.append(name)
        else:
            not_available_image_name_list.append(name)

    for name in available_image_name_list:
        print(name)

    print()
    for name in not_available_image_name_list:
        print(name)


image_name_list()
