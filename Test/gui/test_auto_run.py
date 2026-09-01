"""AUTO RUN plays whole careers with nobody at the keyboard.

The thing worth testing is not the state machine -- that is four counters --
but whether the scripted answers actually carry a career from the first round
to the final scoreboard without the engine ever reaching a question nobody
answers. A prompt Auto Run does not recognise falls through to the real
`input`, which in a harness is EOF, so an unanswered screen shows up here as
a crash rather than as a hang.
"""
import io
import os
import random
import sys
from contextlib import redirect_stdout, suppress

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else ".")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Test", "gui"))
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

# This harness plays real games, and the engine saves with no way to redirect
# it. Must happen before the game modules are imported.
import saveguard                                                  # noqa: E402
saveguard.install(ROOT, OUT, tag="auto_run")

fails = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(what)


import main                                                       # noqa: E402
from Scripts.Art import music                                     # noqa: E402
from Scripts.Data.competitors import list_of_competitors          # noqa: E402
from Scripts.Game import auto_run                                 # noqa: E402
from Scripts.Game.game_system import GameSystem                   # noqa: E402

print("-- the scripted answers --")
auto_run.start()
check("the start menu is never answered",
      auto_run.answer("Your Option: "), None)
check("...nor the slot question",
      auto_run.answer("Which save slot? "), None)
check("pre-battle menu picks Battle",
      auto_run.answer("What do you want to do?"), "0")
check("the first move prompt turns auto battle on",
      auto_run.answer("What is the move for Pikachu?"),
      auto_run.AUTO_BATTLE_CODE)
check("...and the next one plays a real move",
      auto_run.answer("What is the move for Pikachu?"), auto_run.FIRST_MOVE)
check("a new battle re-arms it", auto_run.answer("What do you want to do?"), "0")
check("...so auto battle is switched on again",
      auto_run.answer("What is the move for Pikachu?"),
      auto_run.AUTO_BATTLE_CODE)
# The swap rule needs the two lists, and they are printed in the prompts that
# follow the Y/N rather than in it -- so it says Y to see them and backs out
# with 9 if the trade is not an improvement. Backing out re-asks the Y/N,
# which is why the refusal is remembered.
MINE = ("Choose the pokemon you don't want on your team, or 9 to go back:"
        + chr(10) + "[(0, 'Magikarp'), (1, 'Dragonite')]" + chr(10) + "--> ")
BETTER = ("Take the pokemon you want on the other team, or 9 to go back:"
          + chr(10) + "[(0, 'Garchomp'), (1, 'Sunkern')]" + chr(10) + "--> ")
WORSE = ("Take the pokemon you want on the other team, or 9 to go back:"
         + chr(10) + "[(0, 'Sunkern'), (1, 'Magikarp')]" + chr(10) + "--> ")
SWAP = "Input Y if you want to swap, and N otherwise. "

check("it says Y to see both teams", auto_run.answer(SWAP), "Y")
check("...offers up its worst (Magikarp)", auto_run.answer(MINE), "0")
check("...and takes their best when it beats it",
      auto_run.answer(BETTER), "0")
check("a second round starts clean", auto_run.answer(SWAP), "Y")
check("...offers its worst again", auto_run.answer(MINE), "0")
check("...but backs out when theirs is no better", auto_run.answer(WORSE), "9")
check("...and the re-asked question is declined", auto_run.answer(SWAP), "N")
# Two of a species cover the same matchups, so a Pokemon already on the books
# is skipped and the next best considered instead. The team here is set up
# above by the engine; these use whatever it holds.
from copy import deepcopy as _copy                                # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon as _pokemon      # noqa: E402
_me = list_of_competitors["Protagonist"]
_kept_team, _kept_unused = _me.team, getattr(_me, "unused_team", [])
_me.team = [_copy(_pokemon[n]) for n in ("Magikarp", "Garchomp", "Dragonite")]
_me.unused_team = []
DUPES = ("Take the pokemon you want on the other team, or 9 to go back:"
         + chr(10) + "[(0, 'Garchomp'), (1, 'Volcarona'), (2, 'Sunkern')]"
         + chr(10) + "--> ")
