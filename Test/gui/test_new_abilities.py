"""Memento, Outliers and Quantum Roll.

Three character abilities whose rules are all easy to get subtly wrong:

  Memento       fires on a *faint*, not on any switch-out
  Outliers      widens the damage roll, so the average must barely move
  Quantum Roll  seals three types for a turn, announces the next turn's
                three, never touches a status move, does nothing on turn 1,
                and always leaves one attack open

    python Test/gui/test_new_abilities.py <root> <out>
"""
import io
import math
import os
import random
import sys
from contextlib import redirect_stdout
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

import Scripts.Battle.battle_cycle                            # noqa: F401,E402
from Scripts.Battle.constants import ORDER_PHASE              # noqa: E402
from Scripts.Battle.context import Side, Turn                 # noqa: E402
from Scripts.Battle.switching import switching_mechanism      # noqa: E402
from Scripts.Data.battlefield import Battleground             # noqa: E402
from Scripts.Data.character_abilities import (                # noqa: E402
    OUTLIERS_BAND, QUANTUM_TYPES, UseCharacterAbility)
from Scripts.Data.competitors import list_of_competitors      # noqa: E402
from Scripts.Data.moves import list_of_moves                  # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon              # noqa: E402

fails = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(what)


field = [c for c in list_of_competitors.values() if not c.main]


def fresh(name):
    p = deepcopy(list_of_pokemon[name])
    p.hp = 200
    p.battle_stats = [200, 80, 80, 80, 80, 80]
    p.status = "Normal"
    p.nominal_base_stats = list(p.base_stats)
    p.default_name = p.name
    p.default_type = list(p.type)
    p.default_ability = list(p.ability)
    p.default_nominal_base_stats = list(p.base_stats)
    return p


def sides(ability):
    me, them = deepcopy(field[0]), deepcopy(field[1])
    me.ability, them.ability = ability, ""
    return me, them


# ------------------------------------------------------------------- Memento
print("-- Memento: on a faint, and only on a faint --")


def leaves(ability, fainted, boosts):
    me, them = sides(ability)
    out_mon = fresh("Scrafty")
    in_mon = fresh("Krookodile")
    foe = fresh("Pikachu")
    if fainted:
        out_mon.status = "Fainted"
        out_mon.battle_stats[0] = 0
    foe.modifier = list(boosts)
    team = [out_mon, in_mon]
    me.team, them.team = team, [foe]
    with redirect_stdout(io.StringIO()):
        switching_mechanism(me, them, Battleground(), team, [foe], 1, False)
    return foe.modifier


UP = [0, 2, 0, 2, 0, 0, 0, 0, 0]
check("a faint takes 2 off the foe's Attack and SpA",
      leaves("Memento", True, UP), [0, 0, 0, 0, 0, 0, 0, 0, 0])
check("...into the negatives when there was nothing to take",
      leaves("Memento", True, [0] * 9), [0, -2, 0, -2, 0, 0, 0, 0, 0])
check("a switch by choice does nothing", leaves("Memento", False, UP), UP)
check("and without the ability, a faint does nothing",
      leaves("", True, UP), UP)
check("it touches only Attack and SpA",
      [i for i, s in enumerate(leaves("Memento", True, [0] * 9)) if s], [1, 3])

# ------------------------------------------------------------------ Outliers
print()
print("-- Outliers: the band is wide and the mean now leans his way --")
check("the band is 0.8 to 1.5", OUTLIERS_BAND, (0.8, 1.5))
check("...which is wider than the engine's own 0.85-1.00",
      (OUTLIERS_BAND[1] - OUTLIERS_BAND[0]) > 0.15, True)
# The mean is deliberately above 1.0 now. Centred on it the ability measured
# at nothing -- 39.9%, 66th of 72 on ability alone, the same figure it scored
# in a run where it was unregistered and never fired -- because variance
# around an unchanged mean wins the battles it would have lost and loses the
# ones it would have won. The tilt is what makes it worth holding; the range
# either side of it is what makes it Kurtosis.
check("...and the mean now favours him rather than sitting on 1.0",
      1.10 < sum(OUTLIERS_BAND) / 2 < 1.20, True)

rolled = []
for seed in range(400):
    random.seed(seed)
    me, them = sides("Outliers")
    mine = fresh("Scrafty")
    foe = fresh("Pikachu")
    mv = deepcopy(list_of_moves["Thunderbolt"])
    mv.damage = 100
    turn = Turn(Battleground(), Side(me, [mine], mine), Side(them, [foe], foe))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, mv, abilityphase=4)
    rolled.append(mv.damage)
