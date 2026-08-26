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
        # terrain -- its own layer, deliberately not inside field_effect.
        # Weather, terrain and rooms are separate slots in the real games:
        # Rain, Electric Terrain and Trick Room can all be up at once and
        # only members of the same layer replace each other. Sharing
        # field_effect with Trick Room would have made those two exclusive.
        # See Scripts/Battle/terrain.py.
        self.terrain = 'None'
        self.terrain_turn = 0
        # other factors
        self.battle_continuation = True
        #: a second move to run inside this same turn, and a guard so the
        #: repeat cannot queue another. Set by the Wizardry and Overloaded
        #: character abilities, read once by move_order_and_execution.
        #: On the battleground because it is rebuilt per battle, so it
        #: cannot leak from one to the next.
        self.encore_move = None
        self.encore_running = False
        self.reality = True
        self.sudden_death = False
        # stackable
        self.field_effect = {
            "Trick Room": 0,
        }
        # text
        self.ability_text = ""

