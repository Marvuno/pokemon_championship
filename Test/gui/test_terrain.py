"""The four terrains, and the one rule that makes them different from weather.

Weather is in the air and touches everything. Terrain is underfoot, so a
Flying-type, a Levitate holder or anything half-way through Fly is untouched
by all of it -- the boost, the healing and the protection alike. Every check
below that says "from the air" is testing that.

Terrain is also its own layer: it lives in `battleground.terrain`, not inside
`field_effect` next to Trick Room, because in the real games Rain and
Electric Terrain and Trick Room can all be up at once and only members of the
same layer replace each other.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                                 # noqa: F401,E402
from Scripts.Battle import terrain as TR                            # noqa: E402
from Scripts.Data.battlefield import Battleground                   # noqa: E402
from Scripts.Data.moves import list_of_moves                        # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                    # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


class Mon:
    def __init__(self, types, hp=100, grounded=1, ability=None):
        self.type = list(types)
        self.hp = hp
        self.battle_stats = [hp // 2] + [100] * 5
        self.status = "Normal"
        self.ability = list(ability or [])
        self.volatile_status = {"Grounded": grounded}
        self.charging = ["", "", 0]
        self.name = "Test"


ground = Mon(["Electric"])
flier = Mon(["Flying"])
floater = Mon(["Electric"], ability=["Levitate"])
flying_now = Mon(["Electric"])
flying_now.charging = ["Fly", "Semi-invulnerable", 1]

print("-- who is standing on it --")
check("a normal Pokemon is", TR.is_grounded(ground))
check("a Flying-type is not", TR.is_grounded(flier), False)
check("a Levitate holder is not", TR.is_grounded(floater), False)
check("something half-way through Fly is not",
      TR.is_grounded(flying_now), False)

print()
print("-- laying it, and it lapsing --")
field = Battleground()
check("a fresh field has none", field.terrain, "None")
check("laying one says so",
      bool(TR.set_terrain(field, "Electric")))
check("...and it is up for five turns",
      (field.terrain, field.terrain_turn), ("Electric", 5))
check("laying the same one again fails rather than refreshing",
      TR.set_terrain(field, "Electric"), "")
check("a different one replaces it",
      bool(TR.set_terrain(field, "Grassy")) and field.terrain == "Grassy")
for _ in range(4):
    TR.tick(field)
check("four turns later it is still there", field.terrain, "Grassy")
check("the fifth lifts it", bool(TR.tick(field)))
check("...leaving none", (field.terrain, field.terrain_turn), ("None", 0))
check("only the four real terrains exist, plus None",
      TR.TERRAINS, ("None", "Electric", "Grassy", "Misty", "Psychic"))

print()
print("-- the boost, and who gets it --")
bolt = list_of_moves["Thunderbolt"]
field.terrain = "Electric"
check("Electric Terrain lifts an Electric move",
      TR.move_multiplier(field, ground, ground, bolt), TR.BOOST)
check("...only for something standing on it",
      TR.move_multiplier(field, flier, ground, bolt), 1)
check("...and leaves other types alone",
      TR.move_multiplier(field, ground, ground,
                         list_of_moves["Flamethrower"]), 1)
field.terrain = "Grassy"
check("Grassy Terrain lifts a Grass move",
      TR.move_multiplier(field, ground, ground,
                         list_of_moves["Leaf Blade"]), TR.BOOST)
check("...and muffles Earthquake",
      TR.move_multiplier(field, ground, ground,
                         list_of_moves["Earthquake"]), TR.BLUNT)
field.terrain = "Misty"
check("Misty Terrain halves Dragon moves at the ground",
      TR.move_multiplier(field, ground, ground,
                         list_of_moves["Dragon Pulse"]), TR.BLUNT)
check("...but not at something in the air",
      TR.move_multiplier(field, ground, flier,
                         list_of_moves["Dragon Pulse"]), 1)
field.terrain = "None"
check("no terrain, no change",
      TR.move_multiplier(field, ground, ground, bolt), 1)

print()
print("-- protection --")
field.terrain = "Misty"
check("Misty refuses every status", TR.blocks_status(field, ground,
                                                     "Poison")[0])
check("...and confusion too", TR.blocks_confusion(field, ground))
check("...but not for a flier", TR.blocks_status(field, flier, "Poison")[0],
      False)
check("Normal is not a status to refuse",
      TR.blocks_status(field, ground, "Normal")[0], False)
field.terrain = "Electric"
check("Electric refuses sleep", TR.blocks_status(field, ground, "Sleep")[0])
check("...and nothing else", TR.blocks_status(field, ground, "Burn")[0],
      False)
field.terrain = "Psychic"
priority = next(m for m in list_of_moves.values()
                if getattr(m, "priority", 0) > 0)
check("Psychic refuses a priority move",
      TR.blocks_priority(field, ground, priority))
check("...aimed at the ground only",
      TR.blocks_priority(field, flier, priority), False)
check("...and lets an ordinary move through",
      TR.blocks_priority(field, ground, list_of_moves["Flamethrower"]),
      False)

print()
print("-- Grassy Terrain heals --")
field.terrain = "Grassy"
hurt = Mon(["Electric"], hp=160)
hurt.battle_stats[0] = 80
check("a grounded Pokemon gets a sixteenth back",
      TR.end_of_turn_heal(field, hurt), 160 // TR.HEAL_FRACTION)
check("a flier gets nothing", TR.end_of_turn_heal(field, flier), 0)
full = Mon(["Electric"], hp=160)
full.battle_stats[0] = 160
check("a full Pokemon gets nothing", TR.end_of_turn_heal(field, full), 0)
down = Mon(["Electric"], hp=160)
down.status = "Fainted"
check("a fainted one is not revived", TR.end_of_turn_heal(field, down), 0)

print()
print("-- the moves that lay it --")
for name, laid in (("Electric Terrain", "Electric"),
                   ("Grassy Terrain", "Grassy"),
                   ("Misty Terrain", "Misty"),
                   ("Psychic Terrain", "Psychic")):
    move = list_of_moves.get(name)
    check("%s is in the table" % name, move is not None)
    if move is not None:
        check("...as a terrain-laying Status move",
              (move.effect_type, move.special_effect, move.attack_type),
              ("terrain", laid, "Status"))

holders = {name: [p for p, mon in list_of_pokemon.items()
                  if name in (mon.moveset or [])]
           for name in ("Electric Terrain", "Grassy Terrain",
                        "Misty Terrain", "Psychic Terrain")}
check("something knows each of them, or terrain never happens",
      sorted(n for n, who in holders.items() if not who), [])
for name, who in sorted(holders.items()):
    print("   %-17s %s" % (name, ", ".join(who)))

print()
print("-- the ground a battle opens on --")
import collections                                                  # noqa: E402
import random                                                       # noqa: E402

random.seed(7)
tally = collections.Counter()
turns = set()
for _ in range(20000):
    field = Battleground()
    said = TR.roll_natural(field)
    tally[field.terrain] += 1
    if field.terrain != "None":
        turns.add(field.terrain_turn)
        if not said:
            FAILURES.append("a terrain arrived without saying so")
    elif said:
        FAILURES.append("no terrain but something was said")

check("each terrain is close to %d%%" % TR.NATURAL_CHANCE,
      all(abs(100.0 * tally[name] / 20000 - TR.NATURAL_CHANCE) < 1
          for name in TR.TERRAINS[1:]))
check("...so about four battles in five open on none",
      abs(100.0 * tally["None"] / 20000 - 80) < 2)
check("every terrain does turn up", sorted(tally) == sorted(TR.TERRAINS))
check("one that turns up lasts ten turns, not a move's five",
      turns, {TR.NATURAL_TURNS})
check("...which is longer than a move lays it",
      TR.NATURAL_TURNS > TR.TERRAIN_TURNS)
for name in TR.TERRAINS:
    print("   %-9s %5.2f%%" % (name, 100.0 * tally[name] / 20000))

# it lapses, unlike the arena's own weather
field = Battleground()
field.terrain, field.terrain_turn = "Grassy", TR.NATURAL_TURNS
for _ in range(TR.NATURAL_TURNS - 1):
    TR.tick(field)
check("nine turns in, the opening terrain is still there",
      field.terrain, "Grassy")
check("the tenth lifts it", bool(TR.tick(field)) and field.terrain == "None")

# a move can still replace it, and then it runs on a move's clock
field = Battleground()
TR.roll_natural(field)
field.terrain, field.terrain_turn = "Grassy", TR.NATURAL_TURNS
TR.set_terrain(field, "Misty")
check("a move overrides the ground it opened on",
      (field.terrain, field.terrain_turn), ("Misty", TR.TERRAIN_TURNS))

print()
print("-- terrain is its own layer --")
field = Battleground()
TR.set_terrain(field, "Electric")
field.weather_effect = "Rain"
field.field_effect["Trick Room"] = 4
check("weather, terrain and a room coexist",
      (field.weather_effect, field.terrain, field.field_effect["Trick Room"]),
      ("Rain", "Electric", 4))
check("and terrain is not hiding inside field_effect",
      "Electric" in field.field_effect, False)

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
