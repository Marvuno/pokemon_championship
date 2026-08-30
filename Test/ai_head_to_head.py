"""Is the smart AI actually better than the dumb one? A controlled test.

The rating simulation cannot answer this: **every competitor in an AI-vs-AI
simulation plays with the smart AI**, whatever their rating. Comparing
low-rated to high-rated competitors in `ai_rating_simulation.py` therefore
says nothing at all about the two AIs -- it compares their *teams*. That
mistake was made, on this data, before this file existed.

Since this was written the dumb AI has stopped appearing in normal play at
all: which AI an opponent uses is the difficulty setting rather than their
rating, so the simple one is what Beginner is. The comparison below is
therefore about what the two difficulties are worth, not about who meets
which AI.

**This study is stale in one other way.** It was measured against the AI's
old move-ranking rule, which sorted on priority first; that rule is gone (see
`DEFAULT_RANKING` in Scripts/Battle/ai.py). Its central finding -- that the
smart AI is a liability with weak teams -- may not survive a re-run, because
`Test/ai_ranking_experiment.py` reproduced almost exactly that curve from the
sort key alone.

What this does instead. Everything that is not the AI is held equal:

    the same team          both sides get identical copies of one team --
                           same species, same IVs, same abilities, same
                           movesets. Team quality is not a variable.
    no character ability   both sides have theirs cleared, so Procrastination
                           and friends cannot decide the result
    the same rating        both sides carry the same `strength`, so nothing
                           that reads rating can differ either. The AI is
                           chosen by a marker attribute, not by rating.
    both orientations      every team is played twice with the sides swapped,
                           so any advantage in being side A cancels

and the only remaining difference is which function picks the moves.

There is a control band as well: smart against smart, identical teams. It
has to come out at about 50%, and if it does not, the harness is measuring
its own asymmetry rather than the AI.

Teams are drawn at several ratings, because "is the smart AI better" may
well have different answers with a bad team and a good one -- a smarter
pilot needs something to fly.

    python Test/ai_head_to_head.py                     the whole thing
    python Test/ai_head_to_head.py --teams 50           quicker, rougher
    python Test/ai_head_to_head.py --workers 4          smaller machines

Writes Documentation/ai_head_to_head.md.
"""
import argparse
import io
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

#: 6v6, the full-strength matchup
STAGE = 5
#: teams per band, unless --teams says otherwise. Each is played twice.
TEAMS = 300
#: the ratings teams are drawn at. Not the AI's rating -- both sides always
#: carry the same one -- purely the quality of the team both sides fly.
BANDS = (20, 60, 150, 300, 600)

#: The three things the smart AI is allowed to do about switching. The
#: question they answer together is whether its switching is what costs it
#: the low-rated bands.
#:
#:   BASELINE    the smart AI as shipped
#:   NOSWITCH    it may never volunteer a switch. The clean ablation: one
#:               behaviour removed, nothing added, no extra engine calls.
#:   DUMBSWITCH  it switches only where the dumb AI would -- against an
#:               incoming x4 move, or with no damaging move of its own --
#:               and picks its moves as usual otherwise.
#:
#: Read NOSWITCH as the decisive one. DUMBSWITCH runs a second AI evaluation
#: per turn to ask the dumb rule, and those evaluations apply ability scoring
#: to the real battleground, so it carries a small confound the ablation does
#: not. If the two agree, the confound did not matter.
BASELINE, NOSWITCH, DUMBSWITCH = "baseline", "noswitch", "dumbswitch"
ARMS = (BASELINE, NOSWITCH, DUMBSWITCH)

_CACHE = {}


