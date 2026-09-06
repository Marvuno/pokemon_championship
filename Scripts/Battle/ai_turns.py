"""An AI that scores every move in one unit: turns in the race.

The existing scorer in ai.py adds four incommensurable quantities together --
priority as small integers, damage as `min(dmg, hp*1.12) * accuracy`, effects
as hand-picked constants (15 paralysis, 20 hazard, 30 sleep), then blends them
with conversion factors chosen by hand: `* 0.5`, PRIORITY_WORTH, LETHAL_BONUS.
It works, and it is measurably decent -- it picks the best expected-value
attack 89% of the time it attacks. But every fault found in it has been fixed
by inventing another constant, which is the signature of a missing unit rather
than of wrong numbers.

This module supplies the unit. Two Pokemon are in a race:

    t_kill   turns I need to knock the target out
    t_die    turns the target needs to knock me out

and the margin `t_die - t_kill` is what winning looks like. Every move is
worth the change it makes to that margin, measured in turns:

    an attack        cuts t_kill, and a miss costs a whole turn -- so accuracy
                     prices itself instead of being multiplied in twice
    a kill           takes t_kill to zero and erases every turn the target had
                     left to hurt me, which is why no LETHAL_BONUS is needed
    an Attack boost  cuts t_kill for the rest of the fight, so it is worth a
                     lot with four turns left and nothing with one -- which is
                     the "set up while comfortably ahead" bug, priced away
    a screen         raises t_die
    priority         is worth a fraction of a turn exactly when the race is
                     tied, rather than a flat 25 points

Nothing here is a free parameter except the EFFECT_TURNS table, and every
entry in that is an estimate about the game that can be argued with, rather
than a number holding a formula together.

    Tier 1  damage and lethality in turns                _race, _turns_to
    Tier 2  every other effect in turns                  EFFECT_TURNS
    Tier 3  one ply of search over the move matrix       _matrix_choice

Tier 4 was the line not to cross: no learned policy and no self-play. A game
with 72 hand-designed characters wants an AI that can be reasoned about.

Selection is opt-in and per trainer, so nothing changes for anybody until a
competitor asks for it:

    competitor.brain = "turns"

`ai.smart_ai_select_move` checks that attribute and delegates here. The old
scorer is untouched and remains the default.
"""
import math
import random
from contextlib import suppress

from Scripts.Battle import ai_knowledge
from Scripts.Battle.fastcopy import fast_copy
from Scripts.Battle.type_chart import modifierChart
from Scripts.Data.moves import list_of_moves
from Scripts.Data.pokemon import list_of_pokemon

#: Turns bought by an effect that is not damage. This is Tier 2, and it is the
#: only table of judgement calls in the module -- each number says "this is
#: worth about this many turns of the race", which is a claim about the game
#: that can be checked, unlike `+= 15`.
#:
#: Read as: how many turns of the opponent's clock this removes, or how many
#: turns of mine it buys. A sleep that lasts two turns is worth two turns.
#: Paralysis costs a quarter of every remaining turn. A burn halves physical
#: output, which is most of a turn's damage for most attackers.
EFFECT_TURNS = {
    "Sleep": 2.0,
    "Freeze": 2.0,
    "Paralysis": 0.25,          # per remaining turn, scaled below
    "Burn": 0.35,               # per remaining turn: halves physical output
    "Poison": 0.15,
    "BadPoison": 0.30,
    "Confused": 0.40,
    "Binding": 0.30,
    "Octolock": 0.35,
    "Trapped": 0.20,
    "Frighten": 0.50,
}

#: A screen halves incoming damage of its kind for five turns. Half the
#: incoming damage over the turns it covers is worth that much of t_die.
SCREEN_TURNS = 0.8

#: One layer of entry hazard costs whoever walks in a slice of their health.
#: Worth the turns that slice represents, times the Pokemon still to come --
#: which is why laying rocks is worth a lot on turn one and nothing at all
#: when the opponent has one Pokemon left.
HAZARD_TURNS_PER_ARRIVAL = 0.18

#: Moving first is worth a fraction of a turn, and only when the race is
#: close: if I need three turns and they need five, going first this turn
#: changes nothing. Priced against how tight the race is rather than flat.
PRIORITY_TURNS = 0.45

#: The most turns any single effect may claim. Sleep aside, an effect that
#: appears to buy four turns is a modelling error, not a play.
EFFECT_CEILING = 1.5

#: How much of a persistent effect's value carries past the Pokemon in front
#: of it.
#:
#: t_kill and t_die describe two Pokemon on a field of twelve, so on their own
#: they price a Swords Dance at the one turn it saves against *this* target --
#: when what it is actually for is the three targets after it. Boosts, screens
#: and hazards all outlive the matchup that paid for them; damage does not.
#:
#: So a persistent effect is multiplied by how many opponents are left to
#: spend it on, discounted by whether the holder will still be standing to do
#: the spending.
#:
#: **Measured at zero, and it is off.** The reasoning above is sound and the
#: engine disagrees with it, over 240 battles each way against the shipped
#: scorer:
#:
#:     0.45  -13.3 points     0.15  -8.8 points     0.0  -4.6 points
#:
#: Monotone, so this is not a tuning miss -- every unit of sweep weight costs
#: about twenty points per unit. The likely reason is that a boost is only
#: banked while the holder stays in, and in a six-Pokemon game at this
#: engine's damage levels it usually does not: the sweep is priced in
#: advance and then collected by the opponent's next attacker. `survival`
#: was meant to discount exactly that and is too crude to.
#:
#: Left in place at zero rather than deleted, because the idea deserves a
#: better test than this one -- a real answer needs the boost's value to be
#: conditional on actually surviving to spend it, which is a two-ply question
#: and belongs with the search, not with a multiplier.
SWEEP_WEIGHT = 0.0

