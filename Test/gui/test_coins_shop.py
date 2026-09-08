"""Coins, and the shop that spends them.

Coins are earned from the knockouts a round takes off the opponent less the
ones it gives up, floored at nothing -- so a rout pays and a loss costs
nothing rather than taking coins away. They belong to one career in one save
slot, so what matters is that they survive a save and start at zero.

The shop's two purchases are both about the team you have rather than a
bigger one, and both have a rule that keeps them from becoming a way to buy
power: an IV re-roll can come out worse, and a swap carries the IV total
across unchanged.
"""
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
from Scripts.Data.competitors import list_of_competitors        # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon as POKEMON     # noqa: E402
from Scripts.Game import before_battle, savefile, shop          # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-62s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


class Trainer:
    def __init__(self, coins=0, result=0, strength=200, team=()):
        self.coins = coins
        self.result = result
        self.strength = strength
        self.team = list(team)
        self.unused_team = []


def build(species, ivs=None):
    from copy import deepcopy
    mon = deepcopy(POKEMON[species])
    mon.iv = list(ivs) if ivs else [20] * 6
    mon.total_iv = sum(mon.iv)
    mon.nominal_base_stats = [a + b for a, b in zip(mon.base_stats, mon.iv)]
    return mon


# =============================================================== the payout
print("-- what a round pays --")
for mine, theirs, want in ((6, 0, 6), (6, 5, 1), (3, 3, 0), (0, 6, 0),
                           (1, 0, 1), (2, 4, 0)):
    check("  you KO %d, they KO %d -> %d" % (mine, theirs, want),
          shop.coins_earned(Trainer(result=mine), Trainer(result=theirs)),
          want)

purse = Trainer(coins=3, result=5)
check("a payout adds to what you had",
      shop.award(purse, Trainer(result=1)), 4)
check("...and the balance follows", shop.balance(purse), 7)
check("a losing round pays nothing rather than taking any",
      shop.award(purse, Trainer(result=99)), 0)
check("...leaving the balance alone", shop.balance(purse), 7)
check("a balance is never negative", shop.balance(Trainer(coins=-5)), 0)

check("you cannot spend what you do not have",
      shop.spend(Trainer(coins=1), shop.COST_SWAP_POKEMON), False)
short = Trainer(coins=1)
shop.spend(short, shop.COST_SWAP_POKEMON)
check("...and nothing is taken when it is refused", shop.balance(short), 1)
rich = Trainer(coins=9)
check("a purchase that can be paid is", shop.spend(rich, 5), True)
check("...and takes exactly its price", shop.balance(rich), 4)


# ============================================================ refreshing IVs
print()
print("-- re-rolling one Pokemon's IVs --")
random.seed(4)
owner = Trainer(strength=200)
mon = build("Garchomp", [5] * 6)
before, after = shop.refresh_iv(mon, owner)
check("the IVs change", before != after)
check("...every one of them legal",
      all(0 <= value <= shop.IV_CEILING for value in after))
check("...and the stats follow the new IVs",
      mon.nominal_base_stats,
      [base + iv for base, iv in zip(mon.base_stats, mon.iv)])
check("...with the total kept in step", mon.total_iv, sum(after))

# An even gamble from wherever the Pokemon starts, which took three goes.
# Floored at the player's rating it reached 31 at a high rating and did
# nothing at all; drawing the six stats independently over 0..31 is pulled
# to *that* mean of 93, so a Pokemon at 170 came out worse 300 times in 300.
# The total is drawn either side of the current one instead.
print("   %-10s %8s %8s %8s   %s" % ("from", "higher", "lower", "equal",
                                     "mean"))
