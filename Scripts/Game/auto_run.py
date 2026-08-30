"""Play whole careers unattended, from the start menu.

AUTO RUN takes an existing save slot and a number of runs, then plays that
career through to the end that many times over. It exists to exercise the
game the way a player does -- every screen, every prompt, a real save -- for
as long as it takes to see something go wrong.

**It answers the engine's own questions rather than replacing anything.**
The engine asks through `input()`; this installs itself in front of whatever
`input` is currently bound to and replies to the prompts it recognises,
passing anything else straight through. So it works the same in the terminal
build and behind the window, and neither of them had to learn about it.

The defaults, in the order a run meets them:

    pre-battle menu        Battle -- never the information screens
    too many Pokemon       bench the weakest, on base stats plus IVs, and
                           only draw lots between Pokemon that really tie
    first move of a battle 100 to turn auto battle on, then the first move,
                           because the engine still wants a move for the turn
                           it was asked on; after that it never asks again
    a forced switch        the first Pokemon still standing
    winning a round        trade if their best beats your worst, on base
                           stats *plus IVs* -- the figures Fast Comparison
                           shows -- skipping any Pokemon already on the team;
                           two of a species cover the same matchups. Take a
                           free Pokemon whenever one is offered, on the same
                           rule.
    keeping a team         everything, one index at a time
    any "press any key"    a bare Enter

Two rules about what it must *not* do:

- **It never answers the start menu.** `stop()` runs before the menu is
  reached, so a finished Auto Run hands control back rather than choosing
  AUTO RUN again forever.
- **It never answers a pick with the go-back sentinel unless it means it.**
  9 backs out and the engine asks again; answering 9 to a question that is
  then re-asked is an infinite loop, and that is exactly what the reward
  screen did until the pick was read out of the prompt properly.

**Where the numbers come from.** Team facts -- who is still standing, how
many Pokemon there are -- come from the game. The reward screen's two lists
do not: `protagonist.opponent` is appended *after* it runs, so at that moment
it still holds the previous round. Those prompts print the list they are
asking about, so that is what gets read.
"""
import random
import re

from Scripts.Art import music

#: The most careers one Auto Run may be asked for.
MAX_RUNS = 100

#: Entered at the move prompt to turn auto battle on. `select_move` reads it
#: and says the turn still needs a move, which is why the reply after it is
#: an actual move rather than another 100.
AUTO_BATTLE_CODE = "100"

#: Moveset slot 0 is always "Switching" (battle_setup prepends it), so the
#: first move a Pokemon actually knows is slot 1.
FIRST_MOVE = "1"


class _Run:
    """Everything one Auto Run needs to remember. Module-level by design.

    The engine has no object to hang this off -- `input()` is a builtin and
    the prompts come from six different modules -- so the state lives here
    and `active` is the single thing every other module asks about.
    """

    active = False
    #: how many careers were asked for, and how many are done
    total = 0
    done = 0
    #: True from the moment a run stops until the end-of-run screen is up.
    #: The last battle's result gate is raised by the *window*, on its own
    #: thread, and can arrive after the engine has already finished the
    #: career and called stop() -- so a gate that clears only while `active`
    #: leaves the very last one standing, waiting for a click nobody is
    #: there to give. This covers that gap.
    settling = False
    #: auto battle is per *battle* (`Battleground` is rebuilt each time), so
    #: this is cleared every time a new battle is started from the menu
    battle_armed = False
    #: the previous `input`, restored by stop()
    previous = None


state = _Run()


def start(times=1):
    """Play the loaded career through, unattended, `times` over.

    Repeating happens *inside* start_game(), never around it -- the start
    menu is the one thing an Auto Run deliberately never answers, so a
    repeat that loops back to it stops dead. `main()` owns that loop;
    `finished_one()` is what tells it another career is owed, and
    `draw_bracket()` is what puts the tournament back for it.

    Silences the game for the duration: an unattended run that plays battle
    music for twenty careers is not something anybody wants to sit next to.

    The `input` wrapper is installed *here*, not at import, and that timing
    matters. The window replaces `builtins.input` with its own when it
    installs its hooks; wrapping at import would put this underneath it and
    the window would answer first. Taking whatever is bound at the moment
    Auto Run starts puts it in front, with the real one kept to delegate to.
    """
    import builtins
    state.active = True
    state.total = max(1, min(int(times), MAX_RUNS))
    state.done = 0
    state.settling = False
    _fresh_career()
    music.silence(True)

    if state.previous is None:
        state.previous = builtins.input

        def scripted(prompt=""):
            reply = answer(prompt)
            if reply is None:
                return state.previous(prompt)
            # Echo it, because the log is the only record of what happened
            # and a run that answers silently reads as a game playing itself
            # with no input at all.
            print("%s%s" % (prompt, reply))
            return reply

        builtins.input = scripted


