"""The four permanent upgrades.

Bought once and owned for the whole career -- every run in that save slot.
All four are deliberately *meta*: what a round pays, what you know going in,
whether a loss sticks, and how many rounds you play. None of them changes a
rule on the field, and none touches the IV curve or the tier shelf, so every
rating in Data/competitors.csv still describes the game it was measured
against.
"""
import builtins
import io
import os
import random
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import Scripts.Battle.battle_cycle                              # noqa: E402,F401
from Scripts.Battle import battle_win_condition as WIN          # noqa: E402
from Scripts.Battle.constants import ROUND_LIMIT                # noqa: E402
from Scripts.Data.competitors import list_of_competitors        # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon as POKEMON     # noqa: E402
from Scripts.Game import before_battle, savefile, shop          # noqa: E402
from Scripts.Game.game_system import GameSystem                 # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-64s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


class Trainer:
    def __init__(self, coins=0, result=0, strength=200, main=True,
                 upgrades=(), team=()):
        self.coins = coins
        self.result = result
        self.strength = strength
        self.main = main
        self.upgrades = list(upgrades)
        self.team = list(team)
        self.unused_team = []
        self.stage = 1
        self.score = 0
        self.nickname = self.name = "You"
        self.side_color = ""
        self.scouted = None
        # end_battle clears these on both sides, so a stand-in that reaches
        # it has to carry them
        self.entry_hazard = {"Stealth Rock": 0, "Spikes": 0,
                             "Toxic Spikes": 0, "Sticky Web": 0}
        self.in_battle_effects = {"Reflect": 0, "Light Screen": 0,
                                  "Aurora Veil": 0, "Tailwind": 0}


class Ground:
    def __init__(self, exhibition=True):
        self.exhibition = exhibition
        self.verbose = True
        self.battle_continuation = True


def army(*names):
    from copy import deepcopy
    built = []
    for name in names:
        mon = deepcopy(POKEMON[name])
        mon.iv = [20] * 6
        mon.status = "Normal"
        built.append(mon)
    return built


def answering(script):
    """builtins.input answered from `script`, then 'N' for ever.

    `script` may also be a callable taking the prompt, for answering the way
    something other than a list would -- an Auto Run, for instance.
    """
    reply = script if callable(script) else None
    queue = [] if reply else list(script)
    real = builtins.input
    asked = []

    def spy(prompt=""):
        asked.append(str(prompt))
        if reply is not None:
            return reply(str(prompt))
        return queue.pop(0) if queue else "N"

    builtins.input = spy
    return real, asked


# =============================================================== the catalogue
print("-- the four, and what they cost --")
check("there are four", len(shop.UPGRADES), 4)
check("priced as agreed",
      [(name, cost) for name, cost, _l in shop.UPGRADES],
      [("Double Pay", 80), ("Auto Scout", 120),
       ("Retry", 200), ("Seeded", 400)])
check("Seeded covers two rounds", shop.SEEDED_ROUNDS, 2)

print()
print("-- bought once, then owned --")
buyer = Trainer(coins=800)
for name, cost, _line in shop.UPGRADES:
    was = shop.balance(buyer)
    check("  buying %-11s costs %3d" % (name, cost),
          (shop.buy_upgrade(buyer, name), was - shop.balance(buyer)),
          (True, cost))
check("all four owned", len(shop.owned(buyer)), 4)
for name, _cost, _line in shop.UPGRADES:
    check("  %-11s cannot be bought twice" % name,
          shop.buy_upgrade(buyer, name), False)
check("...and nothing more was taken", shop.balance(buyer), 0)

poor = Trainer(coins=79)
check("one coin short buys nothing",
      shop.buy_upgrade(poor, shop.DOUBLE_PAY), False)
check("...and takes nothing", shop.balance(poor), 79)
check("an unknown upgrade is refused", shop.buy_upgrade(poor, "Wings"), False)