#: What a move that does not resolve in one turn actually costs.
#:
#: Two numbers, because a turn currency can measure exactly two things about
#: a slow move: how many turns pass before the hit lands, and how much of the
#: opponent's free time in the meantime is spent hurting me.
#:
#:     (strike_delay, exposure)
#:
#: Read off battle_move_execution rather than guessed:
#:
#:   Charging            onChargingMove sets `move.damage = 0` on the first
#:                       turn and resolves on the second, and I am a normal
#:                       target throughout -- one hit for two turns, fully
#:                       exposed. Solar Beam, Solar Blade, Skull Bash,
#:                       Annihilation.
#:   Semi-invulnerable   the same two turns, but
#:                       move_fail_checklist_during_execution fails almost
#:                       everything aimed at a target that is mid-Fly, so the
#:                       damage exposure is nil and the cost is tempo alone --
#:                       see SEMI_EXPOSURE. Fly, Dig, Dive, Bounce,
#:                       Phantom Force.
#:   Frenzy              *not a slow move at all*. Outrage, Thrash, Petal
#:                       Dance and Raging Fury deal full damage on every turn
#:                       of the lock and only then confuse the user. They
#:                       cost no tempo whatsoever.
#:
#: The version this replaces had a single scalar over a single cost table,
#: with Frenzy in it at 0.85. Swept twice, it measured monotone-against both
#: times (0.0 -3.2, 0.5 -4.4, 1.0 -4.8) and was switched off as a bad idea.
#: That reading was wrong, and the reason is here: the knob was docking
#: Outrage and Petal Dance -- two of the strongest moves in the roster -- for
#: a cost the engine never charges them, and the damage that did swamped
#: whatever the four genuine two-turn moves gained. A scalar could not have
#: found this, because the three cases do not differ by a multiplier; they
#: differ in shape.
CHARGE_SHAPE = {
    "Charging":          (1.0, 1.0),
    "Semi-invulnerable": (1.0, None),   # None -> SEMI_EXPOSURE, swept
    "Frenzy":            (0.0, 0.0),
}

#: What the opponent's free turn is worth while I am underground or in the air.
#:
#: Not damage -- they cannot reach me. Tempo: they set up, heal, lay hazards,
#: or switch to something that beats what is about to land. Expressed on the
#: same 0-1 scale as ordinary exposure so the same arithmetic covers it, and
#: kept separate from the shape table because it is the one number here that
#: is a judgement rather than a reading of the engine.
SEMI_EXPOSURE = 0.35

#: What locking yourself into a Frenzy move costs, in turns.
#:
#: The lock itself is free -- full damage every turn. The bill is the
#: Confused that onChargingMove applies when the lock ends, which is the same
#: thing this module prices at 0.40 turns when it is inflicted on somebody
#: else, so it is priced at 0.40 turns when it is inflicted on me. Charged
#: once, at the moment of committing, because `choose` returns early on every
#: subsequent turn of the lock and never revisits the decision.
FRENZY_TAIL = EFFECT_TURNS["Confused"]


def _charge_shape(move):
    """(strike_delay, exposure) for a move, (0, 0) for an ordinary one."""
    kind = str(getattr(move, "charging", "") or "")
    delay, exposure = CHARGE_SHAPE.get(kind, (0.0, 0.0))
    return delay, SEMI_EXPOSURE if exposure is None else exposure


#: How long you have to still be standing for a setup move to pay for itself.
#:
#: A boost is banked, not spent -- it is worth the turns it saves *later*, and
#: there is no later if the Pokemon holding it faints this turn. Without this
#: the model happily played Bulk Up in front of something that kills it next
#: turn, which is what the shipped scorer says with `-= 50` on Belly Drum and
#: friends when `protagonist_cause_faint_turns < 3`.
#:
#: Expressed as a gate on t_die rather than a list of move names, so it
#: covers every setup move in the game including ones added later.
#: Swept at 1.0 / 2.0 / 3.5: -3.0, -3.4, -3.5, all inside the noise of the
#: -3.2 baseline. So the gate costs nothing and is kept for being right rather
#: than for being worth points -- the model should not think a boost has value
#: with no turns left to spend it, whatever the scoreboard says.
SETUP_HORIZON = 1.0

#: What leaving the field costs, in turns. A switch gives up the turn, takes
#: a free hit on the way in, and throws away every stat stage -- so it is
#: charged more than the one turn the first version billed it.
SWITCH_COST = 1.0

