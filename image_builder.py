from wand.image import Image
from copy import deepcopy
import os
import requests
import shutil

from Scripts.Data.pokemon import *



def gif_downloader():
    pokemon_list = [mon.lower() for mon in list_of_pokemon if not list_of_pokemon[mon].custom]
    print(pokemon_list)
    url = 'https://projectpokemon.org/images/normal-sprite/'
    for name in pokemon_list:
        name_format = str(name) + '.gif'
        new_url = url + name_format
        img_data = requests.get(new_url, stream=True)

        if img_data.status_code == 200:
            with open(name_format, 'wb') as f:
                shutil.copyfileobj(img_data.raw, f)
            print('Image sucessfully Downloaded: ', name_format)
        else:
            print('Image Couldn\'t be retrieved')


def animation_convertor():
    # used for flipping all animations horizontally
    name_list = [name for name in os.listdir('Assets/pokemon/right/')]
    for name in name_list:
        original_image = name
        new_image = original_image.removesuffix('.gif') + '-left.gif'

        with Image() as output:
            with Image(filename='Assets/pokemon/right/' + original_image) as input:
                for frame in input.sequence:
                    frame.flop()
                    output.sequence.append(frame)
                output.save(filename='Assets/pokemon/left/' + new_image)

        os.rename('Assets/pokemon/right/' + original_image, 'Assets/pokemon/right/' + original_image.removesuffix('.gif') + '-right.gif')


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
