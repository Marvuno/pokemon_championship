import random
import math
from contextlib import suppress
from copy import deepcopy
import os

from Scripts.Art.text_color import *
from Scripts.Art.music import *
from Scripts.Data.pokemon import *
from Scripts.Data.competitors import *
from Scripts.Battle.move_additional_effect import *
from Scripts.Battle.constants import *
from Scripts.Game.game_system import *
from Scripts.Game.single_elimination_bracket import *
from Scripts.Art import narrator
from Scripts.Data import tiers


def wins_a_draw(one, two):
    """Who takes a mutual knockout: the lower-rated of the two.

    Both sides being wiped out on the same turn is a real outcome -- recoil,
    entry hazards, a self-KO move -- and it has to resolve the same way
    everywhere. It did not: this function's rule sets the winner's points,
    while round_end() separately decided the line shown in the matchup, the
    head-to-head record and the rating change, and round_end broke a tie by
    "whichever came second in the pairing". So a draw could award the point
    to one competitor and the win to the other, and the matchup disagreed
    with the standings. Both now call this.
    """
    if one.strength != two.strength:
        return one if one.strength < two.strength else two
    return one          # dead level: settle it deterministically


def check_win_or_lose(protagonist, competitor, player_team, opponent_team, battleground):
    player_side = all(pokemon.status == "Fainted" for pokemon in player_team)
    opponent_side = all(pokemon.status == "Fainted" for pokemon in opponent_team)

    if player_side and opponent_side:
        # player_side means "your team is gone", i.e. you lost
        winner = wins_a_draw(protagonist, competitor)
        player_side, opponent_side = (winner is competitor,
                                      winner is protagonist)

    if player_side:
        battleground.battle_continuation = False
        narrator.say("Opponent emerges victorious. You have lost.")
        competitor.stage += 1
    elif opponent_side:
        battleground.battle_continuation = False
        narrator.say("Congratulations! You have won.")
        music(audio='Assets/music/victory.mp3', loop=False)
        protagonist.stage += 1

    if not battleground.battle_continuation:
        protagonist.result = sum(1 for pokemon in opponent_team if pokemon.status == "Fainted")
        competitor.result = sum(1 for pokemon in player_team if pokemon.status == "Fainted")
        protagonist.score += protagonist.result - competitor.result
        competitor.score += competitor.result - protagonist.result
        choose_pokemon(protagonist, competitor, battleground)
        end_battle(protagonist, competitor, player_team, opponent_team, battleground)


# battle ended
# reset every in-battle state
def end_battle(protagonist, competitor, player_team, opponent_team, battleground):
    # Both sides, and outside the per-Pokemon loop. These are properties of a
    # *side*, not of a Pokemon, and only the protagonist's were being cleared
    # -- so a competitor's Stealth Rock and Reflect outlived the battle that
    # set them and were still there the next time that competitor played.
    for side in (protagonist, competitor):
        side.entry_hazard = dict.fromkeys(side.entry_hazard.keys(), 0)
        side.in_battle_effects = dict.fromkeys(side.in_battle_effects.keys(), 0)

    for pokemon in player_team + opponent_team:
        pokemon.modifier = [0] * 9
        pokemon.status = "Normal"
        # ...and the HP with it. Clearing the status but leaving
        # `battle_stats[0]` on 0 left a knocked-out Pokemon still *looking*
        # fainted to anything that reads its HP -- and it stayed that way
        # until the next `battle_setup` rebuilt the stats, which is after the
        # next battle has already been drawn. That is the "fainted on turn 1"
        # that was really the previous battle showing through: `snap_pokemon`
        # calls anything on 0 HP fainted, and `snap_roster` had to paper over
        # it. Every battle starts from full HP anyway, so putting it back
        # here changes nothing about play and everything about what is shown
        # in between.
        with suppress(AttributeError, IndexError, TypeError):
            pokemon.battle_stats[0] = pokemon.hp
        pokemon.volatile_status = dict.fromkeys(pokemon.volatile_status.keys(), 0)
        pokemon.protection = [0, 0]
        pokemon.charging = ["", "", 0]
        pokemon.moveset = [x for x in pokemon.moveset if x != 'Switching']
        pokemon.move_order = []
        # "" and not None: Pokemon starts it as "", and the counter moves ask
        # `if type(previous_move) is not str` before reading `.damage` off it.
        # None slips through that guard, so a Counter or Mirror Coat on the
        # first turn of the *next* battle raised AttributeError.
        pokemon.previous_move = ""
        pokemon.disabled_moves = {}
        pokemon.disguise, pokemon.transform = False, False
        pokemon.roosting = None
        with suppress(AttributeError):
            # copies: a Pokemon's live typing is what moves like Forest's
            # Curse add to, and handing it the same list the default is held
            # in means the default gets edited along with it
            pokemon.name = pokemon.default_name
            pokemon.ability = list(pokemon.default_ability)
            pokemon.type = list(pokemon.default_type)

    if not battleground.verbose:
        for mon in protagonist.unused_team:
            protagonist.team.append(mon)
        protagonist.unused_team = []

        input("Press any key to continue.")
        os.system('cls' if os.name == 'nt' else 'clear')
        # An exhibition is one battle played outside the bracket, which is
        # what Custom Play is. There is no round to close and no stage to
        # advance -- and `round_end` walks all thirty-two seeded competitors,
        # so on a field that was never drawn it raises IndexError rather than
        # doing nothing.
        if not getattr(battleground, "exhibition", False):
            round_end(GameSystem.stage)
            GameSystem.stage += 1


