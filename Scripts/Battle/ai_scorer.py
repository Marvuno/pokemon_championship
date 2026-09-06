"""The superseded move scorer, kept because it is the control arm.

This is the AI the game shipped with, and it is no longer the one that plays:
`ai.smart_ai_select_move` hands every turn to Scripts/Battle/ai_turns.py
unless a trainer asks otherwise.

    competitor.brain = "scorer"      # opts back in, per trainer

It is archived here rather than deleted because it is still doing a job. Every
measurement of the turn-currency AI is reported against this one -- it is what
"+0.5 against the scorer" is measured against -- and three suites drive it
directly. Deleting it would throw away the only baseline the project has.

How it works, and why it was replaced: it scores a move as four numbers,
[priority, damage, effects, score], and blends them with conversion factors
chosen by hand -- PRIORITY_WORTH, LETHAL_BONUS, `* 0.5`. Damage is in hit
points, effects are in invented units (15 paralysis, 20 hazard, 30 sleep), and
priority is a small integer, so every comparison between two of them needs its
own constant. It works, and it is measurably decent: it picks the best
expected-value attack 88.9% of the time it attacks. But every fault found in
it was fixed by adding another constant, which is the signature of a missing
unit rather than of wrong numbers, and supplying that unit is what ai_turns
is. See that module's docstring for the argument in full.

Nothing here imports Scripts/Battle/ai.py at module level. The three things
this needs from it -- the damage estimate, the speed estimate and the switch
chooser -- are imported inside the functions that call them, the same way
`before_battle.career_history` reaches `start_interface`. A module-level
import would close a cycle, and in this package a cycle is not an ImportError:
Scripts/ is full of `from x import *`, so the importing module simply gets a
half-built namespace and the failure surfaces later as a missing name. That is
how `user_turn_in_battle_stats` went missing from battle_cycle once already.
"""
import random
from contextlib import suppress
from copy import deepcopy

from Scripts.Battle import move_rules
from Scripts.Battle.fastcopy import Bystander, fast_copy
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
from Scripts.Battle.damage_calculation import (check_attack_power,
                                               check_defense_strength,
                                               check_if_weather_affect_moves)
from Scripts.Battle.battle_win_condition import check_win_or_lose
from Scripts.Art import narrator
from Scripts.Battle import terrain


#: How the AI ranks its own scored moves. `ai_move_score[k]` is
#: [priority, damage, effects, score], where `score` is damage weighted by
#: whether it would actually knock the target out (see
#: move_score_finalization) plus half the effect score.
#:
#: The shipped rule sorts on **priority first**, so a move one priority point
#: higher wins however much better the alternative scores. Measured over 40
#: battles, 1,291 real decisions: priority overrides the better-scoring move
#: on 13.6% of them, and gives up 50 or more score -- a likely knockout -- on
#: 4.8%. Two thirds of decisions have every move at equal priority, where the
#: rule does not matter at all.
#:
#: Worth knowing: the AI already predicts the *player* with a three-part key
#: that falls through to raw damage (see protagonist_best_move), and uses
#: only two parts for itself.
#:
#: A trainer may carry `move_ranking` to pick one of the others. Nothing in
#: the game sets it, so the shipped behaviour is untouched and the
#: fingerprint is unchanged. Test/ai_ranking_experiment.py compares them.
PRIORITY_FIRST = "priority-first"
PRIORITY_THEN_DAMAGE = "priority-then-damage"
SCORE_FIRST = "score-first"
BLENDED = "blended"

#: What one point of priority is worth in score, for BLENDED. The median
#: score given up to a one-point priority margin measured at 23, so this is
#: set just above it: enough that priority still decides the close calls it
#: should, not enough to give away a knockout.
PRIORITY_WORTH = 25.0

