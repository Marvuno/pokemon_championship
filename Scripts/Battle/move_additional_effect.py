import random
import math
from contextlib import suppress
from copy import deepcopy

from Scripts.Art.text_color import *
from Scripts.Data.pokemon import *
from Scripts.Data.abilities import *
from Scripts.Data.moves import *
from Scripts.Data.competitors import *
from Scripts.Game.game_procedure import *
from Scripts.Battle.weather import *
from Scripts.Battle.entry_hazard import *
from Scripts.Battle.type_chart import *
from Scripts.Battle.damage_calculation import *
from Scripts.Battle.constants import *
from Scripts.Battle.type_immunity import *
from Scripts.Battle.battle_checklist import *
from Scripts.Battle.switching import *
from Scripts.Battle.ai import *
from Scripts.Battle.context import Side, Turn
from Scripts.Art import narrator
from Scripts.Battle import terrain


# check if the modifier reaches +6/-6
def check_modifier_limit(pokemon):
    pokemon.modifier = [6 if x > 6 else x for x in pokemon.modifier]
    pokemon.modifier = [-6 if x < -6 else x for x in pokemon.modifier]
    return pokemon.modifier


def move_special_effect(turn, move):
    """Apply whatever the move does beyond damage.

    One dispatch table, one signature for every handler. They used to take the
    same nine positional arguments each -- two competitors, two parties, two
    Pokemon, the battleground, the move and its payload -- and the median
    handler used three of them; `target_team` was used by one of twenty-four.
    See Scripts/Battle/context.py.
    """
    move_additional_effect = {
        "target_non_volatile": check_move_target_non_volatile_status_effect,
        "target_volatile": check_move_target_volatile_status_effect,
        "user_volatile": check_move_user_volatile_status_effect,
        "opponent_modifier": check_move_target_modifier,
        "self_modifier": check_move_user_modifier,
        "self_heal": check_move_user_heal,
        "weather_heal": check_move_user_heal_by_weather,
        "roost": check_move_roost,
        "team_status_heal": check_move_heal_team_status,
        "hp_draining": check_move_hp_draining,
        "user_protection": check_move_user_protection,
        "self_team_buff": check_move_user_team_buff,
        "weather_effect": check_move_battleground_weather_effect,
        "field_effect": check_move_battleground_field_effect,
        "terrain": check_move_terrain,
        "apply_entry_hazard": check_move_entry_hazard_effect,
        "clear_entry_hazard": check_move_clear_entry_hazard,
        "switching": check_move_self_switching_effect,
        "cursing": check_move_cursing,
        "hp_split": check_move_hp_split,
        "target_disable": check_move_disable,
        "reset_target_modifier": check_move_reset_target_modifier,
        "reset_user_modifier": check_move_reset_user_modifier,
        "swap_barrier": check_move_swap_barrier,
        "add_target_type": check_move_add_target_type,
        "countering": check_move_countering,
        "ohko": check_move_ohko,
    }
    vartype = type(move.effect_type)
    # only one effect
    if vartype is str:
        if move.effect_type in move_additional_effect.keys():
            move_additional_effect[move.effect_type](
                turn, move, move.special_effect)
    # more than one effect
    elif vartype is list:
        for i in range(len(move.effect_type)):
            # Same membership check the single-effect branch above does. Five
            # effect_types are handled elsewhere -- retaliation, before_hand,
            # after_hand and modifier_dependent are power modifiers, and
            # remove_team_buff is applied with type effectiveness -- so they
            # have no entry here on purpose. A single-effect move naming one
            # of them is skipped quietly; a *list* naming one used to index
            # this dict directly and raise KeyError. No move does today; the
            # first one to would have been a crash rather than a no-op.
            handler = move_additional_effect.get(move.effect_type[i])
            if handler is None:
                continue
            special_effect = move.special_effect[i]
            handler(turn, move, special_effect)


