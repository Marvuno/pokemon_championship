"""Beginner difficulty must leave no route to the smart AI, and Normal must
leave it exactly as it was."""
import os
import sys

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

report, failures = [], []


def check(label, got, want):
    ok = got == want
    report.append("%-58s %s" % (label, "PASS" if ok else
                                "FAIL got=%r want=%r" % (got, want)))
    if not ok:
        failures.append(label)


class FakeBridge:
    """Enough of Bridge for install_hooks; records what it publishes."""

    def __init__(self, difficulty):
        self.difficulty = difficulty
        self.root = ROOT
        self.state = {}
        self.published = {}
        self.texts = []
        self.ctx = {}
        self.before_input = None
        self.next_input_kind = "generic"
        self.refresh = None
        self.side_of = None

    def publish(self, **fields):
        self.state.update(fields)
        self.published.update(fields)

    def emit(self, kind, payload=None):
        self.texts.append(str(payload))

    def capture(self, fn, *a, **kw):
        return fn(*a, **kw), ""

    def capture_quiet(self, fn, *a, **kw):
        return fn(*a, **kw), ""

    def emit_banner(self, *a, **kw):
        pass


def modules_holding(name):
    """Every module whose `name` attribute is bound, and to what."""
    out = {}
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        try:
            value = getattr(mod, name, None)
        except Exception:
            continue
        if value is not None and callable(value):
            out[getattr(mod, "__name__", "?")] = getattr(
                value, "__name__", "?")
    return out


difficulty = sys.argv[2]
import main                                                 # noqa: E402
import GUI.bridge as B                                      # noqa: E402
import Scripts.Battle.ai as battle_ai                       # noqa: E402

smart, dumb = battle_ai.smart_ai_select_move, battle_ai.dumb_ai_select_move
check("the two AIs take the same arguments",
      smart.__code__.co_varnames[:smart.__code__.co_argcount],
      dumb.__code__.co_varnames[:dumb.__code__.co_argcount])

before = modules_holding("smart_ai_select_move")
check("smart_ai is bound in more than one module before patching",
      len(before) > 1, True)

bridge = FakeBridge(difficulty)
B.install_hooks(bridge, main)

after = modules_holding("smart_ai_select_move")
still_smart = {m: v for m, v in after.items()
               if v == "smart_ai_select_move"}
now_dumb = {m: v for m, v in after.items() if v == "dumb_ai_select_move"}

if difficulty == "beginner":
    check("no module still points smart_ai at the smart routine",
          still_smart, {})
    check("every one of them now points at the simple routine",
          len(now_dumb), len(before))
    check("battle_cycle in particular",
          after.get("Scripts.Battle.battle_cycle"), "dumb_ai_select_move")
    check("the interface was told", bridge.published.get("difficulty"),
          "beginner")
    check("no failure was reported",
          [t for t in bridge.texts if "could not be applied" in t], [])
    # the rating gate can no longer reach the smart AI either way
    import Scripts.Battle.battle_cycle as cycle
    check("both branches of the rating gate are the same function now",
          cycle.smart_ai_select_move is cycle.dumb_ai_select_move, True)
else:
    check("Normal leaves smart_ai bound everywhere it was",
          len(still_smart), len(before))
    check("nothing was rebound to the simple routine", now_dumb, {})
    check("no difficulty was published",
          bridge.published.get("difficulty"), None)
    import Scripts.Battle.battle_cycle as cycle
    check("the rating gate still has two different functions",
          cycle.smart_ai_select_move is cycle.dumb_ai_select_move, False)

# auto battle is untouched either way -- it is the player's own AI
check("auto_ai_select_move is never swapped",
      battle_ai.auto_ai_select_move.__name__, "auto_ai_select_move")

print("== difficulty = %s ==" % difficulty)
print("\n".join(report))
print("%s\n" % ("ALL PASS" if not failures
                else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
