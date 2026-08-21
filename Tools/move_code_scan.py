"""Which moves have behaviour written in code rather than in Data/moves.csv.

Found by reading the engine, not by keeping a list: anything of the shape
`something.name == "Fire Blast"` is a move the table alone does not fully
describe. The `remarks` column of moves.csv is generated from this, and
Test/gui/test_engine_integrity.py fails if the two disagree -- so a new
`if move.name == ...` is a test failure until it is written down where the
person editing the spreadsheet will see it.

    python Tools/move_code_scan.py        show what it finds

WHY holds the one-line reason for each. A move found by the scan with no entry
here is reported rather than silently described as "special-cased", because
"there is code for this somewhere" is not much help to the next person.
"""
import ast
import io
import os

#: move -> why its behaviour cannot live in the table.
#:
#: The distinction the whole thing turns on: a *computation* has to be code,
#: because no cell can hold a formula. A *condition* is only in code because
#: nobody has given it a column yet -- those are marked "could be data", and
#: they are the list to work through if the table is to become the whole
#: truth. See the "Adding a move" section of CLAUDE.md.
WHY = {
    # -- computations: these belong in code -------------------------------
    "Metronome": "picks a random other move",
    "Electro Ball": "power from the speed ratio",
    "Time Pressure": "power from the speed ratio",
    "Acupressure": "raises one random stat by two",
    "Spectral Thief": "steals the target's positive boosts",
    "Cannibalism": "heals from the overkill damage",
    "Fell Stinger": "fires when the target faints",
    "Counter": "reads the target's last move",
    "Mirror Coat": "reads the target's last move",
    "Metal Burst": "reads the target's last move",
    "Rapid Spin": "clears hazards on its own side only",
    "Defog": "clears hazards and screens on both sides",
    "Baton Pass": "hands its stat changes to the Pokemon coming in",

    # -- conditions still without a column ---------------------------------
    "Toxic": "could be data: never misses from a Poison-type user",
    "Dream Eater": "the AI weighs it specially (the rule itself is data)",
    "Sucker Punch": "the AI weighs it specially (the rule itself is data)",
    "Thunder": "could be data: hits a target in the air",
    "Hurricane": "could be data: hits a target in the air",
    "Smack Down": "could be data: hits a target in the air",
    "Earthquake": "could be data: double power on a target underground",
    "Whirlpool": "could be data: double power on a target underwater",
    "Surf": "could be data: double power on a target underwater",
    "Protect": "the AI weighs it specially",
    "Destiny Bond": "the AI weighs it specially",

    # -- not really a move -------------------------------------------------
    "Switching": "not a move: the engine's name for swapping out",
    "King's Shield": "read by the Stance Change ability",
    "Water Shuriken": "read by the Battle Bond ability",
    "Mind Blown": "read by a character ability",
}

#: attributes whose comparison against a string literal names a move
NAME_ATTRIBUTES = ("name",)
#: where the engine lives
ENGINE = "Scripts"


class _Branches(ast.NodeVisitor):
    def __init__(self, path, out):
        self.path, self.out = path, out

    def visit_Compare(self, node):
        left = node.left
        if isinstance(left, ast.Attribute) and left.attr in NAME_ATTRIBUTES:
            for comparator in node.comparators:
                for literal in self._strings(comparator):
                    self.out.setdefault(literal, []).append(
                        "%s:%d" % (self.path, node.lineno))
        self.generic_visit(node)

    @staticmethod
    def _strings(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value
        elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for element in node.elts:
                if isinstance(element, ast.Constant) \
                        and isinstance(element.value, str):
                    yield element.value


def scan(root="."):
    """{name compared against: [file:line, ...]} across the engine."""
    out = {}
    base = os.path.join(root, ENGINE)
    for folder, _, names in os.walk(base):
        if "__pycache__" in folder:
            continue
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            shown = os.path.relpath(path, root).replace("\\", "/")
            source = io.open(path, encoding="utf-8").read()
            _Branches(shown, out).visit(ast.parse(source))
    return out


def remarks_for(move_names, root="."):
    """{move: the remark that belongs in its row}, for real moves only."""
    found = scan(root)
    out = {}
    for name, places in found.items():
        if name not in move_names:
            continue                       # a status or a Pokemon, not a move
        why = WHY.get(name)
        where = sorted(set(places))[0]
        out[name] = ("in code: %s (%s)" % (why, where) if why
                     else "in code: reason not recorded -- add one to "
                          "Tools/move_code_scan.py (%s)" % where)
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("POKEMON_MUTE", "1")
    import Scripts.Battle.battle_cycle                            # noqa: F401
    from Scripts.Data.moves import list_of_moves

    marks = remarks_for(set(list_of_moves))
    print("%d of %d moves have behaviour in code:\n"
          % (len(marks), len(list_of_moves)))
    for name in sorted(marks):
        print("   %-22s %s" % (name, marks[name]))

    ghosts = sorted(n for n in scan() if n not in list_of_moves)
    print("\nnames compared against `.name` that are not moves: %s" % ghosts)