def choose_pokemon(protagonist, opponent, battleground):
    # An exhibition has nothing to keep. Custom Play deals both teams for the
    # one battle out of the opponent's own recipe and throws them away
    # afterwards -- there is no career for a kept Pokemon to go into, and the
    # player is not even playing as themselves. Offering the screen anyway
    # asked which of somebody else's Pokemon to add to a team that will not
    # exist in a moment. See start_interface.custom_play.
    if battleground.verbose or getattr(battleground, "exhibition", False):
        return

    def pokemon_init(pokemon):
        pokemon.iv = [random.randint(PLAYER_IV(protagonist.strength), 31) for _ in range(6)]
        pokemon.total_iv = sum(pokemon.iv)
        pokemon.nominal_base_stats = list(map(operator.add, pokemon.base_stats, pokemon.iv))
        pokemon.total_base_stats = sum(pokemon.base_stats)
        pokemon.ability = [random.choice(pokemon.ability)]
        pokemon.moveset = random.sample(pokemon.moveset, min(4, len(pokemon.moveset)))
        pokemon.moveset = ["Switching"] + pokemon.moveset
        return pokemon

    def info_display(participant, team=None):
        print()
        for i, pokemon in enumerate(team if team is not None else participant.team):
            narrator.say(f"{participant.side_color}ID: {pokemon.id} || Name: {pokemon.name} || Type: {pokemon.type}")
            narrator.say(f"Ability: {pokemon.ability} || Total Stats: {pokemon.total_stats}({pokemon.total_iv})")
            print("Base Stats:", [f"{STATISTICS[x]}: {pokemon.nominal_base_stats[x]}" for x in range(len(pokemon.nominal_base_stats))])
            narrator.say(f"Moveset: {pokemon.moveset}{CEND}\n")

    #: Entering this instead of an index backs out of a pick and asks the
    #: Y/N question again, so changing your mind part-way through is no
    #: longer a dead end. A team can never hold more than MAX_POKEMON (6),
    #: so 9 is never a real slot -- the same sentinel the keep-team screen
    #: already uses for "I am done".
    GO_BACK = 9

    def ask_index(question, team):
        """An index into `team`, or None if the player backed out."""
        while True:
            with suppress(ValueError):
                answer = int(input(question))
                if answer == GO_BACK:
                    return None
                if 0 <= answer < len(team):
                    return answer

    def my_roster():
        """Everyone on your books, not just the ones who played.

        team_selection() parks the Pokemon you held back from this round in
        unused_team and end_battle() folds them home again -- but that
        happens *after* this function runs, so `team` here is only the ones
        that fought. Offering just those made the Pokemon you benched
        impossible to trade away: bring five of six and the sixth could
        never be swapped out.
        """
        return list(protagonist.team) + list(protagonist.unused_team)

    def replace_mine(index, incoming):
        """Put `incoming` in roster slot `index`, in whichever list it lives."""
        if index < len(protagonist.team):
            protagonist.team[index] = incoming
        else:
            protagonist.unused_team[index - len(protagonist.team)] = incoming

    choice, obtained_pokemon, thrown_pokemon = None, -1, -1
    current_pokemon = [pokemon.name for pokemon in my_roster()]

    # win the round
    if protagonist.stage > opponent.stage:
        narrator.say(f"{protagonist.side_color}Your Team: {[pokemon.name for pokemon in protagonist.team]}\n"
              f"{opponent.side_color}Opponent Team: {[pokemon.name for pokemon in opponent.team]}{CEND}")
        # not yet full team, can get extra pokemon
        if len(protagonist.team + protagonist.unused_team) < MAX_POKEMON:
            while choice != "Y" and choice != "N":
                choice = input(f"Input Y if you want to take from the opponent, and N to get a random pokemon from the organizer. ").upper()

                if choice == "Y":
                    # pokemon info
                    info_display(opponent)
                    obtained_pokemon = ask_index(f"You may take one pokemon from the opponent, or {GO_BACK} to go back:\n"
                                                 f"{CRED2}{CBOLD}{[(index, pokemon.name) for index, pokemon in enumerate(opponent.team)]}{CEND}\n"
                                                 f"--> ", opponent.team)
                    if obtained_pokemon is None:
                        choice = None
                    else:
                        protagonist.team.append(opponent.team[obtained_pokemon])
                elif choice == "N":
                    # What the organiser hands you scales with the *rating*
                    # of whoever you beat, not with their tier label. The
                    # label meant a 58-rated opponent and a 115-rated one
                    # paid exactly the same, because both are "Intermediate".
                    # See Scripts/Data/tiers.py.
                    wanted = tiers.reward_tier(opponent.strength)
                    pokemon_availability_list = [pokemon for pokemon in list_of_pokemon if
                                                 list_of_pokemon[pokemon].tier == wanted and pokemon not in current_pokemon]
                    obtained_pokemon = pokemon_init(deepcopy(list_of_pokemon[random.choice(pokemon_availability_list)]))
                    narrator.say(f"You have obtained {CVIOLET2}{CBOLD}{obtained_pokemon.name}{CEND} from the organizer.")
                    protagonist.team.append(obtained_pokemon)
        # swap pokemon
        else:
            # when full team
            while choice != "Y" and choice != "N":
                choice = input(f"Input Y if you want to swap, and N otherwise. ").upper()

                if choice == "Y":
                    mine = my_roster()
                    info_display(protagonist, mine), info_display(opponent)
                    thrown_pokemon = ask_index(f"Choose the pokemon you don't want on your team, or {GO_BACK} to go back:\n"
                                               f"{CGREEN2}{CBOLD}{[(index, pokemon.name) for index, pokemon in enumerate(mine)]}{CEND}\n"
                                               f"--> ", mine)
                    obtained_pokemon = None if thrown_pokemon is None else \
                        ask_index(f"Take the pokemon you want on the other team, or {GO_BACK} to go back:\n"
                                  f"{CRED2}{CBOLD}{[(index, pokemon.name) for index, pokemon in enumerate(opponent.team)]}{CEND}\n"
                                  f"--> ", opponent.team)
                    # backing out of either pick leaves the team untouched and
                    # returns to the swap-or-not question
                    if thrown_pokemon is None or obtained_pokemon is None:
                        choice = None
                    else:
                        replace_mine(thrown_pokemon,
                                     opponent.team[obtained_pokemon])
    # lose the round
    else:
        # when lost
        if len(protagonist.team + protagonist.unused_team) < MAX_POKEMON:
            # A consolation, scaled to where *you* are: a notch below what a
            # competitor at your rating fields. It used to be a flat draw
            # from Very Low, Low and Medium -- 138 Pokemon wide, your rating
            # ignored -- so a 300-rated player who lost could be handed the
            # same Pokemon as a 2-rated one.
            wanted = tiers.consolation_tier(protagonist.strength)
            pokemon_availability_list = [pokemon for pokemon in list_of_pokemon if
                                         list_of_pokemon[pokemon].tier == wanted and pokemon not in current_pokemon]
            obtained_pokemon = pokemon_init(deepcopy(list_of_pokemon[random.choice(pokemon_availability_list)]))
            narrator.say(f"You have obtained {CVIOLET2}{CBOLD}{obtained_pokemon.name}{CEND} from the organizer.")
            protagonist.team.append(obtained_pokemon)