# check if the move induces a status condition on the target
def check_move_target_non_volatile_status_effect(turn, move, special_effect):
    # status condition
    temporary_status = special_effect(move.effect_accuracy)
    refused, line = terrain.blocks_status(turn.ground, turn.foe.active,
                                          temporary_status[0])
    if refused:
        narrator.say(line % turn.foe.active.name, "fail")
        return
    if turn.foe.active.status == "Normal" and temporary_status[0] != "Normal":  # change of non-volatile status
        turn.foe.active.status = status_effect_immunity_check(turn.user.active, turn.foe.active, move, temporary_status[0])
        with suppress(IndexError, KeyError):
            if turn.foe.active.volatile_status["NonVolatile"] <= 0:
                turn.foe.active.volatile_status["NonVolatile"] = temporary_status[1]
                narrator.say(f"{turn.foe.active.name} is now {turn.foe.active.status}!")
    elif turn.foe.active.status != "Normal" and temporary_status[0] != "Normal":  # non-volatile status won't add up
        narrator.say(f"{turn.foe.active.name} is already {turn.foe.active.status}!")


# check if the move induces a volatile status on the target
def check_move_target_volatile_status_effect(turn, move, special_effect):
    # status condition
    temporary_status = special_effect(move.effect_accuracy)
    # for yawn only
    if (temporary_status[0] == "Confused"
            and terrain.blocks_confusion(turn.ground, turn.foe.active)):
        narrator.say("The mist keeps %s clear-headed!"
                     % turn.foe.active.name, "fail")
    elif temporary_status[0] == "Yawn" and turn.foe.active.status != "Normal":
        narrator.failed()
    elif temporary_status[0] == "Flinch" and turn.foe.trainer.faster:
        pass
    else:
        with suppress(KeyError):
            if turn.foe.active.volatile_status[temporary_status[0]] <= 0:
                turn.foe.active.volatile_status[temporary_status[0]] = temporary_status[1]
                narrator.say(f"{turn.foe.active.name} is now {temporary_status[0]}!")
            else:
                narrator.say(f"The opponent is already {temporary_status[0]}!")


# check if the move induces a volatile status on the user
def check_move_user_volatile_status_effect(turn, move, special_effect):
    # status condition
    temporary_status = special_effect(move.effect_accuracy)
    with suppress(KeyError):
        if turn.user.active.volatile_status[temporary_status[0]] <= 0 or temporary_status[0] == "Grounded":
            turn.user.active.volatile_status[temporary_status[0]] = temporary_status[1]
            narrator.say(f"You are now {temporary_status[0]}!")
        else:
            narrator.say(f"You are already {temporary_status[0]}!")


# check if the move changes the target's stats (+ve/-ve)
def check_move_target_modifier(turn, move, special_effect):
    # increase/decrease stats on the target
    turn.foe.active.applied_modifier = special_effect if random.random() <= move.effect_accuracy else [0] * 9
    was = list(turn.foe.active.modifier)
    turn.foe.active.modifier = list(map(operator.add, turn.foe.active.applied_modifier, turn.foe.active.modifier))
    turn.foe.active.modifier = check_modifier_limit(turn.foe.active)
    # A sentence per stat, saying which way and how far -- see
    # narrator.stat_change. `any()` rather than `sum() > 0`, because a pure
    # debuff sums to a negative and a mixed change can sum to zero, so stat
    # drops were never announced at all.
    if any(turn.foe.active.applied_modifier):
        narrator.stat_change(turn.foe.active, was, turn.foe.active.modifier,
                             turn.foe.active.applied_modifier, turn.ground)


# check if the move changes the user's stats (+ve/-ve)
def check_move_user_modifier(turn, move, special_effect):
    # increase/decrease stats on the user
    turn.user.active.applied_modifier = special_effect if random.random() <= move.effect_accuracy else [0] * 9
    was = list(turn.user.active.modifier)
    turn.user.active.modifier = list(map(operator.add, turn.user.active.applied_modifier, turn.user.active.modifier))
    turn.user.active.modifier = check_modifier_limit(turn.user.active)
    if any(turn.user.active.applied_modifier):
        narrator.stat_change(turn.user.active, was, turn.user.active.modifier,
                             turn.user.active.applied_modifier, turn.ground)


