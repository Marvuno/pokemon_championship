import random
import math
import os
from contextlib import suppress
from copy import deepcopy

from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Data.pokemon import *
from Scripts.Data.abilities import *
from Scripts.Data.character_abilities import *
from Scripts.Data.battlefield import *
from Scripts.Data.moves import *
from Scripts.Data.competitors import *
from Scripts.Battle.volatile_status_condition import *
from Scripts.Battle.damage_calculation import *
from Scripts.Battle.move_additional_effect import *
from Scripts.Battle.constants import *
from Scripts.Battle.context import Side, Turn
from Scripts.Battle.ai import *
from Scripts.Battle.switching import *
from Scripts.Battle.battle_move_execution import *
from Scripts.Battle.battle_win_condition import *
from Scripts.Battle.battle_initialization import *
from Scripts.Battle.weather import *
from Scripts.Art import narrator
from Scripts.Battle import terrain


def hp_bar_display(pokemon):
    health_bar = 20
    percent = int(pokemon.battle_stats[0] / pokemon.hp * 100)
    current_health_bar = int(pokemon.battle_stats[0] / pokemon.hp * health_bar)
    return f"\n|{'█' * current_health_bar}{' ' * (health_bar - current_health_bar)}| {percent}%"


def speed_adjustment(user_side, user, battleground):
    # check if paralysis exists to slow pokemon
    def check_paralysis(pokemon):
        if pokemon.status == "Paralysis":
            return pokemon.battle_stats[5] // 2
        return pokemon.battle_stats[5]

    user.battle_stats[5] = check_paralysis(user)
    user.battle_stats[5] *= 2 if user_side.in_battle_effects['Tailwind'] > 0 else 1
    user.battle_stats[5] *= -1 if battleground.field_effect["Trick Room"] > 0 else 1
    return user.battle_stats[5]


def select_move(pokemon, target, battleground):
    # comprehensive type effectiveness indicator
    move_effectiveness = []
    for move in pokemon.moveset:
        move = list_of_moves[move]
        if move.attack_type == "Status":
            move_effectiveness.append('Status')
            continue

        initial_type_effectiveness = [2 if target.type[x] in move.ignoreType else typeChart[move.type][target.type[x]] for x in range(len(target.type))]
        extra_type_effectiveness = [typeChart[move.multiType[y]][target.type[x]] for x in range(len(target.type)) for y in range(len(move.multiType))]

        # special condition to override type chart (e.g. mold breaker, lock-on, grounded etc)
        if target.volatile_status['Grounded'] == 1 and move.type == "Ground":
            initial_type_effectiveness = [1 if effective == 0 else effective for effective in initial_type_effectiveness]
            extra_type_effectiveness = [1 if effective == 0 else effective for effective in extra_type_effectiveness]

        for type in move.ignoreImmunity:
            if type in target.type:
                initial_type_effectiveness = [1 if effective == 0 else effective for effective in initial_type_effectiveness]
                extra_type_effectiveness = [1 if effective == 0 else effective for effective in extra_type_effectiveness]

        interchange_type_effectiveness = max(0, math.prod(initial_type_effectiveness))
        for y in range(len(move.interchangeType)):
            new_type_effectiveness = math.prod([typeChart[move.interchangeType[y]][target.type[x]] for x in range(len(target.type))])
            if new_type_effectiveness > interchange_type_effectiveness:
                interchange_type_effectiveness = new_type_effectiveness
                move.type = move.interchangeType[y]

        type_effectiveness = interchange_type_effectiveness if len(move.interchangeType) > 0 else math.prod(initial_type_effectiveness) * math.prod(
            extra_type_effectiveness)
        move_effectiveness.append(type_effectiveness)

    pokemon_move = None
    # charging move
    if pokemon.charging[0] != "":
        pokemon_move = pokemon.charging[0]
        input(f"{CVIOLET2}{CBOLD}{pokemon.name} continues using {pokemon_move}. Enter any key to proceed.{CEND}")

    # very clumsily indicate move type and effect for noobs
    print(CBOLD, end='')
    for index, move in enumerate(pokemon.moveset):
        if move == "Switching":
            narrator.say(f"{index}: {move}")
        else:
            try:
                # `>= 2`, matching damage_calculation.py -- "super effective"
                # means the type chart really doubled it, not merely that it
                # came out above 1x.
                narrator.say(f"{index}: {move} ({list_of_moves[move].type}) "
                      f"[{'No Effect' if move_effectiveness[index] == 0 else 'Super Effective' if move_effectiveness[index] >= 2 else 'Not Effective' if move_effectiveness[index] < 1 else ''}]", "fail")
            except TypeError:
                narrator.say(f"{index}: {move} ({list_of_moves[move].type}) [Status]")
    narrator.say("100: Turn on/off Auto Battle")
    print(CEND, end='')

    while pokemon_move not in pokemon.moveset:  # avoid making a non-move option
        with suppress(ValueError, IndexError):
            while True:
                move_choice = int(input(f"What is the move for {pokemon.name}?\n--> "))

                if move_choice == 100:
                    battleground.auto_battle = True if not battleground.auto_battle else False
                    print(f"Auto battle is", end=' ')
                    narrator.say('activated.\nNote: You still have to make a move on this turn. You will NOT be able to switch it off until the end of this battle.' if battleground.auto_battle else 'deactivated.')
                try:
                    if pokemon.disabled_moves[pokemon.moveset[move_choice]] <= 0:
                        pokemon_move = pokemon.moveset[move_choice]
                        break
                    else:
                        narrator.say("The move is disabled.")
                except KeyError:
                    pokemon_move = pokemon.moveset[move_choice]
                    break

    narrator.say(list_of_moves[pokemon_move].name)
    sound(audio="Assets/music/confirm.mp3")
    return list_of_moves[pokemon_move]


