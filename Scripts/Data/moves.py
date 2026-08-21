"""What a move is, and the table of every one of them.

Every move used to be a hand-written call to a thirty-one argument constructor
inside a 1,425-line Python literal. Adding one meant editing code, and the
one bug that escaped from it -- `'Razor Shell'` keyed a Move whose name was
`"RazorShell"` -- is exactly the typo a literal invites and a validated table
catches. Pokemon and competitors have always been CSV; moves are now too.

This module owns the encoding, and it is the only place that knows it.


The awkward column, and why it is awkward
-----------------------------------------
Thirty of the thirty-one fields are scalars or plain lists. `special_effect`
is not: across the 387 moves it takes twelve different shapes -- a string, an
array of nine stat stages, a *function reference*, a float, and seven kinds of
mixed list including `[[stages], None]` and `['Disable', '', <function>]`.
Nineteen moves also carry a *list* `effect_type`, paired positionally with a
list of payloads.

So `special_effect` is encoded with four rules and nothing else:

    |   separates one effect from the next, paired positionally with the
        pipe-separated entries in `effect_type`. 368 of 387 moves never use it.
    @   names one of the status functions in
        Scripts/Battle/moves_status_condition_apply.py -- `@Confused`. There
        are 24 of them and the registry below is built by introspecting that
        module, so it cannot fall out of step with it.
    ,   an array: `0,0,0,0,-2,0,0,0,0` is a stat-stage change. A *trailing*
        comma marks a one-entry array -- `Grass,` is `['Grass']` where a bare
        `Grass` is the string `'Grass'`. Forest's Curse is the one move that
        needs the distinction, and it needs it badly: its handler iterates the
        value, so the string would add five types called G, r, a, s and s.
    ~   None, which three moves genuinely mean.

Anything else is the literal string, which is what 160 moves have. An empty
cell is the empty string; `Haze` is a bare `|`, being two empty effects.

    Acid Spray        opponent_modifier                  0,0,0,0,-2,0,0,0,0
    Destiny Bond      user_volatile                      @DestinyBond
    Reign of Terror   opponent_modifier|target_volatile  0,0,0,0,0,-1,0,-1,0|@Frighten
    Defog             clear_entry_hazard|opponent_modifier   0,0,0,0,0,0,-1,0,0|~

An unknown `@Name` is a load-time error naming the move and the effect, not a
silently missing effect at some point mid-battle.
"""
import csv
import inspect
import os
import random

from Scripts.Battle.moves_status_condition_apply import *
from Scripts.Battle import moves_status_condition_apply as status
from Scripts.Battle.constants import *
from Scripts.Battle import move_rules

"""
0 Normal, 1 Fire, 2 Water, 3 Electric, 4 Grass, 5 Ice, 6 Fighting, 7 Poison, 8 Ground, 9 Flying, 10 Psychic, 11 Bug,
12 Rock, 13 Ghost, 14 Dragon, 15 Dark, 16 Steel, 17 Fairy
0 Physical | 1 Special | 2 Status
0 HP | 1 Attack | 2 Defense | 3 SpA | 4 SpDef | 5 Speed | 6 Evasion | 7 Accuracy | 8 Crit
"""


class Move:
    def __init__(self, name, power, attack_type, type, accuracy, pp,
                 ignoreEvasion=False, ignoreDef=False, ignoreWeather=False, ignoreType=[], ignoreImmunity=[],
                 ignoreBarrier=False, ignoreAbility=False, ignoreInvulnerability=False,
                 targetAtk=False, inverseDef=False, DefAsAtk=False, multiType=[], interchangeType=[],
                 charging="", crit=0, priority=0, recoil=0, deduct=0, crash=0, multi=[0, 1], flags='', custom=False,
                 effect_type="no_effect", special_effect="", effect_accuracy=1,
                 power_when="", weather_when="", fails_unless=""):
        self.name = name
        self.power = power
        self.abilitymodifier = 1
        self.evasion = 1
        self.super_effective = False
        self.critical_hit = False
        self.attack_type = attack_type
        self.type = type
        self.accuracy = accuracy
        self.pp = pp
        self.ignoreEvasion = ignoreEvasion
        self.ignoreDef = ignoreDef
        self.ignoreWeather = ignoreWeather
        self.ignoreType = ignoreType
        self.ignoreImmunity = ignoreImmunity
        self.ignoreBarrier = ignoreBarrier
        self.ignoreAbility = ignoreAbility
        self.ignoreInvulnerability = ignoreInvulnerability
        self.targetAtk = targetAtk
        self.inverseDef = inverseDef
        self.DefAsAtk = DefAsAtk
        self.multiType = multiType
        self.interchangeType = interchangeType
        self.charging = charging
        self.critRatio = crit
        self.priority = priority
        self.recoil = recoil
        self.deduct = deduct
        self.crash = crash
        self.multi = multi
        self.effect_type = effect_type
        self.special_effect = special_effect
        self.effect_accuracy = effect_accuracy
        self.flags = flags
        self.custom = custom
        # Named conditions, resolved in Scripts/Battle/move_rules.py. Each is
        # the *name* of a rule rather than the rule itself: the choice is
        # data, the behaviour is code. Blank for the 360-odd moves whose row
        # already says everything about them.
        self.power_when = power_when
        self.weather_when = weather_when
        self.fails_unless = fails_unless


