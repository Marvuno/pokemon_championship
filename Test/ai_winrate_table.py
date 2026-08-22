"""Who actually wins, with no rating arithmetic anywhere.

The same round robin as `ai_rating_simulation.py` -- every competitor except
the player against every other, ten times each -- reported as win rate and
knockout score only. No Elo, no drift, nothing that compounds.

Worth having as its own table because the two orderings genuinely disagree,
and neither is wrong. A rating is a weighted record: beating a strong
competitor moves it more than beating a weak one, so a competitor who feeds on
the bottom of the field is rated below one with the same win rate who beat the
top. Win rate treats every match the same. When the two disagree, the gap is
telling you *who* somebody's wins came from.

Note that the ratings were never able to feed back into play: teams are always
rolled from each competitor's shipped rating, so the win/loss records in the
Elo report are already "without rating change". This reads the same battles
and just declines to weight them.

    python Test/ai_winrate_table.py                        replay and report
    python Test/ai_winrate_table.py --cache <file>         reuse battles
    python Test/ai_winrate_table.py --matches 3 --limit 12 quicker

Writes Documentation/ai_win_rate_table.md.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")


def tally(names, results):
    """Records and margins.

    The engine's `score` is already a *net* differential -- how many of the
    opponent's Pokemon fainted minus how many of yours -- so the two sides of
    a battle always mirror each other exactly (checked: 16,530 of 16,530).
    There is no gross "knocked out" count to recover from it, so this reports
    the margin and nothing it cannot actually know.
    """
    record = {name: [0, 0, 0] for name in names}       # win, loss, draw
    margin = {name: [0, 0] for name in names}          # net total, worst
    head = {name: {} for name in names}                # wins against each foe

    for name_a, name_b, winner, score_a, score_b in results:
        if name_a not in record or name_b not in record:
            continue
        margin[name_a][0] += score_a
        margin[name_b][0] += score_b
        margin[name_a][1] = min(margin[name_a][1], score_a)
        margin[name_b][1] = min(margin[name_b][1], score_b)
        if winner < 0:
            record[name_a][2] += 1
            record[name_b][2] += 1
            continue
        won, lost = (name_a, name_b) if winner == 0 else (name_b, name_a)
        record[won][0] += 1
        record[lost][1] += 1
        head[won][lost] = head[won].get(lost, 0) + 1
        head[lost].setdefault(won, 0)
    return record, margin, head


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


def write_report(path, names, original, record, margin, head, matches,
                 rating_order=None):
    def rate(name):
        won, lost, drew = record[name]
        played = won + lost + drew
        return (100.0 * won / played) if played else 0.0

    order = sorted(names, key=lambda n: (-rate(n), -margin[n][0]))
    place = {name: index + 1 for index, name in enumerate(order)}

    lines = []
    add = lines.append
    add("Win rate and knockout score -- no rating arithmetic")
    add("=" * 78)
    add("")
    add("Every competitor except the player played every other %d times."
        % matches)
    add("Ranked by win rate, ties broken by margin. Nothing here is")
    add("weighted by who the opponent was, and no rating was changed.")
    add("")
    add("MARGIN is the net Pokemon knocked out across every match -- theirs")
    add("minus yours. PER is that per match, so +3.0 means winning by three")
    add("Pokemon on average. WORST is the heaviest single defeat. SHIP is the")
    add("rating the competitor ships with, for comparison only -- it took no")
    add("part in this table.")
    add("")
    add("%-4s %-22s %6s %5s %5s %5s %8s %6s %6s %7s"
        % ("#", "COMPETITOR", "WIN%", "W", "L", "D", "MARGIN", "PER",
           "WORST", "SHIP"))
    add("-" * 84)
    for name in order:
        won, lost, drew = record[name]
        played = won + lost + drew
        add("%-4d %-22s %5.1f%% %5d %5d %5d %+8d %+6.2f %6d %7d"
            % (place[name], name[:22], rate(name), won, lost, drew,
               margin[name][0], margin[name][0] / played if played else 0,
               margin[name][1], original.get(name, 0)))

    add("")
    add("")
    add("Where win rate and the Elo ladder disagree")
    add("-" * 78)
    if not rating_order:
        add("    (no rating ladder to compare against)")
    else:
        elo_place = {name: i + 1 for i, name in enumerate(rating_order)}
        gaps = sorted((n for n in names if n in elo_place),
                      key=lambda n: -abs(elo_place[n] - place[n]))
        add("A competitor above their Elo place won often but against weaker")
        add("opposition; below it, their wins came from harder matches.")
        add("")
        add("    %-22s %8s %8s %6s" % ("COMPETITOR", "BY WIN%", "BY RATING",
                                       "MOVE"))
        for name in gaps[:15]:
            shift = elo_place[name] - place[name]
            add("    %-22s %8d %8d %+6d"
                % (name[:22], place[name], elo_place[name], shift))

    add("")
    add("")
    add("Hardest and easiest match-ups on record")
    add("-" * 78)
    pairs = []
    for name in names:
        for foe, wins in head[name].items():
            played = wins + head.get(foe, {}).get(name, 0)
            if played >= matches:                 # both directions counted
                pairs.append((wins / played, played, name, foe))
    pairs.sort(reverse=True)
    add("    most one-sided (winner took every meeting):")
    shown = 0
    for share, played, name, foe in pairs:
        if share < 1.0 or shown >= 10:
            break
        add("        %-22s beat %-22s %d-0" % (name[:22], foe[:22], played))
        shown += 1
    if not shown:
        add("        none -- every pairing was split at least once")

    with open(path, "w", encoding="utf-8") as out:
        out.write(as_markdown("Win rate table",
                              chr(10).join(lines)))
    return len(lines), order


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default=os.path.join(
        ROOT, "Test", "gui", "_out", "rating_sim_results.json"),
        help="battles recorded by ai_rating_simulation.py --cache; replayed "
             "rather than fought again, since the outcomes do not depend on "
             "any rating arithmetic")
    parser.add_argument("--matches", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--out", default=os.path.join(
        ROOT, "Documentation", "ai_win_rate_table.md"))
    args = parser.parse_args()

    if args.cache and os.path.exists(args.cache):
        with open(args.cache, encoding="utf-8") as source:
            cached = json.load(source)
        original = cached["original"]
        results = cached["results"]
        names = list(original)
        print("replaying %d battles from %s" % (len(results), args.cache))
    else:
        # no cache: fight them, using the other harness's machinery
        from Test.ai_rating_simulation import run, _cached_engine
        roster = _cached_engine()[0]
        names = list(roster.keys())[1:]
        if args.limit:
            names = names[:args.limit]
        original = {name: int(roster[name].strength) for name in names}
        workers = args.workers or max(1, (os.cpu_count() or 2) - 2)
        results = run(names, args.matches, workers)

    if args.limit:
        names = names[:args.limit]
    record, margin, head = tally(names, results)

    # the Elo ordering, if that report is around, purely to contrast with
    rating_order = None
    elo = os.path.join(ROOT, "Documentation", "ai_rating_simulation.md")
    if os.path.exists(elo):
        import re
        rows, started = [], False
        for line in open(elo, encoding="utf-8"):
            if line.startswith("COMPETITOR"):
                started = True
                continue
            if not started or line.startswith("-") or not line.strip():
                continue
            match = re.match(r"^(.{1,24}?)\s{2,}\d+\s+(\d+)\s+[\d.]+", line)
            if not match:
                if rows:
                    break
                continue
            rows.append((match.group(1).strip(), int(match.group(2))))
        rating_order = [name for name, _ in rows]

    written, order = write_report(args.out, names, original, record,
                                 margin, head, args.matches, rating_order)
    print("wrote %s (%d lines)" % (args.out, written))
    print("top by win rate: %s" % ", ".join(order[:5]))


if __name__ == "__main__":
    main()
