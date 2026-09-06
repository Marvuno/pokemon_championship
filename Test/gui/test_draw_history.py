"""A mutual knockout must resolve the same way in the standings, the matchup,
the head-to-head record and the rating -- and looking up a competitor who has
never played must not crash."""
import builtins
import os
import sys
import traceback

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import main                                                    # noqa: E402,F401
from Scripts.Data.competitors import list_of_competitors        # noqa: E402
from Scripts.Game.game_system import GameSystem                 # noqa: E402
import Scripts.Battle.battle_win_condition as W                 # noqa: E402

report, failures = [], []
real_print = builtins.print


def check(label, got, want):
    ok = got == want
    report.append("%-56s %s" % (label, "PASS" if ok else
                                "FAIL got=%r want=%r" % (got, want)))
    if not ok:
        failures.append(label)


def quiet():
    builtins.print = lambda *a, **k: None
    for mod in list(sys.modules.values()):
        if mod and getattr(mod, "__name__", "").startswith("Scripts") \
                and hasattr(mod, "print"):
            mod.print = builtins.print


def loud():
    builtins.print = real_print
    for mod in list(sys.modules.values()):
        if mod and getattr(mod, "__name__", "").startswith("Scripts") \
                and hasattr(mod, "print"):
            mod.print = real_print


class Mon:
    def __init__(self):
        self.status = "Fainted"
        self.modifier = [0] * 9
        self.volatile_status = {}
        self.protection = [0, 0]
        self.charging = ["", "", 0]
        self.moveset = []
        self.move_order = []
        self.previous_move = None
        self.disabled_moves = {}
        self.disguise = self.transform = False


class Ground:
    verbose = True          # skip choose_pokemon / end_battle
    battle_continuation = True


# ------------------------------------------------- 1. the shared tie-break
# Derived, not named. This used to pin Mivy Wenceslas as the lower rated and
# Magnus Carlsen as the higher, with `# 200` and `# 288` written beside them --
# comments that were already four re-ratings out of date, and the pair
# inverted the moment the Elite tier was reordered. The rule under test is
# "the lower rated wins a draw"; which two competitors happen to sit either
# side of it is not part of it.
_pair = sorted((list_of_competitors['Mivy Wenceslas'],
                list_of_competitors['Magnus Carlsen']),
               key=lambda c: c.strength)
low, high = _pair
assert low.strength < high.strength, "pick two competitors rated differently"
check("wins_a_draw picks the lower rated",
      W.wins_a_draw(high, low) is low, True)
check("...whichever order they are given in",
      W.wins_a_draw(low, high) is low, True)
check("a dead-level draw is deterministic",
      W.wins_a_draw(low, low) is low, True)

# ------------------------- 2. check_win_or_lose awards the point that way
quiet()
for label, me_rating, foe_rating, i_should_win in (
        ("you are the lower rated", 100, 500, True),
        ("you are the higher rated", 500, 100, False)):
    me = list_of_competitors['Protagonist']
    foe = list_of_competitors['Reaper Conan']
    me.strength, foe.strength = me_rating, foe_rating
    me.stage = foe.stage = 1
    me.score = foe.score = 0
    ground = Ground()
    W.check_win_or_lose(me, foe, [Mon()], [Mon()], ground)
    loud()
    check("a mutual KO when %s -> you get the point" % label,
          me.stage == 2 and foe.stage == 1, i_should_win)
    check("   ...and the other side does not",
          foe.stage == 2 and me.stage == 1, not i_should_win)
    quiet()
loud()

# -------------- 3. round_end declares the same winner in the matchup
quiet()
names = [n for n in list_of_competitors if n != 'Protagonist'][:31]
GameSystem.participants = ['Protagonist'] + names
GameSystem.stage = 1
me = list_of_competitors['Protagonist']
foe = list_of_competitors[names[0]]
me.strength, foe.strength = 100, 500          # you are lower rated: you win
for index, name in enumerate(GameSystem.participants):
    comp = list_of_competitors[name]
    comp.stage = 1
    comp.result = 0
    comp.score = 0
    comp.opponent = []
    comp.win_order = []
    comp.match_id = index // 2
    comp.opponent_history = {k: [0, 0] for k in list_of_competitors}
    comp.opponent_scores = {}