def _fresh_career():
    """Clear everything that is remembered only for the length of one career."""
    state.battle_armed = False
    state.done_keeping = 0
    state.swap_declined = False
    state.take_declined = False
    state.swap_out = None
    state.swap_mine = 0
    state.excluded = set()


def finished_one():
    """One career is over. True when another is owed.

    Also wipes the per-career scratch: auto battle has to be switched on
    again in the next career's first battle, and a half-finished swap
    decision must not carry across.
    """
    if not state.active:
        return False
    state.done += 1
    _fresh_career()
    return state.done < state.total


def remaining():
    return max(0, state.total - state.done) if state.active else 0


def stop():
    """End the run, restore `input`, and give the machine its voice back.

    There is deliberately no end-of-run sound. One was tried -- a generated
    chime played on a mixer channel so the returning menu music could not cut
    it off -- and it never actually reached the player on the machine this is
    developed for, through several attempts. The run says it has finished in
    the log instead, which is the part that always worked.
    """
    import builtins
    state.active = False
    state.total = state.done = 0
    state.settling = True
    _fresh_career()
    if state.previous is not None:
        builtins.input = state.previous
        state.previous = None
    music.silence(False)


def _living(team):
    """Indices of the Pokemon on `team` that can still be sent out."""
    return [index for index, mon in enumerate(team or [])
            if getattr(mon, "status", "") != "Fainted"
            and (getattr(mon, "battle_stats", [1]) or [1])[0] > 0]


def _total(mon):
    """A Pokemon's worth, as base stats. Deliberately not the rolled total.

    Base stats are the species; IVs are the individual. Comparing "how good
    is this Pokemon to own" across two teams is a question about the species,
    and the IV roll would otherwise decide trades on noise.
    """
    return sum(getattr(mon, "base_stats", []) or [0])


#: `[(0, 'Vanilluxe'), (1, 'Delphox')]` -- the engine prints the list it is
#: asking about *in the prompt itself*, which is the one place the two teams
#: are both available. `protagonist.opponent` is not: it is appended after
#: the reward screen, so at this point it still holds the previous round.
RE_CHOICE = re.compile(r"\(\s*(\d+)\s*,\s*'([^']*)'\s*\)")


def _named(mon):
    return getattr(mon, "default_name", None) or getattr(mon, "name", "")


def _their_team(text):
    """The real Pokemon behind a reward prompt's list, or [].

    The prompt gives names, and a name only reaches the *species*, which has
    no IVs on it -- so ranking on a lookup would compare two teams by base
    stats alone. The competitor whose team is exactly this list, in this
    order, is the one being offered, and their Pokemon carry the rolls.

    `protagonist.opponent` cannot be used for this: `check_win_or_lose`
    appends to it *after* the reward screen, so at this moment it is either
    empty or holds the previous round.
    """
    names = [name for _, name in RE_CHOICE.findall(text or "")]
    if not names:
        return []
    from Scripts.Data.competitors import list_of_competitors
    for who in list_of_competitors.values():
        team = list(getattr(who, "team", []) or [])
        if len(team) == len(names) and                 all(_named(mon) == name for mon, name in zip(team, names)):
            return team
    return []


def _offered(text, objects=None):
    """[(index, name, strength)] for every Pokemon a prompt offers.

    `strength` is `nominal_base_stats` -- base plus the IVs that individual
    rolled -- whenever the real Pokemon can be reached, which is the same
    figure Fast Comparison puts on screen. Species base stats are the
    fallback for when they cannot be, and they tie two of a species however
    differently the two rolled.
    """
    from Scripts.Data.pokemon import list_of_pokemon
    out = []
    for raw, name in RE_CHOICE.findall(text or ""):
        index = int(raw)
        if objects is not None and index < len(objects):
            out.append((index, name, _individual_total(objects[index])))
            continue
        species = list_of_pokemon.get(name)
        out.append((index, name, _total(species) if species else 0))
    return out