# check if the move heals the user
def check_move_user_heal(turn, move, special_effect):
    narrator.say(f"{turn.user.active.name} heals {math.floor(turn.user.active.hp * special_effect)} HP.")
    turn.user.active.battle_stats[0] = min(turn.user.active.hp, turn.user.active.battle_stats[0] + math.floor(turn.user.active.hp * special_effect))


#: how far a decimal in the move table may sit below the fraction it means
#: before a floor() reads one short. See check_move_user_heal_by_weather.
FRACTION_SLACK = 1e-6


def check_move_roost(turn, move, special_effect):
    """Heal a third, rounded up, and land for the rest of the turn.

    `special_effect` is the fraction, so the table still says how much.
    Rounded **up**, unlike every other heal here, because that is what the
    move does in the series -- `math.ceil`, not `math.floor`.

    The typing half is the interesting part. A Flying type using Roost is on
    the ground until the end of the turn, which means:

      * a dual type loses Flying and keeps the other half
      * a pure Flying type is left with no type at all -- typeless, not
        Normal, so nothing is super effective or resisted against it
      * anything that was not Flying is untouched

    and something ungrounded *only* by being Flying is grounded meanwhile, so
    terrain and Ground moves reach it.

    The typing is put back by `end_of_turn`, from the copy taken here rather
    than from `default_type`: a move like Forest's Curse may have added a
    type this battle, and restoring the default would throw that away. Same
    reasoning as the switching code, which takes copies for the same reason.
    """
    user = turn.user.active
    healed = min(user.hp - user.battle_stats[0],
                 math.ceil(user.hp * special_effect))
    if healed > 0:
        user.battle_stats[0] += healed
        narrator.say(f"{user.name} settles and recovers {healed} HP.",
                     "heal", pokemon=user.name, amount=healed)
    else:
        narrator.say(f"{user.name} is already at full health.", "fail")

    if "Flying" not in (user.type or []):
        return                      # nothing to come down from
    user.roosting = list(user.type)
    user.type = [kind for kind in user.type if kind != "Flying"]
    if user.type:
        narrator.say(f"{user.name} touches down -- it is no longer Flying "
                     f"this turn.")
    else:
        narrator.say(f"{user.name} touches down -- it has no type this turn.")
    # ungrounded only by its wings, so it is standing on the field now
    user.volatile_status['Grounded'] = 1


def check_move_user_heal_by_weather(turn, move, special_effect):
    """A heal whose size depends on the sky. Synthesis, and its two siblings
    if they are ever added.

    `special_effect` is the fair-weather fraction -- a third for Synthesis.
    Harsh sun doubles it and any other weather halves it, which is exactly
    the 1/3, 2/3, 1/6 the real games use, without three numbers in the cell.
    """
    weather = turn.ground.weather_effect
    scale = 2 if weather == "Sunny" else 1 if weather == "Clear" else 0.5
    fraction = special_effect * scale
    # FRACTION_SLACK, because the cell holds a *decimal approximation* of a
    # fraction -- 0.333333333 for a third -- and flooring that is always one
    # short on exactly the numbers that matter: floor(180 * 0.333333333) is
    # 59, not 60. No number of extra digits fixes it either, since a float
    # third is below a true third. Nudging up by a millionth restores the
    # exact cases and changes nothing else: a third of 100 still floors to
    # 33, and a sixth of 50 still floors to 8.
    mended = min(turn.user.active.hp - turn.user.active.battle_stats[0],
                 math.floor(turn.user.active.hp * fraction + FRACTION_SLACK))
    turn.user.active.battle_stats[0] += max(0, mended)
    narrator.say(f"{turn.user.active.name} draws {max(0, mended)} HP from "
                 f"the light.", "heal", pokemon=turn.user.active.name,
                 amount=max(0, mended))