# ================================================================ Double Pay
print()
print("-- Double Pay: both directions --")
plain = Trainer()
rich = Trainer(upgrades=[shop.DOUBLE_PAY])
for mine, theirs in ((6, 0), (6, 5), (1, 5), (0, 6)):
    plain.result = rich.result = mine
    single = shop.coins_change(plain, Trainer(result=theirs))
    double = shop.coins_change(rich, Trainer(result=theirs))
    check("  KO %d vs %d  %+d -> %+d" % (mine, theirs, single, double),
          double, single * 2)


# ================================================================ Auto Scout
print()
print("-- Auto Scout: every scout lands --")
GameSystem.stage = 3
random.seed(1)
without = Trainer(strength=5)
weak_foe = Trainer(strength=800, main=False)
rolls = [before_battle.scout_result(without, Trainer(strength=800,
                                                     main=False))
         for _ in range(40)]
check("without it, a heavy underdog often fails (%d of 40 landed)"
      % sum(rolls), not all(rolls))

withit = Trainer(strength=5, upgrades=[shop.AUTO_SCOUT])
landed = [before_battle.scout_result(withit, Trainer(strength=800,
                                                     main=False))
          for _ in range(40)]
check("with it, every one lands", all(landed))
check("...and the roll is not even taken",
      before_battle.scout_result(withit, weak_foe), True)
check("...stamped for this round", weak_foe.scouted, (3, True))


# ===================================================================== Retry
print()
print("-- Retry: once a run, and only if you take it --")
check("not available unowned", shop.retry_available(Trainer()), False)
holder = Trainer(upgrades=[shop.RETRY])
shop.begin_run(holder)
check("available once a run starts", shop.retry_available(holder))
shop.spend_retry(holder)
check("...and gone once spent", shop.retry_available(holder), False)
shop.begin_run(holder)
check("...but back for the next run", shop.retry_available(holder))


def losing_round(who, ground, script):
    """check_win_or_lose with the player's team wiped.

    `end_battle` is stubbed out: it closes the round by walking all
    thirty-two seeded competitors, and the field here is the eight the
    module imports with. The decision being tested happens before it.
    """
    mine = army("Garchomp")
    for mon in mine:
        mon.status = "Fainted"
    theirs = army("Metagross")
    who.team = mine
    foe = Trainer(strength=200, main=False, team=theirs)
    real, asked = answering(script)
    real_end = WIN.end_battle
    WIN.end_battle = lambda *a, **k: None
    real_choose = WIN.choose_pokemon
    WIN.choose_pokemon = lambda *a, **k: None
    raised = None
    try:
        with redirect_stdout(io.StringIO()):
            WIN.check_win_or_lose(who, foe, mine, theirs, ground)
    except shop.RoundRetry:
        raised = True
    except Exception as problem:                       # noqa: BLE001
        raised = type(problem).__name__
    finally:
        builtins.input = real
        WIN.end_battle = real_end
        WIN.choose_pokemon = real_choose
    return raised, asked, foe


owner = Trainer(upgrades=[shop.RETRY], strength=200)
shop.begin_run(owner)
raised, asked, _foe = losing_round(owner, Ground(exhibition=False), ["Y"])
check("a loss offers the retry",
      any("Retry" in question for question in asked))
check("...and saying yes abandons the round", raised, True)
check("...spending it", shop.retry_available(owner), False)

# ...and it is optional
again = Trainer(upgrades=[shop.RETRY], strength=200)
shop.begin_run(again)
raised, asked, foe = losing_round(again, Ground(exhibition=False), ["N"])
check("saying no lets the loss stand", raised, None)
check("...the retry is not spent", shop.retry_available(again))
check("...and the opponent advances", foe.stage, 2)

# never offered where it does not belong
quiet = Trainer(upgrades=[shop.RETRY], strength=200)
shop.begin_run(quiet)
_r, asked, _f = losing_round(quiet, Ground(exhibition=False), ["N"])
check("it is offered to a player", any("Retry" in q for q in asked))

ai = Trainer(upgrades=[shop.RETRY], strength=200, main=False)
shop.begin_run(ai)
_r, asked, _f = losing_round(ai, Ground(exhibition=False), ["Y"])
check("never offered in an AI-vs-AI battle",
      any("Retry" in q for q in asked), False)