ALL_DUPES = ("Take the pokemon you want on the other team, or 9 to go back:"
             + chr(10) + "[(0, 'Garchomp'), (1, 'Dragonite')]"
             + chr(10) + "--> ")
MINE3 = ("Choose the pokemon you don't want on your team, or 9 to go back:"
         + chr(10) + "[(0, 'Magikarp'), (1, 'Garchomp'), (2, 'Dragonite')]"
         + chr(10) + "--> ")

check("a duplicate is skipped for the next best", (auto_run.answer(SWAP),
                                                   auto_run.answer(MINE3),
                                                   auto_run.answer(DUPES)),
      ("Y", "0", "1"))
check("...and every one being a duplicate backs out",
      (auto_run.answer(SWAP), auto_run.answer(MINE3),
       auto_run.answer(ALL_DUPES), auto_run.answer(SWAP)),
      ("Y", "0", "9", "N"))
_me.team, _me.unused_team = _kept_team, _kept_unused


def _rolled(name, iv):
    """A Pokemon with IVs on it, the way team_generation leaves one."""
    mon = _copy(_pokemon[name])
    mon.iv = [iv] * 6
    mon.total_iv = iv * 6
    mon.nominal_base_stats = [base + iv for base in mon.base_stats]
    mon.default_name = name
    return mon


# Ranked on nominal_base_stats -- base plus the IVs that individual rolled,
# the figures Fast Comparison shows -- not the species total, which ties two
# of a species however differently the two rolled. These two Garchomp are the
# case: identical on base stats, 174 apart once the rolls are counted.
_foe = list_of_competitors["Titan"]
_kept_foe = _foe.team
_me.team = [_rolled("Garchomp", 2), _rolled("Dragonite", 31)]
_me.unused_team = []
_foe.team = [_rolled("Sunkern", 31), _rolled("Garchomp", 31)]
SAME_SPECIES = ("Take the pokemon you want on the other team, or 9 to go back:"
                + chr(10) + "[(0, 'Sunkern'), (1, 'Garchomp')]"
                + chr(10) + "--> ")
MINE_2 = ("Choose the pokemon you don't want on your team, or 9 to go back:"
          + chr(10) + "[(0, 'Garchomp'), (1, 'Dragonite')]" + chr(10) + "--> ")

check("the opponent's real Pokemon are found behind the printed list",
      [sum(m.nominal_base_stats) for m in auto_run._their_team(SAME_SPECIES)],
      [366, 786])
check("a better-rolled copy of one you own is still an upgrade",
      (auto_run.answer(SWAP), auto_run.answer(MINE_2),
       auto_run.answer(SAME_SPECIES)), ("Y", "0", "1"))
_foe.team = _kept_foe
_me.team, _me.unused_team = _kept_team, _kept_unused

check("a free slot is always filled",
      auto_run.answer("Input Y if you want to take from the opponent, and N "
                      "to get a random pokemon from the organizer. "), "Y")
check("...with the best one offered",
      auto_run.answer("You may take one pokemon from the opponent, or 9 to "
                      "go back:" + chr(10) + "[(0, 'Sunkern'), (1, 'Garchomp')]"
                      + chr(10) + "--> "), "1")
# Benching for a short round takes the weakest, not a random pick -- rounds
# one and two are the ones that ask, and giving up the best Pokemon there
# throws the run away. IVs settle a tie between two of the same species, and
# only a true tie is drawn for.
def _mon(name, iv):
    mon = _copy(_pokemon[name])
    mon.iv = [iv] * 6
    mon.total_iv = iv * 6
    mon.nominal_base_stats = [base + iv for base in mon.base_stats]
    return mon


BENCH = "Select the Pokemon you DO NOT need this round: "
_me.team = [_mon("Garchomp", 31), _mon("Magikarp", 31),
            _mon("Dragonite", 31), _mon("Sunkern", 31)]
# Sunkern (366) then Magikarp (386) are the two weakest and their order is
# fixed. Garchomp and Dragonite are both 600 base and both rolled 31, so they
# tie exactly -- asserting an order between them would be asserting the
# shuffle, and it passed by luck until it did not.
_benched = [auto_run.answer(BENCH) for _ in range(4)]
check("the two weakest are benched first, in order", _benched[:2], ["3", "1"])
check("...and the two that tie exactly come last, either way round",
      sorted(_benched[2:]), ["0", "2"])

