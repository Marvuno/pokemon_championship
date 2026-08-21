"""Who is fighting whom, and on what field.

The engine threads the same cluster of six things through nearly every
function in a battle: two competitors, their two parties, the two Pokemon
currently out, and the battleground. Forty-one functions take eight or more
positional arguments because of it, and the effect handlers in
`move_additional_effect.py` are the clearest case -- all twenty-four take the
same nine parameters, and the median one uses three. `target_team` is used by
exactly one of them.

Two small objects replace that. A `Side` is one competitor's corner of the
battle; a `Turn` is the battle seen from the point of view of whoever is
acting.

    def check_move_user_heal(turn, move, special_effect):
        healed = math.floor(turn.user.active.hp * special_effect)

reads as what it does, and the handler no longer carries six things it never
touches.


Why `active` is stored and not derived
--------------------------------------
It would be tidier for `Side.active` to return `team[0]`, and it would be
wrong. The engine does not always hand these functions `team[0]`: mid-switch
it passes the Pokemon that *was* out while the team list already holds the
replacement, and several call sites re-derive `user = user_team[0]` at a
specific moment precisely because the two differ in between. Deriving it
would silently change which Pokemon those functions act on. So `active` holds
exactly what the caller passed, and code that wants to re-read the front of
the party says so.


Both slots hold references, never copies
----------------------------------------
`Side` holds the caller's own competitor, party list and Pokemon. Nothing
here copies anything, so a handler writing through `turn.user.active` writes
to the real Pokemon, exactly as it did when the same object arrived as a bare
argument. `__slots__` keeps that cheap: these are built several times per
turn and a dict per instance would be pure waste.
"""


class Side:
    """One competitor's corner: the trainer, their party, and who is out.

    `trainer` is the competitor object the engine calls `user_side` or
    `protagonist` depending on where you read it -- it owns the entry hazards,
    the barriers and the score. `team` is their party list. `active` is the
    Pokemon currently out.
    """

    __slots__ = ("trainer", "team", "active")

    def __init__(self, trainer, team, active=None):
        self.trainer = trainer
        self.team = team
        self.active = active if active is not None else (team[0] if team
                                                        else None)

    def __repr__(self):
        return "Side(%s, %s)" % (getattr(self.trainer, "nickname", "?"),
                                 getattr(self.active, "name", "-"))


class Turn:
    """A battle from the acting side's point of view.

    `user` is whoever is doing the thing, `foe` is the other side, `ground` is
    the battleground. Plenty of the engine's calls are made from the other
    side's perspective -- an ability that fires on the Pokemon being hit, for
    instance -- and `flip()` is how to say that without rebuilding anything.
    """

    __slots__ = ("ground", "user", "foe")

    def __init__(self, ground, user, foe):
        self.ground = ground
        self.user = user
        self.foe = foe

    def flip(self):
        """The same battle, read from the other side."""
        return Turn(self.ground, self.foe, self.user)

    def __repr__(self):
        return "Turn(%r vs %r)" % (self.user, self.foe)


def turn_of(battleground, user_side, user_team, user, target_side,
            target_team, target):
    """Build a Turn from the six arguments the engine currently threads.

    A shim for call sites that have not been converted yet: it lets one layer
    move to the context object at a time, with the fingerprint proving each
    step changed nothing.
    """
    return Turn(battleground,
                Side(user_side, user_team, user),
                Side(target_side, target_team, target))
