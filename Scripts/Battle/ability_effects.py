"""What each of the 153 abilities actually does, one named function each.

These were closures inside `UseAbility`, all 153 of them, defined afresh on
every call -- and that function is called about 6,500 times in five battles.
They lived there because they read six names out of the enclosing scope
rather than taking them as arguments. `AbilityCall` is those six names, so
the bodies can live out here where they can be read, tested and found.

The registry at the bottom is the whole list: name -> (phase or phases, the
function, and "Custom" for the ones invented for this game rather than taken
from the series). `Scripts/Data/abilities.py` dispatches through it and is
now only the dispatcher.

The nine phases, since the numbers are otherwise opaque:

    1  switching in                 6  after dealing damage
    2  using a move                 7  after taking damage
    3  being targeted by a move     8  end of turn
    4  dealing damage               9  switching out
    5  taking damage

Adding an ability: write the function here, add one registry line naming its
phase. Nothing else knows it exists -- that is the point of the registry.
"""
import math
import operator
import random
from contextlib import suppress

from Scripts.Art.text_color import *
from Scripts.Battle.constants import (GUARANTEE_ACCURACY, ORDER_PHASE,
                                      has_ability)
from Scripts.Battle.moves_status_condition_apply import (Burn, Paralysis,
                                                         Poison, Sleep)
from Scripts.Battle.type_chart import modifierChart, typeChart
from Scripts.Battle.type_immunity import status_effect_immunity_check
from Scripts.Data.moves import list_of_moves
from Scripts.Data.pokemon import list_of_pokemon
from Scripts.Art import narrator


class AbilityCall:
    """One firing of one ability: whose it is, who they face, and why.

    The six names every ability body used to close over, plus the move in
    play and the phase that fired. Built once per `UseAbility` call that has
    something to do -- see Scripts/Data/abilities.py.

    `user` is always the Pokemon whose ability this is. Callers that mean
    "the ability of the Pokemon being hit" pass `turn.flip()`, so a body
    never has to work out which side it is on.
    """

    __slots__ = ("user_side", "target_side", "user", "target", "ground",
                 "move", "phase")

    def __init__(self, turn, move, phase):
        self.user_side = turn.user.trainer
        self.target_side = turn.foe.trainer
        self.user = turn.user.active
        self.target = turn.foe.active
        self.ground = turn.ground
        self.move = move
        self.phase = phase


def cloudnine(call):
    call.ground.starting_weather_effect = 'Clear'
    call.ground.weather_effect = call.ground.starting_weather_effect

def drizzle(call):
    call.ground.starting_weather_effect = 'Rain'
    call.ground.weather_effect = call.ground.starting_weather_effect

def drought(call):
    call.ground.starting_weather_effect = 'Sunny'
    call.ground.weather_effect = call.ground.starting_weather_effect

def snowwarning(call):
    call.ground.starting_weather_effect = 'Hail'
    call.ground.weather_effect = call.ground.starting_weather_effect

def sandstream(call):
    call.ground.starting_weather_effect = 'Sandstorm'
    call.ground.weather_effect = call.ground.starting_weather_effect

def download(call):
    call.user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0] if call.target.battle_stats[2] < call.target.battle_stats[4] else [0, 0, 0, 1, 0, 0, 0, 0, 0]
    _stages_before = list(call.user.modifier)
    call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
    narrator.stat_change(call.user, _stages_before, call.user.modifier,
                         call.user.applied_modifier, call.ground)

def intimidate(call):
    # ability is a list; both comparisons were always true, so neither
    # Clear Body nor Hyper Cutter ever blocked the Attack drop
    if not has_ability(call.target, "Clear Body", "Hyper Cutter"):
        call.target.applied_modifier = [0, -1, 0, 0, 0, 0, 0, 0, 0]
        _stages_before = list(call.target.modifier)
        call.target.modifier = list(map(operator.add, call.target.applied_modifier, call.target.modifier))
        narrator.stat_change(call.target, _stages_before, call.target.modifier,
                             call.target.applied_modifier, call.ground)

def anticipation(call):
    for move in call.target.moveset:
        move = list_of_moves[move]
        type_effectiveness = math.prod([typeChart[move.type][call.user.type[x]] for x in range(len(call.user.type))])
        if type_effectiveness >= 2 and move.attack_type != "Status":
            narrator.say(f"{call.user.name} shuddered.")
            break

def naturalcure(call):
    if call.user.status != "Normal":
        call.user.status, call.user.volatile_status["NonVolatile"] = "Normal", 0

