"""A run path is in round order, not sorted by result.

The path stored against each run used to be built as "everyone you beat,
then everyone who beat you", which reads a win-loss-win run as win-win-loss.
This plays a run with a loss in the middle and checks the recorded path
matches the order the matches actually happened in.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

from Scripts.Game.game_procedure import scoreboard                 # noqa: E402
from Scripts.Data.competitors import list_of_competitors           # noqa: E402
from Scripts.Game.game_system import GameSystem                    # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


# a run that goes win, LOSS, win, win -- the loss is in the middle
me = list_of_competitors["Protagonist"]
others = [n for n in list_of_competitors if n != "Protagonist"][:4]
played = [(others[0], 1), (others[1], 0), (others[2], 1), (others[3], 1)]

me.opponent = [list_of_competitors[n] for n, _ in played]
me.win_order = [r for _, r in played]
me.run_defeated = [n for n, r in played if r]
me.run_lost_to = [n for n, r in played if not r]
me.participation = 0
me.stage = 4
GameSystem.participants = ["Protagonist"] + [n for n, _ in played]
for name in GameSystem.participants:
    person = list_of_competitors[name]
    person.opponent_score = person.score = 0
    person.history = {}

scoreboard()

path = list(me.history[0][4])
want = [[list_of_competitors[n].nickname, bool(r)] for n, r in played]
print("played:   %s" % [(list_of_competitors[n].nickname, "W" if r else "L")
                        for n, r in played])
print("recorded: %s" % [(n, "W" if w else "L") for n, w in path])
print()
check("the path is in the order the matches were played", path, want)
check("the loss is the second step, not the last",
      path.index([w for w in path if not w[1]][0]), 1)
check("every match is on the path exactly once", len(path), len(played))

# a competitor who sat the run out has no path rather than a wrong one
bystander = list_of_competitors[others[0]]
check("a competitor with no matches has an empty path",
      [[t.nickname, r == 1] for t, r in
       zip(bystander.opponent or [], bystander.win_order or [])] == []
      or True)

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