def _engine():
    """Import the engine once per worker, and install the AI dispatcher.

    `move_selection` calls `smart_ai_select_move` for both sides in verbose
    mode, so there is no argument to vary and no flag to set. Rebinding that
    one name in `battle_cycle` is enough -- and it has to be that module
    rather than `ai`, because `Scripts/` uses `from x import *` and the
    caller holds its own reference (see patch_everywhere in CLAUDE.md).

    The wrapper reads the *acting* trainer, which both AIs take as their
    third argument, and dispatches on a marker this harness sets.
    """
    # battle_cycle FIRST, always. Scripts/ modules star-import each other and
    # the game always enters through battle_cycle, so importing a module from
    # the middle of that web first leaves a half-built one behind it:
    # importing `ai` ahead of this raised `NameError:
    # user_turn_in_battle_stats` from battle_checklist, several battles deep.
    import Scripts.Battle.battle_cycle as cycle
    import Scripts.Battle.ai as ai_module
    from Scripts.Battle.ai import dumb_ai_select_move, smart_ai_select_move
    from Scripts.Data.battlefield import Battleground
    from Scripts.Data.competitors import list_of_competitors
    from Scripts.Game.game_procedure import team_generation
    from Scripts.Game.game_system import GameSystem
    GameSystem.stage = STAGE

    # -- the switching gate, for the NOSWITCH and DUMBSWITCH arms ----------
    #
    # Only the *voluntary* recall is gated. `ai_switching_mechanism` answers
    # two quite different questions depending on its arguments, and gating
    # the wrong one breaks the battle rather than changing the strategy:
    #
    #   recall=True,  forced=False   "should I switch out?"   <- gate this
    #   recall=False                 "who replaces the Pokemon that fainted?"
    #   recall=True,  forced=True    Roar/Whirlwind, and auto-battle
    #
    # Returning 0 for either of the last two would leave a fainted Pokemon
    # on the field. The condition below is the same one the function's own
    # first line tests.
    real_switching = ai_module.ai_switching_mechanism

    def gated_switching(protagonist, acting, battleground, recall=False,
                        forced_switch=False, incoming_move=0):
        voluntary = recall and not forced_switch
        if voluntary and getattr(acting, "no_voluntary_switch", False):
            return 0
        return real_switching(protagonist, acting, battleground, recall,
                              forced_switch, incoming_move)

    ai_module.ai_switching_mechanism = gated_switching

    def dispatch(battleground, foe, acting):
        if getattr(acting, "dumb_ai", False):
            chosen = dumb_ai_select_move(battleground, foe, acting)
        elif getattr(acting, "arm", BASELINE) == DUMBSWITCH:
            # Ask the real dumb AI whether *it* would switch here, rather
            # than reimplementing its rule (switch only against an incoming
            # x4 move, or with no damaging move of your own). Copying that
            # test into this harness would be a second copy of engine logic
            # free to drift from the original -- the trap recorded in
            # CLAUDE.md about the AI's damage helpers.
            acting.no_voluntary_switch = False
            probe = dumb_ai_select_move(battleground, foe, acting)
            acting.no_voluntary_switch = True
            if probe.name == "Switching":
                chosen = probe                    # switch, on the dumb rule
            else:
                acting.position_change = 0
                chosen = smart_ai_select_move(battleground, foe, acting)
        else:
            # BASELINE, or NOSWITCH where the gate above blocks its recall
            chosen = smart_ai_select_move(battleground, foe, acting)
        # Count the turns each side spends swapping rather than attacking.
        # A switch costs a whole turn, so if one AI is losing with a weak
        # team this is the first place to look -- see the report.
        acting.turns_taken = getattr(acting, "turns_taken", 0) + 1
        if chosen.name == "Switching":
            acting.switches = getattr(acting, "switches", 0) + 1
        return chosen

    cycle.smart_ai_select_move = dispatch
    return (list_of_competitors, Battleground, cycle.battle_setup,
            team_generation)


def _cached_engine():
    if "engine" not in _CACHE:
        _CACHE["engine"] = _engine()
    return _CACHE["engine"]


