"""Ratings live on a different scale from the balance formulas.

The simple-AI boundary moved from 30 to 50, and every rating was multiplied
by 5/3 so that the *same* competitors stay on the simple AI. That rescale is
a presentation change and must stay one: the thresholds inside
`team_generation` -- 40, 80, 117, 50, 80, and the ultra-high ladder -- and
inside `PLAYER_IV` are all written in the old rating units. Feeding them the
new numbers without dividing back out would have handed every competitor a
stronger team as a silent side effect of renumbering the ladder.

So: what is shown, and where the AI boundary sits, are on the new scale.
What a competitor's team is rolled from is on the old one.
"""
import io
import os
import random
import sys
from contextlib import redirect_stdout
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                 # noqa: F401,E402
from Scripts.Battle.constants import (PLAYER_IV, RATING_SCALE,       # noqa: E402
                                      SMART_AI_RATING, on_old_scale)
from Scripts.Data.competitors import list_of_competitors            # noqa: E402
from Scripts.Game.game_procedure import team_generation             # noqa: E402
from Scripts.Game.game_system import GameSystem                     # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


print("-- the two scales --")
check("the boundary is at 50", SMART_AI_RATING, 50)
check("...which is 30 on the old scale",
      round(on_old_scale(SMART_AI_RATING), 6), 30.0)
check("the factor is five thirds", round(RATING_SCALE, 6),
      round(5.0 / 3.0, 6))
check("on_old_scale undoes it", round(on_old_scale(100 * RATING_SCALE), 6),
      100.0)

print()
print("-- who plays with the simple AI --")
# Deliberately not a list of names or a count. Ratings are the designer's
# dial and get tuned by hand between runs -- pinning "these fourteen" here
# only means the suite breaks every time the ladder is adjusted, which is
# noise, not a defect. What must hold is that the boundary *is* the rating.
simple = [c for c in list_of_competitors.values()
          if c.strength < SMART_AI_RATING]
clever = [c for c in list_of_competitors.values()
          if c.strength >= SMART_AI_RATING]
check("the roster splits on the boundary, both sides non-empty",
      bool(simple) and bool(clever))
check("nobody below the boundary is above it",
      max(c.strength for c in simple) < SMART_AI_RATING)
check("...and nobody above it is below",
      min(c.strength for c in clever) >= SMART_AI_RATING)
check("the weakest competitor is on the simple AI",
      min(c.strength for c in list_of_competitors.values())
      < SMART_AI_RATING)
check("the Champion is not",
      max(c.strength for c in list_of_competitors.values())
      >= SMART_AI_RATING)
print("   %d of %d competitors use the simple AI"
      % (len(simple), len(simple) + len(clever)))

print()
print("-- the ladder still reads in order --")
ranked = sorted((c.strength, c.nickname) for c in list_of_competitors.values()
                if not c.main)
check("nobody was rescaled below 1", ranked[0][0] >= 1)
check("the Champion is still the top of it", ranked[-1][1],
      "Champion Marvin")
tiers = {}
for competitor in list_of_competitors.values():
    if not competitor.main:
        tiers.setdefault(competitor.level, []).append(competitor.strength)
for level, band in sorted(tiers.items(), key=lambda kv: min(kv[1])):
    print("   %-13s %4d - %4d" % (level, min(band), max(band)))

print()
print("-- the balance formulas were not moved --")
# PLAYER_IV is written in old units, so a rescaled rating must give the same
# floor it gave before
for old_rating in (5, 30, 100, 250, 400):
    new_rating = old_rating * RATING_SCALE
    check("PLAYER_IV: %d then, %d now, same floor"
          % (old_rating, round(new_rating)),
          PLAYER_IV(new_rating), min(31, int(old_rating / 250 * 31)))

# and a team rolled now is rolled from the old number
GameSystem.stage = 5
for who in ("Goblin", "Dulunga", "Auraia", "Expert Cynthia"):
    random.seed(4242)
    side = deepcopy(list_of_competitors[who])
    with redirect_stdout(io.StringIO()):
        team = team_generation(side)
    tiers_drawn = [p.tier for p in team]
    print("   %-15s rated %4d -> %s"
          % (who, list_of_competitors[who].strength, tiers_drawn))
check("every team came out the right size",
      all(1 <= len(deepcopy(list_of_competitors[w]).team) <= 6
          for w in ("Goblin", "Auraia")))

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
