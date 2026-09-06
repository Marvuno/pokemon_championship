import random
import sys
from copy import deepcopy
from contextlib import suppress

from Scripts.Art.text_color import *
from Scripts.Data.competitors import *
from Scripts.Game.single_elimination_bracket import *
from Scripts.Game.game_system import *
from Scripts.Battle.constants import *
from Scripts.Battle.ai import *
from Scripts.Data import tiers
from Scripts.Game import savefile
from Scripts.Art import narrator


def next_battle():
    round_begin()
    opponent = ""
    for participant in GameSystem.participants:
        participant = list_of_competitors[participant]
        if participant.match_id == list_of_competitors['Protagonist'].match_id and participant.id != list_of_competitors['Protagonist'].id:
            opponent = participant
            break
    opponent.team = team_generation(opponent)
    return opponent


def team_generation(participant, rand=False):
    # pokemon is divided to 6 tier (very low, low, medium, high, very high, custom)
    # should be selected based on strength
    nominal_team, unavailable_pokemon = [], set()
    # One IV rule for everybody, from their own rating. It used to be a
    # fixed floor per *tier label* for the competitors -- Low 0,
    # Intermediate 8, Advanced 16, Elite 24, Champion 31 -- while the player
    # alone got the PLAYER_IV curve. Two different kinds of rule meant the
    # two curves crossed: by the Elite rounds the player's floor was 31
    # against their 24, and below that the player was behind. Now the same
    # formula reads both.
    iv_floor = PLAYER_IV(participant.strength)
    # A designed ace's IVs are rolled here, before the tier weights are
    # drawn, because that is where the old custom_team.csv pass rolled them
    # and the random stream has to come out in the same order -- otherwise
    # the same seed builds different teams and every before/after comparison
    # of an engine change is worthless. The rest of the team is rolled in the
    # loop further down, as it always was.
    # Keyed by the Ace itself, not by its position: `nominal_team` is
    # prepended to the team further down, which shifts every index. Keyed by
    # index, the ace was looked up under the wrong one, missed, and had its
    # IVs rolled a second time -- six extra draws that moved the whole
    # random stream and left it with different IVs than were rolled here.
    pinned_iv = {id(entry): roll_iv(entry,
                                    iv_floor)
                 for entry in participant.team
                 if isinstance(entry, Ace) and entry.iv is not None}

    # Which tiers a competitor draws from is Scripts/Data/tiers.py now. It
    # was six lines of bare numbers here -- max(0, 40 - ratings),
    # min(60, 3 + ratings), an ultra-high ladder of six ifs -- and it was one
    # of *three* different answers in this codebase to "how good should these
    # Pokemon be": this, a level->tier dict for winning a round, and a flat
    # junk list for losing one. All three ask that module now.
    # pokemon testing purpose
    if rand:
        tier_count = []
        TIER = {0: 'Very Low', 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Very High', 5: 'Ultra High'}
        for index, tier in TIER.items():
            tier_count.append(sum([1 for pokemon in list_of_pokemon if tier == list_of_pokemon[pokemon].tier]))
        participant.team = []
        tier_list = random.choices(["Very Low", "Low", "Medium", "High", "Very High", "Ultra High"],
                                   weights=[tier_count[0], tier_count[1], tier_count[2], tier_count[3], tier_count[4], tier_count[5]], k=6)
    else:
        tier_list = tiers.tier_list(
            participant.strength,
            ROUND_LIMIT[GameSystem.stage] - len(participant.team),
            for_ai=not participant.main)
    for pokemon in participant.team:
        unavailable_pokemon.add(pokemon) if isinstance(pokemon, str) else unavailable_pokemon.add(pokemon.name)
    for tier in tier_list:
        new_pokemon = random.choice([pokemon for pokemon in list(list_of_pokemon) if
                                     pokemon not in unavailable_pokemon and list_of_pokemon[pokemon].tier == tier])
        nominal_team.append(new_pokemon)
        unavailable_pokemon.add(new_pokemon)

    # print(tier_list)  # debug

    with suppress(ValueError):
        # ace pokemon are put at the last (but the ai can still take it out when he wants)
        participant.team = nominal_team + participant.team
    # Every entry is an Ace: a species name, optionally with the IV, ability
    # and moveset that make it this competitor's own. Whatever the cell does
    # not pin is rolled here, exactly as a bare name always was.
    #
    # This replaced a `try:` that resolved `list_of_pokemon[entry]` and a
    # bare `except:` that assumed anything raising must already be a Pokemon
    # object -- which is how the second team file used to be merged in. A
    # mistyped species name took that same branch and turned into a broken
    # Pokemon instead of an error. Now it says which name it cannot find.
    for i in range(len(participant.team)):
        entry = participant.team[i]

        # An entry that is already a built Pokemon is left alone. This is
        # not an edge case: team_generation writes its results back into
        # `participant.team`, so every round after the first sees the
        # Pokemon it built last time, and the player's kept team arrives
        # this way too. Rebuilding them from the species would rewrite
        # somebody's kept Pokemon with fresh IVs and a fresh moveset every
        # round. The old code got this right by accident -- indexing
        # `list_of_pokemon` with an object raised, and a bare `except:`
        # caught it -- which is also why a *mistyped name* took the same
        # branch and became a broken Pokemon instead of an error.
        if not isinstance(entry, (str, Ace)):
            pokemon = deepcopy(entry)
            pokemon.total_stats = sum(pokemon.base_stats)
            pokemon.total_iv = sum(pokemon.iv)
            pokemon.nominal_base_stats = list(map(operator.add, pokemon.base_stats, pokemon.iv))
            participant.team[i] = pokemon
            continue

        ace = entry if isinstance(entry, Ace) else Ace(entry)
        if ace.name not in list_of_pokemon:
            raise KeyError("%s has no Pokemon called %r -- check their Poke "
                           "columns in Data/competitors.csv"
                           % (participant.name, ace.name))
        pokemon = deepcopy(list_of_pokemon[ace.name])
        if pokemon.iv == 0:
            pokemon.iv = pinned_iv.get(id(ace)) or roll_iv(ace, iv_floor)
        pokemon.total_iv = sum(pokemon.iv)
        pokemon.nominal_base_stats = list(map(operator.add, pokemon.base_stats, pokemon.iv))
        pokemon.ability = ([ace.ability] if ace.ability
                           else [random.choice(pokemon.ability)])
        pokemon.moveset = (list(ace.moves) if ace.moves
                           else random.sample(pokemon.moveset,
                                              min(4, len(pokemon.moveset))))
        participant.team[i] = pokemon
    # the order of the team matters
    # player can keep 6 pokemon
    if not participant.main:
        if len(participant.team) > ROUND_LIMIT[GameSystem.stage]:
            participant.team = participant.team[len(participant.team) - ROUND_LIMIT[GameSystem.stage]:len(participant.team)]

    return participant.team


def round_begin():
    GameSystem.participants.sort(key=lambda x: list_of_competitors[x].stage, reverse=True)
    print(f"\nRound {GameSystem.stage}:\n")

    for i in range(0, int(math.pow(2, 5))):
        participant = list_of_competitors[GameSystem.participants[i]]
        participant.match_id = i // 2
        bold = CBOLD if participant.championship > 0 else ''
        crown = f' |{participant.championship}|' if participant.championship > 0 else ''
        print(bold + EntryBox(participant.id, f"{participant.nickname} [{participant.strength}]{crown}", participant.stage - 1, ).structure + CEND)
        if i % 2 != 0:
            print("\n")


#: How far the people the champion beat went, as a trophy on the title.
#: The champion's title, and how well proven it is.
#:
#:   PROVEN_TITLE   the opponents they beat are worth more than
#:                  PROVEN_SHARE of the whole bracket's rating
#:   MODEST_TITLE   less than MODEST_SHARE of it
#:
#: This used to be decided by `opponent_score` -- how far the people you
#: beat went -- which says nothing about how good they were: a champion can
#: get through weak opponents who happened to place well. Accumulated rating
#: asks the question the badge is actually for, so it is the only test now.
#:
#: The thresholds are not 80% and 20%, and the reason is arithmetic rather
#: than taste. A champion beats about five of the thirty-one others, so
#: their share of the field's rating cannot approach 80% however strong
#: those five are. Measured over 140 real careers it ran from 9.7% to 45.8%,
#: centred on 25.3% -- read against 80/20 the crown is unreachable and the
#: medal fires on a rounding error.
#:
#: Both are set from that measured distribution rather than by eye, so each
#: mark stays roughly as rare as the other: the crown comes up on about 12%
#: of runs and the medal on 10%. Retuning either means measuring again --
#: they are percentiles of a distribution, not round numbers.
PROVEN_TITLE, MODEST_TITLE = " 👑", " 🥇"
PROVEN_SHARE = 0.36
MODEST_SHARE = 0.15


def beaten_rating(competitor):
    """What the opponents this competitor beat are worth, added up.

    The player is left out. Their rating climbs on a different scale from the
    competitors' -- it is the only one with no ceiling -- so a road that
    happened to include them would look hard whoever walked it. That holds
    when the player is the champion too: the question is who they beat.

    Read live rather than from `base_strength`, so a competitor on form
    counts for what they are worth now.
    """
    total = 0
    for name in (getattr(competitor, "run_defeated", None) or []):
        other = list_of_competitors.get(name)
        if other is not None and not other.main:
            total += other.strength
    return total


def road_mark(champion, field):
    """PROVEN_TITLE, MODEST_TITLE or "" for this champion's road.

    The opponents they beat are added up and measured against the whole
    bracket's rating added up. Everybody in the field counts, the player
    included -- beating them is a real part of a road, and the same rating
    sits on both sides of the fraction so it cannot tilt one without the
    other. The champion's own rating is the only thing left out, since they
    cannot draw themselves.
    """
    beaten = [list_of_competitors[name] for name
              in (getattr(champion, "run_defeated", None) or [])
              if name in list_of_competitors]
    if not beaten:
        return ""
    theirs = sum(who.strength for who in beaten)
    whole = sum(list_of_competitors[name].strength for name in field
                if name in list_of_competitors
                and list_of_competitors[name] is not champion)
    if whole <= 0:
        return ""
    share = theirs / whole
    if share > PROVEN_SHARE:
        return PROVEN_TITLE
    if share <= MODEST_SHARE:
        return MODEST_TITLE
    return ""


def match_rating_steps(me):
    """What each of this competitor's matches was worth, in rating.

    Only the player has one, and that is a fact about the design rather than
    a gap: `elo_rating` applies an Elo step per match to the Protagonist,
    while every other competitor's rating moves once per career in
    `competitor_form` -- on the whole run, against what their rating
    predicted. There is no per-round figure to report for them, so this
    returns an empty list and the interface shows nothing.

    Deterministic from the two ratings and the result, and `me.strength` is
    not touched until every step has been added up -- so calling this from
    `scoreboard`, which runs first, gets exactly the numbers `elo_rating`
    will go on to apply.
    """
    if not getattr(me, "main", False):
        return []
    steps = []
    faced = list(getattr(me, "opponent", None) or [])
    results = list(getattr(me, "win_order", None) or [])
    for index, opponent in enumerate(faced[:len(results)]):
        won = results[index] == 1
        match_rating = opponent.strength + me.strength
        proportion = (opponent.strength if won else me.strength) / match_rating
        step = int(round(math.sqrt(match_rating) * proportion
                         * (1 if won else -1)))
        # starter protection, as elo_rating has always applied it
        step += 1 if step < 0 else 0
        steps.append(step)
    return steps


def scoreboard():

    # calculating opponent stage as tiebreaks
    for participant in GameSystem.participants:
        participant = list_of_competitors[participant]
        for index, opponent in enumerate(participant.opponent):
            participant.opponent_score += (opponent.stage - 1) * (participant.win_order[index] + 1)

    print(f"{CBOLD}{CYELLOW2}Leaderboard:{CEND}")
    print(f"{CBOLD}|| RANK || NAME                   || PTS || OS || NKS ||{CEND}")
    GameSystem.participants = sorted(GameSystem.participants,
                                     key=lambda x: (-list_of_competitors[x].stage, -list_of_competitors[x].opponent_score,
                                                    -list_of_competitors[x].score, list_of_competitors[x].strength))
    # player always participate
    attendance = list_of_competitors['Protagonist'].participation
    for index, competitor in enumerate(GameSystem.participants):
        competitor = list_of_competitors[competitor]
        print(f"{CBOLD}", end='')
        print(f"||  {index + 1}{' ' * (3 - len(str(index + 1)))} "
              f"|| {competitor.nickname}[{competitor.strength}]{' ' * (20 - len(competitor.nickname) - len(str(competitor.strength)))} "
              f"||  {competitor.stage - 1}  || {competitor.opponent_score}{' ' * (2 - len(str(competitor.opponent_score)))} "
              f"|| {competitor.score}{' ' * (3 - len(str(competitor.score)))} ||{CEND}")
        # The crown and the medal are the road the champion walked, in the
        # rating of the opponents they actually beat. `opponent_score`
        # decided this once and no longer does: it counts how far those
        # people went, not how good they were.
        trophy = road_mark(list_of_competitors[GameSystem.participants[0]],
                           GameSystem.participants)
        # A fourth element: who the champion of this run got through. Stored
        # against every competitor's own history entry, because the champion
        # roll is read off the player's history and has to name them without
        # loading anybody else's save.
        champion = list_of_competitors[GameSystem.participants[0]]
        beaten = [list_of_competitors[name].nickname
                  for name in (getattr(champion, "run_defeated", None) or [])
                  if name in list_of_competitors]
        # A fifth element: this competitor's own path through the run, in the
        # order the matches were played, each step marked won or lost.
        #
        # It used to be built by listing run_defeated and then run_lost_to,
        # which sorts the path by *result* rather than by round: a run that
        # went win, loss, win read as win, win, loss. That is only right for
        # single elimination, and this is a Swiss tournament -- everybody
        # plays every round, so losses sit in the middle of a path.
        #
        # `opponent` and `win_order` are the record that was always in match
        # order: both are appended once per battle, together, in
        # battle_win_condition. They are per-run, being rebuilt each launch
        # and never saved. run_defeated is still what the champion roll reads.
        # A third element per step: what that match moved the rating by, so
        # the Tournaments tab can show the run round by round rather than
        # only as a finishing rank. None for everybody but the player -- see
        # match_rating_steps. Older saves hold two-element steps and every
        # reader of this list copes with both lengths.
        steps = match_rating_steps(competitor)
        own = [[them.nickname, result == 1,
                steps[position] if position < len(steps) else None]
               for position, (them, result)
               in enumerate(zip(getattr(competitor, "opponent", None) or [],
                                getattr(competitor, "win_order", None) or []))]
        competitor.history[attendance] = (champion.nickname + trophy,
                                          index + 1, competitor.strength,
                                          beaten, own)
        if index == 0:
            competitor.championship += 1
        competitor.participation += 1


def save_game():
    # You may keep as many of your team as you like, up to a full six.
    # It used to depend on how far you got -- 6 as World Champion, 4 in the
    # semis, otherwise 3 -- which meant an early exit quietly threw away
    # Pokemon you had chosen to keep.
    keep_team, keep_list = [], set()
    for pokemon in list_of_competitors['Protagonist'].team:
        print(f"\n{CBOLD}{pokemon.name}:")
        print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}({pokemon.iv[x]})" for x in range(6)], "Total:", f"{pokemon.total_stats}({pokemon.total_iv})")
        print(f"Ability: {pokemon.ability} || Moveset: {pokemon.moveset}{CEND}")

    while True:
        print(f"\n{[(index, pokemon.name) for index, pokemon in enumerate(list_of_competitors['Protagonist'].team)]}")
        with suppress(KeyError, ValueError):
            acceptable_values = list(range(0, len(list_of_competitors['Protagonist'].team)))
            keep_number = min(MAX_POKEMON, len(list_of_competitors['Protagonist'].team))
            if len(keep_list) >= keep_number:
                break
            keep = int(input(f"You can keep at most {keep_number} Pokemon for your next run. Pick them one at a time, then enter 9 when you are done: "))

            if keep == 9:
                break
            elif keep not in acceptable_values:
                pass
            else:
                keep_list.add(keep)
    for index in keep_list:
        keep_team.append(list_of_competitors['Protagonist'].team[index])

    # preserved team
    list_of_competitors['Protagonist'].team = keep_team

    # The save is JSON now (see Scripts/Game/savefile.py). It stores the few
    # facts that need to outlive a run, keyed by name, and rebuilds the rest
    # from the CSVs on load -- so there is no longer a list of attributes to
    # delete here just to make the objects picklable, and renaming a
    # competitor no longer makes older saves unloadable.
    savefile.save(list_of_competitors)


