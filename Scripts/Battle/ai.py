import random
from contextlib import suppress
from copy import deepcopy

from Scripts.Battle import ai_scorer
from Scripts.Battle import ai_turns
from Scripts.Battle.fastcopy import fast_copy
from Scripts.Battle.context import Side, Turn

from Scripts.Art.text_color import *
from Scripts.Data.pokemon import *
from Scripts.Data.abilities import *
from Scripts.Data.character_abilities import *
from Scripts.Data.battlefield import *
from Scripts.Data.moves import *
from Scripts.Data.competitors import *
from Scripts.Battle.entry_hazard import *
from Scripts.Battle.type_chart import *
from Scripts.Battle.constants import *
from Scripts.Battle.battle_move_execution import *
# The AI must estimate damage with the same rules the engine applies, so
# these three come from the engine instead of being copied here. They were
# byte-identical duplicates, which meant correcting a formula in
# damage_calculation.py silently left the AI deciding by the old one. The
# five helpers still defined inside estimated_damage_calculation genuinely
# differ: an estimate has to be silent and deterministic where the real
# calculation rolls dice and narrates.
from Scripts.Battle.damage_calculation import (check_attack_power,
                                               check_defense_strength,
                                               check_if_weather_affect_moves)
from Scripts.Battle.battle_win_condition import check_win_or_lose
from Scripts.Art import narrator
from Scripts.Battle import terrain


#: What one positive stat stage on the active Pokemon adds to the case for
#: staying in, as a fraction of what that Pokemon is already worth in the
#: matchup. Switching resets the stages, so leaving throws them away -- and
#: the switch arithmetic priced them at nothing, which is why the AI would
#: buff on one turn and switch on the next.
STAGE_FORFEIT = 0.15


#: The move scorer the game shipped with lives in Scripts/Battle/ai_scorer.py
#: now. It is no longer the brain -- `smart_ai_select_move` below hands every
#: turn to the turn-currency AI unless a trainer opts out -- and it was moved
#: so that reading this file tells you what actually plays.
#:
#: These four names are re-exported because three suites and the ranking
#: experiment reach them through this module. Everything else the scorer needs
#: went with it.
PRIORITY_FIRST = ai_scorer.PRIORITY_FIRST
BLENDED = ai_scorer.BLENDED
DEFAULT_RANKING = ai_scorer.DEFAULT_RANKING
move_ranking = ai_scorer.move_ranking
move_score_finalization = ai_scorer.move_score_finalization
intelligent_move_selection = ai_scorer.intelligent_move_selection


def estimated_speed_adjustment(user_side, user, battleground):
    # check if paralysis exists to slow pokemon
    def check_paralysis(pokemon, speed):
        if pokemon.status == "Paralysis":
            return speed // 2
        return speed

    ability_impact_speed = {'Sunny': 'Chlorophyll', 'Rain': 'Swift Swim', 'Hail': 'Slush Rush'}
    # the speed stat, not a copy of it: battle_stats[5] is an int, and
    # ints are immutable -- deepcopy returned the same object every
    # time, about 4,000 times a battle, for nothing.
    speed = user.battle_stats[5]
    with suppress(KeyError):
        speed *= 2 if ability_impact_speed[battleground.weather_effect] in user.ability else 1
    speed = check_paralysis(user, speed)
    speed *= 2 if user_side.in_battle_effects['Tailwind'] > 0 else 1
    speed *= -1 if battleground.field_effect["Trick Room"] > 0 else 1
    return speed


