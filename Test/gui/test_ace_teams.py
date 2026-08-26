"""A competitor's designed team lives in competitors.csv, in one place.

There used to be two files. `Data/custom_team.csv` held one Pokemon per
competitor with its IV, ability and moveset, keyed by ID, and was re-read in
full for every competitor on every round. `competitors.csv` held the same
competitors' ace Pokemon as bare names in Poke1..Poke6. So a competitor's
team was written down in two places, and only one of them could say anything
beyond a species name.

Now a Poke cell is either a bare name or a name with the details that make it
theirs:

    Grimmsnarl|iv=20|ability=Prankster|moves=Bulk Up,Foul Play,Play Rough

Any of the six slots can carry detail, not just one, and a malformed cell is
an error at startup naming the competitor and the column.
"""
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
from Scripts.Data.competitors import (Ace, AceError, list_of_competitors,
                                      read_ace, roll_iv)            # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                    # noqa: E402
from Scripts.Game.game_procedure import team_generation             # noqa: E402
from Scripts.Game.game_system import GameSystem                     # noqa: E402
from copy import deepcopy                                           # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


print("-- reading a cell --")
plain = read_ace("Durant", "test")
check("a bare name is just a name", (plain.name, plain.detailed),
      ("Durant", False))
full = read_ace("Pikachu|iv=60|ability=Static|moves=Iron Tail,Thunderbolt",
                "test")
check("details are read off the cell",
      (full.name, full.iv, full.ability, full.moves),
      ("Pikachu", 60, "Static", ["Iron Tail", "Thunderbolt"]))
check("a name with spaces survives", read_ace("Alolan Raichu").name,
      "Alolan Raichu")
check("so does a move with spaces",
      read_ace("Gyarados|moves=Dragon Dance,Waterfall").moves,
      ["Dragon Dance", "Waterfall"])
check("one detail on its own is fine",
      (read_ace("Pikachu|iv=60").iv, read_ace("Pikachu|iv=60").moves),
      (60, None))

print()
print("-- a cell that makes no sense is caught at read time --")
for cell, wanted in (("Gyarados|iv=abc", "not a number"),
                     ("Gyarados|speed=fast", "knows no detail"),
                     ("Gyarados|moves=", "nothing in it"),
                     ("Gyarados|ability=", "empty ability"),
                     ("|iv=31", "no name"),
                     ("Gyarados|iv=-4", "negative")):
    raised = ""
    try:
        read_ace(cell, "test")
    except AceError as problem:
        raised = str(problem)
    check("%-22s is refused (%s)" % (cell, wanted), wanted in raised)

print()
print("-- the roster --")
designed = [(name, entry) for name, competitor in list_of_competitors.items()
            for entry in competitor.team
            if isinstance(entry, Ace) and entry.detailed]
check("every competitor's ace slots are Aces, not raw strings",
      sorted({type(entry).__name__ for c in list_of_competitors.values()
              for entry in c.team}), ["Ace"])
check("the detailed cells came across (%d of them)" % len(designed),
      len(designed) > 0)
for name, ace in sorted(designed):
    print("   %-19s %-12s iv=%-3s %s" % (name, ace.name, ace.iv, ace.ability))
check("every ace names a Pokemon that exists",
      sorted({a.name for _, a in designed} - set(list_of_pokemon)), [])
check("...and so does every bare one",
      sorted({e.name for c in list_of_competitors.values() for e in c.team}
             - set(list_of_pokemon)), [])

print()
print("-- building a team from them --")
GameSystem.stage = 5
random.seed(11)
ash = deepcopy(list_of_competitors["Ash Ketchum"])
team = team_generation(ash)
pikachu = next((p for p in team if p.name == "Pikachu"), None)
check("the designed ace is on the team", pikachu is not None)
if pikachu is not None:
    # The number is the designer's -- it has been 60 and is now higher.
    # What a test can hold it to is that the *cell* is what decided it, and
    # that a pinned IV is allowed past the 31 a wild roll can reach.
    _pinned = next(a.iv for a in list_of_competitors["Ash Ketchum"].team
                   if a.name == "Pikachu")
    check("...with the IV the cell pinned (%d), not a rolled one" % _pinned,
          pikachu.iv, [_pinned] * 6)
    check("...which is above the usual ceiling", _pinned > 31)
    check("...its own ability", pikachu.ability, ["Static"])
    check("...and its own moveset",
          pikachu.moveset,
          ["Quick Attack", "Iron Tail", "Thunderbolt", "Electro Ball"])
others = [p for p in team if p is not pikachu]
check("the rest of the team was rolled", len(others) > 0)
check("...each with one ability", {len(p.ability) for p in others}, {1})
check("...and at most four moves",
      max(len(p.moveset) for p in others) <= 4)
check("...with IVs inside the normal range",
      all(0 <= value <= 31 for p in others for value in p.iv))

print()
print("-- a Pokemon already built is left alone --")
random.seed(5)
someone = deepcopy(list_of_competitors["Goblin"])
first = team_generation(someone)
kept = deepcopy(first[0])
kept.iv = [7] * 6
kept.moveset = list(kept.moveset)
someone.team = [kept]
again = team_generation(someone)
survivor = next((p for p in again if p.name == kept.name), None)
check("a kept Pokemon keeps its own IVs rather than being rerolled",
      survivor is not None and survivor.iv == [7] * 6)

print()
print("-- a mistyped species is an error, not a broken Pokemon --")
broken = deepcopy(list_of_competitors["Goblin"])
broken.team = [Ace("Grimmsnarrl")]        # one letter out
raised = ""
try:
    team_generation(broken)
except KeyError as problem:
    raised = str(problem)
check("it says which name it cannot find", "Grimmsnarrl" in raised)
check("...and where to look", "competitors.csv" in raised)

print()
print("-- the old files are gone --")
for path in ("Data/custom_team.csv", "Scripts/Data/custom_team.py"):
    check("%s no longer exists" % path, os.path.exists(path), False)

print()
print("-- a pinned IV is rolled between its own bounds --")
random.seed(1)
check("iv=60 gives exactly 60", roll_iv(Ace("x", iv=60), 0), [60] * 6)
rolled = roll_iv(Ace("x", iv=20), 0)
check("iv=20 rolls between 20 and 31",
      all(20 <= value <= 31 for value in rolled))
bare = roll_iv(Ace("x"), 24)
check("no iv at all rolls from the tier floor",
      all(24 <= value <= 31 for value in bare))

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
