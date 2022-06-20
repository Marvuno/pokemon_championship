import random
import math
import operator
import inspect
from contextlib import suppress

from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Data.moves import *
from Scripts.Battle.type_immunity import *


def notice(battleground):
    if battleground.reality:
        print(f"{CVIOLET2}{CBOLD}Character Ability: {inspect.currentframe().f_back.f_code.co_name.replace('_', ' ').title()}{CEND}")


def UseCharacterAbility(user_side, target_side, user, target, battleground, move="", abilityphase=1, verbose=False):
    def trashy(*args):
        # trash power makes poison moves more decimating
        if 'Poison' in move.type:
            move.power *= 1.3
            notice(battleground)

    def dim(*args):
        # although pokemon is slower being dim, they hit more accurately
        user.applied_modifier = [0, 0, 0, 0, 0, -1, 0, 1, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        notice(battleground)

    def sand_veil(*args):
        # boost pokemon evasion in a sandstorm
        if battleground.weather_effect.id == 'Sandstorm':
            move.evasion *= 1.25
            notice(battleground)

    def violence(*args):
        # boost move power for move with direct contact
        if 'a' in move.flags:
            move.power *= 1.3
            notice(battleground)

    def naive(*args):
        # trap user and target pokemon
        user.volatile_status['Trapped'] = 1
        target.volatile_status['Trapped'] = 1
        notice(battleground)

    def telekinesis(*args):
        # boost evasion for psychic Pokemon
        if 'Psychic' in user.type:
            user.applied_modifier = [0, 0, 0, 0, 0, 0, 1, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            notice(battleground)

    def energy_imbalance(*args):
        # trigger sudden death at the last pokemon
        if sum(1 for pokemon in user_side.team if pokemon.status != 'Fainted') == 1:
            battleground.sudden_death = True
            print("Sudden Death is activated!!!")
            sound(audio="Assets/music/sudden_death.mp3")
            notice(battleground)

    def death_realm(*args):
        # increase random stats when causing pokemon to faint
        if target.status == "Fainted":
            user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 0]
            user.applied_modifier[random.randint(1, 8)] += 1
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            notice(battleground)

    def monkey(*args):
        # monkey just being monkey
        if random.random() <= 0.2:
            if target_side.main and not battleground.auto_battle:
                input(f"{user_side.name}: Ook-ook! Eeek-aak-eek! (P.S. you may enter any key to proceed.)\n{target_side.name}: ")
                notice(battleground)

    def charm(*args):
        # charm causes opponent and its pokemon to get distracted and misses its move
        if random.random() <= 0.1:
            move.accuracy = 0
            if target_side.main and not battleground.auto_battle:
                input(f"{user_side.name}: Do I look {random.choice(['cute', 'charming', 'gorgeous', 'dazzling'])} today? (P.S. you may enter any key to proceed.)\n{target_side.name}: ")
                notice(battleground)

    def experienced(*args):
        # half recoil damage
        if move.recoil > 0:
            move.recoil *= 0.5
            notice(battleground)

    def ball_trick(*args):
        # boost move power for ball/bomb moves
        if 'i' in move.flags and battleground.reality:
            move.power *= 1.5
            notice(battleground)

    def mad_scientist(*args):
        # add priority for electric and steel type moves
        if 'Electric' in move.type or 'Steel' in move.type:
            move.priority += 1
            notice(battleground)

    def moody(*args):
        # random chance to increase and decrease user pokemon health
        random_factor = random.random()
        if random_factor <= 0.15:
            target.battle_stats[0] += math.floor(min(target.hp - target.battle_stats[0], target.hp * 0.15))
            notice(battleground)
        elif random_factor >= 0.75:
            target.battle_stats[0] -= math.floor(target.hp * 0.15)
            notice(battleground)

    def string_manipulation(*args):
        # manipulate invisible string to slow target Pokemon down
        if random.random() <= 0.2:
            target.applied_modifier = [0, 0, 0, 0, 0, -1, 0, 0, 0]
            target.modifier = list(map(operator.add, target.applied_modifier, target.modifier))
            notice(battleground)

    def heavy_blow(*args):
        # hit harder but move slower
        user.applied_modifier = [0, 2, 0, 0, 0, -2, 0, 0, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        notice(battleground)

    def nimble(*args):
        # move faster but hit less for physical moves
        user.applied_modifier = [0, -1, 0, 0, 0, 2, 0, 0, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        notice(battleground)

    def fireworks(*args):
        # deduct-HP moves no longer deduct HP (e.g. Mind Blown, Belly Drum!) and boost power for Mind Blown
        if move.deduct > 0:
            move.deduct = 0
            if move.name == 'Mind Blown':
                move.power *= 1.2
            notice(battleground)

    def gluttony(*args):
        # gluttony causes pokemon to consume anything, including entry hazard set up against them and in-battle barriers of opponent team
        if sum(user_side.entry_hazard.values()) > 0 or sum(target_side.in_battle_effects.values()) > 0:
            user_side.entry_hazard = dict.fromkeys(user_side.entry_hazard.keys(), 0)
            target_side.in_battle_effects = dict.fromkeys(target_side.in_battle_effects.keys(), 0)
            notice(battleground)

    def buggy(*args):
        # bug pokemon gains speed at the end of each turn (aka apply speed boost)
        if 'Bug' in user.type:
            user.ability += ['Speed Boost']
            notice(battleground)

    def brain_wave(*args):
        # boost additional effect chance and damage for psychic type moves
        if 'Psychic' in move.type:
            move.damage *= 1.3
            move.effect_accuracy *= 1.3
            notice(battleground)

    def champion(*args):
        champion_pokemon = {'Diantha': 'Gardevoir', 'Steven': 'Metagross', 'Leon': 'Charizard', 'Lance': 'Dragonite'}
        # champion signature pokemon get a boost
        # technically no same pokemon for each team
        if user.name == champion_pokemon[user_side.name]:
            user.applied_modifier = [0, 1, 0, 1, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            notice(battleground)

    def impatient(*args):
        # random chance to decrease target and user health
        # small random chance to trigger sudden death
        if random.random() <= 0.01:
            battleground.sudden_death = True
            print("Sudden Death is activated!!!")
            sound(audio="Assets/music/sudden_death.mp3")
            notice(battleground)
        elif random.random() >= 0.8:
            target.battle_stats[0] -= target.hp // 4
            user.battle_stats[0] -= user.hp // 8

    def outlier(*args):
        # apply super luck to every pokemon
        user.ability += ['Super Luck']
        notice(battleground)

    def thief(*args):
        # steal positive stats at a random chance
        if random.random() <= 0.2:
            user.applied_modifier = [modifier if modifier > 0 else 0 for modifier in target.modifier]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            target.modifier = [0 if modifier > 0 else modifier for modifier in target.modifier]

    def tenebrous(*args):
        # boost additional effect chance and damage for dark type moves
        if 'Dark' in move.type:
            move.damage *= 1.3
            move.effect_accuracy *= 1.3
            notice(battleground)

    def sucking(*args):
        # pokemon drains 30% HP for every attacking move at 50% HP or below
        if move.damage > 0 and user.battle_stats[0] <= user.hp // 2:
            user.battle_stats[0] += min(user.hp - user.battle_stats[0], math.floor((move.damage + min(target.battle_stats[0], 0)) * 0.3))
            notice(battleground)

    def ultra_boost(*args):
        # increase random stats for each pokemon at start except crit-ratio
        user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        user.applied_modifier[random.randint(1, 7)] += 1
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        notice(battleground)

    def plot_armor(*args):
        # last pokemon has 3 lives, when dead, it will recover all its HP twice
        if abilityphase == 1:
            if sum(1 for pokemon in user_side.team if pokemon.status != 'Fainted') == 1:  # last pokemon
                user.second_life = 2
        elif abilityphase == 5 and battleground.reality:
            if move.damage > user.battle_stats[0] and user.second_life > 0:
                user.second_life -= 1
                move.damage = 0
                user.battle_stats[0] = user.hp
                notice(battleground)
        elif abilityphase == 7:
            if user.battle_stats[0] <= 0 and user.second_life > 0:
                user.second_life -= 1
                user.battle_stats[0] = user.hp
                notice(battleground)
        elif abilityphase == 8:
            if user.battle_stats[0] <= 0 and user.second_life > 0:
                user.second_life -= 1
                user.battle_stats[0] = user.hp
                notice(battleground)

    def calm(*args):
        # pokemon is immune to any non-volatile status
        if user.status not in ['Normal', 'Fainted']:
            user.status, user.volatile_status['NonVolatile'] = 'Normal', 0
            notice(battleground)

    def ruthless(*args):
        # deal additional damage depending on target health and user health, the more the target health, the more it hit
        # however, also suffer additional damage from target
        if abilityphase == 4:
            move.damage = math.floor(move.damage * min(1.7, max(1, target.battle_stats[0] / user.battle_stats[0])))  # at most 1.7x
            notice(battleground)
        elif abilityphase == 5:
            move.damage = math.floor(move.damage * 1.3)  # suffer 30% more damage
            notice(battleground)

    def death_note(*args):
        # for user pokemon with boosts (>1 stats boost), inflict it with Perish Song
        if sum(target.modifier) > 1 and target.volatile_status['PerishSong'] == 0:
            target.volatile_status['PerishSong'] += 2
            notice(battleground)

    def soak(*args):
        # add water type to user pokemon
        if 'Water' not in user.type:
            user.type += ['Water']
            notice(battleground)

    def time_travel(*args):
        # user can stop any priority move with seer ability from time travel, rendering any priority move useless
        if move.priority > 0:
            move.accuracy = 0
            notice(battleground)

    def gargantuan(*args):
        # random chance to half damage from any incoming attack
        if random.random() <= 0.25:
            move.damage *= 0.5
            notice(battleground)

    def irrational(*args):
        # pokemon receives boost but confuses
        user.applied_modifier = [0, 1, 0, 1, 0, 1, 0, 0, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        user.volatile_status['Confused'] = random.randint(2, 5)
        notice(battleground)

    def light_speed(*args):
        # add electric type to user pokemon
        if 'Electric' not in user.type:
            user.type += ['Electric']
            user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            notice(battleground)

    def killer_instinct(*args):
        # random chance to deal double damage
        if random.random() <= 0.1:
            move.damage *= 2
            notice(battleground)

    def helper(*args):
        # start with reflect
        user_side.in_battle_effects['Reflect'] = TEAM_BUFF_TURNS
        notice(battleground)

    def wanderer(*args):
        # start with tailwind
        user_side.in_battle_effects['Tailwind'] = TEAM_BUFF_TURNS
        notice(battleground)

    def motivator(*args):
        # start with light screen
        user_side.in_battle_effects['Light Screen'] = TEAM_BUFF_TURNS
        notice(battleground)

    def curse_of_forest(*args):
        # apply grass type to every target pokemon
        if 'Grass' not in target.type:
            target.type += ['Grass']
            notice(battleground)

    def blunders(*args):
        # random chance for target to damage himself instead (its move damage applies to itself)
        if random.random() <= 0.1:
            user.battle_stats[0] -= move.damage
            move.damage = 0
            notice(battleground)

    def musical(*args):
        # random chance for special moves to paralyze, freeze and hypnotize target
        if random.random() <= 0.1:
            if target.status == "Normal" and move.attack_type == "Special":
                temporary_effect = random.choices([Freeze(1), Sleep(1), Paralysis(1)], weights=[1, 2, 3], k=1)[0]
                print(temporary_effect)
                target.status = status_effect_immunity_check(user, target, move, temporary_effect[0])
                target.volatile_status['NonVolatile'] = temporary_effect[1]
                notice(battleground)

    def infiltration(*args):
        # every user move ignores ability and weather (dead calm + mold breaker)
        # thus, apply dead calm and mold breaker instead
        ability_list = ['Dead Calm', 'Mold Breaker']
        if not all(ability in user.ability for ability in ability_list):
            user.ability = list(set(user.ability + ability_list))
            notice(battleground)

    def silhouette(*args):
        # apply illusion to every pokemon and shuffle second pokemon
        if 'Illusion' not in user.ability:
            user.ability += ['Illusion']
            non_fainted = [user_side.team.index(pokemon) for pokemon in user_side.team[2:] if pokemon.status != 'Fainted']
            if len(non_fainted) > 0:
                shuffle_choice = int(random.choice(non_fainted))
                user_side.team[1], user_side.team[shuffle_choice] = user_side.team[shuffle_choice], user_side.team[1]
            notice(battleground)

    def old_legends(*args):
        # pokemon immune to fairy type attacking moves
        if 'Fairy' in move.type and move.damage > 0:
            move.damage = 0
            notice(battleground)

    def blood_magic(*args):
        # pokemon drains 20% HP for every attacking move
        if move.damage > 0:
            user.battle_stats[0] += min(user.hp - user.battle_stats[0], math.floor((move.damage + min(target.battle_stats[0], 0)) * 0.2))
            notice(battleground)

    def primordial(*args):
        # always rain and apply swift swim to every pokemon
        if abilityphase == 0:
            battleground.starting_weather_effect = 'Rain'
            battleground.weather_effect = battleground.starting_weather_effect
        elif abilityphase == 1:
            user.ability += ['Swift Swim']
            notice(battleground)

    def last_stand(*args):
        # at the last pokemon, massive buff and renegerate all HP but suffer from BadPoison (start at 2/16)
        if sum(1 for pokemon in user_side.team if pokemon.status != 'Fainted') == 1:
            user.battle_stats[0] = user.hp
            user.applied_modifier = [0, 1, 1, 1, 1, 1, 1, 1, 1]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            user.status, user.volatile_status['NonVolatile'] = 'BadPoison', 2
            notice(battleground)

    list_of_character_abilities = {
        "Trashy": (2, trashy),
        "Dim": (1, dim),
        "Monkey": (3, monkey),
        "Sand Veil": (3, sand_veil),
        "Violence": (2, violence),
        "Naive": (1, naive),
        "Telekinesis": (1, telekinesis),
        "Energy Imbalance": (1, energy_imbalance),
        "Death Realm": (6, death_realm),
        "Charm": (3, charm),
        "Mad Scientist": (2, mad_scientist),
        "Moody": (8, moody),
        "Experienced": (2, experienced),
        "Ball Trick": (2, ball_trick),
        "String Manipulation": (8, string_manipulation),
        "Heavy Blow": (1, heavy_blow),
        "Nimble": (1, nimble),
        "Fireworks": (2, fireworks),
        "Gluttony": (8, gluttony),
        "Buggy": (1, buggy),
        "Brain Wave": (4, brain_wave),
        "Champion": (1, champion),
        "Impatient": (8, impatient),
        "Outlier": (1, outlier),
        "Thief": (4, thief),
        "Tenebrous": (4, tenebrous),
        "Sucking": (6, sucking),
        "Ultra Boost": (1, ultra_boost),
        "Plot Armor": ((1, 5, 7, 8), plot_armor),
        "Calm": ((7, 8), calm),
        "Ruthless": ((4, 5), ruthless),
        "Death Note": (8, death_note),
        "Soak": (1, soak),
        "Time Travel": (3, time_travel),
        "Gargantuan": (5, gargantuan),
        "Irrational": (1, irrational),
        "Light Speed": (1, light_speed),
        "Killer Instinct": (4, killer_instinct),
        "Helper": (0, helper),
        "Wanderer": (0, wanderer),
        "Motivator": (0, motivator),
        "Curse of Forest": ((1, 8), curse_of_forest),
        "Blunders": (5, blunders),
        "Musical": (6, musical),
        "Infiltration": (1, infiltration),
        "Silhouette": (1, silhouette),
        "Old Legends": (5, old_legends),
        "Blood Magic": (6, blood_magic),
        "Primordial": ((0, 1), primordial),
        "Last Stand": (1, last_stand),
    }

    with suppress(KeyError, AttributeError):
        vartype = type(list_of_character_abilities[user_side.ability][0])
        if vartype is tuple:
            if abilityphase in list_of_character_abilities[user_side.ability][0]:
                list_of_character_abilities[user_side.ability][1](user_side, target_side, user, target, battleground, move, abilityphase)
        elif vartype is int:
            if abilityphase == list_of_character_abilities[user_side.ability][0]:
                list_of_character_abilities[user_side.ability][1](user_side, target_side, user, target, battleground, move, abilityphase)
