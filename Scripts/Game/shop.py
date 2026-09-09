"""Coins, and what they buy.

Coins follow the kill score, both ways: a round settles on the knockouts you
took off the opponent less the ones they took off you. A rout pays well, a
scrape pays a little, and losing more than you took costs you coins. The
balance stops at nothing -- it never goes negative -- so a bad round can
empty the purse but not put you in debt.

They belong to one career in one save slot. A new game starts at zero -- the
Protagonist's row in Data/competitors.csv says nothing about coins, which is
also what a save written before this feature restores to.

Two things to buy, both of them about the team you already have rather than
about getting a bigger one:

    refresh the IVs     re-roll one Pokemon's IVs, wholesale, no take-backs
    swap, same tier     trade one Pokemon for another off the same shelf,
                        carrying the same IV total across

The second is deliberately the expensive one. It is the answer to a bad
draft, which is the thing coins are really for.
"""
import random
from contextlib import suppress
from copy import deepcopy

from Scripts.Data.pokemon import list_of_pokemon
from Scripts.Art import narrator
from Scripts.Art.text_color import *

#: what each thing costs
COST_REFRESH_IV = 2
COST_SWAP_POKEMON = 5

# ------------------------------------------------------- permanent upgrades
#: name -> (cost, one line). Bought once, owned for the whole career.
#:
#: Deliberately all *meta*: what a round pays, what you know going in, and
#: how many rounds you play. None of them changes a rule on the field, and
#: none touches the IV curve or the tier shelf -- so every rating in
#: Data/competitors.csv still describes the game it was measured against.
#:
#: They are also all things whose value holds up as a career matures. An
#: upgrade that mostly helps a *bad* team is worth little by the time 200
#: coins have been saved, which is what ruled out the earlier candidates.
DOUBLE_PAY = "Double Pay"
AUTO_SCOUT = "Auto Scout"
RETRY = "Retry"
SEEDED = "Seeded"

UPGRADES = (
    (DOUBLE_PAY, 80, "Kill score pays double, up and down."),
    (AUTO_SCOUT, 120, "Opponents are always fully scouted."),
    (RETRY, 200, "Once a run, replay a round you lost."),
    (SEEDED, 400, "The first two rounds are won for you."),
)
UPGRADE_COST = {name: cost for name, cost, _line in UPGRADES}

#: how many opening rounds Seeded wins for you
SEEDED_ROUNDS = 2


class RoundRetry(Exception):
    """Raised to abandon a lost round so it can be played again.

    Thrown from `check_win_or_lose` before it commits anything and caught by
    the career loop in main.py. An exception rather than a return value
    because the turn loop is deep mutual recursion -- `move_selection` and
    `end_of_turn` call each other about five frames a turn -- and there is no
    single place to hand a "stop, we are replaying this" answer back through.
    """


def retry_available(protagonist):
    """Whether the retry is owned and still unspent this run.

    Deliberately says nothing about who is answering. An unattended run
    declines the offer in `auto_run.answer`, which is the one place that
    knows how to reply to a prompt with nobody watching -- putting a second
    rule here as well would mean two mechanisms for one decision, and the
    next person would have to find both.
    """
    return (owns(protagonist, RETRY)
            and not getattr(protagonist, "retry_used", False))


def begin_run(protagonist):
    """Called once as a run starts: the retry is per run, not per career."""
    protagonist.retry_used = False


def spend_retry(protagonist):
    protagonist.retry_used = True


def owned(protagonist):
    """The upgrade names this career holds, as a set."""
    held = getattr(protagonist, "upgrades", None)
    if not isinstance(held, (set, list, tuple)):
        return set()
    return {str(name) for name in held}


def owns(protagonist, name):
    return str(name) in owned(protagonist)


def buy_upgrade(protagonist, name):
    """Pay for an upgrade and record it. False if it cannot be bought."""
    cost = UPGRADE_COST.get(str(name))
    if cost is None or owns(protagonist, name):
        return False
    if not spend(protagonist, cost):
        return False
    protagonist.upgrades = sorted(owned(protagonist) | {str(name)})
    return True


