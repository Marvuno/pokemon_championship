"""What is each competitor's rating actually worth?

Every competitor except the player plays every other competitor ten times,
and each result moves both their ratings by the game's own Elo formula. The
question it answers is not "who wins" -- `ai_simulation.py` already covers
per-Pokemon win rates -- but whether the rating each competitor is *shipped*
with is the rating their team can actually earn.

    python Test/ai_rating_simulation.py                  the whole thing
    python Test/ai_rating_simulation.py --matches 2      quicker, rougher
    python Test/ai_rating_simulation.py --limit 12       first 12 competitors
    python Test/ai_rating_simulation.py --workers 4      smaller machines

Writes Documentation/ai_rating_simulation.md.


Teams follow the shipped rating, never the earned one
-----------------------------------------------------
`team_generation` picks Pokemon tiers by weights derived from
`participant.strength`, so a competitor whose rating climbs during the run
would start fielding better Pokemon and climb further -- a feedback loop
measuring itself. Every team here is rolled from the competitor as shipped,
which is what makes the final number readable as "what this roster is worth".

That has a useful consequence. Match *outcomes* depend only on the shipped
ratings, so they are all independent of each other and can be played in any
order, on any number of cores. Only the *rating arithmetic* is sequential.
So the battles run in a process pool and the rating changes are replayed
afterwards in a fixed order -- which lands on exactly the ratings a strictly
sequential run would have produced, about ten times quicker.

Order of play is ten passes over the whole pairing list rather than ten
matches per pair back to back: within a pass every competitor meets every
other once, so nobody banks ten wins against a rating that has not moved yet.

The whole run is reproducible: each battle is seeded from its position in the
schedule, and the engine replays a battle from a seed (which took three fixes
to become true -- see the determinism note in CLAUDE.md). Verified by running
a subset twice and comparing every battle result and every report line. So a
before/after comparison across an engine change measures the change, not the
noise.

The engine is not touched. Battles run through `battle_setup` with
`battleground.verbose` on -- the AI-vs-AI path both `ai_simulation.py` and
the game's own simulation use.
"""
import argparse
import io
import json
import math
import os
import random
import sys
import time
import zlib
from contextlib import redirect_stdout, suppress
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# A harness, not the game: no window, and above all no sound. A run of this
# is twenty minutes of battles and every one of them would otherwise be
# entitled to play the battle music. See Scripts/Art/music.py.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

#: which stage's team size to simulate at. ROUND_LIMIT[5] is 6, so 6v6 --
#: the full-strength matchup rather than an early-round four.
STAGE = 5
#: matches per ordered pair, unless --matches says otherwise
MATCHES = 10
#: how far a rating has to move before it is worth calling out in the report
NOTABLE = 0.25


def _engine():
    """Import the engine lazily, so a worker process pays for it once."""
    from Scripts.Data.competitors import list_of_competitors
    from Scripts.Data.battlefield import Battleground
    from Scripts.Battle.battle_cycle import battle_setup
    from Scripts.Game.game_procedure import team_generation
    from Scripts.Game.game_system import GameSystem
    GameSystem.stage = STAGE
    return (list_of_competitors, Battleground, battle_setup, team_generation)


_CACHE = {}


def _cached_engine():
    if "engine" not in _CACHE:
        _CACHE["engine"] = _engine()
    return _CACHE["engine"]


def play(task):
    """One battle. `task` is (name_a, name_b, seed); returns who won.

    Runs in a worker process. The return value is deliberately tiny -- names
    and integers -- because everything else about a battle is thrown away and
    pickling teams back to the parent would cost more than the battle did.
    """
    name_a, name_b, seed = task
    roster, Battleground, battle_setup, team_generation = _cached_engine()
    random.seed(seed)

    side_a = deepcopy(roster[name_a])
    side_b = deepcopy(roster[name_b])
    # No `team = []` here. A competitor's `team` arrives holding the ace
    # Pokemon they are designed around -- five of them have a full roster of
    # six, and thirty-six have one -- and team_generation fills the rest
    # around it. Clearing it first threw the designed team away and handed
    # them six random Pokemon instead, which flattened the whole top of the
    # field: the tier weights saturate at about rating 200, so with no aces
    # every competitor above that drew from an identical distribution and,
    # on the same seed, literally the same team. Champion Marvin fielded a
    # generic squad instead of his own. Fresh copies come from deepcopy
    # above, so there is nothing to clear.
    side_a.team = team_generation(side_a)
    side_b.team = team_generation(side_b)

    ground = Battleground()
    # the AI-vs-AI path: both sides choose their own moves. It also turns on
    # the engine's roster debug printing, which is why stdout goes in the bin.
    ground.verbose = True
    sink = io.StringIO()
    with redirect_stdout(sink):
        with suppress(RecursionError):
            battle_setup(side_a, side_b, side_a.team, side_b.team, ground)

    if side_a.score > side_b.score:
        winner = 0
    elif side_b.score > side_a.score:
        winner = 1
    else:
        winner = -1                                   # a draw; nothing moves
    return (name_a, name_b, winner, int(side_a.score), int(side_b.score))


