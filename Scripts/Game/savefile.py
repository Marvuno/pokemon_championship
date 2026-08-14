"""
Reading and writing the save.

The save used to be `pickle.dump([Competitor, ...])` -- the live objects, with
fifteen attributes deleted first to keep them picklable. That coupled the file
to the shape of the classes, so renaming a competitor in Data/competitors.csv
made every older save fail to load, and editing a save meant writing Python.

This writes JSON instead: only the handful of facts that actually need to
outlive a run, keyed by name, with everything else rebuilt from the CSVs on
load. A Pokemon keeps just what was *rolled* for it -- its IVs, which ability
it got, which four moves -- because the rest (base stats, typing, tier) is
already in Data/pokemon.csv and would only go stale in a copy.

Old pickle saves still load: see `load`. Nothing overwrites them, so an
existing savefile.dat stays put as a backup once savefile.json is written.
"""

import json
import os
import pickle
import re

JSON_PATH = "savefile.json"
LEGACY_PATH = "savefile.dat"
VERSION = 1

#: Four careers, kept side by side in Save/ rather than one file at the root.
#: The single save was the reason the folder already had "savefile MAIN.dat"
#: and "savefile Evonne.dat" copied by hand -- swapping careers meant renaming
#: files with the game closed.
SLOTS = 4
SLOT_DIR = "Save"
#: Which slot save()/load()/exists() mean when not told otherwise. The engine
#: calls save(list_of_competitors) with no path from several places, so the
#: choice of career lives here rather than being threaded through all of them.
_current = 1


def slot_path(slot):
    """Where slot `slot` lives. Slots are 1-based, as the player sees them."""
    return os.path.join(SLOT_DIR, "savefile%d.json" % int(slot))


def select(slot):
    """Choose the career that save() and load() work on from here on."""
    global _current
    _current = max(1, min(SLOTS, int(slot)))
    return _current


def current():
    return _current


def _resolved(path=None, slot=None):
    if path is not None:
        return path
    return slot_path(slot if slot is not None else _current)


def exists(slot=None, path=None):
    """True if there is a career to continue in that slot.

    Slot 1 also answers for the two old single-save locations, so a player who
    has never seen slots still has their career offered as the first one.
    """
    target = _resolved(path, slot)
    if os.path.exists(target):
        return True
    if (slot if slot is not None else _current) == 1 and path is None:
        return os.path.exists(JSON_PATH) or os.path.exists(LEGACY_PATH)
    return False


def any_exists():
    """True if any of the four slots has anything in it."""
    return any(exists(slot=number) for number in range(1, SLOTS + 1))


def summary(slot):
    """What to print beside a slot on the menu, without loading it properly.

    Reads only the handful of header facts, so listing four careers does not
    mean rebuilding four teams from the CSVs. A slot that will not parse is
    reported as damaged rather than raising -- the menu still has to draw.
    """
    target = slot_path(slot)
    if not os.path.exists(target) and slot == 1:
        # the pre-slots save, not yet migrated
        target = JSON_PATH if os.path.exists(JSON_PATH) else None
        if target is None:
            return {"slot": slot, "used": os.path.exists(LEGACY_PATH),
                    "legacy": True, "nickname": "?", "rating": 0,
                    "participation": 0, "championship": 0}
    if not target or not os.path.exists(target):
        return {"slot": slot, "used": False}
    try:
        with open(target, encoding="utf-8") as handle:
            player = (json.load(handle) or {}).get("player") or {}
    except (ValueError, OSError):
        return {"slot": slot, "used": True, "damaged": True}
    return {"slot": slot, "used": True,
            "nickname": player.get("nickname") or "?",
            "rating": player.get("rating") or 0,
            "participation": player.get("participation") or 0,
            "championship": player.get("championship") or 0,
            "team": len(player.get("team") or [])}


def slots():
    """All four, in order, for whoever is drawing the menu."""
    return [summary(number) for number in range(1, SLOTS + 1)]


def describe(entry):
    """One line for a slot on the menu."""
    if not entry.get("used"):
        return "Slot %d: empty" % entry["slot"]
    if entry.get("damaged"):
        return "Slot %d: unreadable" % entry["slot"]
    if entry.get("legacy"):
        return "Slot %d: an older save" % entry["slot"]
    return ("Slot %d: %s -- rating %s, %s run(s), %s title(s)"
            % (entry["slot"], entry["nickname"], entry["rating"],
               entry["participation"], entry["championship"]))


def adopt_single_save():
    """Copy a pre-slots save into slot 1, once.

    Copied rather than moved, and only when slot 1 is empty, so the original
    savefile.json stays exactly where it was as a backup. Nothing here can
    lose a career: the worst case is a duplicate.
    """
    if os.path.exists(slot_path(1)) or not os.path.exists(JSON_PATH):
        return False
    if not os.path.isdir(SLOT_DIR):
        os.makedirs(SLOT_DIR, exist_ok=True)
    with open(JSON_PATH, "rb") as source:
        payload = source.read()
    with open(slot_path(1), "wb") as target:
        target.write(payload)
    return True