#: effect name -> the function that applies it. Built from the module rather
#: than written out, so a status added there is available here at once and a
#: typo cannot invent one.
STATUS_EFFECTS = {
    name: value for name, value in vars(status).items()
    if inspect.isfunction(value) and value.__module__ == status.__name__
}

#: the sigils
EFFECT_SEPARATOR = "|"
FUNCTION_MARK = "@"
NONE_MARK = "~"

#: which fields hold a list of bare strings (types, mostly)
STRING_LISTS = ("ignoreType", "ignoreImmunity", "multiType", "interchangeType")
#: which hold a list of numbers
NUMBER_LISTS = ("multi",)
#: which are yes/no
FLAGS = ("ignoreEvasion", "ignoreDef", "ignoreWeather", "ignoreBarrier",
         "ignoreAbility", "ignoreInvulnerability", "targetAtk", "inverseDef",
         "DefAsAtk", "custom")
#: which are plain numbers
NUMBERS = ("power", "accuracy", "pp", "crit", "priority", "recoil", "deduct",
           "crash", "effect_accuracy")
#: the column order of Data/moves.csv, and the argument order of Move()
FIELDS = ("name", "power", "attack_type", "type", "accuracy", "pp",
          "ignoreEvasion", "ignoreDef", "ignoreWeather", "ignoreType",
          "ignoreImmunity", "ignoreBarrier", "ignoreAbility",
          "ignoreInvulnerability", "targetAtk", "inverseDef", "DefAsAtk",
          "multiType", "interchangeType", "charging", "crit", "priority",
          "recoil", "deduct", "crash", "multi", "flags", "custom",
          "effect_type", "special_effect", "effect_accuracy",
          "power_when", "weather_when", "fails_unless")

#: `remarks` is a note to whoever is reading the spreadsheet, not something
#: the engine acts on -- so it is a column but not a constructor field, and
#: decode_row drops it. It says which moves have behaviour written in code as
#: well as in the table, and it is *generated* from the code by
#: Tools/move_code_scan.py rather than typed, so it cannot quietly go stale.
#: test_engine_integrity fails if the column and the code disagree.
#: columns naming a rule in Scripts/Battle/move_rules.py
RULE_COLUMNS = ("power_when", "weather_when", "fails_unless")

NOTE_COLUMNS = ("remarks",)
COLUMNS = FIELDS + NOTE_COLUMNS

MOVES_CSV = os.path.join("Data", "moves.csv")


class MoveDataError(Exception):
    """A row that cannot be read, named so the fix is obvious."""


# -- numbers ---------------------------------------------------------------
def _looks_numeric(text):
    body = text.strip().lstrip("-")
    return bool(body) and body.replace(".", "", 1).isdigit()


def _number(text, where):
    """int when it looks like one, float when it does not.

    The distinction is kept because the literal kept it: `power=40` was an int
    and `effect_accuracy=0.3` a float, and reproducing both exactly is what
    lets the conversion be checked field by field rather than approximately.
    """
    text = text.strip()
    try:
        return int(text) if "." not in text and "e" not in text.lower() \
            else float(text)
    except ValueError:
        raise MoveDataError("%s: %r is not a number" % (where, text))


