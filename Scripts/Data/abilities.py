"""Firing the right ability at the right moment.

This file was 1,064 lines, of which about 950 were 153 ability bodies nested
inside `UseAbility` as closures. They are in Scripts/Battle/ability_effects.py
now, one named module-level function each, and this is only the dispatcher.

The bodies had to be nested because they read six names -- both trainers, both
active Pokemon, the battleground and the move -- straight out of the enclosing
scope instead of taking arguments. `AbilityCall` carries those six, so they no
longer have to be inside anything.

To add an ability, edit ability_effects.py. Nothing here needs to change.
"""
import math
import operator
from contextlib import suppress

# These star imports are not for this module -- it uses almost none of them.
# Nine other modules do `from Scripts.Data.abilities import *` and have been
# picking up modifierChart, typeChart, list_of_moves and the rest through
# here for as long as that has been true. Dropping them breaks
# damage_calculation at the first critical hit. Untangling that is its own
# job; this file's job is dispatch, and it keeps its exported surface.
from Scripts.Art.text_color import *
from Scripts.Data.moves import *
from Scripts.Data.pokemon import *
from Scripts.Battle.type_chart import *
from Scripts.Battle.type_immunity import *
from Scripts.Battle.context import Side, Turn
from Scripts.Battle.constants import has_ability

from Scripts.Battle.ability_effects import REGISTRY, AbilityCall

#: the old name for the registry, kept because it reads well at call sites
#: and because "list of abilities" is what it is
list_of_abilities = REGISTRY


#: the nine moments an ability can fire on. Named because "abilityphase=7"
#: at a call site says nothing on its own.
PHASES = {1: "switching in", 2: "using a move", 3: "being targeted",
          4: "dealing damage", 5: "taking damage", 6: "after dealing damage",
          7: "after taking damage", 8: "end of turn", 9: "switching out"}

#: Abilities a Pokemon actually holds that have NO entry in the registry, and
#: why. These do nothing whatsoever in a battle.
#:
#: Declared here rather than discovered at runtime, so that a *new* one is a
#: test failure instead of a Pokemon quietly playing with no ability. This
#: replaces a `usage.update({'Surge Surfer': 0})` line in the debug read-out,
#: which stopped that read-out raising KeyError without recording why.
KNOWN_INERT = {
    "Surge Surfer": "doubles Speed on Electric Terrain, and this game has no "
                    "terrain. Alolan Raichu holds it and nothing else, so it "
                    "plays with no ability at all -- while ability_text.py "
                    "still promises the player it does something.",
}


def problems():
    """Everything wrong with the registry, as a list of sentences.

    Read by Test/gui/test_ability_registry.py. The checks are here rather
    than in the test because they are statements about the data, and the next
    person to add an ability should find them next to the registry.
    """
    from Scripts.Data.pokemon import list_of_pokemon
    found = []

    for name, entry in REGISTRY.items():
        if not (2 <= len(entry) <= 3):
            found.append("%s: registry entry has %d parts, expected 2 or 3"
                         % (name, len(entry)))
            continue
        for phase in _phases_of(entry[0]):
            if phase not in PHASES:
                found.append("%s: fires on phase %r, which does not exist"
                             % (name, phase))
        if not callable(entry[1]):
            found.append("%s: second part is not a function" % name)
        if len(entry) == 3 and entry[2] != "Custom":
            found.append("%s: third part is %r, expected 'Custom'"
                         % (name, entry[2]))

    held = {ability for mon in list_of_pokemon.values()
            for ability in (getattr(mon, "ability", None) or [])}
    for name in sorted(held - set(REGISTRY) - set(KNOWN_INERT)):
        found.append("%s: held by a Pokemon but not registered, so it does "
                     "nothing. Add it to ability_effects.py, or to "
                     "KNOWN_INERT with the reason." % name)
    for name in sorted(set(KNOWN_INERT) - held):
        found.append("%s: listed in KNOWN_INERT but no Pokemon holds it any "
                     "more -- drop the entry." % name)
    return found


def _phases_of(spec):
    """The registry stores either one phase or a tuple of them."""
    return spec if isinstance(spec, tuple) else (spec,)


#: ability name -> the phases it fires on. Derived from the registry rather
#: than written out, so it cannot disagree with it.
_ABILITY_PHASES = {name: _phases_of(entry[0])
                   for name, entry in REGISTRY.items()}


def _fires(pokemon, phase):
    """Has this Pokemon any ability with something to do this phase?

    Worth asking before anything else: a Pokemon has one or two abilities and
    there are nine phases, so the overwhelming majority of the ~6,500 calls a
    five-battle stretch makes have no work at all.

    getattr rather than attribute access because the dispatch below runs
    inside suppress(KeyError, AttributeError) -- callers may hand this a
    Pokemon with no ability attribute, and that has always been tolerated.
    """
    held = getattr(pokemon, "ability", None) or []
    if not isinstance(held, list):
        held = [held]
    return any(phase in _ABILITY_PHASES.get(name, ()) for name in held)


def UseAbility(turn, move="", abilityphase=1, verbose=False):
    """Fire whichever of this Pokemon's abilities match this phase.

    `turn` is the battle from the point of view of the Pokemon whose ability
    this is -- see Scripts/Battle/context.py. Callers that mean "the ability
    of the Pokemon being hit" pass `turn.flip()` rather than reordering six
    arguments, which is what the old signature made them do.
    """
    if verbose:
        _describe()
        return

    if not _fires(turn.user.active, abilityphase):
        return

    with suppress(KeyError, AttributeError):
        if move.ignoreAbility:
            return

    call = None
    with suppress(KeyError, AttributeError):
        for ability in turn.user.active.ability:
            phases, effect = REGISTRY[ability][0], REGISTRY[ability][1]
            if abilityphase in _phases_of(phases):
                if call is None:
                    call = AbilityCall(turn, move, abilityphase)
                effect(call)


def _describe():
    """The debug read-out: what is registered, and who has what."""
    custom = sum(1 for values in REGISTRY.values() if len(values) == 3)
    print(f"\n{CBOLD}Total Number of Abilities: {len(REGISTRY)}\n"
          f"Custom: {custom}{CEND}")
    for name, values in REGISTRY.items():
        if len(values) == 3 and values[2] == "Custom":
            print(f"{CYELLOW2}{name}{CEND}")

    print(f"\n\n{CBOLD}Ability Usage: {CEND}\n")
    usage = dict.fromkeys(REGISTRY, 0)
    usage.update(dict.fromkeys(KNOWN_INERT, 0))
    for pokemon in list_of_pokemon:
        for ability in list_of_pokemon[pokemon].ability:
            usage[ability] += 1
    for ability, count in sorted(usage.items(), key=lambda item: item[1]):
        print(f"{ability}: {count}")