def estimated_damage_calculation(user_side, target_side, user, target, battleground, move):
    def check_estimated_power_modifier(user_side, target_side, user, target, move):
        power = move.power
        user_speed, target_speed = estimated_speed_adjustment(user_side, user, battleground), estimated_speed_adjustment(target_side, target, battleground)
        # 5-strike move
        if move.multi[0] == 1:
            power = power * (2 * 0.35 + 3 * 0.35 + 4 * 0.15 + 5 * 0.15)
        # 3-strike double power move
        elif move.multi[0] == 2:
            power = power * (0 * (1 - move.accuracy) + 1 * (1 - move.accuracy) * move.accuracy + 3 * (1 - move.accuracy) * (
                    move.accuracy ** 2) + 6 * move.accuracy ** 3)

        if "after_hand" in move.effect_type:
            # this means target should move first to double power
            if target_speed > user_speed:
                power *= 2
        elif "before_hand" in move.effect_type:
            # this means user should move first to double power
            if user_speed > target_speed:
                power *= 2
        elif "modifier_dependent" in move.effect_type:
            positive_modifier = sum([i if i > 0 else 0 for i in user.modifier])
            power += positive_modifier * 20
        # activate flash fire
        if "Fire" in move.type and user.volatile_status['FlashFire'] > 0:
            power *= 1.5
        # custom retaliate move
        # the more pokemon fainted the stronger -- kept in step with
        # check_power_modifier in damage_calculation.py, which is the whole
        # point of this estimate: an AI scoring a move by a formula the
        # engine no longer uses is deciding by a game that isn't running.
        if "retaliation" in move.effect_type:
            power *= max(1, sum(1 for pokemon in user_side.team
                                if pokemon.status == "Fainted"))
        return power

    # determine crit
    def check_estimated_crit(user, move):
        return 1 + 0.5 * modifierChart[8][min(user.modifier[8] + move.critRatio, 3)]

    # determine STAB
    def check_estimated_STAB(user, move):
        if move.type in user.type:
            return 1.5
        return 1

    # determine type effectiveness
    def check_estimated_type_effectiveness(target_side, target, move):
        initial_type_effectiveness = [2 if target.type[x] in move.ignoreType else typeChart[move.type][target.type[x]] for x in range(len(target.type))]
        extra_type_effectiveness = [typeChart[move.multiType[y]][target.type[x]] for x in range(len(target.type)) for y in range(len(move.multiType))]

        # special condition to override type chart (e.g. mold breaker, lock-on, grounded etc)
        # A move that names a type in `ignoreType` is saying it reaches
        # that type anyway, and the line above already gave it 2x for
        # doing so. This blanket rule then appended a 0 for anything
        # ungrounded, and prod([2, 0]) is 0 -- so Bodhisattva, a Ground
        # move written specifically to hit Flying types hard, did nothing
        # to them at all. The override is for ordinary Ground moves.
        _reaches_anyway = any(t in move.ignoreType
                              for t in target.type)
        if move.type == "Ground" and not _reaches_anyway:
            # grounded
            if target.volatile_status['Grounded'] >= 1:
                initial_type_effectiveness = [1 if effective == 0 else effective for effective in initial_type_effectiveness]
                extra_type_effectiveness = [1 if effective == 0 else effective for effective in extra_type_effectiveness]
            # ungrounded
            elif target.volatile_status['Grounded'] == 0 or "Flying" in target.type:
                initial_type_effectiveness += [0]
                extra_type_effectiveness += [0]

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

        # wonder guard
        move.super_effective = True if type_effectiveness >= 2 else False
        # tinted lens
        move.not_effective = True if type_effectiveness <= 0.5 else False
        return type_effectiveness

    def check_estimated_other_factor(user_side, target_side, user, target, move):
        other = 1
        # reflect, light screen & aurora veil does not stack
        if not move.ignoreBarrier:
            if move.attack_type == "Physical":
                if target_side.in_battle_effects['Reflect'] > 0 or target_side.in_battle_effects['Aurora Veil'] > 0:
                    other *= 0.5
            elif move.attack_type == "Special":
                if target_side.in_battle_effects['Light Screen'] > 0 or target_side.in_battle_effects['Aurora Veil'] > 0:
                    other *= 0.5

        # charging move
        if move.charging == "Charging":
            other *= 0.5
        return other

    # damage calculation
    if move.attack_type == "Status":
        return 0

    attack = check_attack_power(user, target, move)
    defense = check_defense_strength(user, target, move)
    critical = check_estimated_crit(user, move)
    STAB = check_estimated_STAB(user, move)
    rand_factor = 0.9  # random
    type_effectiveness = check_estimated_type_effectiveness(target_side, target, move)
    weather = check_if_weather_affect_moves(battleground, move)
    # the same terrain factor the real formula uses -- an AI scoring moves by
    # different rules than the engine resolves them by is the trap
    # CLAUDE.md records for the three damage helpers
    ground = terrain.move_multiplier(battleground, user, target, move)
    other = check_estimated_other_factor(user_side, target_side, user, target, move)
    power = check_estimated_power_modifier(user_side, target_side, user, target, move)

    damage = math.floor((((((2 * 100 / 5) + 2) * power * attack / defense) / 50) + 2) * weather * ground * critical * (
            rand_factor * STAB * type_effectiveness * other * move.abilitymodifier))

    return damage


