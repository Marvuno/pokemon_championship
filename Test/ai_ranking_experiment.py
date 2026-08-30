"""Does the smart AI's move-ranking rule cost it battles?

`smart_ai_select_move` ends by sorting its scored moves like this:

    ranked = sorted(ai_move_score, key=lambda x: (-score[x][0],    # priority
                                                  -score[x][3]))   # score

Priority is an integer nudged by about a dozen conditions; score is damage
weighted by whether it would actually knock the target out. Priority being
the *primary* key means a move one point higher wins however much better the
alternative scores -- a move that would kill, passed over for a jab.

Measured over 40 battles (1,291 real decisions): priority overrides the
better-scoring move on 13.6%, and gives up 50 or more score -- a likely
knockout -- on 4.8%. Two thirds of decisions have every move at equal
priority, where the rule cannot matter either way.

This asks whether that costs anything, holding everything else equal:

    the same team       both sides fly identical copies of one team -- same
                        species, IVs, abilities, movesets
    the same rating     both carry the same `strength`, so nothing that
                        reads rating can differ
    no character ability  cleared on both sides
    both orientations   every team played twice with the sides swapped, so
                        any advantage in being side A cancels
    a control arm       the shipped rule against itself, which has to come
                        out at 50% or the harness is measuring its own
                        asymmetry rather than the rule

The only difference between the sides is `move_ranking`, which the AI reads
off the acting trainer. No dispatcher is needed: in verbose mode both sides
already go through `smart_ai_select_move`, and each reads its own.

Teams are drawn at five ratings, because the head-to-head study found the
smart AI's value depends on the team it is flying -- a smarter pilot needs
something to fly.

    python Test/ai_ranking_experiment.py
    python Test/ai_ranking_experiment.py --teams 40        quicker, rougher
    python Test/ai_ranking_experiment.py --workers 4

Writes Documentation/ai_ranking_experiment.md.
"""
import argparse
import io
import math
import os
import random
import sys
import time
from contextlib import redirect_stdout, suppress
from copy import deepcopy
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

# A harness, not the game: no window, and no sound. See Scripts/Art/music.py.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

STAGE = 5                       # 6v6, the full-strength matchup
TEAMS = 120                     # per band, per arm; each played twice
BANDS = (20, 60, 150, 300, 600)

CONTROL = "control"
_CACHE = {}


def _engine():
    # battle_cycle FIRST. Scripts/ modules star-import each other and the
    # game always enters through battle_cycle; importing from the middle of
    # that web leaves a half-built module behind it.
    import Scripts.Battle.battle_cycle as cycle
    import Scripts.Battle.ai as ai_module
    from Scripts.Data.battlefield import Battleground
    from Scripts.Data.competitors import list_of_competitors
    from Scripts.Game.game_procedure import team_generation
    from Scripts.Game.game_system import GameSystem
    GameSystem.stage = STAGE
    return (list_of_competitors, Battleground, cycle.battle_setup,
            team_generation, ai_module)


def _cached_engine():
    if "engine" not in _CACHE:
        _CACHE["engine"] = _engine()
    return _CACHE["engine"]


def seed_for(rating, trial, tag):
    """A reproducible seed.

    Arithmetic, never `hash()`. String and tuple hashes are salted per
    process and the workers are separate processes, so a hash-derived seed
    would hand the two orientations of one trial *different teams* -- quietly
    destroying the only control this experiment has.
    """
    return (rating * 1000003 + trial * 9176 + tag * 7919) & 0x7FFFFFFF


