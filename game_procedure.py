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


def before_battle_option(protagonist, opponent):
    option = None
    choices = {0: proceed_to_battle, 1: view_pokemon, 2: switch_order, 3: spy_opponent, 4: check_history, 5: quit_game}
    text = "What do you want to do?\n" \
           "0: Battle || 1: View My Pokemon || 2: Switch Pokemon Order || 3: Spy on Opponent || 4: Check History || 5: Quit Game\n" \
           "--> "
    while option != 0:
        with suppress(ValueError, KeyError):
            print("")
            option = int(input(text))
            print("")
            choices[option](protagonist, opponent)
            if option == 3:
                del choices[3]
                text = f"What do you want to do?\n" \
                       f"0: Battle || 1: View My Pokemon || 2: Switch Pokemon Order || {CGREY}3: Spy on Opponent{CEND} || 4: Check History || 5: Quit Game\n" \
                       f"--> "


def proceed_to_battle(protagonist, opponent):
    print(f"{CBOLD}Round {GameSystem.stage}{CEND}")
    print(f"{CWHITE2}{CBOLD}{protagonist.name} [{protagonist.strength}] VS {opponent.name} [{opponent.strength}]{CEND}")
    print(f"{CITALIC}{CBOLD}This is a {ROUND_LIMIT[GameSystem.stage]}vs{ROUND_LIMIT[GameSystem.stage]} battle.{CEND}")


def view_pokemon(protagonist, opponent):
    statistics = {0: "HP", 1: "Atk", 2: "Def", 3: "SpA", 4: "SpDef", 5: "Speed"}
    for i, pokemon in enumerate(protagonist.team):
        print(f"{CBEIGE+CBOLD if i % 2 == 0 else CBOLD}ID: {pokemon.id} || Name: {pokemon.name} || Type: {pokemon.type}")
        print(f"Ability: {pokemon.ability}")
        print("Base Stats:", [f"{statistics[x]}: {pokemon.nominal_base_stats[x]}({pokemon.iv[x]})" for x in range(6)])
        print(f"Moveset: {pokemon.moveset}{CEND}\n")


def switch_order(protagonist, opponent):
    swap_pokemon_order = 0
    while not (1 <= swap_pokemon_order < len(protagonist.team)):
        with suppress(ValueError, IndexError):
            swap_pokemon_order = int(input(f'Which pokemon would you like to swap to be the first? Input 9 if you do not want to swap. '
                                           f'{[(index, pokemon.name) for index, pokemon in enumerate(protagonist.team)]} '))
            if swap_pokemon_order == 9:
                break
            else:
                protagonist.team[0], protagonist.team[swap_pokemon_order] = protagonist.team[swap_pokemon_order], protagonist.team[0]
                print(f'New Order: {CVIOLET2}{CBOLD}{[(index, pokemon.name) for index, pokemon in enumerate(protagonist.team)]}{CEND}\n')


def spy_opponent(protagonist, opponent):
    print(f"{CBOLD}Opponent Introduction:\n{CYELLOW}{opponent.desc}\nTier: {opponent.level}{CEND}")
    print(f"You have carefully sneaked into the training facility of {opponent.name}.")
    if random.random() <= 0.5 * protagonist.strength / opponent.strength:
        revealed_pokemon = opponent.team[0]
        print(f"You have found that {opponent.name} will be using {CVIOLET2}{CBOLD}{revealed_pokemon.name}{CEND} as the 1st Pokemon for the next round!")
        if random.random() <= 0.5:
            print(
                f"Not only that, but you found that {CVIOLET2}{CBOLD}{revealed_pokemon.name}{CEND} has the moveset {CVIOLET2}{CBOLD}{revealed_pokemon.moveset}{CEND}!!")
    else:
        print("Unfortunately, you have failed to obtain any useful information.")