# the whole move execution order and procedure
def move_order_and_execution(turn, move, target_move):
    """One Pokemon takes its move.

    `turn` is oriented on whoever is acting; the ability calls below say
    turn.flip() where they used to reorder six arguments to mean "the other
    side". See Scripts/Battle/context.py.
    """
    user_side, target_side = turn.user.trainer, turn.foe.trainer
    user_team, target_team = turn.user.team, turn.foe.team
    user, target = turn.user.active, turn.foe.active
    battleground = turn.ground
    user_turn_in_battle_stats(user_side, user)
    # Type-changing abilities fire here, as this Pokemon takes its turn --
    # not before the turn for both sides at once. See on_move_used().
    on_move_used(user_side, target_side, user, target, battleground, move)
    # status condition
    user_health_condition = check_volatile_status(user, move)
    fail, immune = True, False
    #: the move reached the target even if it did no damage. Only
    #: the self-switching effect reads this -- see below.
    connected = False

    if not user_health_condition and move.name != "Switching":
        narrator.used(user_side.side_color, user.name, move.name)

        onWeatherCheck(battleground, move)
        # Psychic Terrain refuses a priority move aimed at anything standing
        # on it. Accuracy 0 is how Queenly Majesty and Dazzling already say
        # "this move does not reach", so terrain says it the same way.
        if terrain.blocks_priority(battleground, target, move):
            if battleground.reality:
                narrator.say("The strange field protects %s from priority "
                             "moves!" % target.name, "fail")
            move.accuracy = 0
        onParticularMoveChange(user, target, move)
        UseAbility(turn.flip(), move, abilityphase=3)
        UseCharacterAbility(turn.flip(), move, abilityphase=3)
        move.accuracy = move.accuracy * modifierChart[7][user.modifier[7]] * (1 / (modifierChart[6][0]) * move.evasion) if move.ignoreEvasion else \
            move.accuracy * modifierChart[7][user.modifier[7]] * (1 / (modifierChart[6][target.modifier[6]] * move.evasion))

        if not move_fail_checklist_before_execution(user, target, move, target_move):  # check if move fail before using
            if random.random() <= move.accuracy:  # accuracy check
                for _ in range(move.multi[1]):  # number of multi strikes
                    if not move_fail_checklist_during_execution(user, target, move, target_move):  # check if move fail to attack
                        move.damage = damage_calculation(turn, move)

                        # check if the charging move double counts the special effect
                        doublecount = onChargingMove(user, target, move)

                        # this order exclusive for ability Illusion
                        UseCharacterAbility(turn, move, abilityphase=4)
                        UseCharacterAbility(turn.flip(), move, abilityphase=5)
                        UseAbility(turn, move, abilityphase=4)
                        UseAbility(turn.flip(), move, abilityphase=5)

                        # no effect move and not a charging move
                        if move.damage <= 0 and move.attack_type != "Status" and move.charging not in ("Charging", "Semi-invulnerable"):
                            immune = True
                            # ...but "did no damage" and "never connected" are
                            # different things, and one effect cares about
                            # the difference. U-turn leaves the field because
                            # it *hit*, not because it hurt -- so an ability
                            # that reduces the damage to nothing (Illusion's
                            # halving on a weak hit, Silhouette's, an
                            # absorbing ability) stopped it switching out, and
                            # the player was left standing there. The type
                            # chart is what decides whether it connected at
                            # all: a real immunity is 0x.
                            if getattr(move, "type_effectiveness", 1):
                                connected = True

                        # trigger effects when using move
                        other_effect_when_use_move(user, target, battleground, move)
                        # damaging moves
                        move.damage = int(move.damage)
                        move.recoil = math.ceil(min(target.battle_stats[0], move.damage) * move.recoil)
                        target.battle_stats[0] -= move.damage
                        # recoil moves
                        user.battle_stats[0] -= move.recoil
                        # explosive / deduct HP moves
                        user.battle_stats[0] -= math.ceil(user.hp * move.deduct)

                        # Two lines, and the second one only when there is
                        # something to say. It used to be one f-string that
                        # always ended with "<user> took N recoil damage",
                        # printed on every damaging move -- so the overwhelming
                        # majority of attacks in the game, which have no recoil
                        # and no HP cost, announced "took 0 recoil damage"
                        # anyway. It reads as the attacker hurting itself, and
                        # it was reported as exactly that: a Hustle Durant
                        # "damaging itself" with Iron Head, whose HP had not
                        # moved at all.
                        self_cost = move.recoil + math.ceil(user.hp
                                                            * move.deduct)
                        narrator.say(f"{CBEIGE}{CBOLD}{move.damage} damage is "
                                     f"dealt to {target.name} with "
                                     f"{target.battle_stats[0]} HP left.{CEND}")
                        if self_cost > 0:
                            narrator.say(f"{CBEIGE}{CBOLD}{user.name} took "
                                         f"{self_cost} recoil damage.{CEND}")

                        # moves that directly cause fainted condition
                        if target.battle_stats[0] <= 0 and move.damage > 0:
                            fainting_blow_move_effect(user, target, move)

                        # check if any pokemon fainted
                        check_fainted(user, target)
                        # check if the turn can end here
                        if all(pokemon.status == "Fainted" or pokemon2.status == "Fainted" for pokemon, pokemon2 in zip(user_team, target_team)):
                            fail = False
                            break
                        # excluding no effect moves, trigger move additional effect
                        if not immune:
                            if not doublecount:
                                # The effect handlers take a context object
                                # now -- see Scripts/Battle/context.py. Built
                                # here rather than threaded down from the turn
                                # loop because this is as far as the context
                                # has reached; the layers above still pass the
                                # six arguments separately, and turn_of() is
                                # the shim that lets them be converted one at
                                # a time.
                                move_special_effect(turn, move)
                            # trigger ability when target is being hit
                            UseAbility(turn, move, abilityphase=6)
                            UseAbility(turn.flip(), move, abilityphase=7)
                            UseCharacterAbility(turn, move, abilityphase=6)
                            UseCharacterAbility(turn.flip(), move, abilityphase=7)
                            fail = False
                        elif connected and "switching" in str(
                                move.effect_type):
                            # It hit; it just did not hurt. U-turn and its kin
                            # still leave the field.
                            move_special_effect(turn, move)
                            fail = False
                            break
                        else:
                            # A move the target is immune to does not get to
                            # keep striking. Phase 5 is inside this loop --
                            # rightly, since Rough Skin and its kin answer
                            # every hit -- but the *absorbing* abilities are
                            # there too, and they heal a quarter of maximum
                            # HP each time they fire.
                            #
                            # Water Shuriken hits up to five times. Against
                            # Water Absorb that was five quarters: the move
                            # reported 0 damage, as it should, and refilled a
                            # nearly-fainted Pokemon to full. Volt Absorb and
                            # Dry Skin had the same arithmetic waiting.
                            #
                            # In the real games an absorbed move is negated
                            # outright -- one trigger, then nothing -- and a
                            # multi-hit move against an immune target stops
                            # rather than swinging four more times at
                            # somebody it cannot touch.
                            break
            # the move is dodged
            else:
                narrator.say(f"\nOpponent Pokemon avoided the attack!\n")

            # The move has been spent either way. Fired here rather than on
            # phase 7 so that it also answers a miss, and outside the
            # multi-strike loop so a five-hit move counts as one use. Only
            # character abilities are consulted: nothing in Data/abilities.py
            # registers this phase, and firing it for both would be a lookup
            # per move for no one.
            UseCharacterAbility(turn.flip(), move,
                                abilityphase=MOVE_SPENT_PHASE)

        if fail:
            move_fail_consequence_upon_execution(user, target, move)

    # Nothing is printed on the else branch any more. It used to say
    # "<target> is still <status>." -- about the *target*, when the branch is
    # reached because the *user* could not move, and on every switch as well.
    # Most of the time that read "Garchomp is still Normal.", which says
    # nothing at all; when there really is a reason (asleep, paralysed,
    # flinched, frozen) check_volatile_status has already said so properly.

    user.previous_move = move
    # Remember an attack that landed nothing against who is standing there.
    # The AI already docks a move its *estimate* says will do no damage, but an
    # estimate can be wrong -- an immunity or an ability that zeroes the damage
    # is only certain once it has been tried -- and without this the AI would
    # keep picking the same dud every turn. Keyed on the target so switching in
    # something else does not inherit the verdict.
    if move.name != "Switching" and move.attack_type != "Status":
        if getattr(move, "damage", 0) > 0:
            user.ineffective_moves.get(target.name, set()).discard(move.name)
        elif connected:
            # `connected`, not merely "dealt no damage" -- and this is the
            # whole of the fix. A move that *missed*, or that was thrown at
            # something half-way through Phantom Force or Fly, also reports
            # zero, and blacklisting on that taught the AI its attacks were
            # useless against a Pokemon it had simply failed to reach.
            #
            # Against a Phantom Force user that blacklisted every attacking
            # move in turn, leaving a status move as the only thing left to
            # pick: Armadragdon stood there casting Empyrean Glory with its
            # Defence already at +6, 148 times out of 170 in a measured
            # sample. `connected` is the type chart's own answer to "did this
            # reach at all", which is exactly the question being asked.
            user.ineffective_moves.setdefault(target.name, set()).add(move.name)
    user.modifier, target.modifier = check_modifier_limit(user), check_modifier_limit(target)
    narrator.say("")

    # -- a move that goes off twice --------------------------------------
    # Wizardry asks for a second move inside the one turn, drawn at random.
    # It sets `encore_move` on the Pokemon as its move resolves; this is the
    # only place that reads it, because this is the only place that knows a
    # move has finished.
    #
    # On the *Pokemon*, deliberately. It sat on the battleground, which both
    # sides share, so the extra move went to whoever finished a move next
    # rather than to whoever earned it -- and the AI's scoring, which runs
    # the real ability code, queued one without any move being played at
    # all. Neither is possible with the slot where it belongs.
    #
    # `encore_running` is not belt and braces. The repeat runs the same code
    # path, so the ability fires again on the way through and would queue
    # another -- a Pokemon with Wizardry would take its turn until the
    # recursion limit stopped it. One extra move per turn, and the flag is
    # cleared however the repeat ends.
    #
    # **Only once the move actually worked.** The ability sets its intent as
    # the move goes off, which is before anyone knows whether it landed, so
    # the decision is made here where the answer is known:
    #
    #   fail            the move missed, was refused, or hit an immunity
    #   name Switching  swapping out is not a move to follow up
    #   charging set    the Pokemon committed to Fly or Dig rather than
    #                   landing anything; it is eligible on the turn it
    #                   comes down, which is the turn the charge clears
    #
    # Without these the extra move fired on misses and on switches, and the
    # log read as a mess of moves nobody had chosen.
    encore = getattr(user, "encore_move", None)
    user.encore_move = None
    worked = (not fail and move.name != "Switching"
              and user.charging[0] == ""
              and user.status != "Fainted" and target.status != "Fainted")
    if (encore is not None and worked
            and not getattr(turn.ground, "encore_running", False)):
        narrator.say(f"{user.name} is not finished -- {encore.name} follows.",
                     "ability")
        turn.ground.encore_running = True
        try:
            move_order_and_execution(turn, encore, target_move)
        finally:
            turn.ground.encore_running = False


