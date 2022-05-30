"""
typeChart
0 Typeless, 1 Normal, 1 Fire, 2 Water, 3 Electric, 4 Grass, 5 Ice, 6 Fighting, 7 Poison, 8 Ground, 9 Flying,
10 Psychic, 11 Bug, 12 Rock, 13 Ghost, 14 Dragon, 15 Dark, 16 Steel, 17 Fairy

modifierChart
0 HP | 1 Attack | 2 Defense | 3 SpA | 4 SpDef | 5 Speed | 6 Evasion | 7 Accuracy | 8 Crit
"""

typeChart = {
    "Typeless": {"Typeless": 1, "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1, "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1,
               "Psychic": 1, "Bug": 1, "Rock": 1, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 1, "Fairy": 1},
    "Normal": {"Typeless": 1, "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1, "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1,
               "Psychic": 1, "Bug": 1, "Rock": 0.5, "Ghost": 0, "Dragon": 1, "Dark": 1, "Steel": 0.5, "Fairy": 1},
    "Fire": {"Typeless": 1, "Normal": 1, "Fire": 0.5, "Water": 0.5, "Electric": 1, "Grass": 2, "Ice": 2, "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1,
             "Psychic": 1, "Bug": 2, "Rock": 0.5, "Ghost": 1, "Dragon": 0.5, "Dark": 1, "Steel": 2, "Fairy": 1},
    "Water": {"Typeless": 1, "Normal": 1, "Fire": 2, "Water": 0.5, "Electric": 1, "Grass": 0.5, "Ice": 1, "Fighting": 1, "Poison": 1, "Ground": 2, "Flying": 1,
              "Psychic": 1, "Bug": 1, "Rock": 2, "Ghost": 1, "Dragon": 0.5, "Dark": 1, "Steel": 1, "Fairy": 1},
    "Electric": {"Typeless": 1, "Normal": 1, "Fire": 1, "Water": 2, "Electric": 0.5, "Grass": 0.5, "Ice": 1, "Fighting": 1, "Poison": 1, "Ground": 0, "Flying": 2,
                 "Psychic": 1, "Bug": 1, "Rock": 1, "Ghost": 1, "Dragon": 0.5, "Dark": 1, "Steel": 1, "Fairy": 1},
    "Grass": {"Typeless": 1, "Normal": 1, "Fire": 0.5, "Water": 2, "Electric": 1, "Grass": 0.5, "Ice": 1, "Fighting": 1, "Poison": 0.5, "Ground": 2, "Flying": 0.5,
              "Psychic": 1, "Bug": 0.5, "Rock": 2, "Ghost": 1, "Dragon": 0.5, "Dark": 1, "Steel": 0.5, "Fairy": 1},
    "Ice": {"Typeless": 1, "Normal": 1, "Fire": 0.5, "Water": 0.5, "Electric": 1, "Grass": 2, "Ice": 0.5, "Fighting": 1, "Poison": 1, "Ground": 2, "Flying": 2,
            "Psychic": 1, "Bug": 1, "Rock": 1, "Ghost": 1, "Dragon": 2, "Dark": 1, "Steel": 0.5, "Fairy": 1},
    "Fighting": {"Typeless": 1, "Normal": 2, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 2, "Fighting": 1, "Poison": 0.5, "Ground": 1, "Flying": 0.5,
                 "Psychic": 0.5, "Bug": 0.5, "Rock": 2, "Ghost": 0, "Dragon": 1, "Dark": 2, "Steel": 2, "Fairy": 0.5},
    "Poison": {"Typeless": 1, "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 2, "Ice": 1, "Fighting": 1, "Poison": 0.5, "Ground": 0.5, "Flying": 1,
               "Psychic": 1, "Bug": 1, "Rock": 0.5, "Ghost": 0.5, "Dragon": 1, "Dark": 1, "Steel": 0, "Fairy": 2},
    "Ground": {"Typeless": 1, "Normal": 1, "Fire": 2, "Water": 1, "Electric": 2, "Grass": 0.5, "Ice": 1, "Fighting": 1, "Poison": 2, "Ground": 1, "Flying": 0,
               "Psychic": 1, "Bug": 0.5, "Rock": 2, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 2, "Fairy": 1},
    "Flying": {"Typeless": 1, "Normal": 1, "Fire": 1, "Water": 1, "Electric": 0.5, "Grass": 2, "Ice": 1, "Fighting": 2, "Poison": 1, "Ground": 1, "Flying": 1,
               "Psychic": 1, "Bug": 2, "Rock": 0.5, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 0.5, "Fairy": 1},
    "Psychic": {"Typeless": 1, "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1, "Fighting": 2, "Poison": 2, "Ground": 1, "Flying": 1,
                "Psychic": 0.5, "Bug": 1, "Rock": 1, "Ghost": 1, "Dragon": 1, "Dark": 0, "Steel": 0.5, "Fairy": 1},
    "Bug": {"Typeless": 1, "Normal": 1, "Fire": 0.5, "Water": 1, "Electric": 1, "Grass": 2, "Ice": 1, "Fighting": 0.5, "Poison": 0.5, "Ground": 1, "Flying": 0.5,
            "Psychic": 2, "Bug": 1, "Rock": 1, "Ghost": 0.5, "Dragon": 1, "Dark": 2, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Typeless": 1, "Normal": 1, "Fire": 2, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 2, "Fighting": 0.5, "Poison": 1, "Ground": 0.5, "Flying": 2,
             "Psychic": 1, "Bug": 2, "Rock": 1, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 0.5, "Fairy": 1},
    "Ghost": {"Typeless": 1, "Normal": 0, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1, "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1,
              "Psychic": 2, "Bug": 1, "Rock": 1, "Ghost": 2, "Dragon": 1, "Dark": 0.5, "Steel": 1, "Fairy": 1},
    "Dragon": {"Typeless": 1, "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1, "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1,
               "Psychic": 1, "Bug": 1, "Rock": 1, "Ghost": 1, "Dragon": 2, "Dark": 1, "Steel": 0.5, "Fairy": 0},
    "Dark": {"Typeless": 1, "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1, "Fighting": 0.5, "Poison": 1, "Ground": 1, "Flying": 1,
             "Psychic": 2, "Bug": 1, "Rock": 1, "Ghost": 2, "Dragon": 1, "Dark": 0.5, "Steel": 1, "Fairy": 0.5},
    "Steel": {"Typeless": 1, "Normal": 1, "Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Grass": 1, "Ice": 2, "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1,
              "Psychic": 1, "Bug": 1, "Rock": 2, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 0.5, "Fairy": 2},
    "Fairy": {"Typeless": 1, "Normal": 1, "Fire": 0.5, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1, "Fighting": 2, "Poison": 0.5, "Ground": 1, "Flying": 1,
              "Psychic": 1, "Bug": 1, "Rock": 1, "Ghost": 1, "Dragon": 2, "Dark": 2, "Steel": 0.5, "Fairy": 1}
}