def stancechange(call):
    # when switched in
    if call.phase == 1:
        call.user.name, call.user.type = call.user.default_name, call.user.default_type
        call.user.nominal_base_stats = call.user.default_nominal_base_stats
    # when using move
    elif call.phase == 2:
        if call.move.attack_type != "Status":
            if call.user.charging[2] == 0:
                # to prove it is shield form (spdef > spa)
                if call.user.nominal_base_stats[4] > call.user.nominal_base_stats[3]:
                    # switched to blade form
                    narrator.say(f"{call.user.name} switches to Blade Forme.")
                    call.user.name = "Aegislash (Blade Forme)"
                    call.user.nominal_base_stats = list(map(operator.add, list_of_pokemon[call.user.name].base_stats, call.user.iv))
                    for x in range(1, 5):
                        call.user.battle_stats[x] = math.floor(0.01 * 2 * call.user.nominal_base_stats[x] * modifierChart[x][call.user.modifier[x]] * 100 + 5)
        elif call.move.name == "King's Shield":
            if call.user.nominal_base_stats[3] > call.user.nominal_base_stats[4]:
                # switched to shield form
                narrator.say(f"{call.user.name} switches to Shield Forme.")
                call.user.name, call.user.type = call.user.default_name, call.user.default_type
                call.user.nominal_base_stats = call.user.default_nominal_base_stats
                for x in range(1, 5):
                    call.user.battle_stats[x] = math.floor(0.01 * 2 * call.user.nominal_base_stats[x] * modifierChart[x][call.user.modifier[x]] * 100 + 5)

def illusion(call):
    """Wear another team-mate's face until something lands a hit.

    Every typing here is assigned as a **copy**. Handing the live `type` the
    same list object as `default_type` -- or as the team-mate being imitated
    -- makes the two one list, so a move like Forest's Curse that extends the
    live typing edits the default it will later be restored from, and the
    imitated Pokemon's typing along with it. That is the aliasing trap in
    CLAUDE.md; switching and end_battle both take copies for the same reason.
    """
    # switching in
    if call.phase == 1:
        if sum(1 for pokemon in call.user_side.team if pokemon.status != "Fainted") != 1:
            call.user.disguise = True
            for pokemon in call.user_side.team[1:]:
                if pokemon.status != "Fainted":  # use id when finalizing pokemon list
                    call.user.name = pokemon.name
                    call.user.type = list(pokemon.type)
                    break
    elif call.phase == 2 and call.ground.reality:
        call.user.type = list(call.user.default_type)
    elif call.phase == 3 and call.ground.reality:
        call.user.type = list(call.user.default_type)
    elif call.phase == 5 and call.ground.reality:
        if call.move.damage > 0 and call.user.disguise:
            call.user.name = call.user.default_name
            call.user.type = list(call.user.default_type)
            narrator.say(f"{call.user.name} is in disguise!")
            call.user.disguise = False
    elif call.phase == 8:
        if call.user.disguise:
            call.user.type = list(list_of_pokemon[call.user.name].type)
    # switched out
    elif call.phase == 9:
        call.user.name = call.user.default_name
        call.user.type = list(call.user.default_type)

def prankster(call):
    if call.move.attack_type == "Status" and "Dark" not in call.target.type:
        call.move.priority += 1

def rockhead(call):
    call.move.recoil = 0

def marvelscale(call):
    call.user.battle_stats[2] *= 1.5 if call.user.status != "Normal" else 1

def adaptability(call):
    # STAB is applied separately as 1.5, so the multiplier that turns it
    # into Adaptability's 2.0 is 2/1.5. It was wrapped in math.floor,
    # and floor(1.333) is 1 -- the ability granted nothing at all.
    call.move.abilitymodifier = (2 / 1.5) if call.move.type in call.user.type else 1

def ironfist(call):
    call.move.power *= 1.2 if 'e' in call.move.flags else 1

def strongjaw(call):
    call.move.power *= 1.5 if 'd' in call.move.flags else 1

def megalauncher(call):
    call.move.power *= 1.5 if 'h' in call.move.flags else 1

def sheerforce(call):
    if call.move.effect_type != "no_effect":
        if not (call.move.effect_type == "self_modifier" and sum(call.move.special_effect) < 0):
            call.move.power *= 1.3
            call.move.effect_accuracy = 0

def shielddust(call):
    if call.move.damage > 0 and call.move.effect_type != "no_effect":
        call.move.effect_type = "no_effect"

def overgrow(call):
    call.move.power *= 1.3 if call.move.type == "Grass" and call.user.battle_stats[0] <= call.user.hp // 3 else 1

def blaze(call):
    call.move.power *= 1.3 if call.move.type == "Fire" and call.user.battle_stats[0] <= call.user.hp // 3 else 1

def torrent(call):
    call.move.power *= 1.3 if call.move.type == "Water" and call.user.battle_stats[0] <= call.user.hp // 3 else 1

def formation(call):
    if call.move.type == "Rock":
        call.move.power *= 1.3

def landlord(call):
    if call.move.type == "Ground":
        call.move.power *= 1.3

def technician(call):
    call.move.power *= 1.5 if call.move.power <= 60 else 1

def levitate(call):
    call.user.volatile_status['Grounded'] = 0

def flashfire(call):
    if call.phase == 3:
        call.move.abilitymodifier = 0 if call.move.type == "Fire" else call.move.abilitymodifier
    elif call.phase == 5:
        if call.move.attack_type != "Status" and call.move.type == "Fire":
            call.user.volatile_status['FlashFire'] = 1

def bulletproof(call):
    call.move.abilitymodifier = 0 if 'i' in call.move.flags else call.move.abilitymodifier

def serenegrace(call):
    call.move.effect_accuracy *= 2

def victorystar(call):
    call.move.accuracy *= 1.1

def compoundeyes(call):
    call.move.accuracy *= 1.3

def skilllink(call):
    if call.move.multi[0] == 1:
        call.move.multi[1] = 5