# reducing hp at the end of each turn
def hp_decreasing_modifier(pokemon, target, battleground):
    # ability is a list; "!= 'Magic Guard'" was always true, so Magic Guard
    # never stopped any of the chip damage below
    if not has_ability(pokemon, 'Magic Guard'):
        # status condition
        if pokemon.status == "Poison":  # regular poison
            narrator.say(f"The Poison has eroded {pokemon.name} {max(1, pokemon.hp // 8)} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 8)
        elif pokemon.status == "BadPoison":  # bad poison
            pokemon.volatile_status["NonVolatile"] += 1
            narrator.say(f"The Bad Poison has eroded {pokemon.name} {max(1, pokemon.hp * pokemon.volatile_status['NonVolatile'] // 16)} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp * pokemon.volatile_status['NonVolatile'] // 16)
        elif pokemon.status == "Burn":  # burn
            narrator.say(f"The Burn has burned away {pokemon.name} {max(1, pokemon.hp // 16)} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 16)
        # sudden death
        if battleground.sudden_death:
            narrator.say(f"The dark energy has eroded {pokemon.name} {max(1, pokemon.hp // 4)} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 4)

        # weather effect
        if battleground.weather_effect == 'Sandstorm':  # sandstorm
            if "Ground" not in pokemon.type and "Steel" not in pokemon.type and "Rock" not in pokemon.type:  # ground, rock, steel type immune
                # `any(ability not in ...)` was true unless the Pokemon held
                # *both* abilities, so a Sand Veil holder still took the chip.
                # Holding either one is what grants the immunity.
                if not has_ability(pokemon, "Sand Veil", "Sand Rush"):
                    narrator.say(f"The Sandstorm has hurt {pokemon.name} {pokemon.hp // 16} HP.")
                    pokemon.battle_stats[0] -= max(1, pokemon.hp // 16)
        elif battleground.weather_effect == 'Hail':  # hail
            if "Ice" not in pokemon.type:  # ice type immune
                if not has_ability(pokemon, "Snow Cloak"):
                    narrator.say(f"The Hail has hurt {pokemon.name} {pokemon.hp // 16} HP.")
                    pokemon.battle_stats[0] -= max(1, pokemon.hp // 16)

        # binding effect
        if pokemon.volatile_status['Binding'] >= 1:
            narrator.say(f"The binding has damaged {pokemon.name} {pokemon.hp // 8} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 8)
        # cursed
        if pokemon.volatile_status['Curse'] >= 1:
            narrator.say(f"The curse has damaged {pokemon.name} {pokemon.hp // 4} HP.")
            pokemon.battle_stats[0] -= max(1, pokemon.hp // 4)
        # leech seed
        # The number says which kind of seed it is, not how many turns are
        # left: 8 for the move, 16 for one Sylvan Sprout planted. See
        # SYLVAN_SEED in constants.py.
        seeded = pokemon.volatile_status['LeechSeed']
        if seeded > 0:
            share = SEED_SHARE.get(seeded, DEFAULT_SEED_SHARE)
            drained = max(1, pokemon.hp // share)
            kind = "Sylvan seed" if seeded == SYLVAN_SEED else "Leech seed"
            narrator.say(f"{kind} has drained {pokemon.name} {drained} HP.")
            pokemon.battle_stats[0] -= drained
        theirs = target.volatile_status['LeechSeed']
        if theirs > 0:
            share = SEED_SHARE.get(theirs, DEFAULT_SEED_SHARE)
            pokemon.battle_stats[0] += max(1, min(target.hp // share, pokemon.hp - pokemon.battle_stats[0]))
        # ingrain
        if pokemon.volatile_status['Ingrain'] > 0:
            narrator.say(f"Ingrain roots has regenerated {pokemon.name} {min(pokemon.hp // 16, pokemon.hp - pokemon.battle_stats[0])} HP.")
            pokemon.battle_stats[0] += max(1, min(pokemon.hp // 16, pokemon.hp - pokemon.battle_stats[0]))
        # aqua ring
        if pokemon.volatile_status['AquaRing'] > 0:
            narrator.say(f"Aqua ring has regenerated {pokemon.name} {min(pokemon.hp // 16, pokemon.hp - pokemon.battle_stats[0])} HP.")
            pokemon.battle_stats[0] += max(1, min(pokemon.hp // 16, pokemon.hp - pokemon.battle_stats[0]))

    return pokemon.battle_stats[0]


# check if weather effect stops
def check_weather_persist(battleground):
    if battleground.artificial_weather:
        if battleground.weather_turn == WEATHER_EFFECT_TURNS:
            battleground.artificial_weather = False
            battleground.weather_turn = 0
            if battleground.weather_effect != battleground.starting_weather_effect:
                narrator.say(weather_del[battleground.weather_effect], "weather")
                narrator.say(weather_desc[battleground.starting_weather_effect], "weather")
            return battleground.starting_weather_effect
        battleground.weather_turn += 1
    return battleground.weather_effect


def switch_fainted_pokemon_at_end_of_turn(user, opponent, user_team, opponent_team, battleground):
    if user_team[0].status == "Fainted" and battleground.battle_continuation:  # fainted
        if user.main:  # human
            user_team[0] = switching_criteria(user, opponent, user_team, opponent_team, battleground) if not battleground.auto_battle else \
                switching_mechanism(user, opponent, battleground, user_team, opponent_team, ai_switching_mechanism(opponent, user, battleground), False)
        else:  # ai
            user_team[0] = switching_mechanism(user, opponent, battleground, user_team, opponent_team,
                           ai_switching_mechanism(opponent, user, battleground), False)
    return user_team[0]