def play(task):
    """One battle. Returns (rating, "variant" | "baseline" | "draw")."""
    rating, trial, variant_first, arm = task
    roster, Battleground, battle_setup, team_generation, ai_module = _cached_engine()

    # One team, built once, then copied. Seeded from (rating, trial) alone --
    # not the orientation -- so both orientations fly the same team. That is
    # the entire control.
    random.seed(seed_for(rating, trial, 1))
    builder = deepcopy(roster["Protagonist"])
    builder.main = False          # so team_generation fills all six
    builder.team = []             # no designed aces: a random team
    builder.strength = rating
    with redirect_stdout(io.StringIO()):
        team = team_generation(builder)

    side_a, side_b = deepcopy(builder), deepcopy(builder)
    for index, side in enumerate((side_a, side_b)):
        side.name = side.nickname = ("A", "B")[index]
        side.strength = rating
        side.ability = ""         # character abilities off
        side.team = deepcopy(team)

    base = ai_module.PRIORITY_FIRST
    tried = base if arm == CONTROL else arm
    side_a.move_ranking = tried if variant_first else base
    side_b.move_ranking = base if variant_first else tried

    ground = Battleground()
    ground.verbose = True         # the AI-vs-AI path, both sides choosing
    random.seed(seed_for(rating, trial, 2))
    with redirect_stdout(io.StringIO()):
        with suppress(RecursionError):
            battle_setup(side_a, side_b, side_a.team, side_b.team, ground)

    if side_a.score == side_b.score:
        return (rating, "draw")
    ahead = side_a if side_a.score > side_b.score else side_b
    # In the control neither side carries a variant, so report side A as the
    # "variant". The tally then reads as side A's win rate, which must be 50%.
    if arm == CONTROL:
        return (rating, "variant" if ahead is side_a else "baseline")
    carries = side_a if variant_first else side_b
    return (rating, "variant" if ahead is carries else "baseline")


def band_rate(results):
    """Win rate counting a draw as half, and the 95% interval on it."""
    total = len(results)
    if not total:
        return 0.0, 0.0, 0
    wins = sum(1 for _, who in results if who == "variant")
    draws = sum(1 for _, who in results if who == "draw")
    rate = (wins + draws * 0.5) / total
    margin = 1.96 * math.sqrt(max(rate * (1 - rate), 1e-9) / total)
    return rate * 100, margin * 100, total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", type=int, default=TEAMS)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--arms", default="",
                        help="comma-separated arms, e.g. control,blended=10,"
                             "blended=50 -- a blended arm may carry the price "
                             "of one priority point in score")
    parser.add_argument("--out", default=os.path.join(
        ROOT, "Documentation", "ai_ranking_experiment.md"))
    args = parser.parse_args()

    import Scripts.Battle.battle_cycle                      # noqa: F401
    import Scripts.Battle.ai as ai_module
    arms = tuple(args.arms.split(",")) if args.arms else (
        CONTROL, ai_module.PRIORITY_THEN_DAMAGE,
        ai_module.SCORE_FIRST, ai_module.BLENDED)

    tasks = [(rating, trial, first, arm)
             for arm in arms
             for rating in BANDS
             for trial in range(args.teams)
             for first in (True, False)]
    workers = args.workers or max(1, (os.cpu_count() or 2) - 2)
    print("%d battles across %d workers" % (len(tasks), workers))

    started = time.time()
    with Pool(workers) as pool:
        done = pool.map(play, tasks, chunksize=8)
    took = time.time() - started

    by_arm = {}
    for task, row in zip(tasks, done):
        by_arm.setdefault(task[3], []).append(row)

    head = "| rule | " + " | ".join("r%d" % band for band in BANDS) + " | overall |"
    lines = ["# The smart AI's move-ranking rule",
             "",
             "%d battles, %d teams per band per arm, both orientations, in "
             "%.0f seconds." % (len(tasks), args.teams, took),
             "",
             "Win rate of each variant against the shipped "
             "`(-priority, -score)` rule, with everything else held equal. "
             "The control is that rule against itself and has to read 50%.",
             "",
             head,
             "|---|" + "---|" * (len(BANDS) + 1)]
    for arm in arms:
        rows = by_arm[arm]
        cells = []
        for band in BANDS:
            rate, margin, _ = band_rate([r for r in rows if r[0] == band])
            cells.append("%.1f +/-%.1f" % (rate, margin))
        rate, margin, _ = band_rate(rows)
        lines.append("| %s | %s | **%.1f +/-%.1f** |"
                     % (arm, " | ".join(cells), rate, margin))
    report = chr(10).join(lines) + chr(10)
    with io.open(args.out, "w", encoding="utf-8") as handle:
        handle.write(report)
    print(report)


if __name__ == "__main__":
    main()
