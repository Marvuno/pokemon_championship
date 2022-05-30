from weather import *
from moves import *
from pokemon import *
from type_chart import *
from type_immunity import *
from contextlib import suppress
from text_color import *
import math
import operator


def UseAbility(user_side, target_side, user, target, battleground, move="", abilityphase=1, verbose=False):
    def cloudnine(user_side, target_side, user, target, battleground, move, abilityphase):
        battleground.weather_effect = Clear()

    def drizzle(user_side, target_side, user, target, battleground, move, abilityphase):
        battleground.weather_effect = Rain()

    def drought(user_side, target_side, user, target, battleground, move, abilityphase):
        battleground.weather_effect = Sunny()

    def snowwarning(user_side, target_side, user, target, battleground, move, abilityphase):
        battleground.weather_effect = Hail()

    def sandstream(user_side, target_side, user, target, battleground, move, abilityphase):
        battleground.weather_effect = Sandstorm()

    def download(user_side, target_side, user, target, battleground, move, abilityphase):
        user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0] if target.battle_stats[2] < target.battle_stats[4] else [0, 0, 0, 1, 0, 0, 0, 0, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def intimidate(user_side, target_side, user, target, battleground, move, abilityphase):
        if target.ability != "Clear Body" and target.ability != "Hyper Cutter":
            target.applied_modifier = [0, -1, 0, 0, 0, 0, 0, 0, 0]
            target.modifier = list(map(operator.add, target.applied_modifier, target.modifier))

    def anticipation(user_side, target_side, user, target, battleground, move, abilityphase):
        for move in target.moveset:
            move = list_of_moves[move]
            type_effectiveness = math.prod([typeChart[move.type][user.type[x]] for x in range(len(user.type))])
            if type_effectiveness >= 2 and move.attack_type != "Status":
                print(f"{user.name} shuddered.")
                break

    def naturalcure(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status != "Normal":
            user.status, user.volatile_status["NonVolatile"] = "Normal", 0

    # aegislash only
    def stancechange(user_side, target_side, user, target, battleground, move, abilityphase):
        # when switched in
        if abilityphase == 1:
            if user.name == "Aegislash (Blade Forme)":
                user.name = "Aegislash (Shield Forme)"
                user.nominal_base_stats[2], user.nominal_base_stats[1] = user.nominal_base_stats[1], user.nominal_base_stats[2]
                user.nominal_base_stats[4], user.nominal_base_stats[3] = user.nominal_base_stats[3], user.nominal_base_stats[4]
        # when using move
        elif abilityphase == 2:
            if move.attack_type != "Status":
                if user.charging[2] == 0:
                    # to prove it is shield form (spdef > spa)
                    if user.nominal_base_stats[4] > user.nominal_base_stats[3]:
                        # switched to blade form
                        print(f"{user.name} switches to Blade Forme.")
                        user.name = "Aegislash (Blade Forme)"
                        user.nominal_base_stats[1], user.nominal_base_stats[2] = user.nominal_base_stats[2], user.nominal_base_stats[1]
                        user.nominal_base_stats[3], user.nominal_base_stats[4] = user.nominal_base_stats[4], user.nominal_base_stats[3]
                        for x in range(1, 5):
                            user.battle_stats[x] = math.floor(0.01 * 2 * user.nominal_base_stats[x] * modifierChart[x][user.modifier[x]] * 100 + 5)
            elif move.name == "King's Shield":
                if user.nominal_base_stats[3] > user.nominal_base_stats[4]:
                    # switched to shield form
                    print(f"{user.name} switches to Shield Forme.")
                    user.name = "Aegislash (Shield Forme)"
                    user.nominal_base_stats[2], user.nominal_base_stats[1] = user.nominal_base_stats[1], user.nominal_base_stats[2]
                    user.nominal_base_stats[4], user.nominal_base_stats[3] = user.nominal_base_stats[3], user.nominal_base_stats[4]
                    for x in range(1, 5):
                        user.battle_stats[x] = math.floor(0.01 * 2 * user.nominal_base_stats[x] * modifierChart[x][user.modifier[x]] * 100 + 5)

    # zoroark only
    def illusion(user_side, target_side, user, target, battleground, move, abilityphase):
        # switching in
        if abilityphase == 1:
            illusion_name = user.name
            for pokemon in user_side.team:
                if pokemon.status != "Fainted" and pokemon.name != "Zoroark":  # use id when finalizing pokemon list
                    illusion_name = pokemon.name
                    break
            user.name = illusion_name
        elif abilityphase == 5:
            if move.damage > 0:
                user.name = "Zoroark"
                print(f"{user.name} is in disguise!")
        # switched out
        elif abilityphase == 9:
            if user.status != "Fainted":
                user.name = "Zoroark"

    def prankster(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.attack_type == "Status" and "Dark" not in target.type:
            move.priority += 1

    def rockhead(user_side, target_side, user, target, battleground, move, abilityphase):
        move.recoil = 0

    def marvelscale(user_side, target_side, user, target, battleground, move, abilityphase):
        user.battle_stats[2] *= 1.5 if user.status != "Normal" else 1

    def adaptability(user_side, target_side, user, target, battleground, move, abilityphase):
        move.abilitymodifier = math.floor(1 / 1.5 * 2) if move.type in user.type else 1

    def ironfist(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.2 if 'e' in move.flags else 1

    def strongjaw(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.5 if 'd' in move.flags else 1

    def megalauncher(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.5 if 'h' in move.flags else 1

    def sheerforce(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.effect_type != "no_effect":
            if not (move.effect_type == "self_modifier" and sum(move.special_effect) < 0):
                move.power *= 1.3
                move.effect_accuracy = 0

    def shielddust(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.damage > 0 and move.effect_type != "no_effect":
            move.effect_type = "no_effect"

    def overgrow(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.3 if move.type == "Grass" and user.battle_stats[0] <= user.hp // 3 else 1

    def blaze(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.3 if move.type == "Fire" and user.battle_stats[0] <= user.hp // 3 else 1

    def torrent(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.3 if move.type == "Water" and user.battle_stats[0] <= user.hp // 3 else 1

    def formation(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.type == "Rock":
            move.power *= 1.3

    def technician(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.5 if move.power <= 60 else 1

    def levitate(user_side, target_side, user, target, battleground, move, abilityphase):
        user.volatile_status['Ungrounded'] = 1

    def flashfire(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Fire" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Fire":
                user.volatile_status['Flash Fire'] = 1

    def bulletproof(user_side, target_side, user, target, battleground, move, abilityphase):
        move.abilitymodifier = 0 if 'i' in move.flags else move.abilitymodifier

    def serenegrace(user_side, target_side, user, target, battleground, move, abilityphase):
        move.effect_accuracy *= 2

    def victorystar(user_side, target_side, user, target, battleground, move, abilityphase):
        move.accuracy *= 1.1

    def compoundeyes(user_side, target_side, user, target, battleground, move, abilityphase):
        move.accuracy *= 1.3

    def skilllink(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.multi[0]:
            move.multi[1] = 5

    def pixelate(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.type == "Normal":
            move.type, move.power = "Fairy", move.power * 1.2

    def refrigerate(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.type == "Normal":
            move.type, move.power = "Ice", move.power * 1.2

    def moxie(user_side, target_side, user, target, battleground, move, abilityphase):
        if target.status == "Fainted":
            user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def grimneigh(user_side, target_side, user, target, battleground, move, abilityphase):
        if target.status == "Fainted":
            user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def improvise(user_side, target_side, user, target, battleground, move, abilityphase):
        if target.status == "Fainted":
            user.applied_modifier = [0, 0, 0, 0, 0, 1, 1, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def beastboost(user_side, target_side, user, target, battleground, move, abilityphase):
        if target.status == "Fainted":
            best_stat = user.nominal_base_stats.index(max(user.nominal_base_stats[1:6]))
            user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 0]
            user.applied_modifier[best_stat] += 1
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def roughskin(user_side, target_side, user, target, battleground, move, abilityphase):
        damage = max(1, target.hp // 8) if ('a' in move.flags) else 0
        target.battle_stats[0] -= damage
        if damage > 0:
            print(f"{user.ability} dealt {damage} damage to {target.name}.")

    def clearbody(user_side, target_side, user, target, battleground, move, abilityphase):
        if "opponent_modifier" in move.effect_type:
            new_modifier = [x * -1 if x < 0 else 0 for x in user.applied_modifier]
            print(f"{user.name}'s stats cannot be lowered.")
            user.modifier = list(map(operator.add, new_modifier, user.modifier))

    def weakarmor(user_side, target_side, user, target, battleground, move, abilityphase):
        if 'a' in move.flags:
            user.applied_modifier = [0, 0, -1, 0, 0, 2, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def aftermath(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Fainted":
            damage = max(1, target.hp // 4) if ('a' in move.flags) else 0
            target.battle_stats[0] -= damage
            if damage > 0:
                print(f"{user.ability} dealt {damage} damage to {target.name}.")

    def static(user_side, target_side, user, target, battleground, move, abilityphase):
        if 'a' in move.flags and target.status == "Normal":
            if "Electric" not in target.type:
                target.status = "Paralysis" if random.random() < 0.3 else "Normal"

    def defiant(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.effect_type == "opponent_modifier" and sum(user.applied_modifier) < 0:
            user.applied_modifier = [0, 2, 0, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def stamina(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.attack_type != "Status":
            user.applied_modifier = [0, 0, 1, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def sandspit(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.damage > 0 and battleground.weather_effect.id != 3:
            battleground.weather_effect = Sandstorm()
            battleground.artificial_weather = True

    def poisonpoint(user_side, target_side, user, target, battleground, move, abilityphase):
        if 'a' in move.flags and target.status == "Normal":
            target.status = "Poison" if random.random() < 0.3 else "Normal"

    def justified(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.attack_type != "Status" and move.type == "Dark":
            user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def cursedbody(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.damage > 0:
            if random.random() < 0.3:
                with suppress(ValueError, AttributeError):
                    target.disabled_moves[move.name] = 5

    def speedboost(user_side, target_side, user, target, battleground, move, abilityphase):
        user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        print(f"{user.ability} gains speed.")

    def shedskin(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status not in ("Normal", "Fainted"):
            user.status = "Normal" if random.random() < 1 / 3 else user.status
            print(f"{user.ability} cured status condition.")

    def baddreams(user_side, target_side, user, target, battleground, move, abilityphase):
        if target.status == "Sleep":
            target.battle_stats[0] -= max(1, target.hp // 8)

    def poisonousblow(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.battle_stats[0] <= user.hp // 3:
            target.status = status_effect_immunity_check(user, target, move, 'BadPoison')

    def arenatrap(user_side, target_side, user, target, battleground, move, abilityphase):
        target.volatile_status['Trapped'] += 1 if target.volatile_status['Ungrounded'] == 0 else 0

    def battlearmor(user_side, target_side, user, target, battleground, move, abilityphase):
        move.critRatio = 0

    def shellarmor(user_side, target_side, user, target, battleground, move, abilityphase):
        move.critRatio = 0

    def chlorophyll(user_side, target_side, user, target, battleground, move, abilityphase):
        # double speed when sunny
        user.battle_stats[5] *= 2 if battleground.weather_effect.id == 1 else 1

    def swiftswim(user_side, target_side, user, target, battleground, move, abilityphase):
        # double speed when rain
        user.battle_stats[5] *= 2 if battleground.weather_effect.id == 2 else 1

    def slushrush(user_side, target_side, user, target, battleground, move, abilityphase):
        # double speed when hail
        user.battle_stats[5] *= 2 if battleground.weather_effect.id == 4 else 1

    def raindish(user_side, target_side, user, target, battleground, move, abilityphase):
        if battleground.weather_effect.id == 2:
            user.battle_stats[0] += min(user.hp - user.battle_stats[0], user.hp // 16)
            print(f"{user.name} healed {min(user.hp - user.battle_stats[0], user.hp // 16)} HP.")

    def icebody(user_side, target_side, user, target, battleground, move, abilityphase):
        if battleground.weather_effect.id == 4:
            user.battle_stats[0] += min(user.hp - user.battle_stats[0], user.hp // 16)
            print(f"{user.name} healed {min(user.hp - user.battle_stats[0], user.hp // 16)} HP.")

    def earlybird(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Sleep":
            user.volatile_status['NonVolatile'] -= 1

    def effectspore(user_side, target_side, user, target, battleground, move, abilityphase):
        if 'a' in move.flags and target.status == "Normal":
            if random.random() <= 0.3:
                temporary_effect = random.choice([Paralysis(1), Poison(1), Sleep(1)])
                target.status = status_effect_immunity_check(user, target, move, temporary_effect[0])
                target.volatile_status['NonVolatile'] = temporary_effect[1]

    def flamebody(user_side, target_side, user, target, battleground, move, abilityphase):
        if 'a' in move.flags and target.status == "Normal":
            temporary_effect = Burn(0.3)
            target.status = status_effect_immunity_check(user, target, move, temporary_effect[0])
            target.volatile_status['NonVolatile'] = temporary_effect[1]

    def guts(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status != "Normal":
            user.battle_stats[1] *= 1.5

    def hugepower(user_side, target_side, user, target, battleground, move, abilityphase):
        user.battle_stats[1] *= 2

    def purepower(user_side, target_side, user, target, battleground, move, abilityphase):
        user.battle_stats[1] *= 2

    def hustle(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.attack_type == "Physical":
            move.power *= 1.5
            move.accuracy *= 0.8

    def hypercutter(user_side, target_side, user, target, battleground, move, abilityphase):
        if "opponent_modifier" in move.effect_type:
            if user.applied_modifier[1] < 0:
                new_modifier = [0, user.applied_modifier[1] * -1, 0, 0, 0, 0, 0, 0, 0]
                print(f"{user.name}'s attack cannot be lowered.")
                user.modifier = list(map(operator.add, new_modifier, user.modifier))

    def insomnia(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Sleep":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def vitalspirit(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Sleep":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def sweetveil(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Sleep":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def limber(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Paralysis":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def immunity(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Poison" or user.status == "BadPoison":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def innerfocus(user_side, target_side, user, target, battleground, move, abilityphase):
        user.volatile_status['Flinched'] = 0

    def owntempo(user_side, target_side, user, target, battleground, move, abilityphase):
        user.volatile_status['Confused'] = 0

    def magmaarmor(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Freeze":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def waterveil(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status == "Burn":
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def lightningrod(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Electric" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Electric":
                user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def stormdrain(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Water" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Water":
                user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def sapsipper(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Grass" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Grass":
                user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def voltabsorb(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Electric" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Electric":
                user.battle_stats[0] += min(user.hp // 4, user.hp - user.battle_stats[0])

    def motordrive(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Electric" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Electric":
                user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
                user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def waterabsorb(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 3:
            move.abilitymodifier = 0 if move.type == "Water" else move.abilitymodifier
        elif abilityphase == 5:
            if move.attack_type != "Status" and move.type == "Water":
                user.battle_stats[0] += min(user.hp // 4, user.hp - user.battle_stats[0])

    def sandveil(user_side, target_side, user, target, battleground, move, abilityphase):
        if battleground.weather_effect.id == 3:
            move.evasion *= 1.25

    def snowcloak(user_side, target_side, user, target, battleground, move, abilityphase):
        if battleground.weather_effect.id == 4:
            move.evasion *= 1.25

    def shadowtag(user_side, target_side, user, target, battleground, move, abilityphase):
        target.volatile_status['Trapped'] += 1

    def soundproof(user_side, target_side, user, target, battleground, move, abilityphase):
        move.abilitymodifier = 0 if 'f' in move.flags else move.abilitymodifier

    def sturdy(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.damage > user.battle_stats[0] and user.battle_stats[0] == user.hp:
            user.battle_stats[0] += (move.damage - user.battle_stats[0] + 1)

    def swarm(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.5 if move.type == "Bug" and user.battle_stats[0] <= user.hp // 3 else 1

    def synchronize(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.status in ['Paralysis', 'Poison', 'BadPoison', 'Burn']and "target_non_volatile" in move.effect_type and target.status == "Normal":
            target.status = status_effect_immunity_check(user, target, move, user.status)
            target.volatile_status['NonVolatile'] = 1 if target.status == "BadPoison" else 0

    def trace(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 1:
            if target.ability not in ['Disguise', 'Flower Gift', 'Gulp Missile', 'Hunger Switch', 'Ice Face', 'Illusion', 'Imposter', 'Neutralizing Gas', 'Receiver', 'RKS System',
                'Schooling', 'Stance Change', 'Trace', 'Zen Mode']:
                user.ability = target.ability
        elif abilityphase == 9:
            user.ability = "Trace"

    def thickfat(user_side, target_side, user, target, battleground, move, abilityphase):
        if "Ice" in move.type or "Fire" in move.type:
            target.battle_stats[1] *= 0.5
            target.battle_stats[3] *= 0.5

    def whitesmoke(user_side, target_side, user, target, battleground, move, abilityphase):
        if "opponent_modifier" in move.effect_type:
            new_modifier = [x * -1 if x < 0 else 0 for x in user.applied_modifier]
            print(f"{user.name}'s stats cannot be lowered.")
            user.modifier = list(map(operator.add, new_modifier, user.modifier))

    def wonderguard(user_side, target_side, user, target, battleground, move, abilityphase):
        if not move.super_effective:
            move.damage = 0

    def solidrock(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.super_effective:
            move.damage *= 0.75

    def angerpoint(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.critical_hit:
            user.applied_modifier = [0, 6, 0, 0, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def hydration(user_side, target_side, user, target, battleground, move, abilityphase):
        if battleground.weather_effect.id == 2:
            user.status, user.volatile_status['NonVolatile'] = "Normal", 0

    def reckless(user_side, target_side, user, target, battleground, move, abilityphase):
        move.power *= 1.2 if move.recoil > 0 else 1

    def defeatist(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.battle_stats[0] <= user.hp // 2:
            user.battle_stats[1] *= 0.5
            user.battle_stats[3] *= 0.5

    def moody(user_side, target_side, user, target, battleground, move, abilityphase):
        buff_index, nerf_index = random.randint(1, 7), random.randint(1, 7)
        new_modifier = [0] * 9
        new_modifier[buff_index] += 2
        new_modifier[nerf_index] -= 1
        user.applied_modifier = new_modifier
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def multiscale(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.battle_stats[0] == user.hp:
            move.damage *= 0.5

    def regenerator(user_side, target_side, user, target, battleground, move, abilityphase):
        user.battle_stats[0] += min(user.hp - user.battle_stats[0], user.hp // 3)

    def competitive(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.effect_type == "opponent_modifier" and sum(user.applied_modifier) < 0:
            user.applied_modifier = [0, 0, 0, 2, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def galewings(user_side, target_side, user, target, battleground, move, abilityphase):
        move.priority += 1 if move.type == "Flying" else 0

    def sniper(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.critical_hit:
            move.damage = math.floor(move.damage * 1.5)

    def simple(user_side, target_side, user, target, battleground, move, abilityphase):
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def unaware(user_side, target_side, user, target, battleground, move, abilityphase):
        move.ignoreDef, move.ignoreEvasion = True, True

    def disguise(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 1:
            if not user.transform:
                user.disguise = True
        elif abilityphase == 5:
            if move.attack_type != "Status":
                if user.disguise:
                    move.damage = 0
                    user.disguise, user.transform = False, True
                    print("The disguise is busted.")

    def noguard(user_side, target_side, user, target, battleground, move, abilityphase):
        move.accuracy = GUARANTEE_ACCURACY  # guarantee hit
        move.ignoreInvulnerability = True

    def icescales(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.attack_type == "Special":
            move.power //= 2

    def deadcalm(user_side, target_side, user, target, battleground, move, abilityphase):
        move.ignoreWeather = True

    def berserk(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.battle_stats[0] < user.hp // 2 and move.damage > 0:
            user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))

    def scrappy(user_side, target_side, user, target, battleground, move, abilityphase):
        move.ignoreImmunity = ["Ghost"]

    def infiltrator(user_side, target_side, user, target, battleground, move, abilityphase):
        move.ignoreBarrier = True

    def moldbreaker(user_side, target_side, user, target, battleground, move, abilityphase):
        ignorable_ability_list = ['Battle Armor', 'Clear Body', 'Damp', 'Dry Skin', 'Flash Fire', 'Heatproof', 'Hyper Cutter', 'Immunity', 'Inner Focus',
                                  'Insomnia', 'Keen Eye', 'Leaf Guard', 'Levitate', 'Lightning Rod', 'Limber', 'Magma Armor', 'Marvel Scale', 'Motor Drive',
                                  'Oblivious', 'Own Tempo', 'Sand Veil', 'Shell Armor', 'Shield Dust', 'Simple', 'Snow Cloak', 'Solid Rock', 'Soundproof',
                                  'Sticky Hold', 'Storm Drain', 'Sturdy', 'Suction Cups', 'Tangled Feet', 'Thick Fat', 'Unaware', 'Vital Spirit', 'Volt Absorb',
                                  'Water Absorb', 'Water Veil', 'White Smoke', 'Wonder Guard', 'Big Pecks', 'Contrary', 'Friend Guard', 'Heavy Metal',
                                  'Light Metal', 'Magic Bounce', 'Multiscale', 'Sap Sipper', 'Telepathy', 'Wonder Skin', 'Aroma Veil', 'Bulletproof',
                                  'Flower Veil', 'Fur Coat', 'Overcoat', 'Sweet Veil', 'Dazzling', 'Disguise', 'Fluffy', 'Queenly Majesty', 'Water Bubble',
                                  'Mirror Armor', 'Punk Rock', 'Ice Scales', 'Ice Face', 'Pastel Veil']
        if target.ability in ignorable_ability_list:
            move.ignoreAbility = True

    def protean(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 1:
            user.type = list_of_pokemon[user.name].type
        elif abilityphase == 2:
            user.type = [move.type]
        elif abilityphase == 9:
            user.type = list_of_pokemon[user.name].type

    def libero(user_side, target_side, user, target, battleground, move, abilityphase):
        if abilityphase == 1:
            user.type = list_of_pokemon[user.name].type
        elif abilityphase == 2:
            user.type = [move.type]
        elif abilityphase == 9:
            user.type = list_of_pokemon[user.name].type

    def longreach(user_side, target_side, user, target, battleground, move, abilityphase):
        with suppress(KeyError):
            move.flags.remove('a')

    def scorch(user_side, target_side, user, target, battleground, move, abilityphase):
        if target.status == "Normal" and target.volatile_status['Grounded'] > 0:  # grounded
            effect = Burn(1)
            target.status = status_effect_immunity_check(user, target, move, effect[0])
            if target.status != "Normal":
                target.volatile_status['NonVolatile'] = effect[1]

    def steelworker(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.type == "Steel":
            move.power *= 1.5

    def analytic(user_side, target_side, user, target, battleground, move, abilityphase):
        if not user_side.faster:
            move.damage = math.floor(move.damage * 1.3)

    def goredrinker(user_side, target_side, user, target, battleground, move, abilityphase):
        if user.battle_stats[0] < user.hp // 2:
            user.battle_stats[0] += math.floor(min(user.hp - user.battle_stats[0], move.damage * 0.5))
            print(f"Goredrinker ability drains {math.floor(min(user.hp - user.battle_stats[0], move.damage * 0.5))} HP.")

    def screencleaner(user_side, target_side, user, target, battleground, move, abilityphase):
        team_effect = ["Aurora Veil", "Reflect", "Light Screen"]
        for effect in team_effect:
            if user_side.in_battle_effects[effect] > 0:
                user_side.in_battle_effects[effect] = 0
            if target_side.in_battle_effects[effect] > 0:
                target_side.in_battle_effects[effect] = 0

    def queenlymajesty(user_side, target_side, user, target, battleground, move, abilityphase):
        if move.priority > 0:
            print(f"{target.name} cannot use {move.name} due to the Majesty's pressure!")
            move.accuracy = 0

    def toughclaws(user_side, target_side, user, target, battleground, move, abilityphase):
        if 'a' in move.flags:
            move.power *= 1.3

    def fluffy(user_side, target_side, user, target, battleground, move, abilityphase):
        if 'a' in move.flags:
            move.damage //= 2
        if "Fire" in move.type:
            move.damage *= 2

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
        'Illusion': ((1, 5, 9), illusion),
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
        'Technician': (2, technician),
        'Levitate': (1, levitate),
        'Flash Fire': ((3, 5), flashfire),
        'Bulletproof': (3, bulletproof),
        'Serene Grace': (2, serenegrace),
        'Victory Star': (2, victorystar),
        'Compound Eyes': (2, compoundeyes),
        'Skill Link': (2, skilllink),
        'Pixelate': (2, pixelate),
        'Refrigerate': (2, refrigerate),
        'Moxie': (6, moxie),
        'Grim Neigh': (6, grimneigh),
        'Improvise': (6, improvise, "Custom"),
        'Beast Boost': (6, beastboost),
        'Rough Skin': (7, roughskin),
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
        'Water Absorb': ((3, 5), waterabsorb),
        'Sand Veil': (3, sandveil),
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
        'Tough Claws': (2, toughclaws),
        'Fluffy': (5, fluffy),
    }

    try:
        ignoreAbility = True if move.ignoreAbility else False
    except (KeyError, AttributeError):
        ignoreAbility = False
    if not ignoreAbility:
        with suppress(KeyError, AttributeError):
            vartype = type(list_of_abilities[user.ability][0])
            if vartype is tuple:
                if abilityphase in list_of_abilities[user.ability][0]:
                    list_of_abilities[user.ability][1](user_side, target_side, user, target, battleground, move, abilityphase)
            elif vartype is int:
                if abilityphase == list_of_abilities[user.ability][0]:
                    list_of_abilities[user.ability][1](user_side, target_side, user, target, battleground, move, abilityphase)

    if verbose:
        print(f"\n{CBOLD}Total Number of Abilities: {len(list_of_abilities)}\nCustom: {CEND}")
        for key, value in list_of_abilities.items():
            with suppress(IndexError):
                if value[2] == "Custom":
                    print(f"{CYELLOW2}{key}{CEND}")