unowned = Trainer(strength=200)
shop.begin_run(unowned)
_r, asked, _f = losing_round(unowned, Ground(exhibition=False), ["Y"])
check("never offered without the upgrade",
      any("Retry" in q for q in asked), False)

show = Trainer(upgrades=[shop.RETRY], strength=200)
shop.begin_run(show)
_r, asked, _f = losing_round(show, Ground(exhibition=True), ["Y"])
check("never offered in an exhibition -- Custom Play has no round to replay",
      any("Retry" in q for q in asked), False)

# ...and an Auto Run declines it. The offer is still made -- an unattended
# run answers prompts rather than being spared them -- and `auto_run.answer`
# is what replies, because that is the one place that knows how to answer a
# question with nobody watching. Anything it does not recognise returns None
# and falls through to whoever asked, which in an Auto Run is nobody, so a
# missing rule here would stall the run at the first round it lost.
from Scripts.Game import auto_run                                # noqa: E402

RETRY_PROMPT = WIN.RETRY_QUESTION
auto_run.state.active = True
try:
    check("an Auto Run answers the retry prompt",
          auto_run.answer(RETRY_PROMPT), "N")
finally:
    auto_run.state.active = False
check("...and nobody else's answer is scripted",
      auto_run.answer(RETRY_PROMPT), None)


def simulated(prompt):
    """What an Auto Run would answer, falling back to the wrong answer.

    "Y" rather than "N" on purpose: if `auto_run.answer` ever stops
    recognising the prompt, this says yes and the round is retried, so the
    check below fails instead of passing by accident.
    """
    scripted = auto_run.answer(prompt)
    return "Y" if scripted is None else scripted


def simulated_round(who, ground):
    """A losing round whose prompts are answered the way an Auto Run is."""
    auto_run.state.active = True
    try:
        raised, asked, _foe = losing_round(who, ground, simulated)
    finally:
        auto_run.state.active = False
    return raised, asked


lonely = Trainer(upgrades=[shop.RETRY], strength=200)
shop.begin_run(lonely)
raised, asked = simulated_round(lonely, Ground(exhibition=False))
check("the retry is still owned during an Auto Run",
      shop.retry_available(lonely))
check("...it is offered", any("Retry" in q for q in asked))
check("...and declined, so the loss stands", raised, None)
check("...leaving it unspent", shop.retry_available(lonely))
check("the rule lives in auto_run, not in a gate in shop",
      "Retry" in io.open("Scripts/Game/auto_run.py",
                         encoding="utf-8").read())
check("...and shop never consults it (it only says where the rule lives)",
      "import auto_run" in io.open("Scripts/Game/shop.py",
                                   encoding="utf-8").read(), False)


# ==================================================================== Seeded
print()
print("-- Seeded: a round won without being played --")
GameSystem.stage = 1
random.seed(3)
lines = []
scores = []
for _ in range(40):
    me = Trainer(coins=0, strength=200, upgrades=[shop.SEEDED],
                 team=army("Garchomp"))
    foe = Trainer(strength=200, main=False, team=army("Metagross"))
    with redirect_stdout(io.StringIO()):
        WIN.seeded_win(me, foe, Ground(exhibition=True))
    lines.append((me.result, foe.result))
    scores.append(shop.balance(me))

limit = ROUND_LIMIT[1]
check("you always take the full round (%d)" % limit,
      {mine for mine, _t in lines}, {limit})
check("...and they always take fewer",
      all(theirs < limit for _m, theirs in lines))
# Every scoreline from a shutout to a scrape, flat. It used to borrow
# result_announcement's rating-weighted shape and came out 4-3 every time in
# round 1 -- 4 * 200/400 = 2.0, times uniform(1.25, 1.75) is 2.5..3.5, which
# rounds to 3 or 4 and is then clamped to limit - 1. The clamp ate the spread.
check("...and every margin from a shutout up is reachable (%s)"
      % sorted({theirs for _m, theirs in lines}),
      sorted({theirs for _m, theirs in lines}), list(range(limit)))
