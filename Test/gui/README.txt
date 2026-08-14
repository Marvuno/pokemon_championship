The interface's test suites
===========================

    python Test/run_tests.py                 every suite
    python Test/run_tests.py pokedex swap    only suites whose name matches
    python Test/run_tests.py --list          just show what there is

Everything runs headless -- QT_QPA_PLATFORM=offscreen -- so no window ever
opens and nothing takes over the screen while you are working.

These used to live in a scratch folder outside the project, which meant every
check written for the interface would have been lost the moment that folder
was cleaned. They are in the repo now.


What is here
------------
test_*.py            one suite each; see the docstring at the top of each
playthrough.py       plays a whole tournament through the window, answering
                     every prompt from the parsed prompt itself, and reports
                     battles seen, clipped screens and exceptions
saveguard.py         in-process save protection, imported by the suites that
                     play real games
probe_*.py           diagnostics rather than tests: they print measurements
                     (geometry, positions, weather, standings) instead of
                     passing or failing
measure_art.py       how often artwork is re-decoded, and what it costs
analyse.py           static sweep for dead code, duplication, no-op
                     expressions and over-long functions
diffhelpers.py       which of the AI's damage helpers still differ from the
                     engine's, and how
_out/                everything the harnesses write: reports, screenshots,
                     parked saves. Safe to delete.


The save file, and why this is careful about it
-----------------------------------------------
Several suites play real games, and the engine saves into the project folder
with no way to redirect it. So every save is snapshotted by hash before a
suite runs and put back afterwards:

  savefile.json, savefile.dat      the pre-slots pair at the root
  Save/savefile1..4.json           the four slots

Slot 1 matters most: a career from before there were slots is migrated there,
so it is where the real save lives. A harness that starts a new game picks a
slot like anyone else, which is exactly why Save/ is guarded too.

run_tests.py runs each suite as a *subprocess* rather than importing it. That
is not tidiness. saveguard.py restores on atexit, which covers a clean exit or
an exception -- but a PySide6 access violation kills the interpreter outright,
atexit never runs, and whatever the harness saved stays behind. A test run's
career has shadowed the real one that way before. A separate process means the
runner can put the saves back however the child died.

If the runner says "save file put back", that is the guard working, not a
failure.


Reading the output
------------------
Each suite prints one summary line: "ALL PASS", "N FAILURES: [...]", or "ok"
for the ones that only need to not raise. The runner echoes the last few lines
of anything that failed, and exits non-zero if any suite did.
