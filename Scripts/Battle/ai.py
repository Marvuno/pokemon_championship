import random
from contextlib import suppress
from copy import deepcopy

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


def move_score_finalization(user, target, move_score, index):
    # rounding for readability
    move_score[index][1] = round(move_score[index][1], 2)
    move_score[index][2] = round(move_score[index][2], 2)

    # converting move damage and move additional effect into one single metric
    move_score[index][3] = move_score[index][1] ** (min(move_score[index][1] / max(1, target.battle_stats[0]), 1))  # damage conversion
    move_score[index][3] += move_score[index][2] * 0.5  # additional effect conversion
    try:
        move_score[index][3] = round(move_score[index][3], 2)  # rounding
    except TypeError:
        move_score[index][3] = 0
    return move_score


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


def intelligent_move_selection(user_side, target_side, user, target, battleground, move_score, user_stats):
    # declare temp. variables
    # 3 deciding factors: priority, damage and other factors
    # other factors score or damage will convert to measurable metrics at last
    # higher priority moves override score

    user_speed, target_speed = estimated_speed_adjustment(user_side, user, battleground), estimated_speed_adjustment(target_side, target, battleground)
    # maximum number of entry hazards that can be placed
    entry_hazard_maximum_usage = {"Stealth Rock": 1, "Spikes": 3, "Toxic Spikes": 2, "Sticky Web": 1}

    # first, estimate the max damage of protagonist pokemon
    # protagonist pokemon as user, ai pokemon as target
    for index, move in enumerate(user.moveset):
        # reset stats each time to avoid duplicated changes
        # a flat list of numbers, so a slice is the whole copy
        user.battle_stats = list(user_stats)
        move = fast_copy(list_of_moves[move])

        scoring = Turn(battleground,
                       Side(user_side, getattr(user_side, 'team', []), user),
                       Side(target_side, getattr(target_side, 'team', []),
                            target))
        UseAbility(scoring, move, abilityphase=2)
        UseAbility(scoring.flip(), move, abilityphase=3)
        UseCharacterAbility(scoring, move, abilityphase=2)
        UseCharacterAbility(scoring.flip(), move, abilityphase=3)
        onWeatherCheck(battleground, move)
        onParticularMoveChange(user, target, move)

        move.accuracy = move.accuracy * modifierChart[7][user.modifier[7]] * (1 / (modifierChart[6][0]) * move.evasion) if move.ignoreEvasion else \
            move.accuracy * modifierChart[7][user.modifier[7]] * (1 / (modifierChart[6][target.modifier[6]] * move.evasion))
        move.accuracy = min(move.accuracy, 1)  # for calculation purpose

        move.damage = estimated_damage_calculation(user_side, target_side, user, target, battleground, move)

        UseCharacterAbility(scoring, move, abilityphase=4)
        UseCharacterAbility(scoring.flip(), move, abilityphase=5)
        UseAbility(scoring, move, abilityphase=4)
        UseAbility(scoring.flip(), move, abilityphase=5)

        # expected damage
        move_score[index][1] = min(move.damage, target.battle_stats[0] * 1.12) * move.accuracy

        # conversion of move additional effect
        vartype = type(move.effect_type)
        # only one effect
        if vartype is str:
            effect_type, special_effect = [move.effect_type], [move.special_effect]
        # multiple effect
        elif vartype is list:
            effect_type, special_effect = move.effect_type, move.special_effect

        # move additional effect list
        for i in range(len(effect_type)):
            # always protect
            if "user_protection" in effect_type[i] and move.name != 'Protect' and user.protection[1] <= 0:
                move_score[index][2] += 50
            # recovery moves
            elif "self_heal" in effect_type[i]:
                if user.battle_stats[0] < user.hp * 0.33:
                    move_score[index][2] += user.hp * 0.5 * special_effect[i] * ((user.hp - user.battle_stats[0]) / user.hp)
            elif "hp_draining" in effect_type[i]:
                move_score[index][2] += move.damage * special_effect[i] * ((user.hp - user.battle_stats[0]) / user.hp)
            # team buff moves
            if "self_team_buff" in effect_type[i]:
                if user_side.in_battle_effects[move.name] <= 0:
                    move_score[index][2] += 20 * sum(1 for pokemon in user_side.team if pokemon.status != "Fainted")
            # entry hazard
            elif "apply_entry_hazard" in effect_type[i]:
                if target_side.entry_hazard[special_effect[i]] < entry_hazard_maximum_usage[special_effect[i]]:
                    move_score[index][2] += 20 * (1 / entry_hazard_maximum_usage[special_effect[i]]) * (sum(
                        1 for pokemon in target_side.team if pokemon.status != "Fainted") - 1)  # max 50
            # clear entry hazard
            elif "clear_entry_hazard" in effect_type[i]:
                move_score[index][2] += 20 * sum(1 for hazard in target_side.entry_hazard.values() if hazard > 0)
            # status condition move
            elif "target_non_volatile" in effect_type[i] and target.status == "Normal":
                # ground and electric type immune to paralysis status moves
                if special_effect[i] == Paralysis:
                    if not ("Ground" in target.type or "Electric" in target.type):
                        move_score[index][2] += 15 * move.effect_accuracy * move.accuracy
                # poison and steel type immune to poison
                elif special_effect[i] == Poison:
                    if not ("Poison" in target.type or "Steel" in target.type):
                        move_score[index][2] += 5 * move.effect_accuracy * move.accuracy
                elif special_effect[i] == BadPoison:
                    if not ("Poison" in target.type or "Steel" in target.type):
                        move_score[index][2] += 15 * move.effect_accuracy * move.accuracy
                elif special_effect[i] == Burn:
                    move_score[index][2] += 10 * move.effect_accuracy * move.accuracy if sum(
                        1 for moves in target.moveset if list_of_moves[moves].attack_type == "Physical") >= \
                        sum(1 for moves in target.moveset if list_of_moves[moves].attack_type == "Special") \
                        else 5 * move.effect_accuracy * move.accuracy
                else:
                    move_score[index][2] += 30 * move.effect_accuracy * move.accuracy
            # volatile condition move
            elif "target_volatile" in effect_type[i]:
                volatile_score = {Confused: 6, Octolock: 15, Binding: 15, Trapped: 3, Grounded: 1, TakeAim: 3, Frighten: 30}
                volatile_effect = special_effect[i]
                if target.volatile_status[volatile_effect.__name__] <= 0:
                    try:
                        move_score[index][2] += volatile_score[volatile_effect] * move.effect_accuracy * move.accuracy
                    except KeyError:
                        if volatile_effect == Flinch:
                            move_score[index][2] += 10 * move.effect_accuracy * move.accuracy if user_speed > target_speed else 0
            # self buff move
            # tbh, should distinguish clearly what buffs are good to user first
            elif "self_modifier" in effect_type[i]:
                total = 0
                for j in range(len(user.modifier)):
                    temp = max(6 - user.modifier[j], 1) ** (special_effect[i][j] / max(user.modifier[j], 1))
                    total += temp - 1
                move_score[index][2] += total * move.effect_accuracy * move.accuracy
            # debuff move
            elif "opponent_modifier" in effect_type[i]:
                for j in range(len(target.modifier)):
                    temp = (6 + target.modifier[j]) * (special_effect[i][j] / max(user.modifier[j], 1))
                    temp = temp if temp < 0 else 0
                    move_score[index][2] += temp * -1 * move.effect_accuracy * move.accuracy
            # self buff move
            elif "reset_user_modifier" in effect_type[i]:
                move_score[index][2] += sum(user.modifier) * -3
            # debuff move
            elif "reset_target_modifier" in effect_type[i]:
                move_score[index][2] += sum(target.modifier) * 3
            elif "target_disable" in effect_type[i]:
                if move.name not in user.move_order:
                    if special_effect[i] == 'Encore':
                        move_score[index][2] += 25
                    elif special_effect[i] == 'Taunt':
                        move_score[index][2] += 5 ** sum(1 for moves in target.moveset if list_of_moves[moves].attack_type == "Status")
                    elif special_effect[i] == 'Sound':
                        move_score[index][2] += 5 ** sum(1 for moves in target.moveset if 'f' in list_of_moves[moves].flags)
                    elif special_effect[i] == 'Disable':
                        move_score[index][2] += 5
            # can be good or bad
            elif "user_volatile" in effect_type[i]:
                good_volatile = {TotalConcentration: 50, AquaRing: 15, Ingrain: 10}
                with suppress(KeyError):
                    if user.volatile_status[special_effect[i]] <= 0:
                        move_score[index][2] += good_volatile[special_effect[i]]

        # forbid certain moves after usage
        use_frequency = user.move_order.count(move.name)
        no_repeat_move_list = ['Taunt', 'Torment', 'Encore', 'Belly Drum']
        if move.attack_type == 'Status':
            if 'self_modifier' in move.effect_type and use_frequency > 2:
                move_score[index][0] -= 1
            elif move.name in no_repeat_move_list and use_frequency > 0:
                move_score[index][0] -= 1

        # prioritize certain moves situationally
        if 'j' in move.flags and user.volatile_status["Turn"] <= 2:
            move_score[index][0] += 1
        elif move_score[index][1] > target.battle_stats[0] and move.priority > 0:
            move_score[index][0] += 1

        # Moves that cannot be used at all. These are not bad ideas to be
        # weighed against good ones -- the engine will refuse them outright,
        # so choosing one spends the turn on nothing. They go to the back of
        # the ranking, the same treatment `ineffective_moves` gets below.
        #
        # Both were docked a single point, which was not enough: the sort in
        # `smart_ai_select_move` reads this score *first* and damage only as
        # a tie-break, so a locked move that led by two points was still
        # picked. Measured against a Torment holder at 5.6 wasted turns a
        # battle -- and Torment locks whatever the AI most wants to use, so
        # it was losing its best move and its turn together.
        with suppress(KeyError):
            if user.disabled_moves[move.name] > 0:
                move_score[index][0] -= UNUSABLE_MOVE_PENALTY
                move_score[index][1] = 0
        if 'j' in move.flags and user.volatile_status["Turn"] > 2:
            move_score[index][0] -= UNUSABLE_MOVE_PENALTY
            move_score[index][1] = 0
        # prolly no-effect move
        if move.attack_type != 'Status' and move.damage == 0:
            move_score[index][0] -= 1
        # Already tried it on this Pokemon and it did nothing. The estimate
        # above can be wrong -- an immunity or a damage-zeroing ability only
        # shows up once the move has actually been thrown -- so a move with a
        # proven record of doing nothing to whatever is standing there is
        # pushed right to the back rather than merely docked a point.
        if move.name in user.ineffective_moves.get(target.name, ()):
            move_score[index][0] -= 20
            move_score[index][1] = 0

        landing = Turn(battleground,
                       Side(user_side, getattr(user_side, 'team', []), user),
                       Side(target_side, getattr(target_side, 'team', []),
                            target))
        UseAbility(landing, move, abilityphase=6)
        UseAbility(landing.flip(), move, abilityphase=7)
        UseCharacterAbility(landing, move, abilityphase=6)
        UseCharacterAbility(landing.flip(), move, abilityphase=7)

        move_score = move_score_finalization(user, target, move_score, index)

    return move_score


