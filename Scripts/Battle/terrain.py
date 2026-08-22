"""The four terrains, and what standing on one does.

Terrain is its **own field layer**, not a kind of weather and not a member of
`field_effect`. In the real games weather, terrain and rooms occupy separate
slots: Rain, Electric Terrain and Trick Room can all be up at once, and only
members of the same layer replace each other. Putting terrain into
`field_effect` alongside Trick Room would have made those two mutually
exclusive, which is wrong -- hence `battleground.terrain`, on its own.

The one rule that makes terrain different from weather: **it only reaches
Pokemon standing on it.** Weather is in the air and touches everything;
terrain is underfoot, so a Flying-type, a Levitate holder or anything
half-way through Fly is untouched by all of it -- the boost, the healing and
the protection alike.

    Electric   Electric moves x1.3; nothing on the ground can fall asleep
    Grassy     Grass moves x1.3; the ground heals 1/16 a turn; quakes halved
    Misty      no status and no confusion on the ground; Dragon moves halved
    Psychic    Psychic moves x1.3; priority moves cannot touch the ground

The multiplier is 1.3, which is what it has been since Generation 7 (it was
1.5 when terrain was introduced).

Terrain arrives two ways, and they last different lengths:

    a move lays it            5 turns   (Electric Terrain and its three kin)
    the battle opens on it   10 turns   (5% chance each, so 1 battle in 5)

The second is this game's own, not a mechanic from the series -- the same
idea as the arena rolling its own weather in `battle_setup`. It is longer
because it is the ground the battle is fought on rather than something
somebody spent a turn on. Unlike the arena's own *weather*, which never
lifts, it does lapse: `tick` counts both kinds down the same way.
"""
import math
import random

from Scripts.Battle.constants import has_ability

#: what may be in `battleground.terrain`. "None" is a terrain like Clear is a
#: weather -- a real value, not a missing one.
TERRAINS = ("None", "Electric", "Grassy", "Misty", "Psychic")
#: how long one lasts once a move lays it
TERRAIN_TURNS = 5
#: how long an arena's own terrain lasts. Longer than a move's, because it
#: is the ground the battle opens on rather than something somebody spent a
#: turn on -- it shapes the early game and then fades.
NATURAL_TURNS = 10
#: the chance, in percent, of each terrain being there when a battle starts.
#: Four terrains at 5 means one in five battles opens on some terrain, and
#: four in five on none.
NATURAL_CHANCE = 5

#: Terrain-laying moves that no Pokemon in this roster learns, and are
#: therefore reachable only by the arena's own opening roll.
#:
#: Declared rather than left to be noticed, the same bargain as KNOWN_INERT
#: in abilities.py: a move nobody can use is either a deliberate gap or an
#: editing accident, and the two look identical from the outside. Sylveon
#: carried Misty Terrain for a while and does not any more -- that is the
#: designer's call, so it is written down here instead of being quietly
#: handed to another Fairy.
#:
#: Give it to somebody and delete the entry; `test_terrain` fails on a
#: terrain move that is *neither* learnable nor listed here.
UNLEARNED = {
    "Misty Terrain": "no Fairy in the roster carries it; the arena's own "
                     "opening roll is the only way it happens",
}
#: what a terrain does to the type it favours
BOOST = 1.3
#: and what it does to the type it blunts
BLUNT = 0.5
#: Grassy Terrain's end-of-turn healing, as a fraction of full HP
HEAL_FRACTION = 16

#: terrain -> the move type it strengthens
FAVOURS = {"Electric": "Electric", "Grassy": "Grass", "Psychic": "Psychic"}
#: the ground-shaking moves Grassy Terrain muffles
MUFFLED = ("Earthquake", "Bulldoze", "Magnitude")

TERRAIN_ARRIVES = {
    "Electric": "An electric current runs across the field!",
    "Grassy": "Grass grows to cover the field!",
    "Misty": "Mist swirls up around the field!",
    "Psychic": "The field gets weird!",
}
TERRAIN_LEAVES = {
    "Electric": "The electricity disappeared from the field.",
    "Grassy": "The grass disappeared from the field.",
    "Misty": "The mist disappeared from the field.",
    "Psychic": "The weirdness disappeared from the field.",
}
#: one line each, for the field strip's tooltip
TERRAIN_NOTE = {
    "None": "Nothing underfoot.",
    "Electric": "Electric moves hit harder. Nothing on the ground can be "
                "put to sleep.",
    "Grassy": "Grass moves hit harder and the ground heals every turn. "
              "Earthquake and its kind are halved.",
    "Misty": "Nothing on the ground can be statused or confused. Dragon "
             "moves are halved.",
    "Psychic": "Psychic moves hit harder. Priority moves cannot reach "
               "anything on the ground.",
}


