import random
from competitors import *


class GameSystem:
    def __init__(self):
        self.participants = [name for name in list_of_competitors if list_of_competitors[name].level in ("Champion", "Protagonist")]
        self.participants += random.sample([name for name in list_of_competitors if list_of_competitors[name].level == "Elite"], k=random.randint(3, 5))
        self.competitor_list = [name for name in list_of_competitors if list_of_competitors[name].level in ("Low", "Intermediate", "Advanced")]
        self.stage = 1


GameSystem = GameSystem()
