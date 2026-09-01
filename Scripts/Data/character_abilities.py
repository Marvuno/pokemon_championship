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
from Scripts.Battle.constants import (FOE_ARRIVAL_PHASE, GUARANTEE_ACCURACY,
                                      ORDER_PHASE, SYLVAN_SEED,
                                      TEAM_BUFF_TURNS, blocks_seeding)
from Scripts.Battle.fastcopy import fast_copy
from Scripts.Data.competitors import ability_text
from Scripts.Art import narrator


#: Serene Grace doubles a secondary effect but never past this. A move
#: already at or above the cap is left alone, so nothing it touches can
#: become a certainty -- doubling used to clamp to 1.0, which made a 50%
#: effect land every time.
SERENE_GRACE_CEILING = 0.8

#: How many stages of priority Assassination is worth while its Pokemon is
#: untouched. One, so it beats an ordinary move and still loses to a real
#: priority move -- Extreme Speed at +2 goes first either way.
ASSASSINATION_PRIORITY = 1

#: Sparking Cascade's per-turn paralysis roll, and the types the current
#: does not reach: Flying is not standing in it, Ground earths it, Electric
#: is made of it.
SPARKING_CASCADE_CHANCE = 0.1
SPARKING_CASCADE_IMMUNE = frozenset(("Flying", "Ground", "Electric"))

#: Killer Instinct's chance of doubling a hit.
KILLER_INSTINCT_CHANCE = 0.1

#: Blunders' chance of flattening a hit to a straight 1x.
BLUNDERS_CHANCE = 0.1

#: Overloaded's chance of a move going off twice in the one turn.
OVERLOADED_CHANCE = 0.2

#: How often Primordial checks that it is still raining, in turns.
PRIMORDIAL_REFRESH_TURNS = 10

#: What Primordial multiplies its holders' Speed by while it is raining.
#: It used to hand out Swift Swim, which doubles; x1.5 still usually wins
#: the turn but a genuinely fast Pokemon can get above it.
PRIMORDIAL_RAIN_SPEED = 1.5

#: Gargantuan's chance of halving an incoming hit.
GARGANTUAN_CHANCE = 0.15

#: Moody's swing, and the two chances: a tenth of the time it heals the
#: opponent, a fifth of the time it hurts them.
MOODY_FRACTION = 0.10
MOODY_HEAL_CHANCE = 0.10
MOODY_HURT_CHANCE = 0.20

#: What fraction of the damage dealt Blood Magic drains back as HP.
BLOOD_MAGIC_DRAIN = 0.33

#: Brain Wave's multipliers for Psychic moves: damage, then effect chance.
BRAIN_WAVE_DAMAGE = 1.5
BRAIN_WAVE_EFFECT = 1.3

#: The types Tenebrous sharpens.
TENEBROUS_TYPES = ("Dark", "Ghost")

#: How far Tension Release pushes its user down the order. Deeply negative
#: rather than -1: forcing the other side to switch is worth a turn of
#: initiative, and the move should land after whatever they were going to do.
TENSION_RELEASE_PRIORITY = -10

#: Anger Point's reward, in stages, to Attack and Special Attack each.
ANGER_POINT_STAGES = 2

#: How long Torment locks a move away, in turns of lockout.
#:
#: The counter is read when the move is *chosen* and ticked down
#: afterwards, in `user_turn_in_battle_stats`, so the number is
#: simply how many turns the move is unavailable for: 1 means
#: used this turn, gone next turn, back the turn after. It was 2,
#: which held the move away for two turns rather than one.
TORMENT_TURNS = 1

#: The stat slots a "random stat" may touch. `modifier` is
#: [HP, Atk, Def, SpA, SpDef, Speed, Evasion, Accuracy, Crit] -- HP is not a
#: stage at all and the crit slot is a different kind of thing, so a roll
#: that included either produced a stat change that did nothing visible.
RANDOM_STAT_SLOTS = (1, 2, 3, 4, 5, 6, 7)