# ---------------------------------------------------------------- writing
def _pokemon_out(pokemon):
    """The rolled facts about one Pokemon. Everything else is in the CSV.

    getattr throughout because this also reads the Pokemon out of a legacy
    pickle, which was written with attributes deleted.
    """
    iv = getattr(pokemon, "iv", None)
    ability = getattr(pokemon, "ability", None)
    return {
        "name": getattr(pokemon, "name", ""),
        "iv": list(iv) if isinstance(iv, list) else [],
        "ability": list(ability) if isinstance(ability, list)
                   else ([ability] if ability else []),
        "moveset": [m for m in (getattr(pokemon, "moveset", None) or [])
                    if m != "Switching"],
    }


def _record_out(competitor):
    """Head-to-head, keyed by opponent name."""
    out = {}
    history = getattr(competitor, "opponent_history", None) or {}
    scores = getattr(competitor, "opponent_scores", None) or {}
    for name, record in history.items():
        wins, losses = (record + [0, 0])[:2]
        if not (wins or losses):
            continue                       # never met: nothing worth storing
        entry = {"wins": wins, "losses": losses}
        lines = scores.get(name)
        if lines:
            entry["scores"] = [list(pair) for pair in lines]
        out[name] = entry
    return out


def save(list_of_competitors, path=None, slot=None):
    player = list_of_competitors["Protagonist"]
    data = {
        "version": VERSION,
        "player": {
            "nickname": player.nickname,
            "rating": player.strength,
            "participation": player.participation,
            "championship": player.championship,
            "team": [_pokemon_out(p) for p in (player.team or [])],
            "history": {str(k): list(v)
                        for k, v in (player.history or {}).items()},
            "opponents": _record_out(player),
        },
        "competitors": {},
    }
    for name, competitor in list_of_competitors.items():
        if competitor.main:
            continue
        entry = {
            "participation": competitor.participation,
            "championship": competitor.championship,
        }
        history = {str(k): list(v)
                   for k, v in (competitor.history or {}).items()}
        if history:
            entry["history"] = history
        record = _record_out(competitor)
        if record:
            entry["opponents"] = record
        # Only competitors with something on record are written. A fresh
        # roster entry that has never played adds nothing but noise, and
        # omitting it is what lets a renamed competitor simply start clean.
        if history or record or competitor.participation:
            data["competitors"][name] = entry

    # ensure_ascii off so names keep their accents and emoji instead of
    # turning into \uXXXX -- the point of JSON here is that you can open the
    # file and read it.
    text = json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False)
    path = _resolved(path, slot)
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(_compact(text, data))
    return path


#: an indented array or object with nothing nested inside it -- a set of IVs,
#: one [my score, their score] pair, one {"wins": .., "losses": ..}
LEAF_RE = re.compile(r"[\[{]\s+[^][{}]*?\s+[]}]")


def _compact(text, data):
    """Put anything with nothing nested inside it back on one line.

    json.dumps(indent=1) gives every IV, move name and win count its own line,
    which turns a 69KB save into 234KB of mostly punctuation. These read
    better inline anyway -- "iv": [26, 26, 28, ...] rather than eight lines of
    it -- and it is the difference between a save you can scroll through and
    one you cannot.

    The result is parsed back and compared before it is accepted, so a name
    containing a bracket cannot quietly corrupt the file: on any mismatch the
    fully indented text is returned instead.
    """
    def one_line(match):
        return " ".join(match.group(0).split())

    # One pass, deliberately: a parent keeps the braces of the child it just
    # absorbed, so it can never match and whole sections stay on their own
    # lines. "iv" and one scoreline collapse; "team" and "opponents" don't.
    packed = LEAF_RE.sub(one_line, text)
    try:
        if json.loads(packed) == data:
            return packed
    except ValueError:
        pass
    return text


# ---------------------------------------------------------------- reading
def _apply_record(competitor, roster, record):
    """Fill in head-to-head, defaulting every roster name to a clean slate."""
    competitor.opponent_history = {name: [0, 0] for name in roster}
    competitor.opponent_scores = {}
    for name, entry in (record or {}).items():
        if name not in competitor.opponent_history:
            continue                     # renamed or removed since the save
        competitor.opponent_history[name] = [int(entry.get("wins", 0)),
                                             int(entry.get("losses", 0))]
        lines = entry.get("scores")
        if lines:
            competitor.opponent_scores[name] = [list(pair) for pair in lines]


def _apply_history(competitor, history):
    competitor.history = {int(k): tuple(v) for k, v in (history or {}).items()}