#: How far a competitor's rating can move in one career, and how far it may
#: ever get from the rating they shipped with -- both as a fraction of that
#: shipped rating, so a 1000-rated competitor moves in tens and a 20-rated
#: one in ones.
#:
#: This is deliberately **not** the Elo formula `elo_rating()` uses for the
#: player. Elo is an exchange: what one competitor gains another loses, and
#: with 80 matches a career and no anchor the field random-walks apart --
#: measured at +467/-223 on individuals over 200 careers, with the pool
#: spreading from 193 to 233. What a competitor's rating is *for* here is
#: choosing their team (`PLAYER_IV(participant.strength)`) and ordering the
#: bracket, so it wants to stay near where it was designed while still
#: moving enough for the player to notice.
FORM_SWING = 0.03
FORM_BAND = 0.30


def competitor_form():
    """Move each competitor's rating on how their run actually went.

    The comparison is with what their rating *predicted*, not with an even
    50% -- and that is the whole design. Against a 50% baseline every
    competitor above the median wins more than half by definition, so they
    climb every career until the band stops them, and everyone below sinks:
    measured over 200 careers, 43 of 69 pinned to an edge and the ladder
    stretched from 193 to 226 while ranks barely moved. Against their own
    predicted record the expected move is zero, so the band is a safety net
    rather than the mechanism: 1.8 of 69 pinned after 50 careers, the spread
    holds at 193, and 39 of 69 change rank.

    A competitor-vs-competitor match is not battled -- it is a weighted coin
    on rating (`battle_win_condition`) -- so the prediction here uses exactly
    that rule against the opponents they actually drew. Swiss pairing means
    a competitor who wins early meets stronger opponents later, and reading
    the real draw is what accounts for it.

    Every delta is worked out before any is applied. Ratings are read off
    the opponents, so updating in the loop would score later competitors
    against ratings the same career had already moved.
    """
    moves = {}
    for competitor in list_of_competitors.values():
        if competitor.main:
            continue
        faced = list(getattr(competitor, "opponent", []) or [])
        results = list(getattr(competitor, "win_order", []) or [])
        matches = min(len(faced), len(results))
        if not matches:
            continue                      # not in this career's field
        mine = competitor.strength
        record = sum(results[:matches]) / matches
        predicted = sum(mine / max(1, mine + other.strength)
                        for other in faced[:matches]) / matches
        shipped = getattr(competitor, "base_strength", mine) or mine
        step = FORM_SWING * shipped * (record - predicted) * 2
        # the randomised part: the size of the move, never its direction
        step *= random.uniform(0.5, 1.5)
        low, high = shipped * (1 - FORM_BAND), shipped * (1 + FORM_BAND)
        moves[competitor] = int(round(max(1, min(high, max(low, mine + step)))))
    for competitor, rating in moves.items():
        competitor.strength = rating


