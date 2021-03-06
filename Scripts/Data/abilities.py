import math
import operator
from contextlib import suppress

from Scripts.Art.text_color import *
from Scripts.Data.moves import *
from Scripts.Data.pokemon import *
from Scripts.Battle.type_chart import *
from Scripts.Battle.type_immunity import *


def UseAbility(user_side, target_side, user, target, battleground, move="", abilityphase=1, verbose=False):
    def cloudnine(*args):
        battleground.starting_weather_effect = 'Clear'
        battleground.weather_effect = battleground.starting_weather_effect

    def drizzle(*args):
        battleground.starting_weather_effect = 'Rain'
        battleground.weather_effect = battleground.starting_weather_effect

    def drought(*args):
        battleground.starting_weather_effect = 'Sunny'
        battleground.weather_effect = battleground.starting_weather_effect

    def snowwarning(*args):
        battleground.starting_weather_effect = 'Hail'
        battleground.weather_effect = battleground.starting_weather_effect

    def sandstream(*args):
        battleground.starting_weather_effect = 'Sandstorm'
        battleground.weather_effect = battleground.starting_weather_effect

    def download(*args):
        user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0] if target.battle_stats[2] < target.battle_stats[4] else [0, 0, 0, 1, 0, 0, 0, 0, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def intimidate(*args):
        if target.ability != "Clear Body" and target.ability != "Hyper Cutter":
            target.applied_modifier = [0, -1, 0, 0, 0, 0, 0, 0, 0]
            target.modifier = list(map(operator.add, target.applied_modifier, target.modifier))

    def anticipation(*args):
        for move in target.moveset:
            move = list_of_moves[move]
            type_effectiveness = math.prod([typeChart[move.type][user.type[x]] for x in range(len(user.type))])
            if type_effectiveness >= 2 and move.attack_type != "Status":
                print(f"{user.name} shuddered.")
                break

    def naturalcure(*args):
        if user.status != "Normal":
            user.status, user.volatile_status["NonVolatile"] = "Normal", 0

    # aegislash only
    def stancechange(*args):
        # when switched in
        if abilityphase == 1:
            user.name, user.type = user.default_name, user.default_type
            user.nominal_base_stats = user.default_nominal_base_stats
        # when using move
        elif abilityphase == 2:
            if move.attack_type != "Status":
                if user.charging[2] == 0:
                    # to prove it is shield form (spdef > spa)
                    if user.nominal_base_stats[4] > user.nominal_base_stats[3]:
                        # switched to blade form
                        print(f"{user.name} switches to Blade Forme.")
                        user.name = "Aegislash (Blade Forme)"
                        user.nominal_base_stats = list(map(operator.add, list_of_pokemon[user.name].base_stats, user.iv))
                        for x in range(1, 5):
                            user.battle_stats[x] = math.floor(0.01 * 2 * user.nominal_base_stats[x] * modifierChart[x][user.modifier[x]] * 100 + 5)
            elif move.name == "King's Shield":
                if user.nominal_base_stats[3] > user.nominal_base_stats[4]:
                    # switched to shield form
                    print(f"{user.name} switches to Shield Forme.")
                    user.name, user.type = user.default_name, user.default_type
                    user.nominal_base_stats = user.default_nominal_base_stats
                    for x in range(1, 5):
                        user.battle_stats[x] = math.floor(0.01 * 2 * user.nominal_base_stats[x] * modifierChart[x][user.modifier[x]] * 100 + 5)

    # zoroark only
    def illusion(*args):
        # switching in
        if abilityphase == 1:
            if sum(1 for pokemon in user_side.team if pokemon.status != "Fainted") != 1:
                user.disguise = True
                for pokemon in user_side.team[1:]:
                    if pokemon.status != "Fainted":  # use id when finalizing pokemon list
                        user.name, user.type = pokemon.name, pokemon.type
                        break
        elif abilityphase == 2 and battleground.reality:
            user.type = user.default_type
        elif abilityphase == 3 and battleground.reality:
            user.type = user.default_type
        elif abilityphase == 5 and battleground.reality:
            if move.damage > 0 and user.disguise:
                user.name, user.type = user.default_name, user.default_type
                print(f"{user.name} is in disguise!")
                user.disguise = False
        elif abilityphase == 8:
            if user.disguise:
                user.type = list_of_pokemon[user.name].type
        # switched out
        elif abilityphase == 9:
            user.name, user.type = user.default_name, user.default_type

    def prankster(*args):
        if move.attack_type == "Status" and "Dark" not in target.type:
            move.priority += 1

    def rockhead(*args):
        move.recoil = 0

    def marvelscale(*args):
        user.battle_stats[2] *= 1.5 if user.status != "Normal" else 1

    def adaptability(*args):
        move.abilitymodifier = math.floor(1 / 1.5 * 2) if move.type in user.type else 1

    def ironfist(*args):
        move.power *= 1.2 if 'e' in move.flags else 1

    def strongjaw(*args):
        move.power *= 1.5 if 'd' in move.flags else 1

    def megalauncher(*args):
        move.power *= 1.5 if 'h' in move.flags else 1

    def sheerforce(*args):
        if move.effect_type != "no_effect":
            if not (move.effect_type == "self_modifier" and sum(move.special_effect) < 0):
                move.power *= 1.3
                move.effect_accuracy = 0

    def shielddust(*args):
        if move.damage > 0 and move.effect_type != "no_effect":
            move.effect_type = "no_effect"

    def overgrow(*args):
        move.power *= 1.3 if move.type == "Grass" and user.battle_stats[0] <= user.hp // 3 else 1

    def blaze(*args):
        move.power *= 1.3 if move.type == "Fire" and user.battle_stats[0] <= user.hp // 3 else 1

    def torrent(*args):
        move.power *= 1.3 if move.type == "Water" and user.battle_stats[0] <= user.hp // 3 else 1

    def formation(*args):
        if move.type == "Rock":
            move.power *= 1.3

    def landlord(*args):
        if move.type == "Ground":
            move.power *= 1.3

    def technician(*args):
        move.power *= 1.5 if move.power <= 60 else 1

    def levitate(*args):
        user.volatile_status['Grounded'] = 0

    def flashfire(*args):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Fire" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Fire":
                user.volatile_status['FlashFire'] = 1

    def bulletproof(*args):
        move.abilitymodifier = 0 if 'i' in move.flags else move.abilitymodifier

    def serenegrace(*args):
        move.effect_accuracy *= 2

    def victorystar(*args):
        move.accuracy *= 1.1

    def compoundeyes(*args):
        move.accuracy *= 1.3

    def skilllink(*args):
        if move.multi[0] == 1:
            move.multi[1] = 5

    def pixelate(*args):
        if move.type == "Normal":
            move.type, move.power = "Fairy", move.power * 1.2

    def materialize(*args):
        if move.type == "Normal":
            move.type, move.power = "Steel", move.power * 1.2

    def refrigerate(*args):
        if move.type == "Normal":
            move.type, move.power = "Ice", move.power * 1.2

    def moxie(*args):
        if target.status == "Fainted" and battleground.reality:
            user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def soulheart(*args):
        if target.battle_stats[0] <= 0 and battleground.reality:  # fainted
            user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def grimneigh(*args):
        if target.status == "Fainted" and battleground.reality:
            user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def improvise(*args):
        if target.status == "Fainted" and battleground.reality:
            user.applied_modifier = [0, 0, 0, 0, 0, 1, 1, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def beastboost(*args):
        if target.status == "Fainted" and battleground.reality:
            best_stat = user.nominal_base_stats.index(max(user.nominal_base_stats[1:6]))
            user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 0]
            user.applied_modifier[best_stat] += 1
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def roughskin(*args):
        if battleground.reality:
            damage = max(1, target.hp // 8) if ('a' in move.flags and move.damage > 0) else 0
            target.battle_stats[0] -= damage
            if damage > 0:
                print(f"{user.ability} dealt {damage} damage to {target.name}.")

    def ironbarbs(*args):
        if battleground.reality:
            damage = max(1, target.hp // 8) if ('a' in move.flags and move.damage > 0) else 0
            target.battle_stats[0] -= damage
            if damage > 0:
                print(f"{user.ability} dealt {damage} damage to {target.name}.")

    def clearbody(*args):
        if "opponent_modifier" in move.effect_type and battleground.reality:
            new_modifier = [x * -1 if x < 0 else 0 for x in user.applied_modifier]
            print(f"{user.name}'s stats cannot be lowered.")
            user.modifier = list(map(operator.add, new_modifier, user.modifier))

    def weakarmor(*args):
        if 'a' in move.flags:
            user.applied_modifier = [0, 0, -1, 0, 0, 2, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def aftermath(*args):
        if user.status == "Fainted":
            damage = max(1, target.hp // 4) if ('a' in move.flags) else 0
            target.battle_stats[0] -= damage
            if damage > 0:
                print(f"{user.ability} dealt {damage} damage to {target.name}.")

    def static(*args):
        if 'a' in move.flags and target.status == "Normal":
            if "Electric" not in target.type:
                target.status = "Paralysis" if random.random() < 0.3 else "Normal"

    def defiant(*args):
        if move.effect_type == "opponent_modifier" and sum(user.applied_modifier) < 0:
            user.applied_modifier = [0, 2, 0, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def stamina(*args):
        if move.attack_type != "Status":
            user.applied_modifier = [0, 0, 1, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def sandspit(*args):
        if move.damage > 0 and battleground.weather_effect != 'Sandstorm':
            battleground.weather_effect = 'Sandstorm'
            battleground.artificial_weather = True

    def poisonpoint(*args):
        if 'a' in move.flags and target.status == "Normal":
            target.status = "Poison" if random.random() < 0.3 else "Normal"

    def justified(*args):
        if move.attack_type != "Status" and move.type == "Dark":
            user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def cursedbody(*args):
        if move.damage > 0:
            if random.random() < 0.3:
                with suppress(ValueError, AttributeError):
                    target.disabled_moves[move.name] = 5

    def speedboost(*args):
        user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        print(f"{user.ability} gains speed.")

    def shedskin(*args):
        if user.status not in ("Normal", "Fainted"):
            user.status = "Normal" if random.random() < 1 / 3 else user.status
            print(f"{user.ability} cured status condition.")

    def baddreams(*args):
        if target.status == "Sleep":
            target.battle_stats[0] -= max(1, target.hp // 8)

    def poisonousblow(*args):
        if user.battle_stats[0] <= user.hp // 3:
            target.status = status_effect_immunity_check(user, target, move, 'BadPoison')

    def arenatrap(*args):
        target.volatile_status['Trapped'] += 1 if target.volatile_status['Ungrounded'] == 0 else 0

    def battlearmor(*args):
        move.critRatio = 0

    def shellarmor(*args):
        move.critRatio = 0

    def chlorophyll(*args):
        # double speed when sunny
        user.battle_stats[5] *= 2 if battleground.weather_effect == 'Sunny' else 1

    def swiftswim(*args):
        # double speed when rain
        user.battle_stats[5] *= 2 if battleground.weather_effect == 'Rain' else 1

    def slushrush(*args):
        # double speed when hail
        user.battle_stats[5] *= 2 if battleground.weather_effect == 'Hail' else 1

    def raindish(*args):
        if battleground.weather_effect == 'Rain':
            user.battle_stats[0] += min(user.hp - user.battle_stats[0], user.hp // 16)
            print(f"{user.name} healed {min(user.hp - user.battle_stats[0], user.hp // 16)} HP.")

    def icebody(*args):
        if battleground.weather_effect == 'Hail':
            user.battle_stats[0] += min(user.hp - user.battle_stats[0], user.hp // 16)
            print(f"{user.name} healed {min(user.hp - user.battle_stats[0], user.hp // 16)} HP.")

    def earlybird(*args):
        if user.status == "Sleep":
            user.volatile_status['NonVolatile'] -= 1

    def effectspore(*args):
        if 'a' in move.flags and target.status == "Normal":
            if random.random() <= 0.3:
                temporary_effect = random.choice([Paralysis(1), Poison(1), Sleep(1)])
                target.status = status_effect_immunity_check(user, target, move, temporary_effect[0])
                target.volatile_status['NonVolatile'] = temporary_effect[1]

    def flamebody(*args):
        if 'a' in move.flags and target.status == "Normal":
            temporary_effect = Burn(0.3)
            target.status = status_effect_immunity_check(user, target, move, temporary_effect[0])
            target.volatile_status['NonVolatile'] = temporary_effect[1]

    def guts(*args):
        if user.status != "Normal":
            user.battle_stats[1] *= 1.5

    def hugepower(*args):
        user.battle_stats[1] *= 2

    def purepower(*args):
        user.battle_stats[1] *= 2

    def hustle(*args):
        if move.attack_type == "Physical":
            move.power *= 1.5
            move.accuracy *= 0.8

    def hypercutter(*args):
        if "opponent_modifier" in move.effect_type:
            if user.applied_modifier[1] < 0:
                new_modifier = [0, user.applied_modifier[1] * -1, 0, 0, 0, 0, 0, 0, 0]
                print(f"{user.name}'s attack cannot be lowered.")
                user.modifier = list(map(operator.add, new_modifier, user.modifier))

    def keeneye(*args):
        if "opponent_modifier" in move.effect_type:
            if user.applied_modifier[1] < 0:
                new_modifier = [0, 0, 0, 0, 0, 0, 0, user.applied_modifier[7] * -1, 0]
                print(f"{user.name}'s accuracy cannot be lowered.")
                user.modifier = list(map(operator.add, new_modifier, user.modifier))

    def insomnia(*args):
        if user.status == "Sleep":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def vitalspirit(*args):
        if user.status == "Sleep":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def sweetveil(*args):
        if user.status == "Sleep":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def limber(*args):
        if user.status == "Paralysis":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def immunity(*args):
        if user.status == "Poison" or user.status == "BadPoison":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def innerfocus(*args):
        user.volatile_status['Flinch'] = 0

    def owntempo(*args):
        user.volatile_status['Confused'] = 0

    def magmaarmor(*args):
        if user.status == "Freeze":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def waterveil(*args):
        if user.status == "Burn":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def lightningrod(*args):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Electric" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Electric":
                user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def stormdrain(*args):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Water" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Water":
                user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def sapsipper(*args):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Grass" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Grass":
                user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def voltabsorb(*args):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Electric" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Electric":
                user.battle_stats[0] += min(user.hp // 4, user.hp - user.battle_stats[0])

    def motordrive(*args):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Electric" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Electric":
                user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def watercompaction(*args):
        if move.attack_type != "Status" and move.type == "Water":
            user.applied_modifier = [0, 0, 2, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def waterabsorb(*args):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Water" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Water":
                user.battle_stats[0] += min(user.hp // 4, user.hp - user.battle_stats[0])

    def sandveil(*args):
        if battleground.weather_effect == 'Sandstorm':
            move.evasion *= 1.25

    def sandforce(*args):
        if battleground.weather_effect == 'Sandstorm':
            if move.type in ("Rock", "Steel", "Ground"):
                move.power *= 1.3

    def snowcloak(*args):
        if battleground.weather_effect == 'Hail':
            move.evasion *= 1.25

    def shadowtag(*args):
        target.volatile_status['Trapped'] += 1

    def soundproof(*args):
        move.abilitymodifier = 0 if 'f' in move.flags else move.abilitymodifier

    def sturdy(*args):
        if move.damage > user.battle_stats[0] and user.battle_stats[0] == user.hp:
            user.battle_stats[0] += (move.damage - user.battle_stats[0] + 1)

    def swarm(*args):
        move.power *= 1.5 if move.type == "Bug" and user.battle_stats[0] <= user.hp // 3 else 1

    def synchronize(*args):
        if user.status in ['Paralysis', 'Poison', 'BadPoison', 'Burn']and "target_non_volatile" in move.effect_type and target.status == "Normal":
            target.status = status_effect_immunity_check(user, target, move, user.status)
            target.volatile_status['NonVolatile'] = 1 if target.status == "BadPoison" else 0

    def trace(*args):
        if abilityphase == 1:
            if target.ability not in ['Disguise', 'Flower Gift', 'Gulp Missile', 'Hunger Switch', 'Ice Face', 'Illusion', 'Imposter', 'Neutralizing Gas', 'Receiver', 'RKS System',
                'Schooling', 'Stance Change', 'Trace', 'Zen Mode']:
                user.ability = target.ability
        elif abilityphase == 9:
            user.ability = user.default_ability

    def thickfat(*args):
        if "Ice" in move.type or "Fire" in move.type:
            target.battle_stats[1] *= 0.5
            target.battle_stats[3] *= 0.5

    def whitesmoke(*args):
        if "opponent_modifier" in move.effect_type:
            new_modifier = [x * -1 if x < 0 else 0 for x in user.applied_modifier]
            print(f"{user.name}'s stats cannot be lowered.")
            user.modifier = list(map(operator.add, new_modifier, user.modifier))

    def wonderguard(*args):
        if not move.super_effective:
            move.damage = 0

    def tintedlens(*args):
        if move.not_effective:
            move.damage *= 2

    def divinepower(*args):
        if not move.super_effective:
            move.damage = math.floor(move.damage * 1.5)

    def divineaegis(*args):
        if not move.super_effective:
            move.damage = math.floor(move.damage * 0.75)

    def solidrock(*args):
        if move.super_effective:
            move.damage *= 0.75

    def angerpoint(*args):
        if move.critical_hit:
            user.applied_modifier = [0, 6, 0, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def hydration(*args):
        if battleground.weather_effect == 'Rain':
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def reckless(*args):
        move.power *= 1.2 if move.recoil > 0 else 1

    def defeatist(*args):
        if user.battle_stats[0] <= user.hp // 2:
            user.battle_stats[1] *= 0.5
            user.battle_stats[3] *= 0.5

    def moody(*args):
        indexes = random.sample(range(1, 7), 2)
        new_modifier = [0] * 9
        new_modifier[indexes[0]] += 2
        new_modifier[indexes[1]] -= 1
        user.applied_modifier = new_modifier
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def multiscale(*args):
        if user.battle_stats[0] == user.hp:
            move.damage *= 0.5

    def regenerator(*args):
        user.battle_stats[0] += min(user.hp - user.battle_stats[0], user.hp // 3)

    def competitive(*args):
        if move.effect_type == "opponent_modifier" and sum(user.applied_modifier) < 0:
            user.applied_modifier = [0, 0, 0, 2, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def galewings(*args):
        move.priority += 1 if move.type == "Flying" else 0

    def sniper(*args):
        if move.critical_hit:
            move.damage = math.floor(move.damage * 1.5)

    def simple(*args):
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def unaware(*args):
        move.ignoreDef, move.ignoreEvasion = True, True

    def disguise(*args):
        if abilityphase == 1:
            if not user.transform:
                user.disguise = True
        elif abilityphase == 5 and battleground.reality:
            if move.attack_type != "Status" and move.damage > 0:
                if user.disguise:
                    move.damage = 0
                    user.disguise, user.transform = False, True
                    print("The disguise is busted.")

    def noguard(*args):
        move.accuracy = GUARANTEE_ACCURACY  # guarantee hit
        move.ignoreInvulnerability = True

    def icescales(*args):
        if move.attack_type == "Special":
            move.power //= 2

    def deadcalm(*args):
        move.ignoreWeather = True

    def berserk(*args):
        if user.battle_stats[0] < user.hp // 2 and move.damage > 0:
            user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def scrappy(*args):
        move.ignoreImmunity = ["Ghost"]

    def infiltrator(*args):
        move.ignoreBarrier = True

    def moldbreaker(*args):
        ignorable_ability_list = ['Battle Armor', 'Clear Body', 'Damp', 'Dry Skin', 'Flash Fire', 'Heatproof', 'Hyper Cutter', 'Immunity', 'Inner Focus',
                                  'Insomnia', 'Keen Eye', 'Leaf Guard', 'Levitate', 'Lightning Rod', 'Limber', 'Magma Armor', 'Marvel Scale', 'Motor Drive',
                                  'Oblivious', 'Own Tempo', 'Sand Veil', 'Shell Armor', 'Shield Dust', 'Simple', 'Snow Cloak', 'Solid Rock', 'Soundproof',
                                  'Sticky Hold', 'Storm Drain', 'Sturdy', 'Suction Cups', 'Tangled Feet', 'Thick Fat', 'Unaware', 'Vital Spirit', 'Volt Absorb',
                                  'Water Absorb', 'Water Veil', 'White Smoke', 'Wonder Guard', 'Big Pecks', 'Contrary', 'Friend Guard', 'Heavy Metal',
                                  'Light Metal', 'Magic Bounce', 'Multiscale', 'Sap Sipper', 'Telepathy', 'Wonder Skin', 'Aroma Veil', 'Bulletproof',
                                  'Flower Veil', 'Fur Coat', 'Overcoat', 'Sweet Veil', 'Dazzling', 'Disguise', 'Fluffy', 'Queenly Majesty', 'Water Bubble',
                                  'Mirror Armor', 'Punk Rock', 'Ice Scales', 'Ice Face', 'Pastel Veil']
        # custom abilities
        ignorable_ability_list += ['Divine Aegis']
        if target.ability in ignorable_ability_list:
            move.ignoreAbility = True

    def protean(*args):
        if abilityphase == 1:
            user.type = user.default_type
        elif abilityphase == 2:
            user.type = [move.type]
        elif abilityphase == 9:
            user.type = user.default_type

    def libero(*args):
        if abilityphase == 1:
            user.type = user.default_type
        elif abilityphase == 2:
            user.type = [move.type]
        elif abilityphase == 9:
            user.type = user.default_type

    def longreach(*args):
        with suppress(KeyError):
            move.flags.remove('a')

    def scorch(*args):
        if target.status == "Normal" and target.volatile_status['Grounded'] > 0:  # grounded
            effect = Burn(1)
            target.status = status_effect_immunity_check(user, target, move, effect[0])
            if target.status != "Normal":
                target.volatile_status['NonVolatile'] = effect[1]

    def steelworker(*args):
        if move.type == "Steel":
            move.power *= 1.5

    def analytic(*args):
        if not user_side.faster:
            move.damage = math.floor(move.damage * 1.3)

    def goredrinker(*args):
        if user.battle_stats[0] < user.hp // 2 and battleground.reality:
            user.battle_stats[0] += math.floor(min(user.hp - user.battle_stats[0], move.damage * 0.5))
            print(f"Goredrinker ability drains {math.floor(min(user.hp - user.battle_stats[0], move.damage * 0.5))} HP.")

    def screencleaner(*args):
        team_effect = ["Aurora Veil", "Reflect", "Light Screen"]
        for effect in team_effect:
            if user_side.in_battle_effects[effect] > 0:
                user_side.in_battle_effects[effect] = 0
            if target_side.in_battle_effects[effect] > 0:
                target_side.in_battle_effects[effect] = 0

    def queenlymajesty(*args):
        if move.priority > 0 and battleground.reality:
            print(f"{target.name} cannot use {move.name} due to the Majesty's pressure!")
            move.accuracy = 0

    def dazzling(*args):
        if move.priority > 0 and battleground.reality:
            print(f"{target.name} cannot use {move.name}!")
            move.accuracy = 0

    def toughclaws(*args):
        if 'a' in move.flags:
            move.power *= 1.3

    def fluffy(*args):
        if 'a' in move.flags:
            move.damage //= 2
        if "Fire" in move.type:
            move.damage *= 2

    def heatproof(*args):
        if "Fire" in move.type:
            move.damage //= 2

    def mummy(*args):
        if 'a' in move.flags:
            if target.ability not in ('Multitype', 'Zen Mode', 'Stance Change', 'Schooling', 'Battle Bond', 'Power Construct', 'Shields Down', 'RKS System', 'Disguise', 'Comatose', 'Mummy'):
                target.ability = "Mummy"

    def punkrock(*args):
        if abilityphase == 4:
            if 'f' in move.flags:
                move.damage *= 1.3
        elif abilityphase == 5:
            if 'f' in move.flags:
                move.damage //= 2

    def instrumental(*args):
        if abilityphase == 4:
            if 'f' in move.flags:
                move.damage *= 1.3
        elif abilityphase == 5:
            if 'f' in move.flags:
                move.damage *= 0.5
            if move.type == "Fire" or move.type == "Water":
                move.damage *= 1.5

    def illuminate(*args):
        # this ability does nothing in battle
        # added custom ability for illuminate (see in spy opponent)
        pass

    def pressure(*args):
        # this ability does nothing in battle
        # added custom ability for pressure (see in spy opponent)
        pass

    def magicguard(*args):
        # this ability effect is indicated in hp_decreasing_modifier
        pass

    def battlebond(*args):
        # exclusive to faker-greninja
        if move.name == "Water Shuriken":
            move.power *= 1.5

    def waterbubble(*args):
        if abilityphase == 4:
            if 'Water' in move.type:
                move.damage *= 2
        elif abilityphase == 5:
            if 'Fire' in move.type:
                move.damage *= 0.5
        elif abilityphase == 6:
            # immune to burn
            if user.status == 'Burn':
                user.status = 'Normal'

    def superluck(*args):
        user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 1]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def liquidooze(*args):
        if 'hp_draining' in move.effect_type:
            drain = move.special_effect if type(move.effect_type) is str else move.special_effect[move.effect_type.index('hp_draining')]
            print(f"{target.name} is affected by liquid ooze.")
            target.battle_stats[0] -= min(target.hp - target.battle_stats[0] + move.damage, math.floor((move.damage + min(target.battle_stats[0] + move.damage, 0)) * drain)) * 2

    def strongroots(*args):
        user.volatile_status['Ingrain'] = 1
        user.volatile_status['Trapped'] = 1

    list_of_abilities = {
        "Cloud Nine": ((1, 8), cloudnine),
        "Drizzle": (1, drizzle),
        "Drought": (1, drought),
        "Snow Warning": (1, snowwarning),
        "Sand Stream": (1, sandstream),
        "Download": (1, download),
        "Intimidate": (1, intimidate),
        "Anticipation": (1, anticipation),
        'Natural Cure': (1, naturalcure),
        'Stance Change': ((1, 2), stancechange),
        'Illusion': ((1, 2, 3, 5, 8, 9), illusion),
        'Prankster': (2, prankster),
        'Rock Head': (2, rockhead),
        'Marvel Scale': (3, marvelscale),
        'Adaptability': (2, adaptability),
        'Iron Fist': (2, ironfist),
        'Strong Jaw': (2, strongjaw),
        'Mega Launcher': (2, megalauncher),
        'Sheer Force': (2, sheerforce),
        'Shield Dust': (5, shielddust),
        'Overgrow': (2, overgrow),
        'Blaze': (2, blaze),
        'Torrent': (2, torrent),
        'Formation': (2, formation, "Custom"),
        'Landlord': (2, landlord, "Custom"),
        'Technician': (2, technician),
        'Levitate': (1, levitate),
        'Flash Fire': ((3, 5), flashfire),
        'Bulletproof': (3, bulletproof),
        'Serene Grace': (2, serenegrace),
        'Victory Star': (2, victorystar),
        'Compound Eyes': (2, compoundeyes),
        'Skill Link': (2, skilllink),
        'Pixelate': (2, pixelate),
        'Materialize': (2, materialize, "Custom"),
        'Refrigerate': (2, refrigerate),
        'Moxie': (6, moxie),
        'Soul-Heart': (8, soulheart),
        'Grim Neigh': (6, grimneigh),
        'Improvise': (6, improvise, "Custom"),
        'Beast Boost': (6, beastboost),
        'Rough Skin': (7, roughskin),
        'Iron Barbs': (7, ironbarbs),
        'Clear Body': (7, clearbody),
        'Weak Armor': (7, weakarmor),
        'Aftermath': (7, aftermath),
        'Static': (7, static),
        'Defiant': (7, defiant),
        'Stamina': (7, stamina),
        'Sand Spit': (7, sandspit),
        'Poison Point': (7, poisonpoint),
        'Justified': (7, justified),
        'Cursed Body': (7, cursedbody),
        'Speed Boost': (8, speedboost),
        'Shed Skin': (8, shedskin),
        'Bad Dreams': (8, baddreams),
        'Poisonous Blow': (8, poisonousblow, "Custom"),
        'Arena Trap': (1, arenatrap),
        'Battle Armor': (3, battlearmor),
        'Shell Armor': (3, shellarmor),
        'Chlorophyll': (2, chlorophyll),
        'Swift Swim': (2, swiftswim),
        'Slush Rush': (2, slushrush),
        'Rain Dish': (8, raindish),
        'Ice Body': (8, icebody),
        'Early Bird': (8, earlybird),
        'Effect Spore': (7, effectspore),
        'Flame Body': (7, flamebody),
        'Guts': (2, guts),
        'Huge Power': (2, hugepower),
        'Pure Power': (2, purepower),
        'Hustle': (2, hustle),
        'Hyper Cutter': (7, hypercutter),
        'Keen Eye': (7, keeneye),
        'Insomnia': ((6, 7), insomnia),
        'Vital Spirit': ((6, 7), vitalspirit),
        'Sweet Veil': ((6, 7), sweetveil),
        'Limber': ((6, 7), limber),
        'Immunity': ((1, 6, 7), immunity),
        'Inner Focus': (7, innerfocus),
        'Own Tempo': (7, owntempo),
        'Magma Armor': (7, magmaarmor),
        'Water Veil': (7, waterveil),
        'Lightning Rod': ((3, 5), lightningrod),
        'Storm Drain': ((3, 5), stormdrain),
        'Sap Sipper': ((3, 5), sapsipper),
        'Volt Absorb': ((3, 5), voltabsorb),
        'Motor Drive': ((3, 5), motordrive),
        'Water Compaction': (5, watercompaction),
        'Water Absorb': ((3, 5), waterabsorb),
        'Sand Veil': (3, sandveil),
        'Sand Force': (2, sandforce),
        'Snow Cloak': (3, snowcloak),
        'Shadow Tag': (1, shadowtag),
        'Soundproof': (3, soundproof),
        'Sturdy': (5, sturdy),
        'Swarm': (2, swarm),
        'Synchronize': (7, synchronize),
        'Trace': ((1, 9), trace),
        'Thick Fat': (3, thickfat),
        'White Smoke': (7, whitesmoke),
        'Wonder Guard': (5, wonderguard),
        'Tinted Lens': (4, tintedlens),
        'Divine Power': (4, divinepower, "Custom"),
        'Divine Aegis': (5, divineaegis, "Custom"),
        'Solid Rock': (5, solidrock),
        'Anger Point': (5, angerpoint),
        'Hydration': (8, hydration),
        'Reckless': (2, reckless),
        'Defeatist': (2, defeatist),
        'Moody': (8, moody),
        'Multiscale': (5, multiscale),
        'Regenerator': (9, regenerator),
        'Competitive': (7, competitive),
        'Gale Wings': (2, galewings),
        'Sniper': (4, sniper),
        'Simple': ((1, 6, 7), simple),
        'Unaware': (2, unaware),
        'Disguise': ((1, 5), disguise),
        'No Guard': (2, noguard),
        'Ice Scales': (3, icescales),
        'Dead Calm': (2, deadcalm, "Custom"),
        'Berserk': (7, berserk),
        'Scrappy': (2, scrappy),
        'Infiltrator': (2, infiltrator),
        'Mold Breaker': (2, moldbreaker),
        'Protean': ((1, 2, 9), protean),
        'Libero': ((1, 2, 9), libero),
        'Long Reach': (2, longreach),
        'Scorch': (8, scorch, "Custom"),
        'Steelworker': (2, steelworker),
        'Analytic': (4, analytic),
        'Goredrinker': (4, goredrinker, "Custom"),
        'Screen Cleaner': (1, screencleaner),
        'Queenly Majesty': (3, queenlymajesty),
        'Dazzling': (3, dazzling),
        'Tough Claws': (2, toughclaws),
        'Fluffy': (5, fluffy),
        'Heatproof': (5, heatproof),
        'Mummy': (7, mummy),
        'Punk Rock': ((4, 5), punkrock),
        'Instrumental': ((4, 5), instrumental, "Custom"),
        'Illuminate': (1, illuminate),
        'Pressure': (1, pressure),
        'Magic Guard': (8, magicguard),
        'Battle Bond': (2, battlebond),
        'Water Bubble': ((4, 5, 6), waterbubble),
        'Super Luck': (1, superluck),
        'Liquid Ooze': (7, liquidooze),
        'Strong Roots': (1, strongroots, "Custom"),
    }

    try:
        ignoreAbility = True if move.ignoreAbility else False
    except (KeyError, AttributeError):
        ignoreAbility = False
    if not ignoreAbility:
        with suppress(KeyError, AttributeError):
            for ability in user.ability:
                vartype = type(list_of_abilities[ability][0])
                if vartype is tuple:
                    if abilityphase in list_of_abilities[ability][0]:
                        list_of_abilities[ability][1](user_side, target_side, user, target, battleground, move, abilityphase)
                elif vartype is int:
                    if abilityphase == list_of_abilities[ability][0]:
                        list_of_abilities[ability][1](user_side, target_side, user, target, battleground, move, abilityphase)

    if verbose:
        print(f"\n{CBOLD}Total Number of Abilities: {len(list_of_abilities)}\nCustom: {sum([1 for abilities, values in list_of_abilities.items() if len(values) == 3])}{CEND}")
        for key, value in list_of_abilities.items():
            with suppress(IndexError):
                if value[2] == "Custom":
                    print(f"{CYELLOW2}{key}{CEND}")
        print(f"\n\n{CBOLD}Ability Usage: {CEND}\n")
        ability_usage = True  # debug only
        if ability_usage:
            ability_list = dict.fromkeys([ability for ability in list_of_abilities], 0)
            ability_list.update({'Surge Surfer': 0})
            for pokemon in list_of_pokemon:
                for ability in list_of_pokemon[pokemon].ability:
                    ability_list[ability] += 1
            ability_list = dict(sorted(ability_list.items(), key=lambda item: item[1]))
            for ability, usage in ability_list.items():
                print(f"{ability}: {usage}")