check("...so a seeded round can be a shutout",
      0 in {theirs for _m, theirs in lines})
check("...and can be a scrape",
      limit - 1 in {theirs for _m, theirs in lines})
check("the round advances your stage",
      Trainer(upgrades=[shop.SEEDED]).stage, 1)

me = Trainer(coins=4, strength=200, upgrades=[shop.SEEDED],
             team=army("Garchomp"))
foe = Trainer(strength=200, main=False, team=army("Metagross"))
before_stage, before_team = me.stage, len(me.team)
with redirect_stdout(io.StringIO()):
    WIN.seeded_win(me, foe, Ground(exhibition=True))
check("your stage advances", me.stage, before_stage + 1)
check("the coins are paid", shop.balance(me) > 4)
# the whole cost of the upgrade: a round you did not play pays no Pokemon
check("no Pokemon is handed out", len(me.team), before_team)

# and it only covers the opening rounds -- the call site checks the stage
main_src = io.open("main.py", encoding="utf-8").read()
check("the career loop gates it on the opening rounds",
      "GameSystem.stage <= shop.SEEDED_ROUNDS" in main_src)
check("...after next_battle, so the field is drawn",
      main_src.index("opponent = next_battle()")
      < main_src.index("seeded_win("))
check("...and it hands out no reward",
      "choose_pokemon" not in
      main_src[main_src.index("seeded_win("):
               main_src.index("before_battle_option")])

# Seeded applies to an Auto Run as well, unlike the retry. It asks nothing,
# so there is nobody to ask: the round closes itself either way, and a
# simulated career of a save that owns the upgrade should play the career
# that save actually has.
gate = main_src[main_src.index("if (shop.owns(protagonist, shop.SEEDED)"):
                main_src.index("before_battle_option")]
check("nothing in the seeded gate asks whether a run is simulated",
      "auto_run" in gate, False)

auto_run.state.active = True
try:
    me = Trainer(coins=0, strength=200, upgrades=[shop.SEEDED],
                 team=army("Garchomp"))
    foe = Trainer(strength=200, main=False, team=army("Metagross"))
    with redirect_stdout(io.StringIO()):
        WIN.seeded_win(me, foe, Ground(exhibition=True))
    check("a simulated round is still won", me.result > foe.result)
    check("...and still advances the stage", me.stage, 2)
    check("...and still pays", shop.balance(me) > 0)
finally:
    auto_run.state.active = False


# ============================================================= in the career
print()
print("-- owned for the whole career --")
room = tempfile.mkdtemp(prefix="upgrades-")
target = os.path.join(room, "savefile1.json")
try:
    player = list_of_competitors["Protagonist"]
    was_up = list(getattr(player, "upgrades", None) or [])
    was_coins = getattr(player, "coins", 0)
    player.upgrades = [shop.DOUBLE_PAY, shop.SEEDED]
    savefile.save(list_of_competitors, path=target)
    player.upgrades = []
    savefile.load(list_of_competitors, POKEMON, path=target)
    check("they survive a save and load",
          sorted(shop.owned(player)), sorted([shop.DOUBLE_PAY, shop.SEEDED]))

    body = io.open(target, encoding="utf-8").read()
    body = body.replace('"upgrades": [', '"was_upgrades": [')
    io.open(target, "w", encoding="utf-8").write(body)
    player.upgrades = ["x"]
    savefile.load(list_of_competitors, POKEMON, path=target)
    check("a save written before them restores to none",
          shop.owned(player), set())
finally:
    player.upgrades = was_up
    player.coins = was_coins
    shutil.rmtree(room, ignore_errors=True)

# NEW GAME clears them, because start_fresh restores from the CSVs
save_src = io.open("Scripts/Game/savefile.py", encoding="utf-8").read()
check("a new game is not given any (nothing in the CSVs grants one)",
      "upgrades" not in
      io.open("Data/competitors.csv", encoding="ISO-8859-1").read().lower())