def _build_team(entries, list_of_pokemon):
    """Rebuild the kept team from Data/pokemon.csv plus the rolled facts."""
    from copy import deepcopy
    import operator

    team = []
    for entry in entries or []:
        template = list_of_pokemon.get(entry.get("name"))
        if template is None:
            continue                     # Pokemon renamed or removed since
        pokemon = deepcopy(template)
        ivs = entry.get("iv") or [0] * 6
        pokemon.iv = [int(v) for v in ivs][:6] or [0] * 6
        pokemon.total_iv = sum(pokemon.iv)
        pokemon.nominal_base_stats = list(map(operator.add,
                                              pokemon.base_stats, pokemon.iv))
        ability = entry.get("ability") or []
        if ability:
            pokemon.ability = list(ability)
        moves = [m for m in (entry.get("moveset") or []) if m != "Switching"]
        if not moves:
            # Nothing rolled on record: fall back to the CSV's move pool.
            moves = [m for m in pokemon.moveset if m != "Switching"][:4]
        # Deliberately without "Switching". battle_cycle prefixes it at the
        # start of every battle and end_battle strips it again, so a resting
        # team member does not carry it -- saving one would have the engine
        # add a second and leave two Switching entries in the move list.
        pokemon.moveset = moves
        team.append(pokemon)
    return team


def load(list_of_competitors, list_of_pokemon, path=None, slot=None):
    """Restore a save. Reads JSON, falling back to a legacy pickle.

    Returns the format it read ("json" | "pickle" | None) so the caller can
    say so, and never raises for a save that mentions someone the roster no
    longer has -- that competitor is simply skipped.

    Slot 1 falls back to the two pre-slots locations, so a career from before
    there were slots still loads without being migrated first.
    """
    target = _resolved(path, slot)
    if os.path.exists(target):
        with open(target, encoding="utf-8") as handle:
            data = json.load(handle)
        _load_json(data, list_of_competitors, list_of_pokemon)
        return "json"
    if path is None and (slot if slot is not None else _current) == 1:
        if os.path.exists(JSON_PATH):
            with open(JSON_PATH, encoding="utf-8") as handle:
                data = json.load(handle)
            _load_json(data, list_of_competitors, list_of_pokemon)
            return "json"
        if os.path.exists(LEGACY_PATH):
            _load_pickle(list_of_competitors, list_of_pokemon)
            return "pickle"
    return None


def _load_json(data, list_of_competitors, list_of_pokemon):
    roster = list(list_of_competitors)
    player = list_of_competitors["Protagonist"]
    saved = data.get("player") or {}
    player.nickname = saved.get("nickname", player.nickname)
    player.strength = int(saved.get("rating", player.strength))
    player.participation = int(saved.get("participation", 0))
    player.championship = int(saved.get("championship", 0))
    player.team = _build_team(saved.get("team"), list_of_pokemon)
    _apply_history(player, saved.get("history"))
    _apply_record(player, roster, saved.get("opponents"))

    for name, competitor in list_of_competitors.items():
        if competitor.main:
            continue
        entry = (data.get("competitors") or {}).get(name) or {}
        competitor.participation = int(entry.get("participation", 0))
        competitor.championship = int(entry.get("championship", 0))
        _apply_history(competitor, entry.get("history"))
        _apply_record(competitor, roster, entry.get("opponents"))


def _load_pickle(list_of_competitors, list_of_pokemon):
    """One-way migration from the old format."""
    roster = list(list_of_competitors)
    with open(LEGACY_PATH, "rb") as handle:
        records = pickle.load(handle)
    for record in records:
        name = getattr(record, "name", None)
        if getattr(record, "main", False):
            competitor = list_of_competitors["Protagonist"]
            competitor.nickname = getattr(record, "nickname",
                                          competitor.nickname)
            competitor.strength = getattr(record, "strength",
                                          competitor.strength)
            # Rebuilt through _build_team rather than reused directly: the
            # pickled Pokemon were written with attributes deleted and by an
            # older version of the class, so a fresh copy of the CSV entry
            # carrying the rolled facts is the only shape that is certain to
            # be complete.
            competitor.team = _build_team(
                [_pokemon_out(p) for p in getattr(record, "team", []) or []],
                list_of_pokemon)
        elif name in list_of_competitors:
            competitor = list_of_competitors[name]
        else:
            continue                     # renamed or removed since that save
        competitor.participation = getattr(record, "participation", 0)
        competitor.championship = getattr(record, "championship", 0)
        competitor.history = dict(getattr(record, "history", {}) or {})
        old = getattr(record, "opponent_history", {}) or {}
        competitor.opponent_history = {n: [0, 0] for n in roster}
        competitor.opponent_scores = {}
        for key, value in old.items():
            if key in competitor.opponent_history:
                competitor.opponent_history[key] = list(value)
