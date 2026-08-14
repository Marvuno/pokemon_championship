"""Protect the player's save from a test harness that plays real games.

Every harness that starts or continues a game must call install(ROOT, OUT)
before Qt or the game modules are imported. It snapshots savefile.dat and
savefile.json byte-for-byte and puts exactly that snapshot back on the way
out, whatever happened in between.

Written after a harness left its own savefile.json in the project: the old
guard only knew about savefile.dat, and because load() prefers JSON the game
would have booted into a test career ("X", rating 6) instead of the real one.

Two rules the previous version got wrong:

  * a file the run created is *moved aside*, never deleted -- if it turns out
    to matter, it is still there
  * the restore verifies itself by hash and shouts on stderr if it failed,
    rather than assuming a copy2 worked
"""

import atexit
import hashlib
import os
import shutil
import sys
import time

# Every career, not just the pre-slots pair at the root. A harness that
# starts a new game now picks a slot, and slot 1 is where a career from
# before slots was migrated to -- so leaving Save/ unguarded would put a
# test run straight into the real save.
FILES = ("savefile.dat", "savefile.json") + tuple(
    "Save/savefile%d.json" % number for number in range(1, 5))


def _digest(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _flat(name):
    """A save's path as one filename. The slots live in Save/, and parking
    "Save/savefile1.json" under a name that still has the separator in it
    asks for a folder that is not there -- which is how this failed the first
    time the slots were added to FILES."""
    return name.replace(chr(92), "-").replace("/", "-")


def install(root, out, tag="guard"):
    """Snapshot the saves and register the restore. Returns the snapshot."""
    snapshot = {}
    for name in FILES:
        live = os.path.join(root, name)
        digest = _digest(live)
        park = None
        if digest is not None:
            park = os.path.join(out, "GUARD-%s-%s" % (tag, _flat(name)))
            shutil.copy2(live, park)
        snapshot[name] = (live, park, digest)

    def restore():
        for name, (live, park, digest) in snapshot.items():
            try:
                if park is not None:
                    shutil.copy2(park, live)
                elif os.path.exists(live):
                    # the run created this one; keep it, out of the way
                    shutil.move(live, os.path.join(
                        out, "CREATED-%s-%d-%s" % (tag, int(time.time()),
                                                   _flat(name))))
                after = _digest(live)
                if after != digest:
                    sys.stderr.write(
                        "SAVE GUARD FAILED for %s: expected %s, got %s\n"
                        % (name, digest, after))
            except Exception as error:               # pragma: no cover
                sys.stderr.write("SAVE GUARD ERROR on %s: %r\n"
                                 % (live, error))

    atexit.register(restore)
    return snapshot