def check_history(protagonist, opponent):
    colors = {"": "", "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}
    print(
        f"{CBOLD}{protagonist.name} {protagonist.opponent_history[opponent.name][0]} : {protagonist.opponent_history[opponent.name][1]} {opponent.name}{CEND}")
    print(f"\nYou have participated the Pokemon Championship for {protagonist.participation} time(s), with {protagonist.championship} World Champion title(s).")
    for i in range(len(protagonist.opponent)):
        print(f"{colors[protagonist.opponent[i].color]}{protagonist.opponent[i].name}: {'Win' if protagonist.win_order[i] == 1 else 'Lose'}{CEND}")
    print(
        f"\nYour opponent {opponent.name} has participated the Pokemon Championship for {opponent.participation} time(s), with {opponent.championship} World Champion title(s).")
    for i in range(len(opponent.opponent)):
        print(f"{colors[opponent.opponent[i].color]}{opponent.opponent[i].name}: {'Win' if opponent.win_order[i] == 1 else 'Lose'}{CEND}")
    confirmation = input("\nWanna know the Pokemon Championship history? Press Y to confirm: ").upper()
    if confirmation == 'Y':
        print(f"\nYour Pokemon Championship history: ")
        for parti, hist in protagonist.history.items():
            print(f"#{parti + 1}: Rank {hist[1]} | Ratings {hist[2]}")
        print(f"\nYour opponent's Pokemon Championship history: ")
        for parti, hist in opponent.history.items():
            print(f"#{parti + 1}: Rank {hist[1]}")
        print(f"\nThe Champion of the Pokemon Championship: ")
        for parti, hist in protagonist.history.items():
            print(f"#{parti + 1}: {hist[0]}")


def quit_game(protagonist, opponent):
    elo_rating()
    save_game()
    sys.exit()


def team_selection(protagonist):
    # exclusive to player
    # select pokemon when there is too many
    unused_list = set()
    print(f"You have more Pokemon than needed for this round! Select {len(protagonist.team) - ROUND_LIMIT[GameSystem.stage]} "
          f"Pokemon you DO NOT need this round:")
    for pokemon in protagonist.team:
        print(f"\n{CBOLD}{pokemon.name}:")
        print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}({pokemon.iv[x]})" for x in range(6)])
        print(f"Ability: {pokemon.ability} || Moveset: {pokemon.moveset}{CEND}")
    while len(unused_list) != len(protagonist.team) - ROUND_LIMIT[GameSystem.stage]:
        print(f"\n{[(index, pokemon.name) for index, pokemon in enumerate(protagonist.team)]}")
        with suppress(KeyError, ValueError, IndexError):
            unused = int(input(f"Select the Pokemon you DO NOT need this round: "))
            unused_list.add(unused)
    unused_list = sorted(unused_list, reverse=True)
    for index in unused_list:
        protagonist.unused_team.append(protagonist.team[index])
        del protagonist.team[index]
    return protagonist.team


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
    # strength limit: low 20 | intermediate 70 | advanced 120 | lower elite 228 | upper elite 357 | champion 600
    random_iv_on_tier = {"Low": 0, "Intermediate": 8, "Advanced": 16, "Elite": 24, "Champion": 31, "Protagonist": min(31, int(participant.strength / 120 * 31))}
    custom_team(participant)
    # weights formula
    very_low = max(0, 40 - participant.strength * 2)
    low = 60 - participant.strength if participant.strength <= 15 else max(0, 75 - participant.strength * 2)
    medium = min(40, 3 + participant.strength) if participant.strength <= 37 else max(0, 78 - participant.strength)
    high = min(max(0, participant.strength - 30), 70) if participant.strength <= 100 else max(0, 170 - participant.strength)
    very_high = min(max(0, participant.strength - 60), 50)
    ultra_high = 0 if participant.strength <= 100 else 1 if participant.strength <= 200 else 2
    # new version
    # at strength 120, always get very high tier pokemon
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
        # debug
        # print(unavailable_pokemon)
    print(tier_list)  # debug

    with suppress(ValueError):
        # ace pokemon are put at the last (but the ai can still take it out when he wants)
        participant.team = nominal_team + participant.team
    for i in range(len(participant.team)):
        try:
            pokemon = deepcopy(list_of_pokemon[participant.team[i]])
            pokemon.iv = [random.randint(random_iv_on_tier[participant.level], 31) for _ in range(6)] if pokemon.iv == 0 else pokemon.iv
            pokemon.nominal_base_stats = list(map(operator.add, pokemon.base_stats, pokemon.iv))
            pokemon.ability = random.choice(pokemon.ability)
            pokemon.moveset = random.sample(pokemon.moveset, min(4, len(pokemon.moveset)))
            participant.team[i] = pokemon
        except:
            pokemon = deepcopy(participant.team[i])
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
        print(
            colors[participant.color] + EntryBox(participant.id, f"{participant.name} [{participant.strength}]", participant.stage - 1, ).structure + CEND)
        if i % 2 != 0:
            print("\n")


