"""The engine says facts, not just sentences.

The interface used to recover numbers by running regular expressions over
what the engine printed. This checks the replacement: every line still goes
to the terminal exactly as before, and the facts behind the lines arrive
without anyone reading English.
"""
import io
import os
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                 # noqa: F401,E402
from Scripts.Art import narrator                                   # noqa: E402
from Scripts.Data.competitors import list_of_competitors           # noqa: E402
from Scripts.Game.game_procedure import elo_rating                 # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


print("-- say() --")
heard = []
stop = narrator.listen(lambda kind, text, facts: heard.append((kind, facts)))
buffer = io.StringIO()
with redirect_stdout(buffer):
    narrator.say("plain line")
    narrator.failed()
    narrator.say("hit", "damage", amount=12)
stop()
check("every line still reaches the terminal",
      buffer.getvalue(), "plain line\nThe move failed.\nhit\n")
check("and each one carries its kind",
      [k for k, _ in heard], ["plain", "fail", "damage"])
check("with the facts behind it", heard[2][1], {"amount": 12})

silent = io.StringIO()
with redirect_stdout(silent):
    narrator.say("nobody listening")
check("a listener that stops hearing stops being called", len(heard), 3)
check("every kind used is a declared one",
      sorted({k for k, _ in heard} - set(narrator.KINDS)), [])

print()
print("-- the rating figures the interface used to parse --")
me = list_of_competitors["Protagonist"]
others = [n for n in list_of_competitors if n != "Protagonist"][:3]
me.strength = 40
me.opponent = [list_of_competitors[n] for n in others]
me.win_order = [1, 0, 1]

facts = []
stop = narrator.listen(
    lambda kind, text, f: facts.append(f) if "rating_change" in f else None)
spoken = io.StringIO()
with redirect_stdout(spoken):
    elo_rating()
stop()

lines = [l for l in spoken.getvalue().splitlines() if ":" in l and "[" in l]
check("one fact per match", len(facts), 3)
check("one printed line per match", len(lines), 3)
check("the facts name the opponents in match order",
      [f["nickname"] for f in facts],
      [list_of_competitors[n].nickname for n in others])
check("and carry the result", [f["won"] for f in facts], [True, False, True])
check("the number in the fact is the number in the line",
      all(("[%+d]" % f["rating_change"]).replace("+0", "+0") in line
          or str(abs(f["rating_change"])) in line
          for f, line in zip(facts, lines)))

# the bug the rewrite removed: a repeat opponent used to be scored twice
# with the first meeting's result
me.opponent = [list_of_competitors[others[0]]] * 2
me.win_order = [1, 0]
facts = []
stop = narrator.listen(
    lambda kind, text, f: facts.append(f) if "rating_change" in f else None)
with redirect_stdout(io.StringIO()):
    elo_rating()
stop()
check("facing the same opponent twice scores each meeting separately",
      [f["won"] for f in facts], [True, False])

print()
print("-- the engine speaks through one door --")
import ast as _ast                                                 # noqa: E402

BATTLE = sorted(os.path.join("Scripts/Battle", f)
                for f in os.listdir("Scripts/Battle") if f.endswith(".py"))
stray = []
dumps = 0
for path in BATTLE:
    tree = _ast.parse(io.open(path, encoding="utf-8").read())
    for node in _ast.walk(tree):
        if not (isinstance(node, _ast.Call)
                and isinstance(node.func, _ast.Name)
                and node.func.id == "print"):
            continue
        # `print(x, end='')` and multi-argument prints are the per-turn state
        # dump, which is debug output rather than something the game says
        if node.keywords or len(node.args) != 1:
            dumps += 1
            continue
        stray.append("%s:%d" % (path.replace(chr(92), "/"), node.lineno))

check("nothing in the battle engine prints speech directly", stray, [])
print("   %d state-dump prints left alone (they are not speech)" % dumps)

says = sum(io.open(p, encoding="utf-8").read().count("narrator.say(")
           for p in BATTLE)
check("the battle engine says %d lines through the narrator" % says,
      says > 100)

kinds = set()
for path in BATTLE:
    tree = _ast.parse(io.open(path, encoding="utf-8").read())
    for node in _ast.walk(tree):
        if (isinstance(node, _ast.Call)
                and _ast.unparse(node.func) == "narrator.say"
                and len(node.args) > 1
                and isinstance(node.args[1], _ast.Constant)):
            kinds.add(node.args[1].value)
check("every kind used is declared in KINDS",
      sorted(kinds - set(narrator.KINDS)), [])
print("   kinds in use: %s" % ", ".join(sorted(kinds)))

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