def rating_change(own, other, won, cushion=True):
    """The game's own formula, from `elo_rating()` in game_procedure.py.

    Beating someone above you is worth more than beating someone below you,
    and losing costs in proportion to what you were rated -- the shape is
    Elo's, on a square root rather than a logistic.

    `cushion` is the engine's "starter protection", the `+1` that softens
    every loss. It is on in the game and on by default here, but it is the
    reason this report carries two ladders: see LADDERS below.
    """
    total = own + other
    if total <= 0:
        return 0
    proportion = (other / total) if won else (own / total)
    change = int(round(math.sqrt(total) * proportion * (1 if won else -1)))
    if cushion and change < 0:
        change += 1
    return change


# LADDERS ------------------------------------------------------------------
# Two ratings are tracked per competitor, from the same match results.
#
#   AS-SHIPPED   the engine's formula exactly, starter protection included.
#                This is "actually apply the rating change" and it is what a
#                career in the real game would do to these numbers.
#
#   CONVERGED    the same formula with the starter protection off.
#
# The second one exists because the first has no equilibrium. Starter
# protection rounds a loss up by one, so at an even 50% win rate a
# competitor *gains* +1 for every win/loss pair -- at rating 1 and at rating
# 750 alike (checked across the range; the net is +1 everywhere). Over the
# 570 matches each competitor plays here that is roughly +280 of pure
# inflation on everybody, which swamps the thing being measured. The
# as-shipped column is still the honest answer to "what does the game do",
# but it is the converged column that answers "what is this team worth":
# with no cushion, a competitor climbs exactly until they are winning half
# their matches against the field, which is what a rating is supposed to
# mean.
LADDERS = (("shipped_formula", True), ("converged", False))


def build_schedule(names, matches, seed=20260819):
    """`matches` passes over every unordered pair, shuffled within each pass.

    Passes rather than ten-in-a-row per pair: within a pass every competitor
    meets every other once, so nobody banks ten results against a rating that
    has not moved yet. Shuffling within the pass matters for the same reason
    -- in a fixed order the competitor listed first would always play their
    matches before anyone's rating had shifted.
    """
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    rng = random.Random(seed)
    schedule = []
    for pass_no in range(matches):
        this_pass = list(pairs)
        rng.shuffle(this_pass)
        for index, (a, b) in enumerate(this_pass):
            # A distinct seed per battle, and crc32 rather than hash():
            # Python salts string hashing per process, so hash() would hand a
            # worker a different seed than a re-run of the same schedule --
            # the one thing a seed exists to prevent.
            tag = ("%s|%s|%d|%d" % (a, b, pass_no, index)).encode("utf-8")
            schedule.append((a, b, zlib.crc32(tag)))
    return schedule


def _progress(done, total, started):
    spent = time.perf_counter() - started
    rate = done / spent if spent else 0
    left = (total - done) / rate if rate else 0
    print("    %6d/%d  %5.1f%%  %4.0f battles/s  ~%.1f min left"
          % (done, total, 100.0 * done / total, rate, left / 60.0),
          flush=True)


