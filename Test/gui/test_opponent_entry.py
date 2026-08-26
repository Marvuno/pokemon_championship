"""The Pokedex entry for a competitor, and what it may not give away.

The Pokedex publishes **no roster**. Which Pokemon a competitor brings is
what About Opponent makes you earn, so the entry names only the ace their own
Strategy blurb already names -- that text is on the same screen, so naming it
reveals nothing new. All this adds is the typing, which is what a player
reads the line for.

The strongest competitors have all six Poke columns filled. Listing those
would hand the whole designed team over for free.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                 # noqa: F401,E402
from GUI import codex                                               # noqa: E402
from Scripts.Data.competitors import list_of_competitors            # noqa: E402
from Scripts.Data.moves import list_of_moves                        # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                    # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


data = codex.build(list_of_pokemon, list_of_moves, list_of_competitors)
entries = {entry["name"]: entry for entry in data["opponents"]}

print("-- the ace, with its typing --")
_aceless = sorted(n for n, e in entries.items() if not e.get("aces"))
check("every competitor names one (%d competitors)" % len(entries),
      _aceless, [])
for name, expected in (("Jason", ["Durant"]),
                       ("Expert Cynthia", ["Garchomp"]),
                       ("Goblin", ["Grimmsnarl"])):
    entry = entries.get(name)
    check("%s's ace is %s" % (name, expected[0]),
          [a["name"] for a in entry["aces"]], expected)
marvin = entries.get("Champion Marvin")
check("a blurb naming two gets both",
      len(marvin["aces"]) if marvin else 0, 2)
check("every ace carries its typing",
      all(a["types"] for e in entries.values() for a in e["aces"]))
check("...and a triple typing survives",
      next((a["types"] for a in marvin["aces"]
            if a["name"] == "Armadragdon"), []),
      ["Dragon", "Flying", "Steel"])

print()
print("-- and nothing else about them --")
extra = sorted({key for e in entries.values() for a in e["aces"]
                for key in a} - {"name", "types"})
check("only the name and the typing are published", extra, [])
check("no entry carries a roster", [k for k in data["opponents"][0]
                                    if k == "roster"], [])

# the point of the whole restriction
biggest = max(len(c.team) for c in list_of_competitors.values())
most = max(len(e["aces"]) for e in entries.values())
check("the largest designed team is %d Pokemon" % biggest, biggest, 6)
check("...but no entry reveals more than 2", most, 2)
leaked = [(name, a["name"]) for name, e in entries.items()
          for a in e["aces"]
          if a["name"] not in str(list_of_competitors[name].strategy or "")]
check("every ace shown is one the blurb already names", leaked, [])

# a competitor whose blurb names nothing on their team reveals nothing
# the Protagonist has no team until a run starts, so borrow somebody's
sample = next(c.team[0] for c in list_of_competitors.values() if c.team)


class Quiet:
    strategy = "Ace: somebody who is not on the team"
    team = [sample]


check("a blurb that names no team member reveals nothing",
      codex._aces_of(Quiet()), [])
check("no blurb at all reveals nothing",
      codex._aces_of(type("X", (), {"strategy": "", "team": Quiet.team})()),
      [])

print()
print("-- the panel's four sections --")
# About Them, Quote, Ace, Character Ability -- in that order, and each with
# something to show. The ability is named *and* explained: naming it alone
# says nothing, which is the reason a player looked it up.
for name in ("Auraia", "Dulunga", "Expert Cynthia"):
    entry = entries[name]
    check("%s has a write-up" % name, len(entry["description"]) > 40)
    check("...with no hard line breaks left in it",
          chr(10) in entry["description"], False)
    check("...a quote", bool(entry["quote"]))
    check("...an ace with a typing",
          bool(entry["aces"]) and all(a["types"] for a in entry["aces"]))
    check("...and an ability that says what it does",
          bool(entry["ability"]) and bool(entry["ability_effect"]))

check("every competitor's ability is explained, not just named",
      sorted(e["nickname"] for e in entries.values()
             if e["ability"] and not e["ability_effect"]), [])
check("no write-up anywhere still carries a hard line break",
      sorted(e["nickname"] for e in entries.values()
             if chr(10) in e["description"]), [])
check("nor any quote",
      sorted(e["nickname"] for e in entries.values()
             if chr(10) in e["quote"]), [])

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