#: The odds below which staying in is bad enough to look at the bench at all.
#:
#: Swept against the shipped scorer, 520 battles an arm:
#:
#:     0.30  -5.1    0.40  -6.3    0.50  -3.0    0.55  -0.9
#:     0.70  +0.4    0.85  +0.6    0.95  +0.0    1.01  +0.0
#:
#: Monotone upward to about 0.85 and flat after -- switching *more* is what
#: helped, which is the opposite of the guess that started the sweep. The
#: trigger was never the brake it looked like: a bench candidate still has to
#: beat staying in after being charged SWITCH_COST, so a permissive trigger
#: only means the bench is *considered*, and considering it more often is
#: free. 0.85 rather than 1.01 because the last stretch buys nothing and a
#: threshold that is never reached is a line of code pretending to be a rule.
SWITCH_TRIGGER = 0.85

#: How much a *damaging* move's secondary effect is allowed to sway the
#: choice. A rider is real but it is not why the move is being used, and
#: over-crediting it is exactly what makes the shipped scorer reach for Cling
#: and Whirlpool -- moves that are never the best hit and still get picked a
#: quarter of the time.
#: Measured: 1.0 gives -3.9 against the shipped scorer, 0.5 gives -1.7, 0.0
#: gives -2.2. Half credit beats both full credit and none -- the rider is
#: worth something and it is not worth what it looks like.
RIDER_WEIGHT = 0.5

#: What knocking the target out is worth beyond zeroing the clock.
#:
#: A kill does two things and the first version only counted one. It takes
#: t_kill to zero -- and it also removes the thing that was going to kill me,
#: so the danger resets to whatever walks in next rather than continuing from
#: here. Without the second half a kill scored `t_die` while a status move
#: scored `t_die + effect`, so anything on the effect table beat finishing:
#: 12.5% of turns passed up a certain kill.
#:
#: Three turns is roughly what a fresh Pokemon on a full bar is worth, and it
#: is deliberately larger than EFFECT_CEILING so that no effect can outbid a
#: knockout.
KO_RELIEF = 3.0

#: How sharply the race margin converts into odds of winning it.
#:
#: The margin alone is not the objective, and ranking by it directly was the
#: first version's mistake: it prices a turn added to my clock exactly like a
#: turn cut from theirs, so Recover, Light Screen and Toxic Spikes -- which
#: lengthen the fight without advancing the kill -- outscored attacking.
#: Measured, that AI spent 28.4% of its turns on status against the scorer's
#: 11.6%, passed up a certain kill on 11.5% of turns against 0.3%, and lost
#: by 16.2 points.
#:
#: Winning requires t_kill < t_die and nothing more. Margin past that is
#: worth almost nothing, which a logistic says and a subtraction cannot: at a
#: margin of +2 another turn of padding buys 0.1 of a win, while at 0 it buys
#: 0.25. Sharpness 1.0 keeps a one-turn edge meaningful (0.73) without making
#: a two-turn edge a certainty.
#: Swept against the shipped scorer: 2.4 gives -4.4, 1.6 -3.3, 1.0 -1.7, and
#: everything from 0.6 down to 0.15 sits at parity. Ranking by odds is
#: monotone in the margin, so this constant changes exactly one thing -- the
#: risk attitude in the accuracy expectation, where the odds of two branches
#: are averaged. Flatter is better here, which says the engine's misses are
#: not worth being clever about.
RACE_SHARPNESS = 0.45

#: How many turns ahead is "the fight is already decided". Beyond this the
#: race margin stops being informative and everything looks equally won, so
#: the value is clamped and ties fall through to the damage tiebreak.
RACE_CEILING = 6.0

#: Damage-per-turn floor, so a Pokemon that cannot hurt anything still yields
#: a finite number of turns rather than a division by zero.
MIN_DAMAGE = 1.0

#: Turns assigned when nothing can finish the job. Not infinity: it has to
#: stay comparable with real turn counts.
NEVER = 12.0


def _real_accuracy(move, attacker, defender):
    """The move's accuracy against *this* target, stages and all.

    The printed accuracy is not the odds. The engine folds in the attacker's
    accuracy stages and the defender's evasion stages before it rolls, and
    the old scorer did the same before scoring -- this module did not, and
    read every move at its face value.

    What that cost: a Maractus using Acupressure reaches +6 evasion, and
    Champion Marvin's Armadragdon threw Fly at it twenty-one times over a
    49-turn battle, believing a 95% move was landing while it missed nearly
    every time. It lost him the game to a competitor rated 1. The AI was not
    being stubborn -- it genuinely could not see the dodging.

    `ignoreEvasion` moves read the defender's stage as 0, which is what
    "ignores evasion" means and what the engine itself does.
    """
    accuracy = getattr(move, "accuracy", 1.0)
    try:
        accuracy = float(accuracy)
    except (TypeError, ValueError):
        return 1.0

    # A two-turn move is judged on the turn it *lands*, not the turn it starts.
    #
    # onParticularMoveChange sets a charging move's accuracy to
    # GUARANTEE_ACCURACY the moment it is begun, which is right -- starting a
    # Fly cannot miss. But the AI only ever decides from the not-yet-charging
    # state, so it always saw the guarantee and never the 95% the landing turn
    # actually rolls at. Fly read as an unmissable 90-power STAB hit forever.
    #
    # That, and not stubbornness, is why Champion Marvin threw Fly at a +6
    # evasion Maractus twenty-one times in one battle and lost to Goblin. The
    # table entry is the honest number; the probe has been overwritten.
    original = list_of_moves.get(getattr(move, "name", ""))
    if original is not None and getattr(move, "charging", "") in (
            "Charging", "Semi-invulnerable"):
        with suppress(TypeError, ValueError):
            accuracy = float(getattr(original, "accuracy", accuracy))

    # ...and a sentinel above 1 is a certainty, not a multiplier: clamp before
    # the stages divide into it, or "guaranteed" survives being dodged.
    accuracy = min(1.0, accuracy)
    evasion = getattr(move, "evasion", 1) or 1
    try:
        stages = attacker.modifier[7]
        dodge = 0 if getattr(move, "ignoreEvasion", False) else defender.modifier[6]
        accuracy *= modifierChart[7][stages] / (modifierChart[6][dodge] * evasion)
    except (AttributeError, IndexError, TypeError, ZeroDivisionError):
        pass
    return min(1.0, max(0.0, accuracy))