#: What a move that finishes the target this turn is worth on top of its
#: damage score.
#:
#: It needs one because the damage score is *proportional to what is left of
#: the victim*. Damage is capped at 1.12x the target's remaining HP
#: (intelligent_move_selection) and then raised to a power of at most 1, so a
#: kill on a Pokemon holding 10 HP scores about 11 -- while a Swords Dance
#: worth 40 in effects contributes 20 and beats it. The closer something was
#: to death, the less the AI wanted to finish it, and it spent the turn
#: setting up instead. Measured over 200 battles: a kill was on the table
#: 1,176 times and passed up 100 of them, most often for Light Screen, Nasty
#: Plot, Stealth Rock or Swords Dance.
#:
#: Flat rather than scaled, because what it is paying for does not scale
#: either: the target stops existing, and everything it would have done for
#: the rest of the battle stops with it. That is worth the same whether it
#: had 10 HP left or 200.
#:
#: `move_score[1]` is already accuracy-weighted, so testing it against the
#: target's HP asks "does this still kill after accuracy" rather than "could
#: it kill if it lands" -- an 85%-accurate move that only just kills does not
#: qualify, which is the right answer.
LETHAL_BONUS = 100.0


#: What the AI uses when a trainer does not name a rule. BLENDED since the
#: experiment below; PRIORITY_FIRST is the rule the game shipped with, and
#: putting it back here is the whole of the revert.
#:
#: Test/ai_ranking_experiment.py, 16,000 battles with the team, IVs,
#: abilities, character abilities and rating held identical on both sides and
#: every team played in both orientations. Read against the control arm in the
#: same run -- the shipped rule against itself, which measures side A's
#: structural advantage and is not exactly 50 -- BLENDED is worth about +3 to
#: +6 points, and it is ahead in all five team-quality bands.
#:
#: The two rules that did not work are worth knowing. Adding damage as a
#: third tiebreak scored 50.0 in every band: priority stays primary, so the
#: extra key almost never engages. Ranking score above priority came out at
#: nothing overall -- 45.6 with the weakest teams and 54.1 with the best --
#: because when nothing on a team can knock anything out, `score` is flat and
#: priority really is the better signal. Priority was never the mistake;
#: being *lexicographic* was, and pricing it fixes that without discarding
#: it. Sweeping the price over 10, 25, 50 and 100 put them all within noise
#: of each other, so the value is not delicate -- 25 is chosen because the
#: median score given up to a one-point priority margin measured at 23.
DEFAULT_RANKING = BLENDED


def move_ranking(scores, index, mode=PRIORITY_FIRST):
    """The sort key for one scored move. Lower sorts first, as `sorted` wants.

    Every branch keeps priority in the key somewhere. The question is not
    whether priority matters -- a genuine +1 priority move really does go
    first -- but whether it should be worth an unbounded amount of score,
    which is what making it the primary key means.
    """
    row = scores[index]
    if mode == PRIORITY_THEN_DAMAGE:
        # the key the AI already uses to predict the player
        return (-row[0], -row[3], -row[1])
    if mode == SCORE_FIRST:
        return (-row[3], -row[0])
    if mode == BLENDED or str(mode).startswith(BLENDED + "="):
        # priority priced in score rather than ranked above it. A trailing
        # "=n" overrides the price, which is how the sweep in
        # Test/ai_ranking_experiment.py tunes it.
        worth = PRIORITY_WORTH
        if "=" in str(mode):
            worth = float(str(mode).split("=", 1)[1])
        return (-(row[3] + row[0] * worth), -row[0])
    return (-row[0], -row[3])


def move_score_finalization(user, target, move_score, index):
    # rounding for readability
    move_score[index][1] = round(move_score[index][1], 2)
    move_score[index][2] = round(move_score[index][2], 2)

    # converting move damage and move additional effect into one single metric
    move_score[index][3] = move_score[index][1] ** (min(move_score[index][1] / max(1, target.battle_stats[0]), 1))  # damage conversion
    move_score[index][3] += move_score[index][2] * 0.5  # additional effect conversion
    # ...and finishing the target is worth more than anything it sets up for
    # a fight that is about to be over. See LETHAL_BONUS.
    if move_score[index][1] >= target.battle_stats[0] > 0:
        move_score[index][3] += LETHAL_BONUS
    try:
        move_score[index][3] = round(move_score[index][3], 2)  # rounding
    except TypeError:
        move_score[index][3] = 0
    return move_score