# -- the special_effect column --------------------------------------------
def decode_effect(text, where):
    """One entry of `special_effect`. See the module docstring for the rules."""
    text = text.strip()
    if text == NONE_MARK:
        return None
    if text.startswith(FUNCTION_MARK):
        name = text[1:]
        try:
            return STATUS_EFFECTS[name]
        except KeyError:
            raise MoveDataError(
                "%s: no status effect called %r. The ones there are live in "
                "Scripts/Battle/moves_status_condition_apply.py: %s"
                % (where, name, ", ".join(sorted(STATUS_EFFECTS))))
    if "," in text:
        parts = text.split(",")
        if parts and parts[-1].strip() == "":
            parts = parts[:-1]              # trailing comma: a list of one
        return [_number(part, where) if _looks_numeric(part) else part.strip()
                for part in parts]
    # a bare number is a fraction or a count; anything else is a plain string
    if _looks_numeric(text):
        return _number(text, where)
    return text


# -- whole rows ------------------------------------------------------------
def decode_row(row):
    """A CSV row -> the keyword arguments Move() wants."""
    name = (row.get("name") or "").strip()
    if not name:
        raise MoveDataError("a row with no name")
    where = "move %r" % name
    out = {"name": name}

    for field in FIELDS:                  # not COLUMNS: remarks is a note
        if field == "name":
            continue
        raw = (row.get(field) or "")
        if field in FLAGS:
            out[field] = raw.strip().upper() in ("Y", "YES", "TRUE", "1")
        elif field in NUMBERS:
            out[field] = _number(raw, "%s, %s" % (where, field))
        elif field in STRING_LISTS:
            # blank entries dropped: these are genuinely just lists of type
            # names, so a trailing comma is decoration rather than meaning
            out[field] = [part.strip() for part in raw.split(",")
                          if part.strip()]
        elif field in NUMBER_LISTS:
            out[field] = [_number(part, "%s, %s" % (where, field))
                          for part in raw.split(",") if part.strip()]
        elif field == "effect_type":
            parts = raw.split(EFFECT_SEPARATOR)
            out[field] = ([part.strip() for part in parts] if len(parts) > 1
                          else raw.strip())
        elif field == "special_effect":
            parts = raw.split(EFFECT_SEPARATOR)
            out[field] = ([decode_effect(part, where) for part in parts]
                          if len(parts) > 1
                          else decode_effect(raw, where))
        elif field in RULE_COLUMNS:
            # a name from a closed vocabulary; an unknown one is an error
            # here rather than a condition that silently never fires
            try:
                move_rules.check(field, raw, where)
            except ValueError as problem:
                raise MoveDataError(str(problem))
            out[field] = raw.strip()
        else:                                   # attack_type, type, charging, flags
            out[field] = raw.strip()

    kinds = out["effect_type"]
    payload = out["special_effect"]
    if isinstance(kinds, list) and (not isinstance(payload, list)
                                    or len(payload) != len(kinds)):
        raise MoveDataError(
            "%s lists %d effect_type(s) but %s payload(s) -- they are paired "
            "by position, so the two columns must have the same number of "
            "%r-separated entries"
            % (where, len(kinds),
               len(payload) if isinstance(payload, list) else "1",
               EFFECT_SEPARATOR))
    return out


def _attribute_for(field):
    """The CSV column name and the attribute name differ in one place."""
    return "critRatio" if field == "crit" else field


def load(path=None):
    """Every move in the table, as {name: Move}."""
    path = path or MOVES_CSV
    moves = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            if not (row.get("name") or "").strip():
                # A wholly blank line is fine -- spreadsheets leave them, and
                # a spacer row between sections is a reasonable thing to want.
                # A row with *data* and no name is not: it would be dropped in
                # silence, and the move it was meant to add would simply not
                # exist in the game.
                if any((value or "").strip() for value in row.values()):
                    raise MoveDataError(
                        "%s line %d: this row has data but no name, so it "
                        "would be skipped without a word. Give it a name, or "
                        "empty the row." % (path, line))
                continue
            try:
                fields = decode_row(row)
            except MoveDataError as problem:
                raise MoveDataError("%s line %d: %s" % (path, line, problem))
            name = fields.pop("name")
            if name in moves:
                raise MoveDataError("%s line %d: %r appears twice"
                                    % (path, line, name))
            moves[name] = Move(name=name, **fields)
    return moves


#: every move in the game, read from Data/moves.csv.
#:
#: This was 1,368 lines of hand-written Move(...) calls above -- one per move,
#: each a call to the thirty-one argument constructor. Adding a move meant
#: editing Python, and the one bug that escaped from it was a name typed twice
#: and spelled differently the second time.
#:
#: Tools/moves_to_csv.py generated the table out of that literal and checked
#: all 387 moves field for field, status functions compared by identity.
#: `python Tools/moves_to_csv.py --check` still validates it.
list_of_moves = load()