auto_run.answer("What do you want to do?")          # a new round forgets it
_me.team = [_mon("Garchomp", 31), _mon("Garchomp", 5), _mon("Garchomp", 18)]
check("...with IVs settling a tie between the same species",
      [auto_run.answer(BENCH) for _ in range(3)], ["1", "2", "0"])

# The engine asks until it has enough *distinct* indices, so repeating an
# answer would leave it asking forever.
auto_run.answer("What do you want to do?")
_me.team = [_mon("Magikarp", 31) for _ in range(4)]
check("four asks give four different Pokemon, never a repeat",
      sorted(auto_run.answer(BENCH) for _ in range(4)), ["0", "1", "2", "3"])

_spread = set()
for _round in range(30):
    auto_run.answer("What do you want to do?")
    _spread.add(auto_run.answer(BENCH))
check("...and an all-identical team is drawn for, not always slot 0",
      len(_spread) > 1, True)
_me.team, _me.unused_team = _kept_team, _kept_unused
auto_run.answer("What do you want to do?")          # leave no round half-done

check("every pause is a bare Enter",
      auto_run.answer("Press any key to continue."), "")
check("the batting order is left alone",
      auto_run.answer("Which pokemon would you like to swap to be the first?"),
      "9")
check("it is silent while running", music._SILENCED, True)
auto_run.stop()
check("...and audible again afterwards", music._SILENCED, False)

print()
print("-- the run counter --")
auto_run.start(3)
check("three careers asked for", (auto_run.state.total, auto_run.remaining()),
      (3, 3))
check("after the first, another is owed", auto_run.finished_one(), True)
check("...and after the second", auto_run.finished_one(), True)
check("...but not after the third", auto_run.finished_one(), False)
check("a request over the cap is clamped", (auto_run.start(999) or
                                            auto_run.state.total),
      auto_run.MAX_RUNS)
check("...and one under it is floored", (auto_run.start(0) or
                                         auto_run.state.total), 1)
auto_run.stop()
check("the window is left unattended until the player is asked",
      auto_run.unattended(), True)
auto_run.settled()
check("...and hands back once they are", auto_run.unattended(), False)

print()
print("-- input is wrapped in front of whatever was there, then put back --")
import builtins                                                   # noqa: E402
before = builtins.input
auto_run.start()
check("input was replaced", builtins.input is not before, True)
check("...and the original kept", auto_run.state.previous is before, True)
check("an unknown prompt falls through",
      auto_run.answer("Something nobody scripted"), None)
auto_run.stop()
check("...and restored on stop", builtins.input is before, True)

print()
print("-- a designed team survives one career and starts the next --")
# `team_generation` writes the Pokemon it builds back into `participant.team`,
# and `round_begin` trims that list for a short round -- so a competitor who
# has been fought once carries built Pokemon from then on, reordered and cut,
# instead of the Ace specs the CSV describes. One career meant one process, so
# `restart()` used to undo it; an Auto Run playing several in one cannot.
from Scripts.Data.pokemon import list_of_pokemon as _all_pokemon  # noqa: E402
from Scripts.Game import savefile as _savefile                    # noqa: E402
from Scripts.Data.competitors import Ace as _Ace                  # noqa: E402
_savefile.remember_pristine(list_of_competitors, _all_pokemon)

_designed = list_of_competitors["Champion Marvin"]
_as_shipped = [getattr(a, "name", a) for a in (_designed.team or [])]
check("Champion Marvin ships with Ace specs, not built Pokemon",
      all(isinstance(entry, _Ace) for entry in (_designed.team or [])), True)

# whatever a career leaves behind...
_designed.team = [_copy(_pokemon["Magikarp"])]
check("...and a career can leave him holding something else",
      [getattr(a, "name", a) for a in _designed.team], ["Magikarp"])

# ...the next one starts from the CSV again
_savefile.restore_designed_teams(list_of_competitors)
check("...but the next career restores what the CSV says",
      [getattr(a, "name", a) for a in (_designed.team or [])], _as_shipped)
