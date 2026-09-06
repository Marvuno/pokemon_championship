"""What a trainer knows about the Pokemon in front of them.

The AI has always read the opponent's exact moveset and ability straight off
the object, from turn one, which no player can do. Measured over 600 battles
an arm, that is worth more than anything else about the AI:

    knows everything (what shipped)         50.0%
    knows the species pool, learns by use   46.4%   -3.6
    knows nothing, learns by use            44.1%   -5.9
    ...and the ability hidden too           41.7%   -8.3

For scale, the whole gap between the smart AI and the dumb one is 3.7 points,
and a complete re-architecture of the move scorer was worth zero. Information
is the only lever on this AI that measures large, which is why the difficulty
ladder is built out of it rather than out of making low-tier trainers think
badly. A weak trainer here is *fallible* -- playing well on poor information
-- rather than stupid, which is the difference between a character and a bug.

Three rungs, by the competitor's own tier:

    Low                     nothing. Every unseen slot is a Typeless 80, the
                            ability is unknown, and the stat line is read off
                            the species with no IVs. Learns each move the
                            first time it lands.
    Intermediate            what it *is*, not what it has. Knows the typing,
                            so unseen slots are attacks of the Pokemon's own
                            types -- all of them, cycled. The ability is still
                            unknown and the stat line is still the species'
                            own. Learns the actual four by watching.
    Advanced/Elite/Champion everything: the exact four moves, the exact
                            ability, and the exact stat line including the
                            IVs it was raised with. Earned by rank rather
                            than given to everyone.

Character abilities are tiered on the same line: Advanced and above play
around the opponent's, Low and Intermediate do not know it is there.

Nothing here is expensive. The pool is `list_of_pokemon[species].moveset`,
which the game already loads; what has been revealed is `move_order`, which
the engine already appends to on every use. There is no belief state to keep,
nothing to persist, and nothing to reset between battles.
"""
#: The three rungs, weakest first.
BLIND, POOL, FULL = 0, 1, 2

#: Which rung each competitor tier stands on. Keyed by the `Level` column of
#: Data/competitors.csv, so adding a tier there is the only edit needed.
BY_LEVEL = {
    "Low": BLIND,
    "Intermediate": POOL,
    "Advanced": FULL,
    "Elite": FULL,
    "Champion": FULL,
}

#: Tiers that also see the opponent's *character* ability and can play around
#: it. Below this the AI scores as though the opponent had none.
SEES_CHARACTER_ABILITY = (FULL,)

#: What an unseen slot is assumed to be. It has to be something: handed an
#: empty moveset the AI computes zero incoming damage, concludes it cannot be
#: hurt, and plays recklessly -- so "unknown" must mean "assume an ordinary
#: attack", which is what a person assumes too.
#:
#: **Typeless, not Normal.** This was Body Slam, and a real move carries a real
#: type, which quietly reintroduces the exact bug the prior exists to prevent:
#: Ghost is immune to Normal, so a blind trainer facing a Gengar read three of
#: its four unseen slots as zero damage and went right back to concluding it
#: could not be hurt. The engine already carries a `Typeless` entry in the
#: chart that is 1.0 against all nineteen types -- the only one that is -- and
#: that is what "some attack, I do not know what" should mean.
#:
#: 80 power and 100% accurate: an unremarkable attack, deliberately. A
#: stronger stand-in makes a blind trainer over-fear every unseen slot and
#: play *more* cautiously, narrowing the gap to a knowing one; a weaker one
#: makes it reckless and widens it.
UNKNOWN_POWER = 80

#: Slots are named rather than filled with a real move, so nothing can confuse
#: a placeholder with a move the Pokemon genuinely has. The type rides on the
#: name because it is what separates the two lower rungs -- see `assumed_type`.
UNKNOWN_PREFIX = "<unknown:"


def unknown_slot(type_name):
    """The name of a placeholder slot of the given type."""
    return "%s%s>" % (UNKNOWN_PREFIX, type_name)


def slot_type(name):
    """The type carried by a placeholder name, or None if it is a real move."""
    if isinstance(name, str) and name.startswith(UNKNOWN_PREFIX):
        return name[len(UNKNOWN_PREFIX):-1]
    return None

