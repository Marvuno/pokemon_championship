from Scripts.Battle.battle_checklist import *
from Scripts.Battle.battle_initialization import *
from Scripts.Battle.battle_move_execution import *
from Scripts.Battle.battle_win_condition import *
from Scripts.Battle.move_additional_effect import *
from Scripts.Game.game_procedure import *
from Scripts.Data.abilities import *
from Scripts.Data.character_abilities import *
from Scripts.Art.music import *


def battle_setup(protagonist, competitor, player_team, opponent_team, battleground):
    if battleground.verbose:
        for pokemon in player_team:
            print(f"{CGREEN2}{CBOLD}{pokemon.name} {pokemon.nominal_base_stats} {pokemon.iv} {pokemon.moveset} {pokemon.ability}{CEND}")
        for pokemon in opponent_team:
            print(f"{CRED2}{CBOLD}{pokemon.name} {pokemon.nominal_base_stats} {pokemon.iv} {pokemon.moveset} {pokemon.ability}{CEND}")

    for pokemon, pokemon2 in zip(player_team, opponent_team):
        # side 1
        pokemon.hp = math.floor(0.01 * 2 * pokemon.nominal_base_stats[0] * 100) + 100 + 10 if pokemon.name != "Shedinja" else 1
        pokemon.battle_stats = [pokemon.hp] + [math.floor(0.01 * 2 * pokemon.nominal_base_stats[x] * 100 + 5) for x in range(1, 6)]
        pokemon.moveset = ['Switching'] + pokemon.moveset
        pokemon.side_color = CGREEN2 + CBOLD
        pokemon.default_name, pokemon.default_ability, pokemon.default_type = deepcopy(pokemon.name), deepcopy(pokemon.ability), deepcopy(pokemon.type)
        pokemon.default_nominal_base_stats = deepcopy(pokemon.nominal_base_stats)
        # side 2
        pokemon2.hp = math.floor(0.01 * 2 * pokemon2.nominal_base_stats[0] * 100) + 100 + 10 if pokemon2.name != "Shedinja" else 1
        pokemon2.battle_stats = [pokemon2.hp] + [math.floor(0.01 * 2 * pokemon2.nominal_base_stats[x] * 100 + 5) for x in range(1, 6)]
        pokemon2.moveset = ['Switching'] + pokemon2.moveset
        pokemon2.side_color = CRED2 + CBOLD
        pokemon2.default_name, pokemon2.default_ability, pokemon2.default_type = deepcopy(pokemon2.name), deepcopy(pokemon2.ability), deepcopy(pokemon2.type)
        pokemon2.default_nominal_base_stats = deepcopy(pokemon2.nominal_base_stats)

    # color for different side
    protagonist.side_color = CGREEN2 + CBOLD
    competitor.side_color = CRED2 + CBOLD

    # select weather
    battleground.starting_weather_effect = random.choices(['Clear', 'Rain', 'Sunny', 'Sandstorm', 'Hail'], weights=[6, 1, 1, 1, 1], k=1)[0]
    battleground.weather_effect = battleground.starting_weather_effect

    player, opponent = player_team[0], opponent_team[0]

    # character ability at start
    UseCharacterAbility(protagonist, competitor, player, opponent, battleground, "", abilityphase=0)
    UseCharacterAbility(competitor, protagonist, opponent, player, battleground, "", abilityphase=0)

    switched_in_initialization(protagonist, competitor, player, opponent, battleground)
    switched_in_initialization(competitor, protagonist, opponent, player, battleground)

    # music on
    music(audio=f"Assets/music/{competitor.music}", loop=True)

    move_selection(protagonist, competitor, player_team, opponent_team, player, opponent, battleground)


