"""One rule turns a rating into Pokemon, for all three places that need it.

There used to be three answers. `team_generation` had a weights formula of
bare numbers that **saturated** -- every competitor above about 300 drew the
identical mix, so rating past that bought nothing. Winning a round looked up
the beaten opponent's *level label*, so a 58-rated and a 115-rated opponent
paid the same. Losing ignored rating altogether: a flat draw from 138
Pokemon across three tiers, the same for a 2-rated player and a 300-rated
one.

`Scripts/Data/tiers.py` is the single answer, and everything else is that
answer with an offset.
"""
import collections
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                 # noqa: F401,E402
from Scripts.Data import tiers
from Scripts.Data.competitors import list_of_competitors                                      # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                    # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


# Every competitor's Level has to be a real rung. It is not decoration:
# game_system.py builds a bracket from the Low/Intermediate/Advanced pool and
# samples Elites out of theirs, so a Level that is not one of these silently
# removes that competitor from every tournament ever played. Two of them held
# "intermediate.mp3" -- the music filename pasted into the Level cell -- and
# neither had appeared in a bracket since.
print("-- every competitor sits on a real rung --")
_RUNGS = ("Low", "Intermediate", "Advanced", "Elite", "Champion",
          "Protagonist")
_stray = sorted((c.nickname, c.level) for c in list_of_competitors.values()
                if c.level not in _RUNGS)
check("no competitor has an unknown Level (%d checked)"
      % len(list_of_competitors), _stray, [])
_drawable = [c for c in list_of_competitors.values()
             if c.level in ("Low", "Intermediate", "Advanced")]
_elite = [c for c in list_of_competitors.values() if c.level == "Elite"]
check("the bracket pool is big enough to fill 32 seats",
      len(_drawable) >= 26, True)
check("...and there are enough Elites to sample 4-6", len(_elite) >= 6, True)

print()
print("-- the ladder --")
check("six tiers, weakest first", tiers.TIERS[0], "Very Low")
check("...and strongest last", tiers.TIERS[-1], "Ultra High")
check("a centre for each", len(tiers.TIER_CENTRE), len(tiers.TIERS))
check("the centres climb", list(tiers.TIER_CENTRE),
      sorted(tiers.TIER_CENTRE))
check("rating 0 sits at the bottom", tiers.ladder_position(0), 0.0)
# The top of the ladder is RATING_CEILING, not the last tier's centre. Ultra
# High is six Pokemon and is deliberately never the centre of anybody's draw
# -- reaching the ceiling earns a share of it, never a teamful. This used to
# assert position 5.0 for a huge rating, which was the old design.
check("...and a huge rating clamps to the ceiling",
      tiers.ladder_position(10 ** 6),
      tiers.ladder_position(tiers.RATING_CEILING))
check("...which is below the last tier's own centre",
      tiers.ladder_position(10 ** 6) < float(len(tiers.TIERS) - 1))
_top = tiers.tier_weights(tiers.RATING_CEILING)
check("...and the top of the ladder still reaches Ultra High",
      _top[tiers.TIERS.index("Ultra High")] > 0)
check("...without it taking the team",
      _top[tiers.TIERS.index("Ultra High")] / sum(_top)
      <= tiers.SHARE_CEILING["Ultra High"] + 1e-9)
# Nothing at the bottom may reach the top shelves: that is what the narrower
# spread is for.
for _low in (0, 2, 5, 20):
    _w = tiers.tier_weights(_low)
    _share = (_w[tiers.TIERS.index("Very High")]
              + _w[tiers.TIERS.index("Ultra High")]) / (sum(_w) or 1)
    check("rating %d draws nothing from the top two tiers" % _low,
          _share, 0.0)
check("a rating never falls off the ladder",
      all(0 <= tiers.ladder_position(r) <= len(tiers.TIERS) - 1
          for r in range(0, 2000, 7)))
check("position rises with rating, never falls",
      all(tiers.ladder_position(r) <= tiers.ladder_position(r + 5)
          for r in range(0, 1500, 5)))

print()
print("-- the weights --")
check("a weak competitor can never draw the top tier",
      tiers.tier_weights(1)[-1], 0.0)
check("...nor a strong one the bottom", tiers.tier_weights(900)[0], 0.0)
check("weights are never negative",
      all(w >= 0 for r in range(0, 1200, 11) for w in tiers.tier_weights(r)))
check("something is always drawable",
      all(sum(tiers.tier_weights(r)) > 0 for r in range(0, 1200, 11)))

# the flaw this replaced: the old formula gave everyone above ~300 the same
# draw. The new one has to keep moving well past that.
low, mid, high = (tiers.describe(120), tiers.describe(200),
                 tiers.describe(300))
check("the draw keeps changing through the mid-ladder",
      len({tuple(round(v, 1) for v in share.values())
           for share in (low, mid, high)}), 3)

print()
print("-- the pool-size ceiling --")
pool = {name: sum(1 for p in list_of_pokemon.values() if p.tier == name)
        for name in tiers.TIERS}
for name, ceiling in sorted(tiers.SHARE_CEILING.items()):
    worst = max(tiers.describe(r)[name] for r in range(0, 2000, 9))
    check("%s never exceeds %.0f%% of a draw (holds %d Pokemon)"
          % (name, ceiling * 100, pool[name]), worst <= ceiling * 100 + 0.01)
