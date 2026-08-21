"""How a rating turns into Pokemon.

Three separate things in this game used to answer "how good should these
Pokemon be", and all three answered it differently:

* **team_generation** ran a six-line weights formula full of bare numbers
  (`max(0, 40 - ratings)`, `min(60, 3 + ratings)`, an `ultra_high` ladder of
  six `if`s). It **saturated**: every competitor from about 300 upward drew
  the identical mix -- 35% High, 59% Very High, 6% Ultra High -- so rating
  above that bought literally nothing. Champion Marvin fielded the same
  calibre of team as somebody a third of his rating.
* **winning a round** looked up the *level label* of whoever you beat in a
  dict -- Low and Intermediate both mean Medium, Advanced means High -- so
  beating a 58-rated opponent and a 115-rated one paid exactly the same, and
  your own rating never entered into it.
* **losing a round** ignored rating altogether: a flat draw from Very Low,
  Low and Medium, 138 Pokemon wide. A 300-rated player who lost could be
  handed the same Pokemon as a 2-rated one.

This module is the one answer. A rating becomes a position on the tier
ladder, and every case is the same ladder read at a different rating:

    a competitor's own team      their rating
    the player's own team        their rating -- the same, with no thumb on
                                 the scale; there used to be a 1.2 for the AI
    winning a round              the beaten opponent's rating x 1.2
    losing a round               your own rating x 0.8

so "you get what somebody at that rating fields" is the whole rule, and the
only question is whose rating and how much of it.

IVs follow the same principle and live in constants.PLAYER_IV: one curve on
rating, for the player and the competitors alike. That used to be a fixed
floor per *tier label* for competitors (Low 0, Intermediate 8, Advanced 16,
Elite 24, Champion 31) against the player's curve -- two different kinds of
rule, so the two crossed rather than tracked.

Ratings here are the ones in Data/competitors.csv and on screen -- the new
scale, not the old one the balance formulas used to be written in.
"""
import random

#: weakest first. The index into this is what a rating is converted into.
TIERS = ("Very Low", "Low", "Medium", "High", "Very High", "Ultra High")

#: the rating at which a competitor's centre of gravity sits on each tier.
#: Tuned so the *top* of the roster is spread out rather than bunched: the
#: old formula gave everyone above ~300 the same draw, which is the flaw
#: this fixes. Ultra High is deliberately far out -- there are only six
#: Pokemon in it, and it should read as the Champion's own shelf.
TIER_CENTRE = (0, 40, 90, 160, 320, 700)

#: how many tiers either side of the centre still get a look in. 1.5 means a
#: competitor draws from about three tiers, which is roughly the spread the
#: old formula had in its mid-range -- the part of it that worked.
SPREAD = 1.5

#: The player and every competitor read the same ladder at their own rating.
#: There was a 1.2 here -- an opponent fielded Pokemon as though rated 20%
#: higher -- which meant "the same rating" never meant the same team.
AI_ADVANTAGE = 1.0

#: What winning and losing are worth, as a multiplier on a *rating* rather
#: than a shift along the ladder. Same idea as everything else here: one
#: rule, read at a different rating.
#:
#:   win   the beaten opponent's rating, +20% -- beating somebody stronger
#:         pays more, continuously, with no tier labels involved
#:   lose  your own rating, -20% -- a consolation pitched just under what
#:         you already field
WIN_MULTIPLIER = 1.2
LOSS_MULTIPLIER = 0.8

#: The most of a draw any one tier may take, where that tier is too small to
#: fill a team on its own.
#:
#: This is a *pool size* constraint, not a balance one, and it is the whole
#: reason this is not just a kernel. Ultra High holds six Pokemon. A kernel
#: centred on it hands the top competitors 75% of their draw from those six,
#: so Champion Marvin would field the same six every single run -- less
#: variety than the saturating formula this replaced, not more. Capping the
#: share pushes the remainder down the ladder, where there are 28 Very High
#: and 69 High to choose from.
#:
#: A tier not named here is unconstrained.
SHARE_CEILING = {"Ultra High": 0.15, "Very High": 0.55}