#: Set by the interface: called after anything here changes the team.
#:
#: It has to be told. The shop runs at a pre-battle prompt, and the snapshot
#: taken before each prompt is deliberately only the battlefield flags --
#: snapshotting the rosters that often slowed the game to a crawl (see
#: bridge.refresh_before_input). So a swap or a re-roll happened and the team
#: window went on showing what was there before. A purchase is not every
#: prompt and can afford the full snapshot.
#:
#: A plain optional callback, the same shape `narrator.listen` already uses.
#: Nothing here knows what is on the other end of it.
changed = None


def _changed(protagonist):
    if changed is not None:
        changed(protagonist)

#: the highest any single IV goes. The same ceiling pokemon_init rolls to.
IV_CEILING = 31
#: how far a re-roll can move the total, either way
IV_SWING = 30

#: Tiers whose Pokemon cannot be traded away. "Boss" is the five strongest in
#: the game and sits outside the normal ladder in Scripts/Data/tiers.py -- they
#: are prizes rather than stock, and a shop that shuffles them is a shop that
#: hands out the best Pokemon in the game for five coins.
UNSWAPPABLE_TIERS = ("Boss",)


def coins_change(protagonist, competitor):
    """What a finished round does to the balance. Signed.

    `result` is how many of the other side went down, and it is set on both
    competitors by check_win_or_lose before this is called. The difference is
    the whole rule: a rout pays well, a scrape pays a little, and a round
    where you lost more than you took *costs* you.

    Nothing is floored here. The floor belongs to the balance -- see
    `award` -- because a player holding one coin who loses by four can only
    lose the one they have.
    """
    mine = int(getattr(protagonist, "result", 0) or 0)
    theirs = int(getattr(competitor, "result", 0) or 0)
    change = mine - theirs
    # Double Pay doubles the *settlement*, not the income: a bad round costs
    # twice as much too. Doubling only the gains would change the risk you
    # are running rather than the rate you are paid, which is not what the
    # name says and is a good deal stronger than it sounds.
    return change * 2 if owns(protagonist, DOUBLE_PAY) else change


def balance(protagonist):
    return max(0, int(getattr(protagonist, "coins", 0) or 0))


def award(protagonist, competitor):
    """Settle the round. Returns what actually moved, which may be negative.

    Clamped at nothing and no further: a balance never goes below zero, so
    a deduction bigger than the purse takes only what is in it. The figure
    returned is what *left* rather than what was owed, so whatever reports
    it cannot disagree with the number on screen.
    """
    was = balance(protagonist)
    protagonist.coins = max(0, was + coins_change(protagonist, competitor))
    return balance(protagonist) - was


def can_afford(protagonist, cost):
    return balance(protagonist) >= int(cost)


def spend(protagonist, cost):
    """Take `cost` coins. False -- and nothing taken -- if it cannot be paid."""
    if not can_afford(protagonist, cost):
        return False
    protagonist.coins = balance(protagonist) - int(cost)
    return True


# --------------------------------------------------------------- the IVs
def spread(total, slots=6, ceiling=IV_CEILING):
    """A random split of `total` across `slots`, none of them above `ceiling`.

    Handed out one point at a time to a slot with room left, which is slower
    than a formula and is exactly right by construction: it cannot overshoot
    the ceiling, and it cannot come to anything other than `total`. Six slots
    and at most 186 points, so the cost is nothing.
    """
    total = max(0, min(int(total), slots * ceiling))
    parts = [0] * slots
    room = list(range(slots))
    for _ in range(total):
        pick = random.choice(room)
        parts[pick] += 1
        if parts[pick] >= ceiling:
            room.remove(pick)
    return parts


