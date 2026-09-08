from Scripts.Battle.battle_checklist import *
from Scripts.Battle.battle_initialization import *
from Scripts.Battle.battle_move_execution import *
from Scripts.Battle.battle_win_condition import *
from Scripts.Battle.move_additional_effect import *
from Scripts.Game.game_procedure import *
from Scripts.Data.abilities import *
from Scripts.Data.character_abilities import *
from Scripts.Art.music import *
from Scripts.Battle.fastcopy import fast_copy
from Scripts.Battle.context import Side, Turn
from Scripts.Art import narrator
from Scripts.Battle import terrain


def battle_setup(protagonist, competitor, player_team, opponent_team, battleground):
    if battleground.verbose:
        for pokemon in player_team:
            narrator.say(f"{CGREEN2}{CBOLD}{pokemon.name} {pokemon.nominal_base_stats} {pokemon.iv} {pokemon.moveset} {pokemon.ability}{CEND}")
        for pokemon in opponent_team:
            narrator.say(f"{CRED2}{CBOLD}{pokemon.name} {pokemon.nominal_base_stats} {pokemon.iv} {pokemon.moveset} {pokemon.ability}{CEND}")

    for pokemon in player_team + opponent_team:
        # side 1 + side 2
        pokemon.hp = math.floor(0.01 * 2 * pokemon.nominal_base_stats[0] * 100) + 100 + 10 if pokemon.name != "Shedinja" else 1
        pokemon.battle_stats = [pokemon.hp] + [math.floor(0.01 * 2 * pokemon.nominal_base_stats[x] * 100 + 5) for x in range(1, 6)]
        pokemon.moveset = ['Switching'] + pokemon.moveset
        pokemon.default_name, pokemon.default_ability, pokemon.default_type = deepcopy(pokemon.name), deepcopy(pokemon.ability), deepcopy(pokemon.type)
        pokemon.default_nominal_base_stats = deepcopy(pokemon.nominal_base_stats)

    for side1, side2 in zip(player_team, opponent_team):
        side1.side_color, side2.side_color = CGREEN2 + CBOLD, CRED2 + CBOLD

    # color for different side
    protagonist.side_color, competitor.side_color = CGREEN2 + CBOLD, CRED2 + CBOLD

    # The weather this arena happens to have: one roll for whether there is
    # any, then an even pick of which. Two steps rather than one weighted
    # draw across five outcomes, because the two numbers a designer wants to
    # turn -- how often weather happens, and which weathers are possible --
    # are then separate. Adding a sixth weather no longer changes how often
    # weather happens at all.
    # `bare_arena` opts out of both rolls below. Set by the Metronome mode,
    # whose whole point is that the two sides are identical -- an opening
    # weather or a terrain is drawn per battle and would hand one of them an
    # advantage nobody chose. Nothing else sets it, so every ordinary battle
    # rolls exactly as it always has.
    bare = bool(getattr(battleground, "bare_arena", False))
    if not bare and random.random() < OPENING_WEATHER_CHANCE:
        battleground.starting_weather_effect = random.choice(OPENING_WEATHERS)
    else:
        battleground.starting_weather_effect = 'Clear'
    battleground.weather_effect = battleground.starting_weather_effect

    # and the ground it happens to be fought on, rolled the same way and at
    # the same odds. Ten turns rather than a move's five -- see
    # Scripts/Battle/terrain.py.
    opened_on = None if bare else terrain.roll_natural(battleground)
    if opened_on:
        narrator.say(opened_on, "field", terrain=battleground.terrain)

    player, opponent = player_team[0], opponent_team[0]

    # character ability at start
    opening = Turn(battleground,
                   Side(protagonist, player_team, player),
                   Side(competitor, opponent_team, opponent))
    UseCharacterAbility(opening, "", abilityphase=0)
    UseCharacterAbility(opening.flip(), "", abilityphase=0)

    switched_in_initialization(protagonist, competitor, player, opponent, battleground)
    switched_in_initialization(competitor, protagonist, opponent, player, battleground)

    # music on
    music(audio=f"Assets/music/{competitor.music}", loop=True)

    # player / opponent may have been reassigned by the fainted-switch loop
    # above, so the context is built here rather than reused.
    move_selection(Turn(battleground,
                        Side(protagonist, player_team, player),
                        Side(competitor, opponent_team, opponent)))