def auto_ai_select_move(battleground, protagonist, ai):
    """
    This AI is very stupid. It is only used for players who prefer auto-battle.
    Hence, it exhibits normal human behavior - not being able to know the moves and other stuff of the opponent Pokemon.
    Its behavior is as follows:
    - never switch
    - only use highest-attack move by its own standard (power * type effectivenvess)
    - if there is no such move, use random move
    - it considers first-turn only moves only and nothing else
    """
    protagonist_pokemon, ai_pokemon = fast_copy(protagonist.team[0]), fast_copy(ai.team[0])
    move_damage = [0] * len(ai_pokemon.moveset)

    if ai_pokemon.charging[0] != "":
        return list_of_moves[ai_pokemon.charging[0]]

    for index, move in enumerate(ai_pokemon.moveset):
        move = fast_copy(list_of_moves[move])
        # even worse calculation
        move.damage = move.power * math.prod([2 if protagonist_pokemon.type[x] in move.ignoreType else \
        typeChart[move.type][protagonist_pokemon.type[x]] for x in range(len(protagonist_pokemon.type))])
        # move.damage = estimated_damage_calculation(ai, protagonist, ai_pokemon, protagonist_pokemon, battleground, move)
        move_damage[index] = move.damage

        # failed moves
        with suppress(KeyError):
            if ai_pokemon.disabled_moves[move.name] > 0:
                move_damage[index] = NEG_INF
        if 'j' in move.flags and ai_pokemon.volatile_status["Turn"] > 2:
            move_damage[index] = NEG_INF

    # # debug
    # print("")
    # for index, move in enumerate(ai_pokemon.moveset):
    #     print(f"{list_of_moves[move].name} || Damage: {move_damage[index]}")
    # print("")

    return list_of_moves[ai_pokemon.moveset[move_damage.index(max(move_damage))]] if move_damage.index(max(move_damage)) != 0 \
        else list_of_moves[ai_pokemon.moveset[random.randint(1, len(ai_pokemon.moveset) - 1)]]


