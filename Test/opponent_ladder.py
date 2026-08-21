"""
Which competitors are actually stronger than which?

A round robin: every competitor plays every other one N times (5 by default)
with the AI driving both sides, and the results become a ladder. Nothing here
touches the game -- no save is read or written, the player never appears, and
it runs from the project root as:

    python Test/opponent_ladder.py                  every pairing, 5 each
    python Test/opponent_ladder.py --repeat 10      more matches per pairing
    python Test/opponent_ladder.py --stage 3        4v4 instead of 6v6
    python Test/opponent_ladder.py --pair "Goblin" "Monkey King"
    python Test/opponent_ladder.py --only Elite Champion   by tier
    python Test/opponent_ladder.py --seed 7         reproducible

The point of the "vs rating" column is the interesting one: it is where a
competitor finished on win rate minus where their Data/competitors.csv rating
says they should have finished. A big positive number is someone underrated,
a big negative number someone the file flatters.

Teams are rolled the way the game rolls them (team_generation from their own
rating, plus whichever Pokemon the CSV pins to them), so this measures the
competitor -- rating, roster and all -- and not a random six.

It runs at roughly five battles a second, so the full 55-competitor round
robin at five each is about 7,400 battles and half an hour. Progress goes to
stderr as it works. --only or --pair is the way to ask a narrower question
quickly; the table is written to Documentation/opponent_ladder.txt either way.

Test/ai_simulation.py is the older, Pokemon-focused sibling: same battle
engine, but it asks which *Pokemon* win rather than which competitors.
"""

import argparse
import itertools
import math
import json
import os
import random
import sys
import time
from contextlib import redirect_stdout, suppress
from copy import deepcopy

if __name__ == "__main__":                       # run from the project root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))))

from Scripts.Data.competitors import *
from Scripts.Data.battlefield import *
from Scripts.Battle.battle_cycle import *
from Scripts.Battle.battle_win_condition import wins_a_draw
from Scripts.Game.game_procedure import team_generation
from Scripts.Game.game_system import *

REPORT = os.path.join("Documentation", "opponent_ladder.txt")

#: battles the engine could not finish -- reported, not fatal
FAULTS = []


class Record:
    """One competitor's running tally."""

    __slots__ = ("name", "nickname", "rating", "drifted", "tier", "wins",
                 "losses", "draws", "kills", "conceded", "beat", "lost_to")

    def __init__(self, competitor):
        self.name = competitor.name
        self.nickname = competitor.nickname
        #: what Data/competitors.csv says, and what team_generation keeps using
        #: all run -- so every match is fought by the roster the CSV pins to
        #: this competitor, not by a team that grows as they win
        self.rating = competitor.strength
        #: the same number, but moved by every result. This is the answer to
        #: "what is this competitor's team actually worth", which is the point
        #: of running the ladder: where it settles against `rating` says
        #: whether the CSV flatters them or sells them short.
        self.drifted = float(competitor.strength)
        self.tier = competitor.level
        self.wins = self.losses = self.draws = 0
        self.kills = self.conceded = 0
        self.beat = {}                 # opponent name -> times beaten
        self.lost_to = {}

    @property
    def played(self):
        return self.wins + self.losses

    @property
    def win_rate(self):
        return 100.0 * self.wins / self.played if self.played else 0.0

    @property
    def diff(self):
        return self.kills - self.conceded


def apply_drift(winner, loser):
    """Move both drifted ratings by one result, the way the game does.

    Deliberately the same shape as elo_rating() in Scripts/Game/game_procedure:
    the square root of the combined rating, scaled by the loser's share of it,
    so beating somebody far above you moves the number more than beating
    somebody far below. A formula of my own here would have produced something
    that looked like a rating but could not be compared with one.

    Reads `drifted` rather than `rating`, so a competitor who has been winning
    all afternoon is a genuinely harder scalp by the end of the run.
    """
    combined = winner.drifted + loser.drifted
    if combined <= 0:
        return
    change = math.sqrt(combined) * (loser.drifted / combined)
    winner.drifted += change
    # starter protection, as the engine has it: a loss never drops you below 1
    loser.drifted = max(1.0, loser.drifted - change)


