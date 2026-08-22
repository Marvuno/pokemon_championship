import random
import math
import operator
import inspect
from contextlib import suppress

from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Data.moves import *
from Scripts.Battle.type_immunity import *
from Scripts.Battle.context import Side, Turn
from Scripts.Battle.weather import weather_desc
from Scripts.Battle import terrain
from Scripts.Battle.constants import GUARANTEE_ACCURACY
from Scripts.Data.competitors import ability_text
from Scripts.Art import narrator


#: Serene Grace only sharpens a secondary effect that was *worse* than a
#: coin flip. At or above this, the move is already reliable and is left
#: alone.
SERENE_GRACE_CEILING = 0.5

#: Sparking Cascade's per-turn paralysis roll, and the types the current
#: does not reach: Flying is not standing in it, Ground earths it, Electric
#: is made of it.
SPARKING_CASCADE_CHANCE = 0.1
SPARKING_CASCADE_IMMUNE = frozenset(("Flying", "Ground", "Electric"))


def notice(battleground, side=None):
    """Announce that a character ability just fired, and what it does.

    It used to say only `Character Ability: Procrastination`, which in a
    battle where both competitors have one does not say whose it is, and
    never said what it changed. The trainer's own `ability` field is the
    display name -- better than title-casing the function name, which turned
    `curse_of_forest` into "Curse Of Forest".
    """
    if not battleground.reality:
        return
    name = getattr(side, "ability", None) or inspect.currentframe(
    ).f_back.f_code.co_name.replace('_', ' ').title()
    who = getattr(side, "nickname", "") or getattr(side, "name", "")
    # the official wording, from this competitor's own Strategy cell in
    # Data/competitors.csv -- not a second copy of it kept in code
    effect = ability_text(side) if side is not None else ""

    # What it does, the first time it fires in this battle; the name alone
    # after that. Some of these trigger on every move -- Trashy fires on
    # every Poison attack -- and repeating the explanation each turn would
    # bury the rest of the log. The battleground is rebuilt per battle, so
    # this resets itself.
    told = getattr(battleground, "_abilities_explained", None)
    if told is None:
        told = battleground._abilities_explained = set()
    first = (who, name) not in told
    told.add((who, name))

    headline = f"{who}'s character ability: {name}" if who \
        else f"Character Ability: {name}"
    narrator.say(f"{CVIOLET2}{CBOLD}* {headline}"
                 f"{' -- ' + effect if effect and first else ''}{CEND}",
                 "ability", trainer=who, ability=name, effect=effect,
                 explained=first)


#: character ability name -> the phases it fires on, learned from the registry
#: on the first call for the same reason as _ABILITY_PHASES in abilities.py
_CHARACTER_PHASES = None