def move_selection(protagonist, competitor, player_team, opponent_team, player, opponent, battleground):
    while battleground.battle_continuation:
        player.battle_stats = [player.battle_stats[0]] + \
                              [math.floor(0.01 * 2 * player.nominal_base_stats[x] * modifierChart[x][player.modifier[x]] * 100 + 5) for x in range(1, 6)]
        opponent.battle_stats = [opponent.battle_stats[0]] + \
                                [math.floor(0.01 * 2 * opponent.nominal_base_stats[x] * modifierChart[x][opponent.modifier[x]] * 100 + 5) for x in range(1, 6)]

        print(f"\n\n{CBOLD}{weather_conversionChart.get(battleground.weather_effect)} [{battleground.weather_effect}]\n"
              f"{battleground.field_effect}\nTurn {battleground.turn}\n{CEND}")

        # # debug mode stats display
        # print(CGREEN2 + CBOLD +
        #       player.name, player.type, player.ability, player.moveset[1:5],
        #       player.status, "\n",
        #       [f"{STATISTICS[x]}: {player.battle_stats[x]}" for x in range(len(player.battle_stats))],
        #       player.iv,
        #       player.modifier, "\n",
        #       [f"{key}: {value}" for key, value in player.volatile_status.items() if value > 0], "\n",
        #       "In-battle Effects:", [f"{key}: {value}" for key, value in protagonist.in_battle_effects.items() if value > 0],
        #       "|| Entry Hazard:", [f"{key}: {value}" for key, value in protagonist.entry_hazard.items() if value > 0],
        #       "|| Protection:", player.protection,
        #       "|| Charging:", player.charging,
        #       "|| Disabled:", player.disabled_moves, "\n",
        #       "Move History:", player.move_order,
        #       hp_bar_display(player))
        #
        # print(CRED2 + CBOLD +
        #       opponent.name, opponent.type, opponent.ability, opponent.moveset[1:5],
        #       opponent.status, "\n",
        #       [f"{STATISTICS[x]}: {opponent.battle_stats[x]}" for x in range(len(opponent.battle_stats))],
        #       opponent.iv,
        #       opponent.modifier, "\n",
        #       [f"{key}: {value}" for key, value in opponent.volatile_status.items() if value > 0], "\n",
        #       "In-battle Effects:", [f"{key}: {value}" for key, value in competitor.in_battle_effects.items() if value > 0],
        #       "|| Entry Hazard:", [f"{key}: {value}" for key, value in competitor.entry_hazard.items() if value > 0],
        #       "|| Protection:", opponent.protection,
        #       "|| Charging:", opponent.charging,
        #       "|| Disabled:", opponent.disabled_moves, "\n",
        #       "Move History:", opponent.move_order,
        #       hp_bar_display(opponent),
        #       "\n" + CEND)

        # actual stats display
        print(protagonist.side_color +
              player.name, player.type, player.ability,
              "\nStatus:", player.status,
              "\nBase Stats:", [f"{STATISTICS[x]}: {player.battle_stats[x]}" for x in range(len(player.battle_stats))],
              "\nStats Change:", player.modifier,
              "\nVolatile Status:", [f"{key}{': ' + str(value) if key == 'Turn' else ''}" for key, value in player.volatile_status.items() if value > 0],
              "\nIn-battle Effects:", [f"{key}: {value}" for key, value in protagonist.in_battle_effects.items() if value > 0],
              "|| Entry Hazard:", [f"{key}: {value}" for key, value in protagonist.entry_hazard.items() if value > 0],
              "|| Protection:", player.protection,
              "\nCharging:", player.charging,
              "|| Disabled:", player.disabled_moves,
              hp_bar_display(player), '\n')

        print(competitor.side_color +
              opponent.name, opponent.type,
              "\nStatus:", opponent.status,
              "\nStats Change:", opponent.modifier,
              "\nVolatile Status:", [f"{key}{': ' + str(value) if key == 'Turn' else ''}" for key, value in opponent.volatile_status.items() if value > 0],
              "\nIn-battle Effects:", [f"{key}: {value}" for key, value in competitor.in_battle_effects.items() if value > 0],
              "|| Entry Hazard:", [f"{key}: {value}" for key, value in competitor.entry_hazard.items() if value > 0],
              "|| Protection:", opponent.protection,
              "\nCharging:", opponent.charging,
              "|| Disabled:", opponent.disabled_moves,
              hp_bar_display(opponent),
              "\n" + CEND)

        # add turn
        battleground.turn += 1
        player.volatile_status['Turn'] += 1
        opponent.volatile_status['Turn'] += 1

        battleground.reality = False

        # for ai simulation
        if battleground.verbose:
            player_move = smart_ai_select_move(battleground, competitor, protagonist)
            opponent_move = smart_ai_select_move(battleground, protagonist, competitor)

        # player vs ai
        else:
            player_move = select_move(player, opponent, battleground) if not battleground.auto_battle else auto_ai_select_move(battleground, competitor,
                                                                                                                               protagonist)
            opponent_move = smart_ai_select_move(battleground, protagonist, competitor) if competitor.strength >= 30 \
                else dumb_ai_select_move(battleground, protagonist, competitor)
            # player_move, opponent_move = select_move(player), select_move(opponent)

        # switching
        # for ai simulation
        if player_move.name == "Switching":
            if battleground.verbose:
                player = switching_mechanism(protagonist, competitor, battleground, player_team, opponent_team, protagonist.position_change, False)
                player_team = protagonist.team
            # player vs ai
            else:
                # not auto battle
                if not battleground.auto_battle:
                    current_player = player
                    while player == current_player and player_move.name == "Switching":
                        player = switching_criteria(protagonist, competitor, player_team, opponent_team, battleground)
                        if player == current_player:
                            player_move = select_move(player, opponent, battleground)
                # auto battle
                else:
                    player = switching_mechanism(protagonist, competitor, battleground, player_team, opponent_team,
                                                 ai_switching_mechanism(competitor, protagonist, battleground, True, True), False)
                    player_team = protagonist.team

        # ai switching
        if opponent_move.name == "Switching":
            # opponent = switching_criteria(competitor, protagonist, opponent_team, player_team, battleground)
            opponent = switching_mechanism(competitor, protagonist, battleground, opponent_team, player_team, competitor.position_change, False)
            opponent_team = competitor.team

        battleground.reality = True

        player_move, opponent_move = deepcopy(player_move), deepcopy(opponent_move)

        compare_speed(protagonist, competitor, player_team, opponent_team, player, opponent, battleground, player_move, opponent_move)


