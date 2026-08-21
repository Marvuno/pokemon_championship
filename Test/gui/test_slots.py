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
os.makedirs(savefile.SLOT_DIR, exist_ok=True)

player = list_of_competitors["Protagonist"]
# Before anything is written or loaded, the way main_screen() does it -- the
# snapshot is only pristine if it is taken first.
savefile.remember_pristine(list_of_competitors, list_of_pokemon)


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

    # ------------------------------- a new game must not inherit a career
    # load() writes into the shared rosters in place, so opening HISTORY or
    # CONTINUE on one slot leaves that career in memory. A new game in another
    # slot used to save all of it -- runs, titles, championship history, head
    # to head -- under the new slot.
    write_slot(2, "Lady Evonne", 788, 13, 30)
    player.opponent_history["Pudding"] = [7, 2]
    savefile.save(list_of_competitors, slot=2)
    savefile.select(2)
    savefile.load(list_of_competitors, list_of_pokemon)
    check("the established career is in memory",
          (player.participation, player.championship), (30, 13))
    savefile.select(3)
    check("start_fresh reports success",
          savefile.start_fresh(list_of_competitors, list_of_pokemon), True)
    fresh_player = list_of_competitors["Protagonist"]
    fresh_player.nickname = "Fresh Start"
    savefile.save(list_of_competitors, slot=3)
    third = savefile.summary(3)
    check("a new career starts on zero runs", third["participation"], 0)
    check("...and zero titles", third["championship"], 0)
    check("...under its own name", third["nickname"], "Fresh Start")
    check("...while the slot it was read from is untouched",
          (savefile.summary(2)["nickname"],
           savefile.summary(2)["participation"]), ("Lady Evonne", 30))
    check("...and slot 4 is still free", savefile.summary(4)["used"], False)

    # The pickle format is gone: savefile.dat is not read, written or looked
    # for any more, so a stray one leaves slot 1 empty rather than occupied.
    os.remove(savefile.slot_path(1))
    os.remove(savefile.JSON_PATH)
    with open(os.path.join(sandbox, "savefile.dat"), "wb") as handle:
        handle.write(b"an old pickle nobody reads")
    check("an old pickle no longer counts as a career",
          savefile.exists(slot=1), False)
    check("...and the module has no legacy path at all",
          hasattr(savefile, "LEGACY_PATH"), False)
finally:
    shutil.rmtree(sandbox, ignore_errors=True)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