def intelligent_move_selection(user_side, target_side, user, target, battleground, move_score, user_stats):
    # ai.py keeps the three shared estimators: ai_turns uses them as
    # well, so they are not part of this archive. Imported here
    # rather than at module level -- see the note in the docstring.
    from Scripts.Battle.ai import (estimated_damage_calculation,
                                   estimated_speed_adjustment)
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

        # The two Pokemon here are already copies -- see the caller -- but
        # the sides were the live trainers, and a side is writable: a hazard
        # ability reaches for `entry_hazard` rather than for a Pokemon.
        # Measured at 6 evaluations in 2,852 laying real Toxic Spikes.
        scoring = Turn(battleground,
                       Side(Bystander(user_side),
                            getattr(user_side, 'team', []), user),
                       Side(Bystander(target_side),
                            getattr(target_side, 'team', []), target))
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
        # ...and nothing at all if the move's own condition cannot be met.
        # Same gap as the turn AI had: the engine checks this at execution
        # time and the scorer never did, so Dream Eater was worth its full
        # power against somebody awake. See move_rules.certainly_fails.
        if move_rules.certainly_fails(user, target, move):
            move.damage = 0

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
        # Accuracy zeroed means the move cannot reach at all -- Psychic
        # Terrain, Queenly Majesty and Dazzling all say "this does not
        # reach" that way, and no move in the table ships with 0. Damage
        # score is already multiplied by accuracy, so it is 0 here; without
        # this the only mark against the move was the single point below,
        # and a strong priority move still outranked everything and was
        # thrown into the wall every turn.
        if move.accuracy <= 0:
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


def choose(battleground, protagonist, ai):
    """One turn of the shipped scorer. Returns a Move, as the engine expects.

    This was the body of `ai.smart_ai_select_move` before the dispatch was put
    in front of it; the signature is unchanged so the two brains are
    interchangeable at the call site.

    Its own description of itself, kept from that function:

    - it knows all the moves of the opponent Pokemon
    - it considers move damage, special properties, additional effects, speed
    - it summarises those into three deciding factors: Priority, Damage,
      Effects, and combines the last two into Score
    - with no higher-priority move available it uses the highest score, which
      is why it leans toward entry hazards and team buffs
    - if it expects to win the race it plays the best move outright; if not it
      re-weights toward status moves and tries again
    - if the matchup is bad and it is healthy enough, it looks at the bench
    - twice switched is the limit, so it cannot loop
    """
    # ai.py keeps the three shared estimators: ai_turns uses them as
    # well, so they are not part of this archive. Imported here
    # rather than at module level -- see the note in the docstring.
    from Scripts.Battle.ai import (ai_switching_mechanism,
                                   estimated_speed_adjustment)
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
    # "Comfortably ahead, so there is time to set up" -- true only while the
    # opponent is still going to be there. This block doubles every status
    # score and knocks 40% off the best attack, and it was firing on turns
    # where that attack would have ended the fight; against the weaker AIs,
    # which it is ahead of more often, it fired more and cost more.
    ai_can_finish = ai_move_score[ai_best_attack][1] >= protagonist_pokemon.battle_stats[0] > 0
    if turns_diff >= 3 and protagonist_move_score[protagonist_best_move][3] <= 5             and not ai_can_finish:
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

    ranked = sorted(ai_move_score,
                    key=lambda x: move_ranking(
                        ai_move_score, x,
                        getattr(ai, 'move_ranking', DEFAULT_RANKING)))
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
