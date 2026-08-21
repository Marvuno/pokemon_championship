"""Generate Data/moves.csv from the move literal, and prove it round-trips.

Kept because it is also the check: it writes the table out of the live
`list_of_moves` and reads it back through
Scripts/Data/moves.py, and compares all 387 moves *field by field* --
including which status function each effect points at. Nothing is transcribed
by hand, so nothing can be mistyped.

    python Tools/moves_to_csv.py            write and verify
    python Tools/moves_to_csv.py --check    verify only, write nothing

Run --check after editing the CSV by hand: it will not compare against the
literal once that is gone, but it still loads every row and reports any row
the loader rejects.
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

from Scripts.Data import moves as table                           # noqa: E402
from Scripts.Data.moves import Move, MoveDataError, list_of_moves  # noqa: E402


# -- writing the table ------------------------------------------------------
# The encoder lives here rather than in the game. The game only ever *reads*
# Data/moves.csv; the only thing that writes it is this tool, and keeping the
# two halves in one module meant Scripts/Data/moves.py carried fifty lines it
# would never run.
STATUS_NAMES = {value: name for name, value in table.STATUS_EFFECTS.items()}


def _write_number(value):
    return repr(value)


def encode_effect(value):
    """The inverse, for generating the CSV."""
    if value is None:
        return table.NONE_MARK
    if callable(value):
        return table.FUNCTION_MARK + STATUS_NAMES[value]
    if isinstance(value, list):
        body = ",".join(_write_number(item) if isinstance(item, (int, float))
                        else str(item) for item in value)
        # a one-entry list would be indistinguishable from a bare scalar
        return body + "," if len(value) == 1 else body
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return _write_number(value)
    return str(value)


def encode_row(move):
    """A Move -> the CSV row that reproduces it."""
    row = {}
    for field in table.FIELDS:
        value = getattr(move, table._attribute_for(field))
        if field in table.FLAGS:
            row[field] = "Y" if value else ""
        elif field in table.NUMBERS:
            row[field] = _write_number(value)
        elif field in table.STRING_LISTS or field in table.NUMBER_LISTS:
            row[field] = ",".join(_write_number(item)
                                  if isinstance(item, (int, float))
                                  else str(item) for item in value)
        elif field in ("effect_type", "special_effect"):
            if isinstance(value, list) and field == "effect_type":
                row[field] = table.EFFECT_SEPARATOR.join(str(v) for v in value)
            elif field == "special_effect" and isinstance(move.effect_type,
                                                          list):
                row[field] = table.EFFECT_SEPARATOR.join(
                    encode_effect(item) for item in value)
            else:
                row[field] = (str(value) if field == "effect_type"
                              else encode_effect(value))
        else:
            row[field] = str(value)
    return row





CHECK_ONLY = "--check" in sys.argv
DEST = table.MOVES_CSV


def write():
    # the remarks column is generated, never typed -- see move_code_scan
    from Tools import move_code_scan
    notes = move_code_scan.remarks_for(set(list_of_moves))
    rows = []
    for move in list_of_moves.values():
        row = encode_row(move)
        row["remarks"] = notes.get(move.name, "")
        rows.append(row)
    with open(DEST, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table.COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    print("wrote %s: %d moves, %d columns (%d of them carrying a remark)"
          % (DEST, len(rows), len(table.COLUMNS),
             sum(1 for r in rows if r["remarks"])))


def differences(original, rebuilt):
    """Every way the two could fail to be the same move."""
    problems = []
    for field in table.FIELDS:
        attribute = table._attribute_for(field)
        mine = getattr(original, attribute)
        theirs = getattr(rebuilt, attribute)
        if callable(mine) or callable(theirs):
            # a status effect must be the *same function object*, not one that
            # merely shares a name
            if mine is not theirs:
                problems.append("%s: %r is not %r" % (field, mine, theirs))
            continue
        if isinstance(mine, list) and isinstance(theirs, list):
            if len(mine) != len(theirs):
                problems.append("%s: %d entries vs %d"
                                % (field, len(mine), len(theirs)))
                continue
            for index, (a, b) in enumerate(zip(mine, theirs)):
                if callable(a) or callable(b):
                    if a is not b:
                        problems.append("%s[%d]: %r is not %r"
                                        % (field, index, a, b))
                elif a != b:
                    problems.append("%s[%d]: %r vs %r" % (field, index, a, b))
                elif type(a) is not type(b):
                    problems.append("%s[%d]: %s vs %s"
                                    % (field, index, type(a), type(b)))
            continue
        if mine != theirs:
            problems.append("%s: %r vs %r" % (field, mine, theirs))
        elif type(mine) is not type(theirs):
            problems.append("%s: %s vs %s" % (field, type(mine), type(theirs)))
    return problems


def verify():
    rebuilt = table.load(DEST)
    print("read back %d moves from %s" % (len(rebuilt), DEST))

    missing = sorted(set(list_of_moves) - set(rebuilt))
    extra = sorted(set(rebuilt) - set(list_of_moves))
    if missing:
        print("  MISSING from the table: %s" % missing[:8])
    if extra:
        print("  NOT in the literal: %s" % extra[:8])

    bad = 0
    for name in sorted(set(list_of_moves) & set(rebuilt)):
        problems = differences(list_of_moves[name], rebuilt[name])
        if problems:
            bad += 1
            if bad <= 8:
                print("  %-24s %s" % (name, "; ".join(problems[:3])))
    print()
    if missing or extra or bad:
        print("FAILED: %d move(s) differ, %d missing, %d extra"
              % (bad, len(missing), len(extra)))
        return 1
    print("every one of the %d moves round-trips identically, field for field,"
          % len(rebuilt))
    print("status effects included (compared by function identity, not name)")
    return 0


if not CHECK_ONLY:
    write()
raise SystemExit(verify())