def play(one, two, stage):
    """One AI-vs-AI battle. Returns (winner, loser, one_kills, two_kills).

    Both sides are deep-copied first: battle_setup mutates the team in place
    (HP, statuses, transformed names) and the roster objects are shared with
    the module-level competitor list.
    """
    side1, side2 = deepcopy(one), deepcopy(two)
    side1.team = team_generation(side1)
    side2.team = team_generation(side2)
    battleground = Battleground()
    battleground.verbose = True          # no narration, no prompts, no music

    # A deep recursion in a long stall is a known engine limit that
    # ai_simulation.py already suppresses; it should not stop a run of
    # several thousand battles. (Narration is swallowed by run(), which
    # redirects stdout once for the whole ladder -- doing it per battle cost
    # a file open each time.)
    #
    # Anything else raising is a real engine bug, and thousands of AI-vs-AI
    # battles is exactly how you find one -- so it is counted and named at the
    # end of the run rather than taking the other 7,000 results down with it.
    # (This is how the phantom-move-slot IndexError in ai.py was found.)
    try:
        with suppress(RecursionError):
            battle_setup(side1, side2, side1.team, side2.team, battleground)
    except Exception as error:
        FAULTS.append("%s vs %s: %s: %s" % (one.name, two.name,
                                            type(error).__name__, error))
        return None, None, 0, 0

    ones, twos = side1.result, side2.result
    if ones == twos:
        # Same tie-break the tournament uses, so the ladder cannot disagree
        # with what a real round would have recorded.
        winner = one if wins_a_draw(side1, side2) is side1 else two
    else:
        winner = one if ones > twos else two
    loser = two if winner is one else one
    return winner, loser, ones, twos


def run(competitors, repeat, stage, pairs=None):
    GameSystem.stage = stage
    records = {c.name: Record(c) for c in competitors}
    pairs = pairs if pairs is not None else list(
        itertools.combinations(competitors, 2))
    total = len(pairs) * repeat
    done, started = 0, time.time()

    # The engine narrates through print() even in verbose mode, and on a
    # Windows console that is also an encoding hazard: the colour codes and
    # the crowned nicknames are not cp1252. One sink for the whole run,
    # errors replaced rather than raised. Progress goes to stderr, which is
    # deliberately left alone.
    with open(os.devnull, "w", encoding="utf-8", errors="replace") as sink:
        with redirect_stdout(sink):
            for one, two in pairs:
                for _ in range(repeat):
                    winner, loser, ones, twos = play(one, two, stage)
                    done += 1
                    if done % 25 == 0 or done == total:
                        rate = done / max(0.001, time.time() - started)
                        sys.stderr.write(
                            "\r  %d/%d battles  (%.1f/s, %.0fs left)   "
                            % (done, total, rate,
                               (total - done) / max(0.001, rate)))
                        sys.stderr.flush()
                    if winner is None:
                        continue                 # the engine gave up; see FAULTS
                    win, lose = records[winner.name], records[loser.name]
                    win.wins += 1
                    lose.losses += 1
                    win.beat[loser.name] = win.beat.get(loser.name, 0) + 1
                    lose.lost_to[winner.name] = \
                        lose.lost_to.get(winner.name, 0) + 1
                    apply_drift(win, lose)
                    if ones == twos:
                        win.draws += 1
                        lose.draws += 1
                    for record, mine, theirs in (
                            (records[one.name], ones, twos),
                            (records[two.name], twos, ones)):
                        record.kills += mine
                        record.conceded += theirs
    sys.stderr.write("\n")
    return records, total, time.time() - started


def ladder(records):
    """Sorted strongest first, with each one's rank by rating alongside."""
    rows = sorted(records.values(),
                  key=lambda r: (-r.win_rate, -r.diff, r.rating))
    by_rating = {r.name: index for index, r in enumerate(
        sorted(records.values(), key=lambda r: -r.rating), start=1)}
    return [(index, row, by_rating[row.name] - index)
            for index, row in enumerate(rows, start=1)]