def _individual_total(mon):
    """This Pokemon's real strength: its base stats *plus* the IVs it rolled.

    `total_stats` is the species figure from the CSV and says nothing about
    the individual, so two Magikarp would tie on it however they rolled.
    `nominal_base_stats` is what the engine builds a battle from.
    """
    stats = getattr(mon, "nominal_base_stats", None)
    if isinstance(stats, (list, tuple)) and stats:
        return sum(stats)
    return getattr(mon, "total_stats", 0) or 0


def _iv_total(mon):
    total = getattr(mon, "total_iv", None)
    if total:
        return total
    ivs = getattr(mon, "iv", None)
    return sum(ivs) if isinstance(ivs, (list, tuple)) else 0


def _weakest_first(team):
    """Indices of `team`, weakest first, ties broken at random.

    Shuffled *before* the sort rather than after: Python's sort is stable, so
    equal keys keep the shuffled order and a team of six identical Pokemon is
    dropped at random rather than always from slot 0. Sorting first and
    shuffling after would throw the ordering away.
    """
    order = list(range(len(team)))
    random.shuffle(order)
    order.sort(key=lambda index: (_individual_total(team[index]),
                                  _iv_total(team[index])))
    return order


def _roster_names():
    """Every Pokemon already on the books, played or benched."""
    me = _protagonist()
    everyone = list(getattr(me, "team", []) or []) +         list(getattr(me, "unused_team", []) or [])
    return {getattr(mon, "default_name", None) or getattr(mon, "name", "")
            for mon in everyone}


def _pick(text, best=True, avoid=(), objects=None):
    """(index, name, total) for the strongest or weakest Pokemon offered.

    `avoid` is names already on the team. Taking a second copy of a Pokemon
    is a wasted trade -- the same species twice covers the same matchups --
    so a duplicate is skipped and the next best considered instead. If every
    one of them is a duplicate this returns None, and the caller has to back
    out rather than pick one anyway.
    """
    offered = [row for row in _offered(text, objects)
               if row[1] not in set(avoid)]
    if not offered:
        return None
    return (max if best else min)(offered, key=lambda row: row[2])


def _protagonist():
    """The player, looked up late.

    Imported inside the function rather than at module scope: competitors.py
    reaches back into this package, and importing it at the top makes the
    cycle real.
    """
    from Scripts.Data.competitors import list_of_competitors
    return list_of_competitors.get("Protagonist")


