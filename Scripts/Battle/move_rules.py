"""The conditions a move can carry, named so a spreadsheet can name them.

Some of what a move does cannot live in Data/moves.csv: Metronome picks
another move at random, Counter reads what the target just did. Those are
computations, and no cell holds a formula.

But a great deal of what *was* in code is not a computation at all -- it is a
condition. "Brine hits twice as hard when the target is below half HP" was an
`elif move.name == "Brine"` buried in a chain of twelve, and so were the three
other moves with exactly that shape. This module is where those conditions
live, one small function each, in a table keyed by the name a move's row uses.

The vocabulary is closed and validated: a row naming a condition that is not
here is a load-time error naming the move, the column and every name that
would have worked. Before, a typo in a hardcoded branch was silent.

Same idea as `effect_type`, which has always been a name in a cell dispatched
to a handler here. What moves to the table is the *choice*; the behaviour
stays where behaviour belongs.

    power_when     double (or otherwise multiply) power when a condition holds
    weather_when   what a weather does to this move
    fails_unless   the move fails outright unless a condition holds

Adding a move that reuses an existing condition is one cell and no Python.
Adding a genuinely new condition is one function and one dictionary entry,
here, next to its siblings.
"""
import math

from Scripts.Battle.constants import GUARANTEE_ACCURACY

#: how a `power_when` cell separates the condition from its multiplier.
#: Bare means x2, which is what every one of them is today.
MULTIPLIER_MARK = "*"
DEFAULT_MULTIPLIER = 2
#: how a `weather_when` cell separates one weather's entry from the next, and
#: the weather from what it does
WEATHER_SEPARATOR = "|"
WEATHER_MARK = ":"


