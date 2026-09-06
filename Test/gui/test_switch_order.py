"""A switch is announced when it happens, not when the state is next read.

Switching outranks every move in this game -- it resolves first in the turn --
so the feed has to show it first. It did not, and the reason was structural
rather than a slip: the window found switches by comparing the published state
against what it saw last time, and a publish only happens once the turn's work
is done. The line therefore arrived after the move banner, and often after the
next turn's divider: a Pokemon sent out at the top of turn 3 was drawn beneath
the TURN 4 rule, having already visibly taken damage during turn 3.

`switching_mechanism` is wrapped now, so the switch goes through the same
queue as the move that follows it and lands in the order it happened.

What this checks, and what it deliberately does not: the composition -- feed
order in a running window -- needs the bridge owning stdout and a real career,
which is `playthrough`'s job. What is pinned here is the three things that
compose: the engine's switch is what announces, the window no longer invents a
second late line, and the arena callout is raised from the banner rather than
from a state diff.

    python Test/gui/test_switch_order.py <root> <out>
"""
import inspect
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_out")
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

# install_hooks imports `main`, which loads every game module, and anything
# that loads the game can write into the project folder. See saveguard.py.
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, OUT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import saveguard                                                      # noqa
saveguard.install(ROOT, OUT, tag="test_switch_order")

fails = []


def check(label, got, want):
    ok = got == want
    print("%-58s %s%s" % (label, "PASS" if ok else "FAIL",
                          "" if ok else "  got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(label)


# ------------------------------------------- 1. the engine's switch announces
print("-- the switch itself is what announces --")
from GUI import bridge as B                                           # noqa
import Scripts.Battle.battle_cycle as cycle                           # noqa
import Scripts.Battle.switching as switching                          # noqa

before = switching.switching_mechanism
bridge = B.Bridge(ROOT)
import main as game_main                                              # noqa
B.install_hooks(bridge, game_main)

check("switching_mechanism is wrapped",
      switching.switching_mechanism is not before, True)
# patch_everywhere exists because Scripts/ is full of `from x import *`:
# rebinding it in its home module alone would leave every caller on the
# original, which is the trap this whole codebase is shaped around.
check("...and the rebinding reached battle_cycle too",
      cycle.switching_mechanism is switching.switching_mechanism, True)
check("...and it emits a switch banner",
      "emit_banner" in inspect.getsource(switching.switching_mechanism)
      and '"switch"' in inspect.getsource(switching.switching_mechanism),
      True)

# ------------------------------------- 2. the window invents no second line
print("")
print("-- and the window does not add a late one of its own --")
from GUI_qt.main_window import MainWindow                             # noqa

# `_announce_switches` is the state-diff path -- `_sync_field` calls it once
# it has worked out which sides changed. It is not silenced outright, because
# two arrivals never reach a banner: the opening send-out, which is not a
# switch and never goes through switching_mechanism, and anything driving the
# window with no bridge attached. It defers instead.
sync = inspect.getsource(MainWindow._announce_switches)
check("the state-diff path defers to what the engine already said",
      "_announced_switch" in sync, True)
check("...and only announces when nobody has", "if not already:" in sync,
      True)
check("...but always flashes the card, which is a picture not a record",
      "flash_switch()" in sync, True)

banner_src = inspect.getsource(MainWindow._show_banner)
check("the banner is what claims the arrival",
      "_announced_switch.add" in banner_src, True)

# The claim only holds if the record is emptied per match, or a Pokemon that
# came in during match one is silently skipped in match two.
check("the record is cleared between matches",
      "_announced_switch = set()" in inspect.getsource(MainWindow._clear_feed),
      True)

# --------------------------------------- 3. the arena callout follows suit
print("")
print("-- the on-field callout is raised from the banner --")
banner = inspect.getsource(MainWindow._show_banner)
check("a switch banner raises the arena beat",
      'kind == "switch"' in banner and "_beat" in banner, True)
check("...tagged as a switch rather than as an ability",
      'tag="SWITCH"' in banner, True)

flare = inspect.getsource(MainWindow._beat)
check("the beat takes its own tag", "tag" in flare, True)

print("")
print("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(fails))
sys.exit(1 if fails else 0)
