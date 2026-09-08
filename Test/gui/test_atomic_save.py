"""A save is written whole or not at all.

`open(path, "w")` truncates the file before writing a byte of the 2.5MB that
replaces it, so anything interrupting the write destroyed the career -- the
one failure in this game a player cannot undo. This checks the file is built
beside the real one and renamed over it, that the previous one is kept, and
that a write which dies partway leaves the old save exactly as it was.

Everything here writes to a temp directory via save(path=...), so no real
save is touched whatever happens.
"""
import io
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from Scripts.Data.competitors import list_of_competitors          # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                  # noqa: E402
from Scripts.Game import savefile                                 # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-62s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


room = tempfile.mkdtemp(prefix="atomic-save-")
target = os.path.join(room, "savefile1.json")


def body(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


try:
    # ------------------------------------------------------ an ordinary save
    savefile.save(list_of_competitors, path=target)
    check("the save is written", os.path.exists(target))
    first = body(target)
    check("...and is complete JSON", first.rstrip().endswith("}"))
    check("...leaving no half-written file behind",
          os.path.exists(target + savefile.PENDING_SUFFIX), False)
    check("...and no backup yet, there being nothing to back up",
          savefile.backup_of(target), "")

    # ------------------------------------------------- the second save keeps
    player = list_of_competitors["Protagonist"]
    player.nickname = "Second"
    savefile.save(list_of_competitors, path=target)
    check("a second save keeps the first beside it",
          bool(savefile.backup_of(target)))
    check("...and the backup is the one that was there before",
          body(target + savefile.BACKUP_SUFFIX), first)
    check("...while the save itself moved on",
          body(target) != first)
    second = body(target)

    # ----------------------------------------- a write that dies partway
    #
    # The whole point. os.replace is the last step, so making it fail is the
    # closest thing to the process being killed mid-save.
    intact = body(target)
    real_replace = os.replace
    calls = {"n": 0}

    def failing_replace(src, dst):
        # let the backup rename through, break the one that matters
        calls["n"] += 1
        if str(dst) == str(target):
            raise OSError("interrupted")
        return real_replace(src, dst)

    player.nickname = "Third"
    os.replace = failing_replace
    try:
        savefile.save(list_of_competitors, path=target)
    except OSError:
        pass
    finally:
        os.replace = real_replace
    check("a failed write raised rather than passed silently", calls["n"] > 0)
    check("...and the save on disk is untouched", body(target), intact)

    # and the same for a failure before the rename
    for pending in (target + savefile.PENDING_SUFFIX,):
        if os.path.exists(pending):
            os.remove(pending)
    real_fsync = os.fsync

    def failing_fsync(fd):
        raise OSError("no room")

    os.fsync = failing_fsync
    try:
        savefile.save(list_of_competitors, path=target)
    except OSError:
        pass
    finally:
        os.fsync = real_fsync
    check("a failure before the rename leaves the save alone",
          body(target), intact)

    # -------------------------------------------------------- putting it back
    # The backup is the *previous* save, not the first one ever written --
    # every successful save refreshes it, and so does an attempt that fails
    # at the rename (the copy happens before it). After the sequence above
    # that is the "Second" career.
    check("the backup can be restored", savefile.recover(path=target))
    check("...and the save is the previous career again", body(target),
          second)
    check("...restoring is itself written whole",
          os.path.exists(target + savefile.PENDING_SUFFIX), False)

    # a slot with no backup says so rather than raising
    lonely = os.path.join(room, "savefile2.json")
    savefile.save(list_of_competitors, path=lonely)
    check("nothing to recover is answered, not raised",
          savefile.recover(path=lonely), False)
    check("...and the save is still there", os.path.exists(lonely))

    # ------------------------------------- what the test runner has to guard
    sys.path.insert(0, os.path.join(ROOT, "Test"))
    import run_tests                                              # noqa: E402
    guarded = set(run_tests.SAVES)
    wanted = [os.path.join("Save", "savefile1.json") + savefile.BACKUP_SUFFIX,
              os.path.join("Save", "savefile1.json") + savefile.PENDING_SUFFIX]
    for name in wanted:
        # A harness that writes a save now leaves a .bak holding a *test*
        # career next to the real one, which recover() would happily put
        # back. The runner has to park those with everything else.
        check("the runner guards %s" % name, name in guarded)
finally:
    shutil.rmtree(room, ignore_errors=True)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
