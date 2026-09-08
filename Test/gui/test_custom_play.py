"""Custom Play, driven headlessly.

Three things worth checking, and only the first is about it working at all:

    the teams     are built to the opponent's recipe -- a competitor who pins
                  six means both sides field those six, and one who pins two
                  means both sides hold those two with four rolled around them
    the battle    actually runs to a result from the menu option, with no save
                  loaded and no bracket drawn
    the roster    is untouched afterwards. team_generation writes built Pokemon
                  over the pinned Ace specifications, so the whole mode is
                  worthless if it consumes the designed teams on the way past

Answers the player's prompts from a script, the way Auto Run does, so nothing
waits on a keypress.

    python Test/gui/test_custom_play.py <root> <out>
"""
import builtins
import io
import os
import random
import sys
from contextlib import redirect_stdout, suppress

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                     # noqa
from Scripts.Data.competitors import Ace                               # noqa
from Scripts.Data.competitors import list_of_competitors as L          # noqa
from Scripts.Game import start_interface as SI                         # noqa
from Scripts.Game.game_system import GameSystem                        # noqa

out = sys.__stdout__
fails = []


def check(label, got, want):
    ok = got == want
    print("%-58s %s%s" % (label, "PASS" if ok else "FAIL",
                          "" if ok else "  got=%r want=%r" % (got, want)),
          file=out)
    if not ok:
        fails.append(label)


def pinned(name):
    """How many Pokemon this competitor designs, as the CSV writes them."""
    return len([e for e in L[name].team if isinstance(e, (str, Ace))])


# ------------------------------------------------------- team construction
print("-- the teams are built to the opponent's recipe --", file=out)
for who in ("Reaper Conan", "Magnus Carlsen", "Goblin"):
    random.seed(4242)
    with redirect_stdout(io.StringIO()):
        player, opponent = SI.custom_teams(who)
    designed = pinned(who)
    check("%s: both sides field six" % who,
          (len(player.team), len(opponent.team)), (6, 6))
    check("...player is dealt in at their rating",
          player.strength, L[who].strength)
    # the pinned species have to appear on both sides; team_generation puts
    # the aces last, which is why this reads the tail rather than searching
    theirs = [p.name for p in opponent.team][-designed:] if designed else []
    mine = [p.name for p in player.team][-designed:] if designed else []
    check("...and both hold the %d designed Pokemon" % designed, mine, theirs)

# a competitor who designs a whole team means the two teams match outright
random.seed(11)
with redirect_stdout(io.StringIO()):
    player, opponent = SI.custom_teams("Reaper Conan")
check("Conan pins six, so the teams are the same six",
      sorted(p.name for p in player.team),
      sorted(p.name for p in opponent.team))

# one who designs two does not
random.seed(11)
with redirect_stdout(io.StringIO()):
    player, opponent = SI.custom_teams("Magnus Carlsen")
same = sorted(p.name for p in player.team) == sorted(p.name
                                                     for p in opponent.team)
check("Magnus pins two, so the rest is rolled apart", same, False)

# ------------------------------------------------------- the roster survives
print("", file=out)
print("-- the roster is not consumed --", file=out)
for who in ("Reaper Conan", "Magnus Carlsen"):
    check("%s still has %d Ace specifications" % (who, pinned(who)),
          all(isinstance(e, (str, Ace)) for e in L[who].team), True)

# ------------------------------------------------------- end to end
print("", file=out)
print("-- one battle, from the menu option --", file=out)
GameSystem.stage = 1
# what the career owns, so the mode can be checked for leaving it alone
before_stage = GameSystem.stage
before_field = list(GameSystem.participants)
before_team = list(L['Protagonist'].team)
before_rating = L['Protagonist'].strength

# `input` is patched on builtins, not on start_interface: a battle's prompts
# come from four different modules and a name bound in one of them shadows
# nothing in the others -- which is what left the first version of this
# harness hanging on a forced switch it never saw.
#
# Custom Play asks which game mode first, then who to fight -- so "1" is
# 1 vs 1 and the second "1" is the first competitor on the list. "N" declines
# another battle.
#
# Capped, so a prompt this does not anticipate fails the run in a second
# instead of blocking it forever.
script = ["1", "1", "N"] + ["0"] * 400
asked = []
real_input = builtins.input


def scripted(prompt=""):
    asked.append(str(prompt))
    if len(asked) > len(script):
        raise RuntimeError("unanswered prompt #%d: %r" % (len(asked), prompt))
    return script[len(asked) - 1]


# The player's own moves go to the auto-battle AI, so the script only has to
# cover the menu. custom_play builds its own Battleground, so the flag is set
# by wrapping the class in that module's namespace.
class AutoGround(SI.Battleground):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.auto_battle = True


log = io.StringIO()
SI.Battleground = AutoGround
builtins.input = scripted
try:
    with redirect_stdout(log):
        with suppress(RecursionError, SystemExit):
            SI.custom_play()
finally:
    builtins.input = real_input
text = log.getvalue()

check("a battle was played", " VS " in text, True)
check("...at six a side", "6vs6" in text, True)
check("...and reached a knockout", "fainted" in text.lower(), True)
check("...and the player was named", "Challenger" in text or bool(
    L['Protagonist'].nickname), True)

print("", file=out)
print("-- and the Metronome mode --", file=out)
# Mode 2 needs no opponent chosen: it deals six Gamblers to each side and
# starts. Same script shape, one answer shorter.
asked[:] = []
script[:] = ["2", "N"] + ["0"] * 400
log2 = io.StringIO()
builtins.input = scripted
try:
    with redirect_stdout(log2):
        with suppress(RecursionError, SystemExit):
            SI.custom_play()
finally:
    builtins.input = real_input
metro = log2.getvalue()

check("a Metronome battle was played", " VS " in metro, True)
check("...six a side", "6vs6" in metro, True)
check("...against the house", "The House" in metro, True)
check("...with Gamblers on the field", "Gambler" in metro, True)
# No caption for the mode: the name says it, and a second line under every
# screen was more to read than the choice needed.
check("...and no quote is put in the mode's mouth",
      "\"" not in metro.split(" VS ")[-1][:200], True)
check("...and it reached a knockout", "fainted" in metro.lower(), True)

print("", file=out)
print("-- and the career is left exactly as it was --", file=out)
# The mode borrows GameSystem.stage for ROUND_LIMIT and it is a class
# attribute shared with the career, so a run resumed afterwards would
# otherwise start at whatever round Custom Play used.
check("GameSystem.stage is put back", GameSystem.stage, before_stage)
check("the seeded field is untouched", list(GameSystem.participants),
      before_field)
check("the player's own team is untouched",
      list(L['Protagonist'].team), before_team)
check("the player's own rating is untouched",
      L['Protagonist'].strength, before_rating)

print("", file=out)
print("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(fails), file=out)
sys.exit(1 if fails else 0)