# check if the move heals the status of the team
def check_move_heal_team_status(turn, move, special_effect):
    # Fainted is held in the same field as poison and sleep, so clearing "the
    # team's status" was reviving the dead: a fainted team-mate came back as
    # Normal on 0 HP, which let it be sent out again and stopped
    # check_win_or_lose -- which asks whether *every* Pokemon is Fainted --
    # from ever seeing a wipe.
    for pokemon in turn.user.team:
        if pokemon.status != "Fainted":
            pokemon.status = "Normal"
    narrator.say(f"{turn.user.active.name}'s team's status condition has been healed!", "heal")


# check if the move drains hp
def check_move_ohko(turn, move, special_effect):
    """A one-hit knockout that usually does nothing -- Guillotine.

    `special_effect` is the chance of it landing. The move carries power 0, so
    the damage formula contributes nothing either way; landing it empties the
    turn.foe.active's HP and check_fainted() does the rest on its usual pass, which
    keeps the faint going through the same path as any other.
    """
    if turn.foe.active.status == "Fainted":
        return
    if random.random() > special_effect:
        narrator.failed()
        return
    narrator.say(f"It is a one-hit knockout!")
    turn.foe.active.battle_stats[0] = 0


def check_move_hp_draining(turn, move, special_effect):
    narrator.say(f"{turn.user.active.name} drains {math.floor((move.damage + min(turn.foe.active.battle_stats[0], 0)) * special_effect)} HP.")
    turn.user.active.battle_stats[0] += min(turn.user.active.hp - turn.user.active.battle_stats[0], math.floor((move.damage + min(turn.foe.active.battle_stats[0], 0)) * special_effect))


# protective move
def check_move_user_protection(turn, move, special_effect):
    protective_move_list = {"Protect": 1, "King's Shield": 2, "Baneful Bunker": 3}
    if random.random() <= (1 / pow(2, turn.user.active.protection[1])):
        turn.user.active.protection[0] = protective_move_list[move.name]
        turn.user.active.protection[1] += 1
    else:
        narrator.failed()


# check if the move buff the whole team
def check_move_user_team_buff(turn, move, special_effect):
    team_buff = special_effect
    if team_buff == "Aurora Veil" and turn.ground.weather_effect != 'Hail':  # hail
        narrator.say(f"Not hailing. {team_buff} failed.")
    else:
        if turn.user.trainer.in_battle_effects[team_buff] > 0:
            narrator.say(f"{team_buff} is already there.")
        else:
            narrator.say(f"{team_buff} is set up.")
            turn.user.trainer.in_battle_effects[team_buff] = TEAM_BUFF_TURNS


# check if the move affects the weather
def check_move_battleground_weather_effect(turn, move, special_effect):
    # weather effect
    if turn.ground.weather_effect != special_effect:
        turn.ground.weather_effect = special_effect
        turn.ground.artificial_weather = True
        narrator.say(weather_desc[turn.ground.weather_effect], "weather")


def check_move_terrain(turn, move, special_effect):
    """Lay a terrain. `special_effect` names which one.

    Setting the terrain that is already down fails, as it does in the real
    games, rather than silently refreshing its five turns.
    """
    said = terrain.set_terrain(turn.ground, special_effect)
    if said:
        narrator.say(said, "field", terrain=special_effect)
    else:
        narrator.failed()


def check_move_battleground_field_effect(turn, move, special_effect):
    # field effect
    turn.ground.field_effect[special_effect] = 0 if turn.ground.field_effect[special_effect] > 0 else FIELD_EFFECT_TURNS


# check if the move applies entry hazard
def check_move_entry_hazard_effect(turn, move, special_effect):
    maximum_usage = {"Stealth Rock": 1, "Spikes": 3, "Toxic Spikes": 2, "Sticky Web": 1}  # maximum number of entry hazards that can be placed
    # entry hazard
    if turn.foe.trainer.entry_hazard[special_effect] < maximum_usage[special_effect]:
        narrator.say(f"{special_effect} has been set up.")
        turn.foe.trainer.entry_hazard[special_effect] += 1
    else:
        narrator.say("The entry hazard has already been placed!")


