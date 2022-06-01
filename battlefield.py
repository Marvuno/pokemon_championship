from weather import *


class Battleground:
    def __init__(self):
        self.turn = 1
        self.verbose = False
        self.auto_battle = False
        self.starting_weather_effect = Clear
        self.weather_effect = Clear()
        self.artificial_weather = False
        self.battle_continuation = True
        # stackable
        self.field_effect = {
            "Trick Room": 0,
        }