#: Moves Overloaded and Wizardry must not set off a second time. A two-turn
#: move would start a fresh charge on top of the one it just committed to; a
#: protective move that is already up cannot be re-raised and in the real
#: games fails outright on consecutive use; switching out twice is
#: meaningless; and a move that is itself a random move would recurse.
NO_SECOND_HELPING = frozenset((
    "Switching", "Metronome", "Fly", "Dig", "Dive", "Bounce", "Phantom Force",
    "Shadow Force", "Solar Beam", "Sky Attack", "Razor Wind", "Skull Bash",
    "Protect", "Detect", "King's Shield", "Baneful Bunker", "Spiky Shield",
    "Endure", "Wide Guard", "Quick Guard",
))


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
            move.effect_accuracy = min(SERENE_GRACE_CEILING,
                                       move.effect_accuracy * 2)
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
            # `turn` is 0 until `move_selection` starts the first turn, and
            # switching in at the start of the battle happens before that.
            # So 0 means 'the battle has not begun'; 1 means the first turn
            # is already being played, and a Pokemon arriving then is a
            # mid-battle switch that must not re-lay the ground.
            if (battleground.turn < 1
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

    def anger_point(*args):
        """Being crit, or being poisoned, is answered with force.

        Attack and Special Attack both up by ANGER_POINT_STAGES. Fires on
        the hit that *lands* the status rather than on merely having one, or
        it would go off again every turn the status lasted -- which is why it
        asks the move what it was carrying instead of only asking the Pokemon
        how it feels.
        """
        crit = bool(getattr(move, "critical_hit", False))
        statusing = "target_non_volatile" in str(getattr(move, "effect_type",
                                                         ""))
        newly_statused = statusing and user.status not in ("Normal", "Fainted")
        if not (crit or newly_statused):
            return
        user.applied_modifier = [0, ANGER_POINT_STAGES, 0,
                                 ANGER_POINT_STAGES, 0, 0, 0, 0, 0]
        _stages_before = list(user.modifier)
        user.modifier = list(map(operator.add, user.applied_modifier,
                                 user.modifier))
        narrator.stat_change(user, _stages_before, user.modifier,
                             user.applied_modifier, battleground)
        notice(battleground, user_side)

    def tension_release(*args):
        """A plain hit shoves the other side off the field.

        Three phases, and the third one is the whole reason this is not
        simpler.

        Phase 2 drops the move's priority to TENSION_RELEASE_PRIORITY, so it
        always resolves last -- forcing a switch is worth a turn of
        initiative. Phase 6 notes that a *non*-super-effective hit landed.
        Phase 8, the end of the turn, is where the switch actually happens.

        **The switch cannot happen mid-turn**, and this is not caution. The
        first cut swapped `team[0]` the moment the move landed, at phase 6.
        Both sides choose their moves at the top of a turn, so the Pokemon
        being dragged out still had one pending -- and the replacement
        executed it. Measured: 25 moves in 60 battles were carried out by a
        Pokemon that did not know them, and none at all with this ability
        taken out of the field. End of turn is after both sides have acted,
        so there is nothing left to misattribute.

        It also goes through `switching_mechanism` rather than swapping the
        list by hand, so the Pokemon leaving gets the cleanup every other
        switch gives it -- stat stages, charge, volatile status, typing.
        """
        if abilityphase == ORDER_PHASE:
            move.priority = TENSION_RELEASE_PRIORITY
            notice(battleground, user_side)
            return

        if abilityphase == 6:
            # Remember, act later. `super_effective` is set by the damage
            # calculation for the hit that just happened.
            if not getattr(move, "super_effective", False):
                battleground._tension_release_owed = True
            return

        # phase 8 -- the end of the turn
        if not getattr(battleground, "_tension_release_owed", False):
            return
        battleground._tension_release_owed = False
        team = target_side.team
        bench = [index for index, mon in enumerate(team)
                 if index > 0 and mon.status != "Fainted"]
        if not bench or team[0].status == "Fainted":
            return                      # nobody to bring in, or already gone
        # Imported here, not at the top: switching reaches back into the
        # battle modules that import this one, so a module-level import
        # closes the circle.
        from Scripts.Battle.switching import switching_mechanism
        chosen = random.choice(bench)
        going = team[0].name
        team[0] = switching_mechanism(target_side, user_side, battleground,
                                      team, user_side.team, chosen, False)
        if battleground.reality:
            narrator.say(f"{going} is dragged out! "
                         f"{team[0].name} is forced in.", "switch",
                         pokemon=team[0].name)
        notice(battleground, user_side)

    def _repeatable(candidate):
        """Is this a move an ability may make happen more than once?

        NO_SECOND_HELPING is the list and the reasoning is written on it.
        Three more conditions on top, all of them the same idea -- a move
        only counts once it has actually *happened*:

        * **Not a switch.** Swapping out is not a move to double.
        * **Not a charge turn.** A Pokemon half-way through Fly or Dig has
          committed to something, not landed it; `user.charging` still being
          set is how the engine says so. It is eligible on the turn it comes
          down, which is the turn the charge clears.
        * **Nothing while a repeat is already running**, or the repeat would
          queue another and the turn would never end.

        Whether the move *succeeded* is not knowable here -- these fire as
        the move goes off, not after -- so the engine makes that check
        itself, at the point where it knows. See the note beside
        `encore_move` in battle_checklist.
        """
        if candidate is None or candidate.name == "Switching":
            return False
        if getattr(battleground, "encore_running", False):
            return False
        if candidate.name in NO_SECOND_HELPING:
            return False
        if getattr(candidate, "charging", "") in ("Charging",
                                                  "Semi-invulnerable",
                                                  "Frenzy"):
            return False
        if user.charging[0] != "":
            return False
        return user.status != "Fainted" and target.status != "Fainted"

    def wizardry(*args):
        """Every move is followed by another one, drawn at random.

        Metronome's own list, minus Metronome, so the second move can be
        anything in the game -- and a fresh copy of it, because everything
        downstream writes its working state onto the move it is handed and
        the entries of list_of_moves are shared by every Pokemon alive.
        """
        if not _repeatable(move):
            return
        pool = sorted(set(list_of_moves.keys()) - NO_SECOND_HELPING)
        if not pool:
            return
        # A fresh copy: everything downstream writes its per-use working
        # state onto the move it is handed, and the entries of list_of_moves
        # are shared by every Pokemon in the game.
        # On the *Pokemon*, not the battleground. This is the whole of the
        # fix for a bug that read as "the opponent's ability worked for me".
        #
        # The slot used to be `battleground.encore_move`, which is shared by
        # both sides, and `move_order_and_execution` gives it to whoever
        # finishes a move next. Two things then went wrong at once. The AI
        # scores its candidates by running this very code with `reality`
        # off, so Mivy queued the move while merely *thinking* about one --
        # and a player using a priority move then moved first and collected
        # it, leaving Mivy's own turn to find the slot already emptied.
        #
        # Hanging it on the Pokemon fixes both by construction rather than
        # by a guard: the scorer works on `fast_copy` of the Pokemon, so a
        # write during scoring lands on a copy that is thrown away, and a
        # slot that belongs to one Pokemon cannot be read by the other side.
        user.encore_move = fast_copy(list_of_moves[random.choice(pool)])
        notice(battleground, user_side)

    def overloaded(*args):
        """Now and then a move lands an extra time -- like Double Hit.

        One more *strike* inside the move's own execution, not a second move.
        The first cut ran the whole move again through
        `move_order_and_execution`, which is a different thing entirely: it
        took another slot in the turn, so the holder appeared to move twice
        and the order of the turn came out wrong.

        `multi[1]` is the strike count the loop in
        `battle_checklist.move_order_and_execution` runs on, and
        `compare_speed` has already rolled it by the time this fires -- so
        adding one is exactly "one more hit". An ordinary move goes from one
        strike to two, which is the ability as described; a move that already
        strikes several times gets one more rather than being cut down to
        two.
        """
        if random.random() >= OVERLOADED_CHANCE:
            return
        if not _repeatable(move):
            return
        move.multi[1] = int(move.multi[1] or 1) + 1
        if battleground.reality:
            narrator.say(f"{move.name} strikes an extra time!", "ability")
        notice(battleground, user_side)

    def torment(*args):
        """The other side cannot repeat itself. The holder is unaffected.

        A move the opponent has just used is locked for the following turn,
        which is how the engine already says "you cannot pick that": the
        counter in `disabled_moves` is read when a move is chosen and ticked
        down afterwards, so TORMENT_TURNS of 1 means used this turn, gone
        next turn, back the turn after.

        Phase 7 -- "after taking damage", with the turn flipped, so `user`
        is the holder and `target` is whoever attacked them; the move being
        locked away is the attacker's.

        **Not phase 3.** Phase 3 fires at battle_checklist.py:164, five
        lines before `move_fail_checklist_before_execution` refuses a move
        that is in `disabled_moves` -- so the lock landed on the move that
        was *still being used*, and the engine then threw it out. Every
        attack the other side made failed on the turn it was made. Measured:
        the opponent dealt **zero** damage across 332 turns of ten battles,
        and a Torment holder rated 20 beat the entire roster. Phase 7 runs
        after the move has resolved, which is what "cannot use it twice in
        a row" actually means.

        It fired on phase 2 as well at first, which tormented the holder's
        own Pokemon too and made battles roughly four times longer, both
        sides forever reaching for a move they had just spent.
        """
        if move is None or getattr(move, "name", "Switching") == "Switching":
            return
        if target is None or target.status == "Fainted":
            return
        if target.disabled_moves.get(move.name, 0) >= TORMENT_TURNS:
            return                      # already locked; do not re-announce
        target.disabled_moves[move.name] = TORMENT_TURNS
        if battleground.reality:
            narrator.say(f"{target.name} cannot use {move.name} twice in a "
                         f"row!", "fail")
        notice(battleground, user_side)

    def synchronize_drops(*args):
        """The holder's losses are shared out; the other side's gains are taken.

        Two halves, both one-way:

            what fell on the holder      is also made to fall on the target
            what rose on the target      also rises on the holder

        so the holder never spreads a blessing and never keeps a curse to
        itself. A stat that rose on the holder is its own, and a stat that
        fell on the target is the target's problem.

        Worked out by comparing each side's stages against a snapshot taken
        at the top of the turn rather than by catching each change as it
        happens. Stat changes come from a dozen places -- moves, abilities,
        items, the holder's own other ability -- and hooking them all would
        mean finding them all; the difference across a turn catches every one
        of them by construction.
        """
        # Each snapshot remembers *whose* it is. A stat change is the
        # difference between two readings of the same Pokemon, and the
        # Pokemon standing there can change in between: a switch chosen as
        # the turn's move, a replacement sent out after a faint, or a forced
        # switch from another character ability. Comparing the outgoing
        # Pokemon's stages against the incoming one's reports a change that
        # never happened -- a Pokemon recalled at +2 Attack read as a
        # two-stage drop and Synchronize inflicted it on the other side.
        # Measured at 6 mismatches in 532 firings over 30 battles.
        if abilityphase == ORDER_PHASE:
            battleground.sync_before = (user, list(user.modifier))
            battleground.sync_foe_before = (
                (target, list(target.modifier)) if target is not None else None)
            return
        # end of turn: what went down here, and what went up over there?
        mine = getattr(battleground, "sync_before", None)
        theirs = getattr(battleground, "sync_foe_before", None)
        battleground.sync_before = battleground.sync_foe_before = None
        if target is None or target.status == "Fainted":
            return
        # A snapshot of somebody else is no snapshot at all -- but the right
        # answer is not to give up on the turn, it is to read the Pokemon
        # that *is* standing there from where it started. Switching resets
        # the stat stages, so a Pokemon that arrived this turn began it on
        # zeroes; comparing against those is exactly "what has been done to
        # it since it came in". Discarding the turn instead meant the ability
        # only woke up on the turn *after* a switch, and an Intimidate on the
        # way in was never shared.
        fresh = [0] * 9
        before = mine[1] if mine and mine[0] is user else fresh
        foe_before = theirs[1] if theirs and theirs[0] is target else fresh

        # the curse, spread outwards
        if before:
            drops = [min(0, now - was)
                     for was, now in zip(before, user.modifier)]
            if any(drops):
                target.applied_modifier = drops
                _theirs = list(target.modifier)
                target.modifier = list(map(operator.add, drops,
                                           target.modifier))
                narrator.stat_change(target, _theirs, target.modifier,
                                     target.applied_modifier, battleground)
                notice(battleground, user_side)

        # the blessing, taken. Read against `target.modifier` as it stands
        # *now* -- which already includes any drop just written above, so a
        # stat cannot be counted twice.
        if foe_before and user.status != "Fainted":
            gains = [max(0, now - was)
                     for was, now in zip(foe_before, target.modifier)]
            if any(gains):
                user.applied_modifier = gains
                _mine = list(user.modifier)
                user.modifier = list(map(operator.add, gains, user.modifier))
                narrator.stat_change(user, _mine, user.modifier,
                                     user.applied_modifier, battleground)
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
        # A random swing to the *opponent's* health -- `target` is the other
        # side, which is what makes this an attack rather than a liability:
        # it hurts them twice as often as it helps them.
        random_factor = random.random()
        if random_factor <= MOODY_HEAL_CHANCE:
            target.battle_stats[0] += math.floor(min(target.hp - target.battle_stats[0], target.hp * MOODY_FRACTION))
            notice(battleground, user_side)
        elif random_factor >= 1 - MOODY_HURT_CHANCE:
            target.battle_stats[0] -= math.floor(target.hp * MOODY_FRACTION)
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
        """Psychic moves hit harder, on ground that suits them.

        Phase 1 lays Psychic Terrain at the start of the battle -- the
        battle, not every switch-in, so it still lapses the way any terrain
        does. The turn check is the one Sparking Cascade and Light Speed
        use, and for the same reason.

        The terrain is not decoration: it is another x1.3 on Psychic moves
        for anything standing on it, and it stops priority moves reaching
        the ground, which is what a Psychic specialist most needs. Raising
        the damage multiplier alone was measured and did not reach -- the
        holder simply does not throw enough Psychic moves for the number to
        matter, so the ground does the work instead.
        """
        if abilityphase == 1:
            # 0 is 'before the first turn'; see sparking_cascade above
            if (battleground.turn < 1
                    and terrain.current(battleground) != "Psychic"):
                battleground.terrain = "Psychic"
                battleground.terrain_turn = terrain.NATURAL_TURNS
                if battleground.reality:
                    narrator.say(terrain.TERRAIN_ARRIVES["Psychic"],
                                 "weather", terrain="Psychic")
                notice(battleground, user_side)
            return
        if 'Psychic' in move.type:
            move.damage *= BRAIN_WAVE_DAMAGE
            move.effect_accuracy *= BRAIN_WAVE_EFFECT
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
        # boost additional effect chance and damage for dark and ghost moves
        if any(kind in move.type for kind in TENEBROUS_TYPES):
            move.damage *= 1.3
            move.effect_accuracy *= 1.3
            notice(battleground, user_side)

    def barbaric(*args):
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
        # last pokemon has 3 lives: twice on fainting it comes back on
        # half its maximum HP rather than a full bar
        if abilityphase == 1:
            if sum(1 for pokemon in user_side.team if pokemon.status != 'Fainted') == 1:  # last pokemon
                user.second_life = 2
        elif abilityphase == 5 and battleground.reality:
            if move.damage > user.battle_stats[0] and user.second_life > 0:
                user.second_life -= 1
                move.damage = 0
                user.battle_stats[0] = math.floor(user.hp / 2)
                notice(battleground, user_side)
        elif abilityphase in (7, 8):
            if user.battle_stats[0] <= 0 and user.second_life > 0:
                user.second_life -= 1
                user.battle_stats[0] = math.floor(user.hp / 2)
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
            # The divisor is the holder's *current* HP, which is 0 the moment
            # it faints -- and phase 4 still runs on a Pokemon that has just
            # been knocked out by recoil or a hazard, so this divided by zero.
            # Both simulation harnesses suppress exceptions, so it showed up
            # as a truncated battle rather than as a crash.
            own = max(1, user.battle_stats[0])
            move.damage = math.floor(move.damage * min(1.7, max(1, target.battle_stats[0] / own)))  # at most 1.7x
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
        if random.random() <= GARGANTUAN_CHANCE:
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
        """The battle is fought on a live floor, and nothing earths it.

        Two halves. Phase 1 lays Electric Terrain at the start of the
        battle -- the battle, not every switch-in, so it can still lapse the
        way any other terrain does; the turn check is the same one Sparking
        Cascade uses and for the same reason.

        Phase 3 makes the holder's Pokemon immune to Ground. It is done with
        `abilitymodifier`, the way Flash Fire and Bulletproof refuse a type,
        and *not* by handing out Levitate -- Levitate clears
        `volatile_status['Grounded']`, and `terrain.is_grounded` reads that,
        so a Levitate holder gets none of the Electric Terrain standing
        under it. The two halves would have cancelled each other out.
        """
        if abilityphase == 1:
            # 0 is 'before the first turn'; see sparking_cascade above
            if (battleground.turn < 1
                    and terrain.current(battleground) != "Electric"):
                battleground.terrain = "Electric"
                battleground.terrain_turn = terrain.NATURAL_TURNS
                if battleground.reality:
                    narrator.say(terrain.TERRAIN_ARRIVES["Electric"],
                                 "weather", terrain="Electric")
                notice(battleground, user_side)
        elif abilityphase == 3:
            if move.type == 'Ground':
                move.abilitymodifier = 0
                notice(battleground, user_side)

    def killer_instinct(*args):
        # random chance to deal double damage
        if random.random() <= KILLER_INSTINCT_CHANCE:
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
        """A fumbled hit lands flat: 1x, whatever the type chart said.

        Stat stages, weather, items and the rest still apply -- only the
        type multiplier is undone, by dividing out the number
        `check_type_effectiveness` recorded on the move. So a super
        effective hit is halved and a doubly-super one quartered, which is
        the point of it.

        It used to redirect the whole hit onto the target instead, which
        was far stronger than a fumble should be.
        """
        if random.random() > BLUNDERS_CHANCE:
            return
        effectiveness = getattr(move, "type_effectiveness", 1) or 1
        if effectiveness == 1 or move.damage <= 0:
            return                       # nothing to flatten
        # Clamped so it can only ever take damage away. Flattening to 1x cuts
        # both ways on its own -- a resisted hit would come out *stronger* --
        # and a fumble that sometimes helps the attacker is not a fumble.
        move.damage = min(move.damage, int(move.damage / effectiveness))
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
        # and nothing laid on the floor sticks. Phase 1 runs from
        # `switched_in_initialization`, which `switching_mechanism` calls
        # *before* `entry_hazard_effect` -- so clearing here is immunity
        # rather than a late tidy-up.
        if sum(user_side.entry_hazard.values()) > 0:
            user_side.entry_hazard = dict.fromkeys(user_side.entry_hazard.keys(), 0)
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
        """Immune to Fairy, and the old order asserts itself on arrival.

        One random stat up for its own Pokemon and one random stat down for
        whoever it is facing -- HP and the crit slot excluded from both,
        since neither is a stage that a stat change can move.
        """
        if abilityphase == 1:
            user.applied_modifier = [0] * 9
            user.applied_modifier[random.choice(RANDOM_STAT_SLOTS)] += 1
            _stages_before = list(user.modifier)
            user.modifier = list(map(operator.add, user.applied_modifier,
                                     user.modifier))
            narrator.stat_change(user, _stages_before, user.modifier,
                                 user.applied_modifier, battleground)
            if target is not None and target.status != "Fainted":
                target.applied_modifier = [0] * 9
                target.applied_modifier[random.choice(RANDOM_STAT_SLOTS)] -= 1
                _theirs_before = list(target.modifier)
                target.modifier = list(map(operator.add,
                                           target.applied_modifier,
                                           target.modifier))
                narrator.stat_change(target, _theirs_before, target.modifier,
                                     target.applied_modifier, battleground)
            notice(battleground, user_side)
        elif abilityphase == 5:
            if 'Fairy' in move.type and move.damage > 0:
                move.damage = 0
                notice(battleground, user_side)

    def blood_magic(*args):
        # Drains a third of the damage *actually dealt*, capped at the
        # holder's own missing HP.
        #
        # The two caps do different jobs and both are needed. `min(target
        # HP, 0)` is the overkill: this fires on phase 6, after the hit has
        # been taken off, so a 300-damage blow on a target with 10 HP leaves
        # it at -290 and the sum comes back to the 10 that were really
        # there. Without it, hitting a nearly-dead Pokemon would heal as
        # much as felling a healthy one. The outer `min` stops the drain
        # overflowing the holder's own maximum.
        if move.damage > 0:
            dealt = move.damage + min(target.battle_stats[0], 0)
            user.battle_stats[0] += min(user.hp - user.battle_stats[0],
                                        math.floor(dealt * BLOOD_MAGIC_DRAIN))
            notice(battleground, user_side)

    def primordial(*args):
        """Rain, quicker in it, and rain again if anybody clears it.

        The opening downpour was a one-off: anything that changed the
        weather afterwards -- another competitor's ability, a weather move --
        left the holder with a rain bonus that did nothing for the rest of
        the battle. It checks back every PRIMORDIAL_REFRESH_TURNS now.

        The speed half used to be a granted Swift Swim, which doubles. It is
        PRIMORDIAL_RAIN_SPEED applied here instead, for two reasons: x2
        guaranteed the holder the turn outright, and handing out a *Pokemon*
        ability meant the size of the bonus lived in another file. It fires
        on ORDER_PHASE because that is the only phase that runs before the
        turn order is worked out -- on any of 1..9 the multiplication lands
        after `compare_speed` has already read the stat, which is exactly
        how Swift Swim came to be silently inert.
        """
        if abilityphase == 0:
            battleground.starting_weather_effect = 'Rain'
            battleground.weather_effect = battleground.starting_weather_effect
        elif abilityphase == ORDER_PHASE:
            if battleground.weather_effect == 'Rain':
                user.battle_stats[5] = math.floor(
                    user.battle_stats[5] * PRIMORDIAL_RAIN_SPEED)
        elif abilityphase == 8:
            if (battleground.turn % PRIMORDIAL_REFRESH_TURNS == 0
                    and battleground.weather_effect != 'Rain'):
                battleground.starting_weather_effect = 'Rain'
                battleground.weather_effect = 'Rain'
                battleground.artificial_weather = False
                if battleground.reality:
                    narrator.say(weather_desc['Rain'], "weather",
                                 weather="Rain")
                notice(battleground, user_side)

    def assassination(*args):
        """Strikes first, while it is untouched.

        ORDER_PHASE, not phase 2: the speed comparison reads `move.priority`
        and phase 2 fires after a Pokemon is already taking its turn, which
        is too late to change who goes first. See the note on ORDER_PHASE --
        Swift Swim and Prankster were both silently inert for exactly this
        reason.

        "Full HP" is read at the moment the order is decided, so trading a
        hit costs the edge for the rest of the battle unless something heals
        it back to the top.
        """
        if abilityphase != ORDER_PHASE:
            return
        # `hp` is the maximum and `battle_stats[0]` the current one, which is
        # the pair Sturdy compares too.
        if user.battle_stats[0] < user.hp:
            return
        move.priority += ASSASSINATION_PRIORITY
        notice(battleground, user_side)

    def aurora_borealis(*args):
        """The battle opens in hail, with the veil already up.

        Phase 1 and the turn check, the same shape Light Speed uses: the
        start of the *battle*, not every switch-in, so the veil runs its
        clock down and the hail can be replaced like any other weather.

        The veil is put up directly rather than by playing Aurora Veil,
        because the move refuses to work outside hail (see
        move_additional_effect) and the two would race on the opening turn.
        """
        if abilityphase != 1 or battleground.turn >= 1:
            return
        battleground.weather_effect = "Hail"
        battleground.weather_artificial = True
        user_side.in_battle_effects["Aurora Veil"] = TEAM_BUFF_TURNS
        narrator.say("A polar light rises, and the hail closes in!",
                     "weather")
        notice(battleground, user_side)

    def sylvan_sprout(*args):
        """Anything that walks in gets seeded.

        Fires on FOE_ARRIVAL_PHASE, which is the other side switching in --
        phase 1 would be this trainer's own arrivals, which is the opposite
        of what this does. `target` is the Pokemon that just arrived,
        because the call is flipped (see battle_initialization).

        Leech Seed's own rules apply, via `terrain.blocks_seeding`: Grass
        types and anything not standing on the ground are unseedable, and a
        Pokemon already seeded is not re-seeded.

        What it plants is a *Sylvan seed*, not a Leech Seed: half strength,
        1/16 a turn each way rather than 1/8. The ability plants one on every
        arrival for free, where the move spends a turn on each, and measured
        over 284 battles against the whole roster the two are worth:

            full strength, every arrival    +32.4 points of win rate
            half strength, every arrival    +19.0      <- this
            full strength, own switch-in    +14.8

        At full strength it put a rating-188 competitor 6th of 72 with every
        team drawn at the same rating -- ahead of three of the Elite Four on
        ace and ability alone. See SYLVAN_SEED in constants.py, which is how
        the engine tells the two seeds apart. It never touches this
        trainer's own Pokemon -- the phase is the *opponent* arriving, and
        `target` is that arrival.
        """
        if abilityphase != FOE_ARRIVAL_PHASE:
            return
        if target is None or target.status == "Fainted":
            return
        # The move's own rule, read from the one place that holds it: Grass
        # types and anything off the ground are unseedable. Written out here
        # once and it would have been free to drift from Leech Seed itself.
        refused, line = blocks_seeding(target)
        if refused:
            narrator.say(line % target.name, "fail")
            return
        with suppress(KeyError):
            if target.volatile_status["LeechSeed"] > 0:
                return
            target.volatile_status["LeechSeed"] = SYLVAN_SEED
            narrator.say("A Sylvan seed takes root on %s!" % target.name)
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
        # Phase 1 is "switching in", which is when a Ground type can newly
        # be on the field -- either side's.
        "Desert Wind": (1, desert_wind, "Custom"),
        # Phase 8 is the end of the turn, when the count is taken.
        "Lamplighter": (8, lamplighter, "Custom"),
        # Two phases: using a move, and the end of the turn.
        "Celestial": ((2, 8), celestial, "Custom"),
        # Phase 2 is "using a move", before the effect roll is read.
        "Serene Grace": (2, serene_grace, "Custom"),
        # Phase 7 is "after taking damage", which is where a crit or a
        # freshly applied status can be seen.
        "Anger Point": (7, anger_point, "Custom"),
        # Two phases: using a move, to drop its priority, and after the hit
        # has resolved, to shove the other side out.
        # Three phases: using a move (priority), after it lands (note it),
        # and the end of the turn (the switch itself -- see the docstring
        # for why it cannot be done any earlier).
        "Tension Release": ((ORDER_PHASE, 6, 8),
                            tension_release, "Custom"),
        # Phase 6 is "after a successful hit and its effect" -- the move has
        # finished, which is when a second one can be queued. The turn loop
        # reads `encore_move` at the end of the move it belongs to; see the
        # note in battle_checklist.move_order_and_execution.
        "Wizardry": (6, wizardry, "Custom"),
        # Phase 2 -- "using a move" -- because it fires at the top of
        # move_order_and_execution, before the strike loop reads multi[1].
        # Phase 6 would be after every strike had already run.
        "Overloaded": (2, overloaded, "Custom"),
        # Phase 3 only -- "being targeted". The holder's own Pokemon is not
        # tormented; see the docstring.
        "Torment": (7, torment, "Custom"),
        # A snapshot before anything moves, the comparison at the end.
        "Synchronize": ((ORDER_PHASE, 8), synchronize_drops, "Custom"),
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
        # ORDER_PHASE, not 2: the priority has to be flipped
        # before compare_speed reads it. See constants.py.
        "Procrastination": (ORDER_PHASE, procrastination),
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
        "Brain Wave": ((1, 4), brain_wave),
        "Champion": (1, champion),
        "Impatient": (8, impatient),
        "Outlier": (1, outlier),
        "Thief": (4, thief),
        "Tenebrous": (4, tenebrous),
        "Barbaric": (6, barbaric),
        "Ultra Boost": (1, ultra_boost),
        "Plot Armor": ((1, 5, 7, 8), plot_armor),
        "Calm": ((7, 8), calm),
        "Ruthless": ((4, 5), ruthless),
        "Death Note": (8, death_note),
        "Soak": (1, soak),
        "Time Travel": (3, time_travel),
        "Gargantuan": (5, gargantuan),
        "Irrational": (1, irrational),
        "Light Speed": ((1, 3), light_speed),
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
        # Phase 8 as well now: it checks every few turns that it is
        # still raining, so a weather change does not leave it stranded.
        "Primordial": ((0, ORDER_PHASE, 8), primordial),
        "Last Stand": (1, last_stand),
        "Assassination": (ORDER_PHASE, assassination),
        "Aurora Borealis": (1, aurora_borealis),
        "Sylvan Sprout": (FOE_ARRIVAL_PHASE, sylvan_sprout),
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