# a draw in your match: both sides knocked out the same number
me.result = foe.result = 3
# everyone else needs a result too
for name in GameSystem.participants[2:]:
    list_of_competitors[name].result = 1

boxes = []
original_box = W.EntryBox


class SpyBox(original_box):
    def __init__(self, id=" ", name=" ", score=" ", stage=" "):
        boxes.append((str(name), score, stage))
        super().__init__(id, name, score, stage)


W.EntryBox = SpyBox
try:
    W.round_end(1)
finally:
    W.EntryBox = original_box
    loud()

# the first two boxes are your match: winner printed first
winner_line, loser_line = boxes[0][0], boxes[1][0]
check("the matchup names you as the winner of the draw",
      me.nickname in winner_line, True)
check("...and the higher-rated opponent as the loser",
      foe.nickname in loser_line, True)
check("the head-to-head record agrees",
      (me.opponent_history[foe.name][0],
       me.opponent_history[foe.name][1]), (1, 0))
check("their record agrees too",
      (foe.opponent_history['Protagonist'][0],
       foe.opponent_history['Protagonist'][1]), (0, 1))
check("win_order (which drives the rating) agrees",
      (me.win_order[0], foe.win_order[0]), (1, 0))

# the scoreline Check History shows, recorded on both sides and mirrored
# a round-1 match is ROUND_LIMIT[1]v ROUND_LIMIT[1]; the winner takes them all
LIMIT = W.ROUND_LIMIT[1]
check("your scoreline against them was recorded",
      me.opponent_scores.get(foe.name), [[LIMIT, 3]])
check("...and theirs against you is the mirror of it",
      foe.opponent_scores.get('Protagonist'), [[3, LIMIT]])
# SpyBox records (name, stage, score) -- EntryBox's third argument is the
# stage and its fourth is the score
check("the winner's score matches the matchup box",
      (boxes[0][2], boxes[1][2]), (LIMIT, 3))
check("the other matches were recorded too",
      all(list_of_competitors[n].opponent_scores
          for n in GameSystem.participants[2:]), True)

# and the other way round
quiet()
for name in GameSystem.participants:
    comp = list_of_competitors[name]
    comp.stage, comp.result, comp.score = 1, 1, 0
    comp.opponent, comp.win_order = [], []
    comp.opponent_history = {k: [0, 0] for k in list_of_competitors}
    comp.opponent_scores = {}
me.strength, foe.strength = 500, 100          # you are higher rated: you lose
me.result = foe.result = 3
boxes.clear()
W.EntryBox = SpyBox
try:
    W.round_end(1)
finally:
    W.EntryBox = original_box
    loud()
check("higher rated loses the draw in the matchup too",
      foe.nickname in boxes[0][0] and me.nickname in boxes[1][0], True)
check("...and in the record", me.opponent_history[foe.name], [0, 1])

# ------------------- 4. a competitor with no history does not crash
fresh = list_of_competitors['Rudolf']
fresh.opponent_history = {k: [0, 0] for k in list_of_competitors}
fresh.history = {}
fresh.participation = fresh.championship = 0
total_win = sum(v[0] for v in fresh.opponent_history.values())
total_lose = sum(v[1] for v in fresh.opponent_history.values())
check("a never-played competitor really has no record",
      (total_win, total_lose), (0, 0))
try:
    rate = round(total_win / (total_win + total_lose) * 100, 2)
    check("the old maths would have raised", "no error", "ZeroDivisionError")
except ZeroDivisionError:
    report.append("%-56s PASS" % "the old maths raised ZeroDivisionError")

source = open('Scripts/Game/start_interface.py', encoding='utf-8').read()
check("the history screen guards the win rate first",
      "if total_win + total_lose == 0:" in source, True)
check("...and says so rather than dividing",
      "no match history on record" in source, True)
guard = source.index("if total_win + total_lose == 0:")
divide = source.index("Win Rate: {round(total_win")
check("the guard comes before the division", guard < divide, True)

real_print("\n".join(report))
real_print("\n%s" % ("ALL PASS" if not failures
                     else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
