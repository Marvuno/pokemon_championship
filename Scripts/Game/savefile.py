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

The pickle format is gone. savefile.dat is no longer read, written, or looked
for -- every career is JSON in Save/, and an old .dat file sitting in the
project folder is now just a file the game ignores.
"""

import json
import os
import re
import shutil
from contextlib import suppress
from copy import deepcopy

JSON_PATH = "savefile.json"
VERSION = 1

#: Four careers, kept side by side in Save/ rather than one file at the root.
#: The single save was the reason the folder already had "savefile MAIN.dat"
#: and "savefile Evonne.dat" copied by hand -- swapping careers meant renaming
#: files with the game closed.
SLOTS = 4
SLOT_DIR = "Save"

#: competitors renamed since saves were written: old name -> current name.
#:
#: A save keys everything by competitor name -- who you have beaten, the
#: scorelines, each competitor's own record. `_apply_record` drops any name
#: the roster no longer has, which is right for a competitor who was deleted
#: and wrong for one who was merely renamed: their whole head-to-head history
#: would vanish silently. Translating on the way in keeps it, and costs
#: nothing for the saves that never knew the old name.
#:
#: This is cheaper and safer than rewriting the player's save files, which
#: would have to be done once per slot and could not be undone.
RENAMED = {
    "Voldemort": "Devoltorm",
}


def current_name(name):
    """The name this competitor goes by now."""
    return RENAMED.get(name, name)


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
        return os.path.exists(JSON_PATH)
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
            return {"slot": slot, "used": False}
    if not target or not os.path.exists(target):
        return {"slot": slot, "used": False}
    try:
        with open(target, encoding="utf-8") as handle:
            player = (json.load(handle) or {}).get("player") or {}
    except (ValueError, OSError):
        return {"slot": slot, "used": True, "damaged": True}
    return {"slot": slot, "used": True,
            "nickname": player.get("nickname") or "?",
            "appearance": player.get("appearance") or "",
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
    # Kept short on purpose: the interface turns each of these into a button
    # and a long line pushed the slot list into a scroller.
    return ("Slot %d: %s (%s) | Run: %s | Title: %s"
            % (entry["slot"], entry["nickname"], entry["rating"],
               entry["participation"], entry["championship"]))


#: how the CSVs describe everybody, taken once before anything is loaded
_pristine = None


def remember_pristine(list_of_competitors, list_of_pokemon):
    """Snapshot the freshly-imported rosters, once.

    load() writes into these dicts in place, so once a career has been read
    there is no way back to "as the CSV describes them" without a copy taken
    beforehand. Call this before the first load -- calling it again is a no-op,
    so it cannot capture an already-loaded career by accident.
    """
    global _pristine
    if _pristine is None:
        _pristine = (deepcopy(list_of_competitors), deepcopy(list_of_pokemon))
    return _pristine is not None


def restore_designed_teams(list_of_competitors):
    """Put every competitor's team back to the specs the CSV describes.

    `team_generation` writes the Pokemon it builds *back into*
    `participant.team`, and `round_begin` trims that list when a round wants
    fewer than six -- so a competitor who has been fought once carries built
    Pokemon from then on, in whatever order and number that round left them,
    instead of the `Ace` specs their designed team is written as. Their IVs,
    abilities and movesets are frozen from that first build too.

    Nothing noticed while one career meant one process: `restart()` is
    os.execl, so the roster came back from the CSV every time. An Auto Run
    plays several careers in one process and cannot, so this is what a fresh
    interpreter used to do for free.

    The player is left alone. Their team *is* the career -- it is the one
    thing the save carries forward -- and the competitors' teams are not
    saved at all, being rebuilt from the CSV on every load.
    """
    if _pristine is None:
        return False
    clean, _ = _pristine
    for name, who in list_of_competitors.items():
        if getattr(who, "main", False):
            continue
        source = clean.get(name)
        if source is None:
            continue
        who.team = deepcopy(getattr(source, "team", []) or [])
        if hasattr(who, "unused_team"):
            who.unused_team = []
    return True


def start_fresh(list_of_competitors, list_of_pokemon):
    """Put every competitor and Pokemon back to their CSV state.

    A new game used to inherit whatever was last loaded. Opening HISTORY or
    CONTINUE on one slot reads that career into these shared dicts, and
    starting a new game only ever set a nickname -- so a "new" career in slot 3
    began with the participation count, title count, championship history and
    head-to-head record of whichever save had been looked at, and saved all of
    it back under the new slot.

    Restores into the existing dicts rather than rebinding them, because every
    module has already imported these exact objects by name.
    """
    if _pristine is None:
        return False
    clean_competitors, clean_pokemon = _pristine
    list_of_competitors.clear()
    list_of_competitors.update(deepcopy(clean_competitors))
    list_of_pokemon.clear()
    list_of_pokemon.update(deepcopy(clean_pokemon))
    return True


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
            # who they chose to be, per slot -- the career history
            # shows this portrait for the rest of the save
            "appearance": getattr(player, "appearance", "") or "",
            "rating": player.strength,
            # A character ability copied off somebody they beat. Saved
            # because save_game() runs every round, so anything living only
            # in memory is gone by the next one -- and the Protagonist's own
            # CSV row is blank, which is what an older save restores to.
            "ability": str(getattr(player, "ability", "") or ""),
            # Coins belong to one career in one slot, so they live here
            # rather than anywhere shared. A save written before this
            # feature restores to nothing, which is what a new game has.
            "coins": max(0, int(getattr(player, "coins", 0) or 0)),
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
        # Only when it has actually drifted. A competitor still on their
        # shipped rating writes nothing, so re-tuning Data/competitors.csv
        # still reaches every save that never moved them.
        if competitor.strength != getattr(competitor, "base_strength",
                                          competitor.strength):
            entry["rating"] = competitor.strength
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
    _write_atomically(path, _compact(text, data))
    return path


#: kept beside each save: the last version that was written whole
BACKUP_SUFFIX = ".bak"
#: where a save is built before it replaces the real one
PENDING_SUFFIX = ".new"


def _write_atomically(path, body):
    """Replace `path` with `body`, or leave it exactly as it was.

    `open(path, "w")` truncates immediately and only then writes -- so a
    crash, a power cut or a killed process partway through leaves a
    truncated file where a career used to be. There is no recovering from
    that, and it is the only failure in this game a player cannot undo.
    save() runs every round, so a career is exposed several times a run.

    Built beside the real file and renamed over it instead. os.replace is
    atomic on Windows and POSIX both, so a reader sees either the whole old
    save or the whole new one, never half of either.

    The previous save is kept as a `.bak` too. That covers what renaming
    cannot: a save written perfectly that is nonetheless *unwanted*. It
    costs one rename per round.
    """
    pending = path + PENDING_SUFFIX
    with open(pending, "w", encoding="utf-8") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())     # on the disk, not merely in the cache
    if os.path.exists(path):
        # Copied, not renamed. Renaming the save out of the way first left a
        # window with no save at all -- and if the rename below then failed,
        # the career existed only as a .bak nothing would look for. Copying
        # means `path` always holds the old career right up to the instant
        # it holds the new one.
        #
        # A failed backup must not stop the save: the rename below is what
        # actually protects the career, and this is the extra.
        with suppress(OSError):
            shutil.copyfile(path, path + BACKUP_SUFFIX)
    os.replace(pending, path)


def backup_of(path=None, slot=None):
    """The `.bak` beside a save, if there is one."""
    candidate = _resolved(path, slot) + BACKUP_SUFFIX
    return candidate if os.path.exists(candidate) else ""


def recover(path=None, slot=None):
    """Put the `.bak` back over the save. True if there was one.

    The other half of keeping a backup: one nothing can restore is
    decoration. This is what gives a slot that will not load an answer
    other than "start again".
    """
    path = _resolved(path, slot)
    backup = backup_of(path)
    if not backup:
        return False
    with open(backup, encoding="utf-8") as handle:
        body = handle.read()
    _write_atomically(path, body)
    return True


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
    for saved_name, entry in (record or {}).items():
        # a renamed competitor is the same competitor: keep their record
        name = current_name(saved_name)
        if name not in competitor.opponent_history:
            continue                     # removed from the roster since
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
    """Restore a save.

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
    return None