def pixelate(call):
    if call.move.type == "Normal":
        call.move.type, call.move.power = "Fairy", call.move.power * 1.2

def materialize(call):
    if call.move.type == "Normal":
        call.move.type, call.move.power = "Steel", call.move.power * 1.2

def refrigerate(call):
    if call.move.type == "Normal":
        call.move.type, call.move.power = "Ice", call.move.power * 1.2

def moxie(call):
    if call.target.status == "Fainted" and call.ground.reality:
        call.user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def soulheart(call):
    if call.target.battle_stats[0] <= 0 and call.ground.reality:  # fainted
        call.user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def grimneigh(call):
    if call.target.status == "Fainted" and call.ground.reality:
        call.user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def improvise(call):
    if call.target.status == "Fainted" and call.ground.reality:
        call.user.applied_modifier = [0, 0, 0, 0, 0, 1, 1, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def beastboost(call):
    if call.target.status == "Fainted" and call.ground.reality:
        best_stat = call.user.nominal_base_stats.index(max(call.user.nominal_base_stats[1:6]))
        call.user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        call.user.applied_modifier[best_stat] += 1
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def toxicdebris(call):
    """Toxic Debris: a physical hit scatters poison spikes at the attacker.

    Phase 7 is "after taking damage", which is where Rough Skin sits, and at
    that phase `call.target` is the Pokemon that just attacked -- so
    `target_side` is the side the spikes are laid on. Two layers is the cap
    the move Toxic Spikes uses, and this respects it.
    """
    if call.move.attack_type != "Physical" or call.move.damage <= 0:
        return
    laid = call.target_side.entry_hazard.get("Toxic Spikes", 0)
    if laid >= 2:
        return
    call.target_side.entry_hazard["Toxic Spikes"] = laid + 1
    if call.ground.reality:
        narrator.say(f"{call.user.name} scattered toxic spikes at "
                     f"{call.target.name}'s feet!", "field",
                     hazard="Toxic Spikes")


def _hurts_on_contact(call):
    """Rough Skin and Iron Barbs: an eighth of the attacker's HP back."""
    if call.ground.reality:
        damage = max(1, call.target.hp // 8) if ('a' in call.move.flags and call.move.damage > 0) else 0
        call.target.battle_stats[0] -= damage
        if damage > 0:
            narrator.say(f"{call.user.ability} dealt {damage} damage to {call.target.name}.")


def clearbody(call):
    if "opponent_modifier" in call.move.effect_type and call.ground.reality:
        new_modifier = [x * -1 if x < 0 else 0 for x in call.user.applied_modifier]
        narrator.say(f"{call.user.name}'s stats cannot be lowered.", "fail")
        call.user.modifier = list(map(operator.add, new_modifier, call.user.modifier))

def weakarmor(call):
    if 'a' in call.move.flags:
        call.user.applied_modifier = [0, 0, -1, 0, 0, 2, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def aftermath(call):
    if call.user.status == "Fainted":
        damage = max(1, call.target.hp // 4) if ('a' in call.move.flags) else 0
        call.target.battle_stats[0] -= damage
        if damage > 0:
            narrator.say(f"{call.user.ability} dealt {damage} damage to {call.target.name}.")

def static(call):
    if 'a' in call.move.flags and call.target.status == "Normal":
        if "Electric" not in call.target.type:
            call.target.status = "Paralysis" if random.random() < 0.3 else "Normal"

def defiant(call):
    if call.move.effect_type == "opponent_modifier" and sum(call.user.applied_modifier) < 0:
        call.user.applied_modifier = [0, 2, 0, 0, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def stamina(call):
    if call.move.attack_type != "Status":
        call.user.applied_modifier = [0, 0, 1, 0, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def sandspit(call):
    if call.move.damage > 0 and call.ground.weather_effect != 'Sandstorm':
        call.ground.weather_effect = 'Sandstorm'
        call.ground.artificial_weather = True

def poisonpoint(call):
    if 'a' in call.move.flags and call.target.status == "Normal":
        call.target.status = "Poison" if random.random() < 0.3 else "Normal"

#: Toxic Chain's chance to badly poison whatever it hits, as in the series.
TOXIC_CHAIN_CHANCE = 0.3


def toxicchain(call):
    """A move that connects may badly poison the target. 30%, as in Gen 9.

    Two things this has to do that the first cut did not.

    **Respect the immunity.** Poison and Steel types cannot be poisoned, and
    writing the status straight onto `target.status` walked past that -- a
    Steel type could be left badly poisoned by an ability that in the real
    games does nothing to it. `status_effect_immunity_check` is the engine's
    own answer to that question and is what every move uses.

    **Set the counter.** Bad poison escalates by a counter kept in
    `volatile_status['NonVolatile']`, and every other site that inflicts it
    initialises that alongside the status. Without it the damage escalated
    from whatever number happened to be left there by something else.
    """
    if call.move.damage > 0 and call.target.status == "Normal":
        if random.random() >= TOXIC_CHAIN_CHANCE:
            return
        inflicted = status_effect_immunity_check(
            call.user, call.target, call.move, "BadPoison")
        if inflicted != "BadPoison":
            return                      # immune; the check said so out loud
        call.target.status = "BadPoison"
        call.target.volatile_status['NonVolatile'] = 1

def justified(call):
    if call.move.attack_type != "Status" and call.move.type == "Dark":
        call.user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def cursedbody(call):
    if call.move.damage > 0:
        if random.random() < 0.3:
            with suppress(ValueError, AttributeError):
                call.target.disabled_moves[call.move.name] = 5

def speedboost(call):
    call.user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
    _stages_before = list(call.user.modifier)
    call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
    narrator.stat_change(call.user, _stages_before, call.user.modifier,
                         call.user.applied_modifier, call.ground)
    narrator.say(f"{call.user.ability} gains speed.")

def shedskin(call):
    if call.user.status not in ("Normal", "Fainted"):
        call.user.status = "Normal" if random.random() < 1 / 3 else call.user.status
        narrator.say(f"{call.user.ability} cured status condition.")

def baddreams(call):
    if call.target.status == "Sleep":
        call.target.battle_stats[0] -= max(1, call.target.hp // 8)

def poisonousblow(call):
    if call.user.battle_stats[0] <= call.user.hp // 3:
        call.target.status = status_effect_immunity_check(call.user, call.target, call.move, 'BadPoison')

def arenatrap(call):
    call.target.volatile_status['Trapped'] += 1 if call.target.volatile_status['Ungrounded'] == 0 else 0

def _cannot_be_crit(call):
    """Battle Armor and Shell Armor: no critical hits land."""
    call.move.critRatio = 0


def chlorophyll(call):
    # double speed when sunny
    call.user.battle_stats[5] *= 2 if call.ground.weather_effect == 'Sunny' else 1

def swiftswim(call):
    # double speed when rain
    call.user.battle_stats[5] *= 2 if call.ground.weather_effect == 'Rain' else 1

def slushrush(call):
    # double speed when hail
    call.user.battle_stats[5] *= 2 if call.ground.weather_effect == 'Hail' else 1

def raindish(call):
    if call.ground.weather_effect == 'Rain':
        call.user.battle_stats[0] += min(call.user.hp - call.user.battle_stats[0], call.user.hp // 16)
        narrator.say(f"{call.user.name} healed {min(call.user.hp - call.user.battle_stats[0], call.user.hp // 16)} HP.", "heal")

def icebody(call):
    if call.ground.weather_effect == 'Hail':
        call.user.battle_stats[0] += min(call.user.hp - call.user.battle_stats[0], call.user.hp // 16)
        narrator.say(f"{call.user.name} healed {min(call.user.hp - call.user.battle_stats[0], call.user.hp // 16)} HP.", "heal")

def earlybird(call):
    if call.user.status == "Sleep":
        call.user.volatile_status['NonVolatile'] -= 1

def effectspore(call):
    if 'a' in call.move.flags and call.target.status == "Normal":
        if random.random() <= 0.3:
            temporary_effect = random.choice([Paralysis(1), Poison(1), Sleep(1)])
            call.target.status = status_effect_immunity_check(call.user, call.target, call.move, temporary_effect[0])
            call.target.volatile_status['NonVolatile'] = temporary_effect[1]

def flamebody(call):
    if 'a' in call.move.flags and call.target.status == "Normal":
        temporary_effect = Burn(0.3)
        call.target.status = status_effect_immunity_check(call.user, call.target, call.move, temporary_effect[0])
        call.target.volatile_status['NonVolatile'] = temporary_effect[1]

def guts(call):
    if call.user.status != "Normal":
        call.user.battle_stats[1] *= 1.5

def _doubles_attack(call):
    """Huge Power and Pure Power: twice the Attack stat."""
    call.user.battle_stats[1] *= 2


def hustle(call):
    if call.move.attack_type == "Physical":
        call.move.power *= 1.5
        call.move.accuracy *= 0.8

def hypercutter(call):
    if "opponent_modifier" in call.move.effect_type:
        if call.user.applied_modifier[1] < 0:
            new_modifier = [0, call.user.applied_modifier[1] * -1, 0, 0, 0, 0, 0, 0, 0]
            narrator.say(f"{call.user.name}'s attack cannot be lowered.", "fail")
            call.user.modifier = list(map(operator.add, new_modifier, call.user.modifier))

def keeneye(call):
    if "opponent_modifier" in call.move.effect_type:
        if call.user.applied_modifier[1] < 0:
            new_modifier = [0, 0, 0, 0, 0, 0, 0, call.user.applied_modifier[7] * -1, 0]
            narrator.say(f"{call.user.name}'s accuracy cannot be lowered.", "fail")
            call.user.modifier = list(map(operator.add, new_modifier, call.user.modifier))

def _wakes_up_immediately(call):
    """Insomnia, Vital Spirit and Sweet Veil: cannot stay asleep."""
    if call.user.status == "Sleep":
        call.user.status, call.user.volatile_status['NonVolatile'] = "Normal", 0



def limber(call):
    if call.user.status == "Paralysis":
        call.user.status, call.user.volatile_status['NonVolatile'] = "Normal", 0

def immunity(call):
    if call.user.status == "Poison" or call.user.status == "BadPoison":
        call.user.status, call.user.volatile_status['NonVolatile'] = "Normal", 0

def innerfocus(call):
    call.user.volatile_status['Flinch'] = 0

def owntempo(call):
    call.user.volatile_status['Confused'] = 0

def magmaarmor(call):
    if call.user.status == "Freeze":
        call.user.status, call.user.volatile_status['NonVolatile'] = "Normal", 0

def waterveil(call):
    if call.user.status == "Burn":
        call.user.status, call.user.volatile_status['NonVolatile'] = "Normal", 0

def lightningrod(call):
    if call.phase == 3:
        call.move.abilitymodifier = 0 if call.move.type == "Electric" else call.move.abilitymodifier
    elif call.phase == 5:
        if call.move.attack_type != "Status" and call.move.type == "Electric":
            call.user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
            _stages_before = list(call.user.modifier)
            call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
            narrator.stat_change(call.user, _stages_before, call.user.modifier,
                                 call.user.applied_modifier, call.ground)

def stormdrain(call):
    if call.phase == 3:
        call.move.abilitymodifier = 0 if call.move.type == "Water" else call.move.abilitymodifier
    elif call.phase == 5:
        if call.move.attack_type != "Status" and call.move.type == "Water":
            call.user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
            _stages_before = list(call.user.modifier)
            call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
            narrator.stat_change(call.user, _stages_before, call.user.modifier,
                                 call.user.applied_modifier, call.ground)

def sapsipper(call):
    if call.phase == 3:
        call.move.abilitymodifier = 0 if call.move.type == "Grass" else call.move.abilitymodifier
    elif call.phase == 5:
        if call.move.attack_type != "Status" and call.move.type == "Grass":
            call.user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
            _stages_before = list(call.user.modifier)
            call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
            narrator.stat_change(call.user, _stages_before, call.user.modifier,
                                 call.user.applied_modifier, call.ground)

def voltabsorb(call):
    if call.phase == 3:
        call.move.abilitymodifier = 0 if call.move.type == "Electric" else call.move.abilitymodifier
    elif call.phase == 5:
        if call.move.attack_type != "Status" and call.move.type == "Electric":
            call.user.battle_stats[0] += min(call.user.hp // 4, call.user.hp - call.user.battle_stats[0])

def motordrive(call):
    if call.phase == 3:
        call.move.abilitymodifier = 0 if call.move.type == "Electric" else call.move.abilitymodifier
    elif call.phase == 5:
        if call.move.attack_type != "Status" and call.move.type == "Electric":
            call.user.applied_modifier = [0, 0, 0, 0, 0, 1, 0, 0, 0]
            _stages_before = list(call.user.modifier)
            call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
            narrator.stat_change(call.user, _stages_before, call.user.modifier,
                                 call.user.applied_modifier, call.ground)

def watercompaction(call):
    if call.move.attack_type != "Status" and call.move.type == "Water":
        call.user.applied_modifier = [0, 0, 2, 0, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def waterabsorb(call):
    if call.phase == 3:
        call.move.abilitymodifier = 0 if call.move.type == "Water" else call.move.abilitymodifier
    elif call.phase == 5:
        if call.move.attack_type != "Status" and call.move.type == "Water":
            call.user.battle_stats[0] += min(call.user.hp // 4, call.user.hp - call.user.battle_stats[0])

def sandveil(call):
    if call.ground.weather_effect == 'Sandstorm':
        call.move.evasion *= 1.25

def sandforce(call):
    if call.ground.weather_effect == 'Sandstorm':
        if call.move.type in ("Rock", "Steel", "Ground"):
            call.move.power *= 1.3

def snowcloak(call):
    if call.ground.weather_effect == 'Hail':
        call.move.evasion *= 1.25

def shadowtag(call):
    call.target.volatile_status['Trapped'] += 1

def soundproof(call):
    call.move.abilitymodifier = 0 if 'f' in call.move.flags else call.move.abilitymodifier

def sturdy(call):
    if call.move.damage > call.user.battle_stats[0] and call.user.battle_stats[0] == call.user.hp:
        call.user.battle_stats[0] += (call.move.damage - call.user.battle_stats[0] + 1)

def swarm(call):
    call.move.power *= 1.5 if call.move.type == "Bug" and call.user.battle_stats[0] <= call.user.hp // 3 else 1

def synchronize(call):
    if call.user.status in ['Paralysis', 'Poison', 'BadPoison', 'Burn']and "target_non_volatile" in call.move.effect_type and call.target.status == "Normal":
        call.target.status = status_effect_immunity_check(call.user, call.target, call.move, call.user.status)
        call.target.volatile_status['NonVolatile'] = 1 if call.target.status == "BadPoison" else 0

#: the abilities Trace refuses to copy, for the same reason Mummy cannot
#: replace them: they are the Pokemon rather than something it is holding.
UNTRACEABLE = ('Disguise', 'Flower Gift', 'Gulp Missile', 'Hunger Switch',
               'Ice Face', 'Illusion', 'Imposter', 'Neutralizing Gas',
               'Receiver', 'RKS System', 'Schooling', 'Stance Change',
               'Trace', 'Zen Mode')


def trace(call):
    """Copy the opponent's ability on the way in; give it back on the way out.

    Three separate faults, all of them the list-versus-string and aliasing
    traps in CLAUDE.md:

    * the guard compared the whole *list* against a list of strings, so it
      was permanently true and Trace copied Illusion, Disguise and Stance
      Change -- the abilities it exists to refuse.
    * copying assigned the target's list itself, so both Pokemon then shared
      one list and a later `user.ability += [...]` from a character ability
      wrote into the *opponent's* abilities.
    * restoring assigned `default_ability` itself, which is the alias the
      switching code and `end_battle` both take `list(...)` of. After one
      switch out, "restore to default" and "the current ability" were the
      same object, so the next mutation edited the default it would later
      restore from.
    """
    if call.phase == 1:
        if not has_ability(call.target, *UNTRACEABLE):
            call.user.ability = list(call.target.ability)
    elif call.phase == 9:
        call.user.ability = list(call.user.default_ability)

def thickfat(call):
    if "Ice" in call.move.type or "Fire" in call.move.type:
        call.target.battle_stats[1] *= 0.5
        call.target.battle_stats[3] *= 0.5

def whitesmoke(call):
    if "opponent_modifier" in call.move.effect_type:
        new_modifier = [x * -1 if x < 0 else 0 for x in call.user.applied_modifier]
        narrator.say(f"{call.user.name}'s stats cannot be lowered.", "fail")
        call.user.modifier = list(map(operator.add, new_modifier, call.user.modifier))

def wonderguard(call):
    if not call.move.super_effective:
        call.move.damage = 0

def tintedlens(call):
    if call.move.not_effective:
        call.move.damage *= 2

def divinepower(call):
    # 1.25, down from 1.5. At 1.5 a neutral hit from a Divine Power holder
    # beat most super-effective hits outright, which made type matchups
    # against them close to meaningless.
    if not call.move.super_effective:
        call.move.damage = math.floor(call.move.damage * 1.25)

def divineaegis(call):
    if not call.move.super_effective:
        call.move.damage = math.floor(call.move.damage * 0.75)

def _softens_super_effective(call):
    """Solid Rock and Filter: a quarter off anything super effective."""
    if call.move.super_effective:
        call.move.damage *= 0.75


def supremeoverload(call):
    # 10% more attack and special attack for every team-mate already down.
    # Read off the team rather than kept as a counter, so it is always
    # current -- it rises as the match goes on and needs no bookkeeping
    # when a Pokemon faints.
    fallen = sum(1 for member in call.user_side.team
                 if member is not call.user and member.status == "Fainted")
    if fallen:
        boost = 1 + 0.1 * fallen
        call.user.battle_stats[1] = int(call.user.battle_stats[1] * boost)
        call.user.battle_stats[3] = int(call.user.battle_stats[3] * boost)

def thermalexchange(call):
    if call.phase == 5:
        # hit by a fire move: attack up a stage
        if call.move.attack_type != "Status" and 'Fire' in call.move.type:
            call.user.applied_modifier = [0, 1, 0, 0, 0, 0, 0, 0, 0]
            call.user.modifier = list(map(operator.add, call.user.applied_modifier,
                                     call.user.modifier))
    elif call.phase == 7:
        # and it cannot be burned, the way Water Veil cannot
        if call.user.status == "Burn":
            call.user.status, call.user.volatile_status['NonVolatile'] = "Normal", 0

def angerpoint(call):
    if call.move.critical_hit:
        call.user.applied_modifier = [0, 6, 0, 0, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def hydration(call):
    if call.ground.weather_effect == 'Rain':
        call.user.status, call.user.volatile_status['NonVolatile'] = "Normal", 0

def reckless(call):
    call.move.power *= 1.2 if call.move.recoil > 0 else 1

def defeatist(call):
    if call.user.battle_stats[0] <= call.user.hp // 2:
        call.user.battle_stats[1] *= 0.5
        call.user.battle_stats[3] *= 0.5

def moody(call):
    indexes = random.sample(range(1, 7), 2)
    new_modifier = [0] * 9
    new_modifier[indexes[0]] += 2
    new_modifier[indexes[1]] -= 1
    call.user.applied_modifier = new_modifier
    _stages_before = list(call.user.modifier)
    call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
    narrator.stat_change(call.user, _stages_before, call.user.modifier,
                         call.user.applied_modifier, call.ground)

def multiscale(call):
    if call.user.battle_stats[0] == call.user.hp:
        call.move.damage *= 0.5

def regenerator(call):
    call.user.battle_stats[0] += min(call.user.hp - call.user.battle_stats[0], call.user.hp // 3)

def competitive(call):
    if call.move.effect_type == "opponent_modifier" and sum(call.user.applied_modifier) < 0:
        call.user.applied_modifier = [0, 0, 0, 2, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def galewings(call):
    call.move.priority += 1 if call.move.type == "Flying" else 0

def sniper(call):
    if call.move.critical_hit:
        call.move.damage = math.floor(call.move.damage * 1.5)

def simple(call):
    _stages_before = list(call.user.modifier)
    call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
    narrator.stat_change(call.user, _stages_before, call.user.modifier,
                         call.user.applied_modifier, call.ground)

def unaware(call):
    call.move.ignoreDef, call.move.ignoreEvasion = True, True

def disguise(call):
    if call.phase == 1:
        if not call.user.transform:
            call.user.disguise = True
    elif call.phase == 5 and call.ground.reality:
        if call.move.attack_type != "Status" and call.move.damage > 0:
            if call.user.disguise:
                call.move.damage = 0
                call.user.disguise, call.user.transform = False, True
                narrator.say("The disguise is busted.")

def noguard(call):
    call.move.accuracy = GUARANTEE_ACCURACY  # guarantee hit
    call.move.ignoreInvulnerability = True

def icescales(call):
    if call.move.attack_type == "Special":
        call.move.power //= 2

def deadcalm(call):
    call.move.ignoreWeather = True

def berserk(call):
    if call.user.battle_stats[0] < call.user.hp // 2 and call.move.damage > 0:
        call.user.applied_modifier = [0, 0, 0, 1, 0, 0, 0, 0, 0]
        _stages_before = list(call.user.modifier)
        call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
        narrator.stat_change(call.user, _stages_before, call.user.modifier,
                             call.user.applied_modifier, call.ground)

def scrappy(call):
    call.move.ignoreImmunity = ["Ghost"]

def infiltrator(call):
    call.move.ignoreBarrier = True

def moldbreaker(call):
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
    if call.target.ability in ignorable_ability_list:
        call.move.ignoreAbility = True

def _retypes_to_the_move(call):
    """Protean and Libero: become the type of the move being used."""
    if call.phase == 1:
        call.user.type = call.user.default_type
    elif call.phase == 2:
        call.user.type = [call.move.type]
    elif call.phase == 9:
        call.user.type = call.user.default_type


def longreach(call):
    with suppress(KeyError):
        call.move.flags.remove('a')

def scorch(call):
    if call.target.status == "Normal" and call.target.volatile_status['Grounded'] > 0:  # grounded
        effect = Burn(1)
        call.target.status = status_effect_immunity_check(call.user, call.target, call.move, effect[0])
        if call.target.status != "Normal":
            call.target.volatile_status['NonVolatile'] = effect[1]

def steelworker(call):
    if call.move.type == "Steel":
        call.move.power *= 1.5

def analytic(call):
    if not call.user_side.faster:
        call.move.damage = math.floor(call.move.damage * 1.3)

def goredrinker(call):
    if call.user.battle_stats[0] < call.user.hp // 2 and call.ground.reality:
        call.user.battle_stats[0] += math.floor(min(call.user.hp - call.user.battle_stats[0], call.move.damage * 0.5))
        narrator.say(f"Goredrinker ability drains {math.floor(min(call.user.hp - call.user.battle_stats[0], call.move.damage * 0.5))} HP.")

def screencleaner(call):
    team_effect = ["Aurora Veil", "Reflect", "Light Screen"]
    for effect in team_effect:
        if call.user_side.in_battle_effects[effect] > 0:
            call.user_side.in_battle_effects[effect] = 0
        if call.target_side.in_battle_effects[effect] > 0:
            call.target_side.in_battle_effects[effect] = 0

def queenlymajesty(call):
    if call.move.priority > 0 and call.ground.reality:
        narrator.say(f"{call.target.name} cannot use {call.move.name} due to the Majesty's pressure!")
        call.move.accuracy = 0

def dazzling(call):
    if call.move.priority > 0 and call.ground.reality:
        narrator.say(f"{call.target.name} cannot use {call.move.name}!")
        call.move.accuracy = 0

def toughclaws(call):
    if 'a' in call.move.flags:
        call.move.power *= 1.3

def fluffy(call):
    if 'a' in call.move.flags:
        call.move.damage //= 2
    if "Fire" in call.move.type:
        call.move.damage *= 2

def heatproof(call):
    if "Fire" in call.move.type:
        call.move.damage //= 2

#: the abilities Mummy cannot replace -- the ones that *are* the Pokemon
#: rather than something it happens to have. Four of them are held in this
#: roster: Battle Bond, Disguise, Stance Change, and Mummy itself.
MUMMY_PROOF = ('Multitype', 'Zen Mode', 'Stance Change', 'Schooling',
               'Battle Bond', 'Power Construct', 'Shields Down',
               'RKS System', 'Disguise', 'Comatose', 'Mummy')


def mummy(call):
    """Contact with the holder replaces the attacker's ability with Mummy.

    Both halves of this were the list-versus-string trap from CLAUDE.md.

    The guard read `call.target.ability not in (...)`, comparing the whole
    *list* against a tuple of strings -- a list is never in a tuple of
    strings, so the guard was permanently true and Mummy overwrote exactly
    the four abilities it exists to leave alone: Aegislash's Stance Change,
    Mimikyu's Disguise, Greninja's Battle Bond.

    And it then assigned the bare string `"Mummy"`, where every other site
    in the engine holds a list. That is what crashed the rating simulation
    after 4,000 battles: the `infiltration` character ability does
    `user.ability + ['Dead Calm', 'Mold Breaker']`, and str + list raises.
    It also made `random.choice(pokemon.ability)` in `choose_pokemon` able
    to return a single *letter*.
    """
    if 'a' in call.move.flags:
        if not has_ability(call.target, *MUMMY_PROOF):
            call.target.ability = ["Mummy"]

def punkrock(call):
    if call.phase == 4:
        if 'f' in call.move.flags:
            call.move.damage *= 1.3
    elif call.phase == 5:
        if 'f' in call.move.flags:
            call.move.damage //= 2

def instrumental(call):
    if call.phase == 4:
        if 'f' in call.move.flags:
            call.move.damage *= 1.3
    elif call.phase == 5:
        if 'f' in call.move.flags:
            call.move.damage *= 0.5
        if call.move.type == "Fire" or call.move.type == "Water":
            call.move.damage *= 1.5

def illuminate(call):
    # this ability does nothing in battle
    # added custom ability for illuminate (see in spy opponent)
    pass

def pressure(call):
    # this ability does nothing in battle
    # added custom ability for pressure (see in spy opponent)
    pass

def magicguard(call):
    # this ability effect is indicated in hp_decreasing_modifier
    pass

def battlebond(call):
    # exclusive to faker-greninja
    if call.move.name == "Water Shuriken":
        call.move.power *= 1.5

def waterbubble(call):
    if call.phase == 4:
        if 'Water' in call.move.type:
            call.move.damage *= 2
    elif call.phase == 5:
        if 'Fire' in call.move.type:
            call.move.damage *= 0.5
    elif call.phase == 6:
        # immune to burn
        if call.user.status == 'Burn':
            call.user.status = 'Normal'

def superluck(call):
    call.user.applied_modifier = [0, 0, 0, 0, 0, 0, 0, 0, 1]
    _stages_before = list(call.user.modifier)
    call.user.modifier = list(map(operator.add, call.user.applied_modifier, call.user.modifier))
    narrator.stat_change(call.user, _stages_before, call.user.modifier,
                         call.user.applied_modifier, call.ground)

def liquidooze(call):
    if 'hp_draining' in call.move.effect_type:
        drain = call.move.special_effect if type(call.move.effect_type) is str else call.move.special_effect[call.move.effect_type.index('hp_draining')]
        narrator.say(f"{call.target.name} is affected by liquid ooze.")
        call.target.battle_stats[0] -= min(call.target.hp - call.target.battle_stats[0] + call.move.damage, math.floor((call.move.damage + min(call.target.battle_stats[0] + call.move.damage, 0)) * drain)) * 2

def strongroots(call):
    call.user.volatile_status['Ingrain'] = 1
    call.user.volatile_status['Trapped'] = 1


REGISTRY = {
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
    'Prankster': (ORDER_PHASE, prankster),
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
    'Toxic Debris': (7, toxicdebris),
    'Rough Skin': (7, _hurts_on_contact),
    'Iron Barbs': (7, _hurts_on_contact),
    'Clear Body': (7, clearbody),
    'Weak Armor': (7, weakarmor),
    'Aftermath': (7, aftermath),
    'Static': (7, static),
    'Defiant': (7, defiant),
    'Stamina': (7, stamina),
    'Sand Spit': (7, sandspit),
    'Poison Point': (7, poisonpoint),
    'Toxic Chain': (4, toxicchain),
    'Justified': (7, justified),
    'Cursed Body': (7, cursedbody),
    'Speed Boost': (8, speedboost),
    'Shed Skin': (8, shedskin),
    'Bad Dreams': (8, baddreams),
    'Poisonous Blow': (8, poisonousblow, "Custom"),
    'Arena Trap': (1, arenatrap),
    'Battle Armor': (3, _cannot_be_crit),
    'Shell Armor': (3, _cannot_be_crit),
    'Chlorophyll': (ORDER_PHASE, chlorophyll),
    'Swift Swim': (ORDER_PHASE, swiftswim),
    'Slush Rush': (ORDER_PHASE, slushrush),
    'Rain Dish': (8, raindish),
    'Ice Body': (8, icebody),
    'Early Bird': (8, earlybird),
    'Effect Spore': (7, effectspore),
    'Flame Body': (7, flamebody),
    'Guts': (2, guts),
    'Huge Power': (2, _doubles_attack),
    'Pure Power': (2, _doubles_attack),
    'Hustle': (2, hustle),
    'Hyper Cutter': (7, hypercutter),
    'Keen Eye': (7, keeneye),
    'Insomnia': ((6, 7), _wakes_up_immediately),
    'Vital Spirit': ((6, 7), _wakes_up_immediately),
    'Sweet Veil': ((6, 7), _wakes_up_immediately),
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
    'Solid Rock': (5, _softens_super_effective),
    'Filter': (5, _softens_super_effective),
    # Phase 2 is "using a move", where the attack stats are read, so the
    # boost is applied fresh each time rather than accumulating.
    'Supreme Overload': (2, supremeoverload, "Custom"),
    'Thermal Exchange': ((5, 7), thermalexchange, "Custom"),
    'Anger Point': (5, angerpoint),
    'Hydration': (8, hydration),
    'Reckless': (2, reckless),
    'Defeatist': (2, defeatist),
    'Moody': (8, moody),
    'Multiscale': (5, multiscale),
    'Regenerator': (9, regenerator),
    'Competitive': (7, competitive),
    'Gale Wings': (ORDER_PHASE, galewings),
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
    'Protean': ((1, 2, 9), _retypes_to_the_move),
    'Libero': ((1, 2, 9), _retypes_to_the_move),
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