# ======================================================== the shop's buttons
print()
print("-- the menu the interface reads --")
# The bug this guards was invisible to every check above, because the shop's
# *logic* was right: a player owning all four upgrades could no longer click
# Refresh or Swap. The interface builds its buttons by walking back from the
# prompt through what was printed and stopping after two consecutive lines
# that are not options (GUI/prompt_parser._tail_block, which is what stops a
# previous screen's menu leaking into this one). Four "OWNED" lines printed
# among the numbered ones are four such lines, so the walk broke off above
# them and the two consumables were never seen.
#
# So this drives the real shop and parses what it really printed, in every
# ownership state. A reconstruction of the menu would have agreed with
# whatever the test author believed it printed.
import itertools                                                 # noqa: E402

from GUI import prompt_parser                                    # noqa: E402
from Scripts.Game.game_procedure import team_generation          # noqa: E402

shopper = list_of_competitors["Protagonist"]
held_up, held_coins = list(getattr(shopper, "upgrades", None) or []), \
    getattr(shopper, "coins", 0)
held_team, held_bench = list(shopper.team), list(shopper.unused_team or [])
UPGRADE_NAMES = [name for name, _c, _l in shop.UPGRADES]


def printed_menu(owned):
    """The shop's real menu, captured at the moment it asks its question."""
    shopper.upgrades = list(owned)
    buffer = io.StringIO()
    real, seen = builtins.input, []

    def spy(prompt=""):
        # the log as it stands when the question is asked, which is exactly
        # what the interface has to read its buttons out of
        seen.append((str(prompt), buffer.getvalue()))
        return "0"

    builtins.input = spy
    try:
        with redirect_stdout(buffer):
            shop.shop(shopper)
    finally:
        builtins.input = real
    return seen[0]


try:
    shopper.coins = 1000
    shopper.team = team_generation(shopper)
    shopper.unused_team = []
    broken = []
    for size in range(len(UPGRADE_NAMES) + 1):
        for owned in itertools.combinations(UPGRADE_NAMES, size):
            prompt, log = printed_menu(owned)
            got = prompt_parser.parse(prompt, log)
            values = sorted(int(c.value) for c in got.choices)
            want = sorted([0] + [v for v, _l, _c, _b in shop.SHOP_ITEMS]
                          + [len(shop.SHOP_ITEMS) + 1 + index
                             for index, name in enumerate(UPGRADE_NAMES)
                             if name not in owned])
            if got.mode != prompt_parser.MODE_CHOICES or values != want:
                broken.append((owned, got.mode, values, want))
    check("every option is clickable in all %d ownership states"
          % 2 ** len(UPGRADE_NAMES), broken, [])

    # the case that broke, named on its own so a regression says which
    prompt, log = printed_menu(UPGRADE_NAMES)
    values = sorted(int(c.value)
                    for c in prompt_parser.parse(prompt, log).choices)
    check("...including owning all four, which lost the consumables",
          values, sorted([0] + [v for v, _l, _c, _b in shop.SHOP_ITEMS]))
    check("an owned upgrade is shown, without a number to click",
          all(("%s" % name) in log for name in UPGRADE_NAMES))
    check("...and marked as owned", "OWNED" in log)

    # why it is safe: the numbered lines are one unbroken run
    numbered = [index for index, line in enumerate(log.splitlines())
                if line.strip()[:1].isdigit()]
    check("the numbered lines are contiguous, so no gap rule can cut them",
          numbered == list(range(min(numbered), max(numbered) + 1)))
finally:
    shopper.upgrades = held_up
    shopper.coins = held_coins
    shopper.team = held_team
    shopper.unused_team = held_bench

# and the retry offer is answered by clicking, not by typing
check("the retry offer is a yes/no question, not a text box",
      prompt_parser.parse(WIN.RETRY_QUESTION).mode,
      prompt_parser.MODE_CONFIRM)
check("...and the buttons say Y/N, so the question does not",
      "Y/N" in prompt_parser.parse(WIN.RETRY_QUESTION).question, False)
check("...while auto_run still recognises it",
      "Retry" in WIN.RETRY_QUESTION)


print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