def run(names, matches, workers, report_every=2000):
    schedule = build_schedule(names, matches)
    total = len(schedule)
    print("%d competitors, %d pairs, %d matches each -> %d battles"
          % (len(names), len(names) * (len(names) - 1) // 2, matches, total))
    print("using %d worker process(es)" % workers, flush=True)

    started = time.perf_counter()
    results = []
    if workers <= 1:
        for index, task in enumerate(schedule, 1):
            results.append(play(task))
            if index % report_every == 0:
                _progress(index, total, started)
    else:
        import multiprocessing as mp
        with mp.Pool(workers) as pool:
            for index, outcome in enumerate(
                    pool.imap(play, schedule, chunksize=16), 1):
                results.append(outcome)
                if index % report_every == 0:
                    _progress(index, total, started)
    print("all %d battles done in %.1f minutes"
          % (total, (time.perf_counter() - started) / 60.0), flush=True)
    return results


def tally(names, results, original):
    """Replay the rating arithmetic, in schedule order, on both ladders.

    Sequential on purpose: each change depends on what both sides were rated
    at the time. The battles could be parallel because their outcomes do not
    depend on any of this -- see the module docstring.
    """
    ladders = {key: dict(original) for key, _ in LADDERS}
    peak = {key: dict(original) for key, _ in LADDERS}
    trough = {key: dict(original) for key, _ in LADDERS}
    record = {name: [0, 0, 0] for name in names}        # win, loss, draw
    kills = {name: [0, 0] for name in names}            # dealt, taken

    for name_a, name_b, winner, score_a, score_b in results:
        kills[name_a][0] += score_a
        kills[name_a][1] += score_b
        kills[name_b][0] += score_b
        kills[name_b][1] += score_a
        if winner < 0:
            record[name_a][2] += 1
            record[name_b][2] += 1
            continue
        won, lost = (name_a, name_b) if winner == 0 else (name_b, name_a)
        record[won][0] += 1
        record[lost][1] += 1
        for key, cushion in LADDERS:
            rating = ladders[key]
            before_won, before_lost = rating[won], rating[lost]
            rating[won] = max(1, before_won + rating_change(
                before_won, before_lost, True, cushion))
            rating[lost] = max(1, before_lost + rating_change(
                before_lost, before_won, False, cushion))
            for name in (won, lost):
                peak[key][name] = max(peak[key][name], rating[name])
                trough[key][name] = min(trough[key][name], rating[name])
    return ladders, record, kills, peak, trough


def as_markdown(title, body):
    """Wrap a fixed-width report as a markdown document.

    The body is aligned columns and ruled separators, and markdown
    reflows plain text -- so it goes inside a fence rather than being
    left to collapse into a paragraph. The title is outside it, so the
    file still reads as a document and not as one big code block.
    """
    return ("# %s" % title + chr(10) * 2
            + "Generated. Do not edit by hand." + chr(10) * 2
            + "```" + chr(10) + body.rstrip(chr(10))
            + chr(10) + "```" + chr(10))


def write_report(path, names, original, ladders, record, kills, peak, trough,
                 matches, elapsed):
    shipped = ladders["shipped_formula"]
    real = ladders["converged"]
    played_each = (len(names) - 1) * matches

    lines = []
    add = lines.append
    add("What each competitor's rating is actually worth")
    add("=" * 78)
    add("")
    add("Every competitor except the player played every other competitor")
    add("%d times -- %d matches each, %d battles in all -- and every result"
        % (matches, played_each,
           len(names) * (len(names) - 1) // 2 * matches))
    add("moved both sides' ratings by the game's own formula (elo_rating() in")
    add("Scripts/Game/game_procedure.py).")
    add("")
    add("Teams were rolled from each competitor's SHIPPED rating on every")
    add("match, never from the rating they were climbing to. Otherwise a")
    add("competitor who got ahead would start fielding better Pokemon and get")
    add("further ahead -- a feedback loop measuring itself. So the numbers")
    add("below are what each roster earned, at the strength it ships at.")
    add("")
    add("Generated by Test/ai_rating_simulation.py in %.1f minutes."
        % (elapsed / 60.0))
    add("")
    add("")
    add("Read the REAL column, not the GAME column")
    add("-" * 78)
    add("")
    add("GAME is the engine's formula exactly, starter protection and all.")
    add("REAL is the same formula with starter protection switched off.")
    add("")
    add("They differ because starter protection rounds every loss up by one,")
    add("and that has no equilibrium: a competitor winning exactly half their")
    add("matches still gains +1 per win/loss pair -- at rating 1 and at rating")
    add("750 alike. Over %d matches that is about +%d of inflation on"
        % (played_each, played_each // 2))
    add("everybody, which buries the signal. GAME is what a real career would")
    add("do to these numbers; REAL is what the team is worth, because without")
    add("the cushion a competitor climbs exactly until they are winning half")
    add("their matches against the field.")
    add("")
    add("")
    add("The ladder")
    add("-" * 78)
    add("%-24s %6s %6s %6s   %5s %5s %6s %8s"
        % ("COMPETITOR", "SHIP", "REAL", "DRIFT", "W", "L", "WIN%", "KO +/-"))
    add("-" * 78)
    for name in sorted(names, key=lambda n: -real[n]):
        won, lost, drew = record[name]
        played = won + lost + drew
        drift = (real[name] / original[name]) if original[name] else 0.0
        add("%-24s %6d %6d %6.2f   %5d %5d %5.1f%% %+8d"
            % (name[:24], original[name], real[name], drift, won, lost,
               100.0 * won / played if played else 0.0,
               kills[name][0] - kills[name][1]))

    add("")
    add("")
    add("Shipped too high -- the rating flatters the team")
    add("-" * 78)
    rated = [n for n in names if original[n] > 0]
    by_drift = sorted(rated, key=lambda n: real[n] / original[n])
    for name in by_drift[:15]:
        won, lost, _ = record[name]
        add("    %-24s %5d -> %5d  (x%.2f)   %d-%d, %.0f%% wins"
            % (name[:24], original[name], real[name],
               real[name] / original[name], won, lost,
               100.0 * won / max(1, won + lost)))
    add("")
    add("Shipped too low -- the team is better than the number")
    add("-" * 78)
    for name in reversed(by_drift[-15:]):
        won, lost, _ = record[name]
        add("    %-24s %5d -> %5d  (x%.2f)   %d-%d, %.0f%% wins"
            % (name[:24], original[name], real[name],
               real[name] / original[name], won, lost,
               100.0 * won / max(1, won + lost)))

    add("")
    add("")
    add("Both ladders, and how far each rating travelled")
    add("-" * 78)
    add("%-24s %6s | %6s %6s %6s | %6s %6s %6s"
        % ("COMPETITOR", "SHIP", "REAL", "low", "high", "GAME", "low", "high"))
    add("-" * 78)
    for name in sorted(names, key=lambda n: -real[n]):
        add("%-24s %6d | %6d %6d %6d | %6d %6d %6d"
            % (name[:24], original[name],
               real[name], trough["converged"][name], peak["converged"][name],
               shipped[name], trough["shipped_formula"][name],
               peak["shipped_formula"][name]))

    with open(path, "w", encoding="utf-8") as out:
        out.write(as_markdown("What each competitor's rating is worth",
                              chr(10).join(lines)))
    return len(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", type=int, default=MATCHES,
                        help="matches per pair (default %d)" % MATCHES)
    parser.add_argument("--limit", type=int, default=0,
                        help="use only the first N competitors (a smoke test)")
    parser.add_argument("--workers", type=int, default=0,
                        help="worker processes (default: cores - 2)")
    parser.add_argument("--cache", default="",
                        help="also write the raw battle results here, so the "
                             "report can be recomputed without replaying "
                             "16,000 battles")
    parser.add_argument("--out", default=os.path.join(
        ROOT, "Documentation", "ai_rating_simulation.md"))
    args = parser.parse_args()

    roster = _cached_engine()[0]
    # [1:] drops the Protagonist, who is the player and has no shipped rating
    # worth measuring -- their strength is whatever their career made it.
    names = list(roster.keys())[1:]
    if args.limit:
        names = names[:args.limit]
    original = {name: int(roster[name].strength) for name in names}

    workers = args.workers or max(1, (os.cpu_count() or 2) - 2)
    started = time.perf_counter()
    results = run(names, args.matches, workers)
    elapsed = time.perf_counter() - started

    if args.cache:
        with open(args.cache, "w", encoding="utf-8") as out:
            # `matches` and the roster in `original` are what let a reader
            # tell whether this cache still describes the current game --
            # see ai_winrate_table.py. Without them a cache recorded before
            # six competitors were added was replayed as though it were a
            # fresh run of the whole field.
            json.dump({"original": original, "results": results,
                       "matches": args.matches},
                      out)
        print("cached raw results in %s" % args.cache)
    ladders, record, kills, peak, trough = tally(names, results, original)
    written = write_report(args.out, names, original, ladders, record,
                           kills, peak, trough, args.matches, elapsed)
    print("wrote %s (%d lines)" % (args.out, written))

    real = ladders["converged"]
    moved = [n for n in names
             if original[n] and abs(real[n] / original[n] - 1.0) > NOTABLE]
    print("%d of %d competitors settled more than %d%% away from their "
          "shipped rating" % (len(moved), len(names), int(NOTABLE * 100)))


if __name__ == "__main__":
    main()
