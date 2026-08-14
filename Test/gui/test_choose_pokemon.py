"""Engine-level test of choose_pokemon's new go-back paths.

Drives the real function with scripted input() answers and checks what
happens to the team.
"""
import builtins
import sys
from copy import deepcopy

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
import os
os.chdir(ROOT)

# the game's modules star-import each other, so entering through the same
# door main.py uses is the only order that resolves
import main                                                   # noqa: E402,F401
from Scripts.Data.pokemon import list_of_pokemon              # noqa: E402
import Scripts.Battle.battle_win_condition as W               # noqa: E402

MONS = ['Sunkern', 'Magikarp', 'Pikachu', 'Psyduck', 'Luvdisc', "Farfetch'd"]
THEIRS = ['Mawile', 'Onix', 'Beedrill', 'Parasect', 'Alolan Raticate', 'Watchog']


def build(names):
    team = []
    for name in names:
        mon = deepcopy(list_of_pokemon[name])
        mon.iv = [10] * 6
        mon.total_iv = 60
        mon.nominal_base_stats = [b + 10 for b in mon.base_stats]
        mon.ability = [mon.ability[0]] if isinstance(mon.ability, list) \
            else [mon.ability]
        mon.moveset = ["Switching"] + list(mon.moveset)[:4]
        team.append(mon)
    return team


class Side:
    def __init__(self, stage, names, level="Elite", bench=0):
        self.stage = stage
        full = build(names)
        # team_selection() parks whoever you held back in unused_team
        self.team = full[:len(full) - bench] if bench else full
        self.unused_team = full[len(full) - bench:] if bench else []
        self.side_color = ""
        self.level = level
        self.strength = 300


class Ground:
    verbose = False


def run(script, mine=MONS, theirs=THEIRS, my_stage=2, their_stage=1,
        bench=0):
    asked = []
    answers = list(script)

    def fake_input(prompt=""):
        asked.append(prompt)
        if not answers:
            raise AssertionError("engine asked more than the script covers:\n"
                                 + prompt[:120])
        return answers.pop(0)

    me, them = Side(my_stage, mine, bench=bench), Side(their_stage, theirs)
    real_input, real_print = builtins.input, builtins.print
    builtins.input = fake_input
    builtins.print = lambda *a, **k: None
    # the game modules star-imported print/input at import time
    for module in list(sys.modules.values()):
        if module and getattr(module, "__name__", "").startswith("Scripts"):
            for name, fn in (("input", fake_input),
                             ("print", builtins.print)):
                if hasattr(module, name):
                    setattr(module, name, fn)
    try:
        W.choose_pokemon(me, them, Ground())
    finally:
        builtins.input, builtins.print = real_input, real_print
    return ([m.name for m in me.team + me.unused_team], asked, answers)


def check(label, got, want):
    ok = got == want
    print("%-46s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    return ok

failures = 0

# --- full team: swap, but back out of the first pick, then decline ---------
team, asked, left = run(["Y", "9", "N"])
failures += not check("swap -> go back on pick 1 -> decline", team, MONS)
failures += not check("  and it re-asked swap-or-not",
                      sum("want to swap" in a for a in asked), 2)

# --- full team: swap, back out of the *second* pick, then decline ----------
team, asked, left = run(["Y", "0", "9", "N"])
failures += not check("swap -> go back on pick 2 -> decline", team, MONS)

# --- full team: back out once, then go through with it ---------------------
team, asked, left = run(["Y", "9", "Y", "2", "1"])
failures += not check("swap -> go back -> then swap for real",
                      team, MONS[:2] + [THEIRS[1]] + MONS[3:])

# --- full team: straight swap, no backing out -----------------------------
team, asked, left = run(["Y", "0", "0"])
failures += not check("swap slot 0 for their slot 0", team,
                      [THEIRS[0]] + MONS[1:])

# --- full team: decline outright ------------------------------------------
team, asked, left = run(["N"])
failures += not check("decline the swap", team, MONS)

# --- short team: take from the opponent, backing out first -----------------
short = MONS[:4]
team, asked, left = run(["Y", "9", "Y", "3"], mine=short)
failures += not check("take -> go back -> take Tyranitar",
                      team, short + [THEIRS[3]])
failures += not check("  and it re-asked take-or-organiser",
                      sum("take from the opponent" in a for a in asked), 2)

# --- short team: take straight away ---------------------------------------
team, asked, left = run(["Y", "1"], mine=short)
failures += not check("take their slot 1", team, short + [THEIRS[1]])

# --- short team: back out, then accept the organiser's -------------------
team, asked, left = run(["Y", "9", "N"], mine=short)
failures += not check("take -> go back -> organiser gives one",
                      len(team), len(short) + 1)

# --- an out-of-range index is still rejected, not treated as go-back ------
team, asked, left = run(["Y", "40", "-3", "2", "4"])
failures += not check("out-of-range indexes are re-asked", team,
                      MONS[:2] + [THEIRS[4]] + MONS[3:])

# --- losing the round asks nothing ---------------------------------------
team, asked, left = run([], mine=MONS, my_stage=1, their_stage=2)
failures += not check("a loss with a full team asks nothing", asked, [])

# --- benched Pokemon: brought 5 of 6, want to trade away the 6th ----------
team, asked, left = run(["Y", "5", "0"], bench=1)
failures += not check("the benched 6th can be swapped out",
                      team, MONS[:5] + [THEIRS[0]])
listed = [a for a in asked if "don't want on your team" in a]
failures += not check("  all six were offered",
                      sum(n in listed[0] for n in MONS), 6)

# swapping one who did play still lands in the right list
team, asked, left = run(["Y", "0", "1"], bench=1)
failures += not check("a benched roster leaves played slots alone",
                      team, [THEIRS[1]] + MONS[1:])

# with two benched, the last roster slot is still reachable
team, asked, left = run(["Y", "5", "2"], bench=2)
failures += not check("two benched: last slot still reachable",
                      team, MONS[:5] + [THEIRS[2]])

# six owned with one benched is still a full team, so it swaps not takes
team, asked, left = run(["N"], bench=1)
failures += not check("six with one benched counts as full", team, MONS)

# five owned and none benched is not full -- take, don't swap
team, asked, left = run(["Y", "0"], mine=MONS[:5])
failures += not check("five owned means take, not swap",
                      team, MONS[:5] + [THEIRS[0]])

# the organiser must not hand back a duplicate of a benched Pokemon
for _ in range(12):
    team, asked, left = run(["N"], mine=MONS[:4], bench=1)
    if len(team) != 5 or len(set(team)) != 5:
        failures += not check("organiser never duplicates a benched Pokemon",
                              team, "no duplicates")
        break
else:
    failures += not check("organiser never duplicates a benched Pokemon",
                          True, True)

print("\n%s" % ("ALL PASS" if not failures else "%d FAILURES" % failures))
sys.exit(1 if failures else 0)
