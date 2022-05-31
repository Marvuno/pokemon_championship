import random
from moves_status_condition_apply import *
from weather import *
from constants import *

"""
0 Normal, 1 Fire, 2 Water, 3 Electric, 4 Grass, 5 Ice, 6 Fighting, 7 Poison, 8 Ground, 9 Flying, 10 Psychic, 11 Bug,
12 Rock, 13 Ghost, 14 Dragon, 15 Dark, 16 Steel, 17 Fairy
0 Physical | 1 Special | 2 Status
0 HP | 1 Attack | 2 Defense | 3 SpA | 4 SpDef | 5 Speed | 6 Evasion | 7 Accuracy | 8 Crit
"""


class Move:
    def __init__(self, name, power, attack_type, type, accuracy, pp,
                 ignoreEvasion=False, ignoreDef=False, ignoreWeather=False, ignoreType=[], ignoreImmunity=[],
                 ignoreBarrier=False, ignoreAbility=False, ignoreInvulnerability=False,
                 targetAtk=False, inverseDef=False, multiType=[], interchangeType=[],
                 charging="", crit=0, priority=0, recoil=0, deduct=0, crash=0, multi=[False, 1], flags='', custom=False,
                 effect_type="no_effect", special_effect="", effect_accuracy=1):
        self.name = name
        self.power = power
        self.abilitymodifier = 1
        self.evasion = 1
        self.super_effective = False
        self.critical_hit = False
        self.attack_type = attack_type
        self.type = type
        self.accuracy = accuracy
        self.pp = pp
        self.ignoreEvasion = ignoreEvasion
        self.ignoreDef = ignoreDef
        self.ignoreWeather = ignoreWeather
        self.ignoreType = ignoreType
        self.ignoreImmunity = ignoreImmunity
        self.ignoreBarrier = ignoreBarrier
        self.ignoreAbility = ignoreAbility
        self.ignoreInvulnerability = ignoreInvulnerability
        self.targetAtk = targetAtk
        self.inverseDef = inverseDef
        self.multiType = multiType
        self.interchangeType = interchangeType
        self.charging = charging
        self.critRatio = crit
        self.priority = priority
        self.recoil = recoil
        self.deduct = deduct
        self.crash = crash
        self.multi = multi
        self.effect_type = effect_type
        self.special_effect = special_effect
        self.effect_accuracy = effect_accuracy
        self.flags = flags
        self.custom = custom