def compare_speed(protagonist, competitor, player_team, opponent_team, player, opponent, battleground, player_move, opponent_move):
    # move adjustment
    player_move.multi[1] = multi_strike_move(player_move)
    player_move = pre_move_adjustment(protagonist, competitor, player, opponent, battleground, player_move)
    # print(f"{player_move.name}: {player_move.power}")

    opponent_move.multi[1] = multi_strike_move(opponent_move)
    opponent_move = pre_move_adjustment(competitor, protagonist, opponent, player, battleground, opponent_move)
    # print(f"{opponent_move.name}: {opponent_move.power}")

    player.battle_stats[5] = speed_adjustment(protagonist, player, battleground)
    opponent.battle_stats[5] = speed_adjustment(competitor, opponent, battleground)

    # speed comparison
    if player_move.priority > opponent_move.priority:  # player priority move
        move_execution(protagonist, competitor, player_team, opponent_team, player, opponent, battleground, player_move, opponent_move)
    elif opponent_move.priority > player_move.priority:  # enemy priority move
        move_execution(competitor, protagonist, opponent_team, player_team, opponent, player, battleground, opponent_move, player_move)
    elif player.battle_stats[5] > opponent.battle_stats[5]:  # player out-speed enemy
        move_execution(protagonist, competitor, player_team, opponent_team, player, opponent, battleground, player_move, opponent_move)
    elif player.battle_stats[5] == opponent.battle_stats[5]:  # same speed
        if random.random() < 0.5:
            move_execution(protagonist, competitor, player_team, opponent_team, player, opponent, battleground, player_move, opponent_move)
        else:
            move_execution(competitor, protagonist, opponent_team, player_team, opponent, player, battleground, opponent_move, player_move)
    else:
        move_execution(competitor, protagonist, opponent_team, player_team, opponent, player, battleground, opponent_move,
                       player_move)  # enemy out-speed player
    end_of_turn(protagonist, competitor, player_team, opponent_team, player_team[0], opponent_team[0], battleground, player_move, opponent_move)