def _accuracy(move):
    """The move's own accuracy as a fraction, clamped into [0, 1].

    Zero is a real answer and must survive. `... or 1.0` used to sit on the
    end of this as a guard against a missing value, and `0.0 or 1.0` is 1.0 --
    so every mechanism in the engine that says "this move does not reach" by
    zeroing accuracy was read by this AI as "lands every time":

        Time Travel        priority moves cannot touch Makise Kurisu
        Psychic Terrain    priority moves cannot touch anything grounded
        Charm              the opponent is distracted into missing
        Queenly Majesty / Dazzling, and the accuracy check itself

    Makise Kurisu took 4 of 10 off Emperor Marvuno and 1 off Champion Marvin
    on the strength of it: both hold priority moves, both were told those
    moves were perfectly accurate, and both kept throwing them at the one
    trainer in the game who is immune. The old scorer never had this problem
    -- it multiplies damage by accuracy directly, so a zero was a zero.

    A missing or unparseable accuracy still falls back to 1.0, which is what
    the guard was actually for.
    """
    value = getattr(move, "accuracy", 1.0)
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(1.0, max(0.0, value))


def _turns_to(health, per_turn):
    """Turns to remove `health` at `per_turn`, as a real number.

    Not `ceil`. A half turn of overkill really is worth less than a whole one,
    and rounding up throws away exactly the distinction this module exists to
    make -- with ceil, a move that leaves the target on 1 HP and one that
    leaves it on 99% both read as "one more turn".
    """
    if health <= 0:
        return 0.0
    return min(NEVER, health / max(MIN_DAMAGE, per_turn))


#: A real row borrowed for its shape only -- every field that matters is
#: overwritten below. Nothing reads it except as a starting point.
_TEMPLATE = "Body Slam"


def _placeholder(attacker, type_name):
    """A stand-in for a move nobody has seen yet.

    Built rather than borrowed: a real move drags its own type and its own
    rider along with it, and the rider is the subtler problem -- Body Slam
    carries Paralysis, so a blind trainer would fear a paralysis it has no
    reason to expect on top of guessing the damage.

    The category follows the attacker's better offensive stat, which is the
    assumption a person makes on sight: a Pokemon built to hit physically
    probably hits physically.
    """
    probe = fast_copy(list_of_moves[_TEMPLATE])
    probe.name = ai_knowledge.unknown_slot(type_name)
    probe.type = type_name
    probe.power = ai_knowledge.UNKNOWN_POWER
    probe.accuracy = 1
    probe.effect_type = "no_effect"
    probe.special_effect = None
    stats = getattr(attacker, "battle_stats", []) or []
    physical = len(stats) < 4 or stats[1] >= stats[3]
    probe.attack_type = "Physical" if physical else "Special"
    return probe


def _pool_of(species):
    """The species movepool, as the game already loads it."""
    entry = list_of_pokemon.get(species)
    return [name for name in getattr(entry, "moveset", [])
            if name in list_of_moves]


def _base_stats_of(species):
    """The species' own stat line -- no IVs, which is the point."""
    entry = list_of_pokemon.get(species)
    return list(getattr(entry, "base_stats", []) or [])


def _abilities_of(species):
    """Every ability the species can hold -- one or two of them."""
    entry = list_of_pokemon.get(species)
    known = getattr(entry, "ability", []) or []
    return list(known) if isinstance(known, list) else [known]


def believed(foe, trainer):
    """The opponent as this trainer sees them, or the real thing if fully seen.

    A copy, never the live Pokemon. Handing the estimator a fogged view of the
    real object and restoring it afterwards would work right up until
    something raised in between and left a Pokemon holding a move it does not
    have -- and `fast_copy` costs 14 microseconds against a 50ms battle.
    """
    level = ai_knowledge.rung(trainer)
    if level >= ai_knowledge.FULL:
        return foe
    shadow = fast_copy(foe)
    shadow.moveset = ai_knowledge.believed_moveset(
        foe, level, _pool_of, set(getattr(foe, "move_order", [])))
    ability = ai_knowledge.believed_ability(foe, level, _abilities_of)
    if ability is not None:
        shadow.ability = ability

    # The stat line, and then the stats that follow from it. Writing
    # nominal_base_stats alone would change nothing: every damage and speed
    # read goes through `battle_stats`, which battle_cycle rebuilds from the
    # nominal line at the top of each turn -- so the shadow has to do that
    # same rebuild itself, or it would carry the real individual's numbers
    # under a believed nominal line and none of this would bite.
    #
    # battle_stats[0] is current HP and is deliberately left alone: the bar is
    # on screen, so there is nothing to be ignorant about. The stat stages are
    # kept too -- the engine announces every one of them.
    stats = ai_knowledge.believed_stats(foe, level, _base_stats_of)
    if stats and len(stats) >= 6:
        shadow.nominal_base_stats = list(stats)
        shadow.battle_stats = [foe.battle_stats[0]] + [
            math.floor(0.01 * 2 * stats[x]
                       * modifierChart[x][shadow.modifier[x]] * 100 + 5)
            for x in range(1, 6)]
    return shadow