list_of_moves = {
    'Switching': Move(name="Switching", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=100,
                      flags='b'),

    'Baneful Bunker': Move(name="Baneful Bunker", power=0, attack_type="Status", type="Poison", accuracy=GUARANTEE_ACCURACY, pp=10,
                           crit=0, priority=4, recoil=0, flags='b',
                           effect_type="user_protection"),

    'Destiny Bond': Move(name="Destiny Bond", power=0, attack_type="Status", type="Ghost", accuracy=GUARANTEE_ACCURACY, pp=5,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="user_volatile", special_effect=DestinyBond),

    'King\'s Shield': Move(name="King's Shield", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=10,
                           crit=0, priority=4, recoil=0, flags='b',
                           effect_type="user_protection"),

    'Perish Song': Move(name="Perish Song", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=5,
                        crit=0, priority=0, recoil=0, flags='bf',
                        effect_type=["target_volatile", "user_volatile"], special_effect=[PerishSong, PerishSong]),

    'Accelerock': Move(name="Accelerock", power=40, attack_type="Physical", type="Rock", accuracy=1, pp=20,
                       crit=0, priority=1, flags='a'),

    'Acid Spray': Move(name="Acid Spray", power=40, attack_type="Special", type="Poison", accuracy=1, pp=20,
                       crit=0, priority=0, recoil=0, flags='i',
                       effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -2, 0, 0, 0, 0]),

    'Metal Sound': Move(name="Metal Sound", power=0, attack_type="Status", type="Steel", accuracy=0.85, pp=20,
                        crit=0, priority=0, recoil=0, flags='f',
                        effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -2, 0, 0, 0, 0]),

    'Screech': Move(name="Screech", power=0, attack_type="Status", type="Normal", accuracy=0.85, pp=40,
                    crit=0, priority=0, recoil=0, flags='f',
                    effect_type="opponent_modifier", special_effect=[0, 0, -2, 0, 0, 0, 0, 0, 0]),

    'Aerial Ace': Move(name="Aerial Ace", power=60, attack_type="Physical", type="Flying", accuracy=GUARANTEE_ACCURACY, pp=20,
                       crit=0, priority=0, flags='a'),

    'Smart Strike': Move(name="Smart Strike", power=70, attack_type="Physical", type="Steel", accuracy=GUARANTEE_ACCURACY, pp=10,
                       crit=0, priority=0, flags='a'),

    'Swift': Move(name="Swift", power=60, attack_type="Special", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=20,
                       crit=0, priority=0),

    'Shadow Punch': Move(name="Shadow Punch", power=60, attack_type="Physical", type="Ghost", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, flags='ae'),

    'Spectral Thief': Move(name="Spectral Thief", power=90, attack_type="Physical", type="Ghost", accuracy=1, pp=10,
                           crit=0, priority=0, flags='a'),

    'Agility': Move(name="Agility", power=0, attack_type="Status", type="Psychic", accuracy=GUARANTEE_ACCURACY, pp=30,
                    crit=0, priority=0, recoil=0, flags='b',
                    effect_type="self_modifier", special_effect=[0, 0, 0, 0, 0, 2, 0, 0, 0]),

    'Rock Polish': Move(name="Rock Polish", power=0, attack_type="Status", type="Rock", accuracy=GUARANTEE_ACCURACY, pp=30,
                        crit=0, priority=0, recoil=0, flags='b',
                        effect_type="self_modifier", special_effect=[0, 0, 0, 0, 0, 2, 0, 0, 0]),

    'Air Slash': Move(name="Air Slash", power=75, attack_type="Special", type="Flying", accuracy=0.95, pp=15,
                      crit=0, priority=0, recoil=0,
                      effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Amnesia': Move(name="Amnesia", power=0, attack_type="Status", type="Psychic", accuracy=GUARANTEE_ACCURACY, pp=20,
                    crit=0, priority=0, recoil=0, flags='b',
                    effect_type="self_modifier", special_effect=[0, 0, 0, 0, 2, 0, 0, 0, 0]),

    'Anchor Shot': Move(name="Anchor Shot", power=80, attack_type="Physical", type="Steel", accuracy=1, pp=20,
                        crit=0, priority=0, flags='a',
                        effect_type="target_volatile", special_effect=Trapped),

    'Spirit Shackle': Move(name="Spirit Shackle", power=80, attack_type="Physical", type="Ghost", accuracy=1, pp=10,
                           crit=0, priority=0,
                           effect_type="target_volatile", special_effect=Trapped),

    'Ancient Power': Move(name="Ancient Power", power=60, attack_type="Special", type="Rock", accuracy=1, pp=15,
                          crit=0, priority=0, recoil=0,
                          effect_type="self_modifier", special_effect=[0, 1, 1, 1, 1, 1, 0, 0, 0], effect_accuracy=0.1),

    'Aqua Jet': Move(name="Aqua Jet", power=40, attack_type="Physical", type="Water", accuracy=1, pp=20,
                     crit=0, priority=1, flags='a'),

    'Aqua Tail': Move(name="Aqua Tail", power=90, attack_type="Physical", type="Water", accuracy=0.9, pp=10,
                      crit=0, priority=0, recoil=0, flags='a'),

    'Aura Sphere': Move(name="Aura Sphere", power=80, attack_type="Special", type="Fighting", accuracy=GUARANTEE_ACCURACY, pp=20, flags='hi'),

    'Aurora Veil': Move(name="Aurora Veil", power=0, attack_type="Status", type="Ice", accuracy=GUARANTEE_ACCURACY, pp=20,
                        crit=0, priority=0, recoil=0, flags='b',
                        effect_type="self_team_buff", special_effect="Aurora Veil"),

    'Avalanche': Move(name="Avalanche", power=60, attack_type="Physical", type="Ice", accuracy=1, pp=20,
                      crit=0, priority=-4, flags='a',
                      effect_type="after_hand"),

    'Baton Pass': Move(name="Baton Pass", power=0, attack_type="Status", type="Normal", accuracy=1, pp=20,
                       effect_type="switching"),

    'Belly Drum': Move(name="Belly Drum", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=10,
                       crit=0, priority=0, deduct=0.5, flags='b',
                       effect_type="self_modifier", special_effect=[0, 6, 0, 0, 0, 0, 0, 0, 0]),

    'Bite': Move(name="Bite", power=60, attack_type="Physical", type="Dark", accuracy=1, pp=25,
                 crit=0, priority=0, recoil=0, flags='ad',
                 effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Blaze Kick': Move(name="Blaze Kick", power=85, attack_type="Physical", type="Fire", accuracy=0.9, pp=10,
                       crit=1, priority=0, recoil=0, flags='a',
                       effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.1),

    'Pyro Ball': Move(name="Pyro Ball", power=120, attack_type="Physical", type="Fire", accuracy=0.9, pp=5,
                      crit=0, priority=0, recoil=0, flags='ci',
                      effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.1),

    'Blizzard': Move(name="Blizzard", power=110, attack_type="Special", type="Ice", accuracy=0.7, pp=5,
                     crit=0, priority=0, recoil=0,
                     effect_type="target_non_volatile", special_effect=Freeze, effect_accuracy=0.1),

    'Body Slam': Move(name="Body Slam", power=80, attack_type="Physical", type="Normal", accuracy=1, pp=20,
                      crit=0, priority=0, recoil=0, flags='a',
                      effect_type="target_non_volatile", special_effect=Paralysis, effect_accuracy=0.3),

    'Icicle Crash': Move(name="Icicle Crash", power=85, attack_type="Physical", type="Ice", accuracy=0.9, pp=10,
                         crit=0, priority=0, recoil=0, flags='a',
                         effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Bone Rush': Move(name="Bone Rush", power=25, attack_type="Physical", type="Ground", accuracy=0.9, pp=10,
                      crit=0, priority=0, multi=[True, 5]),

    'Boomburst': Move(name="Boomburst", power=140, attack_type="Special", type="Normal", accuracy=1, pp=10, flags='f'),

    'Brave Bird': Move(name="Brave Bird", power=120, attack_type="Physical", type="Flying", accuracy=1, pp=15,
                       crit=0, priority=0, recoil=1 / 3, flags='a'),

    'Brick Break': Move(name="Brick Break", power=75, attack_type="Physical", type="Fighting", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=0, flags='a',
                        effect_type="remove_team_buff"),

    'Bug Buzz': Move(name="Bug Buzz", power=90, attack_type="Special", type="Bug", accuracy=1, pp=10,
                     crit=0, priority=0, recoil=0, flags='f',
                     effect_type="opponent_modifier", special_effect=[0, 0, 0, -1, 0, 0, 0, 0, 0], effect_accuracy=0.1),

    'Clanging Scales': Move(name="Clanging Scales", power=110, attack_type="Special", type="Dragon", accuracy=1, pp=5,
                     crit=0, priority=0, recoil=0, flags='f',
                     effect_type="self_modifier", special_effect=[0, 0, -1, 0, 0, 0, 0, 0, 0]),

    'Mystical Fire': Move(name="Mystical Fire", power=75, attack_type="Special", type="Fire", accuracy=1, pp=10,
                          crit=0, priority=0, recoil=0,
                          effect_type="opponent_modifier", special_effect=[0, 0, 0, -1, 0, 0, 0, 0, 0]),

    'Shadow Bone': Move(name="Shadow Bone", power=85, attack_type="Physical", type="Ghost", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0,
                        effect_type="opponent_modifier", special_effect=[0, 0, -1, 0, 0, 0, 0, 0, 0], effect_accuracy=0.2),

    'Bulk Up': Move(name="Bulk Up", power=0, attack_type="Status", type="Fighting", accuracy=GUARANTEE_ACCURACY, pp=30,
                    crit=0, priority=0, recoil=0, flags='b',
                    effect_type="self_modifier", special_effect=[0, 1, 1, 0, 0, 0, 0, 0, 0]),

    'Bulldoze': Move(name="Bulldoze", power=60, attack_type="Physical", type="Ground", accuracy=1, pp=20,
                     crit=0, priority=0, recoil=0,
                     effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Icy Wind': Move(name="Icy Wind", power=55, attack_type="Special", type="Ice", accuracy=0.95, pp=15,
                     crit=0, priority=0, recoil=0,
                     effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Rock Tomb': Move(name="Rock Tomb", power=60, attack_type="Physical", type="Rock", accuracy=0.95, pp=15,
                      crit=0, priority=0, recoil=0,
                      effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Bullet Punch': Move(name="Bullet Punch", power=40, attack_type="Physical", type="Steel", accuracy=1, pp=30,
                         crit=0, priority=1, flags='ae'),

    'Mach Punch': Move(name="Mach Punch", power=40, attack_type="Physical", type="Fighting", accuracy=1, pp=30,
                       crit=0, priority=1, flags='ae'),

    'Bullet Seed': Move(name="Bullet Seed", power=25, attack_type="Physical", type="Grass", accuracy=1, pp=30,
                        crit=0, priority=0, multi=[True, 5], flags='i'),

    'Calm Mind': Move(name="Calm Mind", power=0, attack_type="Status", type="Psychic", accuracy=GUARANTEE_ACCURACY, pp=20,
                      crit=0, priority=0, recoil=0, flags='b',
                      effect_type="self_modifier", special_effect=[0, 0, 0, 1, 1, 0, 0, 0, 0]),

    'Charge Beam': Move(name="Charge Beam", power=50, attack_type="Special", type="Electric", accuracy=0.9, pp=10,
                        crit=0, priority=0, recoil=0,
                        effect_type="self_modifier", special_effect=[0, 0, 0, 1, 0, 0, 0, 0, 0], effect_accuracy=0.7),

    'Charm': Move(name="Charm", power=0, attack_type="Status", type="Fairy", accuracy=1, pp=20,
                  crit=0, priority=0, recoil=0,
                  effect_type="opponent_modifier", special_effect=[0, -2, 0, 0, 0, 0, 0, 0, 0]),

    'Close Combat': Move(name="Close Combat", power=120, attack_type="Physical", type="Fighting", accuracy=1, pp=5,
                         crit=0, priority=0, recoil=0, flags='a',
                         effect_type="self_modifier", special_effect=[0, 0, -1, 0, -1, 0, 0, 0, 0]),

    'Coil': Move(name="Coil", power=0, attack_type="Status", type="Poison", accuracy=GUARANTEE_ACCURACY, pp=20,
                 crit=0, priority=0, recoil=0, flags='b',
                 effect_type="self_modifier", special_effect=[0, 1, 1, 0, 0, 0, 0, 1, 0]),

    'Cold Touch': Move(name="Cold Touch", power=30, attack_type="Physical", type="Ice", accuracy=1, pp=20,
                       priority=1, custom=True,
                       effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Confuse Ray': Move(name="Confuse Ray", power=0, attack_type="Status", type="Ghost", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0,
                        effect_type="target_volatile", special_effect=Confused),

    'Sweet Kiss': Move(name="Sweet Kiss", power=0, attack_type="Status", type="Fairy", accuracy=0.75, pp=10,
                       crit=0, priority=0, recoil=0,
                       effect_type="target_volatile", special_effect=Confused),

    'Cotton Spore': Move(name="Cotton Spore", power=0, attack_type="Status", type="Grass", accuracy=1, pp=40,  # grass type immune
                         crit=0, priority=0, recoil=0, flags='g',
                         effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -2, 0, 0, 0]),

    'Counter': Move(name="Counter", power=0, attack_type="Status", type="Fighting", accuracy=1, pp=20,
                    priority=-5,
                    effect_type="countering"),

    'Crabhammer': Move(name="Crabhammer", power=100, attack_type="Physical", type="Water", accuracy=0.9, pp=10,
                       crit=1, priority=0, flags='a'),

    'Cross Chop': Move(name="Cross Chop", power=100, attack_type="Physical", type="Fighting", accuracy=0.8, pp=5,
                       crit=1, priority=0, recoil=0, flags='a'),

    'Cross Poison': Move(name="Cross Poison", power=70, attack_type="Physical", type="Poison", accuracy=1, pp=15,
                         crit=1, priority=0, recoil=0, flags='a',
                         effect_type="target_non_volatile", special_effect=Poison, effect_accuracy=0.1),

    'Crunch': Move(name="Crunch", power=80, attack_type="Physical", type="Dark", accuracy=1, pp=15,
                   crit=0, priority=0, recoil=0, flags='ad',
                   effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -1, 0, 0, 0, 0], effect_accuracy=0.2),

    'Curse': Move(name="Curse", power=0, attack_type="Status", type="Ghost", accuracy=GUARANTEE_ACCURACY, pp=20,
                  crit=0, priority=0, recoil=0, flags='b',
                  effect_type="cursing", special_effect=[0, 1, 1, 0, 0, -1, 0, 0, 0]),

    'Dark Pulse': Move(name="Dark Pulse", power=80, attack_type="Special", type="Dark", accuracy=1, pp=15,  # buff 50% with mega launcher
                       crit=0, priority=0, recoil=0, flags='h',
                       effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.2),

    'Darkest Lariat': Move(name="Darkest Lariat", power=85, attack_type="Physical", type="Dark", accuracy=1, pp=10,
                           ignoreEvasion=True, ignoreDef=True, crit=0, priority=0, recoil=0, flags='a'),

    'Dazzling Gleam': Move(name="Dazzling Gleam", power=80, attack_type="Special", type="Fairy", accuracy=1, pp=10),
    'Defog': Move(name="Defog", power=0, attack_type="Status", type="Flying", accuracy=GUARANTEE_ACCURACY, pp=15,
                  crit=0, priority=0, flags='b',
                  effect_type=["opponent_modifier", "clear_entry_hazard"], special_effect=[[0, 0, 0, 0, 0, 0, -1, 0, 0], None]),

    'Disable': Move(name="Disable", power=0, attack_type="Status", type="Normal", accuracy=1, pp=20,
                    effect_type="target_disable", special_effect="Disable"),

    'Discharge': Move(name="Discharge", power=80, attack_type="Special", type="Electric", accuracy=1, pp=15,
                      crit=0, priority=0, recoil=0,
                      effect_type="target_non_volatile", special_effect=Paralysis, effect_accuracy=0.3),

    'Double Hit': Move(name="Double Hit", power=35, attack_type="Physical", type="Normal", accuracy=0.9, pp=10,
                       crit=0, priority=0, multi=[False, 2], flags='a'),

    'Dual Wingbeat': Move(name="Dual Wingbeat", power=40, attack_type="Physical", type="Flying", accuracy=0.9, pp=10,
                       crit=0, priority=0, multi=[False, 2], flags='a'),

    'Bonemerang': Move(name="Bonemerang", power=50, attack_type="Physical", type="Ground", accuracy=0.9, pp=10,
                       crit=0, priority=0, multi=[False, 2]),

    'Double Kick': Move(name="Double Kick", power=30, attack_type="Physical", type="Fighting", accuracy=1, pp=30,
                        crit=0, priority=0, multi=[False, 2], flags='a'),

    'Double-Edge': Move(name="Double-Edge", power=120, attack_type="Physical", type="Normal", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=1 / 3, flags='a'),

    'Draco Meteor': Move(name="Draco Meteor", power=130, attack_type="Special", type="Dragon", accuracy=0.9, pp=5,
                         crit=0, priority=0, recoil=0,
                         effect_type="self_modifier", special_effect=[0, 0, 0, -2, 0, 0, 0, 0, 0]),

    'Overheat': Move(name="Overheat", power=130, attack_type="Special", type="Fire", accuracy=0.9, pp=5,
                     crit=0, priority=0, recoil=0,
                     effect_type="self_modifier", special_effect=[0, 0, 0, -2, 0, 0, 0, 0, 0]),

    'Dragon Claw': Move(name="Dragon Claw", power=80, attack_type="Physical", type="Dragon", accuracy=1, pp=15, flags='a'),

    'Bug Bite': Move(name="Bug Bite", power=60, attack_type="Physical", type="Bug", accuracy=1, pp=15, flags='a'),

    'Mega Kick': Move(name="Mega Kick", power=120, attack_type="Physical", type="Normal", accuracy=0.75, pp=5, flags='a'),

    'Dragon Pulse': Move(name="Dragon Pulse", power=85, attack_type="Special", type="Dragon", accuracy=1, pp=10, flags='h'),

    'Dragon Dance': Move(name="Dragon Dance", power=0, attack_type="Status", type="Dragon", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="self_modifier", special_effect=[0, 1, 0, 0, 0, 1, 0, 0, 0]),

    'Breaking Swipe': Move(name="Breaking Swipe", power=60, attack_type="Physical", type="Dragon", accuracy=1, pp=15,
                           crit=0, priority=0, recoil=0, flags='a',
                           effect_type="opponent_modifier", special_effect=[0, -1, 0, 0, 0, 0, 0, 0, 0]),

    'Trop Kick': Move(name="Trop Kick", power=70, attack_type="Physical", type="Grass", accuracy=1, pp=15,
                           crit=0, priority=0, recoil=0, flags='a',
                           effect_type="opponent_modifier", special_effect=[0, -1, 0, 0, 0, 0, 0, 0, 0]),

    'Dragon Darts': Move(name="Dragon Darts", power=50, attack_type="Physical", type="Dragon", accuracy=1, pp=10,
                         crit=0, priority=0, multi=[False, 2]),

    'Dragon Hammer': Move(name="Dragon Hammer", power=90, attack_type="Physical", type="Dragon", accuracy=1, pp=15, flags='a'),

    'Dragon Rush': Move(name="Dragon Rush", power=100, attack_type="Physical", type="Dragon", accuracy=0.75, pp=10,
                        crit=0, priority=0, recoil=0, flags='a',
                        effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.2),

    'Drain Punch': Move(name="Drain Punch", power=75, attack_type="Physical", type="Fighting", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0, flags='a',
                        effect_type="hp_draining", special_effect=0.5),

    'Draining Kiss': Move(name="Draining Kiss", power=50, attack_type="Special", type="Fairy", accuracy=1, pp=10,
                          crit=0, priority=0, recoil=0, flags='a',
                          effect_type="hp_draining", special_effect=0.75),

    'Drill Run': Move(name="Drill Run", power=80, attack_type="Physical", type="Ground", accuracy=0.95, pp=20,
                      crit=1, priority=0, flags='a'),

    'Dual Chop': Move(name="Dual Chop", power=40, attack_type="Physical", type="Dragon", accuracy=0.9, pp=15,
                      crit=0, priority=0, multi=[False, 2], flags='a'),

    'Earth Power': Move(name="Earth Power", power=90, attack_type="Special", type="Ground", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0,
                        effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -1, 0, 0, 0, 0], effect_accuracy=0.1),

    'Scorching Sands': Move(name="Scorching Sands", power=70, attack_type="Special", type="Ground", accuracy=1, pp=10, flags='c',
                            effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.3),

    'Earthquake': Move(name="Earthquake", power=100, attack_type="Physical", type="Ground", accuracy=1, pp=10),

    'Electroweb': Move(name="Electroweb", power=55, attack_type="Special", type="Electric", accuracy=0.95, pp=15,
                       crit=0, priority=0, recoil=0,
                       effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Electro Ball': Move(name="Electro Ball", power=40, attack_type="Special", type="Electric", accuracy=1, pp=10, flags='i'),

    'Brine': Move(name="Brine", power=65, attack_type="Special", type="Water", accuracy=1, pp=10),

    'Hex': Move(name="Hex", power=65, attack_type="Special", type="Ghost", accuracy=1, pp=10),

    'Acupressure': Move(name="Acupressure", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=30),

    'Facade': Move(name="Facade", power=70, attack_type="Physical", type="Normal", accuracy=1, pp=20, flags='a'),

    'Venoshock': Move(name="Venoshock", power=65, attack_type="Special", type="Poison", accuracy=1, pp=10),

    'Mud Shot': Move(name="Mud Shot", power=55, attack_type="Special", type="Ground", accuracy=0.95, pp=15,
                     crit=0, priority=0, recoil=0,
                     effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Encore': Move(name="Encore", power=0, attack_type="Status", type="Normal", accuracy=1, pp=5,
                   effect_type="target_disable", special_effect="Encore"),

    'Endeavor': Move(name="Endeavor", power=0, attack_type="Status", type="Normal", accuracy=1, pp=5,
                     flags='a',
                     effect_type="hp_split", special_effect="Same"),

    'Energy Ball': Move(name="Energy Ball", power=90, attack_type="Special", type="Grass", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0, flags='i',
                        effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -1, 0, 0, 0, 0], effect_accuracy=0.1),

    'Explosion': Move(name="Explosion", power=250, attack_type="Physical", type="Normal", accuracy=1, pp=5,
                      crit=0, priority=0, deduct=1),

    'Extrasensory': Move(name="Extrasensory", power=80, attack_type="Special", type="Psychic", accuracy=1, pp=20,
                         crit=0, priority=0, recoil=0,
                         effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.1),

    'Extreme Speed': Move(name="Extreme Speed", power=80, attack_type="Physical", type="Normal", accuracy=1, pp=5,
                          crit=0, priority=2, flags='a'),

    'Fake Out': Move(name="Fake Out", power=40, attack_type="Physical", type="Normal", accuracy=1, pp=30,
                     crit=0, priority=3, flags='ja',
                     effect_type="target_volatile", special_effect=Flinch),

    'Fake Tears': Move(name="Fake Tears", power=0, attack_type="Status", type="Dark", accuracy=1, pp=20,
                       effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -2, 0, 0, 0, 0]),

    'False Surrender': Move(name="False Surrender", power=80, attack_type="Physical", type="Dark", accuracy=GUARANTEE_ACCURACY, pp=10,
                            crit=0, priority=0, flags='a'),

    'Fiery Dance': Move(name="Fiery Dance", power=80, attack_type="Special", type="Fire", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0,
                        effect_type="self_modifier", special_effect=[0, 0, 0, 1, 0, 0, 0, 0, 0], effect_accuracy=0.5),

    'Fire Punch': Move(name="Fire Punch", power=75, attack_type="Physical", type="Fire", accuracy=1, pp=15,
                       crit=0, priority=0, recoil=0, flags='ae',
                       effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.1),

    'Fire Spin': Move(name="Fire Spin", power=35, attack_type="Special", type="Fire", accuracy=0.85, pp=15,
                      crit=0, priority=0,
                      effect_type="target_volatile", special_effect=Binding),

    'First Impression': Move(name="First Impression", power=90, attack_type="Physical", type="Bug", accuracy=1, pp=10,
                             crit=0, priority=2, flags='ja'),

    'Flame Charge': Move(name="Flame Charge", power=50, attack_type="Physical", type="Fire", accuracy=1, pp=25,
                         crit=0, priority=0, recoil=0, flags='a',
                         effect_type="self_modifier", special_effect=[0, 0, 0, 0, 0, 1, 0, 0, 0]),

    'Flame Wheel': Move(name="Flame Wheel", power=60, attack_type="Physical", type="Fire", accuracy=1, pp=25,
                        crit=1, priority=0, recoil=0, flags='ac',
                        effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.1),

    'Flamethrower': Move(name="Flamethrower", power=90, attack_type="Special", type="Fire", accuracy=1, pp=15,
                         crit=0, priority=0, recoil=0,
                         effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.1),

    'Fire Blast': Move(name="Fire Blast", power=110, attack_type="Special", type="Fire", accuracy=0.85, pp=5,
                       crit=0, priority=0, recoil=0,
                       effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.3),

    'Flare Blitz': Move(name="Flare Blitz", power=120, attack_type="Physical", type="Fire", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=1 / 3, flags='ac',
                        effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.1),

    'Flash Cannon': Move(name="Flash Cannon", power=80, attack_type="Special", type="Steel", accuracy=1, pp=10,
                         crit=0, priority=0, recoil=0,
                         effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -1, 0, 0, 0, 0], effect_accuracy=0.1),

    'Fly': Move(name="Fly", power=90, attack_type="Physical", type="Flying", accuracy=0.95, pp=15,
                charging="Semi-invulnerable", flags='a'),

    'Bounce': Move(name="Bounce", power=85, attack_type="Physical", type="Flying", accuracy=0.85, pp=5,
                   charging="Semi-invulnerable", flags='a'),

    'Dig': Move(name="Dig", power=80, attack_type="Physical", type="Ground", accuracy=1, pp=10,
                charging="Semi-invulnerable", flags='a'),

    'Flying Press': Move(name="Flying Press", power=100, attack_type="Physical", type="Fighting", accuracy=0.95, pp=10,
                         crit=0, priority=0, recoil=0, flags='a', multiType=["Flying"]),

    'Depraved Shriek': Move(name="Depraved Shriek", power=120, attack_type="Special", type="Dark", accuracy=1, pp=5,
                            crit=0, priority=0, recoil=0, flags='f', multiType=["Psychic"], custom=True,
                            effect_type="after_hand"),

    'Focus Blast': Move(name="Focus Blast", power=120, attack_type="Special", type="Fighting", accuracy=0.7, pp=5,
                        crit=0, priority=0, recoil=0, flags='i',
                        effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -1, 0, 0, 0, 0], effect_accuracy=0.1),

    'Focus Energy': Move(name="Focus Energy", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="self_modifier", special_effect=[0, 0, 0, 0, 0, 0, 0, 0, 2]),

    'Force Palm': Move(name="Force Palm", power=60, attack_type="Physical", type="Fighting", accuracy=1, pp=10,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="target_non_volatile", special_effect=Paralysis, effect_accuracy=0.3),

    'Foul Play': Move(name="Foul Play", power=95, attack_type="Physical", type="Dark", accuracy=1, pp=15,
                      targetAtk=True, flags='a'),

    'Freeze-Dry': Move(name="Freeze-Dry", power=70, attack_type="Special", type="Ice", accuracy=1, pp=20,
                       ignoreType=["Water"],
                       effect_type="target_non_volatile", special_effect=Freeze, effect_accuracy=0.1),

    'Corrosive Water': Move(name="Corrosive Water", power=80, attack_type="Special", type="Water", accuracy=0.9, pp=10,
                            ignoreType=["Grass", "Fairy"], custom=True,
                            effect_type="target_non_volatile", special_effect=Poison, effect_accuracy=0.2),

    'Giga Drain': Move(name="Giga Drain", power=75, attack_type="Special", type="Grass", accuracy=1, pp=10,
                       crit=0, priority=0, recoil=0,
                       effect_type="hp_draining", special_effect=0.5),

    'Dream Eater': Move(name="Dream Eater", power=100, attack_type="Special", type="Psychic", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=0,
                        effect_type="hp_draining", special_effect=0.5),

    'Glaciate': Move(name="Glaciate", power=65, attack_type="Special", type="Ice", accuracy=0.95, pp=10,
                     crit=0, priority=0, recoil=0,
                     effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Glare': Move(name="Glare", power=0, attack_type="Status", type="Normal", accuracy=1, pp=30,
                  crit=0, priority=0, recoil=0,
                  effect_type="target_non_volatile", special_effect=Paralysis),

    'Growl': Move(name="Growl", power=0, attack_type="Status", type="Normal", accuracy=1, pp=40,
                  crit=0, priority=0, recoil=0, flags='f',
                  effect_type="opponent_modifier", special_effect=[0, -1, 0, 0, 0, 0, 0, 0, 0]),

    'Baby-Doll Eyes': Move(name="Baby-Doll Eyes", power=0, attack_type="Status", type="Fairy", accuracy=1, pp=30,
                  crit=0, priority=1, recoil=0,
                  effect_type="opponent_modifier", special_effect=[0, -1, 0, 0, 0, 0, 0, 0, 0]),

    'Gunk Shot': Move(name="Gunk Shot", power=120, attack_type="Physical", type="Poison", accuracy=0.8, pp=5,
                      crit=0, priority=0, recoil=0,
                      effect_type="target_non_volatile", special_effect=Poison, effect_accuracy=0.3),

    'Gust': Move(name="Gust", power=40, attack_type="Special", type="Flying", accuracy=1, pp=35),

    'Hail': Move(name="Hail", power=0, attack_type="Status", type="Ice", accuracy=GUARANTEE_ACCURACY, pp=5,
                 crit=0, priority=0, recoil=0, flags='b',
                 effect_type="weather_effect", special_effect=Hail),

    'Hammer Arm': Move(name="Hammer Arm", power=100, attack_type="Physical", type="Fighting", accuracy=0.9, pp=15,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="self_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Ice Hammer': Move(name="Ice Hammer", power=90, attack_type="Physical", type="Ice", accuracy=0.9, pp=10,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="self_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Head Smash': Move(name="Head Smash", power=150, attack_type="Physical", type="Rock", accuracy=0.8, pp=5,
                       crit=0, priority=0, recoil=1 / 2, flags='a'),

    'Heat Wave': Move(name="Heat Wave", power=95, attack_type="Special", type="Fire", accuracy=0.95, pp=10,
                      crit=0, priority=0, recoil=0,
                      effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.1),

    'High Horsepower': Move(name="High Horsepower", power=95, attack_type="Physical", type="Ground", accuracy=0.95, pp=10,
                            crit=0, flags='a'),

    'High Jump Kick': Move(name="High Jump Kick", power=130, attack_type="Physical", type="Fighting", accuracy=0.9, pp=10,
                           flags='a', crash=0.5),

    'Hone Claws': Move(name="Hone Claws", power=0, attack_type="Status", type="Dark", accuracy=GUARANTEE_ACCURACY, pp=15,
                       crit=0, priority=0, recoil=0, flags='b',
                       effect_type="self_modifier", special_effect=[0, 1, 0, 0, 0, 0, 0, 1, 0]),

    'Hydro Pump': Move(name="Hydro Pump", power=110, attack_type="Special", type="Water", accuracy=0.8, pp=5),

    'Hypnosis': Move(name="Hypnosis", power=0, attack_type="Status", type="Psychic", accuracy=0.6, pp=20,
                     crit=0, priority=0, recoil=0,
                     effect_type="target_non_volatile", special_effect=Sleep),

    'Leech Seed': Move(name="Leech Seed", power=0, attack_type="Status", type="Grass", accuracy=0.9, pp=20,
                       crit=0, priority=0, recoil=0, flags='g',
                       effect_type="target_volatile", special_effect=LeechSeed),

    'Ingrain': Move(name="Ingrain", power=0, attack_type="Status", type="Grass", accuracy=GUARANTEE_ACCURACY, pp=20,
                    crit=0, priority=0, recoil=0,
                    effect_type=["user_volatile", "user_volatile", "user_volatile"], special_effect=[Ingrain, Trapped, Grounded]),

    'Aqua Ring': Move(name="Aqua Ring", power=0, attack_type="Status", type="Water", accuracy=GUARANTEE_ACCURACY, pp=20,
                    crit=0, priority=0, recoil=0,
                    effect_type="user_volatile", special_effect=AquaRing),

    'Dark Void': Move(name="Dark Void", power=0, attack_type="Status", type="Dark", accuracy=0.7, pp=10,
                      crit=0, priority=0, recoil=0,
                      effect_type="target_non_volatile", special_effect=Sleep),

    'Ice Beam': Move(name="Ice Beam", power=90, attack_type="Special", type="Ice", accuracy=1, pp=10,
                     crit=0, priority=0, recoil=0,
                     effect_type="target_non_volatile", special_effect=Freeze, effect_accuracy=0.1),

    'Ice Punch': Move(name="Ice Punch", power=75, attack_type="Physical", type="Ice", accuracy=1, pp=15,
                      crit=0, priority=0, recoil=0, flags='ae',
                      effect_type="target_non_volatile", special_effect=Freeze, effect_accuracy=0.1),

    'Ice Fang': Move(name="Ice Fang", power=65, attack_type="Physical", type="Ice", accuracy=0.95, pp=15,
                     crit=0, priority=0, recoil=0, flags='ad',
                     effect_type=["target_non_volatile", "target_volatile"], special_effect=[Freeze, Flinch], effect_accuracy=0.1),

    'Thunder Fang': Move(name="Thunder Fang", power=65, attack_type="Physical", type="Electric", accuracy=0.95, pp=15,
                         crit=0, priority=0, recoil=0, flags='ad',
                         effect_type=["target_non_volatile", "target_volatile"], special_effect=[Paralysis, Flinch], effect_accuracy=0.1),

    'Fire Fang': Move(name="Fire Fang", power=65, attack_type="Physical", type="Fire", accuracy=0.95, pp=15,
                      crit=0, priority=0, recoil=0, flags='ad',
                      effect_type=["target_non_volatile", "target_volatile"], special_effect=[Burn, Flinch], effect_accuracy=0.1),

    'Ice Shard': Move(name="Ice Shard", power=40, attack_type="Physical", type="Ice", accuracy=1, pp=30,
                      crit=0, priority=1, flags='a'),

    'Icicle Spear': Move(name="Icicle Spear", power=25, attack_type="Physical", type="Ice", accuracy=1, pp=30,
                         crit=0, priority=0, multi=[True, 5]),

    'Iron Defense': Move(name="Iron Defense", power=0, attack_type="Status", type="Steel", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="self_modifier", special_effect=[0, 0, 2, 0, 0, 0, 0, 0, 0]),

    'Cotton Guard': Move(name="Cotton Guard", power=0, attack_type="Status", type="Grass", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="self_modifier", special_effect=[0, 0, 3, 0, 0, 0, 0, 0, 0]),

    'Iron Head': Move(name="Iron Head", power=80, attack_type="Physical", type="Steel", accuracy=1, pp=15,
                      crit=0, priority=0, recoil=0, flags='a',
                      effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Steel Wing': Move(name="Steel Wing", power=70, attack_type="Physical", type="Steel", accuracy=1, pp=20,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="self_modifier", special_effect=[0, 0, 1, 0, 0, 0, 0, 0, 0], effect_accuracy=0.1),

    'Meteor Mash': Move(name="Meteor Mash", power=90, attack_type="Physical", type="Steel", accuracy=0.9, pp=10,
                        crit=0, priority=0, recoil=0, flags='a',
                        effect_type="self_modifier", special_effect=[0, 1, 0, 0, 0, 0, 0, 0, 0], effect_accuracy=0.2),

    'Iron Tail': Move(name="Iron Tail", power=100, attack_type="Physical", type="Steel", accuracy=0.75, pp=15,
                      crit=0, priority=0, recoil=0, flags='a',
                      effect_type="opponent_modifier", special_effect=[0, 0, -1, 0, 0, 0, 0, 0, 0], effect_accuracy=0.3),

    'Jaw Lock': Move(name="Jaw Lock", power=80, attack_type="Physical", type="Dark", accuracy=1, pp=10,
                     crit=0, priority=0, flags='ad',
                     effect_type="target_volatile", special_effect=Trapped),

    'Jump Kick': Move(name="Jump Kick", power=100, attack_type="Physical", type="Fighting", accuracy=0.95, pp=10,
                      flags='a', crash=0.5),

    'Karate Chop': Move(name="Karate Chop", power=50, attack_type="Physical", type="Fighting", accuracy=1, pp=25,
                        crit=1, flags='a'),

    'Leaf Blade': Move(name="Leaf Blade", power=90, attack_type="Physical", type="Grass", accuracy=1, pp=10,
                       crit=1, priority=0, flags='a'),

    'Leaf Storm': Move(name="Leaf Storm", power=130, attack_type="Special", type="Grass", accuracy=0.9, pp=5,
                       crit=0, priority=0, recoil=0,
                       effect_type="self_modifier", special_effect=[0, 0, 0, -2, 0, 0, 0, 0, 0]),

    'Leech Life': Move(name="Leech Life", power=80, attack_type="Physical", type="Bug", accuracy=1, pp=10,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="hp_draining", special_effect=0.5),

    'Light Screen': Move(name="Light Screen", power=0, attack_type="Status", type="Psychic", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="self_team_buff", special_effect="Light Screen"),

    'Liquidation': Move(name="Liquidation", power=85, attack_type="Physical", type="Water", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0, flags='a',
                        effect_type="opponent_modifier", special_effect=[0, 0, -1, 0, 0, 0, 0, 0, 0], effect_accuracy=0.2),

    'Lovely Kiss': Move(name="Lovely Kiss", power=0, attack_type="Status", type="Normal", accuracy=0.75, pp=10,
                        crit=0, priority=0, recoil=0,
                        effect_type="target_non_volatile", special_effect=Sleep),

    'Hyper Voice': Move(name="Hyper Voice", power=90, attack_type="Special", type="Normal", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0, flags='f'),

    'Low Sweep': Move(name="Low Sweep", power=65, attack_type="Physical", type="Fighting", accuracy=1, pp=20,
                      crit=0, priority=0, recoil=0, flags='a',
                      effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -1, 0, 0, 0]),

    'Lunge': Move(name="Lunge", power=80, attack_type="Physical", type="Bug", accuracy=1, pp=15,
                  crit=0, priority=0, recoil=0, flags='a',
                  effect_type="opponent_modifier", special_effect=[0, -1, 0, 0, 0, 0, 0, 0, 0]),

    'Mean Look': Move(name="Mean Look", power=0, attack_type="Status", type="Normal", accuracy=1, pp=20,
                      crit=0, priority=0, flags='b',
                      effect_type="target_volatile", special_effect=Trapped),

    'Megahorn': Move(name="Megahorn", power=120, attack_type="Physical", type="Bug", accuracy=0.85, pp=10, flags='a'),

    'Memento': Move(name="Memento", power=0, attack_type="Status", type="Dark", accuracy=1, pp=10,
                    crit=0, priority=0, deduct=1,
                    effect_type="opponent_modifier", special_effect=[0, -2, 0, -2, 0, 0, 0, 0, 0]),

    'Mind Blown': Move(name="Mind Blown", power=150, attack_type="Special", type="Fire", accuracy=1, pp=5,
                       crit=0, priority=0, deduct=0.5),

    'Mirror Coat': Move(name="Mirror Coat", power=0, attack_type="Status", type="Psychic", accuracy=1, pp=20,
                        crit=0, priority=-5, recoil=0,
                        effect_type="countering"),

    'Moonblast': Move(name="Moonblast", power=95, attack_type="Special", type="Fairy", accuracy=1, pp=15,
                      crit=0, priority=0, recoil=0,
                      effect_type="opponent_modifier", special_effect=[0, 0, 0, -1, 0, 0, 0, 0, 0], effect_accuracy=0.3),

    'Muddy Water': Move(name="Muddy Water", power=90, attack_type="Special", type="Water", accuracy=0.85, pp=10,
                        crit=0, priority=0, recoil=0,
                        effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, 0, 0, -1, 0], effect_accuracy=0.3),

    'Nasty Plot': Move(name="Nasty Plot", power=0, attack_type="Status", type="Dark", accuracy=GUARANTEE_ACCURACY, pp=20,
                       crit=0, priority=0, recoil=0, flags='b',
                       effect_type="self_modifier", special_effect=[0, 0, 0, 2, 0, 0, 0, 0, 0]),

    'Night Daze': Move(name="Night Daze", power=85, attack_type="Special", type="Dark", accuracy=0.95, pp=10,  # unique for Zoroark
                       crit=0, priority=0, recoil=0,
                       effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, 0, 0, -1, 0], effect_accuracy=0.4),

    'Night Slash': Move(name="Night Slash", power=70, attack_type="Physical", type="Dark", accuracy=1, pp=15,
                        crit=1, priority=0),

    'Nuzzle': Move(name="Nuzzle", power=20, attack_type="Physical", type="Electric", accuracy=1, pp=20,
                   crit=0, priority=0, recoil=0, flags='a',
                   effect_type="target_non_volatile", special_effect=Paralysis),

    'Outrage': Move(name="Outrage", power=120, attack_type="Physical", type="Dragon", accuracy=1, pp=10,
                    flags='a', charging="Frenzy"),

    'Pain Split': Move(name="Pain Split", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=5,
                       effect_type="hp_split", special_effect="Split"),
    'Parabolic Charge': Move(name="Parabolic Charge", power=65, attack_type="Special", type="Electric", accuracy=1, pp=20,
                             crit=0, priority=0, recoil=0,
                             effect_type="hp_draining", special_effect=0.5),

    'Parting Shot': Move(name="Parting Shot", power=0, attack_type="Status", type="Dark", accuracy=1, pp=20,
                         effect_type=["switching", "opponent_modifier"], special_effect=[None, [0, -1, 0, -1, 0, 0, 0, 0, 0]]),

    'Tearful Look': Move(name="Tearful Look", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=20,
                         effect_type="opponent_modifier", special_effect=[0, -1, 0, -1, 0, 0, 0, 0, 0]),

    'Payback': Move(name="Payback", power=50, attack_type="Physical", type="Dark", accuracy=1, pp=20,
                    crit=0, priority=0, flags='a',
                    effect_type="after_hand"),

    'Petal Dance': Move(name="Petal Dance", power=120, attack_type="Special", type="Grass", accuracy=1, pp=10,
                        charging="Frenzy"),

    'Phantom Force': Move(name="Phantom Force", power=90, attack_type="Physical", type="Ghost", accuracy=1, pp=10,
                          charging="Semi-invulnerable", flags='a'),

    'Pin Missile': Move(name="Pin Missile", power=25, attack_type="Physical", type="Bug", accuracy=0.9, pp=20,
                        crit=0, priority=0, multi=[True, 5]),
    'Play Rough': Move(name="Play Rough", power=90, attack_type="Physical", type="Fairy", accuracy=0.9, pp=10,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="opponent_modifier", special_effect=[0, -1, 0, 0, 0, 0, 0, 0, 0], effect_accuracy=0.1),

    'Poison Fang': Move(name="Poison Fang", power=50, attack_type="Physical", type="Poison", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=0, flags='ad',
                        effect_type="target_non_volatile", special_effect=BadPoison, effect_accuracy=0.5),

    'Poison Jab': Move(name="Poison Jab", power=80, attack_type="Physical", type="Poison", accuracy=1, pp=20,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="target_non_volatile", special_effect=Poison, effect_accuracy=0.3),

    'Poison Tail': Move(name="Poison Tail", power=50, attack_type="Physical", type="Poison", accuracy=1, pp=25,
                        crit=1, priority=0, recoil=0, flags='a',
                        effect_type="target_non_volatile", special_effect=Poison, effect_accuracy=0.1),

    'Pollen Puff': Move(name="Pollen Puff", power=90, attack_type="Special", type="Bug", accuracy=1, pp=15,
                        flags='i'),

    'Power Gem': Move(name="Power Gem", power=80, attack_type="Special", type="Rock", accuracy=1, pp=20),

    'Power Trip': Move(name="Power Trip", power=20, attack_type="Physical", type="Dark", accuracy=1, pp=10,
                       crit=0, priority=0, flags='a',
                       effect_type="modifier_dependent"),

    'Power Whip': Move(name="Power Whip", power=120, attack_type="Physical", type="Grass", accuracy=0.85, pp=15,
                       crit=0, priority=0, recoil=0, flags='a'),

    'Power-Up Punch': Move(name="Power-Up Punch", power=40, attack_type="Physical", type="Fighting", accuracy=1, pp=20,
                           crit=0, priority=0, recoil=0, flags='ae',
                           effect_type="self_modifier", special_effect=[0, 1, 0, 0, 0, 0, 0, 0, 0]),

    'Protect': Move(name="Protect", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=10,
                    crit=0, priority=4, recoil=0, flags='b',
                    effect_type="user_protection"),

    'Psychic Fangs': Move(name="Psychic Fangs", power=85, attack_type="Physical", type="Psychic", accuracy=1, pp=10,
                          crit=0, priority=0, recoil=0, flags='ad',
                          effect_type="remove_team_buff"),

    'Psychic': Move(name="Psychic", power=90, attack_type="Special", type="Psychic", accuracy=1, pp=10,
                    crit=0, priority=0, recoil=0,
                    effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -1, 0, 0, 0, 0], effect_accuracy=0.1),

    'Psycho Cut': Move(name="Psycho Cut", power=70, attack_type="Physical", type="Psychic", accuracy=1, pp=20,
                       crit=1, flags='a'),

    'Psyshock': Move(name="Psyshock", power=80, attack_type="Special", type="Psychic", accuracy=1, pp=10,
                     inverseDef=True),

    'Quick Attack': Move(name="Quick Attack", power=40, attack_type="Physical", type="Normal", accuracy=1, pp=30,
                         crit=0, priority=1, flags='a'),

    'Quiver Dance': Move(name="Quiver Dance", power=0, attack_type="Status", type="Bug", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="self_modifier", special_effect=[0, 0, 0, 1, 1, 1, 0, 0, 0]),

    'Raging Fury': Move(name="Raging Fury", power=90, attack_type="Physical", type="Fire", accuracy=1, pp=10,
                        flags='a', charging="Frenzy"),

    'Rain Dance': Move(name="Rain Dance", power=0, attack_type="Status", type="Water", accuracy=GUARANTEE_ACCURACY, pp=5,
                       crit=0, priority=0, recoil=0, flags='b',
                       effect_type="weather_effect", special_effect=Rain),

    'Rapid Spin': Move(name="Rapid Spin", power=50, attack_type="Physical", type="Normal", accuracy=1, pp=40,
                       crit=0, priority=0, flags='a',
                       effect_type=["self_modifier", "clear_entry_hazard"], special_effect=[[0, 0, 0, 0, 0, 1, 0, 0, 0], None]),

    'Razor Shell': Move(name="RazorShell", power=75, attack_type="Physical", type="Water", accuracy=0.95, pp=10,
                        crit=0, priority=0, recoil=0, flags='a',
                        effect_type="opponent_modifier", special_effect=[0, 0, -1, 0, 0, 0, 0, 0, 0], effect_accuracy=0.5),

    'Recover': Move(name="Recover", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=10,
                    crit=0, priority=0, recoil=0, flags='b',
                    effect_type="self_heal", special_effect=0.3),  # nerfed

    'Reflect': Move(name="Reflect", power=0, attack_type="Status", type="Psychic", accuracy=GUARANTEE_ACCURACY, pp=20,
                    crit=0, priority=0, recoil=0, flags='b',
                    effect_type="self_team_buff", special_effect="Reflect"),

    'Tailwind': Move(name="Tailwind", power=0, attack_type="Status", type="Flying", accuracy=GUARANTEE_ACCURACY, pp=20,
                     crit=0, priority=0, recoil=0, flags='b',
                     effect_type="self_team_buff", special_effect="Tailwind"),

    'Revenge': Move(name="Revenge", power=60, attack_type="Physical", type="Fighting", accuracy=1, pp=20,
                    crit=0, priority=-4, flags='a',
                    effect_type="after_hand"),

    'Rock Blast': Move(name="Rock Blast", power=25, attack_type="Physical", type="Rock", accuracy=0.9, pp=10,
                       crit=0, priority=0, multi=[True, 5], flags='i'),

    'Water Shuriken': Move(name="Water Shuriken", power=20, attack_type="Special", type="Water", accuracy=1, pp=20,
                           crit=0, priority=1, multi=[True, 5]),

    'Rock Slide': Move(name="Rock Slide", power=75, attack_type="Physical", type="Rock", accuracy=0.9, pp=10,
                       crit=0, priority=0, recoil=0,
                       effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Sacred Sword': Move(name="Sacred Sword", power=90, attack_type="Physical", type="Fighting", accuracy=1, pp=15,
                         ignoreEvasion=True, ignoreDef=True, crit=0, priority=0, recoil=0, flags='a'),

    'Sand Tomb': Move(name="Sand Tomb", power=35, attack_type="Physical", type="Ground", accuracy=0.85, pp=15,
                      crit=0, priority=0,
                      effect_type="target_volatile", special_effect=Binding),
    'Sandstorm': Move(name="Sandstorm", power=0, attack_type="Status", type="Ground", accuracy=GUARANTEE_ACCURACY, pp=5,
                      crit=0, priority=0, recoil=0, flags='b',
                      effect_type="weather_effect", special_effect=Sandstorm),

    'Scald': Move(name="Scald", power=80, attack_type="Special", type="Water", accuracy=1, pp=15,
                  crit=0, priority=0, recoil=0, flags='c',
                  effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.3),

    'Searing Shot': Move(name="Searing Shot", power=100, attack_type="Special", type="Fire", accuracy=1, pp=5,
                         crit=0, priority=0, recoil=0, flags='i',
                         effect_type="target_non_volatile", special_effect=Burn, effect_accuracy=0.3),

    'Seed Bomb': Move(name="Seed Bomb", power=80, attack_type="Physical", type="Grass", accuracy=1, pp=15,
                      crit=0, priority=0, flags='i'),

    'Self-Destruct': Move(name="Self-Destruct", power=200, attack_type="Physical", type="Normal", accuracy=1, pp=5,
                          crit=0, priority=0, deduct=1),

    'Shadow Ball': Move(name="Shadow Ball", power=80, attack_type="Special", type="Ghost", accuracy=1, pp=15,  # bulletproof immune
                        crit=0, priority=0, recoil=0, flags='i',
                        effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -1, 0, 0, 0, 0], effect_accuracy=0.2),

    'Shadow Claw': Move(name="Shadow Claw", power=80, attack_type="Physical", type="Ghost", accuracy=1, pp=20,
                        crit=1, flags='a'),

    'Slash': Move(name="Slash", power=70, attack_type="Physical", type="Normal", accuracy=1, pp=20,
                        crit=1, flags='a'),

    'Frost Breath': Move(name="Frost Breath", power=60, attack_type="Special", type="Ice", accuracy=0.9, pp=10,
                         crit=4),

    'Shadow Sneak': Move(name="Shadow Sneak", power=40, attack_type="Physical", type="Ghost", accuracy=1, pp=30,
                         crit=0, priority=1, flags='a'),

    'Shell Smash': Move(name="Shell Smash", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=20,
                        crit=0, priority=0, recoil=0, flags='b',
                        effect_type="self_modifier", special_effect=[0, 2, -1, 2, -1, 2, 0, 0, 0]),

    'Signal Beam': Move(name="Signal Beam", power=75, attack_type="Special", type="Bug", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=0,
                        effect_type="target_volatile", special_effect=Confused, effect_accuracy=0.1),

    'Slack Off': Move(name="Slack Off", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=10,
                      crit=0, priority=0, recoil=0, flags='b',
                      effect_type="self_heal", special_effect=0.3),  # nerfed

    'Sleep Powder': Move(name="Sleep Powder", power=0, attack_type="Status", type="Grass", accuracy=0.75, pp=15,  # grass type immune
                         crit=0, priority=0, recoil=0, flags='g',
                         effect_type="target_non_volatile", special_effect=Sleep),

    'Sludge Bomb': Move(name="Sludge Bomb", power=90, attack_type="Special", type="Poison", accuracy=1, pp=10,  # bulletproof immune
                        crit=0, priority=0, recoil=0, flags='i',
                        effect_type="target_non_volatile", special_effect=Poison, effect_accuracy=0.3),

    'Sludge Wave': Move(name="Sludge Wave", power=95, attack_type="Special", type="Poison", accuracy=1, pp=10,  # bulletproof immune
                        crit=0, priority=0, recoil=0,
                        effect_type="target_non_volatile", special_effect=Poison, effect_accuracy=0.1),

    'Solar Beam': Move(name="Solar Beam", power=120, attack_type="Special", type="Grass", accuracy=1, pp=10,
                       crit=0, priority=0, recoil=0, charging="Charging"),

    'Skull Bash': Move(name="Skull Bash", power=130, attack_type="Physical", type="Normal", accuracy=1, pp=10,
                       crit=0, priority=0, recoil=0, charging="Charging", flags='a',
                       effect_type="self_modifier", special_effect=[0, 0, 1, 0, 0, 0, 0, 0, 0]),

    'Solar Blade': Move(name="Solar Blade", power=125, attack_type="Physical", type="Grass", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0, charging="Charging", flags='a', ),

    'Spark': Move(name="Spark", power=65, attack_type="Physical", type="Electric", accuracy=1, pp=20,
                  crit=0, priority=0, recoil=0, flags='a',
                  effect_type="target_non_volatile", special_effect=Paralysis, effect_accuracy=0.3),

    'Spikes': Move(name="Spikes", power=0, attack_type="Status", type="Ground", accuracy=GUARANTEE_ACCURACY, pp=20,
                   crit=0, priority=0, recoil=0, flags='b',
                   effect_type="entry_hazard", special_effect="Spikes"),

    'Spirit Break': Move(name="Spirit Break", power=75, attack_type="Physical", type="Fairy", accuracy=1, pp=15,
                         crit=0, priority=0, recoil=0, flags='a',
                         effect_type="opponent_modifier", special_effect=[0, 0, 0, -1, 0, 0, 0, 0, 0]),
    'Spore': Move(name="Spore", power=0, attack_type="Status", type="Grass", accuracy=1, pp=10,  # grass type immune
                  crit=0, priority=0, recoil=0, flags='g',
                  effect_type="target_non_volatile", special_effect=Sleep),

    'Stealth Rock': Move(name="Stealth Rock", power=0, attack_type="Status", type="Rock", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="entry_hazard", special_effect="Stealth Rock"),

    'Sticky Web': Move(name="Sticky Web", power=0, attack_type="Status", type="Bug", accuracy=GUARANTEE_ACCURACY, pp=20,
                       crit=0, priority=0, recoil=0, flags='b',
                       effect_type="entry_hazard", special_effect="Sticky Web"),

    'Stone Edge': Move(name="Stone Edge", power=100, attack_type="Physical", type="Rock", accuracy=0.8, pp=5,
                       crit=1, priority=0),

    'Stored Power': Move(name="Stored Power", power=20, attack_type="Special", type="Psychic", accuracy=1, pp=10,
                         crit=0, priority=0,
                         effect_type="modifier_dependent"),

    'Strange Steam': Move(name="Strange Steam", power=90, attack_type="Special", type="Fairy", accuracy=0.95, pp=10,
                          crit=0, priority=0, recoil=0,
                          effect_type="target_volatile", special_effect=Confused, effect_accuracy=0.2),

    'Rock Climb': Move(name="Rock Climb", power=90, attack_type="Physical", type="Rock", accuracy=0.85, pp=20,
                          crit=0, priority=0, recoil=0, flags='a',
                          effect_type="target_volatile", special_effect=Confused, effect_accuracy=0.2),

    'Dynamic Punch': Move(name="Dynamic Punch", power=100, attack_type="Physical", type="Fighting", accuracy=0.5, pp=5,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="target_volatile", special_effect=Confused),

    'Strength': Move(name="Strength", power=80, attack_type="Physical", type="Normal", accuracy=1, pp=15, flags='a'),

    'Struggle Bug': Move(name="Struggle Bug", power=50, attack_type="Special", type="Bug", accuracy=1, pp=20,
                         crit=0, priority=0, recoil=0,
                         effect_type="opponent_modifier", special_effect=[0, 0, 0, -1, 0, 0, 0, 0, 0]),

    'Octazooka': Move(name="Octazooka", power=65, attack_type="Special", type="Water", accuracy=0.85, pp=10,
                         crit=0, priority=0, recoil=0, flags='i',
                         effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, 0, 0, -1, 0], effect_accuracy=0.5),

    'Submission': Move(name="Submission", power=80, attack_type="Physical", type="Fighting", accuracy=0.8, pp=20,
                       crit=0, priority=0, recoil=1 / 4, flags='a'),

    'Sucker Punch': Move(name="Sucker Punch", power=70, attack_type="Physical", type="Dark", accuracy=1, pp=5,
                         crit=0, priority=1, flags='a'),

    'Sunny Day': Move(name="Sunny Day", power=0, attack_type="Status", type="Fire", accuracy=GUARANTEE_ACCURACY, pp=5,
                      crit=0, priority=0, recoil=0, flags='b',
                      effect_type="weather_effect", special_effect=Sunny),

    'Superpower': Move(name="Superpower", power=120, attack_type="Physical", type="Fighting", accuracy=1, pp=5,
                       crit=0, priority=0, recoil=0, flags='a',
                       effect_type="self_modifier", special_effect=[0, -1, -1, 0, 0, 0, 0, 0, 0]),

    'Surf': Move(name="Surf", power=90, attack_type="Special", type="Water", accuracy=1, pp=15),

    'Swords Dance': Move(name="Swords Dance", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="self_modifier", special_effect=[0, 2, 0, 0, 0, 0, 0, 0, 0]),

    'Shift Gear': Move(name="Shift Gear", power=0, attack_type="Status", type="Steel", accuracy=GUARANTEE_ACCURACY, pp=10,
                       crit=0, priority=0, recoil=0, flags='b',
                       effect_type="self_modifier", special_effect=[0, 1, 0, 0, 0, 2, 0, 0, 0]),

    'Scary Face': Move(name="Scary Face", power=0, attack_type="Status", type="Normal", accuracy=1, pp=20,
                       crit=0, priority=0, recoil=0,
                       effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, 0, -2, 0, 0, 0]),

    'Work Up': Move(name="Work Up", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=20,
                    crit=0, priority=0, recoil=0, flags='b',
                    effect_type="self_modifier", special_effect=[0, 1, 0, 1, 0, 0, 0, 0, 0]),

    'Double Team': Move(name="Double Team", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=15,
                        crit=0, priority=0, recoil=0, flags='b',
                        effect_type="self_modifier", special_effect=[0, 0, 0, 0, 0, 0, 1, 0, 0]),

    'Crow Dance': Move(name="Crow Dance", power=0, attack_type="Status", type="Dark", accuracy=GUARANTEE_ACCURACY, pp=10,
                       crit=0, priority=0, recoil=0, flags='b', custom=True,
                       effect_type=["self_modifier", "opponent_modifier"], special_effect=[[0, 2, 1, 2, 1, -2, 0, 0, 0], [0, 0, 0, 0, 0, 2, 0, 1, 0]]),

    'Tail Glow': Move(name="Tail Glow", power=0, attack_type="Status", type="Bug", accuracy=GUARANTEE_ACCURACY, pp=20,
                      crit=0, priority=0, recoil=0, flags='b',
                      effect_type="self_modifier", special_effect=[0, 0, 0, 3, 0, 0, 0, 0, 0]),

    'Take Down': Move(name="Take Down", power=90, attack_type="Physical", type="Normal", accuracy=0.85, pp=20,
                      crit=0, priority=0, recoil=1 / 4, flags='a'),

    'Taunt': Move(name="Taunt", power=0, attack_type="Status", type="Dark", accuracy=1, pp=20,
                  effect_type="target_disable", special_effect="Taunt"),

    'Throat Chop': Move(name="Throat Chop", power=80, attack_type="Physical", type="Dark", accuracy=1, pp=15, flags='a',
                  effect_type="target_disable", special_effect="Sound"),

    'Thrash': Move(name="Thrash", power=120, attack_type="Physical", type="Normal", accuracy=1, pp=10,
                   flags='a', charging="Frenzy"),

    'Thunder Punch': Move(name="Thunder Punch", power=75, attack_type="Physical", type="Electric", accuracy=1, pp=15,
                          crit=0, priority=0, recoil=0, flags='ae',
                          effect_type="target_non_volatile", special_effect=Paralysis, effect_accuracy=0.1),

    'Thunder Wave': Move(name="Thunder Wave", power=0, attack_type="Status", type="Electric", accuracy=0.9, pp=20,
                         crit=0, priority=0, recoil=0,
                         effect_type="target_non_volatile", special_effect=Paralysis),

    'Thunder': Move(name="Thunder", power=110, attack_type="Special", type="Electric", accuracy=0.7, pp=5,
                    crit=0, priority=0, recoil=0,
                    effect_type="target_non_volatile", special_effect=Paralysis, effect_accuracy=0.3),

    'Hurricane': Move(name="Hurricane", power=110, attack_type="Special", type="Flying", accuracy=0.7, pp=5,
                      crit=0, priority=0, recoil=0,
                      effect_type="target_non_volatile", special_effect=Confused, effect_accuracy=0.3),

    'Thunderbolt': Move(name="Thunderbolt", power=90, attack_type="Special", type="Electric", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=0,
                        effect_type="target_non_volatile", special_effect=Paralysis, effect_accuracy=0.1),

    'Tickle': Move(name="Tickle", power=0, attack_type="Status", type="Normal", accuracy=1, pp=20,
                   crit=0, priority=0, recoil=0,
                   effect_type="opponent_modifier", special_effect=[0, -1, -1, 0, 0, 0, 0, 0, 0]),

    'Noble Roar': Move(name="Noble Roar", power=0, attack_type="Status", type="Normal", accuracy=1, pp=30,
                   crit=0, priority=0, recoil=0, flags='f',
                   effect_type="opponent_modifier", special_effect=[0, -1, 0, -1, 0, 0, 0, 0, 0]),

    'Torment': Move(name="Torment", power=0, attack_type="Status", type="Dark", accuracy=1, pp=15,
                    effect_type="target_volatile", special_effect=Torment),

    'Toxic Spikes': Move(name="Toxic Spikes", power=0, attack_type="Status", type="Poison", accuracy=GUARANTEE_ACCURACY, pp=20,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="entry_hazard", special_effect="Toxic Spikes"),

    'Toxic': Move(name="Toxic", power=0, attack_type="Status", type="Poison", accuracy=0.9, pp=10,  # poison type guarantee accuracy
                  crit=0, priority=0, recoil=0,
                  effect_type="target_non_volatile", special_effect=BadPoison),

    'Tri Attack': Move(name="Tri Attack", power=80, attack_type="Special", type="Normal", accuracy=1, pp=10,
                       crit=1, priority=0, recoil=0,
                       effect_type="target_non_volatile", special_effect=Tri, effect_accuracy=0.2),

    'Trick Room': Move(name="Trick Room", power=0, attack_type="Status", type="Psychic", accuracy=GUARANTEE_ACCURACY, pp=5,
                       flags='b',
                       effect_type="field_effect", special_effect="Trick Room"),

    'U-Turn': Move(name="U-Turn", power=70, attack_type="Physical", type="Bug", accuracy=1, pp=20,
                   flags='a',
                   effect_type="switching"),

    'Fell Stinger': Move(name="Fell Stinger", power=50, attack_type="Physical", type="Bug", accuracy=1, pp=25,
                         flags='a', ),

    'Vacuum Wave': Move(name="Vacuum Wave", power=40, attack_type="Special", type="Fighting", accuracy=1, pp=35,
                        crit=0, priority=1),

    'Volt Switch': Move(name="Volt Switch", power=70, attack_type="Special", type="Electric", accuracy=1, pp=20,
                        effect_type="switching"),

    'Wail': Move(name="Wail", power=90, attack_type="Special", type="Ghost", accuracy=1, pp=10,
                 custom=True, flags='f',
                 effect_type="opponent_modifier", special_effect=[0, 0, 0, 0, -1, 0, 0, -1, 0], effect_accuracy=0.5),

    'Water Pulse': Move(name="Water Pulse", power=60, attack_type="Special", type="Water", accuracy=1, pp=20,
                        crit=0, priority=0, recoil=0, flags='h',
                        effect_type="target_volatile", special_effect=Confused, effect_accuracy=0.2),

    'Waterfall': Move(name="Waterfall", power=80, attack_type="Physical", type="Water", accuracy=1, pp=15,
                      crit=0, priority=0, recoil=0, flags='a',
                      effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.2),

    'Whirlpool': Move(name="Whirlpool", power=35, attack_type="Special", type="Water", accuracy=0.85, pp=15,
                      crit=0, priority=0,
                      effect_type="target_volatile", special_effect=Binding),

    'Cling': Move(name="Cling", power=35, attack_type="Physical", type="Fairy", accuracy=0.9, pp=15,
                  crit=0, priority=0, flags='a', custom=True,
                  effect_type="target_volatile", special_effect=Binding),

    'Charming Tap': Move(name="Charming Tap", power=60, attack_type="Physical", type="Fairy", accuracy=1, pp=20,
                         crit=0, priority=0, flags='a', custom=True,
                         effect_type="opponent_modifier", special_effect=[0, -1, 0, 0, 0, 0, 0, 0, 0]),

    'Sparkling Punch': Move(name="Sparkling Punch", power=80, attack_type="Physical", type="Fairy", accuracy=1, pp=15,
                            crit=0, priority=0, flags='ae', custom=True,
                            effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Sweet Dreams': Move(name="Sweet Dreams", power=0, attack_type="Status", type="Fairy", accuracy=GUARANTEE_ACCURACY, pp=15,
                            crit=0, priority=0, custom=True, flags='b',
                            effect_type="target_non_volatile", special_effect=Sleep, effect_accuracy=0.7),

    'Wild Charge': Move(name="Wild Charge", power=90, attack_type="Physical", type="Electric", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=1 / 4, flags='a'),

    'Will-O-Wisp': Move(name="Will-O-Wisp", power=0, attack_type="Status", type="Fire", accuracy=0.85, pp=15,
                        crit=0, priority=0, recoil=0,
                        effect_type="target_non_volatile", special_effect=Burn),

    'Wood Hammer': Move(name="Wood Hammer", power=120, attack_type="Physical", type="Grass", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=1 / 3, flags='a'),

    'X-Scissor': Move(name="X-Scissor", power=80, attack_type="Physical", type="Bug", accuracy=1, pp=20, flags='a'),

    'Yawn': Move(name="Yawn", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=10,
                 crit=0, priority=0,
                 effect_type="target_volatile", special_effect=Yawn),

    'Zap Cannon': Move(name="Zap Cannon", power=120, attack_type="Special", type="Electric", accuracy=0.5, pp=5,
                       crit=0, priority=0, recoil=0, flags='i',
                       effect_type="target_non_volatile", special_effect=Paralysis),

    'Zen Headbutt': Move(name="Zen Headbutt", power=80, attack_type="Physical", type="Psychic", accuracy=0.9, pp=15,
                         crit=0, priority=0, recoil=0, flags='a',
                         effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.2),

    'Heal Bell': Move(name="Heal Bell", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=5,
                      crit=0, priority=0, recoil=0, flags='b',
                      effect_type="team_status_heal"),

    'Aromatherapy': Move(name="Aromatherapy", power=0, attack_type="Status", type="Grass", accuracy=GUARANTEE_ACCURACY, pp=5,
                         crit=0, priority=0, recoil=0, flags='b',
                         effect_type="team_status_heal"),

    'Smack Down': Move(name="Smack Down", power=50, attack_type="Physical", type="Rock", accuracy=1, pp=20,
                       crit=0, priority=0, recoil=0,
                       effect_type="target_volatile", special_effect=Grounded),

    'Magnet Rise': Move(name="Magnet Rise", power=0, attack_type="Status", type="Electric", accuracy=GUARANTEE_ACCURACY, pp=20,
                        crit=0, priority=0, recoil=0,
                        effect_type="user_volatile", special_effect=Ungrounded),

    'Double Sickle': Move(name="Double Sickle", power=50, attack_type="Physical", type="Ghost", accuracy=0.9, pp=10,
                          crit=0, priority=0, recoil=0, multi=[False, 2], flags='a', custom=True,
                          effect_type=["target_non_volatile", "hp_draining"], special_effect=[Poison, 0.15], effect_accuracy=0.2),

    'Octolock': Move(name="Octolock", power=0, attack_type="Status", type="Fighting", accuracy=1, pp=15,
                     crit=0, priority=0,
                     effect_type=["target_volatile", "target_volatile"], special_effect=[Trapped, Octolock]),

    'Fish Needle': Move(name="Fish Needle", power=90, attack_type="Special", type="Water", accuracy=1, pp=10,
                        crit=0, priority=0, recoil=0, custom=True,
                        effect_type="target_non_volatile", special_effect=BadPoison, effect_accuracy=0.5),

    'Enragement': Move(name="Enragement", power=70, attack_type="Physical", type="Flying", accuracy=1, pp=5,
                       custom=True, effect_type="retaliation"),

    'Annihilation': Move(name="Annihilation", power=240, attack_type="Physical", type="Fighting", accuracy=0.7, pp=5,
                         crit=0, priority=0, recoil=1 / 4, flags='a', custom=True, charging="Charging"),

    'Crystalline Clone': Move(name="Crystalline Clone", power=0, attack_type="Status", type="Ice", accuracy=GUARANTEE_ACCURACY, pp=10,
                              crit=0, priority=0, multi=[True, 5], custom=True, flags='b',
                              effect_type="self_modifier", special_effect=[0, 0, 0, 1, 0, 0, 0, 1, 0], effect_accuracy=0.5),

    'Bodhisattva': Move(name="Bodhisattva", power=80, attack_type="Special", type="Ground", accuracy=1, pp=10,
                        crit=0, priority=-2, custom=True, flags='a', ignoreType=["Flying"],
                        effect_type="self_modifier", special_effect=[0, 0, 1, 0, 1, 0, 0, 0, 0]),

    'Lotus Petal': Move(name="Lotus Petal", power=60, attack_type="Special", type="Grass", accuracy=1, pp=20,
                        crit=0, priority=1, custom=True, ),

    'Unbreakable Will': Move(name="Unbreakable Will", power=0, attack_type="Status", type="Fighting", accuracy=GUARANTEE_ACCURACY, pp=5,
                             crit=0, priority=0, deduct=1 / 4, flags='b', custom=True,
                             effect_type="self_modifier", special_effect=[0, 1, 1, 1, 1, 1, 0, 0, 0]),

    'Clangorous Soul': Move(name="Clangorous Soul", power=0, attack_type="Status", type="Dragon", accuracy=GUARANTEE_ACCURACY, pp=5,
                             crit=0, priority=0, deduct=1 / 3, flags='b',
                             effect_type="self_modifier", special_effect=[0, 1, 1, 1, 1, 0, 0, 0, 0]),

    'Moon Slash': Move(name="Moon Slash", power=80, attack_type="Physical", type="Dark", accuracy=1, pp=15,
                       crit=0, priority=0, flags='a', custom=True,
                       effect_type="hp_draining", special_effect=0.25),

    'Dragon Crescent': Move(name="Dragon Crescent", power=80, attack_type="Physical", type="Dragon", accuracy=1, pp=10,
                            crit=1, priority=0, flags='a', custom=True,
                            effect_type="target_non_volatile", special_effect=Flinch, effect_accuracy=0.2),

    'First Strike': Move(name="First Strike", power=60, attack_type="Physical", type="Steel", accuracy=1, pp=20,
                         crit=0, priority=2, flags='a', custom=True),

    'Fishious Rend': Move(name="Fishious Rend", power=85, attack_type="Physical", type="Water", accuracy=1, pp=10,
                          crit=0, priority=0, flags='ad',
                          effect_type="before_hand"),

    'Total Concentration': Move(name="Total Concentration", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=5,
                                crit=0, priority=0, custom=True, flags='b',
                                effect_type=["user_volatile", "user_volatile"], special_effect=[TotalConcentration, Trapped]),

    'Nichirin Sword': Move(name="Nichirin Sword", power=90, attack_type="Physical", type="Water", accuracy=1, pp=10,
                           crit=0, priority=0, custom=True, flags='a', interchangeType=["Fire"]),

    'Techno Blast': Move(name="Techno Blast", power=120, attack_type="Special", type="Normal", accuracy=1, pp=5,
                         crit=0, priority=0, interchangeType=["Water"]),

    'Tidal Surge': Move(name="Tidal Surge", power=90, attack_type="Special", type="Water", accuracy=0.9, pp=10,
                        crit=0, priority=0, recoil=0, custom=True,
                        effect_type="target_volatile", special_effect=Confused, effect_accuracy=0.3),

    'Boulder Smash': Move(name="Boulder Smash", power=100, attack_type="Physical", type="Rock", accuracy=0.7, pp=10,
                        crit=0, priority=0, recoil=0, custom=True,
                        effect_type="target_volatile", special_effect=Confused, effect_accuracy=0.5),

    'Thunderous Trident': Move(name="Thunderous Trident", power=120, attack_type="Special", type="Electric", accuracy=0.8, pp=5,
                               crit=0, priority=0, recoil=0, custom=True,
                               effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Cryokinesis': Move(name="Cryokinesis", power=80, attack_type="Special", type="Ice", accuracy=1, pp=15,
                        crit=0, priority=0, recoil=0, custom=True,
                        effect_type="target_non_volatile", special_effect=Freeze, effect_accuracy=0.2),

    'Clear Smog': Move(name="Clear Smog", power=50, attack_type="Special", type="Poison", accuracy=GUARANTEE_ACCURACY, pp=15,
                       effect_type="reset_target_modifier"),

    'Haze': Move(name="Haze", power=0, attack_type="Status", type="Ice", accuracy=GUARANTEE_ACCURACY, pp=30, flags='b',
                 effect_type=["reset_target_modifier", "reset_user_modifier"], special_effect=["", ""]),

    'Court Change': Move(name="Court Change", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=10, flags='b',
                         effect_type="swap_barrier"),

    'Revenant Charge': Move(name="Revenant Charge", power=100, attack_type="Physical", type="Ghost", accuracy=1, pp=10,
                        crit=0, priority=0, custom=True, flags='a',
                        effect_type="opponent_modifier", special_effect=[0, 0, -1, 0, 0, 0, 0, 0, 0], effect_accuracy=0.5),

    'Battle Axe': Move(name="Battle Axe", power=80, attack_type="Physical", type="Rock", accuracy=1, pp=15,
                            crit=0, priority=0, custom=True, flags='a',
                            effect_type="hp_draining", special_effect=0.25),

    'Thunderclap': Move(name="Thunderclap", power=80, attack_type="Physical", type="Electric", accuracy=1, pp=15,
                       crit=0, priority=0, custom=True, flags='a',
                       effect_type="target_non_volatile", special_effect=Paralysis, effect_accuracy=0.2),

    'Chaotic Shockwave': Move(name="Chaotic Shockwave", power=80, attack_type="Physical", type="Electric", accuracy=0.7, pp=10,
                        crit=0, priority=0, custom=True, flags='abf',
                        effect_type="target_volatile", special_effect=Flinch, effect_accuracy=0.3),

    'Feint': Move(name="Feint", power=30, attack_type="Physical", type="Normal", accuracy=1, pp=10,
                              crit=0, priority=2, flags='b'),

    'Lock-On': Move(name="Lock-On", power=0, attack_type="Status", type="Normal", accuracy=GUARANTEE_ACCURACY, pp=5,
                  crit=0, priority=0,
                    effect_type='target_volatile', special_effect=TakeAim),

    'Metronome': Move(name="Metronome", power=0, attack_type="Status", type="Normal", accuracy=1, pp=30),

    'History Rewritten': Move(name="History Rewritten", power=0, attack_type="Status", type="Normal", accuracy=1, pp=10, custom=True,
                 effect_type=["target_disable", "reset_target_modifier", "target_volatile"], special_effect=["Encore", "", Confused], effect_accuracy=0.6),

    'Soul Harvest': Move(name="Soul Harvest", power=50, attack_type="Special", type="Dark", accuracy=1, pp=10,
                              crit=0, priority=2, custom=True,
                              effect_type=["target_volatile", "hp_draining"], special_effect=[Binding, 0.5]),

    'Reign of Terror': Move(name="Reign of Terror", power=100, attack_type="Special", type="Ghost", accuracy=1, pp=5,
                         crit=0, priority=0, custom=True,
                         effect_type=["opponent_modifier", "target_volatile"], special_effect=[[0, 0, -1, 0, -1, -1, 0, 0, 0], Frighten], effect_accuracy=0.5),

    'Empyrean Glory': Move(name="Empyrean Glory", power=0, attack_type="Status", type="Flying", accuracy=GUARANTEE_ACCURACY, pp=5, flags='b', custom=True,
                              effect_type=["user_modifier", "team_status_heal", "self_heal", "weather_effect"], special_effect=[[0, 0, 1, 0, 1, 0, 1, 0, 0], "",0.25, Clear]),

    'Draconic Blade': Move(name="Draconic Blade", power=100, attack_type="Physical", type="Dragon", accuracy=1, pp=10, flags='a', custom=True,
                           effect_type=["opponent_modifier", "target_volatile"], special_effect=[[0, 0, 0, 0, 0, -1, 0, -1, 0], Frighten], effect_accuracy=0.3),
}