def _load_json(data, list_of_competitors, list_of_pokemon):
    roster = list(list_of_competitors)
    player = list_of_competitors["Protagonist"]
    saved = data.get("player") or {}
    player.nickname = saved.get("nickname", player.nickname)
    player.appearance = saved.get("appearance", "") or ""
    player.strength = int(saved.get("rating", player.strength))
    player.coins = max(0, int(saved.get("coins", 0) or 0))
    # "" for a save written before abilities could be copied, which is also
    # exactly what a player who has not copied one has
    player.ability = str(saved.get("ability", "") or "")
    player.participation = int(saved.get("participation", 0))
    player.championship = int(saved.get("championship", 0))
    player.team = _build_team(saved.get("team"), list_of_pokemon)
    _apply_history(player, saved.get("history"))
    _apply_record(player, roster, saved.get("opponents"))

    saved_competitors = data.get("competitors") or {}
    # the same translation for a competitor's *own* record, not just for who
    # they have faced
    for old_name, new_name in RENAMED.items():
        if old_name in saved_competitors and new_name not in saved_competitors:
            saved_competitors[new_name] = saved_competitors[old_name]

    for name, competitor in list_of_competitors.items():
        if competitor.main:
            continue
        entry = saved_competitors.get(name) or {}
        # No "rating" key means a save from before ratings drifted, or a
        # competitor who has never moved: either way the CSV value stands.
        competitor.strength = int(entry.get("rating", competitor.base_strength)) \
            if hasattr(competitor, "base_strength") else competitor.strength
        competitor.participation = int(entry.get("participation", 0))
        competitor.championship = int(entry.get("championship", 0))
        _apply_history(competitor, entry.get("history"))
        _apply_record(competitor, roster, entry.get("opponents"))

