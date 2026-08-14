"""Every name main() and the bridge reach for must actually exist.

Python only raises NameError when the line runs, so deleting a function that
one caller still uses compiles cleanly and then dies mid-run -- which is how
team_selection went missing from before_battle.py and only surfaced when a
playthrough reached the first battle. This resolves those names up front.
"""
import ast
import os
import sys

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

fails = []


def check(label, ok, detail=""):
    print("%-58s %s" % (label, "PASS" if ok else "FAIL " + detail))
    if not ok:
        fails.append(label)


import main                                                     # noqa: E402

# ---- every bare function main() calls has to be bound in main's namespace
source = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
called = sorted({node.func.id
                 for node in ast.walk(ast.parse(source))
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)})
missing = [name for name in called
           if not hasattr(main, name) and name not in dir(__builtins__)
           and name not in vars(__builtins__)]
check("every function main.py calls is bound (%d checked)" % len(called),
      not missing, str(missing))

# ---- and everything the bridge patches must be there to patch
from GUI import bridge as B                                      # noqa: E402

hooked = sorted({node.args[0].value
                 for node in ast.walk(ast.parse(
                     open(os.path.join(ROOT, "GUI", "bridge.py"),
                          encoding="utf-8").read()))
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "patch_everywhere"
                 and node.args and isinstance(node.args[0], ast.Constant)})
absent = [name for name in hooked
          if not any(hasattr(sys.modules[m], name)
                     for m in list(sys.modules)
                     if m.startswith(("Scripts", "main")) and sys.modules[m])]
check("every name the bridge patches exists (%d checked)" % len(hooked),
      not absent, str(absent))

# ---- installing the hooks must not raise, and must leave those names callable
class FakeBridge:
    difficulty = "normal"
    state = {}
    ctx = {}
    next_input_kind = "generic"
    banners = []

    def publish(self, **kw):
        self.state.update(kw)

    def emit(self, *a, **kw):
        pass

    def capture(self, *a, **kw):
        from contextlib import nullcontext
        return nullcontext([])


try:
    B.install_hooks(FakeBridge(), main)
    check("install_hooks runs clean", True)
except Exception as error:
    check("install_hooks runs clean", False, repr(error))

still_callable = [name for name in hooked
                  if not any(callable(getattr(sys.modules[m], name, None))
                             for m in list(sys.modules)
                             if m.startswith(("Scripts", "main"))
                             and sys.modules[m])]
check("all of them are still callable afterwards", not still_callable,
      str(still_callable))

# ---- the pre-battle menu's own handlers
import Scripts.Game.before_battle as before                      # noqa: E402

check("every menu entry resolves to a function",
      all(callable(getattr(before, name, None))
          for _, name, _ in before.MENU),
      str([n for _, n, _ in before.MENU
           if not callable(getattr(before, n, None))]))
check("quit_game really is gone", not hasattr(before, "quit_game"))
check("team_selection is there", callable(getattr(before, "team_selection",
                                                 None)))

print("\n" + ("ALL PASS" if not fails else "%d FAILURES: %s"
                                           % (len(fails), fails)))
sys.exit(1 if fails else 0)