def _restat(pokemon):
    """Put the derived numbers back in step with `pokemon.iv`."""
    pokemon.total_iv = sum(pokemon.iv)
    pokemon.nominal_base_stats = [base + iv for base, iv
                                  in zip(pokemon.base_stats, pokemon.iv)]
    pokemon.total_base_stats = sum(pokemon.base_stats)
    return pokemon


def refresh_iv(pokemon, protagonist):
    """Re-roll one Pokemon's IVs. Returns (before, after).

    A real gamble: the total can go up or down, and every stat is re-spread.

    Two earlier versions were both wrong. Floored at the player's own rating
    it reached 31 at a high rating and became a no-op exactly when a player
    had coins to spend. Drawing the six stats independently over 0..31 is
    pulled towards *its* mean of 93, so a Pokemon at 170 came out worse 300
    times in 300. Drawing the total instead is the only shape that is even
    from wherever the Pokemon happens to start.

    Wholesale and with no take-backs, deliberately. Keeping the better of the
    two would make this a coin sink that converges on perfect IVs, and the IV
    curve is most of what a rating means.
    """
    before = list(pokemon.iv)
    # A total drawn either side of the one it already has, then spread over
    # the six stats afresh. Symmetric on purpose: anything that draws the
    # stats independently is pulled towards its own mean instead -- a flat
    # 0..31 roll averages a total of 93, so a Pokemon at 170 came out worse
    # 300 times in 300. Only the ends are one-way, and they have to be.
    target = sum(before) + random.randint(-IV_SWING, IV_SWING)
    pokemon.iv = spread(max(0, min(6 * IV_CEILING, target)))
    _restat(pokemon)
    return before, list(pokemon.iv)


# ------------------------------------------------------------- the swapping
def tier_of(pokemon):
    return str(getattr(pokemon, "tier", "") or "")


def describe_pokemon(pokemon):
    """One Pokemon, as the shop lists it.

    Short enough to survive being turned into a button label by the
    interface, which is what the pre-battle screens do with every numbered
    line the engine prints.
    """
    line = "%s (IV %d)" % (pokemon.name, sum(pokemon.iv))
    return line if is_swappable(pokemon) else line + " [Can't Swap]"


def is_swappable(pokemon):
    """Whether the shop will trade this Pokemon away."""
    return tier_of(pokemon) not in UNSWAPPABLE_TIERS


def swap_candidates(pokemon, held=()):
    """Everything on the same shelf that is not already on the team."""
    if not is_swappable(pokemon):
        return []
    wanted = tier_of(pokemon)
    taken = {str(name) for name in held}
    return sorted(name for name, other in list_of_pokemon.items()
                  if str(getattr(other, "tier", "")) == wanted
                  and str(name) not in taken
                  and str(name) != str(pokemon.name))


def swap_pokemon(pokemon, held=(), pick=None):
    """One Pokemon for another off the same shelf. None if there is nobody.

    The IV *total* carries across and the split does not: the Pokemon you
    get is worth what the one you gave up was worth, spread differently. That
    is what keeps this a change of shape rather than a way to buy power --
    and it is why the expensive option cannot be farmed for better IVs.

    A Boss-tier Pokemon is never traded away. See UNSWAPPABLE_TIERS.
    """
    options = swap_candidates(pokemon, held)
    if not options:
        return None
    chosen = pick if pick in options else random.choice(options)
    incoming = deepcopy(list_of_pokemon[chosen])
    incoming.iv = spread(sum(pokemon.iv))
    incoming.ability = [random.choice(incoming.ability)] if incoming.ability \
        else []
    incoming.moveset = random.sample(incoming.moveset,
                                     min(4, len(incoming.moveset)))
    incoming.moveset = ["Switching"] + incoming.moveset
    incoming.default_name = incoming.name
    incoming.default_ability = list(incoming.ability)
    incoming.default_type = list(incoming.type)
    _restat(incoming)
    return incoming