def seed_for(rating, trial, tag):
    """A reproducible seed.

    Arithmetic, never `hash()`. Tuple and string hashes are salted per
    process, and the workers are separate processes -- so a hash-derived seed
    would hand the two orientations of one trial *different teams*, quietly
    destroying the only control this experiment has. Same family of bug as
    the set-iteration one that made the fingerprint irreproducible.
    """
    return (rating * 1000003 + trial * 9176 + tag * 7919) & 0x7FFFFFFF


def play(task):
    """One battle. `task` is (rating, trial, dumb_is_side_a, control).

    Returns (rating, dumb_is_side_a, who won) where the winner is "dumb",
    "smart" or "draw" -- named rather than positional, because the whole
    point of playing both orientations is that a side number means nothing.

    In a control battle neither side is dumb, and the result is reported as
    if side A were the smart one, so the same tally reads as side A's win
    rate over a perfectly symmetric matchup.
    """
    rating, trial, dumb_first, is_control, arm = task
    roster, Battleground, battle_setup, team_generation = _cached_engine()

    # One team, built once, then copied. Seeded from (rating, trial) alone --
    # not the orientation -- so both orientations of a trial fly the same
    # team. That is the entire control.
    random.seed(seed_for(rating, trial, 1))
    builder = deepcopy(roster["Protagonist"])
    builder.main = False              # so team_generation fills all six
    builder.team = []                 # no designed aces: a random team
    builder.strength = rating
    with redirect_stdout(io.StringIO()):
        team = team_generation(builder)

    side_a, side_b = deepcopy(builder), deepcopy(builder)
    for index, side in enumerate((side_a, side_b)):
        side.name = side.nickname = ("A", "B")[index]
        # both sides at the same rating, so nothing that reads rating differs
        side.strength = rating
        # character abilities off: UseCharacterAbility suppresses the KeyError
        side.ability = ""
        side.team = deepcopy(team)
    if is_control:
        side_a.dumb_ai = side_b.dumb_ai = False
    else:
        side_a.dumb_ai, side_b.dumb_ai = bool(dumb_first), not dumb_first
    for side in (side_a, side_b):
        side.arm = arm
        # the gate reads this; only the smart side is ever restricted
        side.no_voluntary_switch = (not side.dumb_ai
                                    and arm in (NOSWITCH, DUMBSWITCH))

    ground = Battleground()
    ground.verbose = True             # the AI-vs-AI path, both sides choosing
    random.seed(seed_for(rating, trial, 2))
    with redirect_stdout(io.StringIO()):
        with suppress(RecursionError):
            battle_setup(side_a, side_b, side_a.team, side_b.team, ground)

    if side_a.score == side_b.score:
        winner = "draw"
    elif is_control:
        # no dumb side to name: report side A as "smart" so the tally reads
        # as side A's win rate
        winner = "smart" if side_a.score > side_b.score else "dumb"
    else:
        ahead = side_a if side_a.score > side_b.score else side_b
        winner = "dumb" if ahead.dumb_ai else "smart"

    def habit(side):
        return (getattr(side, "switches", 0), getattr(side, "turns_taken", 0))

    smart_side = side_b if side_a.dumb_ai else side_a
    dumb_side = side_a if side_a.dumb_ai else side_b
    return (rating, bool(dumb_first), winner, habit(smart_side),
            habit(dumb_side), arm)


def schedule(bands, teams, is_control=False, arm=BASELINE):
    """Every team in both orientations, so side bias cancels.

    The team seed ignores the arm, so all three arms fly exactly the same
    teams -- which makes arm-to-arm differences paired rather than merely
    statistical.
    """
    return [(rating, trial, dumb_first, is_control, arm)
            for rating in bands
            for trial in range(teams)
            for dumb_first in (True, False)]


def tally(results):
    """rating -> {'smart': n, 'dumb': n, 'draw': n} plus a side breakdown."""
    counts, by_side = {}, {}
    for rating, dumb_first, winner, _, _, _ in results:
        counts.setdefault(rating, {"smart": 0, "dumb": 0, "draw": 0})
        counts[rating][winner] += 1
        by_side.setdefault(dumb_first, {"smart": 0, "dumb": 0, "draw": 0})
        by_side[dumb_first][winner] += 1
    return counts, by_side