# clear entry hazard
def check_move_clear_entry_hazard(turn, move, special_effect):
    if move.name == "Rapid Spin":
        turn.user.team[0].volatile_status['Binding'] = 0
        turn.user.trainer.entry_hazard = dict.fromkeys(turn.user.trainer.entry_hazard.keys(), 0)
    elif move.name == "Defog":
        turn.user.trainer.entry_hazard = dict.fromkeys(turn.user.trainer.entry_hazard.keys(), 0)
        turn.foe.trainer.entry_hazard = dict.fromkeys(turn.foe.trainer.entry_hazard.keys(), 0)
        turn.foe.trainer.in_battle_effects = dict.fromkeys(turn.foe.trainer.in_battle_effects.keys(), 0)


# switched out own pokemon when using this move
def check_move_self_switching_effect(turn, move, special_effect):
    number_of_pokemon = sum(1 for pokemon in turn.user.team if pokemon.status != "Fainted")
    if number_of_pokemon > 1:
        if turn.user.trainer.main:  # protagonist side
            if not turn.ground.auto_battle:
                if move.name == "Baton Pass":
                    turn.user.team[0] = switching_criteria(turn.user.trainer, turn.foe.trainer, turn.user.team, turn.foe.team, turn.ground, True, True)
                else:
                    turn.user.team[0] = switching_criteria(turn.user.trainer, turn.foe.trainer, turn.user.team, turn.foe.team, turn.ground, True)
            else:
                turn.user.team[0] = switching_mechanism(turn.user.trainer, turn.foe.trainer, turn.ground, turn.user.team, turn.foe.team,
                                                   ai_switching_mechanism(turn.foe.trainer, turn.user.trainer, turn.ground, True, True), False)
        else:
            turn.user.team[0] = switching_mechanism(turn.user.trainer, turn.foe.trainer, turn.ground, turn.user.team, turn.foe.team,
                                               ai_switching_mechanism(turn.foe.trainer, turn.user.trainer, turn.ground, True, True), False)


# exclusive for move curse only
def check_move_cursing(turn, move, special_effect):
    if "Ghost" in turn.user.active.type:
        if turn.foe.active.volatile_status['Curse'] != 0:
            narrator.say("The opponent is already cursed!")
        else:
            turn.user.active.battle_stats[0] -= turn.user.active.hp // 2
            turn.foe.active.volatile_status['Curse'] = 1
    else:
        # increase/decrease stats on the user
        turn.user.active.applied_modifier = special_effect
        turn.user.active.modifier = list(map(operator.add, turn.user.active.applied_modifier, turn.user.active.modifier))
        narrator.say(turn.user.active.modifier)


def check_move_hp_split(turn, move, special_effect):
    if special_effect == "Split":
        splited_hp = (turn.user.active.battle_stats[0] + turn.foe.active.battle_stats[0]) // 2
        turn.user.active.battle_stats[0], turn.foe.active.battle_stats[0] = min(turn.user.active.hp, splited_hp), min(turn.foe.active.hp, splited_hp)
    elif special_effect == "Same":
        turn.foe.active.battle_stats[0] = min(turn.user.active.battle_stats[0], turn.foe.active.battle_stats[0])