def ladder_position(rating):
    """Where `rating` sits on the tier ladder, as a float index into TIERS.

    Piecewise linear between the centres, clamped at both ends. The clamp at
    the top is honest rather than a flaw: Ultra High is the last shelf and
    there is nothing above it to hand out.
    """
    rating = max(0.0, float(rating))
    if rating >= TIER_CENTRE[-1]:
        return float(len(TIERS) - 1)
    for index in range(len(TIER_CENTRE) - 1):
        low, high = TIER_CENTRE[index], TIER_CENTRE[index + 1]
        if rating < high:
            return index + (rating - low) / (high - low)
    return float(len(TIERS) - 1)


def tier_weights(rating, shift=0.0, spread=SPREAD):
    """Weights over TIERS for a competitor at `rating`.

    `shift` moves the centre along the ladder -- positive for the reward for
    winning, negative for a consolation. A triangular kernel rather than
    anything cleverer: it is easy to read off, always sums to something
    positive, and gives exactly zero to tiers further than `spread` away, so
    a rating-2 competitor can never be handed an Ultra High Pokemon.
    """
    centre = ladder_position(rating) + shift
    weights = [max(0.0, 1.0 - abs(index - centre) / spread)
               for index in range(len(TIERS))]
    return _respect_pool_sizes(weights)


def _respect_pool_sizes(weights):
    """Hold the small tiers to their share, giving the rest to the tier below.

    Applied after the kernel rather than as a weight, because a weight
    cannot express "at most this fraction" -- at the top of the ladder only
    two tiers are non-zero, so scaling one of them down still leaves it with
    a third of the draw. See SHARE_CEILING.
    """
    weights = list(weights)
    total = sum(weights)
    if total <= 0:
        return weights
    for index in range(len(TIERS) - 1, 0, -1):
        ceiling = SHARE_CEILING.get(TIERS[index])
        if ceiling is None:
            continue
        total = sum(weights) or 1.0
        excess = weights[index] - ceiling * total
        if excess <= 0:
            continue
        # Solve for the weight that *is* the ceiling once the spare has
        # moved down a tier: the total does not change, so the ceiling is a
        # share of the same total.
        weights[index] -= excess
        weights[index - 1] += excess
    return weights


def tier_list(rating, count, for_ai=True):
    """`count` tier names for a competitor at `rating`, drawn by weight.

    `for_ai` is kept so call sites need not change, but it no longer buys
    anything: AI_ADVANTAGE is 1.0 and the player and the competitors read
    the same ladder at their own rating.
    """
    if for_ai:
        rating = rating * AI_ADVANTAGE
    weights = tier_weights(rating)
    if not any(weights):                 # cannot happen; cheaper than a bug
        weights = [1.0] * len(TIERS)
    return random.choices(list(TIERS), weights=weights, k=max(0, count))


def draw_tier(rating, shift=0.0):
    """One tier name, for a single Pokemon handed over at `rating`."""
    weights = tier_weights(rating, shift=shift)
    if not any(weights):
        weights = [1.0] * len(TIERS)
    return random.choices(list(TIERS), weights=weights, k=1)[0]


def reward_tier(loser_rating):
    """The tier of the Pokemon the organiser hands you for a win.

    Read at the beaten opponent's rating plus a fifth, so a better win pays
    better and nothing depends on their tier label.
    """
    return draw_tier(loser_rating * WIN_MULTIPLIER)


def consolation_tier(own_rating):
    """The tier of the Pokemon you are given after losing a round.

    Read at your own rating less a fifth: a step under what you field, so it
    is a consolation and not a prize, and it scales with you.
    """
    return draw_tier(own_rating * LOSS_MULTIPLIER)


def describe(rating, shift=0.0):
    """The weights as percentages, for a report or a test to read."""
    weights = tier_weights(rating, shift=shift)
    total = sum(weights) or 1.0
    return {name: 100.0 * weight / total
            for name, weight in zip(TIERS, weights)}