# Derived from OUTLIERS_BAND rather than written out. These were 69 and 135
# -- the old band's edges -- and retuning the band broke a test that was
# only ever restating the constant.
LOW, HIGH = (math.floor(100 * edge) for edge in OUTLIERS_BAND)
MEAN = 100 * sum(OUTLIERS_BAND) / 2
check("100 damage lands inside the band (%d..%d, allowed %d..%d)"
      % (min(rolled), max(rolled), LOW, HIGH),
      min(rolled) >= LOW and max(rolled) <= HIGH, True)
check("...and spans most of it",
      (max(rolled) - min(rolled)) > 0.7 * (HIGH - LOW), True)
# +/-5 of the band's own mean over 400 rolls: the standard error here is
# about 1, so this catches a shifted mean without failing on the noise.
check("...averaging near the band's mean of %d (%d)"
      % (MEAN, sum(rolled) // len(rolled)),
      abs(sum(rolled) / len(rolled) - MEAN) < 5, True)

# -------------------------------------------------------------- Quantum Roll
print()
print("-- Quantum Roll: three types, announced, attacks only --")
check("it seals three types", QUANTUM_TYPES, 3)


def quantum_battle(turns, foe_name="Scrafty"):
    """Run the ability through `turns` turns and hand back the state."""
    me, them = sides("Quantum Roll")
    mine = fresh("Alakazam")
    foe = fresh(foe_name)
    ground = Battleground()
    me.team, them.team = [mine], [foe]
    said = []
    for number in range(1, turns + 1):
        ground.turn = number
        turn = Turn(ground, Side(me, [mine], mine), Side(them, [foe], foe))
        text = io.StringIO()
        with redirect_stdout(text):
            UseCharacterAbility(turn, "", abilityphase=ORDER_PHASE)
        said.append(text.getvalue())
    return ground, me, them, mine, foe, said


def blocked(ground, me, them, mine, foe, move_name):
    """Does the foe's `move_name` get through to her Pokemon?

    Phase 3 is consulted from the *defender's* side -- the engine calls it as
    `UseCharacterAbility(turn.flip(), ...)` from inside the attacker's move,
    so by the time the ability runs, `user_side` is whoever is being aimed
    at. Building the turn with her on the user side is that same orientation.
    Flipping it here instead pointed the dispatcher at the attacker, who
    holds no ability -- so nothing fired and every check that expected "not
    blocked" passed for the wrong reason.
    """
    mv = deepcopy(list_of_moves[move_name])
    mv.accuracy = 1
    turn = Turn(ground, Side(me, [mine], mine), Side(them, [foe], foe))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, mv, abilityphase=3)
    return mv.accuracy == 0


ground, me, them, mine, foe, said = quantum_battle(1)
check("turn 1 seals nothing", ground.quantum["now"], set())
check("...but announces the three to come", len(ground.quantum["next"]), 3)
check("...and says so out loud", "refuses" in said[0])

ground, me, them, mine, foe, said = quantum_battle(2)
check("turn 2 seals what turn 1 announced", len(ground.quantum["now"]), 3)
check("...and rolled a fresh three for turn 3", len(ground.quantum["next"]), 3)

sealed_type = sorted(ground.quantum["now"])[0]
attack = next((n for n, m in list_of_moves.items()
               if m.type == sealed_type and m.attack_type != "Status"), None)
status = next((n for n, m in list_of_moves.items()
               if m.type == sealed_type and m.attack_type == "Status"), None)
if attack:
    check("a sealed type's attack is stopped (%s)" % attack,
          blocked(ground, me, them, mine, foe, attack))
if status:
    check("a sealed type's STATUS move still lands (%s)" % status,
          blocked(ground, me, them, mine, foe, status), False)
free = next((n for n, m in list_of_moves.items()
             if m.type and m.type not in ground.quantum["now"]
             and m.type != "Typeless" and m.attack_type != "Status"), None)
if free:
    check("an unsealed type is untouched (%s)" % free,
          blocked(ground, me, them, mine, foe, free), False)

