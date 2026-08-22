import csv
import random


def ability_text(competitor):
    """What this competitor's character ability does, in their own words.

    The authoritative wording lives in the `Strategy` cell of
    Data/competitors.csv, as a line of the form

        Last Stand: regen all HP and increase all stats by 1 stage for the
        last pokemon.

    which is what the Pokedex and the battle log both show. There used to be
    a hand-written table in character_abilities.py saying roughly the same
    thing in different words -- a second description of the same 61
    abilities, free to drift from the one the designer actually maintains,
    and it did. This reads the real one.

    Returns "" when the cell says nothing about it, so a missing line shows
    nothing rather than an invention.
    """
    ability = str(getattr(competitor, "ability", "") or "").strip()
    if not ability:
        return ""
    wanted = ability.lower() + ":"
    for line in str(getattr(competitor, "strategy", "") or "").splitlines():
        line = line.strip()
        if line.lower().startswith(wanted):
            return line[len(wanted):].strip()
    return ""


class AceError(Exception):
    """A Poke1..Poke6 cell that does not describe a Pokemon."""


#: how a Poke cell separates the Pokemon from its details, and one detail
#: from the next
DETAIL_MARK = "|"
#: how a detail separates its name from its value
VALUE_MARK = "="
#: how a list of moves separates its entries
MOVE_MARK = ","
#: the details a cell may carry. Closed on purpose: a typo is a load-time
#: error naming the competitor, the cell and every key that would have
#: worked, instead of a detail that is silently ignored.
ACE_DETAILS = ("iv", "ability", "moves")


class Ace:
    """One entry in a competitor's designed team.

    A `Poke` cell is either a bare name -- `Durant` -- or a name followed by
    the details that make it *theirs*:

        Gyarados|iv=31|ability=Moxie|moves=Dragon Dance,Waterfall,Earthquake

    A bare name is rolled like any other Pokemon: random IVs for the
    competitor's tier, one ability picked from the species' list, four moves
    sampled from its movepool. A cell with details pins exactly those parts
    and leaves the rest to the roll, so `Pikachu|iv=60` is Ash's Pikachu with
    its own movepool and an IV no wild roll can reach.

    This replaced `Data/custom_team.csv` and `Scripts/Data/custom_team.py`.
    That file was a second place a competitor's team was written down, keyed
    by ID, holding exactly one Pokemon each and reachable only by re-reading
    the whole file for every competitor on every round. It also meant the
    team list held a mix of *strings* and *Pokemon objects*, which
    `team_generation` sorted out with a bare `except:` -- a name that had
    been mistyped took the same branch as a real object and became a broken
    Pokemon rather than an error.
    """

    __slots__ = ("name", "iv", "ability", "moves")

    def __init__(self, name, iv=None, ability=None, moves=None):
        self.name = name
        self.iv = iv
        self.ability = ability
        self.moves = moves

    @property
    def detailed(self):
        return (self.iv is not None or self.ability is not None
                or self.moves is not None)

    def __repr__(self):
        return "Ace(%r%s)" % (self.name, ", detailed" if self.detailed else "")


def read_ace(cell, where=""):
    """One Poke cell -> an Ace. Raises AceError on anything unreadable."""
    parts = [p.strip() for p in str(cell).split(DETAIL_MARK)]
    name = parts[0]
    if not name:
        raise AceError("%s: a Pokemon cell with details but no name" % where)
    ace = Ace(name)
    for detail in parts[1:]:
        if not detail:
            continue
        key, _, value = detail.partition(VALUE_MARK)
        key, value = key.strip().lower(), value.strip()
        if key not in ACE_DETAILS:
            raise AceError(
                "%s: %r knows no detail called %r. The ones there are: %s"
                % (where, name, key, ", ".join(ACE_DETAILS)))
        if key == "iv":
            try:
                ace.iv = int(value)
            except ValueError:
                raise AceError("%s: %r has iv=%r, which is not a number"
                               % (where, name, value))
            if ace.iv < 0:
                raise AceError("%s: %r has a negative iv" % (where, name))
        elif key == "ability":
            if not value:
                raise AceError("%s: %r has an empty ability" % (where, name))
            ace.ability = value
        else:
            moves = [m.strip() for m in value.split(MOVE_MARK) if m.strip()]
            if not moves:
                raise AceError("%s: %r has moves= with nothing in it"
                               % (where, name))
            ace.moves = moves
    return ace