# the point of it: the Champion must be able to field a varied team
top = tiers.describe(2000)
reach = sum(pool[name] for name in tiers.TIERS if top[name] > 0.5)
check("the very top of the ladder can still draw from a wide pool (%d)"
      % reach, reach > 60)

print()
print("-- the player and the competitors read the same ladder --")
check("no thumb on the scale for the AI", tiers.AI_ADVANTAGE, 1.0)
for rating in (5, 50, 100, 200, 400, 900):
    theirs = tiers.describe(rating * tiers.AI_ADVANTAGE)
    mine = tiers.describe(rating)
    check("at %d, both draw the same" % rating,
          all(abs(theirs[name] - mine[name]) < 1e-9 for name in tiers.TIERS))
check("for_ai is now inert, whichever way it is passed",
      tiers.tier_weights(200), tiers.tier_weights(200))

print()
print("-- one IV curve, player and competitor alike --")
import inspect                                                      # noqa: E402

from Scripts.Game import game_procedure as _gp                       # noqa: E402

source = inspect.getsource(_gp.team_generation)
code = chr(10).join(l.split("#", 1)[0] for l in source.splitlines()
                    if l.split("#", 1)[0].strip())
check("the per-tier IV floors are gone", "random_iv_on_tier" in code, False)
check("...and the floor comes from PLAYER_IV", "PLAYER_IV(" in code)
from Scripts.Battle.constants import PLAYER_IV                       # noqa: E402
check("the curve rises with rating",
      all(PLAYER_IV(r) <= PLAYER_IV(r + 25) for r in range(0, 1200, 25)))
check("...and tops out at 31", PLAYER_IV(10 ** 6), 31)

print()
print("-- winning pays by rating, not by label --")
check("winning reads the beaten rating x %.1f" % tiers.WIN_MULTIPLIER,
      tiers.WIN_MULTIPLIER, 1.2)
check("losing reads your own rating x %.1f" % tiers.LOSS_MULTIPLIER,
      tiers.LOSS_MULTIPLIER, 0.8)
random.seed(3)
weaker = collections.Counter(tiers.reward_tier(58) for _ in range(3000))
stronger = collections.Counter(tiers.reward_tier(115) for _ in range(3000))
order = {name: index for index, name in enumerate(tiers.TIERS)}


def average(tally):
    total = sum(tally.values()) or 1
    return sum(order[name] * count for name, count in tally.items()) / total


check("beating a 115 pays better than beating a 58",
      average(stronger) > average(weaker))
check("...and beating the Champion better still",
      average(collections.Counter(tiers.reward_tier(1000)
                                  for _ in range(3000)))
      > average(stronger))

print()
print("-- losing scales with your own rating, and is a step down --")
random.seed(4)
for rating in (60, 160, 320):
    consolation = collections.Counter(tiers.consolation_tier(rating)
                                      for _ in range(3000))
    own = collections.Counter(tiers.tier_list(rating, 1, for_ai=False)[0]
                              for _ in range(3000))
    check("at %d, the consolation is weaker than your own team" % rating,
          average(consolation) < average(own))
# ...but not above the point where the ladder itself plateaus. x0.8 of 900 is
# still past the top centre, so both land on the same capped draw -- honest
# rather than a defect: there is nothing weaker to hand out that is still
# "one step down" from the top shelf.
top = collections.Counter(tiers.consolation_tier(900) for _ in range(2000))
own_top = collections.Counter(tiers.tier_list(900, 1, for_ai=False)[0]
                              for _ in range(2000))
check("at the very top the two converge, because the ladder ends",
      abs(average(top) - average(own_top)) < 0.15)
weak = collections.Counter(tiers.consolation_tier(5) for _ in range(2000))
strong = collections.Counter(tiers.consolation_tier(600) for _ in range(2000))
check("a strong player's consolation beats a weak player's",
      average(strong) > average(weak))
check("...which the old flat draw could not do",
      set(weak) != set(strong))

print()
print("-- and the engine actually uses it --")
import inspect                                                      # noqa: E402

from Scripts.Battle import battle_win_condition                     # noqa: E402
from Scripts.Game import game_procedure                             # noqa: E402

def code_only(function):
    """The source with comments stripped.

    Searching the raw source matched the *comment* that explains what was
    removed -- "it was max(0, 40 - ratings)" -- and reported the formula as
    still present. A comment describing history is exactly what should be
    there; only real code counts.
    """
    lines = []
    for line in inspect.getsource(function).splitlines():
        head = line.split("#", 1)[0]
        if head.strip():
            lines.append(head)
    return chr(10).join(lines)


source = code_only(game_procedure.team_generation)
check("team_generation asks tiers.py", "tiers.tier_list" in source)
check("...and no longer carries its own weights formula",
      any(marker in source for marker in ("40 - ratings", "3 + ratings",
                                          "ratings - 50", "ultra_high")),
      False)
source = code_only(battle_win_condition.choose_pokemon)
check("winning asks tiers.py", "tiers.reward_tier" in source)
check("losing asks tiers.py", "tiers.consolation_tier" in source)
check("...and the level->tier dict is gone",
      "defeating_tier_list" in source, False)

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