check("...as Ace specs, so IVs and moves are rolled fresh",
      all(isinstance(entry, _Ace) for entry in (_designed.team or [])), True)
check("...and the player's own team is left alone",
      list_of_competitors["Protagonist"].team is _kept_team
      or _kept_team is None, True)
print()
print("-- the countdown in the top bar --")
# Four earlier shapes were all lost behind something: a caption in the action
# bar at the bottom, a caption squeezed among the top bar's buttons, a child
# widget raised on every publish, and a window of its own. The bar itself is
# always on screen and never drawn over -- so during a run its buttons go and
# the countdown takes their place. Nobody reaches for Settings in the middle
# of a hundred unattended careers.
from PySide6.QtWidgets import QApplication as _QApp                # noqa: E402
from GUI_qt.main_window import MainWindow as _MW                   # noqa: E402
_app = _QApp.instance() or _QApp([])
_w = _MW(ROOT)
_w.bridge.stop()
# The bridge redirects builtins.print into its event queue and a stopped one
# raises Shutdown from it, so this suite's own results have to go back to the
# real print. The 20ms pump has to stop too, or it drains the dead bridge and
# pushes an empty state over the one being fed by hand.
import builtins as _builtins                                       # noqa: E402
_builtins.print = _w.bridge._real_print
_w._timer.stop()
_w.show()
_state = {"phase": "battle", "field": {},
          "player": {"nickname": "You", "name": "P", "hp": 80, "max_hp": 100,
                     "types": ["Electric"], "status": "Normal",
                     "fainted": False},
          "opponent": {"nickname": "T", "name": "G", "hp": 90, "max_hp": 120,
                       "types": ["Dragon"], "status": "Normal",
                       "fainted": False}}
_w._apply_state(_state)
_app.processEvents()
auto_run.start(10)
_w._apply_state(_state)
_app.processEvents()

# Nothing may barge in over an unattended run. The end of every
# career publishes a leaderboard, and that used to open the Standings window.
_busy = dict(_state)
_busy["leaderboard"] = [{"nickname": "somebody"}]
_w._apply_state(_busy)
_app.processEvents()
check("the standings stay shut during a run",
      _w.standings_dialog.isVisible(), False)

auto_run.stop()
_w._apply_state(_state)
_app.processEvents()
auto_run.settled()          # what _show_request does when the player is asked
_busy2 = dict(_state)
_busy2["leaderboard"] = [{"nickname": "another"}]
_w._apply_state(_busy2)
_app.processEvents()
check("...and the standings open again for a person",
      _w.standings_dialog.isVisible(), True)
_w.standings_dialog.hide()



print("-- a whole career, unattended --")
# Two runs, so the loop that plays a second one is exercised rather than
# just the first. GameSystem.stage is what ends a career.
random.seed(20)
protagonist = list_of_competitors["Protagonist"]
# The bracket is what a career is played on, and `main_screen` draws it after
# the menu. Auto Run reaches it the same way; here it is called directly
# because the menu itself is not what this is testing.
from Scripts.Game.start_interface import draw_bracket          # noqa: E402
with redirect_stdout(io.StringIO()):
    draw_bracket()
check("a bracket of 32 was drawn", len(GameSystem.participants), 32)

crash = ""
rounds = 0
finished = 0
auto_run.start()
try:
    with redirect_stdout(io.StringIO()):
        main.play_career()
    # What "played rounds" means: the career reached the end of the bracket
    # and every match was recorded. `protagonist.stage` was read here before
    # and only counts *wins* -- so a seed where the player loses all five
    # failed a check about whether the rounds happened at all. Which seed
    # wins is a property of the ratings, and those move.
    rounds = len([r for r in (getattr(protagonist, "win_order", None) or [])])
    finished = GameSystem.stage
except Exception as error:
    import traceback
    crash = traceback.format_exc()[-500:]
finally:
    auto_run.stop()

check("a career ran to the end with nothing left unanswered", crash, "")
if crash:
    print(crash)
check("...and it actually played rounds (%d)" % rounds, rounds >= 5, True)
check("...reaching the end of the bracket", finished, 6)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
