import random
import pickle
from contextlib import suppress
from game_system import *
from text_color import *
from competitors import *
from single_elimination_bracket import *
from copy import deepcopy
from custom_team import *
from constants import *
from ai import *
import sys


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


def team_generation(participant):
    # pokemon is divided to 6 tier (very low, low, medium, high, very high, custom)
    # should be selected based on strength
    nominal_team, unavailable_pokemon = [], set()
    random_iv_on_tier = {"Low": 0, "Intermediate": 8, "Advanced": 16, "Elite": 24, "Champion": 31, "Protagonist": min(31, int(participant.strength / 250 * 31))}
    custom_team(participant)

    # buff AI pokemon
    ratings = participant.strength * 1.2 if not participant.main else participant.strength
    # weights formula
    very_low = max(0, 40 - ratings)
    low = max(0, 80 - ratings)
    medium = min(60, 3 + ratings) if ratings <= 57 else max(0, 117 - ratings)
    high = min(max(0, ratings - 50), 70)
    very_high = min(max(0, ratings - 80), 120)
    ultra_high = 0 if ratings < 100 else 2 if ratings < 120 else 4 if ratings < 140 else 6 if ratings < 160 \
        else 8 if ratings < 180 else 10 if ratings < 200 else 12
    # new version
    tier_list = random.choices(["Very Low", "Low", "Medium", "High", "Very High", "Ultra High"],
                               weights=[very_low, low, medium, high, very_high, ultra_high],
                               k=ROUND_LIMIT[GameSystem.stage] - len(participant.team))
    for pokemon in participant.team:
        unavailable_pokemon.add(pokemon) if isinstance(pokemon, str) else unavailable_pokemon.add(pokemon.name)
    for tier in tier_list:
        new_pokemon = random.choice([pokemon for pokemon in list(list_of_pokemon) if
                                     pokemon not in unavailable_pokemon and list_of_pokemon[pokemon].tier == tier])
        nominal_team.append(new_pokemon)
        unavailable_pokemon.add(new_pokemon)
    print(tier_list)  # debug

    with suppress(ValueError):
        # ace pokemon are put at the last (but the ai can still take it out when he wants)
        participant.team = nominal_team + participant.team
    for i in range(len(participant.team)):
        try:
            pokemon = deepcopy(list_of_pokemon[participant.team[i]])
            pokemon.iv = [random.randint(random_iv_on_tier[participant.level], 31) for _ in range(6)] if pokemon.iv == 0 else pokemon.iv
            pokemon.total_iv = sum(pokemon.iv)
            pokemon.nominal_base_stats = list(map(operator.add, pokemon.base_stats, pokemon.iv))
            pokemon.ability = [random.choice(pokemon.ability)]
            pokemon.moveset = random.sample(pokemon.moveset, min(4, len(pokemon.moveset)))
            participant.team[i] = pokemon
        except:
            pokemon = deepcopy(participant.team[i])
            pokemon.total_stats = sum(pokemon.base_stats)
            pokemon.total_iv = sum(pokemon.iv)
            pokemon.nominal_base_stats = list(map(operator.add, pokemon.base_stats, pokemon.iv))
            participant.team[i] = pokemon
    # the order of the team matters
    # player can keep 6 pokemon
    if not participant.main:
        if len(participant.team) > ROUND_LIMIT[GameSystem.stage]:
            participant.team = participant.team[len(participant.team) - ROUND_LIMIT[GameSystem.stage]:len(participant.team)]

    return participant.team