def check_move_disable(turn, move, special_effect):
    if special_effect == "Disable":
        with suppress(ValueError, AttributeError):
            try:
                if turn.foe.active.disabled_moves[turn.foe.active.previous_move.name] != 0 and turn.foe.active.previous_move.name != "Switching":
                    narrator.say("The move is already disabled!", "fail")
            except KeyError:
                turn.foe.active.disabled_moves[turn.foe.active.previous_move.name] = 5
    elif special_effect == "Taunt":
        for i in range(len(turn.foe.active.moveset)):
            move = list_of_moves[turn.foe.active.moveset[i]]
            if move.attack_type == "Status" and move.name != "Switching":
                try:
                    if turn.foe.active.disabled_moves[move.name] != 0:
                        narrator.say("The move is already disabled!", "fail")
                except KeyError:
                    turn.foe.active.disabled_moves[move.name] = 5
    elif special_effect == "Encore":
        for i in range(len(turn.foe.active.moveset)):
            move = list_of_moves[turn.foe.active.moveset[i]]
            try:
                if move.name != "Switching" and move.name != turn.foe.active.previous_move.name and turn.foe.active.previous_move.name != "Switching":
                    try:
                        if turn.foe.active.disabled_moves[move.name] != 0:
                            narrator.say("The move is already disabled!", "fail")
                    except KeyError:
                        turn.foe.active.disabled_moves[move.name] = 4
            except AttributeError:
                narrator.failed()
    elif special_effect == "Sound":
        for i in range(len(turn.foe.active.moveset)):
            move = list_of_moves[turn.foe.active.moveset[i]]
            if 'f' in move.flags:
                try:
                    if turn.foe.active.disabled_moves[move.name] != 0 and turn.foe.active.previous_move.name != "Switching":
                        narrator.say("The move is already disabled!", "fail")
                except KeyError:
                    turn.foe.active.disabled_moves[move.name] = 2


def check_move_reset_target_modifier(turn, move, special_effect):
    turn.foe.active.modifier = [0] * 9
    narrator.say(f"{turn.foe.active.name}'s stat change has been reset!")


def check_move_reset_user_modifier(turn, move, special_effect):
    turn.user.active.modifier = [0] * 9
    narrator.say(f"{turn.user.active.name}'s stat change has been reset!")


def check_move_swap_barrier(turn, move, special_effect):
    turn.user.trainer.in_battle_effects, turn.foe.trainer.in_battle_effects = turn.foe.trainer.in_battle_effects, turn.user.trainer.in_battle_effects
    turn.user.trainer.entry_hazard, turn.foe.trainer.entry_hazard = turn.foe.trainer.entry_hazard, turn.user.trainer.entry_hazard
    narrator.say("Entry hazard and in-game barriers have been swapped!")


def check_move_add_target_type(turn, move, special_effect):
    for typing in special_effect:
        if typing not in turn.foe.active.type:
            # a new list, not `+=`: switching_mechanism aliases `type` to
            # `default_type`, and editing in place rewrote the typing the
            # Pokemon is supposed to revert to
            turn.foe.active.type = turn.foe.active.type + [typing]
            narrator.say(f"{turn.foe.active.name} has been added {typing} type.")


def check_move_countering(turn, move, special_effect):
    type_effectiveness = 0 if math.prod([typeChart[move.type][turn.foe.active.type[x]] for x in range(len(turn.foe.active.type))]) == 0 else 1
    # "does it have a move's attributes", not "is it not a string". The old
    # test let None through -- which is what a Pokemon carried into its next
    # battle -- and reading .damage off None raised on the first turn.
    if hasattr(turn.foe.active.previous_move, "attack_type"):
        turn.foe.active.previous_move.damage = getattr(turn.foe.active.previous_move, 'damage', 0)
        if move.name == "Counter" and turn.foe.active.previous_move.attack_type == "Physical":
            narrator.say(f"{turn.foe.active.name} has been counter-attacked, suffering {turn.foe.active.previous_move.damage * 2 * type_effectiveness} damage.")
            turn.foe.active.battle_stats[0] -= turn.foe.active.previous_move.damage * 2 * type_effectiveness
        elif move.name == "Mirror Coat" and turn.foe.active.previous_move.attack_type == "Special":
            narrator.say(f"{turn.foe.active.name} has been counter-attacked, suffering {turn.foe.active.previous_move.damage * 2 * type_effectiveness} damage.")
            turn.foe.active.battle_stats[0] -= turn.foe.active.previous_move.damage * 2 * type_effectiveness
        elif move.name == "Metal Burst":
            narrator.say(f"{turn.foe.active.name} has been counter-attacked, suffering {turn.foe.active.previous_move.damage * 1.5 * type_effectiveness} damage.")
            turn.foe.active.battle_stats[0] -= turn.foe.active.previous_move.damage * 1.5 * type_effectiveness