def round_end(stage):
    colors = {"": CWHITE2, "Yellow": CYELLOW2, "DarkRed": CRED, "Green": CGREEN2}

    def result_announcement(victor, loser, main):
        level_order = {"Low": 1, "Intermediate": 2, "Advanced": 3, "Elite": 4, "Champion": 5, "Protagonist": 6}
        print(colors[victor.color] + EntryBox(victor.id, f"{victor.name} [{victor.strength}]{' !!!' if level_order[victor.level] < level_order[loser.level] else ''}", victor.stage - 1, ROUND_LIMIT[stage]).structure + CEND)
        if main:  # the protagonist battle
            print(CGREY + EntryBox(loser.id, f"{loser.name} [{loser.strength}]",
                                   loser.stage - 1, loser.result).structure, "\n" + CEND)
        else:  # others' battle
            result = ROUND_LIMIT[stage] * loser.strength / (victor.strength + loser.strength)
            result = int(min(round(result * random.uniform(1.25, 1.75), 0), ROUND_LIMIT[stage] - 1))
            victor.score += ROUND_LIMIT[stage] - result
            loser.score += result - ROUND_LIMIT[stage]
            print(CGREY + EntryBox(loser.id, f"{loser.name} [{loser.strength}]", loser.stage - 1, result).structure, "\n" + CEND)

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
    print(f"{CBOLD}{CYELLOW2}Leaderboard:{CEND}")
    print(f"{CBOLD}|| RANK || NAME                       || PTS || NKS ||{CEND}")
    GameSystem.participants = sorted(GameSystem.participants,
                                     key=lambda x: (-list_of_competitors[x].stage, -list_of_competitors[x].score, list_of_competitors[x].strength))
    attendance = list_of_competitors['Protagonist'].participation
    for index, competitor in enumerate(GameSystem.participants):
        competitor = list_of_competitors[competitor]
        print(f"{CBOLD}{colors[competitor.color]}", end='')
        print(f"||  {index + 1}{' ' * (3 - len(str(index + 1)))} "
              f"|| {competitor.name}[{competitor.strength}]{' ' * (24 - len(competitor.name) - len(str(competitor.strength)))} "
              f"||  {competitor.stage - 1}  || {competitor.score}{' ' * (3 - len(str(competitor.score)))} ||{CEND}")
        competitor.history[attendance] = (list_of_competitors[GameSystem.participants[0]].name, index + 1, competitor.strength)
        if index == 0:
            competitor.championship += 1
        competitor.participation += 1


def save_game():
    # options to keep at most 2 pokemon and least 0 pokemon
    keep_team, keep_list = [], set()
    for pokemon in list_of_competitors['Protagonist'].team:
        print(f"\n{CBOLD}{pokemon.name}:")
        print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}({pokemon.iv[x]})" for x in range(6)])
        print(f"Ability: {pokemon.ability} || Moveset: {pokemon.moveset}{CEND}")

    while True:
        print(f"\n{[(index, pokemon.name) for index, pokemon in enumerate(list_of_competitors['Protagonist'].team)]}")
        with suppress(KeyError, ValueError):
            acceptable_values = list(range(0, len(list_of_competitors['Protagonist'].team)))
            keep_number = KEEP_POKEMON_WIN if list_of_competitors['Protagonist'].stage == 6 else \
                KEEP_POKEMON_SEMI if list_of_competitors['Protagonist'].stage == 5 else \
                    KEEP_POKEMON_LOST
            if len(keep_list) == keep_number:
                break
            keep = int(input(f"You can keep at most {keep_number} Pokemon for your next run. Select 9 when you are done: "))

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

    # delete useless variables
    for competitor in list_of_competitors:
        competitor = list_of_competitors[competitor]
        to_delete = ['match_id', 'id', 'stage', 'result', 'level', 'music', 'ace_music', 'faster', 'color', 'in_battle_effects', 'entry_hazard',
                     'desc', 'opponent', 'win_order', 'score', 'quote']
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
        for opponent in list_of_competitors['Protagonist'].opponent:
            match_rating = opponent.strength + list_of_competitors['Protagonist'].strength
            proportion = (opponent.strength / match_rating) if list_of_competitors['Protagonist'].win_order[list_of_competitors['Protagonist'].opponent.index(opponent)] == 1 else (list_of_competitors['Protagonist'].strength / match_rating)
            result = 1 if list_of_competitors['Protagonist'].win_order[list_of_competitors['Protagonist'].opponent.index(opponent)] == 1 else -1
            individual_rating_change = int(round(math.sqrt(match_rating // 2) * proportion * result))
            rating_change += individual_rating_change

            print(f"{colors[opponent.color]}{opponent.name}: {'Win' if list_of_competitors['Protagonist'].win_order[list_of_competitors['Protagonist'].opponent.index(opponent)] == 1 else 'Lose'} [{'+' if individual_rating_change >= 0 else '-'}{abs(individual_rating_change)}]{CEND}")

    print(f"You have {'gained' if rating_change > 0 else 'lost'} {abs(rating_change)} ratings.")
    list_of_competitors['Protagonist'].strength = max(list_of_competitors['Protagonist'].strength + rating_change, 1)


def restart():
    # restart
    # this will break in powershell, but not in exe
    print("Loading......")
    os.execl(sys.executable, '"{}"'.format(sys.executable), *sys.argv)