def _hits(estimator, side, foe_side, me, foe, ground, kit=None,
          sees_theirs=True, want_heal=False):
    """Expected damage and accuracy for each of `me`'s moves against `foe`.

    Computed once and reused by every cell of the Tier 3 matrix, which is what
    keeps a 5x4 search cheaper than the single-move scoring it replaces.

    fast_copy on every probe: the estimator writes its working state onto
    whatever Move it is handed, and the entries of list_of_moves are shared by
    every Pokemon in the game -- the trap test_engine_integrity exists for.

    `kit` carries the engine's own ability hooks, passed in from ai.py so this
    module never imports back into it. Without them the estimate was
    ability-blind: `estimated_damage_calculation` does not fire abilities --
    `intelligent_move_selection` does, around the call -- so this mirrors that
    sequence rather than inventing one.

    `sees_theirs` is the character-ability half of the difficulty ladder. A
    trainer below Advanced does not know the opponent has one, so the flipped
    phase-3 call simply does not happen and the move is scored as though the
    ability were not there. Their own is always fired: it is theirs.
    """
    table = {}
    for name in getattr(me, "moveset", []):
        assumed = ai_knowledge.slot_type(name)
        if assumed is None and (name not in list_of_moves
                                or name == "Switching"):
            continue
        probe = _placeholder(me, assumed) if assumed is not None             else fast_copy(list_of_moves[name])
        if kit is not None:
            scoring = kit["Turn"](
                ground,
                kit["Side"](side, getattr(side, "team", []), me),
                kit["Side"](foe_side, getattr(foe_side, "team", []), foe))
            with suppress(Exception):
                kit["ability"](scoring, probe, abilityphase=2)
                kit["ability"](scoring.flip(), probe, abilityphase=3)
                kit["character"](scoring, probe, abilityphase=2)
                if sees_theirs:
                    kit["character"](scoring.flip(), probe, abilityphase=3)
                kit["weather"](ground, probe)
                kit["particular"](me, foe, probe)
        if getattr(probe, "attack_type", "") == "Status":
            table[name] = (0.0, _real_accuracy(probe, me, foe), 0.0)
            continue
        try:
            dealt = estimator(side, foe_side, me, foe, ground, probe)
        except Exception:
            dealt = 0.0

        # Phases 4 and 5, *after* the number exists.
        #
        # Phase 4 is "dealing damage" -- it is where an ability changes the
        # figure rather than the move, so firing only 2 and 3 left every
        # damage-shaping ability invisible to this AI: Field Study's stacking
        # bonus, Outliers' band, Tenebrous, Ruthless, Thief, and Gargantuan on
        # the flipped side. The competitor held the ability and then chose its
        # moves as though it did not.
        #
        # The engine's own sequence assigns the estimate to `move.damage` and
        # lets the abilities rewrite it in place, so this reads the figure back
        # off the probe rather than trusting what the estimator returned.
        if kit is not None:
            probe.damage = dealt
            with suppress(Exception):
                kit["character"](scoring, probe, abilityphase=4)
                if sees_theirs:
                    kit["character"](scoring.flip(), probe, abilityphase=5)
                kit["ability"](scoring, probe, abilityphase=4)
                kit["ability"](scoring.flip(), probe, abilityphase=5)
            dealt = getattr(probe, "damage", dealt)

        # Phase 6 -- what the attack gives *back*. Blood Magic drains a third
        # of the damage dealt, Barbaric a third below half health, and neither
        # fires anywhere in either AI's move loop, so an attack that heals
        # scored exactly like one that did not. Demon Muzan is rated 689 on an
        # ability his own AI could not see.
        #
        # Fired against a *copy* of the holder, and this is not optional:
        # blood_magic writes straight to `user.battle_stats[0]` with no
        # `reality` guard, so running it here against the live Pokemon would
        # heal it for real, every time the AI thought about a move.
        healed = 0.0
        if kit is not None and want_heal and dealt > 0:
            shadow = fast_copy(me)
            probe.damage = dealt
            landing = kit["Turn"](
                ground,
                kit["Side"](side, getattr(side, "team", []), shadow),
                kit["Side"](foe_side, getattr(foe_side, "team", []), foe))
            before = shadow.battle_stats[0]
            with suppress(Exception):
                kit["character"](landing, probe, abilityphase=6)
                kit["ability"](landing, probe, abilityphase=6)
            healed = max(0.0, float(shadow.battle_stats[0] - before))

        table[name] = (max(0.0, float(dealt or 0.0)),
                       _real_accuracy(probe, me, foe), healed)
    return table