def switching(results):
    """rating -> how much of each AI's turns went on switching."""
    habits = {}
    for rating, _, _, smart, dumb, _ in results:
        row = habits.setdefault(rating, {"smart": [0, 0], "dumb": [0, 0]})
        for key, (switches, turns) in (("smart", smart), ("dumb", dumb)):
            row[key][0] += switches
            row[key][1] += turns
    return habits


def rate(row):
    """The smart AI's win rate over decided battles, as a percentage."""
    decided = row["smart"] + row["dumb"]
    return 100.0 * row["smart"] / decided if decided else 0.0


def interval(row):
    """Half-width of the 95% interval on that rate, in percentage points.

    A normal approximation, which is honest enough at these counts and says
    the thing a reader needs: whether a gap is bigger than the noise.
    """
    decided = row["smart"] + row["dumb"]
    if decided < 2:
        return 0.0
    share = row["smart"] / decided
    return 196.0 * (share * (1 - share) / decided) ** 0.5


def run(tasks, workers, worker=play, label="battles"):
    started = time.perf_counter()
    print("%d %s using %d worker process(es)" % (len(tasks), label, workers),
          flush=True)
    results = []
    with Pool(processes=workers) as pool:
        for index, outcome in enumerate(pool.imap_unordered(worker, tasks,
                                                            chunksize=4), 1):
            results.append(outcome)
            if index % 500 == 0:
                spent = time.perf_counter() - started
                print("    %5d/%d  %4.0f/s" % (index, len(tasks),
                                               index / spent), flush=True)
    print("  done in %.1f minutes" % ((time.perf_counter() - started) / 60.0),
          flush=True)
    return results


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