def move_selection(turn):
    """The turn loop: pick moves, resolve them, tick the turn over.

    `turn` is oriented on the player's side throughout -- turn.user is the
    protagonist, turn.foe the competitor. See Scripts/Battle/context.py. The
    six names below are unpacked once because the body reads them constantly;
    what matters is that they arrive as one thing.
    """
    protagonist, competitor = turn.user.trainer, turn.foe.trainer
    player_team, opponent_team = turn.user.team, turn.foe.team
    player, opponent = turn.user.active, turn.foe.active
    battleground = turn.ground
    while battleground.battle_continuation:
        player.battle_stats = [player.battle_stats[0]] + \
                              [math.floor(0.01 * 2 * player.nominal_base_stats[x] * modifierChart[x][player.modifier[x]] * 100 + 5) for x in range(1, 6)]
        opponent.battle_stats = [opponent.battle_stats[0]] + \
                                [math.floor(0.01 * 2 * opponent.nominal_base_stats[x] * modifierChart[x][opponent.modifier[x]] * 100 + 5) for x in range(1, 6)]

        # The turn starts here, so the count goes up here. It used to be
        # further down -- after this header had already been printed and
        # before a single move had been chosen -- so for the whole of the
        # turn the player was watching, `battleground.turn` held the number
        # of the *next* one. The log header said "Turn 1" while everything
        # reading the counter said 2, which is why the battle appeared to do
        # nothing on turn 1 and start on turn 2.
        battleground.turn += 1
        narrator.say(f"\n\n{CBOLD}{weather_conversionChart.get(battleground.weather_effect)} [{battleground.weather_effect}]\n"
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

        # add turn -- the battleground's own count is done at the top with
        # the header; these two are per-Pokemon and reset on a switch
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
            # Every opponent, whatever their rating. Which AI is played
            # against is the *difficulty setting*, not a property of the
            # competitor: Beginner swaps this routine for the simple one
            # everywhere (GUI/bridge.py), and Normal is what is left.
            #
            # It used to switch on `competitor.strength >= SMART_AI_RATING`,
            # so 16 of the 69 played simply because they were rated low. Two
            # things were wrong with that. It made rating mean two unrelated
            # things at once -- how good a team you bring, and how well you
            # think -- so the early rounds were easy twice over. And once
            # ratings drifted with form it became a cliff: five competitors
            # sat close enough to the boundary that a good career would have
            # switched their brain on and a bad one switched it off, out of a
            # two-point move. Everything else a rating feeds -- the tier
            # ladder, PLAYER_IV -- is a continuous curve and takes drift
            # happily; this was the one step in the whole engine.
            opponent_move = smart_ai_select_move(battleground, protagonist,
                                                 competitor)
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

        # Each side gets its own copy of the move it chose. Everything
        # downstream writes this turn's working state onto the move it is
        # handed -- damage, accuracy, whether it was super effective --
        # and the entries of list_of_moves are shared by the whole game.
        player_move, opponent_move = fast_copy(player_move), fast_copy(opponent_move)

        # Rebuilt each pass: a switch this turn changed who is standing
        # there, and the loop's own `player` / `opponent` were reassigned to
        # match.
        compare_speed(Turn(battleground,
                           Side(protagonist, player_team, player),
                           Side(competitor, opponent_team, opponent)),
                      player_move, opponent_move)


def compare_speed(turn, player_move, opponent_move):
    """Work out who goes first, run the turn, then close it out."""
    protagonist, competitor = turn.user.trainer, turn.foe.trainer
    player_team, opponent_team = turn.user.team, turn.foe.team
    player, opponent = turn.user.active, turn.foe.active
    battleground = turn.ground
    # move adjustment
    player_move.multi[1] = multi_strike_move(player_move)
    player_move = pre_move_adjustment(protagonist, competitor, player, opponent, battleground, player_move)
    # print(f"{player_move.name}: {player_move.power}")

    opponent_move.multi[1] = multi_strike_move(opponent_move)
    opponent_move = pre_move_adjustment(competitor, protagonist, opponent, player, battleground, opponent_move)
    # print(f"{opponent_move.name}: {opponent_move.power}")

    player.battle_stats[5] = speed_adjustment(protagonist, player, battleground)
    opponent.battle_stats[5] = speed_adjustment(competitor, opponent, battleground)

    # Abilities that decide *when* a Pokemon moves, fired here because here is
    # the last moment before the question is settled -- see ORDER_PHASE. Each
    # side is given its own move, so Prankster and Gale Wings adjust the
    # priority of the move their holder is about to use.
    #
    # After speed_adjustment, not before: that reads paralysis, Tailwind and
    # Trick Room off the base speed, and Swift Swim doubles what comes out.
    # Nothing compounds, because move_selection rebuilds battle_stats from
    # nominal_base_stats at the top of every turn.
    UseAbility(turn, player_move, abilityphase=ORDER_PHASE)
    UseCharacterAbility(turn, player_move, abilityphase=ORDER_PHASE)
    UseAbility(turn.flip(), opponent_move, abilityphase=ORDER_PHASE)
    UseCharacterAbility(turn.flip(), opponent_move, abilityphase=ORDER_PHASE)

    # "the player moves first" and "the enemy moves first" are the same
    # context read from either end now, rather than two orderings of nine
    # arguments. flip() is the whole difference.
    yours = turn

    # speed comparison
    if player_move.priority > opponent_move.priority:      # player priority
        move_execution(yours, player_move, opponent_move)
    elif opponent_move.priority > player_move.priority:    # enemy priority
        move_execution(yours.flip(), opponent_move, player_move)
    elif player.battle_stats[5] > opponent.battle_stats[5]:  # player faster
        move_execution(yours, player_move, opponent_move)
    elif player.battle_stats[5] == opponent.battle_stats[5]:  # dead level
        if random.random() < 0.5:
            move_execution(yours, player_move, opponent_move)
        else:
            move_execution(yours.flip(), opponent_move, player_move)
    else:                                                   # enemy faster
        move_execution(yours.flip(), opponent_move, player_move)
    # team[0] on both sides, not the Pokemon this turn began with: whoever is
    # standing there now is who the end-of-turn effects apply to.
    end_of_turn(Turn(battleground,
                     Side(protagonist, player_team, player_team[0]),
                     Side(competitor, opponent_team, opponent_team[0])),
                player_move, opponent_move)


def move_execution(turn, user_move, target_move):
    """Both sides take their move, the faster one first.

    `turn` arrives already oriented: turn.user is whoever won the speed check.
    The second half of the turn is the same battle read the other way round,
    which is what turn.flip() says. See Scripts/Battle/context.py.
    """
    # faster pokemon moves first
    turn.user.trainer.faster, turn.foe.trainer.faster = True, False

    move_order_and_execution(turn, user_move, target_move)
    # Mid-update. Re-read the front of each party rather than trusting the
    # Pokemon this started with: a move can have switched one of them out, and
    # the stats being recomputed have to belong to whoever is standing there
    # now. This is exactly why Side.active is a stored slot rather than
    # team[0] -- the two differ for the span between these two calls.
    turn.user.active, turn.foe.active = turn.user.team[0], turn.foe.team[0]
    for side in (turn.user, turn.foe):
        mon = side.active
        mon.battle_stats = [mon.battle_stats[0]] + [
            math.floor(0.01 * 2 * mon.nominal_base_stats[x]
                       * modifierChart[x][mon.modifier[x]] * 100 + 5)
            for x in range(1, 6)]

    move_order_and_execution(turn.flip(), target_move, user_move)

def end_of_turn(turn, player_move, opponent_move):
    """Everything that happens once both sides have moved."""
    protagonist, competitor = turn.user.trainer, turn.foe.trainer
    player_team, opponent_team = turn.user.team, turn.foe.team
    player, opponent = turn.user.active, turn.foe.active
    battleground = turn.ground
    def in_battle_changes(participant, pokemon, move):
        # yawn
        if pokemon.volatile_status['Yawn'] == 1:
            if pokemon.status != "Normal":
                narrator.say(f"{pokemon.name} is already {pokemon.status}!")
            else:
                status = Sleep(1)
                pokemon.status, pokemon.volatile_status['NonVolatile'] = status[0], status[1]
                narrator.say(f"{pokemon.name} is now {pokemon.status}!")
        pokemon.volatile_status['Yawn'] = pokemon.volatile_status['Yawn'] - 1 if pokemon.volatile_status['Yawn'] > 0 else 0
        # flinch (not necessarily needed but added just in case)
        pokemon.volatile_status["Flinch"] = 0
        # protect
        pokemon.protection[1] = 0 if pokemon.protection[0] == 0 else pokemon.protection[1]
        pokemon.protection[0] = 0
        # disable destiny bond for the next turn after using it
        if pokemon.volatile_status['DestinyBond'] > 0:
            pokemon.disabled_moves[move.name] = 1
        # perish count if fainted
        if pokemon.volatile_status['PerishSong'] == 4:
            pokemon.battle_stats[0] = 0
            narrator.say(f"{pokemon.name} fainted due to perish song!")
        # clear toxic spikes
        if participant.entry_hazard["Toxic Spikes"] > 0:
            if "Poison" in pokemon.type and pokemon.volatile_status['Grounded'] == 1:
                participant.entry_hazard['Toxic Spikes'] = 0
                narrator.say("Toxic Spikes has been cleared!")
        # total concentration
        if pokemon.volatile_status['TotalConcentration'] > 0:
            pokemon.applied_modifier = [0, 1, 0, 1, 0, 0, 0, 0, 0]
            pokemon.modifier = list(map(operator.add, pokemon.applied_modifier, pokemon.modifier))
        # octolock effect
        if pokemon.volatile_status['Octolock'] > 0:
            pokemon.applied_modifier = [0, 0, -1, 0, -1, 0, 0, 0, 0]
            pokemon.modifier = list(map(operator.add, pokemon.applied_modifier, pokemon.modifier))
        # perish song
        if pokemon.volatile_status['PerishSong'] > 0:
            pokemon.volatile_status['PerishSong'] += 1
            narrator.say(f"{CVIOLET2+CBOLD}{pokemon.name}'s perish count is at {5 - pokemon.volatile_status['PerishSong']}!")
        # take aim
        pokemon.volatile_status['TakeAim'] -= 1 if pokemon.volatile_status['TakeAim'] > 0 else 0

    check_win_or_lose(protagonist, competitor, player_team, opponent_team, battleground)
    if battleground.battle_continuation:
        in_battle_changes(protagonist, player, player_move), in_battle_changes(competitor, opponent, opponent_move)
        # field effect
        for effect, turn in battleground.field_effect.items():
            if turn > 0:
                battleground.field_effect[effect] -= 1

        # Grassy Terrain gives the ground back a sixteenth of its HP, then
        # the terrain counts itself down -- a separate layer from the field
        # effects above, and from the weather. See Scripts/Battle/terrain.py.
        for side_pokemon in (player, opponent):
            healed = terrain.end_of_turn_heal(battleground, side_pokemon)
            if healed > 0:
                side_pokemon.battle_stats[0] += healed
                narrator.say(f"{side_pokemon.name} drew {healed} HP from the "
                             f"grass.", "heal", pokemon=side_pokemon.name,
                             amount=healed)
        lapsed = terrain.tick(battleground)
        if lapsed:
            narrator.say(lapsed, "field")

        # trigger ability at the end of each turn
        closing = Turn(battleground,
                       Side(protagonist, player_team, player),
                       Side(competitor, opponent_team, opponent))
        UseAbility(closing, "", abilityphase=8)
        UseAbility(closing.flip(), "", abilityphase=8)
        # character ability
        UseCharacterAbility(closing, "", abilityphase=8)
        UseCharacterAbility(closing.flip(), "", abilityphase=8)

        # reset applied_modifier
        player.applied_modifier, opponent.applied_modifier = [0] * 9, [0] * 9

        # sudden death
        if battleground.turn >= 50 and not battleground.sudden_death:
            narrator.say("Sudden Death is activated!!!")
            sound(audio="Assets/music/sudden_death.mp3")
            battleground.sudden_death = True

        # Roost lasts the turn and no longer. Restored from the copy the
        # handler took, not from default_type, so a type added during this
        # battle survives -- see check_move_roost.
        for roosted in (player, opponent):
            if getattr(roosted, "roosting", None):
                roosted.type = list(roosted.roosting)
                roosted.roosting = None
                if "Flying" in roosted.type:
                    roosted.volatile_status['Grounded'] = 0

        # hp decreasing modifier
        player.battle_stats[0] = hp_decreasing_modifier(player, opponent, battleground)
        opponent.battle_stats[0] = hp_decreasing_modifier(opponent, player, battleground)

        # other check indicators
        battleground.weather_effect = check_weather_persist(battleground)
        player.modifier, opponent.modifier = check_modifier_limit(player), check_modifier_limit(opponent)

        check_fainted(player, opponent)
        while player.status == "Fainted" or opponent.status == "Fainted":
            if all(pokemon.status == "Fainted" for pokemon in player_team) or all(pokemon.status == "Fainted" for pokemon in opponent_team):
                check_win_or_lose(protagonist, competitor, player_team, opponent_team, battleground)
                break

            player = switch_fainted_pokemon_at_end_of_turn(protagonist, competitor, player_team, opponent_team, battleground)
            opponent = switch_fainted_pokemon_at_end_of_turn(competitor, protagonist, opponent_team, player_team, battleground)
            check_fainted(player, opponent)

    # The next turn starts from whoever is at the front of each team.
    #
    # `player` and `opponent` are locals, and only the fainted-switch loop
    # above reassigns them -- so anything *else* that replaced team[0]
    # during the turn left them stale, and the next turn ran with the
    # Pokemon that had left as its `active` while the team already held the
    # replacement. The replacement then executed the move chosen for the
    # one that had gone: 14 moves in 60 battles, once a character ability
    # started forcing switches at the end of a turn.
    #
    # Side.active is stored rather than derived on purpose (see CLAUDE.md)
    # -- mid-switch the two genuinely differ. A turn *boundary* is not
    # mid-switch: here the active Pokemon is team[0] by definition, and
    # after the loop above the two already agree, so this is the same
    # value by a route that cannot go stale.
    move_selection(Turn(battleground,
                        Side(protagonist, player_team, player_team[0]),
                        Side(competitor, opponent_team, opponent_team[0])))
