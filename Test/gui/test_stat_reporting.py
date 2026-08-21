"""What the player is told when a stat moves, or a character ability fires.

Both used to be nearly invisible. A stat change printed the raw contents of
`applied_modifier` -- `Pikachu | Attack -1` -- which is a debug dump, and it
reported what was *asked for* rather than what happened, so a Pokemon already
at the bottom of its range was told its Attack fell again. A character
ability said only `Character Ability: Procrastination`: not whose, and not
what it did.
"""
import io
import os
import re
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
from Scripts.Battle.constants import MODIFIER                      # noqa: E402
from Scripts.Data import character_abilities as CA                 # noqa: E402
from Scripts.Data.competitors import (ability_text,
                                      list_of_competitors)           # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


class Mon:
    side_color = ""
    name = "Pikachu"


def said(before, after, asked):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        narrator.stat_change(Mon(), before, after, asked)
    return [l.strip() for l in buffer.getvalue().splitlines() if l.strip()]


NONE = [0] * 9


def one(index, value):
    out = list(NONE)
    out[index] = value
    return out


print("-- stat changes --")
check("a one-stage drop names the stat and the direction",
      said(NONE, one(1, -1), one(1, -1)),
      ["Pikachu's Attack fell! (-1)"])
check("two stages reads differently from one",
      said(NONE, one(5, 2), one(5, 2)),
      ["Pikachu's Speed rose sharply! (+2)"])
check("three stages differently again",
      said(NONE, one(2, -3), one(2, -3)),
      ["Pikachu's Defense severely fell! (-3)"])
check("the resulting stage is shown, not just the step",
      said(one(1, 1), one(1, 3), one(1, 2)),
      ["Pikachu's Attack rose sharply! (+3)"])

# the old code's actual bug: it announced a change that could not happen
floor = one(1, -6)
check("a stat already at the bottom says so instead of falling again",
      said(floor, floor, one(1, -1)),
      ["Pikachu's Attack won't go any lower!"])
ceiling = one(1, 6)
check("...and at the top", said(ceiling, ceiling, one(1, 1)),
      ["Pikachu's Attack won't go any higher!"])

asked = list(NONE)
asked[1] = asked[2] = -1
check("a mixed change gets a line each",
      said(NONE, asked, asked),
      ["Pikachu's Attack fell! (-1)", "Pikachu's Defense fell! (-1)"])
check("a stat nobody aimed at is not mentioned",
      said(NONE, one(1, -1), NONE), [])

facts = []
stop = narrator.listen(lambda kind, text, f: facts.append((kind, f)))
with redirect_stdout(io.StringIO()):
    narrator.stat_change(Mon(), NONE, one(1, -2), one(1, -2))
stop()
check("the line carries the facts behind it",
      facts, [("stat", {"pokemon": "Pikachu", "stat": "Attack",
                        "delta": -2, "stage": -2})])
check("every stat name is one the engine uses",
      sorted(set(MODIFIER.values()) & {"Attack", "Defense", "Speed"}),
      ["Attack", "Defense", "Speed"])

# a change the AI is only imagining must stay quiet
class Hypothetical:
    reality = False


class Real:
    reality = True


buffer = io.StringIO()
with redirect_stdout(buffer):
    narrator.stat_change(Mon(), NONE, one(1, -1), one(1, -1), Hypothetical())
check("a change the AI is only scoring is not announced",
      buffer.getvalue(), "")
buffer = io.StringIO()
with redirect_stdout(buffer):
    narrator.stat_change(Mon(), NONE, one(1, -1), one(1, -1), Real())
check("...but a real one still is", buffer.getvalue().strip(),
      "Pikachu's Attack fell! (-1)")
check("and with no battleground given it still speaks",
      said(NONE, one(1, -1), one(1, -1)),
      ["Pikachu's Attack fell! (-1)"])

# every site that announces a stat change hands over the battleground, or
# the AI's scoring pass leaks phantom lines into the log
import ast as _ast                                                 # noqa: E402
missing = []
for path in ("Scripts/Battle/ability_effects.py",
             "Scripts/Data/character_abilities.py",
             "Scripts/Battle/move_additional_effect.py"):
    tree = _ast.parse(io.open(path, encoding="utf-8").read())
    for node in _ast.walk(tree):
        if (isinstance(node, _ast.Call)
                and _ast.unparse(node.func).endswith("stat_change")
                and len(node.args) < 5):
            missing.append("%s:%d" % (path.replace(chr(92), "/"),
                                      node.lineno))
check("every stat_change call passes the battleground", missing, [])

print()
print("-- character abilities --")
held = {c.ability for c in list_of_competitors.values()
        if getattr(c, "ability", "")}
check("every competitor's ability has an official description",
      sorted(c.nickname for c in list_of_competitors.values()
             if c.ability and not ability_text(c)), [])
check("...and it comes from their own Strategy cell, not from code",
      ability_text(list_of_competitors["Goblin"]),
      "decrease speed, but increase accuracy.")


class Ground:
    reality = True


def announce(side, ground):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        CA.notice(ground, side)
    return re.sub(r"\x1b\[[0-9;]*m", "",
                  buffer.getvalue()).strip()


someone = next(c for c in list_of_competitors.values()
               if getattr(c, "ability", "") == "Procrastination")
ground = Ground()
first = announce(someone, ground)
# The wording is not restated here: it belongs to Data/competitors.csv and
# the designer edits it. Restating it in the test is how a second, drifting
# copy gets started -- which is exactly what this replaced.
check("the first firing says whose it is and what it does",
      first,
      "* %s's character ability: Procrastination -- %s"
      % (someone.nickname, ability_text(someone)))
check("...and that wording is the CSV's, not the code's",
      ability_text(someone) in (someone.strategy or ""))
check("the second says it fired without repeating the explanation",
      announce(someone, ground),
      "* %s's character ability: Procrastination" % someone.nickname)
check("a new battle explains it again",
      announce(someone, Ground()), first)

quiet = io.StringIO()
with redirect_stdout(quiet):
    class NotReal:
        reality = False
    CA.notice(NotReal(), someone)
check("nothing is said while the AI is only scoring a move",
      quiet.getvalue(), "")

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