# nobody is ever left with nothing to do
print()
print("-- and never a complete lockout --")
locked = 0
spared_ok = 0
for seed in range(200):
    random.seed(seed)
    me, them = sides("Quantum Roll")
    mine = fresh("Alakazam")
    foe = fresh("Scrafty")
    attacks = [n for n in foe.moveset
               if n in list_of_moves
               and list_of_moves[n].attack_type != "Status"]
    if not attacks:
        continue
    ground = Battleground()
    ground.turn = 1
    turn = Turn(ground, Side(me, [mine], mine), Side(them, [foe], foe))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, "", abilityphase=ORDER_PHASE)
    # force every one of the foe's attacks to be sealed on the next turn
    ground.quantum["next"] = set(list_of_moves[n].type for n in attacks)
    ground.turn = 2
    turn = Turn(ground, Side(me, [mine], mine), Side(them, [foe], foe))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, "", abilityphase=ORDER_PHASE)
    still = [n for n in attacks
             if not blocked(ground, me, them, mine, foe, n)]
    locked += 1
    if still:
        spared_ok += 1
check("with every attack sealed, one is always left open (%d of %d)"
      % (spared_ok, locked), spared_ok == locked and locked > 0, True)

# -------------------------------------------------------------- Pixelate
print()
print("-- Pixelate: Misty ground, and Normal comes out Fairy --")
from Scripts.Battle import terrain                             # noqa: E402
from Scripts.Data.character_abilities import PIXELATE_BOOST    # noqa: E402


BODY_SLAM = list_of_moves["Body Slam"].power
MOONBLAST = list_of_moves["Moonblast"].power
THUNDERBOLT = list_of_moves["Thunderbolt"].power


def pixelate_open(ability, move_name, opening_terrain=None):
    me, them = sides(ability)
    mine, foe = fresh("Sylveon"), fresh("Scrafty")
    ground = Battleground()
    ground.turn = 0
    if opening_terrain:
        ground.terrain = opening_terrain
        ground.terrain_turn = 5
    turn = Turn(ground, Side(me, [mine], mine), Side(them, [foe], foe))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, "", abilityphase=1)
    mv = deepcopy(list_of_moves[move_name])
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, mv, abilityphase=2)
    return terrain.current(ground), ground.terrain_turn, mv.type, mv.power


check("it opens the battle on Misty Terrain",
      pixelate_open("Pixelate", "Body Slam")[0], "Misty")
check("...for a full natural spell",
      pixelate_open("Pixelate", "Body Slam")[1], terrain.NATURAL_TURNS)
check("a Normal move comes out Fairy",
      pixelate_open("Pixelate", "Body Slam")[2], "Fairy")
check("...and any other type is left alone",
      pixelate_open("Pixelate", "Thunderbolt")[2], "Electric")
check("without it, no terrain and no retyping",
      pixelate_open("", "Body Slam"), ("None", 0, "Normal", BODY_SLAM))
# The boost follows the type she leaves moves in, not the type they came in
# as: a Fairy move of hers is boosted without being retyped, so a Fairy-type
# Pokemon on her team is helped by the ability rather than exempt from it.
check("a converted Normal move hits 1.2x harder",
      pixelate_open("Pixelate", "Body Slam")[3],
      math.floor(BODY_SLAM * PIXELATE_BOOST))
check("a move that was already Fairy is boosted too",
      pixelate_open("Pixelate", "Moonblast")[3],
      math.floor(MOONBLAST * PIXELATE_BOOST))
check("...and stays Fairy", pixelate_open("Pixelate", "Moonblast")[2], "Fairy")
check("a move of any other type keeps its power",
      pixelate_open("Pixelate", "Thunderbolt")[3], THUNDERBOLT)
check("without it, no boost either",
      pixelate_open("", "Moonblast")[3], MOONBLAST)
# It replaces whatever the arena rolled, which is the same thing Light Speed
# and Sparking Cascade do: these fire before turn 1 and set the ground the
# battle is fought on. A move laying terrain later runs on its own clock and
# overrides this in turn.
check("it replaces the terrain the arena rolled",
      pixelate_open("Pixelate", "Body Slam", "Grassy")[0], "Misty")
check("...and does not re-lay Misty over itself",
      pixelate_open("Pixelate", "Body Slam", "Misty")[1], 5)
# and never the shared table -- retyping an entry of list_of_moves would
# retype it for every Pokemon in the game, for good
pixelate_open("Pixelate", "Body Slam")
check("the shared move table is untouched",
      list_of_moves["Body Slam"].type, "Normal")

# ------------------------------------------------------------ Reflection
print()
print("-- Reflection: the better of the two, stat by stat, never HP --")
from Scripts.Battle.constants import FOE_ARRIVAL_PHASE          # noqa: E402