# on base stats only
modifierChart = [
    [1, 1.5, 2, 2.5, 3, 3.5, 4, 0.25, 0.285, 0.333, 0.4, 0.5, 0.666],  # HP
    [1, 1.5, 2, 2.5, 3, 3.5, 4, 0.25, 0.285, 0.333, 0.4, 0.5, 0.666],  # Attack
    [1, 1.5, 2, 2.5, 3, 3.5, 4, 0.25, 0.285, 0.333, 0.4, 0.5, 0.666],  # Defense
    [1, 1.5, 2, 2.5, 3, 3.5, 4, 0.25, 0.285, 0.333, 0.4, 0.5, 0.666],  # SpA
    [1, 1.5, 2, 2.5, 3, 3.5, 4, 0.25, 0.285, 0.333, 0.4, 0.5, 0.666],  # SpDef
    [1, 1.5, 2, 2.5, 3, 3.5, 4, 0.25, 0.285, 0.333, 0.4, 0.5, 0.666],  # Speed
    [1, 1.33, 1.66, 2, 2.33, 2.66, 3, 0.33, 0.375, 0.428, 0.5, 0.6, 0.75],  # Evasion
    [1, 1.33, 1.66, 2, 2.33, 2.66, 3, 0.33, 0.375, 0.428, 0.5, 0.6, 0.75],  # Accuracy
    [1 / 24, 1 / 8, 1 / 2, 1, 1, 1, 1]  # Crit
]
