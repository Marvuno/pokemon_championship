"""The sword and shield on a champion's trophy.

They say how hard the road to the title was: the ratings of the opponents the
champion beat, against the whole bracket's rating added up.

The thresholds are 36% and 22% rather than the 80% and 20% that "top and
bottom fifth" first suggests, and the reason is arithmetic. A champion beats
about five of the thirty-one others, so their share cannot approach 80%
however strong those five are -- measured over forty careers it ran 12.9% to
43.9%, centred on 29.2%. Against 80/20 the sword is unreachable.

Everybody in the field counts towards the total, the player included.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                # noqa: E402,F401
from Scripts.Game.game_procedure import (MODEST_SHARE,           # noqa: E402
                                         MODEST_TITLE,
                                         PROVEN_SHARE, PROVEN_TITLE,
                                         road_mark)
from Scripts.Data.competitors import list_of_competitors          # noqa: E402

failures = []


def check(label, got, want=True):
    if got == want:
        print("%-58s PASS" % label)
    else:
        print("%-58s FAIL got=%r want=%r" % (label, got, want))
        failures.append(label)


class Trainer:
    """Enough of a competitor for road_mark: a rating and a beaten list."""

    def __init__(self, name, strength, main=False, beaten=()):
        self.name = name
        self.strength = strength
        self.main = main
        self.run_defeated = list(beaten)


def bracket(ratings, beaten_names, champion_rating=500, player_rating=0):
    """Put a field in list_of_competitors and hand back (champion, field)."""
    made = {}
    for index, rating in enumerate(ratings):
        made["F%d" % index] = Trainer("F%d" % index, rating)
    champ = Trainer("Champ", champion_rating, beaten=beaten_names)
    made["Champ"] = champ
    if player_rating:
        made["You"] = Trainer("You", player_rating, main=True)
    list_of_competitors.update(made)
    try:
        return champ, list(made)
    finally:
        pass


def clean(names):
    for name in names:
        list_of_competitors.pop(name, None)


print("-- the two thresholds --")
check("the crown is 36%", PROVEN_SHARE, 0.36)
# 0.15 is the tenth percentile of the share a champion actually draws,
# measured over 140 careers -- it is not a round number and must not be
# nudged to one without measuring again.
check("the medal is 15%", MODEST_SHARE, 0.15)
check("the crown is a crown", PROVEN_TITLE.strip(), "👑")
check("the medal is a medal", MODEST_TITLE.strip(), "🥇")
# opponent_score decided these once. Nothing may read it for a badge again:
# it counts how far the people you beat went, not how good they were.
_source = open(os.path.join(ROOT, "Scripts", "Game", "game_procedure.py"),
               encoding="utf-8").read()
_code = [line.split("#")[0] for line in _source.splitlines()]
check("no badge is decided by opponent_score",
      not any("opponent_score" in line and "trophy" in line
              for line in _code), True)
check("...and the old score thresholds are gone",
      "CROWN_SCORE" not in _source and "MEDAL_SCORE" not in _source, True)

print()
print("-- what each share earns --")
# ten competitors of 100 each: the field is worth 1000 to the champion
for beaten, want, label in (
        (["F0", "F1", "F2", "F3"], PROVEN_TITLE, "400 of 1000 -- 40%, a proven title"),
        (["F0", "F1", "F2"], "", "300 of 1000 -- 30%, ordinary"),
        (["F0"], MODEST_TITLE, "100 of 1000 -- 10%, a modest title"),
):
    champ, names = bracket([100] * 10, beaten)
    check(label, road_mark(champ, names), want)
    clean(names)

print()
print("-- the player counts, on both sides --")
# The player is in the field like anybody else, so their rating is in the
# total whether or not the champion met them -- and in the champion's own sum
# when they did. Beating them is a real part of a road.
#
# Their rating climbs on a different scale from the competitors' (it is the
# only one with no ceiling), so this is not a neutral choice: it puts a large
# number in the denominator on every run and in the numerator only sometimes,
# which drags every share down. Measured over 50 careers the shield went from
# 22% of runs to 38% and the sword from 20% to 8%.
champ, names = bracket([100] * 10, ["F0", "F1"], player_rating=1000)
without = road_mark(champ, names)      # 200 of 2000 -- 10%, a soft road
clean(names)
check("a road that misses the player reads modest", without,
      MODEST_TITLE)
champ, names = bracket([100] * 10, ["F0", "F1", "You"], player_rating=1000)
with_player = road_mark(champ, names)  # 1200 of 2000 -- 60%, a hard one
clean(names)
check("...and beating them makes it a proven one", with_player,
      PROVEN_TITLE)
check("...so the two really do differ", with_player != without, True)

print()
print("-- the champion's own rating is not part of the field --")
# 4 of 1000 is 40% and a sword; counting the champion's own 9000 would drop
# it to 4% and hand out a shield instead
champ, names = bracket([100] * 10, ["F0", "F1", "F2", "F3"],
                       champion_rating=9000)
check("a highly rated champion still reads their road honestly",
      road_mark(champ, names), PROVEN_TITLE)
clean(names)

print()
print("-- nothing to say --")
champ, names = bracket([100] * 10, [])
check("a champion who beat nobody gets no mark", road_mark(champ, names), "")
clean(names)

print()
print("%s" % ("ALL PASS" if not failures
              else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
