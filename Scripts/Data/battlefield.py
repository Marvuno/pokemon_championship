class Battleground:
    def __init__(self):
        # 0 before a turn has been played. `move_selection` counts up to 1
        # as it starts the first turn, so this reads as the turn *being*
        # played all the way through it rather than the next one.
        self.turn = 0
        self.verbose = False
        self.auto_battle = False
        #: A one-off battle outside the tournament -- Custom Play. The battle
        #: itself is ordinary; what an exhibition skips is the bracket
        #: machinery that normally runs when one ends. See
        #: battle_win_condition.end_battle.
        self.exhibition = False
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
        # `encore_move` used to live here and now lives on the Pokemon that
        # earned it -- a slot shared by both sides handed the extra move to
        # whoever moved next. See wizardry() in character_abilities.py.
        self.encore_running = False
        self.reality = True
        self.sudden_death = False
        #: skip the opening weather and terrain rolls -- see battle_setup.
        #: Only the Metronome game mode sets this.
        self.bare_arena = False
        # stackable
        self.field_effect = {
            "Trick Room": 0,
        }
        # text
        self.ability_text = ""

