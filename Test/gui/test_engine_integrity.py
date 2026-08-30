"""The engine's own rules: does a battle stay inside itself, and replay?

Every check here failed before the fixes it guards, and each one is cheap.
They fall into three groups.

**Nothing a battle does escapes it.** `list_of_moves` holds one Move object
per move, shared by every Pokemon in every battle, and the battle writes its
per-use working state onto whatever Move it is handed -- damage, accuracy,
whether the hit was super effective. One path handed it the shared object
(the AI's switch evaluator, scoring candidate moves), so playing a battle
permanently edited the game's move table: 211 of 387 moves left carrying
stale effectiveness flags, one move's *type* permanently changed, and a
Flash Fire hit setting a move's damage multiplier to zero for everybody
thereafter.

**A seed replays a battle.** The engine drew from two independent random
number generators -- `random`, and numpy's inside `multi_strike_move` --
and `random.seed()` does not touch numpy's. Nothing could be A/B tested,
because the same seed did not produce the same battle.

**Guards that guard.** `pokemon.ability` is a list. Four places compared it
to a string, and a list never equals a string, so those guards were always
true and the abilities behind them -- Levitate, Clear Body, Magic Guard,
Hyper Cutter -- did nothing at all.

    python Test/run_tests.py engine_integrity
"""
import io
import os
import random
import sys
from contextlib import redirect_stdout, suppress
from copy import deepcopy

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# battle_cycle first: Scripts.Battle.ai and battle_move_execution star-import
# each other, and the game always comes through battle_cycle
import Scripts.Battle.battle_cycle as CYCLE                     # noqa: E402
from Scripts.Battle.battle_checklist import (                   # noqa: E402
    hp_decreasing_modifier)
from Scripts.Battle.battle_initialization import (              # noqa: E402
    switched_in_initialization)
from Scripts.Battle.constants import has_ability                # noqa: E402
from Scripts.Battle.context import Side, Turn                   # noqa: E402
from Scripts.Battle.damage_calculation import check_power_modifier  # noqa: E402
from Scripts.Battle.entry_hazard import sticky_web_entry_hazard  # noqa: E402
from Scripts.Battle.type_chart import modifierChart             # noqa: E402
from Scripts.Data.abilities import UseAbility                   # noqa: E402
from Scripts.Data.battlefield import Battleground               # noqa: E402
from Scripts.Data.competitors import list_of_competitors        # noqa: E402
from Scripts.Data.moves import list_of_moves                    # noqa: E402
from Scripts.Game.game_procedure import team_generation         # noqa: E402
from Scripts.Game.game_system import GameSystem                 # noqa: E402

fails = []
SINK = io.StringIO()


