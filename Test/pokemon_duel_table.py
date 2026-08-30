"""Which Pokemon is actually the strongest, with nothing else in the way.

`ai_simulation.py` answers a different question. It plays the competitors'
6v6 teams and tallies which Pokemon were standing on the winning side, so
what it measures is mostly *whose team a Pokemon was on*: `tiers.py` hands a
high-rated competitor Ultra High Pokemon, and a character ability like
Primordial or Blood Magic lifts a whole team at once. Rank by that and you
largely get the tier table back, plus Emperor Marvuno's Water types.

So this holds everything else still and varies only the species:

    one Pokemon a side          no team-mates, no switching, no ace slot
    IVs pinned to DUEL_IV       both sides, so it is species against
                                species rather than one roll against another
    no character ability        the trainer is an empty shell
    both orientations played    whatever advantage the protagonist side has,
                                each Pokemon gets it exactly half the time
    several repeats             a moveset and an ability are drawn from the
                                species' own pool every battle, and that pool
                                is part of what the species *is* -- so this
                                averages over the draw rather than pinning it

What it does not measure: a Pokemon's worth to a *team*. Entry hazards, a
Pokemon that exists to take a hit and leave, and anything that pays off over
six slots all read as weak here. A duel is not the whole game -- it is the
part of the game that can be measured without confounds.

    python Test/pokemon_duel_table.py                  the full round robin
    python Test/pokemon_duel_table.py --repeats 1      quicker, noisier
    python Test/pokemon_duel_table.py --limit 40       first 40 Pokemon only
"""
import argparse
import io
import itertools
import multiprocessing
import os
import random
import sys
import time
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

#: Both sides get this, so a duel is base stats, typing, movepool and ability
#: rather than one Pokemon having rolled better than the other.
DUEL_IV = 31

#: The rating the empty shell carries. Nothing reads it -- the team is pinned
#: to one named Pokemon -- but `tiers.py` wants a number.
SHELL_RATING = 200

_ENGINE = {}


def engine():
    """Import the game once per process and hand back what a duel needs."""
    if not _ENGINE:
        import Scripts.Battle.battle_cycle as cycle
        from Scripts.Data.battlefield import Battleground
        from Scripts.Data.competitors import Ace, list_of_competitors
        from Scripts.Data.pokemon import list_of_pokemon
        from Scripts.Game.game_procedure import team_generation
        from Scripts.Game.game_system import GameSystem
        GameSystem.stage = 5
        _ENGINE.update(cycle=cycle, Battleground=Battleground, Ace=Ace,
                       shell=next(c for c in list_of_competitors.values()
                                  if not c.main),
                       pokemon=list_of_pokemon, team_generation=team_generation)
    return _ENGINE


def solo(name):
    """A trainer whose whole team is one named Pokemon and nothing else.

    `team_generation` fills the rest of a team out around the pinned entry
    and puts the ace *last* (game_procedure.py:89), so the tail is the one
    that was asked for and the rest is discarded.
    """
    parts = engine()
    trainer = deepcopy(parts["shell"])
    trainer.name = trainer.nickname = name
    trainer.ability = ""                    # no character ability, either side
    trainer.strength = SHELL_RATING
    trainer.level = "Advanced"
    trainer.score = trainer.opponent_score = 0
    trainer.team = [parts["Ace"](name, iv=DUEL_IV)]
    return trainer


def duel(left, right, seed):
    """One battle. Returns 'left', 'right' or 'draw'."""
    parts = engine()
    random.seed(seed)
    one, two = solo(left), solo(right)
    one.team = parts["team_generation"](one)[-1:]
    two.team = parts["team_generation"](two)[-1:]
    ground = parts["Battleground"]()
    ground.verbose = True               # AI vs AI: both sides plan properly
    with redirect_stdout(io.StringIO()):
        parts["cycle"].battle_setup(one, two, one.team, two.team, ground)
    if one.score > two.score:
        return "left"
    if two.score > one.score:
        return "right"
    return "draw"


def play(job):
    """One pair, every repeat, both orientations. Runs in a worker."""
    index, left, right, repeats = job
    tally = Counter()
    for repeat in range(repeats):
        # Both orientations of the same pairing, so whatever edge the
        # protagonist side carries is shared out evenly rather than being
        # handed to whichever name sorted first.
        for flip in (False, True):
            seed = index * 1000 + repeat * 2 + flip
            try:
                if flip:
                    got = duel(right, left, seed)
                    got = {"left": "right", "right": "left"}.get(got, got)
                else:
                    got = duel(left, right, seed)
            except Exception:
                tally["error"] += 1
                continue
            if got == "left":
                tally[left + "|w"] += 1
                tally[right + "|l"] += 1
            elif got == "right":
                tally[right + "|w"] += 1
                tally[left + "|l"] += 1
            else:
                tally[left + "|d"] += 1
                tally[right + "|d"] += 1
    return tally


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3,
                        help="battles per orientation per pair (default 3, "
                             "so six battles a pairing)")
    parser.add_argument("--limit", type=int, default=0,
                        help="only the first N Pokemon, for a quick run")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--out", default=os.path.join(
        ROOT, "Documentation", "pokemon_duel_table.md"))
    args = parser.parse_args()

    parts = engine()
    names = sorted(parts["pokemon"])
    if args.limit:
        names = names[:args.limit]
    pairs = [(i, a, b, args.repeats)
             for i, (a, b) in enumerate(itertools.combinations(names, 2))]
    total = len(pairs) * args.repeats * 2
    workers = args.workers or max(1, (os.cpu_count() or 4) - 2)
    print("%d Pokemon, %d pairings, %d battles, %d workers"
          % (len(names), len(pairs), total, workers))

    record = defaultdict(Counter)
    errors = done = 0
    started = time.time()
    with multiprocessing.Pool(workers) as pool:
        for chunk, tally in enumerate(pool.imap_unordered(play, pairs, 24), 1):
            for key, count in tally.items():
                if key == "error":
                    errors += count
                    continue
                who, what = key.rsplit("|", 1)
                record[who][what] += count
            done += args.repeats * 2
            if chunk % 2000 == 0:
                rate = done / max(0.001, time.time() - started)
                print("   %6d/%d  %5.1f%%  %4.0f battles/s  ~%.1f min left"
                      % (done, total, 100.0 * done / total, rate,
                         (total - done) / rate / 60))
    print("all %d battles done in %.1f minutes"
          % (total, (time.time() - started) / 60))
    if errors:
        print("%d battles failed and were dropped" % errors)

    report(names, record, args, errors)