def round_begin():
    colors = {"": "", "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}
    GameSystem.participants.sort(key=lambda x: list_of_competitors[x].stage, reverse=True)
    print(f"\nRound {GameSystem.stage}:\n")

    for i in range(0, int(math.pow(2, 5))):
        participant = list_of_competitors[GameSystem.participants[i]]
        participant.match_id = i // 2
        bold = CBOLD if participant.championship > 0 else ''
        crown = f' |{participant.championship}|' if participant.championship > 0 else ''
        print(colors[participant.color] + bold + EntryBox(participant.id, f"{participant.name} [{participant.strength}]{crown}", participant.stage - 1, ).structure + CEND)
        if i % 2 != 0:
            print("\n")


def round_end(stage):
    colors = {"": CWHITE2, "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}

    def result_announcement(victor, loser, main):
        level_order = {"Low": 1, "Intermediate": 2, "Advanced": 3, "Elite": 4, "Champion": 5, "Protagonist": 6}
        victor_crown, loser_crown = f' |{victor.championship}|' if victor.championship > 0 else '', f' |{loser.championship}|' if loser.championship > 0 else ''
        victor_bold, loser_bold = CBOLD if victor.championship > 0 else '', CBOLD if loser.championship > 0 else ''
        print(colors[victor.color] + victor_bold + EntryBox(victor.id, f"{victor.name} [{victor.strength}]{victor_crown}{' !!' if level_order[victor.level] < level_order[loser.level] else ''}", victor.stage - 1, ROUND_LIMIT[stage]).structure + CEND)
        if main:  # the protagonist battle
            print(CGREY + loser_bold + EntryBox(loser.id, f"{loser.name} [{loser.strength}]{loser_crown}",
                                   loser.stage - 1, loser.result).structure, "\n" + CEND)
        else:  # others' battle
            result = ROUND_LIMIT[stage] * loser.strength / (victor.strength + loser.strength)
            result = int(min(round(result * random.uniform(1.25, 1.75), 0), ROUND_LIMIT[stage] - 1))
            victor.score += ROUND_LIMIT[stage] - result
            loser.score += result - ROUND_LIMIT[stage]
            print(CGREY + loser_bold + EntryBox(loser.id, f"{loser.name} [{loser.strength}]{loser_crown}", loser.stage - 1, result).structure, "\n" + CEND)

    for i in range(0, int(math.pow(2, 5)), 2):
        one, two = list_of_competitors[GameSystem.participants[i]], list_of_competitors[GameSystem.participants[i + 1]]
        main = True
        victor = i if one.result > two.result else i + 1
        loser = i + 1 if victor == i else i
        if not (one.main or two.main):
            victor = i if random.random() < one.strength / (one.strength + two.strength) else i + 1
            loser = i + 1 if victor == i else i

            list_of_competitors[GameSystem.participants[victor]].stage += 1
            main = False
        result_announcement(list_of_competitors[GameSystem.participants[victor]],
                            list_of_competitors[GameSystem.participants[loser]], main)

        # save opponent in-game record
        list_of_competitors[GameSystem.participants[victor]].opponent.append(list_of_competitors[GameSystem.participants[loser]])
        list_of_competitors[GameSystem.participants[loser]].opponent.append(list_of_competitors[GameSystem.participants[victor]])
        list_of_competitors[GameSystem.participants[victor]].win_order.append(1)
        list_of_competitors[GameSystem.participants[loser]].win_order.append(0)
        # save opponent match history record
        list_of_competitors[GameSystem.participants[victor]].opponent_history[GameSystem.participants[loser]][0] += 1
        list_of_competitors[GameSystem.participants[loser]].opponent_history[GameSystem.participants[victor]][1] += 1


def scoreboard():
    colors = {"": "", "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}

    # calculating opponent stage as tiebreaks
    for participant in GameSystem.participants:
        participant = list_of_competitors[participant]
        for index, opponent in enumerate(participant.opponent):
            participant.opponent_score += (opponent.stage - 1) * participant.win_order[index]

    print(f"{CBOLD}{CYELLOW2}Leaderboard:{CEND}")
    print(f"{CBOLD}|| RANK || NAME                   || PTS || OS || NKS ||{CEND}")
    GameSystem.participants = sorted(GameSystem.participants,
                                     key=lambda x: (-list_of_competitors[x].stage, -list_of_competitors[x].opponent_score,
                                                    -list_of_competitors[x].score, list_of_competitors[x].strength))
    # player always participate
    attendance = list_of_competitors['Protagonist'].participation
    for index, competitor in enumerate(GameSystem.participants):
        competitor = list_of_competitors[competitor]
        print(f"{CBOLD}{colors[competitor.color]}", end='')
        print(f"||  {index + 1}{' ' * (3 - len(str(index + 1)))} "
              f"|| {competitor.name}[{competitor.strength}]{' ' * (20 - len(competitor.name) - len(str(competitor.strength)))} "
              f"||  {competitor.stage - 1}  || {competitor.opponent_score}{' ' * (2 - len(str(competitor.opponent_score)))} "
              f"|| {competitor.score}{' ' * (3 - len(str(competitor.score)))} ||{CEND}")
        trophy = ' 👑' if list_of_competitors[GameSystem.participants[0]].opponent_score >= 18 else ' 🥇' \
            if list_of_competitors[GameSystem.participants[0]].opponent_score <= 12 else ''
        competitor.history[attendance] = (list_of_competitors[GameSystem.participants[0]].name + trophy, index + 1, competitor.strength)
        if index == 0:
            competitor.championship += 1
        competitor.participation += 1


def save_game():
    # options to keep at most 3, 4, 6 pokemon and least 0 pokemon
    keep_team, keep_list = [], set()
    for pokemon in list_of_competitors['Protagonist'].team:
        print(f"\n{CBOLD}{pokemon.name}:")
        print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}({pokemon.iv[x]})" for x in range(6)], "Total:", f"{pokemon.total_stats}({pokemon.total_iv})")
        print(f"Ability: {pokemon.ability} || Moveset: {pokemon.moveset}{CEND}")

    while True:
        print(f"\n{[(index, pokemon.name) for index, pokemon in enumerate(list_of_competitors['Protagonist'].team)]}")
        with suppress(KeyError, ValueError):
            acceptable_values = list(range(0, len(list_of_competitors['Protagonist'].team)))
            keep_number = KEEP_POKEMON_WIN if list_of_competitors['Protagonist'].stage == 6 else \
                KEEP_POKEMON_SEMI if list_of_competitors['Protagonist'].stage == 5 else KEEP_POKEMON_LOST
            if len(keep_list) == keep_number:
                break
            keep = int(input(f"You can keep at most {keep_number} Pokemon for your next run. Enter 9 when you are done: ")) if list_of_competitors['Protagonist'].stage != 6 \
            else int(input(f"You can keep at most {keep_number} Pokemon for your next run. Enter 9 when you are done and 10 to keep the whole team: "))

            if keep == 9:
                break
            elif keep == 10:
                if list_of_competitors['Protagonist'].stage == 6:
                    for i in range(6):
                        keep_list.add(i)
            elif keep not in acceptable_values:
                pass
            else:
                keep_list.add(keep)
    for index in keep_list:
        keep_team.append(list_of_competitors['Protagonist'].team[index])

    # preserved team
    list_of_competitors['Protagonist'].team = keep_team

    # delete useless variables
    for competitor in list_of_competitors:
        competitor = list_of_competitors[competitor]
        to_delete = ['match_id', 'id', 'stage', 'result', 'level', 'music', 'ace_music', 'faster', 'side_color', 'color', 'in_battle_effects', 'entry_hazard',
                     'desc', 'opponent', 'opponent_score', 'win_order', 'score', 'quote']
        for variable in to_delete:
            delattr(competitor, variable)
        if not competitor.main:
            del competitor.team
            with suppress(AttributeError):
                del competitor.position_change

    with open('savefile.dat', 'wb') as f:
        pickle.dump([list_of_competitors[competitor] for competitor in list_of_competitors], f)


def elo_rating():
    colors = {"": "", "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}
    rating_change = 0
    with suppress(IndexError):
        print(f"\n{CBOLD}Opponent Journey:{CEND}")
        for opponent in list_of_competitors['Protagonist'].opponent:
            match_rating = opponent.strength + list_of_competitors['Protagonist'].strength
            proportion = (opponent.strength / match_rating) if list_of_competitors['Protagonist'].win_order[list_of_competitors['Protagonist'].opponent.index(opponent)] == 1 else (list_of_competitors['Protagonist'].strength / match_rating)
            result = 1 if list_of_competitors['Protagonist'].win_order[list_of_competitors['Protagonist'].opponent.index(opponent)] == 1 else -1
            individual_rating_change = int(round(math.sqrt(match_rating) * proportion * result))
            rating_change += individual_rating_change

            print(f"{colors[opponent.color]}{opponent.name}: {'Win' if list_of_competitors['Protagonist'].win_order[list_of_competitors['Protagonist'].opponent.index(opponent)] == 1 else 'Lose'} [{'+' if individual_rating_change >= 0 else '-'}{abs(individual_rating_change)}]{CEND}")

    print(f"You have {'gained' if rating_change > 0 else 'lost'} {abs(rating_change)} ratings.")
    list_of_competitors['Protagonist'].strength = max(list_of_competitors['Protagonist'].strength + rating_change, 1)


def restart():
    # restart
    # this will break in powershell, but not in exe
    print("Loading......")
    os.execl(sys.executable, '"{}"'.format(sys.executable), *sys.argv)
