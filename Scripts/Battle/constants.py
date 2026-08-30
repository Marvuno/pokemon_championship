import math

GUARANTEE_ACCURACY = 9
INFINITY = math.inf
NEG_INF = math.inf * -1

#: What the AI takes off a move's ranking score when the move *cannot be
#: used at all* -- disabled, or a first-turn-only move after the first turn.
#: Large enough that no situational bonus can lift such a move back to the
#: top: `smart_ai_select_move` sorts on that score first and uses damage
#: only as a tie-break, so a merely-docked move that led on points was still
#: chosen, refused by the engine, and the turn spent on nothing.
UNUSABLE_MOVE_PENALTY = 50
ROUND_LIMIT = {1: 4, 2: 5, 3: 6, 4: 6, 5: 6, 6: 6}  # 4,5,6,6,6
STATISTICS = {0: "HP", 1: "Atk", 2: "Def", 3: "SpA", 4: "SpDef", 5: "Speed"}
MODIFIER = {0: 'HP', 1: 'Attack', 2: 'Defense', 3: 'Special Attack', 4: 'Special Defense', 5: 'Speed', 6: 'Evasion', 7: 'Accuracy', 8: 'Crit'}
#: The ability phase that runs *before* the turn order is worked out.
#:
#: Phases 1..9 all happen once a Pokemon is already taking its turn, and that
#: is too late for an ability whose whole job is to decide *when* the turn is
#: taken. Swift Swim doubled the Speed the order had already been read from;
#: Prankster and Procrastination changed a priority nobody would look at
#: again. Measured: compare_speed saw Barraskewda at 339 every single turn
#: while Swift Swim was quietly doubling it to 678 afterwards, and the next
#: turn's recalculation threw that away.
#:
#: These used to be on phase 2, which fired in `pre_move_adjustment` -- before
#: the comparison, so they worked. Phase 2 moved into `on_move_used` so that
#: Protean and Libero would change type as their Pokemon actually moved
#: rather than before the turn; that was right for them and wrong for these.
#: Hence a phase of its own rather than moving phase 2 back.
ORDER_PHASE = 10
#: How often a battle opens on weather at all, and which weathers it may
#: be. One roll decides whether, a second decides which -- so these two are
#: independent, and adding a weather does not make weather more likely.
OPENING_WEATHER_CHANCE = 0.20
OPENING_WEATHERS = ('Rain', 'Sunny', 'Sandstorm', 'Hail')

TEAM_BUFF_TURNS = 6
FIELD_EFFECT_TURNS = 6
WEATHER_EFFECT_TURNS = 6
KEEP_POKEMON_LOST = 3
KEEP_POKEMON_SEMI = 4
KEEP_POKEMON_WIN = 6
MAX_POKEMON = 6


#: Ratings were multiplied by this when the simple-AI boundary moved from 30
#: to 50 -- a boundary that no longer exists, since which AI an opponent uses
#: is the difficulty setting now rather than their rating. The scale stays:
#: it is what every rating on screen is written in. Every *balance*
#: formula divides it back out again -- the thresholds in team_generation and
#: in PLAYER_IV are written in the old rating units, and rescaling the
#: numbers on screen without dividing here would have handed every competitor
#: a stronger team as a side effect. Displayed ratings and tier labels are on
#: the new scale; team strength is untouched.
RATING_SCALE = 5.0 / 3.0


def on_old_scale(strength):
    """A rating as the balance formulas expect it."""
    return strength / RATING_SCALE


def PLAYER_IV(strength):
    return min(31, int(on_old_scale(strength) / 250 * 31))


def has_ability(pokemon, *names):
    """Does this Pokemon hold any of `names`?

    `pokemon.ability` is a *list* -- a Pokemon can have two. Four guards in
    the engine compared it to a string instead ("if pokemon.ability !=
    'Magic Guard'"), and a list is never equal to a string, so every one of
    those guards was always true and the ability it protected never did
    anything. Tolerant of a bare string as well, because the CSV loader has
    produced one in the past and a guard that raises is worse than a guard
    that reads.
    """
    held = getattr(pokemon, "ability", None) or ()
    if isinstance(held, str):
        held = (held,)
    return any(name in held for name in names)