def roll_iv(ace, floor):
    """The six IVs for this Ace.

    `floor` is the competitor's tier minimum. A pinned iv is used as both
    ends of the roll, which is how an IV above the usual 31 ceiling is
    possible at all -- `randint(60, 60)`.
    """
    if ace.iv is None:
        return [random.randint(floor, 31) for _ in range(6)]
    return [random.randint(ace.iv, max(31, ace.iv)) for _ in range(6)]


class Competitor:
    def __init__(self, raw_id, nickname, name, strength=1, ability="", desc="", level="", music="", ace_music="", quote="", strategy=""):
        self.id, self.match_id = None, None
        self.raw_id = raw_id
        self.nickname = nickname
        self.name = name
        self.strength = strength
        self.ability = ability
        self.main = False
        self.stage = 1
        self.desc = desc
        self.result = 0
        self.score = 0
        self.opponent_score = 0
        self.level = level
        self.music = music
        self.ace_music = ace_music
        self.faster = False
        self.side_color = ""
        #: names beaten during the current run only, so a single title
        #: can say what it was worth. Reset at the start of each run;
        #: opponent_history is the all-time tally and cannot answer it.
        self.run_defeated = []
        #: who beat them during the current run. A list because there can be
        #: several: this is a Swiss tournament, not a knockout -- everybody
        #: plays every round and a loss does not end the run. Do not rebuild
        #: a path from this plus run_defeated; that orders it by result
        #: rather than by round. `opponent`/`win_order` are the ordered
        #: record.
        self.run_lost_to = []
        self.quote = quote
        #: the protagonist's chosen portrait, as a key into
        #: Assets/Player ("Male 3"). Empty for everybody else, and for
        #: a career begun before the picker existed.
        self.appearance = ""
        self.team = []
        self.unused_team = []
        self.switching = 0
        self.in_battle_effects = {"Reflect": 0,
                                  "Light Screen": 0,
                                  "Aurora Veil": 0,
                                  "Tailwind": 0}
        self.entry_hazard = {"Stealth Rock": 0,
                             "Spikes": 0,
                             "Toxic Spikes": 0,
                             "Sticky Web": 0}
        # records
        self.history = {}
        #: opponent name -> [[my score, their score], ...], one pair per
        #: meeting, so Check History can show the scorelines and not just
        #: the tally
        self.opponent_scores = {}
        self.participation = 0
        self.championship = 0
        # in-game stats
        #: every competitor faced this run, in the order the matches were
        #: played, and 1/0 for each. Appended together, one entry per battle.
        #: This is what a run path is read from -- see game_procedure.
        self.opponent = []
        self.win_order = []
        # character ability
        self.reveal_ability = False
        self.strategy = strategy


with open('Data/competitors.csv', encoding="ISO-8859-1") as f:
    reader = csv.DictReader(f)
    list_of_competitors = {}
    for row in reader:
        list_of_competitors[row['Name']] = Competitor(row['ID'], row['Nickname'], row['Name'], int(row['Strength']), row['Ability'], row['Desc'], row['Level'],
                                                      row['Music'], row['Ace Music'], row['Quote'], row['Strategy'])
        for i in range(1, 7):
            if row[f'Poke{i}'] != '':
                # An Ace, not a bare string. A cell may carry the IV,
                # ability and moveset that make the Pokemon *theirs* -- see
                # the Ace class. Read here so a malformed cell is an error
                # at startup naming the competitor and the column, rather
                # than a broken Pokemon mid-battle.
                list_of_competitors[row['Name']].team.append(
                    read_ace(row[f'Poke{i}'],
                             "Data/competitors.csv: %s, Poke%d"
                             % (row['Name'], i)))

    for competitor in list_of_competitors:
        list_of_competitors[competitor].opponent_history = {key: [0, 0] for key in list_of_competitors}
        list_of_competitors[competitor].opponent_scores = {}

list_of_competitors['Protagonist'].main = True