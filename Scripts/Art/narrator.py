"""Everything the engine says out loud, in one place.

There are 262 `print()` calls in Scripts/. Each one decides for itself what
it says *and* how it looks, so "The move failed." is written out five times,
a faint is coloured at each of the places a Pokemon can faint, and changing
how the game reads means finding all of them. Worse, some of what the engine
prints is a fact the interface then reads *back* out of the text with a
regular expression -- `elo_rating()` works out a rating change, prints it,
and GUI/bridge.py parses the number out of the printed line.

`say()` is the one door. It takes the line, the *kind* of thing it is, and
optionally the facts behind it:

    say(f"{user.name} used {move.name}.", "move", user=user.name)

The kind is what makes this worth doing. It travels to anyone listening, so
an interface can style a faint differently from a heal without matching on
ANSI escapes or on the English wording -- and the wording becomes free to
change without breaking anything.

`listen()` registers a listener. The engine keeps printing exactly as it
always did; nothing here changes what reaches a terminal.
"""
from Scripts.Art.text_color import CBOLD, CEND, CGREEN2, CRED, CYELLOW2
from Scripts.Battle.constants import MODIFIER

#: the kinds a line can be. Kept small on purpose: a kind earns its place by
#: being something an interface would plausibly present differently.
KINDS = (
    "move",       # someone used a move
    "damage",     # damage dealt, drained, recoiled
    "heal",       # HP restored
    "faint",      # a Pokemon went down
    "status",     # a status or volatile status landed or lifted
    "stat",       # a stat stage moved
    "fail",       # the move did nothing
    "switch",     # a Pokemon came in or went out
    "weather",    # the sky changed
    "ability",    # an ability announced itself
    "field",      # hazards, screens, terrain
    "result",     # a match or run outcome, ratings included
    "plain",      # everything else
)

#: functions called with (kind, text, facts) for every line said
_listeners = []


def listen(callback):
    """Hear every line the engine says. Returns a function that stops it."""
    _listeners.append(callback)
    return lambda: _listeners.remove(callback)


def say(text, kind="plain", **facts):
    """Say one line, and tell anyone listening what kind of thing it was.

    The text is printed exactly as given -- colouring it here rather than at
    the call site is the point of the helpers below, but a call site that
    has already coloured its own line is passed through untouched.
    """
    print(text)
    for callback in tuple(_listeners):
        callback(kind, text, facts)


# -- the lines that were written out more than once -----------------------
#: what the engine says when a move does nothing. It was five separate
#: string literals, and one of them said "The move failed!" instead.
MOVE_FAILED = "The move failed."


def failed(reason=MOVE_FAILED, **facts):
    """The move did nothing."""
    say(reason, "fail", **facts)


def fainted(pokemon):
    """A Pokemon went down. Coloured by side, as it always was."""
    say(f"{pokemon.side_color}{pokemon.name} fainted!{CEND}", "faint",
        pokemon=getattr(pokemon, "name", ""),
        side=getattr(pokemon, "side_color", ""))


def used(side_color, user_name, move_name):
    """Someone used a move."""
    say(f"{side_color}{user_name} used {move_name}{CEND}.", "move",
        user=user_name, move=move_name)


def switched_in(side_color, name):
    """A Pokemon came in."""
    say(f"{side_color}{name} is switched in!{CEND}", "switch", pokemon=name)


# -- stat stages ----------------------------------------------------------
#: how a stage change reads, by how many stages actually moved. The series
#: wording, because it is the wording players already know.
ROSE = {1: "rose", 2: "rose sharply", 3: "rose drastically"}
FELL = {1: "fell", 2: "harshly fell", 3: "severely fell"}


def stat_change(pokemon, before, after, asked, ground=None):
    """Say what a stat change actually did, stat by stat.

    This used to print `Pikachu | Attack -1 | Speed -1` -- the raw contents
    of `applied_modifier`, which is a debug dump rather than something a
    player reads. Two things were wrong with it beyond the wording:

    * it reported what was *asked for*, not what happened. A Pokemon already
      at -6 Attack was told its Attack fell again. `before` and `after` are
      the stage list either side of the change, so a change that hit the end
      of its range now says so.
    * it said nothing about how far. One stage and three stages read the same.

    `asked` is `applied_modifier`: which stats this change meant to touch.
    A stat nobody aimed at is not mentioned even if something else moved it.

    `ground` is how a *hypothetical* change stays quiet. The AI scores its
    candidate moves by running the real ability code against a copy, on the
    same phases a real turn uses, so thirteen stat-changing abilities fire
    while nothing is actually happening -- measured at 6 of 54 announcements
    over six battles. `battleground.reality` is False for those, and telling
    the player "Defense rose!" for a move the opponent never used is worse
    than saying nothing.
    """
    if ground is not None and not getattr(ground, "reality", True):
        return
    for index, wanted in enumerate(asked):
        if not wanted:
            continue
        stat = MODIFIER[index]
        moved = after[index] - before[index]
        colour = getattr(pokemon, "side_color", "")
        name = getattr(pokemon, "name", "It")
        if moved == 0:
            edge = "higher" if wanted > 0 else "lower"
            say(f"{colour}{name}'s {stat} won't go any {edge}!{CEND}",
                "stat", pokemon=name, stat=stat, delta=0,
                stage=after[index])
            continue
        words = ROSE if moved > 0 else FELL
        say(f"{colour}{name}'s {stat} {words[min(3, abs(moved))]}!"
            f" ({after[index]:+d}){CEND}",
            "stat", pokemon=name, stat=stat, delta=moved,
            stage=after[index])