def report(records, repeat, stage, total, seconds):
    limit = ROUND_LIMIT[stage]
    lines = [
        "Opponent ladder",
        "%d competitors, %d matches per pairing, %dv%d, %d battles in %.0fs"
        % (len(records), repeat, limit, limit, total, seconds),
        "",
        "'vs rating' is rank here minus rank by Data/competitors.csv rating:",
        "positive means they outperformed their rating, negative means the",
        "rating flatters them.",
        "",
        "'settled' is the rating after every result has moved it, starting",
        "from the CSV rating. 'move' is settled minus rating -- the number to",
        "put back into Data/competitors.csv if you want the rating to match",
        "what the team can actually do. Teams are still generated from the",
        "original rating, so this measures the roster, not a snowball.",
        "",
        "%-4s %-24s %6s %8s %7s %5s %5s %7s %7s %7s %9s"
        % ("#", "COMPETITOR", "RATING", "SETTLED", "MOVE", "W", "L", "WIN%",
           "KILLS", "DIFF", "VS RATING"),
    ]
    for index, row, delta in ladder(records):
        settled = int(round(row.drifted))
        lines.append("%-4d %-24s %6d %8d %+7d %5d %5d %6.1f%% %7d %+7d %+9d"
                     % (index, row.nickname[:24], row.rating, settled,
                        settled - row.rating, row.wins, row.losses,
                        row.win_rate, row.kills, row.diff, delta))

    if FAULTS:
        lines += ["", "%d battle%s the engine could not finish (excluded):"
                  % (len(FAULTS), "" if len(FAULTS) == 1 else "s")]
        lines += ["  " + fault for fault in FAULTS[:10]]
        if len(FAULTS) > 10:
            lines.append("  ... and %d more" % (len(FAULTS) - 10))

    over = [(d, r) for _, r, d in ladder(records) if d >= 5]
    under = [(d, r) for _, r, d in ladder(records) if d <= -5]
    if over or under:
        lines += ["", "Worth a look:"]
        # keyed, not plain reverse=True: ties on delta would then compare the
        # Records themselves, which have no ordering
        for delta, row in sorted(over, key=lambda pair: -pair[0])[:8]:
            lines.append("  underrated  %-24s rated %4d, finished %.1f%% "
                         "(%+d places)"
                         % (row.nickname[:24], row.rating, row.win_rate,
                            delta))
        for delta, row in sorted(under, key=lambda pair: pair[0])[:8]:
            lines.append("  overrated   %-24s rated %4d, finished %.1f%% "
                         "(%+d places)"
                         % (row.nickname[:24], row.rating, row.win_rate,
                            delta))
    return "\n".join(lines)


def head_to_head(records, one, two):
    a, b = records[one], records[two]
    return ("\n\n%s vs %s\n  %s %d - %d %s\n  kills %d - %d"
            % (a.nickname, b.nickname, a.nickname, a.beat.get(two, 0),
               b.beat.get(one, 0), b.nickname, a.kills, b.kills))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Round-robin the competitors against each other.")
    parser.add_argument("--repeat", type=int, default=5,
                        help="matches per pairing (default 5)")
    parser.add_argument("--stage", type=int, default=5,
                        help="round number, which sets the team size "
                             "(default 5, a 6v6)")
    parser.add_argument("--pair", nargs=2, metavar=("ONE", "TWO"),
                        help="just these two, by name or nickname")
    parser.add_argument("--only", nargs="+", metavar="TIER",
                        help="restrict to these tiers, e.g. Elite Champion")
    parser.add_argument("--seed", type=int, help="fix the random seed")
    parser.add_argument("--no-write", action="store_true",
                        help="print the table without writing %s" % REPORT)
    args = parser.parse_args(argv)

    if args.seed is not None:
        random.seed(args.seed)
    if args.stage not in ROUND_LIMIT:
        parser.error("--stage must be one of %s" % sorted(ROUND_LIMIT))

    def find(text):
        for competitor in list_of_competitors.values():
            if text.lower() in (competitor.name.lower(),
                                competitor.nickname.lower()):
                return competitor
        parser.error("no competitor called %r" % text)

    field = [c for c in list_of_competitors.values() if not c.main]
    if args.only:
        wanted = {t.lower() for t in args.only}
        field = [c for c in field if c.level.lower() in wanted]
        if not field:
            parser.error("no competitor is in %s -- tiers are %s"
                         % (args.only,
                            sorted({c.level for c in list_of_competitors
                                    .values()})))
    pairs = None
    if args.pair:
        one, two = find(args.pair[0]), find(args.pair[1])
        field, pairs = [one, two], [(one, two)]

    print("%d competitors, %d matches each pairing, %dv%d"
          % (len(field), args.repeat, ROUND_LIMIT[args.stage],
             ROUND_LIMIT[args.stage]))
    records, total, seconds = run(field, args.repeat, args.stage, pairs)
    # The tallies go to disk before anything is formatted. A half-hour run is
    # too expensive to lose to a bug in the table layout -- which is exactly
    # what happened once.
    if not args.no_write:
        with open(os.path.splitext(REPORT)[0] + ".json", "w",
                  encoding="utf-8") as handle:
            json.dump({name: {"nickname": r.nickname, "rating": r.rating,
                              # what the rating became, and by how much: the
                              # two numbers to compare when deciding what to
                              # write back into Data/competitors.csv
                              "settled": int(round(r.drifted)),
                              "move": int(round(r.drifted)) - r.rating,
                              "tier": r.tier, "wins": r.wins,
                              "losses": r.losses, "draws": r.draws,
                              "kills": r.kills, "conceded": r.conceded,
                              "beat": r.beat}
                       for name, r in records.items()},
                      handle, indent=1, sort_keys=True, ensure_ascii=False)
    text = report(records, args.repeat, args.stage, total, seconds)
    if args.pair:
        text += head_to_head(records, field[0].name, field[1].name)
    print("\n" + text)
    if not args.no_write:
        with open(REPORT, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print("\nwritten to %s" % REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