def is_grounded(pokemon):
    """Is this Pokemon actually standing on the terrain?

    Flying-types and Levitate are off the ground by nature; the engine also
    tracks it per-Pokemon in `volatile_status['Grounded']`, which switching
    sets and Levitate clears, and a Pokemon half-way through Fly or Bounce is
    in the air for the turn.
    """
    if pokemon is None:
        return False
    if "Flying" in (getattr(pokemon, "type", None) or []):
        return False
    if has_ability(pokemon, "Levitate"):
        return False
    volatile = getattr(pokemon, "volatile_status", None) or {}
    if volatile.get("Grounded", 1) <= 0:
        return False
    charging = getattr(pokemon, "charging", None) or ["", "", 0]
    if charging[1] == "Semi-invulnerable" and charging[0] in ("Fly", "Bounce"):
        return False
    return True


def current(battleground):
    """The terrain in force, tolerating a battleground built before this
    existed -- the AI copies grounds around, and a save can predate it."""
    return getattr(battleground, "terrain", "None") or "None"


def move_multiplier(battleground, user, target, move):
    """What the terrain does to this move's damage."""
    terrain = current(battleground)
    if terrain == "None":
        return 1
    factor = 1
    if (FAVOURS.get(terrain) == move.type and is_grounded(user)):
        factor *= BOOST
    if terrain == "Grassy" and move.name in MUFFLED:
        factor *= BLUNT
    if terrain == "Misty" and move.type == "Dragon" and is_grounded(target):
        factor *= BLUNT
    return factor


def blocks_status(battleground, target, status):
    """(True, why) when the terrain refuses this status outright."""
    terrain = current(battleground)
    if not is_grounded(target):
        return False, ""
    if terrain == "Misty" and status not in ("Normal", "Fainted"):
        return True, "The mist protects %s from status conditions!"
    if terrain == "Electric" and status == "Sleep":
        return True, "The electric current keeps %s awake!"
    return False, ""


def blocks_confusion(battleground, target):
    """Misty Terrain stops confusion as well as the real statuses."""
    return current(battleground) == "Misty" and is_grounded(target)


def blocks_priority(battleground, target, move):
    """Psychic Terrain refuses a priority move aimed at the ground."""
    return (current(battleground) == "Psychic"
            and getattr(move, "priority", 0) > 0
            and is_grounded(target))


def end_of_turn_heal(battleground, pokemon):
    """How much Grassy Terrain gives this Pokemon back, if anything."""
    if current(battleground) != "Grassy" or not is_grounded(pokemon):
        return 0
    if pokemon.status == "Fainted" or pokemon.battle_stats[0] <= 0:
        return 0
    return min(pokemon.hp - pokemon.battle_stats[0],
               math.floor(pokemon.hp / HEAL_FRACTION))


def set_terrain(battleground, terrain):
    """Lay a terrain, replacing whatever was there. Returns what to say.

    Setting the terrain that is already up refreshes nothing -- the real
    games fail the move -- so this reports that instead.
    """
    if terrain not in TERRAINS:
        raise ValueError("no terrain called %r. There is: %s"
                         % (terrain, ", ".join(TERRAINS)))
    if current(battleground) == terrain and terrain != "None":
        return ""
    battleground.terrain = terrain
    battleground.terrain_turn = 0 if terrain == "None" else TERRAIN_TURNS
    return TERRAIN_ARRIVES.get(terrain, "")


def roll_natural(battleground):
    """The ground this battle happens to open on. Returns what to say.

    Each terrain at NATURAL_CHANCE percent, so most battles open on none.
    Rolled the same way `battle_setup` rolls the weather -- one
    `random.choices` with weights -- so the two read alike at the call site.

    It lasts NATURAL_TURNS rather than a move's five, and unlike the arena's
    own *weather* it does lapse: `tick` counts it down like any other.
    """
    weights = [100 - NATURAL_CHANCE * (len(TERRAINS) - 1)]
    weights += [NATURAL_CHANCE] * (len(TERRAINS) - 1)
    chosen = random.choices(list(TERRAINS), weights=weights, k=1)[0]
    battleground.terrain = chosen
    battleground.terrain_turn = 0 if chosen == "None" else NATURAL_TURNS
    return "" if chosen == "None" else TERRAIN_ARRIVES.get(chosen, "")


def tick(battleground):
    """Count the terrain down a turn. Returns what to say when it lapses."""
    if current(battleground) == "None":
        return ""
    battleground.terrain_turn = getattr(battleground, "terrain_turn", 0) - 1
    if battleground.terrain_turn > 0:
        return ""
    gone = current(battleground)
    battleground.terrain = "None"
    battleground.terrain_turn = 0
    return TERRAIN_LEAVES.get(gone, "")
