import csv


class Competitor:
    def __init__(self, raw_id, nickname, name, strength=1, ability="", desc="", level="", music="", ace_music="", color="", quote="", strategy=""):
        self.id, self.match_id = None, None
        self.raw_id = raw_id
        self.nickname = nickname
        self.name = name
        self.strength = strength
        self.ability = ability
        self.main = False
        self.stage = 1
        self.desc = desc
        self.result = 0
        self.score = 0
        self.opponent_score = 0
        self.level = level
        self.music = music
        self.ace_music = ace_music
        self.faster = False
        self.side_color = ""
        self.color = color
        self.quote = quote
        self.team = []
        self.unused_team = []
        self.switching = 0
        self.in_battle_effects = {"Reflect": 0,
                                  "Light Screen": 0,
                                  "Aurora Veil": 0,
                                  "Tailwind": 0}
        self.entry_hazard = {"Stealth Rock": 0,
                             "Spikes": 0,
                             "Toxic Spikes": 0,
                             "Sticky Web": 0}
        # records
        self.history = {}
        self.participation = 0
        self.championship = 0
        # in-game stats
        self.opponent = []
        self.win_order = []
        # character ability
        self.reveal_ability = False
        self.strategy = strategy


with open('Data/competitors.csv', encoding="ISO-8859-1") as f:
    reader = csv.DictReader(f)
    list_of_competitors = {}
    for row in reader:
        list_of_competitors[row['Name']] = Competitor(row['ID'], row['Nickname'], row['Name'], int(row['Strength']), row['Ability'], row['Desc'], row['Level'],
                                                      row['Music'], row['Ace Music'], row['Color'], row['Quote'], row['Strategy'])
        for i in range(1, 7):
            if row[f'Poke{i}'] != '':
                list_of_competitors[row['Name']].team.append(row[f'Poke{i}'])

    for competitor in list_of_competitors:
        list_of_competitors[competitor].opponent_history = {key: [0, 0] for key in list_of_competitors}

list_of_competitors['Protagonist'].main = True