# ------------------------------------------------------------------ the menu
#: value -> (label, cost). The interface reads this so the buttons and the
#: terminal menu cannot disagree about what anything costs.
SHOP_ITEMS = (
    (1, "Refresh Pokemon IVs", COST_REFRESH_IV,
     "Re-roll one Pokemon's IVs. It can come out worse."),
    (2, "Swap Pokemon (Same Tier)", COST_SWAP_POKEMON,
     "Trade one Pokemon for another off the same shelf, same IV total."),
)


def shop(protagonist):
    """The pre-battle shop, as the terminal build sees it."""
    roster = list(protagonist.team) + list(protagonist.unused_team or [])
    while True:
        print("")
        print(f"{CBOLD}{CYELLOW2}SHOP{CEND}  "
              f"{CBOLD}{balance(protagonist)} Coins{CEND}")
        for value, label, cost, _blurb in SHOP_ITEMS:
            print(f"  {value}: {label}: {cost} Coins")
        # Permanent upgrades, numbered after the consumables. One purchase
        # each and then they are furniture -- shown as OWNED rather than
        # hidden, so the list is a stable thing to learn.
        for offset, (name, cost, line) in enumerate(UPGRADES):
            slot = len(SHOP_ITEMS) + 1 + offset
            if owns(protagonist, name):
                print(f"{CGREY}  -: {name}: OWNED{CEND}")
            else:
                print(f"  {slot}: {name}: {cost} Coins")
                print(f"{CGREY}     {line}{CEND}")
        print("  0: leave")

        buyable = {len(SHOP_ITEMS) + 1 + offset: name
                   for offset, (name, _c, _l) in enumerate(UPGRADES)
                   if not owns(protagonist, name)}
        choice = -1
        allowed = ([value for value, _l, _c, _b in SHOP_ITEMS]
                   + list(buyable) + [0])
        while choice not in allowed:
            with suppress(ValueError):
                choice = int(input("What do you want? "))
        if choice == 0:
            return

        if choice in buyable:
            name = buyable[choice]
            if not buy_upgrade(protagonist, name):
                print(f"{CGREY}Not enough Coins.{CEND}")
                continue
            narrator.say(f"{CBOLD}{name} unlocked, for the rest of your "
                         f"career.{CEND}")
            _changed(protagonist)
            continue

        cost = dict((value, cost) for value, _l, cost, _b in SHOP_ITEMS)[choice]
        if not can_afford(protagonist, cost):
            print(f"{CGREY}Not enough Coins.{CEND}")
            continue

        print("")
        for index, mon in enumerate(roster):
            print(f"  {index}: {describe_pokemon(mon)}")
        print(f"  {len(roster)}: back")
        target = -1
        while not 0 <= target <= len(roster):
            with suppress(ValueError):
                target = int(input("Which Pokemon? "))
        if target == len(roster):
            continue
        mon = roster[target]

        if choice == 1:
            if not spend(protagonist, cost):
                continue
            before, after = refresh_iv(mon, protagonist)
            narrator.say(f"{CBOLD}{mon.name}: IV {sum(before)} -> "
                         f"{sum(after)}{CEND}")
            _changed(protagonist)
        else:
            if not is_swappable(mon):
                print(f"{CGREY}{mon.name} can't be swapped.{CEND}")
                continue
            held = [other.name for other in roster]
            incoming = swap_pokemon(mon, held)
            if incoming is None:
                print(f"{CGREY}No one available at that tier.{CEND}")
                continue
            if not spend(protagonist, cost):
                continue
            _replace(protagonist, mon, incoming)
            roster = list(protagonist.team) + list(protagonist.unused_team
                                                   or [])
            narrator.say(f"{CBOLD}{mon.name} -> "
                         f"{describe_pokemon(incoming)}{CEND}")
            _changed(protagonist)


def _replace(protagonist, going, coming):
    """Put `coming` wherever `going` was, in whichever list holds it."""
    for team in (protagonist.team, protagonist.unused_team or []):
        for index, mon in enumerate(team):
            if mon is going:
                team[index] = coming
                return True
    return False