def dumb_ai_select_move(battleground, protagonist, ai):
    """
    This AI is moderate. It is only used for low-level AI.
    Its behavior is as follows:
    - it knows all the moves of the opponent Pokemon
    - switches only if player Pokemon has x4 effective move
    - only use highest-attack move
    - if there is no such move, use random move
    - it considers some factors, including more abilities, first-turn only moves, weather and special moves
    """
    # low-level ai behavior
    # it will only consider the move with highest dmg against player
    # it never uses status moves
    # it switches if player pokemon has *4 effective move
    protagonist_pokemon, ai_pokemon = fast_copy(protagonist.team[0]), fast_copy(ai.team[0])

    if ai_pokemon.charging[0] != "":
        return list_of_moves[ai_pokemon.charging[0]]

    move_damage, protagonist_move_damage, incoming_move = [0] * len(ai_pokemon.moveset), 0, list_of_moves[protagonist_pokemon.moveset[1]]
    for move in protagonist_pokemon.moveset:
        move = list_of_moves[move]
        damage = estimated_damage_calculation(protagonist, ai, protagonist_pokemon, ai_pokemon, battleground, move)
        protagonist_move_damage = max(damage, protagonist_move_damage)
        if damage == protagonist_move_damage:
            incoming_move = move

    for index, move in enumerate(ai_pokemon.moveset):
        move = fast_copy(list_of_moves[move])

        scoring = Turn(battleground,
                       Side(ai, getattr(ai, 'team', []), ai_pokemon),
                       Side(protagonist, getattr(protagonist, 'team', []),
                            protagonist_pokemon))
        UseAbility(scoring, move, abilityphase=2)
        UseAbility(scoring.flip(), move, abilityphase=3)
        UseCharacterAbility(scoring, move, abilityphase=2)
        UseCharacterAbility(scoring.flip(), move, abilityphase=3)
        onWeatherCheck(battleground, move)
        onParticularMoveChange(ai_pokemon, protagonist_pokemon, move)

        move.damage = estimated_damage_calculation(ai, protagonist, ai_pokemon, protagonist_pokemon, battleground, move)

        UseCharacterAbility(scoring, move, abilityphase=4)
        UseCharacterAbility(scoring.flip(), move, abilityphase=5)
        UseAbility(scoring, move, abilityphase=4)
        UseAbility(scoring.flip(), move, abilityphase=5)

        move_damage[index] = move.damage

        # failed moves
        with suppress(KeyError):
            if ai_pokemon.disabled_moves[move.name] > 0:
                move_damage[index] = NEG_INF
        if 'j' in move.flags and ai_pokemon.volatile_status["Turn"] > 2:
            move_damage[index] = NEG_INF

    # # debug
    # print("")
    # for index, move in enumerate(ai_pokemon.moveset):
    #     print(f"{list_of_moves[move].name} || Damage: {move_damage[index]}")
    # print("")

    if math.prod([typeChart[incoming_move.type][ai_pokemon.type[x]] for x in range(len(ai_pokemon.type))]) == 4 or max(move_damage) == 0:
        ai.position_change = ai_switching_mechanism(protagonist, ai, battleground, True)
        # if confirmed switched, then use Switching
        if ai.position_change != 0:
            return list_of_moves[ai.team[0].moveset[0]]  # switching
        else:
            if move_damage.index(max(move_damage)) != 0:
                return list_of_moves[ai_pokemon.moveset[move_damage.index(max(move_damage))]]
            else:
                return list_of_moves[ai_pokemon.moveset[random.randint(1, len(ai_pokemon.moveset) - 1)]]
    return list_of_moves[ai_pokemon.moveset[move_damage.index(max(move_damage))]]


def smart_ai_select_move(battleground, protagonist, ai):
    """Pick a move for a trainer who is playing properly. Returns a Move.

    This is the engine's one entry point for a thinking opponent, and it is
    now a dispatcher rather than a brain. Two brains sit behind it:

        ai_turns.py     the turn-currency AI, and the default. Scores every
                        move in a single unit -- turns in the race -- instead
                        of adding damage points to effect points to priority
                        points with a hand-chosen conversion factor per pair
        ai_scorer.py    the scorer the game shipped with, archived there. Still
                        reachable, per trainer:  competitor.brain = "scorer"

    They measure level on strength -- the turn AI is +0.5 against the scorer
    over 840 battles a side, inside a +/-2.4 noise band -- and apart on
    behaviour: it picks the best expected-value attack 92.1% of the time
    against 88.9%, it never passes up a certain kill, and it does not throw
    Fly at something twenty-one times running. What it is really here for is
    that the knowledge model hangs off it -- Scripts/Battle/ai_knowledge.py --
    which is worth 7.7 points from Low to Champion, twice the whole gap
    between this AI and the dumb one.

    The estimator and the switch chooser are handed to `ai_turns` rather than
    imported over there, so that module never imports this one back. Scripts/
    is full of `from x import *`, where a cycle is a silently half-built
    namespace rather than an ImportError -- which is exactly how
    `user_turn_in_battle_stats` went missing from battle_cycle once already.
    `ai_scorer` reaches back the other way, by importing inside its functions.
    """
    if str(getattr(ai, "brain", "") or "turns") != "scorer":
        return ai_turns.choose(battleground, protagonist, ai,
                               estimated_damage_calculation,
                               ai_switching_mechanism,
                               kit={"ability": UseAbility,
                                    "character": UseCharacterAbility,
                                    "Turn": Turn, "Side": Side,
                                    "weather": onWeatherCheck,
                                    "particular": onParticularMoveChange})

    return ai_scorer.choose(battleground, protagonist, ai)


