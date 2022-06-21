import csv


class Pokemon:
    def __init__(self, id, name, base_stats, total_stats, type, ability, moveset, tier, custom=False):
        self.id = id
        self.name = name
        self.type = type
        self.base_stats = base_stats
        self.total_stats = total_stats
        self.iv, self.nominal_base_stats, self.total_iv = 0, 0, 0
        self.previous_move = ""
        self.modifier = [0] * 9
        self.applied_modifier = [0] * 9
        self.status = "Normal"
        self.moveset = moveset
        # tier list for pokemon selection
        self.tier = tier
        self.custom = custom
        self.ability = ability
        self.volatile_status = {
            "NonVolatile": 0,
            "Flinch": 0,
            "Confused": 0,
            "Frighten": 0,
            "Curse": 0,
            "DestinyBond": 0,
            "PerishSong": 0,
            "Torment": 0,
            "Binding": 0,
            "Trapped": 0,
            "LeechSeed": 0,
            "Ingrain": 0,
            "AquaRing": 0,
            "Octolock": 0,
            "TotalConcentration": 0,
            "Yawn": 0,
            "FlashFire": 0,
            "TakeAim": 0,
            "Grounded": 0,
            "Turn": 0,
        }
        # in-battle move history
        self.move_order = []
        self.protection = [0, 0]
        # move name, move efect (charging / semi-invulnerable / consecutive), number of turn to end
        self.charging = ["", "", 0]
        # disabled moves
        self.disabled_moves = {}
        # other individual factors
        self.disguise, self.transform = False, False
        self.second_life = 0


with open('Data/pokemon.csv', encoding="ISO-8859-1") as f:
    reader = csv.DictReader(f)
    list_of_pokemon = {}
    for row in reader:
        base_stats = [int(row['HP']), int(row['Atk']), int(row['Def']), int(row['SpA']), int(row['SpDef']), int(row['Spd'])]
        total_stats = int(row['Total'])
        typing = []
        for i in range(1, 4):
            if row[f'Type{i}'] != '':
                typing.append(row[f'Type{i}'])
        abilities = [row['Ability']] if row['SAbility'] == '' else [row['Ability'], row['SAbility']]
        moveset = []
        for i in range(1, 7):
            if row[f'Move{i}'] != '':
                moveset.append(row[f'Move{i}'])
        custom = True if row['Custom'] == 'Y' else False
        list_of_pokemon[row['Name']] = Pokemon(row['ID'], row['Name'], base_stats, total_stats, typing, abilities, moveset, row['Tier'], custom)