#: The rung used when a trainer has no tier at all -- the player, and anything
#: constructed by a harness. Full sight, which is the behaviour that shipped,
#: so nothing changes for anyone this table does not name.
DEFAULT = FULL


def _own_types(foe):
    """Every type an unseen move might be, for a trainer who knows the species.

    All of them, not just the primary: a Ground/Rock Pokemon is a threat on
    both counts and a trainer reading it on sight knows that much.
    """
    kinds = [t for t in (getattr(foe, "type", []) or []) if t]
    return kinds or ["Typeless"]


def believed_stats(foe, level, base_stats_of):
    """The stat line this trainer credits the Pokemon with.

    Below full sight: the species' own base stats, with no IVs. You can see
    *what* is standing there -- the sprite is on screen -- so the species row
    is fair knowledge; how well this particular individual was raised is not.
    That shifts both halves of the read at once: which one outruns the other,
    and which of its attacks lands harder.

    Returns None at full sight, meaning "use the real line, IVs and all".

    Only ever applied to the *opponent*. A trainer knows their own Pokemon.
    """
    if level >= FULL:
        return None
    return list(base_stats_of(getattr(foe, "name", "")) or [])


def rung(trainer):
    """Which rung this trainer stands on."""
    return BY_LEVEL.get(str(getattr(trainer, "level", "") or ""), DEFAULT)


def sees_character_ability(trainer):
    """Does this trainer play around the opponent's character ability?"""
    return rung(trainer) in SEES_CHARACTER_ABILITY


def believed_moveset(foe, level, pool_of, known_moves):
    """The moveset this trainer believes the Pokemon in front of them holds.

    `pool_of(species_name)` yields the species movepool, `known_moves` is the
    set of move names already used in this battle. Revealed moves are always
    believed exactly -- watching something happen is the one form of knowledge
    every rung has.
    """
    actual = list(getattr(foe, "moveset", []))
    if level >= FULL:
        return actual

    seen = [name for name in getattr(foe, "move_order", []) if name in actual]
    if level == POOL:
        # Knows *what it is*, not what it has. A Pokedex tells you the
        # species' typing and its abilities; it does not tell you which four
        # moves this particular individual was raised with. So unseen slots
        # are assumed to be attacks of the Pokemon's own type -- the STAB
        # guess any player makes on sight -- which is real information (a Fire
        # type probably has Fire moves) without being the answer.
        #
        # This replaced reading the whole movepool, which measured identical
        # to full sight: Data/pokemon.csv lists five moves for 52% of the
        # roster and six for 39%, of which four are held, so "the pool" here
        # is almost the exact set. That is a property of this game's data
        # rather than of the model -- in the real games a species learns fifty
        # moves and the same idea would work unmodified.
        # One placeholder per type it actually has, cycled across the unseen
        # slots -- a Ground/Rock Pokemon is expected to threaten with both,
        # not only its primary. Triple typing exists here (Forest's Curse and
        # Soak both add one), so this reads the list rather than assuming two.
        kinds = _own_types(foe)
        believed, spare = [], 0
        for name in actual:
            if name in seen:
                believed.append(name)
            else:
                believed.append(unknown_slot(kinds[spare % len(kinds)]))
                spare += 1
        return believed

    # BLIND: nothing to narrow it with. Not even the typing is assumed, so an
    # unseen slot is Typeless -- neutral against everything, which is the
    # honest shape of "I have no idea what is coming".
    blind = unknown_slot("Typeless")
    return [name if name in seen else blind for name in actual]


def believed_ability(foe, level, abilities_of):
    """The ability this trainer believes the Pokemon holds.

    A list, always. A bare string here is the fault the engine's own integrity
    suite exists to catch -- `random.choice` over a string picks a *letter*,
    and `user.ability + [...]` raises on one.
    """
    if level >= FULL:
        return None                        # no substitution: read the real one
    if level == BLIND:
        return []                          # no idea what it is
    # POOL: knows the species has an ability and cannot know which, so it
    # plans as though there were none rather than guessing. Measured: giving
    # this rung both candidate abilities put it level with full sight, because
    # 51% of species only have one and the guess was simply correct.
    return []