def move_execution(user_side, target_side, user_team, target_team, user, target, battleground, user_move, target_move):
    # faster pokemon moves first
    user_side.faster, target_side.faster = True, False

    move_order_and_execution(user_side, target_side, user_team, target_team, user, target, battleground, user_move, target_move)
    # mid-update
    user, target = user_team[0], target_team[0]
    user.battle_stats = [user.battle_stats[0]] + \
                        [math.floor(0.01 * 2 * user.nominal_base_stats[x] * modifierChart[x][user.modifier[x]] * 100 + 5) for x in range(1, 6)]
    target.battle_stats = [target.battle_stats[0]] + \
                          [math.floor(0.01 * 2 * target.nominal_base_stats[x] * modifierChart[x][target.modifier[x]] * 100 + 5) for x in range(1, 6)]

    move_order_and_execution(target_side, user_side, target_team, user_team, target, user, battleground, target_move, user_move)


def end_of_turn(protagonist, competitor, player_team, opponent_team, player, opponent, battleground, player_move, opponent_move):
    check_win_or_lose(protagonist, competitor, player_team, opponent_team, battleground)
    if battleground.battle_continuation:
        # reset pokemon
        # yawn
        if player.volatile_status['Yawn'] == 1:
            if player.status != "Normal":
                print(f"{player.name} is already {player.status}!")
            else:
                status = Sleep(1)
                player.status, player.volatile_status['NonVolatile'] = status[0], status[1]
                print(f"{player.name} is now {player.status}!")
        player.volatile_status['Yawn'] = player.volatile_status['Yawn'] - 1 if player.volatile_status['Yawn'] > 0 else 0
        if opponent.volatile_status['Yawn'] == 1:
            if opponent.status != "Normal":
                print(f"{opponent.name} is already {opponent.status}!")
            else:
                status = Sleep(1)
                opponent.status, opponent.volatile_status['NonVolatile'] = status[0], status[1]
                print(f"{opponent.name} is now {opponent.status}!")

        # flinch
        player.volatile_status["Flinch"], opponent.volatile_status["Flinch"] = 0, 0

        # protect
        player.protection[1] = 0 if player.protection[0] == 0 else player.protection[1]
        opponent.protection[1] = 0 if opponent.protection[0] == 0 else opponent.protection[1]
        player.protection[0], opponent.protection[0] = 0, 0

        # disable destiny bond for the next turn after using it
        if opponent.volatile_status['DestinyBond'] > 0:
            opponent.disabled_moves[opponent_move.name] = 1
        if player.volatile_status['DestinyBond'] > 0:
            player.disabled_moves[player_move.name] = 1

        # perish count if fainted
        if player.volatile_status['PerishSong'] == 4:
            player.battle_stats[0] = 0
            check_fainted(player, opponent)
            print(f"{player.name} fainted due to perish song!")
        if opponent.volatile_status['PerishSong'] == 4:
            opponent.battle_stats[0] = 0
            check_fainted(opponent, player)
            print(f"{opponent.name} fainted due to perish song!")

        # field effect
        for effect, turn in battleground.field_effect.items():
            if turn > 0:
                battleground.field_effect[effect] -= 1

        # clear toxic spikes
        if protagonist.entry_hazard["Toxic Spikes"] > 0:
            if "Poison" in player_team[0].type and player_team[0].volatile_status['Grounded'] == 1:
                protagonist.entry_hazard['Toxic Spikes'] = 0
                print("Toxic Spikes has been cleared!")
        if competitor.entry_hazard["Toxic Spikes"] > 0:
            if "Poison" in opponent_team[0].type and opponent_team[0].volatile_status['Grounded'] == 1:
                competitor.entry_hazard['Toxic Spikes'] = 0
                print("Toxic Spikes has been cleared!")

        # buff attack and special attack with total concentration
        if opponent.volatile_status['TotalConcentration'] > 0:
            opponent.applied_modifier = [0, 1, 0, 1, 0, 0, 0, 0, 0]
            opponent.modifier = list(map(operator.add, opponent.applied_modifier, opponent.modifier))
        if player.volatile_status['TotalConcentration'] > 0:
            player.applied_modifier = [0, 1, 0, 1, 0, 0, 0, 0, 0]
            player.modifier = list(map(operator.add, player.applied_modifier, player.modifier))

        # octolock effect
        if player.volatile_status['Octolock'] > 0:
            player.applied_modifier = [0, 0, -1, 0, -1, 0, 0, 0, 0]
            player.modifier = list(map(operator.add, player.applied_modifier, player.modifier))
        if opponent.volatile_status['Octolock'] > 0:
            opponent.applied_modifier = [0, 0, -1, 0, -1, 0, 0, 0, 0]
            opponent.modifier = list(map(operator.add, opponent.applied_modifier, opponent.modifier))

        # perish song
        if player.volatile_status['PerishSong'] > 0:
            player.volatile_status['PerishSong'] += 1
            print(f"{CVIOLET2+CBOLD}{player.name}'s perish count is at {5 - player.volatile_status['PerishSong']}!")
        if opponent.volatile_status['PerishSong'] > 0:
            opponent.volatile_status['PerishSong'] += 1
            print(f"{CVIOLET2+CBOLD}{opponent.name}'s perish count is at {5 - opponent.volatile_status['PerishSong']}!")

        # take aim
        player.volatile_status['TakeAim'] -= 1 if player.volatile_status['TakeAim'] > 0 else 0
        opponent.volatile_status['TakeAim'] -= 1 if opponent.volatile_status['TakeAim'] > 0 else 0

        # trigger ability at the end of each turn
        UseAbility(protagonist, competitor, player, opponent, battleground, "", abilityphase=8)
        UseAbility(competitor, protagonist, opponent, player, battleground, "", abilityphase=8)
        # character ability
        UseCharacterAbility(protagonist, competitor, player, opponent, battleground, "", abilityphase=8)
        UseCharacterAbility(competitor, protagonist, opponent, player, battleground, "", abilityphase=8)

        # reset applied_modifier
        player.applied_modifier, opponent.applied_modifier = [0] * 9, [0] * 9

        # sudden death
        if battleground.turn >= 50 and not battleground.sudden_death:
            print("Sudden Death is activated!!!")
            sound(audio="Assets/music/sudden_death.mp3")
            battleground.sudden_death = True

        # hp decreasing modifier
        player.battle_stats[0] = hp_decreasing_modifier(player, opponent, battleground)
        opponent.battle_stats[0] = hp_decreasing_modifier(opponent, player, battleground)

        # other check indicators
        battleground.weather_effect = check_weather_persist(battleground)
        player.modifier, opponent.modifier = check_modifier_limit(player), check_modifier_limit(opponent)

        check_fainted(player, opponent)
        while player.status == "Fainted" or opponent.status == "Fainted":
            if max(sum(1 for pokemon in player_team if pokemon.status == "Fainted"),
                   sum(1 for pokemon in opponent_team if pokemon.status == "Fainted")) == ROUND_LIMIT[GameSystem.stage]:
                check_win_or_lose(protagonist, competitor, player_team, opponent_team, battleground)
                break

            player = switch_fainted_pokemon_at_end_of_turn(protagonist, competitor, player_team, opponent_team, battleground)
            opponent = switch_fainted_pokemon_at_end_of_turn(competitor, protagonist, opponent_team, player_team, battleground)
            check_fainted(player, opponent)

    move_selection(protagonist, competitor, player_team, opponent_team, player, opponent, battleground)