def _output(table):
    """The best expected damage a moveset can manage *per turn*.

    Per turn, not per use, and the distinction is the whole two-turn fix. Fly
    is 90 power and occupies two turns, so its throughput is 45 -- and this
    number is the denominator of every clock in the module. Reading it per use
    meant a Pokemon whose biggest number was a two-turn move believed it
    killed twice as fast as it could, which shortened t_kill for the holder
    and lengthened t_die for whoever faced it. Both errors point the same way,
    toward using the charging move, which is why the AI would throw Fly
    twenty-one times in a row and the previous flat penalty never touched it:
    the penalty argued about the move's score while the clock it was scored
    against was itself wrong.
    """
    best = 0.0
    for name, (dealt, accuracy, _healed) in table.items():
        # placeholders from the knowledge ladder are not in list_of_moves and
        # are never charging moves, so an absent entry means no delay
        delay, _exposure = _charge_shape(list_of_moves.get(name))
        best = max(best, dealt * accuracy / (1.0 + delay))
    return best


def _stage_factor(stages):
    """What a stat multiplier becomes after `stages` stages, via the chart."""
    index = max(-6, min(6, int(stages)))
    try:
        return float(modifierChart[1][index])
    except (IndexError, TypeError, ValueError):
        return 1.0


def _stat_gain(array):
    """How much a stat-stage array multiplies offence, and divides incoming.

    Indices follow the engine's `modifier`: 1 Attack, 2 Defence, 3 Special
    Attack, 4 Special Defence, 5 Speed. Offence is the better of the two
    attacking stats because a Pokemon uses whichever suits its moves; defence
    is the average, since it does not choose what is thrown at it.
    """
    if not isinstance(array, list) or not all(
            isinstance(v, (int, float)) for v in array):
        return 1.0, 1.0
    padded = list(array) + [0] * (9 - len(array))
    offence = max(_stage_factor(padded[1]), _stage_factor(padded[3]))
    defence = (_stage_factor(padded[2]) + _stage_factor(padded[4])) / 2.0
    return offence, max(0.1, defence)


def _effect_value(move, me, foe, ground, my_side, foe_side, t_kill, t_die):
    """Turns bought by everything about a move that is not its damage.

    Everything here is expressed as a change to one of the two clocks, which
    is the whole point: a boost that shortens t_kill and a screen that
    lengthens t_die are finally the same kind of thing and can be compared.
    """
    kinds = str(getattr(move, "effect_type", "") or "")
    special = getattr(move, "special_effect", None)
    gained = 0.0
    remaining = max(1.0, min(t_kill, t_die))

    # How much a thing that outlives this matchup is worth. `survival` is the
    # holder's own prospects -- setting up in front of something about to kill
    # you buys nothing, however many opponents are behind it.
    still_standing = sum(1 for p in getattr(foe_side, "team", [])
                         if getattr(p, "status", "") != "Fainted")
    survival = min(1.0, t_die / max(1.0, t_kill))
    sweep = 1.0 + SWEEP_WEIGHT * max(0, still_standing - 1) * survival

    # a status the target cannot take buys nothing, and the engine's own
    # guards already refuse to score these -- this keeps the two in step
    if "target_non_volatile" in kinds and foe.status in ("Normal",):
        name = getattr(special, "__name__", "")
        worth = EFFECT_TURNS.get(name, 0.0)
        if name in ("Paralysis", "Burn", "Poison", "BadPoison"):
            worth *= remaining
        gained += worth * getattr(move, "effect_accuracy", 1.0)
    if "target_volatile" in kinds:
        name = getattr(special, "__name__", "") or str(special)
        worth = EFFECT_TURNS.get(name, 0.0)
        if worth and not foe.volatile_status.get(name, 0):
            gained += worth * remaining * getattr(move, "effect_accuracy", 1.0)

    # stat stages: offence shortens my clock, defence lengthens it
    if "self_modifier" in kinds:
        offence, defence = _stat_gain(special)
        # A boost pays out on later turns, so it is worth nothing at all if
        # there are none. Zero at t_die = 1, full value once the holder can
        # expect SETUP_HORIZON turns of life.
        lives = min(1.0, max(0.0, (t_die - 1.0) / max(0.5, SETUP_HORIZON - 1.0)))
        if offence > 1.0:
            gained += (t_kill - (t_kill / offence)) * sweep * lives
        if defence > 1.0:
            gained += t_die * (defence - 1.0) * sweep * lives
    if "opponent_modifier" in kinds:
        # negate only a flat numeric array -- `special_effect` holds twelve
        # shapes across the move table, nested lists among them, and unary
        # minus on a list raises. Same family as the four guards in the engine
        # that compared a list to a string and were therefore always true.
        flipped = special
        if isinstance(special, list) and all(
                isinstance(v, (int, float)) for v in special):
            flipped = [-v for v in special]
        offence, defence = _stat_gain(flipped)
        if offence > 1.0:
            gained += t_die * (1.0 - 1.0 / offence)
        if defence > 1.0:
            gained += t_kill - (t_kill / defence)

    if "self_team_buff" in kinds:
        # a screen covers the whole side for five turns, not just this Pokemon
        gained += SCREEN_TURNS * sweep
    if "apply_entry_hazard" in kinds:
        # already a team-wide effect by construction: every arrival pays it
        gained += HAZARD_TURNS_PER_ARRIVAL * max(0, still_standing - 1)
    if "self_heal" in kinds or "hp_draining" in kinds:
        # Healing buys turns on my own clock -- but only up to a point, and
        # this was `t_die * 0.4` uncapped, which made Recover worth two turns
        # against a slow opponent and the second most-picked move in the game.
        # Padding the fight does not win it; the cap says so.
        gained += min(1.0, t_die * 0.25)
    if "user_protection" in kinds:
        gained += 0.5

    return max(-EFFECT_CEILING, min(EFFECT_CEILING, gained))


