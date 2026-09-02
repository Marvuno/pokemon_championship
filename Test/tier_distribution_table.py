"""What Pokemon does each competitor actually draw at their rating?

Not a simulation. `tiers.tier_weights` is a triangular kernel with the small
tiers held to a share, so the draw has a closed form -- these are the exact
probabilities, normalised, and not a Monte Carlo estimate of them. A sampled
version of this table would only add noise to a number the code already
knows.

Two things decide a competitor's team and both read the same rating:

  the tier draw   which shelf each rolled Pokemon comes off, below
  the IV floor    PLAYER_IV(strength), the lowest IV any of their Pokemon
                  can roll, reported here because "what do they field" is
                  not answered by the tier alone

How many Pokemon are *rolled* depends on the round -- ROUND_LIMIT is 4 at
stage 1 and 6 from stage 3 on -- and on how many the competitor pins. A
competitor with one designed ace rolls five of six at the final stage; the
five bosses pin all six and roll none at all, which is why their row is
marked and their tier percentages are what they *would* draw rather than
what they do.

    python Test/tier_distribution_table.py               the whole roster
    python Test/tier_distribution_table.py --stage 1     the opening round

Writes Documentation/tier_distribution_table.md.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, default=5,
                        help="which round's team size to report (1-6)")
    parser.add_argument("--out", default=os.path.join(
        ROOT, "Documentation", "tier_distribution_table.md"))
    args = parser.parse_args()

    from Scripts.Battle.constants import ROUND_LIMIT, PLAYER_IV
    from Scripts.Data import tiers
    from Scripts.Data.competitors import list_of_competitors
    from Scripts.Data.pokemon import list_of_pokemon
    from Test.ai_winrate_table import as_markdown

    # How many Pokemon exist on each shelf. SHARE_CEILING is a pool-size
    # constraint rather than a balance one, so the pool is part of reading
    # the table: Ultra High is capped because there are only six of them.
    pool = {tier: sum(1 for name in list_of_pokemon
                      if list_of_pokemon[name].tier == tier)
            for tier in tiers.TIERS}

    seats = ROUND_LIMIT[args.stage]
    nl = chr(10)
    body = []
    body.append("Pokemon tier distribution, by competitor")
    body.append("=" * 100)
    body.append("")
    body.append("Exact draw probabilities from Scripts/Data/tiers.py, not")
    body.append("sampled. Every competitor reads the same ladder at their own")
    body.append("rating: a triangular kernel of width %.1f tiers around their"
                % tiers.SPREAD)
    body.append("centre, with the small shelves held to a share of the draw.")
    body.append("")
    body.append("ROLLED is how many of their %d Pokemon are drawn from these"
                % seats)
    body.append("shares at stage %d; the rest are the aces they are designed"
                % args.stage)
    body.append("around. A competitor rolling 0 pins a full team, so their")
    body.append("percentages are what they *would* draw, not what they field.")
    body.append("")
    body.append("IV is PLAYER_IV(rating) -- the lowest IV any rolled Pokemon")
    body.append("of theirs can have. It climbs with rating alongside the tiers.")
    body.append("")
    body.append("Nobody above rating %d draws differently from anybody else"
                % tiers.RATING_CEILING)
    body.append("above it: Ultra High is the last shelf and there is nothing")
    body.append("past it to hand out.")
    body.append("")
    body.append("Pokemon available on each shelf:")
    body.append("    " + ",  ".join("%s %d" % (tier, pool[tier])
                                    for tier in tiers.TIERS))
    body.append("")
    body.append("")

    header = "%-4s %-19s %6s %-13s %5s %4s " % (
        "RANK", "COMPETITOR", "RATING", "LEVEL", "ROLL", "IV")
    header += " ".join("%>9s".replace(">", "") % tier[:9]
                       for tier in tiers.TIERS)
    body.append(header)
    body.append("-" * len(header))

    roster = [c for c in list_of_competitors.values() if not c.main]
    roster.sort(key=lambda c: int(c.raw_id))
    for competitor in roster:
        weights = tiers.tier_weights(competitor.strength)
        total = sum(weights) or 1.0
        rolled = max(0, seats - len(competitor.team))
        line = "%-4s %-19s %6d %-13s %5d %4d " % (
            competitor.raw_id, competitor.nickname, competitor.strength,
            competitor.level, rolled, PLAYER_IV(competitor.strength))
        line += " ".join("%8.1f%%" % (100.0 * weight / total)
                         for weight in weights)
        body.append(line)

    # The distinct draws, because most of the roster shares one. Reading it
    # as "which shelves does a rating of about this get" is the question the
    # table is usually asked, and 72 rows bury it.
    body.append("")
    body.append("")
    body.append("The ladder itself, without the names")
    body.append("-" * 100)
    body.append("What any rating draws, whether or not a competitor sits on it.")
    body.append("")
    ladder = "%8s  " % "RATING"
    ladder += " ".join("%9s" % tier[:9] for tier in tiers.TIERS)
    body.append(ladder)
    body.append("-" * len(ladder))
    marks = [0, 5, 10, 20, 40, 60, 100, 150, 200, 250, 300, 400, 500, 750,
             1000]
    for rating in marks:
        weights = tiers.tier_weights(rating)
        total = sum(weights) or 1.0
        note = "  <- ceiling" if rating == tiers.RATING_CEILING else ""
        body.append("%8d  " % rating
                    + " ".join("%8.1f%%" % (100.0 * w / total)
                               for w in weights) + note)

    document = as_markdown("Pokemon tier distribution table", nl.join(body))
    with open(args.out, "w", encoding="utf-8") as out:
        out.write(document)
    print("wrote %s (%d lines)" % (args.out, document.count(nl) + 1))
    print("%d competitors at stage %d (%d Pokemon each)"
          % (len(roster), args.stage, seats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