def ai_switching_mechanism(protagonist, ai, battleground, recall=False, forced_switch=False, incoming_move=0):
    if (not forced_switch) and recall:
        if ai.team[0].volatile_status['Binding'] > 0 or ai.team[0].volatile_status['Trapped'] > 0:
            if 'Ghost' not in ai.team[0].type:
                narrator.say("The pokemon cannot be switched out!", "fail")
                return 0

    available_pokemon = [x for x in ai.team]
    net_damage = [0 if pokemon.status != "Fainted" else NEG_INF for pokemon in ai.team]

    # AI will consider your moveset and its pokemon moveset, calculate the net damage and select the best pokemon
    # for pokemon in available_pokemon:
    #     print(f"{ai.side_color}{pokemon.name} {pokemon.nominal_base_stats} {pokemon.iv} {pokemon.moveset} {pokemon.ability}{CEND}")

    if battleground.verbose:
        for pokemon in available_pokemon:
            narrator.say(f"{ai.side_color}{pokemon.name} {pokemon.nominal_base_stats} {pokemon.iv} {pokemon.moveset} {pokemon.ability}{CEND}")

    # Copies, because the estimator writes to whatever move it is handed --
    # super_effective, not_effective, and for an interchange-type move its very
    # type. This used to pass the *shared* entries of list_of_moves straight
    # in, so scoring a switch quietly rewrote the game's move table for every
    # Pokemon in every later battle: over 25 battles it left 211 of 387 moves
    # carrying stale effectiveness flags and had permanently changed one move's
    # type. It was the only path that did; everything else already copied.
    #
    # Copied once here rather than once per candidate. The Pokemon being
    # switched away from does not change while the candidates are compared, so
    # its moves were being copied six times over -- 43% of all the copying a
    # battle does. Reusing them is exact rather than approximate: the estimator
    # writes three fields and no more (checked against the source), and
    # super_effective and not_effective are overwritten at the top of every
    # call before anything reads them. Only `type` carries over, so only
    # `type` is put back.
    facing = [fast_copy(list_of_moves[name])
              for name in protagonist.team[0].moveset]
    facing_types = [move.type for move in facing]
    incoming = None
    # `incoming_move` is an index, and it was worked out against the moveset
    # of whoever was *on the field* when smart_ai_select_move ran -- while
    # this reads `team[0]`. Those are not always the same Pokemon: mid-switch
    # the engine passes the one that was out while the team list already
    # holds its replacement (see the note on Side.active in CLAUDE.md). A
    # five-move Pokemon's index 4 into a two-move replacement is an
    # IndexError, which is what it was: 120 AI-vs-AI battles found it once a
    # damage change moved which index came out on top.
    #
    # An index that does not apply to the Pokemon standing there tells us
    # nothing about what is incoming, so there is nothing to read.
    if 0 < incoming_move < len(protagonist.team[0].moveset):
        incoming = fast_copy(
            list_of_moves[protagonist.team[0].moveset[incoming_move]])
        incoming_type = incoming.type

    #: what each slot can deal, kept so the stat-stage credit below is a
    #: fraction of real output rather than a flat number
    outgoing = [0.0] * len(available_pokemon)
    for index, pokemon in enumerate(available_pokemon):
        ai_speed, protagonist_speed = estimated_speed_adjustment(ai, pokemon, battleground), \
                                      estimated_speed_adjustment(protagonist, protagonist.team[0], battleground)
        if pokemon.status == "Fainted":
            continue
        else:
            incoming_move_damage, estimated_incoming_damage, estimated_outgoing_damage = 0, 0, 0
            if incoming is not None:
                incoming.type = incoming_type
                incoming_move_damage = estimated_damage_calculation(protagonist, ai, protagonist.team[0], pokemon, battleground, incoming)

            for slot, protagonist_move in enumerate(facing):
                protagonist_move.type = facing_types[slot]
                estimated_incoming_damage = max(estimated_damage_calculation(protagonist, ai, protagonist.team[0], pokemon, battleground, protagonist_move),
                                                estimated_incoming_damage)

            for ai_move in pokemon.moveset:
                ai_move = fast_copy(list_of_moves[ai_move])
                damage = estimated_damage_calculation(ai, protagonist, pokemon, protagonist.team[0], battleground, ai_move)
                estimated_outgoing_damage = max(damage, estimated_outgoing_damage)

            # stealth rock & spikes
            stealth_rock_damage = math.prod([typeChart["Rock"][x] for x in pokemon.type]) * pokemon.hp * 0.125
            spikes_damage = {0: 0, 1: 1 / 8, 2: 1 / 6, 3: 1 / 4}
            estimated_incoming_damage += stealth_rock_damage * ai.entry_hazard["Stealth Rock"] + pokemon.hp * spikes_damage[ai.entry_hazard["Spikes"]]
            estimated_incoming_damage *= 2 if protagonist_speed > ai_speed else 1
            estimated_outgoing_damage *= 2 if protagonist_speed < ai_speed else 1
            estimated_outgoing_damage *= 0 if incoming_move_damage > pokemon.battle_stats[0] else 1
            estimated_outgoing_damage *= 0.5 if estimated_incoming_damage > pokemon.battle_stats[0] else 1
            estimated_outgoing_damage *= 2 if estimated_outgoing_damage > protagonist.team[0].battle_stats[0] else 1

            estimated_incoming_damage = incoming_move_damage + estimated_incoming_damage
            net_damage[index] = estimated_outgoing_damage - estimated_incoming_damage
            outgoing[index] = estimated_outgoing_damage

    # What staying is worth beyond the damage sums above: switching resets
    # every stat stage, and none of the arithmetic above knew that. So a
    # Pokemon that had just spent a turn on Swords Dance would compare a
    # buffed self against a fresh team-mate on damage alone, find the
    # team-mate slightly better, and leave -- having paid for the boost and
    # then binned it. That is the "buffs, then switches" the AI was doing.
    #
    # Priced against the Pokemon's own output rather than as a flat number,
    # because a stage is worth a proportion of what it hits for: +2 Attack on
    # something that hits for 80 is worth far more than on something that
    # hits for 8.
    active = ai.team[0]
    if not forced_switch and active.status != "Fainted":
        stages = sum(max(0, stage) for stage in active.modifier[1:6])
        if stages and outgoing[0] > 0:
            net_damage[0] += STAGE_FORFEIT * stages * outgoing[0]
            if battleground.verbose:
                narrator.say("Staying keeps %d stage(s), worth %.1f"
                             % (stages, STAGE_FORFEIT * stages * outgoing[0]))

    try:
        if recall and max(net_damage) < -50:
            switched_pokemon = 0  # no switching
        else:
            switched_pokemon = net_damage.index(max(net_damage))
    except:
        check_win_or_lose(protagonist, ai, protagonist.team, ai.team, battleground)
    else:
        # Second best pokemon: the best of the *other* slots, when the best
        # overall is the one that has to leave.
        #
        # Was `net_damage.index(max(net_damage[1:5]))`, which had three
        # separate problems. `[1:5]` is slots 1-4, so the sixth Pokemon could
        # never be chosen however good the matchup. `.index()` then searched
        # the whole list for that value, so if slot 0 happened to hold the
        # same score it returned 0 -- the very answer this branch exists to
        # replace. And on a two-Pokemon team the slice could come back empty
        # and max() raise, in an `else` block no `except` covers.
        #
        # max(range, key=...) returns the index directly, is never 0, and
        # considers every slot the team actually has.
        if forced_switch and switched_pokemon == 0 and len(net_damage) > 1:
            switched_pokemon = max(range(1, len(net_damage)),
                                   key=lambda slot: net_damage[slot])
        if battleground.verbose:
            narrator.say(f"Estimated Net Damage: {net_damage}, Switched Pokemon: {switched_pokemon}")

        return switched_pokemon
    return 0