def smart_ai_select_move(battleground, protagonist, ai):
    """
    This AI is intelligent. It is only used for intermediate-level, advanced-level, elite-level and champion AI.
    Its behavior is as follows:
    - it knows all the moves of the opponent Pokemon
    - it considers various factors, including move damage, move's special properties, move additional effects, Pokemon speed etc.
    - it summarizes these factors into 3 deciding factors: Priority, Damage, Effects
    - it further combines Damage and Effects into Score as the factor
    - if there are no higher-priority moves, it will use move with highest score
    - hence, it usually prefers entry-hazard moves, team-buff moves and etc.
    - if it is confident to defeat opponent Pokemon before it does, it will execute the best move
    - otherwise, it will automatically tweak certain values, particularly emphasize more on status moves, when considering best move
    - under certain circumstances, e.g. no good moves or opponent Pokemon is vastly superior, if the Pokemon is not below a certain health threshold,
      it will consider switching into a Pokemon that can withstand the estimated incoming move
    - otherwise, it will go desperato and execute its final move
    - if it switches for 2 times, it is forbidden to switch again to avoid switching loop
    """
    # declare variables
    protagonist_pokemon, ai_pokemon = fast_copy(protagonist.team[0]), fast_copy(ai.team[0])
    protagonist_stats, ai_stats = protagonist_pokemon.battle_stats, ai_pokemon.battle_stats
    # One score slot per move the Pokemon actually has, not a fixed five.
    # Every "best move" below is chosen by sorting these *keys* and is then
    # used to index moveset -- so five slots for a Pokemon with fewer moves
    # left phantom entries that could win the sort and raise IndexError on
    # `moveset[ai_best_attack]`. It needed a Pokemon with under four moves
    # (Magikarp and friends), no move scoring above zero, and a failed
    # switch, which is why it survived this long.
    ai_move_score = {k: [0, 0, 0, 0] for k in range(len(ai_pokemon.moveset))}
    protagonist_move_score = {k: [0, 0, 0, 0]
                              for k in range(len(protagonist_pokemon.moveset))}
    ai_speed, protagonist_speed = estimated_speed_adjustment(ai, ai_pokemon, battleground), estimated_speed_adjustment(protagonist, protagonist_pokemon,
                                                                                                                       battleground)

    # charging moves
    if ai_pokemon.charging[0] != "":
        return list_of_moves[ai_pokemon.charging[0]]

    protagonist_move_score = intelligent_move_selection(protagonist, ai, protagonist_pokemon, ai_pokemon, battleground, protagonist_move_score, protagonist_stats)
    ai_move_score = intelligent_move_selection(ai, protagonist, ai_pokemon, protagonist_pokemon, battleground, ai_move_score, ai_stats)

    # predicting player moves
    protagonist_best_attack = sorted(protagonist_move_score, key=lambda x: (-protagonist_move_score[x][1]))[0]
    protagonist_best_move = sorted(protagonist_move_score, key=lambda x: (-protagonist_move_score[x][0], -protagonist_move_score[x][3], -protagonist_move_score[x][1]))[0]
    # measuring AI moves
    ai_best_attack = sorted(ai_move_score, key=lambda x: (-ai_move_score[x][1]))[0]
    ai_best_move = sorted(ai_move_score, key=lambda x: (-ai_move_score[x][0], -ai_move_score[x][3]))[0]

    # how many turns it took for opponent aka player to faint AI's pokemon
    protagonist_cause_faint_turns = math.ceil(ai_pokemon.battle_stats[0] / max(protagonist_move_score[protagonist_best_attack][1], 1))
    # vice versa
    ai_cause_faint_turns = math.ceil(protagonist_pokemon.battle_stats[0] / max(ai_move_score[ai_best_attack][1], 1))

    # pokemon who moves first has an advantage
    ai_cause_faint_turns = ai_cause_faint_turns - 0.5 if ai_speed > protagonist_speed else ai_cause_faint_turns + 0.5
    # if +ve, AI wins || if -ve, player wins || if turns_diff > 1, AI has time for set-up
    turns_diff = protagonist_cause_faint_turns - ai_cause_faint_turns

    # second update
    # at this stage, the prediction is not universal, based from what we predict player will do
    for index, move in enumerate(ai_pokemon.moveset):
        move = list_of_moves[move]

        # charging move
        if move.charging == "Charging":
            ai_move_score[index][2] -= 10
        # move with certain conditions
        if protagonist_pokemon.status != "Sleep":
            if move.name == "Dream Eater":
                ai_move_score[index][0] -= 1
        if 'Grass' in protagonist_pokemon.type:
            ai_move_score[index][0] -= 1 if 'g' in move.flags else 0

        # based on surviving turns
        if protagonist_cause_faint_turns < 3:
            recommended_move_list = ('Belly Drum', 'Unbreakable Will', 'Clangorous Soul')
            if move.name in recommended_move_list:
                ai_move_score[index][2] -= 50

        # based on speed
        if ai_speed > protagonist_speed:
            if protagonist_move_score[protagonist_best_attack][1] > ai_pokemon.battle_stats[0]:
                # destiny bond
                if move.name == "Destiny Bond":
                    ai_move_score[index][0] += 1
            # deduct HP moves
            if protagonist_cause_faint_turns <= 1:
                recommended_move_list = ('Explosion', 'Self-Destruct', 'Memento', 'Mind Blown')
                unrecommend_move_list = ('Belly Drum', 'Unbreakable Will', 'Clangorous Soul')
                if move.name in recommended_move_list:
                    ai_move_score[index][2] += 50
                elif move.name in unrecommend_move_list:
                    ai_move_score[index][0] -= 1

        else:
            if 1 < protagonist_cause_faint_turns <= 2:
                recommended_move_list = ('Explosion', 'Self-Destruct', 'Memento', 'Mind Blown')
                unrecommend_move_list = ('Belly Drum', 'Unbreakable Will', 'Clangorous Soul')
                if move.name in recommended_move_list:
                    ai_move_score[index][2] += 50
                elif move.name in unrecommend_move_list:
                    ai_move_score[index][0] -= 1

        # if player is not using attacking move
        if list_of_moves[protagonist_pokemon.moveset[protagonist_best_move]].attack_type == "Status":
            # prefer non-attacking move
            ai_move_score[index][2] *= 1.5
            if move.name == "Sucker Punch":
                ai_move_score[index][0] -= 1

    # perish song switching
    if ai_pokemon.volatile_status['PerishSong'] >= 3:
        ai_move_score[0][0] += 2
    elif ai_pokemon.volatile_status['Yawn'] >= 1:
        ai_move_score[0][0] += 1

    # if battleground.verbose:
    #     # converting move damage and move additional effect into one single metric
    #     for index in range(5):
    #         ai_move_score = move_score_finalization(ai_pokemon, protagonist_pokemon, ai_move_score, index)
    #     # debug
    #     print(f'\n{CBOLD}First: {ai_pokemon.name} | Turns: {turns_diff} | Player Move: {protagonist_pokemon.moveset[protagonist_best_move]}{CEND}')
    #     for i, (key, value) in enumerate(ai_move_score.items()):
    #         with suppress(IndexError):
    #             print(f"{ai_pokemon.moveset[key]}: Prio: {ai_move_score[i][0]} | Dmg: {ai_move_score[i][1]} "
    #                   f"| Eff: {ai_move_score[i][2]} | Score: {ai_move_score[i][3]}")

    # attempt analysis to player situation
    # to predict switching
    # condition that player might switch
    if turns_diff >= 3 and protagonist_move_score[protagonist_best_move][3] <= 5:
        protagonist_best_move = 0
        for index, move in enumerate(ai_pokemon.moveset):
            move = list_of_moves[move]

            # prefer non-attacking move
            if move.attack_type == 'Status':
                ai_move_score[index][2] *= 2
            # boldly assume that player will switch into other pokemon that resists incoming attack, so promote other attacking moves instead
            elif ai_pokemon.moveset[ai_best_attack] == move.name:
                ai_move_score[index][1] *= 0.6

    # can do it early
    ai.position_change = ai_switching_mechanism(protagonist, ai, battleground, recall=True, forced_switch=False, incoming_move=protagonist_best_move)

    if turns_diff < 0:
        for index, move in enumerate(ai_pokemon.moveset):
            move = list_of_moves[move]
            recommended_status = ('target_non_volatile', 'target_volatile', 'self_modifier', 'opponent_modifier', 'hp_split')
            if move.effect_type in recommended_status:
                ai_move_score[index][2] *= min(max(turns_diff * -1, 1), 3)
        # first conditions
        if turns_diff <= -2 or ai_best_move == 0 or ai_move_score[ai_best_move][3] <= 5 or protagonist_cause_faint_turns <= 1:
            # second conditions
            if not (ai_pokemon.battle_stats[0] <= ai_pokemon.hp * 0.33 and ai_speed > protagonist_speed):
                if ai.switching < 2:
                    if ai.position_change != 0:
                        for index, move in enumerate(ai_pokemon.moveset):
                            move = list_of_moves[move]
                            if ai_speed > protagonist_speed:
                                if move.name == 'Baton Pass':
                                    ai_move_score[index][0] += 1 if sum(ai_pokemon.modifier) > 0 else 0
                                    ai_move_score[index][0] += 1 if ai_pokemon.volatile_status['Ingrain'] + ai_pokemon.volatile_status['AquaRing'] > 0 else 0
                                    ai_move_score[index][0] -= 1 if ai_pokemon.volatile_status['Binding'] + ai_pokemon.volatile_status['Trapped'] > 0 else 0
                                elif 'switching' in move.effect_type:
                                    ai_move_score[index][0] += 1
                        ai_move_score[0][0] += 1

                    else:
                        # if swtiching is failed, it means AI side is already losing
                        # prefer using attacking moves
                        if battleground.verbose:
                            narrator.say(f"{CREDBG}2{CEND}")
                        if ai_best_attack == 0:
                            # use best attacking move instead
                            ranked = sorted(ai_move_score, key=lambda x: (-ai_move_score[x][0], -ai_move_score[x][1]))
                            ai_best_attack = ranked[0]
                            if ai_best_attack == 0 and len(ranked) > 1:
                                # index 0 is Switching, which is not an attack
                                ai_best_attack = ranked[1]

                        # # debug
                        # print(f'\n{CBOLD}Final: {ai_pokemon.name} | Turns: {turns_diff} | Player Move: {protagonist_pokemon.moveset[protagonist_best_move]}{CEND}')
                        # for i, (key, value) in enumerate(ai_move_score.items()):
                        #     with suppress(IndexError):
                        #         print(f"{ai_pokemon.moveset[key]}: Prio: {ai_move_score[i][0]} | "
                        #               f"Dmg: {ai_move_score[i][1]} | Eff: {ai_move_score[i][2]} | Score: {ai_move_score[i][3]}")

                        return list_of_moves[ai_pokemon.moveset[ai_best_attack]]

    # will keep for now
    # converting move damage and move additional effect into one single metric
    for index in list(ai_move_score):
        ai_move_score = move_score_finalization(ai_pokemon, protagonist_pokemon, ai_move_score, index)

    # # debug
    # print(f'\n{CBOLD}Final: {ai_pokemon.name} | Turns: {turns_diff} | Player Move: {protagonist_pokemon.moveset[protagonist_best_move]}{CEND}')
    # for i, (key, value) in enumerate(ai_move_score.items()):
    #     with suppress(IndexError):
    #         print(f"{ai_pokemon.moveset[key]}: Prio: {ai_move_score[i][0]} | "
    #               f"Dmg: {ai_move_score[i][1]} | Eff: {ai_move_score[i][2]} | Score: {ai_move_score[i][3]}")

    ranked = sorted(ai_move_score, key=lambda x: (-ai_move_score[x][0], -ai_move_score[x][3]))
    ai_best_move = ranked[0]
    if ai.position_change == 0 and ai_best_move == 0 and len(ranked) > 1:
        # staying in, so Switching is not an option -- take the next best
        ai_best_move = ranked[1]

    if ai_best_move != 0:
        ai.switching = 0
    else:
        ai.switching += 1

    if battleground.verbose:
        narrator.say(f"{CVIOLETBG}1{CEND}")

    return list_of_moves[ai_pokemon.moveset[ai_best_move]]


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