def elo_rating():
    """Apply the run's rating change, and say what each match was worth.

    Every figure printed here is also said as a *fact* -- see
    Scripts/Art/narrator.py. The interface used to run a regular expression
    over "Nickname: Win [+12]" to recover a number this function had just
    worked out; it listens now, so retuning the wording cannot break it.

    The win or loss for each match is read by position. It used to be read
    with `me.opponent.index(opponent)`, which finds the *first* entry equal
    to that opponent -- so meeting somebody twice in one run would have
    scored the second meeting with the result of the first.
    """
    me = list_of_competitors['Protagonist']
    rating_change = 0
    # One copy of the arithmetic, in match_rating_steps, because `scoreboard`
    # records the same numbers into the run history before this runs and two
    # copies would be free to drift apart.
    steps = match_rating_steps(me)
    with suppress(IndexError):
        narrator.say(f"\n{CBOLD}Opponent Journey:{CEND}", "result")
        for index, opponent in enumerate(me.opponent):
            won = me.win_order[index] == 1
            individual_rating_change = steps[index]
            rating_change += individual_rating_change

            narrator.say(
                f"{opponent.nickname}: "
                f"{'Win' if won else 'Lose'} "
                f"[{'+' if individual_rating_change >= 0 else '-'}"
                f"{abs(individual_rating_change)}]{CEND}",
                "result", nickname=opponent.nickname, won=won,
                rating_change=individual_rating_change,
                strength=opponent.strength)

    narrator.say(f"You have {'gained' if rating_change > 0 else 'lost'} "
                 f"{abs(rating_change)} ratings.",
                 "result", total_rating_change=rating_change)
    me.strength = max(me.strength + rating_change, 1)


def restart():
    # restart
    # this will break in powershell, but not in exe
    print("Loading......")
    os.execl(sys.executable, '"{}"'.format(sys.executable), *sys.argv)
