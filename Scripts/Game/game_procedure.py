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
        trophy = ' 👑' if list_of_competitors[GameSystem.participants[0]].opponent_score >= 36 else ' 🥇' \
            if list_of_competitors[GameSystem.participants[0]].opponent_score <= 24 else ''
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
        own = [[them.nickname, result == 1] for them, result
               in zip(getattr(competitor, "opponent", None) or [],
                      getattr(competitor, "win_order", None) or [])]
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
    with suppress(IndexError):
        narrator.say(f"\n{CBOLD}Opponent Journey:{CEND}", "result")
        for index, opponent in enumerate(me.opponent):
            won = me.win_order[index] == 1
            match_rating = opponent.strength + me.strength
            proportion = (opponent.strength if won else me.strength) \
                / match_rating
            individual_rating_change = int(round(math.sqrt(match_rating)
                                                 * proportion
                                                 * (1 if won else -1)))
            # starter protection
            individual_rating_change += 1 if individual_rating_change < 0 else 0
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