def rate(row):
    played = row["w"] + row["l"] + row["d"]
    return 100.0 * row["w"] / played if played else 0.0


def report(names, record, args, errors):
    parts = engine()
    lines = []

    def add(text=""):
        lines.append(text)

    order = sorted(names, key=lambda n: (-rate(record[n]), n))
    place = {name: index + 1 for index, name in enumerate(order)}

    #: where the shipped tier ladder puts each Pokemon, weakest first
    ladder = ["Very Low", "Low", "Medium", "High", "Very High", "Ultra High",
              "Boss", "Secret"]

    add("# Which Pokemon wins a straight fight")
    add("")
    add("Every Pokemon against every other, one against one, %d times in each"
        % args.repeats)
    add("orientation. IVs are pinned to %d on both sides and neither trainer"
        % DUEL_IV)
    add("has a character ability, so the only thing that differs between two")
    add("sides is the species: its base stats, its typing, its movepool and")
    add("the ability it rolled.")
    add("")
    add("This is deliberately *not* the same question as")
    add("`Documentation/ai_win_rate_table.md`, which ranks competitors. A")
    add("Pokemon's win rate inside those 6v6 battles mostly reflects whose")
    add("team it was on -- a high-rated competitor draws from a higher tier --")
    add("so this strips the team away entirely.")
    add("")
    add("**What it cannot see:** anything whose value is to a *team*. Entry")
    add("hazards pay off over six slots, a pivot exists to leave, and a wall")
    add("that buys a turn for somebody else has nobody to buy it for. Those")
    add("Pokemon read as weak here and are not.")
    add("")
    if errors:
        add("%d battles failed and were dropped." % errors)
        add("")
    add("```")
    add("%-5s %-26s %7s %6s %5s %5s %5s  %s"
        % ("RANK", "POKEMON", "WIN%", "W", "L", "D", "BST", "TIER"))
    add("-" * 80)
    for name in order:
        row = record[name]
        mon = parts["pokemon"][name]
        bst = sum(mon.base_stats) if getattr(mon, "base_stats", None) else 0
        add("%-5d %-26s %6.1f%% %6d %5d %5d %5d  %s"
            % (place[name], name[:26], rate(row), row["w"], row["l"],
               row["d"], bst, getattr(mon, "tier", "?")))
    add("```")

    # -- is the tier ladder telling the truth? -----------------------------
    add("")
    add("")
    add("## Does the tier ladder match what happens")
    add("")
    add("If the tiers are calibrated, average win rate should climb steadily")
    add("with the tier. Where it does not, the tier is the thing to fix.")
    add("")
    add("```")
    add("%-12s %6s %9s %9s %9s" % ("TIER", "N", "MEAN WIN%", "BEST", "WORST"))
    add("-" * 50)
    for tier in ladder:
        members = [n for n in names
                   if getattr(parts["pokemon"][n], "tier", "?") == tier]
        if not members:
            continue
        rates = [rate(record[n]) for n in members]
        add("%-12s %6d %8.1f%% %8.1f%% %8.1f%%"
            % (tier, len(members), sum(rates) / len(rates),
               max(rates), min(rates)))
    add("```")

    # -- the mis-tiered ones, which is the actionable part -----------------
    add("")
    add("")
    add("## Pokemon in the wrong tier")
    add("")
    add("Each Pokemon's rank compared with the middle of its own tier. A")
    add("large positive number means it beats the company it is keeping and")
    add("belongs a tier up; a large negative one means the reverse. This is")
    add("the same idea as the MOVE column in the competitor table.")
    add("")
    middle = {}
    for tier in ladder:
        members = [n for n in names
                   if getattr(parts["pokemon"][n], "tier", "?") == tier]
        if members:
            ranks = sorted(place[n] for n in members)
            middle[tier] = ranks[len(ranks) // 2]
    drift = []
    for name in names:
        tier = getattr(parts["pokemon"][name], "tier", "?")
        if tier in middle:
            drift.append((middle[tier] - place[name], name, tier,
                          place[name], rate(record[name])))
    drift.sort(key=lambda row: -row[0])
    add("```")
    add("%-24s %-11s %6s %8s  %s"
        % ("POKEMON", "TIER", "RANK", "WIN%", "PLACES FROM ITS TIER'S MIDDLE"))
    add("-" * 78)
    for gap, name, tier, rank, win in drift[:15]:
        add("%-24s %-11s %6d %7.1f%%  %+d" % (name[:24], tier, rank, win, gap))
    add("%-24s %-11s %6s %8s  %s" % ("...", "", "", "", ""))
    for gap, name, tier, rank, win in drift[-15:]:
        add("%-24s %-11s %6d %7.1f%%  %+d" % (name[:24], tier, rank, win, gap))
    add("```")

    text = "\n".join(lines) + "\n"
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print("wrote %s (%d lines)" % (args.out, len(lines)))
    print("strongest:", ", ".join(order[:5]))
    print("weakest:  ", ", ".join(order[-5:]))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
