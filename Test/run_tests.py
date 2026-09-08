"""Run the interface's test suites, with the save file protected.

    python Test/run_tests.py                 every suite
    python Test/run_tests.py pokedex swap    only suites whose name matches
    python Test/run_tests.py --list          just show what there is

Every suite runs headless (QT_QPA_PLATFORM=offscreen), so nothing opens a
window and nothing takes over the screen.

Why each suite is a subprocess rather than an import: several of them play
real games, and the engine saves into the project folder with no way to
redirect it. saveguard.py restores on the way out, which covers a clean exit
or an exception -- but not a native crash. A PySide6 access violation kills
the interpreter outright, atexit never runs, and whatever the harness saved
stays behind. A test run's career has shadowed the real one that way before.
Running each suite in its own process means this file can snapshot the saves
by hash beforehand and put them back afterwards however the process died.
"""
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SUITES = os.path.join(HERE, "gui")
#: harness output -- screenshots, reports, parked saves
OUT = os.path.join(SUITES, "_out")
#: Every career: the four slots, plus the two pre-slots locations at the root
#: that slot 1 was migrated from. A harness starting a new game now picks a
#: slot, so leaving Save/ out of this would let a test run write into the real
#: save -- which is exactly the accident this whole mechanism exists to stop.
#: ...and the files savefile._write_atomically leaves beside each of them.
#: A `.bak` holds the *previous* career, so a harness run that wrote one
#: would leave a test career sitting next to the real save, ready for
#: savefile.recover() to put back over it. A `.new` is only ever a save
#: interrupted mid-write, which is exactly what a killed suite produces.
_SAVE_SIDECARS = (".bak", ".new")
_SAVE_FILES = ("savefile.json", "savefile.dat") + tuple(
    os.path.join("Save", "savefile%d.json" % number)
    for number in range(1, 5))
SAVES = _SAVE_FILES + tuple(
    name + suffix for name in _SAVE_FILES for suffix in _SAVE_SIDECARS)
#: playthrough.py plays a whole run and wants a name for its player
EXTRA = {"playthrough": ["harness"]}


def _flat(name):
    """A save's path as a single filename, so Save/savefile1.json can be
    parked beside the others without needing a folder of its own."""
    return name.replace("\\", "-").replace("/", "-")


def _parked(name):
    return "PARKED-" + _flat(name)


def digest(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def snapshot():
    """Park a copy of each save, and remember what it hashed to."""
    marks = {}
    for name in SAVES:
        live = os.path.join(ROOT, name)
        marks[name] = digest(live)
        if marks[name] is not None:
            shutil.copy2(live, os.path.join(OUT, _parked(name)))
    return marks


def restore(marks):
    """Put the saves back exactly as they were. Returns what it had to fix."""
    fixed = []
    for name in SAVES:
        live = os.path.join(ROOT, name)
        parked = os.path.join(OUT, _parked(name))
        was, now = marks.get(name), digest(live)
        if was == now:
            continue
        if was is None:
            # the suite created a save where there was none: it is a test's
            # career, not the player's, so keep it out of the way but keep it
            if os.path.exists(live):
                shutil.move(live, os.path.join(OUT, "CREATED-"
                                          + _flat(name)))
            fixed.append("removed a created " + name)
        elif os.path.exists(parked):
            shutil.copy2(parked, live)
            fixed.append("restored " + name)
    return fixed


def verdict(text):
    """The one line of a suite's output that says how it went."""
    keep = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ("ALL PASS" in line or "FAILURES" in line or "MISMATCH" in line
                or line == "ok" or "failure" in line.lower()
                or line.startswith("Traceback")):
            keep = line
    return keep or "(no summary)"


def main(argv):
    picks = [a for a in argv[1:] if not a.startswith("-")]
    names = sorted(f[:-3] for f in os.listdir(SUITES)
                   if f.startswith("test_") and f.endswith(".py"))
    names.append("playthrough")            # last: it is much the slowest
    if picks:
        names = [n for n in names if any(p.lower() in n.lower() for p in picks)]
    if "--list" in argv:
        print("\n".join(names))
        return 0
    if not names:
        print("no suites matched %s" % " ".join(picks))
        return 1

    os.makedirs(OUT, exist_ok=True)
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONIOENCODING"] = "utf-8"
    # so the suites that guard the save can `import saveguard`
    environment["PYTHONPATH"] = (SUITES + os.pathsep
                                 + environment.get("PYTHONPATH", ""))

    failed, repaired = [], []
    for name in names:
        marks = snapshot()
        command = [sys.executable, os.path.join(SUITES, name + ".py"),
                   ROOT, OUT] + EXTRA.get(name, [])
        try:
            done = subprocess.run(command, cwd=ROOT, env=environment,
                                  capture_output=True, text=True,
                                  errors="replace", timeout=1800)
            output, code = (done.stdout or "") + (done.stderr or ""), \
                done.returncode
        except subprocess.TimeoutExpired:
            output, code = "timed out", 1
        fixed = restore(marks)
        repaired.extend("%s: %s" % (name, f) for f in fixed)
        line = verdict(output)
        # Some suites assert rather than print, and write their detail to a
        # file in _out/ instead of stdout. Silence plus exit 0 is a pass;
        # silence plus exit 1 means the detail is in that file, so say so
        # rather than leaving a bare "(no summary)" to be puzzled over.
        if line == "(no summary)":
            line = "ok" if code == 0 else "failed -- see %s/*.txt" % (
                os.path.basename(OUT))
        bad = code != 0 or "FAILURES" in line or line.startswith("Traceback")
        if bad:
            failed.append(name)
        print("%-24s %s" % (name, line))
        if bad:
            for tail in output.strip().splitlines()[-12:]:
                print("      | %s" % tail)

    print()
    if repaired:
        # not a failure: it means the guard did its job
        print("save file put back: %d time(s)" % len(repaired))
        for entry in repaired:
            print("  %s" % entry)
    print("%d suite(s), %d failed%s"
          % (len(names), len(failed),
             (": " + ", ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
