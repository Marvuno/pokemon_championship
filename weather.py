from constants import *


class Weather:
    def __init__(self):
        self.turn = 0


class Clear(Weather):
    def __init__(self):
        super().__init__()
        self.id = 0


class Sunny(Weather):
    def __init__(self):
        super().__init__()
        self.id = 1
        self.desc = "in harsh sunlight"

    def __del__(self):
        print("The harsh sunlight faded.")


class Rain(Weather):
    def __init__(self):
        super().__init__()
        self.id = 2
        self.desc = "raining"

    def __del__(self):
        print("The rain stopped.")


class Sandstorm(Weather):
    def __init__(self):
        super().__init__()
        self.id = 3
        self.desc = "in raging sandstorm"

    def __del__(self):
        print("The sandstorm subsided.")


class Hail(Weather):
    def __init__(self):
        super().__init__()
        self.id = 4
        self.desc = "hailing"

    def __del__(self):
        print("The hail stopped.")


weather_conversionChart = {
    0: "The Sky is Clear.",
    1: "The Sunlight is Harsh.",
    2: "It is raining.",
    3: "The Sandstorm is Raging.",
    4: "The Hail Continues to Fall."
}