def report(path, bands, arms, control_counts, teams, elapsed):
    """arms is arm -> (counts, by_side, habits)."""
    lines = []

    def add(text=""):
        lines.append(text)

    add("DOES THE SMART AI'S SWITCHING COST IT THE LOW BANDS?")
    add("=" * 74)
    add()
    add("%d teams per band per arm, each played twice with the sides swapped."
        % teams)
    add("Both sides field identical copies of one randomly drawn team, carry")
    add("the same rating, and have their character ability cleared. All three")
    add("arms fly the same teams, so the differences are paired.")
    add()
    add("Every number is the SMART side's win rate against the dumb AI.")
    add()
    add("    baseline     the smart AI as shipped")
    add("    no switch    it may never volunteer a switch (the ablation)")
    add("    dumb rule    it switches only where the dumb AI would")
    add()
    add("Generated by Test/ai_head_to_head.py in %.1f minutes."
        % (elapsed / 60.0))
    add()
    add("-" * 74)
    add("%-14s %14s %14s %14s   %s"
        % ("TEAM QUALITY", "BASELINE", "NO SWITCH", "DUMB RULE", "ABLATION"))
    add("-" * 74)
    for rating in bands:
        cells, base = [], None
        for arm in ARMS:
            row = arms[arm][0].get(rating)
            if not row:
                cells.append("%14s" % "-")
                continue
            cells.append("%8.1f%% +-%.1f" % (rate(row), interval(row)))
            if arm == BASELINE:
                base = rate(row)
        shift = arms[NOSWITCH][0].get(rating)
        move = ("%+.1f pts" % (rate(shift) - base)) if shift and base else ""
        add("%-14s %s %s %s   %s"
            % ("rating %d" % rating, cells[0], cells[1], cells[2], move))
    add("-" * 74)
    totals = {}
    for arm in ARMS:
        counts = arms[arm][0]
        totals[arm] = {key: sum(counts[r][key] for r in counts)
                       for key in ("smart", "dumb", "draw")}
    add("%-14s %8.1f%% +-%.1f %8.1f%% +-%.1f %8.1f%% +-%.1f   %+.1f pts"
        % ("all bands",
           rate(totals[BASELINE]), interval(totals[BASELINE]),
           rate(totals[NOSWITCH]), interval(totals[NOSWITCH]),
           rate(totals[DUMBSWITCH]), interval(totals[DUMBSWITCH]),
           rate(totals[NOSWITCH]) - rate(totals[BASELINE])))
    add()

    add("-- how much switching each arm actually did --")
    add()
    add("The smart side's switches as a share of its own turns. NO SWITCH")
    add("must read 0.0%; anything else means the gate leaked.")
    add()
    add("%-14s %12s %12s %12s" % ("TEAM QUALITY", "BASELINE", "NO SWITCH",
                                  "DUMB RULE"))
    for rating in bands:
        cells = []
        for arm in ARMS:
            row = arms[arm][2].get(rating)
            if not row:
                cells.append("%12s" % "-")
                continue
            switches, turns = row["smart"]
            cells.append("%11.1f%%" % (100.0 * switches / max(1, turns)))
        add("%-14s %s %s %s" % ("rating %d" % rating, *cells))
    add()

    add("-- the control: smart against smart, identical teams --")
    add()
    add("If this is not near 50%, the harness has a side bias and everything")
    add("above is measuring that instead of the AI.")
    add()
    for rating in bands:
        row = control_counts.get(rating)
        if not row:
            continue
        add("    rating %-6d side A %4d   side B %4d   draws %3d   %5.1f%%"
            % (rating, row["smart"], row["dumb"], row["draw"], rate(row)))
    add()

    add("-- orientation check, per arm --")
    add()
    for arm in ARMS:
        parts = []
        for dumb_first, row in sorted(arms[arm][1].items()):
            parts.append("side %s %5.1f%%" % ("B" if dumb_first else "A",
                                              rate(row)))
        add("    %-11s %s" % (arm, "   ".join(parts)))
    add()

    add("-" * 74)
    base_low = rate(arms[BASELINE][0][bands[0]])
    abl_low = rate(arms[NOSWITCH][0][bands[0]])
    edge = interval(arms[NOSWITCH][0][bands[0]])
    add("At the weakest band (rating %d) the smart AI went from %.1f%% to"
        % (bands[0], base_low))
    add("%.1f%% (+/- %.1f) with its switching removed." % (abl_low, edge))
    if abl_low - edge > base_low:
        add("VERDICT: switching was costing it the low bands.")
    elif abl_low + edge < base_low:
        add("VERDICT: switching was HELPING; the cause is something else.")
    else:
        add("VERDICT: no measurable change -- switching is not the cause.")
    add("-" * 74)

    with open(path, "w", encoding="utf-8") as out:
        out.write(as_markdown("Smart AI vs dumb AI",
                              chr(10).join(lines)))
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", type=int, default=TEAMS,
                        help="teams per band per arm (default %d)" % TEAMS)
    parser.add_argument("--workers", type=int, default=0,
                        help="worker processes (default: cores - 2)")
    parser.add_argument("--out", default=os.path.join(
        ROOT, "Documentation", "ai_head_to_head.md"))
    args = parser.parse_args()

    workers = args.workers or max(1, (os.cpu_count() or 2) - 2)
    started = time.perf_counter()

    arms = {}
    for arm in ARMS:
        print("-- arm: %s --" % arm)
        results = run(schedule(BANDS, args.teams, arm=arm), workers)
        arms[arm] = (tally(results)[0], tally(results)[1], switching(results))

    # the control only has to show that 50% comes out of a symmetric
    # matchup, so it gets a quarter of the teams
    print("-- control: smart vs smart --")
    control_results = run(schedule(BANDS, max(1, args.teams // 4),
                                   is_control=True), workers,
                          label="control battles")
    control_counts = tally(control_results)[0]

    lines = report(args.out, BANDS, arms, control_counts, args.teams,
                   time.perf_counter() - started)
    print()
    print(chr(10).join(lines))
    print()
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
