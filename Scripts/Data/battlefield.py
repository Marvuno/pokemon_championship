class Battleground:
    def __init__(self):
        self.turn = 1
        self.verbose = False
        self.auto_battle = False
        # weather
        self.starting_weather_effect = 'Clear'
        self.weather_effect = 'Clear'
        self.weather_turn = 0
        self.artificial_weather = False
        # other factors
        self.battle_continuation = True
        self.reality = True
        self.sudden_death = False
        # stackable
        self.field_effect = {
            "Trick Room": 0,
        }

