"""The ability registry is the whole truth about what abilities exist.

Three things worth failing over: an entry that is malformed, an ability a
Pokemon holds that nothing implements, and an effect function that does not
take the call object. The first two used to be discoverable only by playing
and noticing nothing happened.
"""
import ast
import inspect
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                 # noqa: F401,E402
from Scripts.Battle import ability_effects as E                    # noqa: E402
from Scripts.Data import abilities as A                            # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                   # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


print("-- the registry --")
check("the registry reports no problems", A.problems(), [])
# Not a hard number: it was 153, then Toxic Debris made it 154, and a
# hardcoded count only ever fails the day somebody adds an ability
# correctly. What matters is that the registry and the effects module agree.
effect_names = {entry[1].__name__ for entry in A.REGISTRY.values()}
check("every registry entry points at a function in ability_effects",
      sorted(n for n in effect_names if not hasattr(E, n)), [])
check("there are abilities at all, and a plausible number of them",
      100 < len(A.REGISTRY) < 400)
check("the phase map is derived from the registry, not written twice",
      sorted(A._ABILITY_PHASES), sorted(A.REGISTRY))

# every effect takes the call object and nothing else
wrong = [name for name, entry in A.REGISTRY.items()
         if list(inspect.signature(entry[1]).parameters) != ["call"]]
check("every effect function takes (call)", wrong, [])

# and they are real module-level functions now, not closures
nested = [name for name, entry in A.REGISTRY.items()
          if entry[1].__qualname__ != entry[1].__name__]
check("no effect is nested inside another function", nested, [])
check("they all live in ability_effects",
      {entry[1].__module__ for entry in A.REGISTRY.values()},
      {"Scripts.Battle.ability_effects"})

print()
print("-- what the Pokemon actually hold --")
held = {a for mon in list_of_pokemon.values()
        for a in (getattr(mon, "ability", None) or [])}
check("every held ability is registered or declared inert",
      sorted(held - set(A.REGISTRY) - set(A.KNOWN_INERT)), [])
for name, why in sorted(A.KNOWN_INERT.items()):
    who = sorted(n for n, m in list_of_pokemon.items()
                 if name in (getattr(m, "ability", None) or []))
    print("   inert: %s -- held by %s" % (name, ", ".join(who)))
    print("          %s" % why.split(".")[0])

# two abilities that do exactly the same thing should be one function with
# two registry entries, or a fix to one silently misses the other
import collections                                                 # noqa: E402
effects = ast.parse(io.open("Scripts/Battle/ability_effects.py",
                            encoding="utf-8").read())
bodies = collections.defaultdict(list)
for node in effects.body:
    if isinstance(node, ast.FunctionDef):
        text = ast.unparse(ast.Module(body=node.body, type_ignores=[]))
        if text.strip() != "pass":          # the deliberate no-ops differ in
            bodies[text].append(node.name)  # why, and say so in comments
check("no two effect functions have identical bodies",
      sorted(v for v in bodies.values() if len(v) > 1), [])
check("shared behaviour is shared by name, not copied",
      sorted({e[1].__name__ for e in A.REGISTRY.values()
              if sum(1 for o in A.REGISTRY.values()
                     if o[1] is e[1]) > 1}),
      ["_cannot_be_crit", "_doubles_attack", "_hurts_on_contact",
       "_retypes_to_the_move", "_softens_super_effective",
       "_wakes_up_immediately"])

print()
print("-- the dispatcher does not rebuild the world --")
source = io.open("Scripts/Data/abilities.py", encoding="utf-8").read()
tree = ast.parse(source)
use = [n for n in ast.walk(tree)
       if isinstance(n, ast.FunctionDef) and n.name == "UseAbility"][0]
check("UseAbility defines no functions inside itself",
      [n.name for n in ast.walk(use) if isinstance(n, ast.FunctionDef)
       and n is not use], [])
check("abilities.py is a dispatcher, not a wall (%d lines)"
      % len(source.splitlines()), len(source.splitlines()) < 250)
check("the effects module holds them all (%d lines)"
      % len(io.open("Scripts/Battle/ability_effects.py",
                    encoding="utf-8").read().splitlines()), True)

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