def answer(prompt):
    """The scripted reply to one prompt, or None to let it through.

    Matching is on a distinctive fragment of each question rather than the
    whole string, so re-wording a screen does not silently stop Auto Run
    answering it -- and anything unrecognised falls through to whoever asked,
    which in the window is the player.
    """
    if not state.active:
        return None
    text = str(prompt or "")

    # -- the pre-battle menu: play, never the information screens ----------
    if "What do you want to do?" in text:
        # a new battle, so auto battle has to be switched on again -- and the
        # team is picked fresh for it, so who was benched last round is
        # forgotten here rather than carried into this one
        state.battle_armed = False
        state.excluded = set()
        return "0"

    # -- the move prompt ---------------------------------------------------
    # First time in a battle: 100 turns auto battle on but the engine still
    # wants a move for this turn. Every turn after this one is chosen by
    # `auto_ai_select_move` and never reaches a prompt at all.
    if "What is the move for" in text:
        if not state.battle_armed:
            state.battle_armed = True
            return AUTO_BATTLE_CODE
        return FIRST_MOVE

    # -- a forced switch ---------------------------------------------------
    # 8 views the team and 9 goes back, so neither is an answer. The first
    # Pokemon still standing is, and that comes from the team rather than
    # from whatever was last printed.
    if "would you like to switch in" in text:
        alive = _living(getattr(_protagonist(), "team", []))
        return str(alive[0]) if alive else "9"

    # -- more Pokemon than the round allows -------------------------------
    # The weakest go, not a random pick: rounds one and two are the ones that
    # ask, and a run that benches its best Pokemon there is a run thrown away.
    #
    # The engine keeps asking until it has enough *distinct* indices, so the
    # same answer twice would never grow its set and the question would be
    # asked forever. Whoever has already been named is remembered, and the
    # next weakest offered instead.
    if "you DO NOT need this round" in text:
        team = getattr(_protagonist(), "team", []) or []
        if not team:
            return "0"
        named = getattr(state, "excluded", None)
        if named is None:
            named = state.excluded = set()
        for index in _weakest_first(team):
            if index not in named:
                named.add(index)
                return str(index)
        return str(random.randrange(len(team)))

    # -- keep the whole team, one index at a time --------------------------
    # The engine stops asking of its own accord once enough have been named
    # (it breaks when the set is full), so counting up is all this needs.
    if "You can keep at most" in text:
        team = getattr(_protagonist(), "team", []) or []
        state.done_keeping = getattr(state, "done_keeping", 0)
        index = state.done_keeping
        state.done_keeping = index + 1
        if index >= len(team):
            state.done_keeping = 0
            return "9"                      # done
        return str(index)

    # -- winning a round: trade up, or not at all --------------------------
    # The rule is "swap if their best is worth more than my worst", and the
    # two lists it needs are printed in the two prompts that follow the Y/N
    # rather than in the Y/N itself. So this says Y to *see* them, notes its
    # own worst on the way past, and backs out with the go-back sentinel if
    # the trade turns out not to be an improvement. Backing out returns to
    # the Y/N, which is why the refusal has to be remembered -- answering Y
    # a second time is the loop this had at first.
    if "Input Y if you want to swap" in text:
        if getattr(state, "swap_declined", False):
            state.swap_declined = False
            return "N"
        return "Y"
    if "you don't want on your team" in text:
        # `my_roster()` in battle_win_condition is the played team followed
        # by whoever was benched, which is exactly what this prompt numbers.
        me = _protagonist()
        mine = list(getattr(me, "team", []) or []) +             list(getattr(me, "unused_team", []) or [])
        worst = _pick(text, best=False, objects=mine)
        if worst is None:
            state.swap_declined = True
            return "9"
        state.swap_mine = worst[2]
        state.swap_out = worst[1]
        return str(worst[0])
    if "Take the pokemon you want on the other team" in text:
        # Anything already on the books is skipped -- except the one being
        # given up, which is about to leave, so taking their copy of it is
        # not a duplicate. The next best is considered in its place, and the
        # comparison against our worst still has to be won.
        keep = _roster_names() - {getattr(state, "swap_out", None)}
        best = _pick(text, best=True, avoid=keep, objects=_their_team(text))
        if best is not None and best[2] > getattr(state, "swap_mine", 0):
            return str(best[0])
        # no improvement, or every one of theirs is one we already have
        state.swap_declined = True
        return "9"

    # An empty slot rather than a trade. Nothing is given up, so their best
    # is always worth taking -- 9 here would back out and ask again forever,
    # which is exactly what it did.
    if "want to take from the opponent" in text:
        if getattr(state, "take_declined", False):
            state.take_declined = False
            return "N"          # let the organiser hand one over instead
        return "Y"
    if "You may take one pokemon from the opponent" in text:
        best = _pick(text, best=True, avoid=_roster_names(),
                     objects=_their_team(text))
        if best is None:
            # every Pokemon they have is one we already own. Back out and
            # take the organiser's instead -- the engine already excludes
            # duplicates from that pool.
            state.take_declined = True
            return "9"
        return str(best[0])

    # -- leave the batting order alone -------------------------------------
    if "swap to be the first" in text:
        return "9"

    # -- every pause ------------------------------------------------------
    if ("any key" in text.lower() or "press any key" in text.lower()
            or "to continue" in text.lower() or "to proceed" in text.lower()):
        return ""

    # Deliberately not answered: "Your Option:" and the save-slot questions.
    # stop() runs before the start menu is reached, so those belong to the
    # player again by the time they are asked.
    return None


def unattended():
    """Should the window clear its own gates without waiting for a click?

    True while a run is going, and afterwards until the player is next asked
    something. Result gates are raised by the *window*, on its own thread,
    and trail behind the engine: the last career leaves more than one of them
    still queued when `stop()` runs, so a check on `active` alone -- or on a
    one-shot flag -- leaves the rest standing forever, waiting for a click
    nobody is there to give. `settled()` is what ends it, called from
    `_show_request` at the moment a question actually reaches the player.
    """
    return bool(state.active or state.settling)


def settled():
    """The player is being asked something; the window is theirs again."""
    state.settling = False