def statted(name):
    p = fresh(name)
    p.nominal_base_stats = list(p.base_stats)
    p.default_nominal_base_stats = list(p.base_stats)
    return p


def reflect(ability, hers, theirs, phase=1, wearing=None):
    me, them = sides(ability)
    a, b = statted(hers), statted(theirs)
    if wearing:
        a.nominal_base_stats = list(wearing)
    turn = Turn(Battleground(), Side(me, [a], a), Side(them, [b], b))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, "", abilityphase=phase)
    return a


weak, strong = "Sunkern", "Garchomp"
lifted = reflect("Reflection", weak, strong)
base = list(statted(weak).base_stats)
foe = list(statted(strong).base_stats)
check("every stat but HP becomes the higher of the two",
      lifted.nominal_base_stats[1:], [max(base[i], foe[i]) for i in range(1, 6)])
check("...and HP is left as her own",
      lifted.nominal_base_stats[0], base[0])
check("a stronger Pokemon of hers is not dragged down",
      reflect("Reflection", strong, weak).nominal_base_stats,
      list(statted(strong).base_stats))
check("without the ability nothing moves",
      reflect("", weak, strong).nominal_base_stats, base)

# it must not ratchet: one brush with a monster cannot be kept for the battle
kept = reflect("Reflection", weak, strong).nominal_base_stats
dropped = reflect("Reflection", weak, weak, phase=FOE_ARRIVAL_PHASE,
                  wearing=kept)
check("a weaker Pokemon switching in lowers her again",
      dropped.nominal_base_stats, base)
check("...which is read from her own defaults, not what she is wearing",
      dropped.nominal_base_stats != kept, True)
check("it recomputes when the opponent arrives, not only when she does",
      reflect("Reflection", weak, strong,
              phase=FOE_ARRIVAL_PHASE).nominal_base_stats[1:],
      [max(base[i], foe[i]) for i in range(1, 6)])

# ------------------------------------------------------------ Cross Court
print()
print("-- Cross Court: always the softer defence --")
from Scripts.Battle.damage_calculation import (                 # noqa: E402
    check_defense_strength)


def swings(ability, foe_name, move_name):
    me, them = sides(ability)
    a = fresh("Scrafty")
    b = fresh(foe_name)
    for mon in (a, b):
        mon.nominal_base_stats = list(mon.base_stats)
        mon.battle_stats = [200] + [mon.base_stats[i] for i in range(1, 6)]
    mv = deepcopy(list_of_moves[move_name])
    turn = Turn(Battleground(), Side(me, [a], a), Side(them, [b], b))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, mv, abilityphase=2)
    return (b.battle_stats[2], b.battle_stats[4],
            check_defense_strength(a, b, mv))


for foe in ("Ferrothorn", "Milotic", "Alakazam"):
    for move_name in ("Body Slam", "Thunderbolt"):
        defence, special, used = swings("Cross Court", foe, move_name)
        check("  %-11s %-11s hits the softer side (%d of %d/%d)"
              % (foe, move_name, used, defence, special),
              used, min(defence, special))

# and without it, the move goes where its own kind sends it
defence, special, used = swings("", "Ferrothorn", "Body Slam")
check("without the ability a physical move still hits Defense",
      used, defence)
defence, special, used = swings("", "Ferrothorn", "Thunderbolt")
check("...and a special one still hits Special Defense", used, special)

# status moves are not attacks and must be left alone
mv = deepcopy(list_of_moves["Growl"])
before = mv.inverseDef
me, them = sides("Cross Court")
a, b = fresh("Scrafty"), fresh("Ferrothorn")
for mon in (a, b):
    mon.nominal_base_stats = list(mon.base_stats)
    mon.battle_stats = [200] + [mon.base_stats[i] for i in range(1, 6)]
with redirect_stdout(io.StringIO()):
    UseCharacterAbility(Turn(Battleground(), Side(me, [a], a),
                             Side(them, [b], b)), mv, abilityphase=2)
check("a status move is left alone", mv.inverseDef, before)
check("the shared move table is untouched",
      list_of_moves["Body Slam"].inverseDef, False)

# ------------------------------------------------------------ Field Study
print()
print("-- Field Study: distinct species only --")
from Scripts.Data.character_abilities import (                  # noqa: E402
    FIELD_STUDY_CAP, FIELD_STUDY_STEP)