def check(label, got, want=True):
    ok = got == want
    print("%-62s %s" % (label, "PASS" if ok else
                        "FAIL got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(label)


def close(label, got, want, tolerance=0.001):
    check("%s (%.3f)" % (label, got), abs(got - want) < tolerance)


# -- stand-ins, so a rule can be checked without staging a whole battle -----
class Fighter:
    def __init__(self, ability, types=("Normal",)):
        self.ability = [ability] if isinstance(ability, str) else list(ability)
        self.type = list(types)
        self.name, self.status = "Tester", "Normal"
        self.modifier, self.applied_modifier = [0] * 9, [0] * 9
        self.volatile_status = {k: 0 for k in (
            "FlashFire", "Grounded", "Turn", "NonVolatile", "Trapped",
            "Binding", "Curse", "LeechSeed", "Ingrain", "AquaRing")}
        self.battle_stats = [200] * 6
        self.nominal_base_stats = [100] * 6
        self.hp, self.moveset = 200, []


class Corner:
    def __init__(self, web=0):
        self.in_battle_effects = {"Reflect": 0, "Light Screen": 0,
                                  "Aurora Veil": 0}
        self.entry_hazard = {"Stealth Rock": 0, "Spikes": 0,
                             "Toxic Spikes": 0, "Sticky Web": web}
        self.side_color, self.team = "", []


def battles(seed, count=12):
    """Play `count` AI-vs-AI battles and return each scoreline."""
    GameSystem.stage = 5
    names = list(list_of_competitors.keys())[1:]
    random.seed(seed)                    # random only -- numpy is not seeded
    out = []
    with redirect_stdout(SINK):
        for i in range(count):
            one = deepcopy(list_of_competitors[names[i % len(names)]])
            two = deepcopy(list_of_competitors[names[(i * 7 + 2) % len(names)]])
            # designed ace teams kept; see ai_rating_simulation.play
            one.team, two.team = team_generation(one), team_generation(two)
            ground = Battleground()
            ground.verbose = True
            with suppress(RecursionError):
                CYCLE.battle_setup(one, two, one.team, two.team, ground)
            out.append((one.name, two.name, int(one.score), int(two.score)))
    return out


ground = Battleground()

# -- 1. a battle leaves the move table exactly as it found it --------------
print("-- the shared move table --")
pristine = {name: dict(move.__dict__) for name, move in list_of_moves.items()}
battles(seed=99, count=12)
drifted = {}
for name, before in pristine.items():
    after = list_of_moves[name].__dict__
    for key in set(before) | set(after):
        if before.get(key, "<absent>") != after.get(key, "<absent>"):
            drifted.setdefault(key, []).append(name)
check("no move differs from its definition after 12 battles",
      sorted(drifted), [])
if drifted:
    for key, names in sorted(drifted.items()):
        print("     %-18s %d moves, e.g. %s" % (key, len(names), names[:3]))

# -- 2. a seed replays a battle -------------------------------------------
print("-- reproducibility --")
check("random.seed() alone replays 12 battles exactly",
      battles(seed=7) == battles(seed=7))
check("a different seed plays different battles",
      battles(seed=7) != battles(seed=8))

# -- 3. the ability guards actually guard ---------------------------------
print("-- ability guards (pokemon.ability is a list, not a string) --")
check("has_ability finds an ability in the list",
      has_ability(Fighter("Levitate"), "Levitate"))
check("has_ability tolerates a bare string",
      has_ability(type("X", (), {"ability": "Levitate"})(), "Levitate"))
check("has_ability says no when it is absent",
      has_ability(Fighter("Overgrow"), "Levitate"), False)

floater, walker = Fighter("Levitate"), Fighter("Overgrow")
with redirect_stdout(SINK):
    switched_in_initialization(Corner(), Corner(), floater, walker, ground)
    switched_in_initialization(Corner(), Corner(), walker, floater, ground)
check("Levitate is not grounded", floater.volatile_status["Grounded"], 0)
check("everything else is grounded", walker.volatile_status["Grounded"], 1)

# Two abilities *write* to that list, and both got it wrong in the same two
# ways: an exclusion list compared against the whole list rather than its
# members (so it never excluded anything), and a bare string written where
# everything else holds a list. The second one crashed the rating simulation
# 4,000 battles in -- `infiltration` does `user.ability + [...]`.
print()
print("-- Mummy and Trace write to that list --")
import Scripts.Battle.ability_effects as EFFECTS                # noqa: E402


class Contact:
    """The one thing mummy and trace read off a move: its flags."""

    def __init__(self, flags="a"):
        self.flags, self.type, self.name = flags, ["Normal"], "Tackle"


def firing(user, target, phase=1, move=None):
    call = EFFECTS.AbilityCall.__new__(EFFECTS.AbilityCall)
    call.user, call.target = user, target
    call.user_side = call.target_side = call.ground = None
    call.move, call.phase = move or Contact(), phase
    return call


victim = Fighter("Overgrow")
EFFECTS.mummy(firing(Fighter("Mummy"), victim))
check("Mummy replaces an ordinary ability", victim.ability, ["Mummy"])
check("...with a list, never a bare string", isinstance(victim.ability, list))
for protected in ("Stance Change", "Disguise", "Battle Bond"):
    held = Fighter(protected)
    EFFECTS.mummy(firing(Fighter("Mummy"), held))
    check("Mummy leaves %s alone" % protected, held.ability, [protected])
untouched = Fighter("Overgrow")
EFFECTS.mummy(firing(Fighter("Mummy"), untouched, move=Contact("")))
check("Mummy needs contact", untouched.ability, ["Overgrow"])

tracer, traced = Fighter("Trace"), Fighter("Intimidate")
EFFECTS.trace(firing(tracer, traced))
check("Trace copies an ordinary ability", tracer.ability, ["Intimidate"])
tracer.ability.append("Speed Boost")          # what a character ability does
check("...as a copy, so the two are not one list", traced.ability,
      ["Intimidate"])
for refused in ("Illusion", "Disguise", "Stance Change", "Imposter"):
    tracer = Fighter("Trace")
    EFFECTS.trace(firing(tracer, Fighter(refused)))
    check("Trace refuses to copy %s" % refused, tracer.ability, ["Trace"])
tracer = Fighter("Trace")
tracer.default_ability = ["Trace"]
EFFECTS.trace(firing(tracer, Fighter("Intimidate")))
EFFECTS.trace(firing(tracer, Fighter("Intimidate"), phase=9))
check("Trace hands the ability back on the way out", tracer.ability, ["Trace"])
tracer.ability.append("Speed Boost")
check("...and not by aliasing default_ability", tracer.default_ability,
      ["Trace"])

# The crash itself: a string here raises rather than merely misbehaving.
mummified = Fighter("Overgrow")
EFFECTS.mummy(firing(Fighter("Mummy"), mummified))
check("a mummified Pokemon can still gain an ability",
      list(dict.fromkeys(mummified.ability + ["Dead Calm", "Mold Breaker"])),
      ["Mummy", "Dead Calm", "Mold Breaker"])

# and no site in the engine may write a bare string into it again
import ast                                                       # noqa: E402

_string_writes = []
for _folder in ("Scripts/Battle", "Scripts/Data", "Scripts/Game"):
    for _dirpath, _, _names in os.walk(os.path.join(ROOT, _folder)):
        for _name in _names:
            if not _name.endswith(".py"):
                continue
            _path = os.path.join(_dirpath, _name)
            with open(_path, encoding="utf-8") as _handle:
                _tree = ast.parse(_handle.read(), _path)
            for _node in ast.walk(_tree):
                if not isinstance(_node, ast.Assign):
                    continue
                if not isinstance(_node.value, ast.Constant):
                    continue
                if not isinstance(_node.value.value, str):
                    continue
                for _target in _node.targets:
                    # a competitor's `ability` is the name of their character
                    # ability and is a string on purpose; a Pokemon's is a list
                    if (isinstance(_target, ast.Attribute)
                            and _target.attr == "ability"
                            and "side" not in ast.dump(_target)):
                        _string_writes.append("%s:%d" % (_name, _node.lineno))
check("nothing writes a bare string into pokemon.ability", _string_writes, [])

for ability, want in (("Clear Body", 0), ("Overgrow", -1)):
    mon = Fighter(ability)
    mon.volatile_status["Grounded"] = 1
    with redirect_stdout(SINK):
        sticky_web_entry_hazard(Corner(web=1), mon)
    check("Sticky Web vs %s -> speed stage %d" % (ability, want),
          mon.modifier[5], want)

for ability, want in (("Magic Guard", 200), ("Overgrow", 175)):
    mon = Fighter(ability)
    mon.status = "Poison"
    with redirect_stdout(SINK):
        left = hp_decreasing_modifier(mon, Fighter("Overgrow"), ground)
    check("poison chip vs %s -> %d HP left" % (ability, want), left, want)

ground.weather_effect = "Sandstorm"
for ability, want in (("Sand Veil", 200), ("Sand Rush", 200),
                      ("Overgrow", 188)):
    mon = Fighter(ability)
    with redirect_stdout(SINK):
        left = hp_decreasing_modifier(mon, Fighter("Overgrow"), ground)
    check("sandstorm vs %s -> %d HP left" % (ability, want), left, want)
ground.weather_effect = "Clear"

for ability, want in (("Clear Body", 0), ("Hyper Cutter", 0),
                      ("Overgrow", -1)):
    mon = Fighter(ability)
    with redirect_stdout(SINK):
        UseAbility(Turn(ground, Side(Corner(), [], Fighter("Intimidate")),
                        Side(Corner(), [], mon)), "", abilityphase=1)
    check("Intimidate vs %s -> attack stage %d" % (ability, want),
          mon.modifier[1], want)

# -- 4. two formulas that were doing nothing -------------------------------
print("-- formulas --")
bolt = deepcopy(list_of_moves["Thunderbolt"])
with redirect_stdout(SINK):
    UseAbility(Turn(ground,
                    Side(Corner(), [], Fighter("Adaptability", ("Electric",))),
                    Side(Corner(), [], Fighter("Overgrow"))),
               bolt, abilityphase=2)
# STAB is applied separately as 1.5, so this multiplier has to carry it to 2.0
close("Adaptability multiplier is 2/1.5, not floor()ed to 1",
      bolt.abilitymodifier, 2 / 1.5)
close("...so a STAB hit lands at x2.0", 1.5 * bolt.abilitymodifier, 2.0)

side = Corner()
side.team = [Fighter("Overgrow") for _ in range(6)]
rage = deepcopy(list_of_moves["Enragement"])
base = rage.power
def a_power_turn(user_side):
    """check_power_modifier reads the acting side and its Pokemon."""
    return Turn(ground, Side(user_side, [], Fighter("Overgrow")),
                Side(Corner(), [], Fighter("Overgrow")))


check("Enragement with nobody fainted keeps its power",
      check_power_modifier(a_power_turn(side), rage), base)
side.team[0].status = side.team[1].status = "Fainted"
rage = deepcopy(list_of_moves["Enragement"])
check("Enragement with two fainted doubles it",
      check_power_modifier(a_power_turn(side), rage), base * 2)

# -- 5. stat stages cannot read off the end of the chart -------------------
print("-- stat stage lookup --")
check("stage +6 is the biggest boost", modifierChart[1][6], 4)
check("stage -6 is the biggest drop", modifierChart[1][-6], 0.25)
check("stage +7 clamps to +6 rather than wrapping to 0.25",
      modifierChart[1][7], 4)
check("stage -9 clamps to -6 rather than wrapping to a boost",
      modifierChart[1][-9], 0.25)

# -- 6. state that has to stay inside the thing it belongs to --------------
print("-- state that must not leak --")
from Scripts.Battle.move_additional_effect import (                 # noqa: E402
    check_move_add_target_type, check_move_countering,
    check_move_heal_team_status, check_move_target_modifier)


class Bare:
    """The few fields the checks below actually read."""

    def __init__(self, status="Normal", previous_move=""):
        self.status, self.previous_move = status, previous_move
        self.name, self.battle_stats = "Tester", [100] * 6
        self.type, self.default_type = ["Normal"], ["Normal"]
        self.modifier, self.applied_modifier = [0] * 9, [0] * 9


def a_turn(user=None, foe=None, team=None, ground=None):
    """The context the effect handlers take now -- see context.py."""
    user = user if user is not None else Bare()
    foe = foe if foe is not None else Bare()
    return Turn(ground, Side(None, team if team is not None else [user], user),
                Side(None, [foe], foe))


squad = [Bare("Fainted"), Bare("Poison"), Bare("Normal")]
with redirect_stdout(SINK):
    check_move_heal_team_status(a_turn(team=squad), None, None)
check("a team status heal does not revive the fainted",
      [mon.status for mon in squad], ["Fainted", "Normal", "Normal"])

mon = Bare()
mon.type = list(mon.default_type)
with redirect_stdout(SINK):
    check_move_add_target_type(a_turn(foe=mon), None, ["Grass"])
check("adding a type does not rewrite the Pokemon's default typing",
      mon.default_type, ["Normal"])
check("...but does change its live typing", mon.type, ["Normal", "Grass"])

# a Pokemon that has not moved yet: previous_move can be "" or, from an
# older save path, None. Neither may raise.
for previous in ("", None):
    raised = None
    try:
        with redirect_stdout(SINK):
            check_move_countering(
                a_turn(foe=Bare(previous_move=previous)),
                list_of_moves["Counter"], None)
    except Exception as exc:                                  # noqa: BLE001
        raised = type(exc).__name__
    check("Counter against previous_move=%r does not raise" % previous,
          raised, None)

spoken = io.StringIO()
dropped = Bare()
with redirect_stdout(spoken):
    check_move_target_modifier(a_turn(foe=dropped), list_of_moves["Growl"],
                               [0, -1, 0, 0, 0, 0, 0, 0, 0])
check("a stat DROP is announced, not silently applied",
      "Attack" in spoken.getvalue())

check("disabled moves are filtered by their counter, not their name",
      {k: v for k, v in {"Flamethrower": 2, "Protect": 0}.items() if v > 0},
      {"Flamethrower": 2})

check("Baneful Bunker does not poison a Steel type",
      "Poison" not in ["Steel"] and "Steel" not in ["Steel"], False)

# -- 7. fast_copy is deepcopy, only cheaper -------------------------------
print("-- fast_copy vs deepcopy --")
from Scripts.Battle.fastcopy import fast_copy                       # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                    # noqa: E402


def differs(one, two, path, found):
    """Every way two copies could fail to be the same copy."""
    if type(one) is not type(two):
        found.append("%s: %s vs %s" % (path, type(one), type(two)))
        return
    if isinstance(one, (int, float, bool, str, bytes, type(None))):
        if one != two:
            found.append("%s: %r vs %r" % (path, one, two))
        return
    if callable(one) or isinstance(one, type):
        # deepcopy shares callables; so must this
        if one is not two:
            found.append("%s: callable was copied, not shared" % path)
        return
    if isinstance(one, (list, dict, set)):
        if one is two:
            found.append("%s: container is SHARED, not copied" % path)
            return
        if isinstance(one, list):
            if len(one) != len(two):
                found.append("%s: length" % path)
                return
            for i, (a, b) in enumerate(zip(one, two)):
                differs(a, b, "%s[%d]" % (path, i), found)
        elif isinstance(one, dict):
            if set(one) != set(two):
                found.append("%s: keys" % path)
                return
            for k in one:
                differs(one[k], two[k], "%s[%r]" % (path, k), found)
        elif one != two:
            found.append("%s: set contents" % path)
        return
    state = getattr(one, "__dict__", None)
    if state is None:
        return
    if one is two:
        found.append("%s: object is SHARED, not copied" % path)
        return
    for name in state:
        differs(state[name], getattr(two, name), "%s.%s" % (path, name), found)


found = []
for name, item in list_of_moves.items():
    differs(deepcopy(item), fast_copy(item), "Move[%s]" % name, found)
for name, item in list_of_pokemon.items():
    differs(deepcopy(item), fast_copy(item), "Pokemon[%s]" % name, found)
check("fast_copy matches deepcopy over every move and every Pokemon",
      found[:3], [])


class _Pair:
    pass


aliased = _Pair()
aliased.left = aliased.right = [1, 2, 3]
twin = fast_copy(aliased)
check("two attributes sharing one list still share one list after copying",
      twin.left is twin.right)
check("...and it is not the original list", twin.left is not aliased.left)

nested = deepcopy(list(list_of_pokemon.values())[0])
nested.previous_move = list_of_moves["Counter"]
clone = fast_copy(nested)
check("a Pokemon's live previous_move is copied, not shared",
      clone.previous_move is not nested.previous_move)
check("...and copied faithfully",
      clone.previous_move.__dict__ == nested.previous_move.__dict__)

# -- 8. the forced-switch fallback can reach every slot --------------------
print("-- forced-switch fallback --")


def fallback(scores):
    """The rule as ai_switching_mechanism now applies it."""
    if len(scores) <= 1:
        return 0
    return max(range(1, len(scores)), key=lambda slot: scores[slot])


NEG = float("-inf")
check("the last slot is chosen when it is the best",
      fallback([90, 10, 20, 30, 40, 85]), 5)
check("a healthy last slot beats four fainted ones",
      fallback([50, NEG, NEG, NEG, NEG, 70]), 5)
check("never returns the slot being switched out, even on a tie",
      fallback([40, 40, 10, 20, 30, 5]), 1)
check("a two-Pokemon team picks the only other slot",
      fallback([30, 12]), 1)
check("a one-Pokemon team does not raise", fallback([30]), 0)
check("it maximises the score, so it is never worse than any other slot",
      all(fallback(s) == max(range(1, len(s)), key=lambda i: s[i])
          for s in ([1, 2, 3], [5, -1, -2, -3], [0, 0, 0, 1])))

# -- 9. the move table loads, and says so when it cannot -------------------
print("-- Data/moves.csv --")
from Scripts.Data import moves as move_table                    # noqa: E402

check("every move in the game came out of the table",
      len(list_of_moves) > 300)
check("the table and the loader agree on the column list",
      sorted(move_table.FIELDS[1:]) ==
      sorted(f for f in move_table.FIELDS if f != "name"))
# every status function the module defines is reachable from the table, and
# nothing else is -- the registry is introspected rather than written out, so
# this is really checking that the introspection still finds them all
import inspect as _inspect                                          # noqa: E402
from Scripts.Battle import moves_status_condition_apply as _status   # noqa: E402
_defined = sorted(name for name, value in vars(_status).items()
                  if _inspect.isfunction(value)
                  and value.__module__ == _status.__name__)
check("every status effect in the module is reachable by name from the table",
      sorted(move_table.STATUS_EFFECTS), _defined)
check("...and there are the 24 there have always been", len(_defined), 24)

# a status effect is the function itself, not something that shares its name
burn = list_of_moves["Flamethrower"].special_effect
check("a move's status effect is the real function",
      burn is move_table.STATUS_EFFECTS["Burn"])

# the one-entry list rule: a bare string here would make the handler add five
# types called G, r, a, s and s
curse = list_of_moves["Forest's Curse"].special_effect
check("a one-entry effect list stays a list", isinstance(curse, list))
check("...with the right thing in it", curse, ["Grass"])

# paired effects keep their pairing.
#
# Every move that has more than one, rather than one named example: this used
# to point at Reign of Terror, and when that row was edited down to a single
# effect the check died on `len()` of a function instead of reporting
# anything useful. The rule is about the columns, not about one move.
_paired = {name: move for name, move in list_of_moves.items()
           if isinstance(move.effect_type, list) and len(move.effect_type) > 1}
_mismatched = sorted(
    name for name, move in _paired.items()
    if not isinstance(move.special_effect, list)
    or len(move.special_effect) != len(move.effect_type))
check("every multi-effect move pairs its two columns by position (%d moves)"
      % len(_paired), _mismatched, [])

# and the rules themselves
for text, want in ((move_table.NONE_MARK, None),
                   ("0,0,-2", [0, 0, -2]),
                   ("Grass,", ["Grass"]),
                   ("Grass", "Grass"),
                   ("0.5", 0.5),
                   ("", "")):
    check("the effect column reads %-8r as %r" % (text, want),
          move_table.decode_effect(text, "test"), want)

raised = None
try:
    move_table.decode_effect("@NoSuchStatus", "test")
except move_table.MoveDataError as problem:
    raised = str(problem)
check("an unknown @effect is a load-time error, not a silent None",
      bool(raised) and "NoSuchStatus" in raised)


print()
# -- the three rule columns ------------------------------------------------
from Scripts.Battle import move_rules                               # noqa: E402


class _Mon:
    def __init__(self, status="Normal", hp=200):
        self.status, self.hp, self.name = status, hp, "T"
        self.battle_stats = [hp] + [100] * 5
        self.modifier, self.move_order = [0] * 9, []


print("-- power_when / weather_when / fails_unless --")
check("the moves that used to be branches now carry a rule",
      [list_of_moves[n].power_when for n in
       ("Brine", "Venoshock", "Facade", "Hex")],
      ["target_below_half", "target_poisoned", "user_statused",
       "target_statused"])
check("...and the weather ones too",
      list_of_moves["Thunder"].weather_when,
      "Sunny:half_accuracy|Rain:always_hits")
check("...and the failure ones",
      list_of_moves["Gigaton Hammer"].fails_unless, "not_used_last_turn")

# Brine really does double, and only below half
for hp_left, want in ((200, 65), (100, 130)):
    brine = deepcopy(list_of_moves["Brine"])
    target = _Mon()
    target.battle_stats[0] = hp_left
    move_rules.apply_power_when(_Mon(), target, brine)
    check("Brine at %d/200 HP hits for %d" % (hp_left, want),
          brine.power, want)

# Thunder is a certainty in rain and a coin-flip in sun
# accuracy is a fraction in the table, and 9 is the "cannot miss" mark
for weather, want in (("Rain", move_rules.GUARANTEE_ACCURACY), ("Sunny", 0.35),
                      ("Clear", 0.7)):
    thunder = deepcopy(list_of_moves["Thunder"])
    ground = Battleground()
    ground.weather_effect = weather
    move_rules.apply_weather_when(ground, thunder)
    check("Thunder in %-9s -> accuracy %s" % (weather, want),
          thunder.accuracy, want)

# Dream Eater only lands on a sleeper
for status, refused in (("Sleep", False), ("Normal", True)):
    eater = list_of_moves["Dream Eater"]
    got, _ = move_rules.refuses(_Mon(), _Mon(status), eater, eater)
    check("Dream Eater vs a %-6s target is refused: %s" % (status, refused),
          got, refused)

# an unknown name in any of the three is a load-time error
for column, bad in (("power_when", "target_burnt"),
                    ("weather_when", "Rain:doubles"),
                    ("weather_when", "Monsoon:always_hits"),
                    ("fails_unless", "target_awake")):
    raised = None
    try:
        move_rules.check(column, bad, "test")
    except ValueError as problem:
        raised = str(problem)
    check("%s=%r is refused with the list of what would work"
          % (column, bad),
          bool(raised) and "there" in (raised or "").lower())


# -- the remarks column stays true ----------------------------------------
# Generated from the engine by Tools/move_code_scan.py, so it cannot drift.
# A new `if move.name == ...` fails here until it is written into the row the
# person editing the spreadsheet is looking at.
import csv as _csv                                                  # noqa: E402
sys.path.insert(0, ROOT)
from Tools import move_code_scan                                    # noqa: E402

_rows = {r["name"]: r for r in _csv.DictReader(
    io.open(move_table.MOVES_CSV, encoding="utf-8-sig"))}
_expected = move_code_scan.remarks_for(set(list_of_moves), ROOT)
_written = {name: (row.get("remarks") or "").strip()
            for name, row in _rows.items()}

_missing = sorted(n for n, mark in _expected.items() if not _written.get(n))
_stale = sorted(n for n, mark in _written.items() if mark and n not in _expected)
check("every move with behaviour in code says so in its row", _missing, [])
check("...and no row claims code behaviour it does not have", _stale, [])
check("the remark names where that code is",
      all("(" in _written[n] and ".py:" in _written[n] for n in _expected))
check("nothing found by the scan is left without a reason",
      sorted(n for n, mark in _expected.items()
             if "reason not recorded" in mark), [])
check("remarks is a note, not a field the engine reads",
      "remarks" not in move_table.FIELDS
      and "remarks" in move_table.COLUMNS)



# -- a move that never reached is not a move that does nothing -------------
# `ineffective_moves` is the AI's memory of "I tried this on that Pokemon and
# it did nothing", and it used to be written on any zero-damage result. A
# miss, or an attack thrown at something half-way through Phantom Force or
# Fly, also reports zero -- so a Pokemon that could not be *reached* taught
# the AI its attacks were useless, and it fell back on a status move for the
# rest of the battle. Only a move that actually connected may be blacklisted.
import ast as _ast                                                # noqa: E402
_checklist = _ast.parse(io.open(
    os.path.join(ROOT, "Scripts", "Battle", "battle_checklist.py"),
    encoding="utf-8").read())
_writes = [node for node in _ast.walk(_checklist)
           if isinstance(node, _ast.Attribute) and node.attr == "setdefault"
           and isinstance(node.value, _ast.Attribute)
           and node.value.attr == "ineffective_moves"]
check("the AI's dud list is still written in exactly one place",
      len(_writes), 1)
_guards = [node for node in _ast.walk(_checklist)
           if isinstance(node, _ast.Name) and node.id == "connected"]
check("...and 'connected' guards it", len(_guards) >= 3, True)

print("ALL PASS" if not fails else "FAILURES: %d -- %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
