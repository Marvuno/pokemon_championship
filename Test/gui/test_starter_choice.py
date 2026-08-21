"""The starter offer: which Pokemon can appear, and what the player is told.

Medium tier, uncapped; or High tier with a base stat total at or below 500.
The cap is on High alone, because High is where the 600-total legendaries
live and one of those decides a career in round one. Medium never gets near
that, so it is not capped -- and a test that checked one flat cap across both
tiers would pass while quietly halving the Medium offer.
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

import builtins                                                    # noqa: E402
import io                                                          # noqa: E402
from contextlib import redirect_stdout                             # noqa: E402

from Scripts.Game import start_interface as si                     # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                   # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


pool = [n for n, m in list_of_pokemon.items() if si._may_start(m)]
by_tier = {}
for name in pool:
    by_tier.setdefault(list_of_pokemon[name].tier, []).append(
        list_of_pokemon[name].total_stats)

check("High is capped at 500", si.STARTER_MAX_BASE_STATS.get("High"), 500)
check("Medium is not capped", "Medium" in si.STARTER_MAX_BASE_STATS, False)
check("nothing in the pool is off-tier", sorted(by_tier), ["High", "Medium"])
check("no High starter is over 500", max(by_tier["High"]) <= 500)

# the half that a flat cap across both tiers would get wrong: Medium keeps
# its Pokemon above 500
big_medium = [n for n, m in list_of_pokemon.items()
              if getattr(m, "tier", None) == "Medium"
              and getattr(m, "total_stats", 0) > 500]
check("Medium keeps its %d Pokemon over 500" % len(big_medium),
      sorted(n for n in big_medium if n not in pool), [])
check("every Medium tier Pokemon is eligible",
      len(by_tier["Medium"]),
      sum(1 for m in list_of_pokemon.values()
          if getattr(m, "tier", None) == "Medium"))

# and the cap does bite on High
over = [n for n, m in list_of_pokemon.items()
        if getattr(m, "tier", None) == "High"
        and getattr(m, "total_stats", 0) > 500]
check("the cap excludes %d High tier Pokemon" % len(over), len(over) > 0)
check("...and excludes nothing else",
      sorted(n for n, m in list_of_pokemon.items()
             if m.tier in si.STARTER_TIERS and n not in pool), sorted(over))
print("   Medium: %d, up to %d (uncapped)"
      % (len(by_tier["Medium"]), max(by_tier["Medium"])))
print("   High:   %d, up to %d (capped); biggest turned away %d"
      % (len(by_tier["High"]), max(by_tier["High"]),
         max(list_of_pokemon[n].total_stats for n in over)))


class _Person:
    def __init__(self):
        self.team = []


# run the real offer a few times and check every Pokemon it puts up
answers = iter(["0"] * 200)
real_input = builtins.input
builtins.input = lambda prompt="": next(answers)
try:
    seen, said = set(), ""
    for seed in range(40):
        random.seed(seed)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            si.choose_starter(_Person())
        said = buffer.getvalue()
        for name in list_of_pokemon:
            if "%s (" % name in said:
                seen.add(name)
finally:
    builtins.input = real_input

check("every Pokemon actually offered is in the pool",
      sorted(n for n in seen if n not in pool), [])
check("40 offers put up a decent spread (%d distinct)" % len(seen),
      len(seen) > 20)

check("the prompt says what is being chosen",
      "Please choose your starter Pokemon" in said)
check("...and that the other five come after it",
      "the other five are drawn around it" in said)
check("...and what is deliberately hidden",
      "its ability, its IVs and its moves" in said)

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
