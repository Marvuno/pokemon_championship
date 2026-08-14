"""Static sweep for dead code, duplication and no-op expressions."""
import ast
import collections
import io
import os
import sys

ROOT = sys.argv[1]
SKIP = {"__pycache__", ".git", "Latest.zip"}

files = []
for base, dirs, names in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for n in names:
        if n.endswith(".py"):
            files.append(os.path.join(base, n))

trees, src = {}, {}
for path in files:
    try:
        text = io.open(path, encoding="utf-8").read()
        trees[path] = ast.parse(text)
        src[path] = text
    except Exception as exc:
        print("PARSE FAIL %s: %s" % (path, exc))

rel = lambda p: os.path.relpath(p, ROOT).replace("\\", "/")

# every name mentioned anywhere (attribute or bare)
used = collections.Counter()
for path, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used[node.id] += 1
        elif isinstance(node, ast.Attribute):
            used[node.attr] += 1
        # names referenced inside strings (getattr / patch_everywhere by name)
for path, text in src.items():
    for node in ast.walk(trees[path]):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            used[node.value] += 1

print("=" * 72)
print("MODULE-LEVEL FUNCTIONS NEVER REFERENCED BY NAME")
print("=" * 72)
star = set()
for path, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(
                a.name == "*" for a in node.names):
            star.add(rel(path))
dead = []
for path, tree in trees.items():
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if used[node.name] == 0 and not node.name.startswith("_"):
                dead.append((rel(path), node.lineno, node.name))
for f, l, n in sorted(dead):
    print("  %-40s :%-5d %s" % (f, l, n))
print("  (%d)" % len(dead))

print()
print("=" * 72)
print("METHODS NEVER REFERENCED BY NAME (excluding Qt overrides)")
print("=" * 72)
QT = {"paintEvent", "closeEvent", "hideEvent", "showEvent", "resizeEvent",
      "mousePressEvent", "mouseReleaseEvent", "keyPressEvent", "enterEvent",
      "leaveEvent", "eventFilter", "sizeHint", "minimumSizeHint", "reject",
      "accept", "event", "wheelEvent", "mouseMoveEvent", "focusInEvent",
      "focusOutEvent", "moveEvent", "changeEvent", "write", "flush",
      "isatty", "readline", "fileno", "close", "run", "__init__"}
deadm = []
for path, tree in trees.items():
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for node in cls.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in QT or node.name.startswith("__"):
                    continue
                if used[node.name] == 0:
                    deadm.append((rel(path), node.lineno,
                                  cls.name + "." + node.name))
for f, l, n in sorted(deadm):
    print("  %-40s :%-5d %s" % (f, l, n))
print("  (%d)" % len(deadm))

print()
print("=" * 72)
print("NO-OP EXPRESSIONS  (x if c else x)")
print("=" * 72)
found = 0
for path, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.IfExp):
            try:
                if ast.dump(node.body) == ast.dump(node.orelse):
                    print("  %s:%d" % (rel(path), node.lineno))
                    found += 1
            except Exception:
                pass
print("  (%d)" % found)

print()
print("=" * 72)
print("DUPLICATE FUNCTION BODIES (identical source, >=4 lines)")
print("=" * 72)
bodies = collections.defaultdict(list)
for path, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            try:
                seg = ast.get_source_segment(src[path], node)
            except Exception:
                seg = None
            if not seg:
                continue
            lines = [l.strip() for l in seg.split("\n")
                     if l.strip() and not l.strip().startswith("#")]
            # drop the def line and any docstring line
            key = "\n".join(lines[1:])
            if len(lines) >= 5:
                bodies[key].append("%s:%d %s" % (rel(path), node.lineno,
                                                 node.name))
dups = {k: v for k, v in bodies.items() if len(v) > 1}
for k, v in list(dups.items())[:12]:
    print("  " + " == ".join(v))
print("  (%d groups)" % len(dups))

print()
print("=" * 72)
print("LONGEST FUNCTIONS")
print("=" * 72)
sizes = []
for path, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            sizes.append((end - node.lineno, rel(path), node.lineno,
                          node.name))
for n, f, l, name in sorted(sizes, reverse=True)[:18]:
    print("  %4d lines  %-34s :%-5d %s" % (n, f, l, name))