def UseCharacterAbility(turn, move="", abilityphase=1, verbose=False):
    """Fire this competitor's character ability, if this is its phase.

    `turn` is the battle from the point of view of the Pokemon whose ability
    this is -- see Scripts/Battle/context.py. Callers that mean "the ability
    of the Pokemon being hit" pass `turn.flip()` rather than reordering six
    arguments, which is what the old signature made them do.

    The six names the ability bodies close over are unpacked here rather than
    rewritten in each of them. There are 52 of those bodies; they read
    `user`, `target`, `move` and `battleground` straight out of this scope,
    and every one of them still does.
    """
    user_side, target_side = turn.user.trainer, turn.foe.trainer
    user, target = turn.user.active, turn.foe.active
    battleground = turn.ground

    # Same shortcut as UseAbility: 52 closures were being built on every one of
    # ~6,500 calls, to discover that this competitor's single ability does not
    # fire this phase.
    global _CHARACTER_PHASES
    if _CHARACTER_PHASES is not None and not verbose:
        phases = _CHARACTER_PHASES.get(getattr(user_side, "ability", None))
        if phases is None or abilityphase not in phases:
            return

    def trashy(*args):
        # trash power makes poison moves more decimating
        if 'Poison' in move.type:
            move.power *= 1.3
            notice(battleground, user_side)

    def dim(*args):
        # although pokemon is slower being dim, they hit more accurately
        user.applied_modifier = [0, 0, 0, 0, 0, -1, 0, 1, 0]
        _stages_before = list(user.modifier)
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        narrator.stat_change(user, _stages_before, user.modifier,
                             user.applied_modifier, battleground)
        notice(battleground, user_side)

    def desert_wind(*args):
        # a Ground type on the field, either side, and the sand comes up
        grounded = ["Ground" in (mon.type or []) for mon in (user, target)]
        if any(grounded) and battleground.weather_effect != 'Sandstorm':
            battleground.starting_weather_effect = 'Sandstorm'
            battleground.weather_effect = 'Sandstorm'
            battleground.artificial_weather = False
            if battleground.reality:
                narrator.say(weather_desc['Sandstorm'], "weather",
                             weather="Sandstorm")
            notice(battleground, user_side)

    def lamplighter(*args):
        # at the end of the turn, whoever is further gone burns a little more
        weakest = min((user, target), key=lambda mon: mon.battle_stats[0])
        if weakest.status == "Fainted" or weakest.battle_stats[0] <= 0:
            return
        burn = max(1, weakest.hp // 16)
        weakest.battle_stats[0] -= burn
        if battleground.reality:
            narrator.say(f"{weakest.name}'s wick burns down by {burn} HP.",
                         "damage", pokemon=weakest.name, amount=burn)
        notice(battleground, user_side)

    def celestial(*args):
        # a status move carries her a step further, and the light knits
        # her Pokemon back together every turn
        if abilityphase == 2:
            if move.attack_type == "Status":
                user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
                _stages_before = list(user.modifier)
                user.modifier = list(map(operator.add, user.applied_modifier,
                                         user.modifier))
                narrator.stat_change(user, _stages_before, user.modifier,
                                     user.applied_modifier, battleground)
                notice(battleground, user_side)
        elif abilityphase == 8:
            if user.status != "Fainted" and user.battle_stats[0] > 0:
                mended = min(user.hp - user.battle_stats[0],
                             max(1, user.hp // 16))
                if mended > 0:
                    user.battle_stats[0] += mended
                    if battleground.reality:
                        narrator.say(f"{user.name} is mended by {mended} HP "
                                     f"of starlight.", "heal",
                                     pokemon=user.name, amount=mended)
                    notice(battleground, user_side)

    def serene_grace(*args):
        # twice the chance of a move's secondary effect -- but only for the
        # long shots. A move that already lands its effect half the time or
        # better is left alone, so this sharpens the unreliable moves rather
        # than making the reliable ones certain. Strictly below a half: at
        # exactly 50% it does nothing.
        if move.effect_accuracy < SERENE_GRACE_CEILING:
            move.effect_accuracy = min(1, move.effect_accuracy * 2)
            notice(battleground, user_side)

    def sparking_cascade(*args):
        # Coco's battles are fought on a live floor. Two halves, two phases.
        if abilityphase == 1:
            # "starts off the battle with an electric terrain" -- the battle,
            # not every switch-in. Phase 1 fires whenever anything comes in,
            # so without the turn check her terrain would be re-laid all
            # game and could never lapse, which is not what the card says.
            #
            # It runs on the arena's own opening clock (NATURAL_TURNS) rather
            # than a move's five: this is the ground the battle starts on,
            # the same as a naturally rolled terrain, not something somebody
            # spent a turn laying.
            # `turn` is 1 on a fresh Battleground, not 0 -- switching in at
            # the start of the battle happens before the first increment.
            if (battleground.turn <= 1
                    and terrain.current(battleground) != "Electric"):
                battleground.terrain = "Electric"
                battleground.terrain_turn = terrain.NATURAL_TURNS
                if battleground.reality:
                    narrator.say(terrain.TERRAIN_ARRIVES["Electric"],
                                 "weather", terrain="Electric")
                notice(battleground, user_side)
        elif abilityphase == 8:
            # and the current keeps arcing: a tenth of the time, whatever is
            # standing in it seizes up. Flying types are not standing in it;
            # Ground and Electric shrug the current off.
            # blocks_status returns (blocked, what to say) -- a tuple, and
            # therefore always truthy. Unpacked, not tested.
            blocked, _ = terrain.blocks_status(battleground, target,
                                               "Paralysis")
            if (target.status == "Normal" and target.battle_stats[0] > 0
                    and not (SPARKING_CASCADE_IMMUNE & set(target.type or []))
                    and not blocked
                    and random.random() < SPARKING_CASCADE_CHANCE):
                # No status_effect_immunity_check here: the three types it
                # would refuse for Paralysis are the three excluded above,
                # and it wants a move to read the type off -- there is no
                # move at the end of a turn.
                paralysis = Paralysis(1)
                target.status = paralysis[0]
                target.volatile_status['NonVolatile'] = paralysis[1]
                if battleground.reality:
                    narrator.say(f"{target.name} is paralysed by the "
                                 f"current!", "status", pokemon=target.name,
                                 status="Paralysis")
                notice(battleground, user_side)

    def calibration(*args):
        # every move measured before it is thrown, so none of them miss.
        #
        # An accuracy of exactly 0 is left alone, and that is not a rounding
        # nicety: 0 is the engine's sentinel for "this move does not reach"
        # -- what Psychic Terrain, Queenly Majesty and Dazzling set to stop a
        # priority move. Calibration makes a throw accurate; it does not make
        # an impossible throw possible.
        if 0 < move.accuracy < GUARANTEE_ACCURACY:
            move.accuracy = GUARANTEE_ACCURACY
            notice(battleground, user_side)

    def violence(*args):
        # boost move power for move with direct contact
        if 'a' in move.flags:
            move.power *= 1.3
            notice(battleground, user_side)

    def naive(*args):
        # trap user and target pokemon
        user.volatile_status['Trapped'] = 1
        target.volatile_status['Trapped'] = 1
        notice(battleground, user_side)

    def telekinesis(*args):
        # boost evasion for psychic Pokemon
        if 'Psychic' in user.type:
            user.applied_modifier = [0, 0, 0, 0, 0, 0, 1, 0, 0]
            _stages_before = list(user.modifier)
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            narrator.stat_change(user, _stages_before, user.modifier,
                                 user.applied_modifier, battleground)
            notice(battleground, user_side)

    def energy_imbalance(*args):
        # trigger sudden death when opponent only has the last pokemon
        if sum(1 for pokemon in target_side.team if pokemon.status != 'Fainted') == 1:
            battleground.sudden_death = True
            narrator.say("Sudden Death is activated!!!")
            sound(audio="Assets/music/sudden_death.mp3")
            notice(battleground, user_side)

    def frighten(*args):
        # Evonne down to her last two turns frightening: every one of the
        # other side's Pokemon deals halved damage for the rest of the match. Applied to the
        # whole team rather than just what is on the field, so switching is no
        # escape -- that is the point of it landing when she is nearly out.
        if sum(1 for pokemon in user_side.team
               if pokemon.status != 'Fainted') != 2:
            return
        if getattr(battleground, 'frighten_done', False):
            return
        battleground.frighten_done = True
        for pokemon in target_side.team:
            if pokemon.status != 'Fainted':
                # Not 3 turns: hers lasts the rest of the match. Frighten is
                # in diminishing_volatile_status, so it ticks down every turn
                # -- a count no battle will ever reach is how it stays on
                # without exempting the move-inflicted version, which should
                # still wear off after three.
                pokemon.volatile_status['Frighten'] = 9999
        narrator.say(f"{user_side.nickname} turns frightening! "
              f"Every one of your Pokemon is shaken.")
        notice(battleground, user_side)

    def procrastination(*args):
        # Everything happens in the wrong order: a priority move goes last and
        # a sluggish one goes first. Negating the number is the whole trick,
        # since compare_speed only ever reads move.priority.
        if move != "" and getattr(move, 'priority', 0) != 0:
            move.priority = -move.priority
            notice(battleground, user_side)

    def death_realm(*args):
        # increase random stats when causing pokemon to faint
        if target.status == "Fainted":
            user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 0]
            user.applied_modifier[random.randint(1, 8)] += 1
            _stages_before = list(user.modifier)
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            narrator.stat_change(user, _stages_before, user.modifier,
                                 user.applied_modifier, battleground)
            notice(battleground, user_side)

    # Both of these used to stop the battle on an input() and wait for a
    # keypress, purely for a line of flavour. In a terminal that reads as the
    # character speaking to you; in the window it became a whole prompt screen
    # with one button that did nothing, in the middle of a turn. The flavour is
    # gone with it -- notice() still names the ability when it fires, and Charm
    # still costs the opponent their move, so nothing mechanical was lost.
    def monkey(*args):
        # monkey just being monkey
        if random.random() <= 0.05:
            if target_side.main and not battleground.auto_battle:
                notice(battleground, user_side)

    def charm(*args):
        # charm causes opponent and its pokemon to get distracted and misses its move
        if random.random() <= 0.1:
            move.accuracy = 0
            if target_side.main and not battleground.auto_battle:
                notice(battleground, user_side)

    def experienced(*args):
        # half recoil damage
        if move.recoil > 0:
            move.recoil *= 0.5
            notice(battleground, user_side)

    def ball_trick(*args):
        # boost move power for ball/bomb moves
        if 'i' in move.flags and battleground.reality:
            move.power *= 1.5
            notice(battleground, user_side)

    def mad_scientist(*args):
        # add priority for electric and steel type moves
        if 'Electric' in move.type or 'Steel' in move.type:
            move.priority += 1
            notice(battleground, user_side)

    def moody(*args):
        # random chance to increase and decrease user pokemon health
        random_factor = random.random()
        if random_factor <= 0.15:
            target.battle_stats[0] += math.floor(min(target.hp - target.battle_stats[0], target.hp * 0.15))
            notice(battleground, user_side)
        elif random_factor >= 0.75:
            target.battle_stats[0] -= math.floor(target.hp * 0.15)
            notice(battleground, user_side)

    def string_manipulation(*args):
        # manipulate invisible string to slow target Pokemon down
        if random.random() <= 0.2:
            target.applied_modifier = [0, 0, 0, 0, 0, -1, 0, 0, 0]
            _stages_before = list(target.modifier)
            target.modifier = list(map(operator.add, target.applied_modifier, target.modifier))
            narrator.stat_change(target, _stages_before, target.modifier,
                                 target.applied_modifier, battleground)
            notice(battleground, user_side)

    def heavy_blow(*args):
        # hit harder but move slower
        user.applied_modifier = [0, 2, 0, 0, 0, -2, 0, 0, 0]
        _stages_before = list(user.modifier)
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        narrator.stat_change(user, _stages_before, user.modifier,
                             user.applied_modifier, battleground)
        notice(battleground, user_side)

    def nimble(*args):
        # move faster but hit less for physical moves
        user.applied_modifier = [0, -2, 0, 0, 0, 2, 0, 0, 0]
        _stages_before = list(user.modifier)
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        narrator.stat_change(user, _stages_before, user.modifier,
                             user.applied_modifier, battleground)
        notice(battleground, user_side)

    def fireworks(*args):
        # deduct-HP moves deduct 50% less HP (e.g. Mind Blown, Belly Drum!) and boost power for Mind Blown
        if move.deduct > 0:
            move.deduct *= 0.5
            if move.name == 'Mind Blown':
                move.power *= 1.2
            notice(battleground, user_side)

    def gluttony(*args):
        # gluttony causes pokemon to consume anything, including entry hazard set up against them and in-battle barriers of opponent team
        if sum(user_side.entry_hazard.values()) > 0 or sum(target_side.in_battle_effects.values()) > 0:
            user_side.entry_hazard = dict.fromkeys(user_side.entry_hazard.keys(), 0)
            target_side.in_battle_effects = dict.fromkeys(target_side.in_battle_effects.keys(), 0)
            notice(battleground, user_side)

    def buggy(*args):
        # bug pokemon gains speed at the end of each turn (aka apply speed boost)
        if 'Bug' in user.type:
            user.ability += ['Speed Boost']
            notice(battleground, user_side)

    def brain_wave(*args):
        # boost additional effect chance and damage for psychic type moves
        if 'Psychic' in move.type:
            move.damage *= 1.3
            move.effect_accuracy *= 1.3
            notice(battleground, user_side)

    def champion(*args):
        champion_pokemon = {'Diantha': 'Gardevoir', 'Steven': 'Metagross', 'Leon': 'Charizard', 'Lance': 'Dragonite'}
        # champion signature pokemon get a boost
        # technically no same pokemon for each team
        if user.name == champion_pokemon[user_side.name]:
            user.applied_modifier = [0, 1, 0, 1, 0, 0, 0, 0, 0]
            _stages_before = list(user.modifier)
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            narrator.stat_change(user, _stages_before, user.modifier,
                                 user.applied_modifier, battleground)
            notice(battleground, user_side)

    def impatient(*args):
        # random chance to decrease target and user health
        # small random chance to trigger sudden death
        if random.random() <= 0.01:
            battleground.sudden_death = True
            narrator.say("Sudden Death is activated!!!")
            sound(audio="Assets/music/sudden_death.mp3")
            notice(battleground, user_side)
        elif random.random() >= 0.8:
            target.battle_stats[0] -= target.hp // 4
            user.battle_stats[0] -= user.hp // 8
            notice(battleground, user_side)

    def outlier(*args):
        # apply super luck to every pokemon
        user.ability += ['Super Luck']
        notice(battleground, user_side)

    def thief(*args):
        # steal positive stats at a random chance
        if random.random() <= 0.2:
            user.applied_modifier = [modifier if modifier > 0 else 0 for modifier in target.modifier]
            _stages_before = list(user.modifier)
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            narrator.stat_change(user, _stages_before, user.modifier,
                                 user.applied_modifier, battleground)
            target.modifier = [0 if modifier > 0 else modifier for modifier in target.modifier]

    def tenebrous(*args):
        # boost additional effect chance and damage for dark type moves
        if 'Dark' in move.type:
            move.damage *= 1.3
            move.effect_accuracy *= 1.3
            notice(battleground, user_side)

    def sucking(*args):
        # pokemon drains 30% HP for every attacking move at 50% HP or below
        if move.damage > 0 and user.battle_stats[0] <= user.hp // 2:
            user.battle_stats[0] += min(user.hp - user.battle_stats[0], math.floor((move.damage + min(target.battle_stats[0], 0)) * 0.3))
            notice(battleground, user_side)

    def ultra_boost(*args):
        # increase random stats for each pokemon at start except crit-ratio
        user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        user.applied_modifier[random.randint(1, 7)] += 1
        _stages_before = list(user.modifier)
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        narrator.stat_change(user, _stages_before, user.modifier,
                             user.applied_modifier, battleground)
        notice(battleground, user_side)

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
                notice(battleground, user_side)
        elif abilityphase == 7:
            if user.battle_stats[0] <= 0 and user.second_life > 0:
                user.second_life -= 1
                user.battle_stats[0] = user.hp
                notice(battleground, user_side)
        elif abilityphase == 8:
            if user.battle_stats[0] <= 0 and user.second_life > 0:
                user.second_life -= 1
                user.battle_stats[0] = user.hp
                notice(battleground, user_side)

    def calm(*args):
        # pokemon is immune to any non-volatile status
        if user.status not in ['Normal', 'Fainted']:
            user.status, user.volatile_status['NonVolatile'] = 'Normal', 0
            notice(battleground, user_side)

    def ruthless(*args):
        # deal additional damage depending on target health and user health, the more the target health, the more it hit
        # however, also suffer additional damage from target
        if abilityphase == 4:
            move.damage = math.floor(move.damage * min(1.7, max(1, target.battle_stats[0] / user.battle_stats[0])))  # at most 1.7x
            notice(battleground, user_side)
        elif abilityphase == 5:
            move.damage = math.floor(move.damage * 1.3)  # suffer 30% more damage
            notice(battleground, user_side)

    def death_note(*args):
        # for user pokemon with boosts (>1 stats boost), inflict it with Perish Song
        if sum(target.modifier) > 1 and target.volatile_status['PerishSong'] == 0:
            target.volatile_status['PerishSong'] += 2
            notice(battleground, user_side)

    def soak(*args):
        # add water type to user pokemon
        if 'Water' not in user.type:
            user.type += ['Water']
            notice(battleground, user_side)

    def time_travel(*args):
        # user can stop any priority move with seer ability from time travel, rendering any priority move useless
        if move.priority > 0:
            move.accuracy = 0
            notice(battleground, user_side)

    def gargantuan(*args):
        # random chance to half damage from any incoming attack
        if random.random() <= 0.25:
            move.damage *= 0.5
            notice(battleground, user_side)

    def irrational(*args):
        # pokemon receives boost but confuses
        user.applied_modifier = [0, 1, 0, 1, 0, 1, 0, 0, 0]
        _stages_before = list(user.modifier)
        user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
        narrator.stat_change(user, _stages_before, user.modifier,
                             user.applied_modifier, battleground)
        user.volatile_status['Confused'] = random.randint(2, 5)
        notice(battleground, user_side)

    def light_speed(*args):
        # add electric type to user pokemon
        if 'Electric' not in user.type:
            user.type += ['Electric']
            user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
            _stages_before = list(user.modifier)
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            narrator.stat_change(user, _stages_before, user.modifier,
                                 user.applied_modifier, battleground)
            notice(battleground, user_side)

    def killer_instinct(*args):
        # random chance to deal double damage
        if random.random() <= 0.2:
            move.damage *= 2
            notice(battleground, user_side)

    def helper(*args):
        # start with reflect
        user_side.in_battle_effects['Reflect'] = TEAM_BUFF_TURNS
        notice(battleground, user_side)

    def wanderer(*args):
        # start with tailwind
        user_side.in_battle_effects['Tailwind'] = TEAM_BUFF_TURNS
        notice(battleground, user_side)

    def motivator(*args):
        # start with light screen
        user_side.in_battle_effects['Light Screen'] = TEAM_BUFF_TURNS
        notice(battleground, user_side)

    def curse_of_forest(*args):
        # apply grass type to every target pokemon at the end of the turn
        # may flinch using attacking moves
        if abilityphase == 8:
            if 'Grass' not in target.type:
                target.type += ['Grass']
                notice(battleground, user_side)
        elif abilityphase == 4:
            if move.damage > 0 and user_side.faster and random.random() <= 0.2:
                target.volatile_status['Flinch'] = 1
                notice(battleground, user_side)

    def blunders(*args):
        # random chance for target to damage himself instead (its move damage applies to itself)
        if random.random() <= 0.1:
            target.battle_stats[0] -= move.damage
            move.damage = 0
            notice(battleground, user_side)

    def musical(*args):
        # random chance for special moves to paralyze, freeze and hypnotize target
        if random.random() <= 0.2:
            if target.status == "Normal" and move.attack_type == "Special":
                temporary_effect = random.choices([Freeze(1), Sleep(1), Paralysis(1)], weights=[1, 2, 3], k=1)[0]
                target.status = status_effect_immunity_check(user, target, move, temporary_effect[0])
                target.volatile_status['NonVolatile'] = temporary_effect[1]
                notice(battleground, user_side)

    def infiltration(*args):
        # every user move ignores ability and weather (dead calm + mold breaker)
        # thus, apply dead calm and mold breaker instead
        ability_list = ['Dead Calm', 'Mold Breaker']
        if not all(ability in user.ability for ability in ability_list):
            # dict.fromkeys, not set(): it removes duplicates while keeping
            # the order, and the order is not cosmetic -- UseAbility walks
            # this list and applies each ability in turn, so two abilities
            # writing the same field resolve by their position here. set()
            # orders by hash, which Python salts per process, so the same
            # battle from the same seed could apply them either way round.
            user.ability = list(dict.fromkeys(user.ability + ability_list))
            notice(battleground, user_side)

    def silhouette(*args):
        # apply illusion to every pokemon and shuffle second pokemon
        # halved damage with illusion on
        if abilityphase == 1:
            if 'Illusion' not in user.ability:
                user.ability += ['Illusion']
                non_fainted = [user_side.team.index(pokemon) for pokemon in user_side.team[2:] if pokemon.status != 'Fainted']
                if len(non_fainted) > 0:
                    shuffle_choice = int(random.choice(non_fainted))
                    user_side.team[1], user_side.team[shuffle_choice] = user_side.team[shuffle_choice], user_side.team[1]
                notice(battleground, user_side)
        elif abilityphase == 5:
            if user.disguise and move.damage > 0:
                move.damage *= 0.5
                notice(battleground, user_side)

    def old_legends(*args):
        # pokemon immune to fairy type attacking moves and with ultra boost
        if abilityphase == 1:
            # increase random stats for each pokemon at start except crit-ratio
            user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 0]
            user.applied_modifier[random.randint(1, 7)] += 1
            _stages_before = list(user.modifier)
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            narrator.stat_change(user, _stages_before, user.modifier,
                                 user.applied_modifier, battleground)
            notice(battleground, user_side)
        elif abilityphase == 5:
            if 'Fairy' in move.type and move.damage > 0:
                move.damage = 0
                notice(battleground, user_side)

    def blood_magic(*args):
        # pokemon drains 20% HP for every attacking move
        if move.damage > 0:
            user.battle_stats[0] += min(user.hp - user.battle_stats[0], math.floor((move.damage + min(target.battle_stats[0], 0)) * 0.2))
            notice(battleground, user_side)

    def primordial(*args):
        # always rain and apply swift swim to every pokemon
        if abilityphase == 0:
            battleground.starting_weather_effect = 'Rain'
            battleground.weather_effect = battleground.starting_weather_effect
        elif abilityphase == 1:
            user.ability += ['Swift Swim']
            notice(battleground, user_side)

    def last_stand(*args):
        # at the last pokemon, massive buff and renegerate all HP
        if sum(1 for pokemon in user_side.team if pokemon.status != 'Fainted') == 1:
            user.battle_stats[0] = user.hp
            user.applied_modifier = [0, 1, 1, 1, 1, 1, 1, 1, 1]
            _stages_before = list(user.modifier)
            user.modifier = list(map(operator.add, user.applied_modifier, user.modifier))
            narrator.stat_change(user, _stages_before, user.modifier,
                                 user.applied_modifier, battleground)
            notice(battleground, user_side)

    list_of_character_abilities = {
        "Trashy": (2, trashy),
        "Dim": (1, dim),
        "Monkey": (3, monkey),
        # Phase 1 is "switching in", which is when a Ground type can newly
        # be on the field -- either side's.
        "Desert Wind": (1, desert_wind, "Custom"),
        # Phase 8 is the end of the turn, when the count is taken.
        "Lamplighter": (8, lamplighter, "Custom"),
        # Two phases: using a move, and the end of the turn.
        "Celestial": ((2, 8), celestial, "Custom"),
        # Phase 2 is "using a move", before the effect roll is read.
        "Serene Grace": (2, serene_grace, "Custom"),
        # Two phases: the opening, when the floor goes live, and the end of
        # every turn, when the current has its chance.
        "Sparking Cascade": ((1, 8), sparking_cascade, "Custom"),
        # Phase 2 is "using a move", before the accuracy roll is read.
        "Calibration": (2, calibration, "Custom"),
        "Violence": (2, violence),
        "Naive": (1, naive),
        "Telekinesis": (1, telekinesis),
        "Energy Imbalance": (1, energy_imbalance),
        # Phase 1 is "switched in", which is when her count is re-checked.
        "Frighten": (1, frighten),
        # Phase 2 is "using a move", the only point where a priority is
        # about to be read, so flipping it there catches both sides.
        "Procrastination": (2, procrastination),
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
        "Curse of Forest": ((4, 8), curse_of_forest),
        "Blunders": (5, blunders),
        "Musical": (6, musical),
        "Infiltration": (1, infiltration),
        "Silhouette": ((1, 5), silhouette),
        "Old Legends": ((1, 5), old_legends),
        "Blood Magic": (6, blood_magic),
        "Primordial": ((0, 1), primordial),
        "Last Stand": (1, last_stand),
    }

    if _CHARACTER_PHASES is None:
        _CHARACTER_PHASES = {
            name: (entry[0] if isinstance(entry[0], tuple) else (entry[0],))
            for name, entry in list_of_character_abilities.items()}

    with suppress(KeyError, AttributeError):
        vartype = type(list_of_character_abilities[user_side.ability][0])
        if vartype is tuple:
            if abilityphase in list_of_character_abilities[user_side.ability][0]:
                list_of_character_abilities[user_side.ability][1](user_side, target_side, user, target, battleground, move, abilityphase)
        elif vartype is int:
            if abilityphase == list_of_character_abilities[user_side.ability][0]:
                list_of_character_abilities[user_side.ability][1](user_side, target_side, user, target, battleground, move, abilityphase)
