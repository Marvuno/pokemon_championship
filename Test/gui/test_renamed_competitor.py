"""Renaming a competitor must not throw away their history.

A save keys everything by competitor name -- each competitor's own record,
who the player has beaten, and every scoreline. `_apply_record` drops a name
the roster no longer has, which is right for somebody deleted and wrong for
somebody merely renamed: their whole head-to-head record would vanish, and
quietly, because a missing key looks exactly like a fresh slate.

`savefile.RENAMED` translates on the way in. Nothing rewrites the player's
save files, so this is undoable and costs nothing for saves that never knew
the old name.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                 # noqa: F401,E402
from Scripts.Data.competitors import list_of_competitors            # noqa: E402
from Scripts.Game import savefile                                   # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


print("-- every old name maps to somebody who exists --")
for old, new in sorted(savefile.RENAMED.items()):
    check("%s is now %s, and is on the roster" % (old, new),
          new in list_of_competitors)
    check("...and %s is not, or the map is pointless" % old,
          old not in list_of_competitors)
check("a name nobody renamed is left alone",
      savefile.current_name("Jason"), "Jason")

print()
print("-- an old save keeps its record --")


class Holder:
    pass


roster = list(list_of_competitors)
for old, new in sorted(savefile.RENAMED.items()):
    who = Holder()
    savefile._apply_record(who, roster, {
        old: {"wins": 4, "losses": 1, "scores": [[6, 2], [3, 6]]},
    })
    check("a %s record reads back under %s" % (old, new),
          who.opponent_history.get(new), [4, 1])
    check("...scorelines included",
          who.opponent_scores.get(new), [[6, 2], [3, 6]])
    check("...and the old key is not kept as well",
          old not in who.opponent_history)

# a competitor genuinely gone is still dropped, which is the behaviour the
# translation must not break
who = Holder()
savefile._apply_record(who, roster, {
    "Somebody Who Left": {"wins": 9, "losses": 9},
})
check("a competitor no longer on the roster is still dropped",
      "Somebody Who Left" in who.opponent_history, False)
check("...and everybody on the roster starts from a clean slate",
      {tuple(record) for record in who.opponent_history.values()},
      {(0, 0)})

print()
print("-- the competitor's own record, not just who they faced --")
data = {"player": {}, "competitors": {}}
for old in savefile.RENAMED:
    data["competitors"][old] = {"participation": 7, "championship": 2,
                                "history": {}, "opponents": {}}
savefile._load_json(data, list_of_competitors,
                    __import__("Scripts.Data.pokemon",
                               fromlist=["list_of_pokemon"]).list_of_pokemon)
for old, new in sorted(savefile.RENAMED.items()):
    person = list_of_competitors[new]
    check("%s's own run count survived the rename" % new,
          (person.participation, person.championship), (7, 2))

print()
print("-- nothing in the game still says the old name --")
looked = []
for folder in ("Scripts", "GUI", "GUI_qt", "Data", "Documentation"):
    for base, _, names in os.walk(folder):
        if "__pycache__" in base:
            continue
        for name in names:
            path = os.path.join(base, name)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for old in savefile.RENAMED:
                if old in text:
                    looked.append("%s (%s)" % (path.replace(os.sep, "/"), old))
# savefile.py is allowed to: it is the file that holds the map
looked = [hit for hit in looked if "savefile.py" not in hit]
check("no data file or module mentions a renamed competitor", looked, [])

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