def round_end(stage):

    def result_announcement(victor, loser, main):
        """Print the matchup line, and return it as (winner, loser) scores.

        The pair is what Check History shows -- "you beat them 6-5" rather
        than only "you are 2-1 against them" -- and it is deliberately the
        same two numbers the boxes below print, so the two screens can never
        disagree about how a match went.
        """
        level_order = {"Low": 1, "Intermediate": 2, "Advanced": 3, "Elite": 4, "Champion": 5, "Protagonist": 6}
        # for world champ
        victor_crown, loser_crown = f' |{victor.championship}|' if victor.championship > 0 else '', f' |{loser.championship}|' if loser.championship > 0 else ''
        victor_bold, loser_bold = CBOLD if victor.championship > 0 else '', CBOLD if loser.championship > 0 else ''
        # An upset is beating somebody from a higher class *while rated below
        # them*, and it needs both halves now that ratings drift with form.
        #
        # The class alone was enough while ratings sat exactly where the CSV
        # put them -- the tiers are stratified there (Low 1-49, Intermediate
        # 53-147, Advanced 162-312, Elite 374-833) and not one of the 2,346
        # pairings disagreed. Drift is what breaks it: the Low/Intermediate
        # gap is four points, so 39 cross-tier pairings can invert, and the
        # badge would then contradict the two ratings printed on the very
        # same line -- "Bojji [67] beat Dulunga [45]", marked UPSET.
        #
        # Rating alone would be worse than either: it would flag every
        # within-class win by the lower-rated side, which is most of them,
        # and a badge that fires constantly says nothing. Requiring both
        # keeps it to what it has always meant and reads the numbers the
        # player can see.
        upset = (level_order[victor.level] < level_order[loser.level]
                 and victor.strength < loser.strength)
        narrator.say(CWHITE2 + victor_bold + EntryBox(victor.id, f"{victor.nickname} [{victor.strength}]{victor_crown}{' !!' if upset else ''}", victor.stage - 1, ROUND_LIMIT[stage]).structure + CEND)
        if main:  # the protagonist battle
            print((CGREEN if loser.main else CGREY) + loser_bold + EntryBox(loser.id, f"{loser.nickname} [{loser.strength}]{loser_crown}",
                                   loser.stage - 1, loser.result).structure, "\n" + CEND)
            return ROUND_LIMIT[stage], loser.result
        else:  # others' battle
            result = ROUND_LIMIT[stage] * loser.strength / (victor.strength + loser.strength)
            result = int(min(round(result * random.uniform(1.25, 1.75), 0), ROUND_LIMIT[stage] - 1))
            victor.score += ROUND_LIMIT[stage] - result
            loser.score += result - ROUND_LIMIT[stage]
            print(CGREY + loser_bold + EntryBox(loser.id, f"{loser.nickname} [{loser.strength}]{loser_crown}", loser.stage - 1, result).structure, "\n" + CEND)
            return ROUND_LIMIT[stage], result

    for i in range(0, int(math.pow(2, 5)), 2):
        one, two = list_of_competitors[GameSystem.participants[i]], list_of_competitors[GameSystem.participants[i + 1]]
        main = True
        if one.result == two.result:
            # A draw. Same rule check_win_or_lose used to award the point, so
            # the matchup line, the head-to-head record and the rating change
            # all agree with the standings.
            victor = i if wins_a_draw(one, two) is one else i + 1
        else:
            victor = i if one.result > two.result else i + 1
        loser = i + 1 if victor == i else i
        if not (one.main or two.main):
            victor = i if random.random() < one.strength / (one.strength + two.strength) else i + 1
            loser = i + 1 if victor == i else i

            list_of_competitors[GameSystem.participants[victor]].stage += 1
            main = False
        winner_score, loser_score = result_announcement(
            list_of_competitors[GameSystem.participants[victor]],
            list_of_competitors[GameSystem.participants[loser]], main)

        # save opponent in-game record
        list_of_competitors[GameSystem.participants[victor]].opponent.append(list_of_competitors[GameSystem.participants[loser]])
        list_of_competitors[GameSystem.participants[victor]].win_order.append(1)
        list_of_competitors[GameSystem.participants[loser]].opponent.append(list_of_competitors[GameSystem.participants[victor]])
        list_of_competitors[GameSystem.participants[loser]].win_order.append(0)
        # save opponent match history record, tally and scoreline both -- the
        # tally alone said "2-1 against them" without ever saying how close
        # any of the three were
        winner = list_of_competitors[GameSystem.participants[victor]]
        beaten = list_of_competitors[GameSystem.participants[loser]]
        winner.opponent_history[GameSystem.participants[loser]][0] += 1
        beaten.opponent_history[GameSystem.participants[victor]][1] += 1
        # Who they got through, this run only. opponent_history is a running
        # total across every championship ever, so it can never say what a
        # single title was worth -- this is the list the champion roll shows.
        # Reset at the start of each run (see team_generation) rather than
        # cleared here, so a run that ends early still leaves its record.
        if not hasattr(winner, "run_defeated") or winner.run_defeated is None:
            winner.run_defeated = []
        winner.run_defeated.append(GameSystem.participants[loser])
        # And the other half of the same fact: who ended their run. Together
        # these give each competitor their whole path through a championship,
        # in order, with the result of every match on it.
        if not hasattr(beaten, "run_lost_to") or beaten.run_lost_to is None:
            beaten.run_lost_to = []
        beaten.run_lost_to.append(GameSystem.participants[victor])
        for side, them, mine, theirs in (
                (winner, GameSystem.participants[loser],
                 winner_score, loser_score),
                (beaten, GameSystem.participants[victor],
                 loser_score, winner_score)):
            if not hasattr(side, "opponent_scores"):
                side.opponent_scores = {}
            side.opponent_scores.setdefault(them, []).append([mine, theirs])