def _turns_of(odds):
    """The margin behind a set of odds -- the inverse of _win_odds.

    Needed because a couple of adjustments are naturally expressed in turns
    (priority, the turn a switch costs) and adding them to a probability
    would be adding a length to a proportion.
    """
    odds = min(1.0 - 1e-9, max(1e-9, odds))
    return math.log(odds / (1.0 - odds)) / RACE_SHARPNESS


def _win_odds(margin):
    """The race margin as odds of winning it. See RACE_SHARPNESS."""
    margin = max(-RACE_CEILING, min(RACE_CEILING, margin))
    return 1.0 / (1.0 + math.exp(-RACE_SHARPNESS * margin))


def _race_after(dealt, accuracy, foe_health, my_output, t_die, effect_turns,
                delay=0.0, exposure=0.0):
    """The race margin after a candidate resolves, in turns.

    The expectation over accuracy is what prices a risky move honestly: with
    probability `accuracy` the target is that much closer to falling, and with
    the rest the turn bought nothing at all. A 70% move is not "70% of the
    damage" -- it is a 30% chance of having wasted the turn, which is a
    different and larger cost.

    `delay` and `exposure` are how a two-turn move is billed, and billing it
    here rather than as a penalty on its score is the point. A charging move
    is not a normal move worth slightly less; it is a move that arrives on a
    different turn, and a turn currency can simply say so:

        the kill clock  runs `delay` turns longer, in *both* branches -- a Fly
                        that kills still takes two turns to do it
        my own clock    runs `delay * exposure` turns shorter, because that is
                        free time handed to the opponent

    The consequence is that the cost scales with the situation instead of
    being flat. A charging move that finishes the target is barely punished:
    the extra turn is all it costs. One that leaves the target standing is
    punished twice, once on each clock -- which is exactly the case the flat
    penalty could not separate, and exactly the case the AI was getting wrong.
    """
    landed = delay + _turns_to(foe_health - dealt, my_output)
    missed = delay + _turns_to(foe_health, my_output)
    # a landed kill also removes the thing that was going to kill me
    relief = KO_RELIEF if dealt >= foe_health > 0 else 0.0
    # the charge turn is a turn of mine the opponent gets to use
    t_die = t_die - delay * exposure

    # The expectation is taken over the *odds*, not over the turns. Averaging
    # turns first and converting once is the utility of the average outcome,
    # which is not the average utility -- and the difference is exactly the
    # risk in a 70% move: a miss does not cost 30% of a turn, it costs a whole
    # turn 30% of the time, and those are not the same bet.
    odds_landed = _win_odds((t_die + effect_turns + relief) - landed)
    odds_missed = _win_odds((t_die + effect_turns) - missed)
    return accuracy * odds_landed + (1.0 - accuracy) * odds_missed


def _matrix_choice(candidates, their_hits, my_health, their_output):
    """Tier 3: one ply over what the opponent might do about it.

    Pokemon is a simultaneous-move game, so the honest question is not "what is
    my best move" but "what is my best move given theirs". Each cell is pure
    arithmetic over damage tables computed once, so the whole matrix costs less
    than one extra estimator call.

    Scored pessimistically -- the worst reply, not the average. An AI that
    plans against the average reply walks into the one move that beats it, and
    against a competent opponent the worst case is the one that arrives.
    """
    # per turn, as in _output: a reply that spends two turns charging is not
    # a reply that can hurt me next turn, and taking the worst case over
    # per-use damage made every Solar Beam user look like a sprinter
    replies = [dealt * accuracy / (1.0 + _charge_shape(list_of_moves.get(name))[0])
               for name, (dealt, accuracy, _h) in their_hits.items()]
    worst = max(replies) if replies else their_output
    ranked = []
    survives = _turns_to(my_health, max(MIN_DAMAGE, worst))
    for name, margin, dealt, accuracy in candidates:
        # the reply is priced in turns off my own clock, then converted --
        # the first version added this straight onto a probability
        ranked.append((_win_odds(_turns_of(margin) + min(1.0, survives / 4.0)),
                       name, dealt, accuracy))
    ranked.sort(key=lambda row: (-row[0], -row[2] * row[3]))
    return ranked


