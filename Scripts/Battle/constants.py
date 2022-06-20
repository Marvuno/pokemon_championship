import math

GUARANTEE_ACCURACY = 9
INFINITY = math.inf
NEG_INF = math.inf * -1
ROUND_LIMIT = {1: 4, 2: 5, 3: 6, 4: 6, 5: 6, 6: 6}  # 4,5,6,6,6
STATISTICS = {0: "HP", 1: "Atk", 2: "Def", 3: "SpA", 4: "SpDef", 5: "Speed"}
MODIFIER = {0: 'HP', 1: 'Attack', 2: 'Defense', 3: 'Special Attack', 4: 'Special Defense', 5: 'Speed', 6: 'Evasion', 7: 'Accuracy', 8: 'Crit'}
TEAM_BUFF_TURNS = 8
FIELD_EFFECT_TURNS = 8
WEATHER_EFFECT_TURNS = 8
KEEP_POKEMON_LOST = 3
KEEP_POKEMON_SEMI = 4
KEEP_POKEMON_WIN = 6
MAX_POKEMON = 6