for start in (60, 120, 170):
    random.seed(9)
    up = down = 0
    totals = []
    for _ in range(300):
        one = build("Garchomp", [start // 6] * 6)
        one.iv[0] += start - sum(one.iv)
        was, now = shop.refresh_iv(one, owner)
        totals.append(sum(now))
        if sum(now) > sum(was):
            up += 1
        elif sum(now) < sum(was):
            down += 1
    mean = sum(totals) / float(len(totals))
    print("   IV %-7d %8d %8d %8d   %.1f"
          % (start, up, down, 300 - up - down, mean))
    check("  IV %d re-rolls both ways" % start, up > 60 and down > 60)
    check("  ...and keeps its average (%.1f vs %d)" % (mean, start),
          abs(mean - start) <= 6)
    check("  ...inside the swing either side",
          max(totals) - min(totals) <= 2 * shop.IV_SWING + 1)


# ================================================================ the spread
print()
print("-- an IV total, spread differently --")
random.seed(7)
for total in (0, 37, 120, 186):
    parts = shop.spread(total)
    check("  %3d spreads to six parts summing to %3d" % (total, total),
          sum(parts), total)
    check("  ...none of them over the ceiling", max(parts) <= shop.IV_CEILING)
check("a total beyond six maxima is clamped",
      sum(shop.spread(999)), 6 * shop.IV_CEILING)


# ================================================================ the swapping
print()
print("-- one Pokemon for another off the same shelf --")
random.seed(2)
mine = build("Garchomp", [17, 3, 21, 8, 30, 11])
tier = shop.tier_of(mine)
incoming = shop.swap_pokemon(mine)
check("a swap produces something", incoming is not None)
if incoming is not None:
    check("...off the same shelf", shop.tier_of(incoming), tier)
    check("...not the same Pokemon", incoming.name != mine.name)
    check("...carrying the same IV total (%d)" % sum(mine.iv),
          sum(incoming.iv), sum(mine.iv))
    check("...spread differently", incoming.iv != mine.iv)
    check("...with its stats in step",
          incoming.nominal_base_stats,
          [b + i for b, i in zip(incoming.base_stats, incoming.iv)])
    check("...and a moveset it can use", len(incoming.moveset) > 1)

# the five strongest in the game are not stock
bosses = [name for name, mon in POKEMON.items()
          if str(getattr(mon, "tier", "")) == "Boss"]
check("there are Boss-tier Pokemon to protect", len(bosses) > 0)
for name in bosses:
    boss = build(name)
    check("  %s cannot be swapped" % name, shop.is_swappable(boss), False)
    check("  ...and the shop offers nothing for it",
          shop.swap_pokemon(boss), None)

# one already on the team is not offered back
held = build("Garchomp")
options = shop.swap_candidates(held, held=[o for o in POKEMON
                                           if shop.tier_of(POKEMON[o])
                                           == shop.tier_of(held)])
check("a shelf with everything already held offers nothing", options, [])


# ============================================================= in the career
print()
print("-- kept with the career, in one slot --")
room = tempfile.mkdtemp(prefix="coins-")
target = os.path.join(room, "savefile1.json")
try:
    player = list_of_competitors["Protagonist"]
    was = getattr(player, "coins", 0)
    player.coins = 17
    savefile.save(list_of_competitors, path=target)
    player.coins = 0
    savefile.load(list_of_competitors, POKEMON, path=target)
    check("coins survive a save and load", shop.balance(player), 17)

    # a save written before coins existed restores to none, which is also
    # what a new game has
    body = io.open(target, encoding="utf-8").read().replace('"coins": 17,',
                                                            '')
    io.open(target, "w", encoding="utf-8").write(body)
    player.coins = 99
    savefile.load(list_of_competitors, POKEMON, path=target)
    check("an older save restores to none", shop.balance(player), 0)
finally:
    player.coins = was
    shutil.rmtree(room, ignore_errors=True)

# Only the player is paid, and only in a real round. An AI-vs-AI battle has
# a competitor in the protagonist slot, whose coins nothing ever reads --
# paying them put a line into every simulated transcript and moved 13 of the
# 40 fingerprint battles for nothing.
import Scripts.Battle.battle_win_condition as WIN                # noqa: E402
guard = io.open("Scripts/Battle/battle_win_condition.py",
                encoding="utf-8").read()
check("the payout is gated on being the player",
      'getattr(protagonist, "main", False)' in guard)
check("...and on not being an exhibition",
      'getattr(battleground, "exhibition", False)' in guard)

check("the Shop is on the pre-battle menu",
      any(label == "Shop" for _v, _name, label in before_battle.MENU))
check("...and its handler exists",
      callable(getattr(before_battle, "visit_shop", None)))
check("the two purchases are priced",
      [(label, cost) for _v, label, cost, _b in shop.SHOP_ITEMS],
      [("Refresh Pokemon IVs", 2), ("Swap Pokemon (Same Tier)", 5)])


# =============================================================== on screen
print()
print("-- and the purse --")
from PySide6.QtWidgets import QApplication                       # noqa: E402
from GUI import bridge as B                                      # noqa: E402
B.Bridge.start = lambda self: None
from GUI_qt.fonts import Fonts                                   # noqa: E402
from GUI_qt.widgets import COIN_ART, CoinPurse                   # noqa: E402

app = QApplication.instance() or QApplication([])
fonts = Fonts()
coin = CoinPurse(fonts, ROOT)
check("the purse starts empty", coin.amount.text(), "0")
coin.set_coins(23)
check("...and shows what it is given", coin.amount.text(), "23")
coin.set_coins(-4)
check("...never a negative", coin.amount.text(), "0")
check("it has a picture", coin.icon.pixmap() is not None
      and not coin.icon.pixmap().isNull())
art = os.path.join(ROOT, *COIN_ART)
print("   (artwork at %s: %s)"
      % (os.path.join(*COIN_ART), "found" if os.path.exists(art)
         else "missing -- a drawn disc is used"))
# the drawn stand-in has to work too, since the asset may not be there
drawn = CoinPurse._drawn(44, 2.0)
check("the drawn stand-in is a real picture",
      not drawn.isNull() and drawn.width() == 44)


print()
print("-- and it costs the battle screen no height --")
# The fault: actions_height is a *budget*. __init__ works the arena's height
# out as whatever is left after the chrome and the action bar, so a row added
# to that bar pushed it past its share and over the arena. The purse takes
# its slice out of the scroller instead.
from GUI_qt.main_window import MainWindow                        # noqa: E402

win = MainWindow(ROOT)
win._timer.stop()
win.resize(1280, 800)
app.processEvents()
# An overlay, sharing the scroller's grid cell -- so the scroller keeps the
# whole budget (or the action screens clip: 43 of them did) and the bar does
# not grow past it (or it covers the arena).
check("the action scroller keeps the whole budget",
      win.actions_scroll.height(), win.actions_height)
check("...and the arena keeps the height it was sized to",
      win.stage_views.height(), win.arena_height)
check("the purse shares the scroller's cell rather than a row of its own",
      win.purse.parentWidget() is win.actions_scroll.parentWidget())
check("the purse is hidden before a career publishes one",
      win.purse.isHidden())
win._sync_purse(0)
check("...and shows even at zero once one does",
      (win.purse.isHidden(), win.purse.amount.text()), (False, "0"))
win._sync_purse(None)
check("...and a publish with nothing to say leaves it alone",
      win.purse.amount.text(), "0")

print()
print("-- the listing says what it is offering --")
plain = build("Garchomp", [20] * 6)
check("a Pokemon reads Name (IV xxx)",
      shop.describe_pokemon(plain), "Garchomp (IV 120)")
boss = build(bosses[0], [25] * 6)
check("...and one the shop refuses says so",
      shop.describe_pokemon(boss), "%s (IV 150) [Can't Swap]" % bosses[0])

print()
print("-- the balance the purse shows is the freshest one --")
# Two sources fed it: `spend` publishes the new figure at the top of the
# state, and the battle snapshot carries a copy inside player_side that is
# read when that snapshot is taken. The copy was applied second, so every
# purchase was overwritten by a stale number. That was the bug.
win._sync_purse(9)
check("a balance shows", win.purse.amount.text(), "9")
win._apply_state({"phase": "prebattle", "coins": 4, "player_roster": [],
                  "player_side": {"nickname": "You", "strength": 5,
                                  "coins": 9}})
app.processEvents()
check("...and a fresh top-level figure beats a stale copy",
      win.purse.amount.text(), "4")
win._apply_state({"phase": "prebattle", "player_roster": [],
                  "player_side": {"nickname": "You", "strength": 5,
                                  "coins": 11}})
app.processEvents()
check("...while the copy still fills in when there is no fresh figure",
      win.purse.amount.text(), "11")

print()
print("-- a long menu sets itself smaller rather than scrolling --")
# The slot lines carry a nickname, a rating, a run count and a title count,
# which does not fit three to a row at the body size.
slots = ("Which save?" + chr(10)
         + "1: Slot 1: Marvin (312) | Run: 7 | Title: 3" + chr(10)
         + "2: Slot 2: Challenger (58) | Run: 2 | Title: 0" + chr(10)
         + "3: Slot 3: empty" + chr(10)
         + "4: Slot 4: Marvuno (781) | Run: 41 | Title: 12" + chr(10)
         + "0: back" + chr(10) + "--> ")
prompt = win.memory.parse(slots, "")
win._clear_actions()
win._render_choices(prompt)
win._fit_actions()
app.processEvents()
check("the slot labels are longer than the dense threshold",
      max(len(c.label) for c in prompt.choices) > MainWindow.DENSE_LABEL)
check("...and the menu fits its viewport",
      win.actions_body.sizeHint().height()
      <= win.actions_scroll.viewport().height())
check("...with no scrollbar needed",
      win.actions_scroll.verticalScrollBar().maximum(), 0)

print()
print("-- and the slot line itself --")
check("a used slot reads Name (Rating) | Run | Title",
      savefile.describe({"used": True, "slot": 2, "nickname": "Marvin",
                         "rating": 312, "participation": 7,
                         "championship": 3}),
      "Slot 2: Marvin (312) | Run: 7 | Title: 3")
check("...and an empty one stays short",
      savefile.describe({"used": False, "slot": 3}), "Slot 3: empty")

print()
print("-- Custom Play names its two modes and nothing else --")
modes = io.open("Scripts/Game/start_interface.py", encoding="utf-8").read()
check("1 VS 1 is written plainly", '"  1: 1 VS 1"' in modes)
check("...and so is Metronome", '"  2: Metronome"' in modes)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