def study(arrivals, ability="Field Study"):
    me, them = sides(ability)
    mine = fresh("Yanmega")
    ground = Battleground()
    for name in arrivals:
        foe = fresh(name)
        turn = Turn(ground, Side(me, [mine], mine), Side(them, [foe], foe))
        with redirect_stdout(io.StringIO()):
            UseCharacterAbility(turn, "", abilityphase=FOE_ARRIVAL_PHASE)
    mv = deepcopy(list_of_moves["Bug Buzz"])
    mv.damage = 100
    foe = fresh(arrivals[-1])
    turn = Turn(ground, Side(me, [mine], mine), Side(them, [foe], foe))
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(turn, mv, abilityphase=4)
    return sorted(getattr(ground, "studied", set())), mv.damage


check("one specimen teaches her nothing", study(["Scrafty"])[1], 100)
check("a second species is worth one step",
      study(["Scrafty", "Pikachu"])[1],
      int(100 * (1 + FIELD_STUDY_STEP)))
check("a full varied team reaches the cap",
      study(["Scrafty", "Pikachu", "Milotic", "Onix", "Gengar",
             "Alakazam"])[1], int(100 * (1 + FIELD_STUDY_CAP)))
check("the cap and the step meet at six species",
      abs(FIELD_STUDY_STEP * 5 - FIELD_STUDY_CAP) < 1e-9, True)

# the point of keying on species: duplicates diminish her
check("three of the same Pokemon count once",
      study(["Scrafty", "Scrafty", "Scrafty"]), (["Scrafty"], 100))
check("...so a doubled team teaches her less than a varied one",
      study(["Scrafty", "Scrafty", "Pikachu"])[1]
      < study(["Scrafty", "Pikachu", "Milotic"])[1], True)
check("without the ability nothing is recorded and nothing changes",
      study(["Scrafty", "Pikachu", "Milotic"], ability=""), ([], 100))

# ------------------------------------------------------------- Groundwork
print()
print("-- Groundwork: rocks on the far side, and only the far side --")
from Scripts.Battle.entry_hazard import entry_hazard_effect   # noqa: E402
from Scripts.Data.character_abilities import (                # noqa: E402
    GROUNDWORK_LAYERS)


def opens(ability, turn=0, already=0):
    """What each side's field holds after her ability gets its phase 1."""
    me, them = sides(ability)
    mine, foe = fresh("Rhyperior"), fresh("Pikachu")
    ground = Battleground()
    ground.turn = turn
    them.entry_hazard["Stealth Rock"] = already
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(Turn(ground, Side(me, [mine], mine),
                                 Side(them, [foe], foe)), "", abilityphase=1)
    return them.entry_hazard["Stealth Rock"], me.entry_hazard["Stealth Rock"]


check("the opening lays rock on the opponent's field",
      opens("Groundwork")[0], GROUNDWORK_LAYERS)
# the trap this ability could most easily fall into: a side's own
# entry_hazard is what its own arrivals walk into, so writing to the wrong
# one would have her paying for her own ability every switch
check("...and none whatsoever on her own",
      opens("Groundwork")[1], 0)
check("without the ability, no rock either", opens(""), (0, 0))
# turn 0 only, so Rapid Spin, Gluttony and Infiltration all still answer it
check("it is not re-laid once the battle is under way",
      opens("Groundwork", turn=3)[0], 0)
check("...and never stacks past the move's own cap",
      opens("Groundwork", already=1)[0], 1)

# and the rocks are real: an arriving Pokemon actually pays for them
def arrives(ability, name="Pikachu"):
    me, them = sides(ability)
    mine, foe = fresh("Rhyperior"), fresh(name)
    ground = Battleground()
    with redirect_stdout(io.StringIO()):
        UseCharacterAbility(Turn(ground, Side(me, [mine], mine),
                                 Side(them, [foe], foe)), "", abilityphase=1)
    before = foe.battle_stats[0]
    entry_hazard_effect(them, foe)
    return before - foe.battle_stats[0]


check("an opponent switching in pays an eighth of its health",
      arrives("Groundwork"), 25)             # 200 hp, neutral to Rock
# Charizard is doubly weak to Rock, and Stealth Rock reads the type chart
check("...and four times that when it is doubly weak to Rock",
      arrives("Groundwork", "Charizard"), 100)
check("without the ability, arriving costs nothing", arrives(""), 0)

print()
print("ALL PASS" if not fails else "FAILURES: %s" % ", ".join(fails))
sys.exit(1 if fails else 0)
