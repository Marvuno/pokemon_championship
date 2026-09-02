"""What is a character ability actually worth?

The same round robin as `ai_winrate_table.py`, with two things changed: every
competitor's team is drawn as though they were rated FLAT, and their designed
ace is thrown away. Nobody's Pokemon are better than anybody else's and
nobody has a signature Pokemon, so every competitor draws from an identical
distribution and the only thing left that differs between any two of them is
the character ability.

That is the point, and it is also the limit: this measures a character nobody
actually plays. Read it as "what is this ability worth" and never as "who is
the better competitor" -- it has deliberately discarded the ace, which is
half of what makes them one. `--keep-aces` puts the aces back and answers the
other question, "ace plus ability, with rating removed".

One ability cannot survive this mode. `champion` fires only when the Pokemon
on the field is Gardevoir, Metagross, Charizard or Dragonite -- exactly the
aces of the four competitors who hold it -- so with the aces gone it does
nothing except by lucky draw. Those rows are marked rather than left to read
as a weak ability. Any future ability keyed to a species belongs in
ACE_DEPENDENT below.

Two things this report can do that a one-ability-at-a-time probe cannot:

  * it scores every ability against a field that *also* has abilities. A
    probe that pits one ability against an opponent with none over-states
    anything reactive -- an ability punishing switches looks wonderful
    against an opponent with no reason not to switch.
  * it is one consistent set of battles, so the numbers can be compared to
    each other rather than only to their own control.

    python Test/ability_score_table.py                 ability only
    python Test/ability_score_table.py --keep-aces     ace plus ability
    python Test/ability_score_table.py --rating 200    a different calibre
    python Test/ability_score_table.py --matches 3     quicker, noisier

Writes Documentation/ability_score_table.md.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

#: Abilities that name a species rather than reading the Pokemon in front of
#: them, and so cannot be measured with the aces stripped. `champion` is the
#: only one today; anything added that hard-codes a Pokemon name belongs here
#: or its holders will silently read as holding a dud.
ACE_DEPENDENT = ("Champion",)

#: The band of ace calibre the control group is drawn from. Wide enough to
#: hold a useful number of competitors, narrow enough that the ace is not
#: what separates them. Fourteen competitors sit in it as of v1.2.6.
CONTROL_BAND = (530, 540)

#: Differences below this mean nothing. Measured, not guessed, from the
#: competitors who share an ability -- see the last section of the report,
#: which prints the spread every run so this constant can be checked against
#: it rather than trusted.
#:
#: With the aces stripped those holders differ in *nothing*, so their spread
#: is pure variance: the four Champion holders came in 3.0 points apart and
#: the two Tenebrous holders 3.2, over 710 battles each. With the aces kept
#: the same comparison reads 13.4 and 11.3, because it is then measuring the
#: aces as well -- which is why the two modes carry different floors and why
#: reading the ace-kept number as variance overstates it four times over.
NOISE_FLOOR = {True: 3.5, False: 12.0}


def ace_calibre(competitor, pokemon):
    """The base-stat total of this competitor's best designed Pokemon.

    Sum of `base_stats` rather than a stored total: the custom Pokemon are
    added by hand and not all of them carry one, and a missing total read as
    zero would have put a 600 ace in the weak-ace column.
    """
    totals = [sum(pokemon[ace.name].base_stats)
              for ace in competitor.team if ace.name in pokemon]
    return (len(totals), max(totals) if totals else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", type=int, default=10)
    parser.add_argument("--rating", type=int, default=150,
                        help="the calibre every team is drawn at")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--keep-aces", action="store_true",
                        help="leave the designed aces in, measuring ace plus "
                             "ability instead of the ability alone")
    parser.add_argument("--out", default=os.path.join(
        ROOT, "Documentation", "ability_score_table.md"))
    args = parser.parse_args()

    # Set before the workers are spawned. Windows spawns rather than forks,
    # so this reaches them through the environment they inherit -- which is
    # why ai_rating_simulation reads it from there and not from a global.
    os.environ["POKEMON_FLAT_RATING"] = str(args.rating)
    os.environ.pop("POKEMON_STRIP_ACES", None)
    if not args.keep_aces:
        os.environ["POKEMON_STRIP_ACES"] = "1"

    from Test.ai_rating_simulation import run, _cached_engine
    from Test.ai_winrate_table import tally, as_markdown
    from Scripts.Data.pokemon import list_of_pokemon

    roster = _cached_engine()[0]
    names = list(roster.keys())[1:]                 # [0] is the Protagonist
    workers = args.workers or max(1, (os.cpu_count() or 2) - 2)
    # No cache option on purpose: every cache in this project is a recording
    # of battles fought at the competitors' shipped ratings, and replaying
    # one here would silently answer the ordinary question instead of this
    # one. These battles have to be fought.
    results = run(names, args.matches, workers)
    record, margin, _ = tally(names, results)

    rows = []
    for name in names:
        won, lost, drew = record[name]
        played = won + lost + drew
        aces, best = ace_calibre(roster[name], list_of_pokemon)
        rows.append({"name": name,
                     "ability": roster[name].ability or "(none)",
                     "win": 100.0 * won / max(1, played),
                     "won": won, "lost": lost,
                     "aces": aces, "best": best,
                     "per": margin[name][0] / max(1, played)})
    rows.sort(key=lambda r: (-r["win"], -r["per"]))

    stripped = not args.keep_aces
    nl = chr(10)
    body = []
    body.append("What a character ability is worth")
    body.append("=" * 78)
    body.append("")
    body.append("Every competitor except the player played every other %d times,"
                % args.matches)
    body.append("with every team drawn at rating %d so nobody's Pokemon are"
                % args.rating)
    if stripped:
        body.append("better than anybody else's, and with their designed ace")
        body.append("thrown away as well -- so every competitor draws from an")
        body.append("identical distribution and the character ability is the")
        body.append("only thing left that differs between any two of them.")
        body.append("")
        body.append("This is not who the better competitor is. It measures a")
        body.append("character nobody plays: the ace is half of what makes one,")
        body.append("and it has been deliberately discarded. --keep-aces answers")
        body.append("that other question.")
    else:
        body.append("better than anybody else's. Designed aces are left in")
        body.append("place, so this is ace plus ability with rating removed.")
        body.append("")
        body.append("ACE is the column to read it against: finishing high on a")
        body.append("weak ace is the ability doing the work.")
    body.append("")
    body.append("ACE is the base-stat total of their best designed Pokemon.")
    if stripped:
        body.append("It took no part in these battles and is here only to say")
        body.append("what each competitor gave up. Neither did RATING.")
    body.append("")
    body.append("Differences under %.1f points are variance, not ability --"
                % NOISE_FLOOR[stripped])
    body.append("measured from the competitors who share one, at the end.")
    body.append("")
    if stripped:
        body.append("A row marked (*) holds an ability this mode cannot measure:")
        body.append("see the note below the table.")
        body.append("")
    body.append("%-4s %-19s %-20s %6s %6s %5s %6s"
                % ("RANK", "COMPETITOR", "ABILITY", "WIN%", "ACE", "ACES",
                   "PER"))
    body.append("-" * 78)
    for place, row in enumerate(rows, 1):
        mark = " (*)" if stripped and row["ability"] in ACE_DEPENDENT else ""
        body.append("%-4d %-19s %-20s %5.1f%% %6d %5d %+6.2f%s"
                    % (place, row["name"], row["ability"], row["win"],
                       row["best"], row["aces"], row["per"], mark))

    hobbled = [r for r in rows if r["ability"] in ACE_DEPENDENT]
    if stripped and hobbled:
        body.append("")
        body.append("")
        body.append("Abilities this mode cannot measure")
        body.append("-" * 78)
        body.append("These name a Pokemon rather than reading whichever one is")
        body.append("in front of them, and the Pokemon they name is their")
        body.append("holder's own ace -- so with the aces stripped they do")
        body.append("nothing except by lucky draw. Their rows are a floor, not")
        body.append("a reading. Run --keep-aces to score them.")
        body.append("")
        for row in hobbled:
            body.append("    %-19s %-20s %5.1f%%"
                        % (row["name"], row["ability"], row["win"]))

    if not stripped:
        low, high = CONTROL_BAND
        control = [r for r in rows
                   if r["aces"] == 1 and low <= r["best"] <= high]
        body.append("")
        body.append("")
        body.append("The control group: one ace, %d-%d" % CONTROL_BAND)
        body.append("-" * 78)
        body.append("Same ace calibre, same flat rating, one ace each -- so")
        body.append("among these the ability is the only variable left. With the")
        body.append("aces stripped the whole table is this, which is the point")
        body.append("of that mode.")
        body.append("")
        for row in control:
            body.append("    %-19s %-20s %5.1f%%  ace %d"
                        % (row["name"], row["ability"], row["win"],
                           row["best"]))
        if control:
            body.append("")
            body.append("    spread: %.1f points, %s (%.1f%%) down to %s (%.1f%%)"
                        % (control[0]["win"] - control[-1]["win"],
                           control[0]["ability"], control[0]["win"],
                           control[-1]["ability"], control[-1]["win"]))

    # The same ability twice over, which is the only direct read on how much
    # of a gap is noise: anything this size means nothing. With the aces
    # stripped it is a clean read, because the holders differ in nothing else.
    same = {}
    for row in rows:
        same.setdefault(row["ability"], []).append(row)
    shared = [(a, rs) for a, rs in same.items() if len(rs) > 1]
    if shared:
        body.append("")
        body.append("")
        body.append("The same ability, more than once")
        body.append("-" * 78)
        body.append("Held by two or more competitors. With the aces stripped")
        body.append("nothing separates those holders at all, so the gap between")
        body.append("them is pure variance and sets the floor for reading every")
        body.append("other gap in the table.")
        body.append("")
        for ability, holders in sorted(shared):
            spread = holders[0]["win"] - holders[-1]["win"]
            body.append("    %-20s spread %4.1f points  %s"
                        % (ability, spread,
                           ", ".join("%s %.1f%%" % (h["name"], h["win"])
                                     for h in holders)))

    document = as_markdown("Ability score table", nl.join(body))
    with open(args.out, "w", encoding="utf-8") as out:
        out.write(document)
    print("wrote %s (%d lines)" % (args.out, document.count(nl) + 1))
    print("strongest: %s" % ", ".join(r["name"] for r in rows[:5]))
    print("weakest  : %s" % ", ".join(r["name"] for r in rows[-5:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