def choose(battleground, protagonist, ai, estimator, switch_chooser, kit=None):
    """The turn-currency move choice. Returns a Move, as the engine expects.

    `estimator` and `switch_chooser` are handed in rather than imported so this
    module never imports ai.py -- ai.py imports this one, and Scripts/ is full
    of `from x import *`, where a cycle is a silent half-built namespace rather
    than an ImportError.
    """
    me, foe = ai.team[0], protagonist.team[0]

    # Where a switch would go, settled before anything can return.
    #
    # The engine reads `competitor.position_change` after the fact to find out
    # which Pokemon to bring in, and the scorer this replaced set it on every
    # single call -- so it was always there. Setting it only on the turns that
    # switch left the attribute missing entirely, and battle_cycle raised
    # AttributeError partway through a 25,560-battle round robin. Nothing in
    # the 58-suite run caught it, because a forced switch after a faint is the
    # path that reads it and the suites rarely reach one.
    ai.position_change = 0

    # committed to Fly or Dig: there is no decision to make
    if getattr(me, "charging", ["", "", 0])[0]:
        return list_of_moves[me.charging[0]]

    # What the opponent looks like from here. Everything below reads `seen`
    # rather than `foe`, so a Low-tier trainer plans against a Pokemon it has
    # only partly worked out -- while the *engine* still resolves the turn
    # against the real one. That gap is the difficulty.
    seen = believed(foe, ai)
    theirs = ai_knowledge.sees_character_ability(ai)
    # want_heal only on my own moves: what their attacks give *them* back
    # does not change which of mine I should use, and the copy it costs is
    # not free.
    my_hits = _hits(estimator, ai, protagonist, me, seen, battleground,
                    kit, theirs, want_heal=True)
    their_hits = _hits(estimator, protagonist, ai, seen, me, battleground,
                       kit, theirs)
    my_output = _output(my_hits)
    their_output = _output(their_hits)

    # health is never fogged: the bar is on screen for both sides
    foe_health = max(0.0, float(foe.battle_stats[0]))
    my_health = max(0.0, float(me.battle_stats[0]))
    t_kill = _turns_to(foe_health, my_output)
    t_die = _turns_to(my_health, their_output)

    disabled = getattr(me, "disabled_moves", {}) or {}
    candidates = []
    for name in getattr(me, "moveset", []):
        if name == "Switching" or name in disabled or name not in list_of_moves:
            continue
        move = list_of_moves[name]
        dealt, accuracy, healed = my_hits.get(name, (0.0, 1.0, 0.0))
        gained = _effect_value(move, me, seen, battleground, ai, protagonist,
                               t_kill, t_die)
        if getattr(move, "attack_type", "") != "Status":
            gained *= RIDER_WEIGHT
        # A Frenzy lock confuses its own user when it ends, and that is the
        # only thing a Frenzy move costs. Charged once, here, at the moment of
        # committing: every later turn of the lock returns early above.
        if str(getattr(move, "charging", "") or "") == "Frenzy":
            gained -= FRENZY_TAIL
        # health handed back is time bought, in the one unit this AI has
        if healed > 0 and their_output > 0:
            gained += min(EFFECT_CEILING, healed / their_output) * accuracy
        delay, exposure = _charge_shape(move)
        margin = _race_after(dealt, accuracy, foe_health, my_output, t_die,
                             gained, delay, exposure)
        # moving first is worth something only while the race is tight
        if getattr(move, "priority", 0) > 0 and abs(t_die - t_kill) <= 1.5:
            # in odds now, so the bonus has to be converted rather than added
            margin = _win_odds(_turns_of(margin) + PRIORITY_TURNS)
        candidates.append((name, margin, dealt, accuracy))

    if not candidates:
        return list_of_moves["Switching"]

    ranked = _matrix_choice(candidates, their_hits, my_health, their_output)
    best_margin, best_name = ranked[0][0], ranked[0][1]

    # Switching is worth taking only if standing here is losing. Priced the
    # same way as everything else: what the replacement's race looks like,
    # less the free hit the opponent gets on the way in.
    if getattr(ai, "switching", 0) < 2 and best_margin < SWITCH_TRIGGER:
        position = switch_chooser(protagonist, ai, battleground, recall=True,
                                  forced_switch=False, incoming_move=0)
        if position:
            bench = ai.team[position] if position < len(ai.team) else None
            if bench is not None and getattr(bench, "status", "") != "Fainted":
                arriving = _hits(estimator, ai, protagonist, bench, seen,
                                 battleground, kit, theirs)
                incoming = _hits(estimator, protagonist, ai, seen, bench,
                                 battleground, kit, theirs)
                margin = (_turns_to(float(bench.battle_stats[0]),
                                    _output(incoming))
                          - _turns_to(foe_health, _output(arriving)))
                # charged in turns, then converted -- see SWITCH_COST
                margin = _win_odds(margin - SWITCH_COST)
                if margin > best_margin:
                    ai.position_change = position
                    ai.switching = getattr(ai, "switching", 0) + 1
                    return list_of_moves["Switching"]

    ai.switching = 0

    # A deliberate misplay rate, off unless a competitor asks for it. This is
    # how a weak character should be weak: the same understanding of the game,
    # applied unreliably -- not a worse evaluator, which makes them incoherent
    # rather than fallible.
    misplay = float(getattr(ai, "misplay", 0.0) or 0.0)
    if misplay > 0 and len(ranked) > 1 and random.random() < misplay:
        return list_of_moves[random.choice([row[1] for row in ranked[1:]])]

    return list_of_moves[best_name]
