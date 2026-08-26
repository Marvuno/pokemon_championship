"""Every prompt gets its own buttons, and nobody else's.

`GUI/prompt_parser.py` turns a terminal question into buttons by reading the
prompt *and* whatever was printed just before it -- which it has to, because
several screens print their list first and then ask a bare question. The risk
in that is picking up a list belonging to the previous screen, and it
happened: scouting an opponent left a ghost button named after their sixth
Pokemon on the pre-battle menu, which answered `5` to a menu with no option 5
and so vanished with no effect.

The rule is disjointness -- a block printed earlier is only used when it is
numbered differently from what the prompt lists itself. This suite is the
real prompts of the game, on both sides of that rule.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

from GUI.prompt_parser import parse                                # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else "\n    got  %r\n    want %r"
                          % (got, want)))
    if not ok:
        FAILURES.append(what)


def values(prompt, recent=""):
    return [c.value for c in parse(prompt, recent).choices]


def labels(prompt, recent=""):
    return [c.label for c in parse(prompt, recent).choices]


# -- the real prompts, copied from the engine ------------------------------
MENU = ("What do you want to do?\n"
        "0: Battle || 1: View My Pokemon || 2: Switch Pokemon Order"
        " || 3: Scout Opponent || 4: Check History\n--> ")
SWITCH = ("Which pokemon would you like to switch in?\n"
          "8: View your pokemon\n9: Return to battle\n--> ")
MOVE = "What is the move for Pikachu?\n--> "

#: what about_opponent leaves on screen after a successful scout
SCOUT = ("You have sized up Coco's entire team:\n"
         "  0: Alolan Raichu\n  1: Pikachu\n  2: Lanturn\n"
         "  3: Rotom\n  4: Zapdos\n  5: Magnezone\n\n"
         "Ace: Alolan Raichu\n")

print("-- the ghost button --")
check("a scouted team leaves the menu alone",
      values(MENU, SCOUT), ["0", "1", "2", "3", "4"])
check("...so no Pokemon name reaches the menu",
      any("Magnezone" in label for label in labels(MENU, SCOUT)), False)
# the size of the scouted team decided whether anything showed: a team of six
# against a five-option menu left exactly one number free, which is why this
# looked intermittent rather than broken
for size in range(1, 7):
    team = "sized up:\n" + "".join("  %d: Mon%d\n" % (i, i)
                                   for i in range(size))
    check("a scouted team of %d leaves no ghost" % size,
          values(MENU, team), ["0", "1", "2", "3", "4"])
check("the menu is itself with nothing before it",
      values(MENU), ["0", "1", "2", "3", "4"])

print()
print("-- and the screens that genuinely need the block above them --")
# The switch window is the case a naive fix breaks: it lists only its two
# sentinels inline and gets the Pokemon themselves from the lines above.
check("the switch window still finds the party",
      values(SWITCH, "0: Pikachu\n1: Charizard\n2: Blastoise (Fainted)\n"),
      ["0", "1", "2", "8", "9"])
check("...including a fainted one, named as such",
      "Blastoise (Fainted)" in labels(
          SWITCH, "0: Pikachu\n1: Charizard\n2: Blastoise (Fainted)\n"))
check("move selection reads the moveset above it",
      values(MOVE, "0: Switching\n1: Thunderbolt\n2: Quick Attack\n"),
      ["0", "1", "2"])
check("team selection reads a printed tuple list",
      values("Which pokemon do you not want to bring?\n--> ",
             "\n[(0, 'Pikachu'), (1, 'Onix'), (2, 'Snorlax')]\n"),
      ["0", "1", "2"])
# Python's repr quotes a name containing an apostrophe with double quotes,
# so a team list mixes both kinds in one line. The tuple pattern used to end
# the name at either quote, which meant Farfetch'd and Sirfetch'd simply were
# not on the switch-order or keep-team screens -- and the rest of the list
# parsed fine, so nothing looked wrong.
_AWKWARD = ["Pikachu", "Farfetch'd", "Onix", "Sirfetch'd", "Mr. Mime",
            "Type: Null"]
_PRINTED = str([(i, n) for i, n in enumerate(_AWKWARD)])
check("every Pokemon survives a printed tuple list, apostrophes included",
      labels("Which pokemon would you like to swap to be the first?",
             _PRINTED), _AWKWARD)
check("...and a sentinel beside it still lands",
      values("Which pokemon would you like to swap to be the first?",
             _PRINTED + chr(10) + "9: No Swapping")[-1], "9")

check("the boxed start menu still parses",
      labels("Please select an option.\n--> ",
             "| 0 NEW GAME |\n| 1 CONTINUE |\n| 2 HISTORY |\n"),
      ["New Game", "Continue", "History"])
check("a sentinel in prose joins a list above it",
      values("Enter 10 to keep the whole team.\n--> ",
             "0: Pikachu\n1: Onix\n2: Snorlax\n"),
      ["0", "1", "2", "10"])

print()
print("-- the rule itself --")
# disjoint: kept. overlapping: dropped whole, not merged around.
check("an overlapping block is dropped entirely, not merged",
      values("Pick one.\n0: Alpha || 1: Beta\n--> ",
             "0: Stale\n1: Older\n2: Oldest\n"), ["0", "1"])
check("a disjoint block is kept in full",
      values("Pick one.\n7: Alpha || 8: Beta\n--> ",
             "0: Fresh\n1: Also fresh\n"), ["0", "1", "7", "8"])
check("the prompt's own labels always win",
      labels("Pick one.\n0: Alpha || 1: Beta\n--> ",
             "0: Stale\n1: Older\n"), ["Alpha", "Beta"])

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