# -- power_when ------------------------------------------------------------
#: name -> does this hold right now? Takes the same three things
#: onParticularMoveChange already has.
POWER_WHEN = {
    "target_below_half":
        lambda user, target, move: (target.battle_stats[0]
                                    <= target.hp // 2),
    "target_poisoned":
        lambda user, target, move: target.status in ("Poison", "BadPoison"),
    "target_statused":
        lambda user, target, move: target.status != "Normal",
    "user_statused":
        lambda user, target, move: user.status != "Normal",
}


def read_power_when(text):
    """`target_below_half` or `target_below_half*1.5` -> (name, multiplier)."""
    text = (text or "").strip()
    if not text:
        return None, DEFAULT_MULTIPLIER
    if MULTIPLIER_MARK in text:
        name, _, factor = text.partition(MULTIPLIER_MARK)
        return name.strip(), float(factor)
    return text, DEFAULT_MULTIPLIER


def apply_power_when(user, target, move):
    """Multiply this move's power if its condition holds."""
    name, factor = read_power_when(getattr(move, "power_when", ""))
    if name and POWER_WHEN[name](user, target, move):
        move.power *= factor


# -- weather_when ----------------------------------------------------------
def _always_hits(move):
    move.accuracy = GUARANTEE_ACCURACY


def _half_accuracy(move):
    move.accuracy /= 2


def _half_power(move):
    move.power /= 2


def _no_charge(move):
    move.charging = ""


#: name -> what it does to the move. One weather, one effect.
WEATHER_EFFECTS = {
    "always_hits": _always_hits,
    "half_accuracy": _half_accuracy,
    "half_power": _half_power,
    "no_charge": _no_charge,
}

#: the weathers a cell may name, so a typo is caught rather than ignored
WEATHERS = ("Clear", "Sunny", "Rain", "Sandstorm", "Hail")


def read_weather_when(text):
    """`Rain:always_hits|Sunny:half_accuracy` -> {weather: effect name}."""
    out = {}
    for entry in (text or "").split(WEATHER_SEPARATOR):
        entry = entry.strip()
        if not entry:
            continue
        weather, _, effect = entry.partition(WEATHER_MARK)
        out[weather.strip()] = effect.strip()
    return out


def apply_weather_when(battleground, move):
    """Whatever today's weather does to this move, if anything."""
    if move.ignoreWeather:
        return
    effect = read_weather_when(getattr(move, "weather_when", "")).get(
        battleground.weather_effect)
    if effect:
        WEATHER_EFFECTS[effect](move)


# -- fails_unless ----------------------------------------------------------
#: name -> may this move go ahead? Takes what
#: move_fail_checklist_before_execution already has.
FAILS_UNLESS = {
    "target_asleep":
        lambda user, target, move, target_move: target.status == "Sleep",
    "user_asleep":
        lambda user, target, move, target_move: user.status == "Sleep",
    # Sucker Punch: it only lands on someone winding up to attack
    "target_attacks":
        lambda user, target, move, target_move:
            target_move.attack_type != "Status",
    # Shell Trap: springs only when the trap is actually struck
    "hit_by_contact":
        lambda user, target, move, target_move: 'a' in target_move.flags,
    # Belly Drum: enough HP to pay, and somewhere left to raise Attack to
    "can_pay_hp_and_still_boost":
        lambda user, target, move, target_move:
            user.battle_stats[0] > math.ceil(user.hp * move.deduct)
            and user.modifier[1] != 6,
    # Gigaton Hammer: move_order already holds this turn's entry, appended in
    # pre_move_adjustment, so the previous move is the one before it
    "not_used_last_turn":
        lambda user, target, move, target_move:
            not (len(user.move_order) >= 2
                 and user.move_order[-2] == move.name),
}

#: What to say when a condition is not met -- one line per condition, so the
#: player is told the reason rather than just "it failed".
#:
#: The interface reads these too, ahead of the turn, to label a move card the
#: player cannot use (see blocked_moves in GUI/bridge.py). That is why they
#: are phrased as a *reason* and not as an event: they have to read correctly
#: both after a wasted turn and before one.
FAILURE_LINES = {
    "not_used_last_turn": "%(user)s cannot swing the hammer twice in a row!",
    "target_asleep": "Only works on a sleeping target",
    "user_asleep": "%(user)s has to be asleep to use it",
    "target_attacks": "Only lands on a target winding up to attack",
    "hit_by_contact": "Springs only when struck by a contact move",
    "can_pay_hp_and_still_boost":
        "Not enough HP to pay, or Attack is already maxed",
}


def refuses(user, target, move, target_move):
    """(True, what to say) when this move's condition is not met."""
    name = (getattr(move, "fails_unless", "") or "").strip()
    if not name or FAILS_UNLESS[name](user, target, move, target_move):
        return False, ""
    line = FAILURE_LINES.get(name, "The move failed.")
    return True, line % {"user": getattr(user, "name", "It")}


# -- validation, for the loader -------------------------------------------
def check(field, text, where):
    """Raise ValueError if a cell names something that does not exist."""
    if not (text or "").strip():
        return
    if field == "power_when":
        name, factor = read_power_when(text)
        if name not in POWER_WHEN:
            raise ValueError(
                "%s: no power condition called %r. The ones there are: %s"
                % (where, name, ", ".join(sorted(POWER_WHEN))))
    elif field == "weather_when":
        for weather, effect in read_weather_when(text).items():
            if weather not in WEATHERS:
                raise ValueError("%s: no weather called %r. There is: %s"
                                 % (where, weather, ", ".join(WEATHERS)))
            if effect not in WEATHER_EFFECTS:
                raise ValueError(
                    "%s: no weather effect called %r. The ones there are: %s"
                    % (where, effect, ", ".join(sorted(WEATHER_EFFECTS))))
    elif field == "fails_unless":
        if text.strip() not in FAILS_UNLESS:
            raise ValueError(
                "%s: no failure condition called %r. The ones there are: %s"
                % (where, text.strip(), ", ".join(sorted(FAILS_UNLESS))))
