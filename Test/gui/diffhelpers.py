"""Which of the AI's mirrored damage helpers actually differ from the real ones."""
import ast, io, os, sys, difflib
ROOT = sys.argv[1]
ai = io.open(os.path.join(ROOT, "Scripts/Battle/ai.py"), encoding="utf-8").read()
dc = io.open(os.path.join(ROOT, "Scripts/Battle/damage_calculation.py"),
             encoding="utf-8").read()


def defs(src, nested_in=None):
    tree = ast.parse(src)
    out = {}
    if nested_in:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == nested_in:
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef):
                        out[sub.name] = ast.get_source_segment(src, sub)
    else:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                out[node.name] = ast.get_source_segment(src, node)
    return out


est = defs(ai, "estimated_damage_calculation")
real = defs(dc)
PAIRS = [("check_estimated_attack_power", "check_attack_power"),
         ("check_estimated_defense_strength", "check_defense_strength"),
         ("check_estimated_power_modifier", "check_power_modifier"),
         ("check_if_estimated_weather_affect_moves",
          "check_if_weather_affect_moves"),
         ("check_estimated_crit", "check_crit"),
         ("check_estimated_STAB", "check_STAB"),
         ("check_estimated_type_effectiveness", "check_type_effectiveness"),
         ("check_estimated_other_factor", "check_other_factor")]


def norm(seg, name, other):
    lines = []
    for line in (seg or "").split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s.replace(name, "F").replace(other, "F"))
    return lines


print("%-42s %s" % ("AI's copy vs the engine's", "verdict"))
print("-" * 72)
for a, b in PAIRS:
    la, lb = norm(est.get(a), a, a), norm(real.get(b), b, b)
    if la == lb:
        print("%-42s IDENTICAL  (%d lines)" % (a, len(la)))
    else:
        d = [l for l in difflib.unified_diff(lb, la, lineterm="", n=0)
             if l and l[0] in "+-" and not l.startswith(("---", "+++"))]
        print("%-42s DIFFERS    (%d changed lines)" % (a, len(d)))
        for line in d[:6]:
            print("      %s" % line[:96])
