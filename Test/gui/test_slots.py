"""Four save slots: reading, writing, listing, and the migration of a
career from before there were slots.

Every path here is redirected into a temporary folder, so this suite never
touches a real save.
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from Scripts.Data.competitors import list_of_competitors        # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon               # noqa: E402
from Scripts.Game import savefile                              # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


# ------------------------------------------------------------- sandbox
sandbox = tempfile.mkdtemp(prefix="slots-")
savefile.SLOT_DIR = os.path.join(sandbox, "Save")
savefile.JSON_PATH = os.path.join(sandbox, "savefile.json")
savefile.LEGACY_PATH = os.path.join(sandbox, "savefile.dat")
os.makedirs(savefile.SLOT_DIR, exist_ok=True)

player = list_of_competitors["Protagonist"]


def write_slot(slot, nickname, rating, titles, runs):
    player.nickname = nickname
    player.strength = rating
    player.championship = titles
    player.participation = runs
    return savefile.save(list_of_competitors, slot=slot)


try:
    check("there are four slots", savefile.SLOTS, 4)
    check("all four start empty",
          [e["used"] for e in savefile.slots()], [False] * 4)
    check("...so nothing can be continued", savefile.any_exists(), False)

    # ------------------------------------------------- writing and reading
    path = write_slot(2, "Marvin", 415, 10, 36)
    check("a slot writes where it says it does",
          os.path.abspath(path), os.path.abspath(savefile.slot_path(2)))
    check("...and only that slot fills up",
          [e["used"] for e in savefile.slots()], [False, True, False, False])
    two = savefile.summary(2)
    check("its summary reads back the career",
          (two["nickname"], two["rating"], two["championship"],
           two["participation"]), ("Marvin", 415, 10, 36))
    check("...and describes itself for the menu",
          "Marvin" in savefile.describe(two)
          and "Slot 2" in savefile.describe(two))
    check("an empty slot says so",
          savefile.describe(savefile.summary(3)), "Slot 3: empty")

    # four separate careers, not one shared one
    write_slot(1, "Evonne", 300, 2, 9)
    write_slot(3, "Guest", 5, 0, 1)
    write_slot(4, "Fourth", 88, 1, 4)
    check("four careers coexist",
          [savefile.summary(n)["nickname"] for n in (1, 2, 3, 4)],
          ["Evonne", "Marvin", "Guest", "Fourth"])
    check("...all four reported as used", savefile.any_exists(), True)

    # ------------------------------------------------------ select() sticks
    savefile.select(3)
    check("select() picks the working slot", savefile.current(), 3)
    player.nickname = "Renamed"
    savefile.save(list_of_competitors)          # no slot given
    check("a save with no slot goes to the selected one",
          savefile.summary(3)["nickname"], "Renamed")
    check("...and leaves the others alone",
          [savefile.summary(n)["nickname"] for n in (1, 2, 4)],
          ["Evonne", "Marvin", "Fourth"])
    check("out-of-range slots are clamped, not crashed",
          (savefile.select(9), savefile.select(0)), (4, 1))

    # ------------------------------------------------------------- loading
    savefile.select(2)
    check("loading the slot reports the format",
          savefile.load(list_of_competitors, list_of_pokemon), "json")
    check("...and restores that career's name", player.nickname, "Marvin")
    check("exists() is per slot",
          [savefile.exists(slot=n) for n in (1, 2, 3, 4)], [True] * 4)

    # ------------------------------------------------------ damaged slot
    with open(savefile.slot_path(4), "w", encoding="utf-8") as handle:
        handle.write("{ this is not json")
    check("an unreadable slot is reported, not raised",
          savefile.summary(4).get("damaged"), True)
    check("...and the menu still has a line for it",
          savefile.describe(savefile.summary(4)), "Slot 4: unreadable")

    # ------------------------------------ migrating a pre-slots career
    for number in range(1, 5):
        os.remove(savefile.slot_path(number))
    payload = {"version": 1,
               "player": {"nickname": "Older", "rating": 481,
                          "participation": 40, "championship": 11,
                          "team": [], "history": {}, "opponents": {}},
               "competitors": {}}
    with open(savefile.JSON_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    check("a pre-slots save is offered as slot 1 before migrating",
          savefile.summary(1)["nickname"], "Older")
    check("...and slot 1 counts as existing", savefile.exists(slot=1), True)
    check("...while the others do not",
          [savefile.exists(slot=n) for n in (2, 3, 4)], [False] * 3)
    check("migration happens", savefile.adopt_single_save(), True)
    check("...putting the career in slot 1",
          savefile.summary(1)["nickname"], "Older")
    check("...by copy, leaving the original where it was",
          os.path.exists(savefile.JSON_PATH), True)
    original = json.load(io_open := open(savefile.JSON_PATH, encoding="utf-8"))
    io_open.close()
    check("...byte-for-byte the same career",
          original["player"]["participation"], 40)
    check("migrating twice does nothing the second time",
          savefile.adopt_single_save(), False)
    savefile.select(1)
    check("and it loads from the slot now",
          savefile.load(list_of_competitors, list_of_pokemon), "json")
    check("...as the same career", player.nickname, "Older")

    # a pre-slots pickle also keeps slot 1 occupied
    os.remove(savefile.slot_path(1))
    os.remove(savefile.JSON_PATH)
    with open(savefile.LEGACY_PATH, "wb") as handle:
        handle.write(b"not really a pickle")
    check("an old pickle still makes slot 1 look occupied",
          savefile.exists(slot=1), True)
finally:
    shutil.rmtree(sandbox, ignore_errors=True)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
