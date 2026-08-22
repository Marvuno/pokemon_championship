"""
The Pokedex's data and its search, with no toolkit in sight.

Two halves:

  build(...)   turns the game's own tables into plain dicts, once, on the
               worker thread -- same contract as the rest of bridge.py, so the
               interface never reaches into live game objects
  search(...)  filters those dicts from a single line of text

The search deliberately takes one string rather than a screen of dropdowns.
Six combo boxes for type/tier/stat/ability is what this usually becomes, and
it is slower to use than typing. Bare words match a name, a type or an
ability; everything else is `key:value` or `stat>number`:

    fire flying               both types
    tier:high spd>110         fast, and high tier
    move:earthquake           learns it
    ability:levitate
    total>500 custom:yes
    water -tier:boss          water, but not boss tier
    ghost cat:special         ghost-type special attackers (moves)

A leading `-` negates any term. Unknown keys match nothing rather than
everything, so a typo shows an empty list instead of the whole roster.
"""

import re

#: stat keys, and every spelling of them worth accepting. Data/pokemon.csv
#: calls Speed "Spd" while the battle HUD calls it "SPE" and uses "SPD" for
#: Special Defence -- so "spd" is genuinely ambiguous and is resolved the way
#: the CSV means it, with "spdef" required for the other one.
STAT_KEYS = {
    "hp": 0,
    "atk": 1, "attack": 1,
    "def": 2, "defence": 2, "defense": 2,
    "spa": 3, "spatk": 3, "sp.atk": 3, "special": 3,
    "spdef": 4, "sdef": 4, "spd.def": 4,
    "spd": 5, "spe": 5, "speed": 5,
}
#: what a bare word is matched against, per section
BARE_FIELDS = {
    "pokemon": ("name", "types", "abilities", "tier"),
    "moves": ("name", "type", "category"),
    "opponents": ("nickname", "name", "tier"),
    # a bare word finds an ability by its own name, or by a Pokemon with it
    "abilities": ("name", "pokemon", "text"),
}
TERM_RE = re.compile(r'([-+]?)([a-z.]+)\s*(>=|<=|>|<|=|:)\s*(.+)', re.I)


# --------------------------------------------------------------- building
def build(list_of_pokemon, list_of_moves, list_of_competitors, art_for=None):
    """Snapshot the three tables. Called once, from install_hooks."""
    moves = {}
    for key, move in (list_of_moves or {}).items():
        if key == "Switching":
            continue                       # not a move anyone "has"
        moves[key] = _move_entry(key, move)

    pokemon = []
    for name, mon in (list_of_pokemon or {}).items():
        pokemon.append(_pokemon_entry(name, mon))
    pokemon.sort(key=lambda entry: entry["name"])

    # which Pokemon learn each move -- an inversion of the table above, and
    # what turns a move list into something you can explore
    for entry in pokemon:
        for move_name in entry["moveset"]:
            if move_name in moves:
                moves[move_name]["learned_by"].append(entry["name"])
    for entry in moves.values():
        entry["learned_by"].sort()

    opponents = []
    for name, competitor in (list_of_competitors or {}).items():
        if getattr(competitor, "main", False):
            continue
        opponents.append(_opponent_entry(name, competitor, art_for))
    opponents.sort(key=lambda entry: -entry["rating"])

    return {"pokemon": pokemon,
            "moves": sorted(moves.values(), key=lambda e: e["name"]),
            "opponents": opponents,
            "abilities": _abilities(pokemon, list_of_competitors),
            "percentiles": _percentiles(pokemon)}


def _abilities(pokemon, list_of_competitors=None):
    """Every Pokemon ability in play, and which Pokemon have it.

    Pokemon abilities only. Character abilities are deliberately left out: they
    belong to the competitor, and which competitor has which is the thing
    Scout Opponent is for -- listing them here would have handed over, for
    free, information the scouting roll exists to gate. `list_of_competitors`
    is still accepted so the call site does not have to change.

    Built from what is actually assigned rather than from the ability registry,
    so an ability written but never given to a Pokemon does not pad the list.
    """
    from Scripts.Data.ability_text import ABILITY_TEXT
    found = {}
    for entry in pokemon:
        for ability in entry.get("abilities") or []:
            record = found.setdefault(str(ability), {
                "name": str(ability), "kind": "pokemon", "pokemon": [],
                # one line from Scripts/Data/ability_text.py, or nothing --
                # a missing entry shows no description rather than a guess
                "text": ABILITY_TEXT.get(str(ability), ""),
            })
            record["pokemon"].append(entry["name"])
    for record in found.values():
        record["pokemon"].sort()
    return sorted(found.values(), key=lambda record: record["name"])


def _pokemon_entry(name, mon):
    stats = list(getattr(mon, "base_stats", []) or [])
    ability = getattr(mon, "ability", None) or []
    return {
        "name": str(name),
        "types": [str(t) for t in (getattr(mon, "type", None) or [])],
        "abilities": [str(a) for a in (ability if isinstance(ability, list)
                                       else [ability])],
        "stats": [int(v) for v in stats],
        "total": int(getattr(mon, "total_stats", 0) or sum(stats)),
        "tier": str(getattr(mon, "tier", "") or ""),
        "custom": bool(getattr(mon, "custom", False)),
        "sprite": sprite_key(name),
        "moveset": [str(m) for m in (getattr(mon, "moveset", None) or [])
                    if m != "Switching"],
    }


def _move_entry(key, move):
    accuracy = getattr(move, "accuracy", 1)
    try:
        accuracy = None if accuracy is None or accuracy > 1 else float(accuracy)
    except Exception:
        accuracy = None
    multi = list(getattr(move, "multi", [0, 1]) or [0, 1])
    return {
        "name": str(getattr(move, "name", key)),
        "key": str(key),
        "type": str(getattr(move, "type", "Normal")),
        "category": str(getattr(move, "attack_type", "Status")),
        "power": int(getattr(move, "power", 0) or 0),
        "accuracy": accuracy,
        "pp": int(getattr(move, "pp", 0) or 0),
        "priority": int(getattr(move, "priority", 0) or 0),
        "crit": int(getattr(move, "critRatio", 0) or 0),
        "recoil": getattr(move, "recoil", 0) or 0,
        # `deduct` is the share of the user's own HP the move SPENDS -- Belly
        # Drum, Clangorous Soul, Unbreakable Will. It was being carried as
        # "drain" and described as recovering HP, which said the opposite of
        # what the move does. Actual draining is effect_type "hp_draining".
        "cost": getattr(move, "deduct", 0) or 0,
        "crash": getattr(move, "crash", 0) or 0,
        "charging": str(getattr(move, "charging", "") or ""),
        "multi": multi,
        # effect_type is sometimes a list of two; special_effect holds live
        # functions and stat lists, reduced here to names and numbers so the
        # snapshot stays plain data (the interface must never hold a reference
        # into the engine)
        "effect_type": (list(move.effect_type)
                        if isinstance(getattr(move, "effect_type", ""), list)
                        else str(getattr(move, "effect_type", "") or "")),
        "special_effect": _reduce_effect(getattr(move, "special_effect", "")),
        "effect_accuracy": getattr(move, "effect_accuracy", 1),
        "flags": str(getattr(move, "flags", "") or ""),
        "custom": bool(getattr(move, "custom", False)),
        "learned_by": [],
    }


def _ability_effect(competitor):
    """What the ability does, in the words Data/competitors.csv uses.

    Not a table in code: that was a second set of wording for the same 61
    abilities, and it drifted from the one the designer maintains.
    """
    try:
        from Scripts.Data.competitors import ability_text
    except Exception:
        return ""
    return _one_paragraph(ability_text(competitor))


def _aces_of(competitor):
    """The ace this competitor is known for, with its typing.

    **Only the Pokemon their own blurb already names.** The Pokedex
    deliberately publishes no roster -- which Pokemon a competitor brings is
    what scouting is for -- and the Poke columns are the whole designed team,
    six of them for the strongest competitors. Listing those would hand over
    for free exactly what About Opponent makes you earn.

    The Strategy text is already on screen and already says "Ace: Garchomp",
    so naming that Pokemon reveals nothing new; all this adds is its typing,
    which is what a player reads the line for. It is also not simply the
    first or last slot: Jason's ace is his only Pokemon, Cynthia's is her
    sixth, and Champion Marvin's blurb names two.

    A Poke cell may carry `iv=`, `ability=` and `moves=` (see
    competitors.Ace); none of that is published. That a Pokemon has been
    given a designed moveset is not a fact about the Pokemon.
    """
    from Scripts.Data.pokemon import list_of_pokemon
    blurb = str(getattr(competitor, "strategy", "") or "")
    out = []
    for entry in (getattr(competitor, "team", None) or []):
        species = str(getattr(entry, "name", entry))
        mon = list_of_pokemon.get(species)
        if mon is None or species not in blurb:
            continue
        if any(shown["name"] == species for shown in out):
            continue
        out.append({"name": species,
                    "types": [str(t) for t in (mon.type or [])]})
    return out


def _one_paragraph(text):
    """Collapse the hard line breaks the CSV carries into one flowing line.

    Data/competitors.csv holds these write-ups with newlines wherever the
    spreadsheet cell wrapped, which is nothing to do with where a sentence
    ends. Left in, they break the paragraph at arbitrary points and the
    word-wrapped label then wraps *again* inside each fragment -- ragged
    two- and three-word lines in the middle of a sentence.
    """
    return " ".join(str(text or "").split())


def _opponent_entry(name, competitor, art_for=None):
    ability = getattr(competitor, "ability", None) or ""
    return {
        "aces": _aces_of(competitor),
        # what the ability actually does, so the Pokedex can say it rather
        # than only naming it
        "ability_effect": _ability_effect(competitor),
        "name": str(name),
        "nickname": str(getattr(competitor, "nickname", name)),
        "rating": int(getattr(competitor, "strength", 0) or 0),
        "tier": str(getattr(competitor, "level", "") or ""),
        "ability": str(ability),
        "description": _one_paragraph(getattr(competitor, "desc", "")),
        "quote": _one_paragraph(getattr(competitor, "quote", "")),
        "strategy": str(getattr(competitor, "strategy", "") or ""),
        # Deliberately no roster. Which Pokemon a competitor always brings is
        # what scouting is for -- publishing it here, or letting a runs: query
        # find it, would hand over for free what About Opponent makes you earn.
        "art": (art_for(competitor) if art_for else ""),
    }


def _percentiles(pokemon):
    """Sorted values per stat, so a bar can say "how fast is 110" in context."""
    columns = []
    for index in range(6):
        columns.append(sorted(entry["stats"][index] for entry in pokemon
                              if len(entry["stats"]) > index))
    totals = sorted(entry["total"] for entry in pokemon)
    return {"stats": columns, "total": totals}


def percentile(sorted_values, value):
    """Where `value` falls in `sorted_values`, 0.0 to 1.0."""
    if not sorted_values:
        return 0.0
    import bisect
    return bisect.bisect_right(sorted_values, value) / len(sorted_values)


def sprite_key(name):
    """Map a Pokemon name to its sprite filename stem.

    The one implementation, imported by bridge.py rather than reimplemented
    there. It was written twice, and the second copy did not know about the
    regional prefixes, the apostrophe in Farfetch'd or the "(Blade Forme)"
    brackets -- so sixteen Pokemon showed a name instead of a sprite in the
    Pokedex while looking fine in battle. Mirrors the project's own
    image_builder.py, with a trailing-dash trim so "Aegislash (Shield Forme)"
    lands on "aegislash-shield" rather than "aegislash-shield-".
    """
    key = str(name).lower()
    for a, b in (("(", ""), (")", ""), ("'", "-"), (" ", "-"), ("forme", "")):
        key = key.replace(a, b)
    for region, suffix in (("alolan", "alola"), ("galarian", "galar"),
                           ("krusadian", "krusades")):
        if region in key:
            key = key.replace(region + "-", "") + "-" + suffix
    return key.strip("-")


# ---------------------------------------------------------------- searching
class Term:
    """One clause of a query."""

    __slots__ = ("negate", "key", "op", "value")

    def __init__(self, negate, key, op, value):
        self.negate, self.key, self.op, self.value = negate, key, op, value


def parse(query):
    """A query string into a list of Terms. Never raises."""
    terms = []
    for word in _split(query or ""):
        negate = word.startswith("-")
        word = word[1:] if negate else word
        if not word:
            continue
        match = TERM_RE.match(word)
        if match:
            _, key, op, value = match.groups()
            terms.append(Term(negate, key.lower(), op, value.strip().lower()))
        else:
            terms.append(Term(negate, None, None, word.lower()))
    return terms


def _split(query):
    """Words, keeping "quoted phrases" together."""
    out, buff, quoted = [], [], False
    for char in query:
        if char == '"':
            quoted = not quoted
            continue
        if char.isspace() and not quoted:
            if buff:
                out.append("".join(buff))
                buff = []
            continue
        buff.append(char)
    if buff:
        out.append("".join(buff))
    return out


def search(query, entries, kind):
    """Entries matching every term. An empty query matches everything."""
    terms = parse(query)
    if not terms:
        return list(entries)
    return [entry for entry in entries
            if all(_matches(term, entry, kind) for term in terms)]


def _matches(term, entry, kind):
    hit = _hit(term, entry, kind)
    return (not hit) if term.negate else hit


def _hit(term, entry, kind):
    if term.key is None:
        return _bare(term.value, entry, kind)

    key = term.key
    # a stat comparison
    if key in STAT_KEYS or key == "total":
        try:
            wanted = float(term.value)
        except ValueError:
            return False
        if key == "total":
            have = entry.get("total")
        else:
            stats = entry.get("stats") or []
            index = STAT_KEYS[key]
            have = stats[index] if len(stats) > index else None
        if have is None:
            return False
        return _compare(have, term.op, wanted)

    # everything else is a named field, matched as a substring
    value = term.value
    if key in ("type", "types"):
        return any(value in t.lower() for t in _listify(entry, "types", "type"))
    if key in ("ability", "abilities"):
        return any(value in a.lower()
                   for a in _listify(entry, "abilities", "ability"))
    if key in ("move", "moves", "learns"):
        if kind == "moves":
            return value in entry.get("name", "").lower()
        return any(value in m.lower() for m in entry.get("moveset") or [])
    if key == "tier":
        return value in str(entry.get("tier", "")).lower()
    if key == "name":
        return value in str(entry.get("name", "")).lower() or \
            value in str(entry.get("nickname", "")).lower()
    if key in ("cat", "category", "class"):
        return value in str(entry.get("category", "")).lower()
    if key == "custom":
        return bool(entry.get("custom")) == (value in ("y", "yes", "1",
                                                       "true"))
    if key in ("power", "pwr"):
        try:
            return _compare(entry.get("power", 0), term.op, float(value))
        except ValueError:
            return False
    if key == "rating":
        try:
            return _compare(entry.get("rating", 0), term.op, float(value))
        except ValueError:
            return False
    if key in ("effect", "does"):
        return value in str(entry.get("effect_type", "")).lower() or \
            value in str(entry.get("effect", "")).lower()
    if key in ("learnedby", "learned_by"):
        return any(value in who.lower() for who in entry.get("learned_by")
                   or [])
    return False               # an unknown key matches nothing, not everything


def _compare(have, op, wanted):
    if op in (":", "="):
        return float(have) == wanted
    if op == ">":
        return float(have) > wanted
    if op == "<":
        return float(have) < wanted
    if op == ">=":
        return float(have) >= wanted
    if op == "<=":
        return float(have) <= wanted
    return False


def _listify(entry, *keys):
    for key in keys:
        value = entry.get(key)
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        if value:
            return [str(value)]
    return []


def _bare(value, entry, kind):
    for field in BARE_FIELDS.get(kind, ("name",)):
        found = entry.get(field)
        if isinstance(found, (list, tuple)):
            if any(value in str(item).lower() for item in found):
                return True
        elif found and value in str(found).lower():
            return True
    return False


# --------------------------------------------------- readable move effects
#: a 9-slot modifier list indexes these, matching CombatantCard.STAGE_LABELS
STAGE_NAMES = ("HP", "Attack", "Defence", "Sp. Atk", "Sp. Def", "Speed",
               "Evasion", "Accuracy", "Crit rate")
#: effect_type -> a sentence about it, where the type alone says enough
EFFECT_PHRASES = {
    "no_effect": "",
    "switching": "Switches the user out afterwards.",
    "user_protection": "Protects the user this turn.",
    "countering": "Counters the damage taken.",
    "hp_split": "Averages both sides' HP.",
    "self_heal": "Heals the user.",
    "team_status_heal": "Cures the user's team of status conditions.",
    "self_team_buff": "Sets a screen or buff for the user's whole side.",
    "remove_team_buff": "Clears the target side's screens.",
    "apply_entry_hazard": "Lays an entry hazard on the target's side.",
    "weather_effect": "Changes the weather.",
    "target_disable": "Stops the target using a move.",
    "after_hand": "Doubles in power if the user moves second.",
    "before_hand": "Doubles in power if the user moves first.",
    "modifier_dependent": "Stronger the more the user is buffed.",
    "hp_draining": "Drains HP from the target.",
    "target_non_volatile": "Can inflict a status condition.",
    "target_volatile": "Can inflict a volatile condition.",
    "user_volatile": "Puts a condition on the user.",
    "self_modifier": "Changes the user's stats.",
    "opponent_modifier": "Changes the target's stats.",
}
#: status conditions as adjectives, for "can leave the target ___"
STATUS_WORDS = {
    "Paralysis": "paralysed", "Burn": "burned", "Poison": "poisoned",
    "Bad Poison": "badly poisoned", "Freeze": "frozen", "Sleep": "asleep",
    "Confused": "confused", "Flinch": "flinching",
}
#: single-letter move flags, from Documentation/documentation.md, written as
#: whole sentences -- "It ball or bomb." was not English
FLAG_NAMES = {
    "a": "It makes contact.",
    "b": "It cannot be protected against.",
    "c": "It thaws out a frozen user.",
    "d": "A biting move, so Strong Jaw powers it up.",
    "e": "A punching move, so Iron Fist powers it up.",
    "f": "Sound-based, so Soundproof is immune to it.",
    "g": "Powder-based, so Grass types are immune to it.",
    "h": "Pulse-based, so Mega Launcher powers it up.",
    "i": "A ball or bomb, so Bulletproof resists it.",
    "j": "Only works on the user's first turn out.",
}


def _reduce_effect(special):
    """special_effect holds live functions and stat lists. Keep only what can
    be described: a function's name, or the numbers."""
    if callable(special):
        return getattr(special, "__name__", "")
    if isinstance(special, (list, tuple)):
        if special and all(isinstance(v, int) for v in special):
            return list(special)
        return [_reduce_effect(item) for item in special]
    return special if isinstance(special, (str, int, float)) else ""


def _spaced(name):
    """"DestinyBond" -> "Destiny Bond". Underscores count as breaks too, and
    runs of space are collapsed -- "Stealth_Rock" was coming out doubled."""
    text = re.sub(r"[_\s]+", " ", str(name or ""))
    text = re.sub(r"(?<!^)(?<![\s])(?=[A-Z])", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def describe(entry):
    """Readable lines about what a move does, from the snapshot dict.

    A hand-written line in Scripts/Data/move_text.py wins outright when there
    is one. Those exist for mechanics that live in code rather than in the
    move's own data -- Brine doubling against a hurt target, Metronome picking
    at random -- which nothing here could work out by reading the move. For
    everything else the description is derived, so it cannot fall out of step
    with the move it describes.
    """
    from Scripts.Data.move_text import MOVE_TEXT
    written = MOVE_TEXT.get(str(entry.get("name", "")))
    if written:
        return [written]

    lines = []
    types = entry.get("effect_type")
    types = types if isinstance(types, list) else [types]
    special = entry.get("special_effect")
    specials = special if isinstance(special, list) and not all(
        isinstance(v, int) for v in special) else [special]

    for index, effect in enumerate(types):
        detail = specials[index] if index < len(specials) else None
        phrase = _stat_phrase(effect, detail) or _named_phrase(effect, detail)
        if phrase:
            lines.append(phrase)
        elif EFFECT_PHRASES.get(str(effect)):
            lines.append(EFFECT_PHRASES[str(effect)])

    chance = entry.get("effect_accuracy")
    try:
        if lines and chance is not None and 0 < float(chance) < 1:
            lines.append("Chance of that: %d%%." % round(float(chance) * 100))
    except (TypeError, ValueError):
        pass

    multi = entry.get("multi") or [0, 1]
    if len(multi) > 1 and multi[0] == 1:
        lines.append("Hits two to five times.")
    elif len(multi) > 1 and multi[0] == 2:
        lines.append("Hits three times, doubling in power each hit.")
    elif len(multi) > 1 and multi[1] > 1:
        lines.append("Hits %d times." % multi[1])

    if entry.get("recoil"):
        lines.append("The user takes recoil damage.")
    if entry.get("cost"):
        share = entry["cost"]
        lines.append("The user gives up %s of its HP to use it."
                     % _fraction(share))
    if entry.get("crash"):
        lines.append("The user is hurt if it misses.")
    if entry.get("charging"):
        lines.append("Takes a turn to charge.")
    if entry.get("priority"):
        lines.append("Priority %+d." % entry["priority"])
    if entry.get("crit"):
        lines.append("Higher critical-hit rate.")
    for flag in entry.get("flags") or "":
        if flag == "b" and _self_targeting(entry):
            # "It cannot be protected against" on Swords Dance is noise: the
            # move is aimed at its own user, so there was never anything to
            # protect against. Nearly every self-buff carries the flag.
            continue
        if flag in FLAG_NAMES:
            lines.append(FLAG_NAMES[flag])
    return lines


#: effects that only ever touch the user
SELF_EFFECTS = ("self_modifier", "user_volatile", "self_heal",
                "user_protection", "self_team_buff", "team_status_heal",
                "remove_team_buff", "weather_effect", "no_effect")


def _fraction(share):
    """A share of HP as words, because "0.3333333333" is not a description."""
    for denominator, name in ((2, "half"), (3, "a third"), (4, "a quarter"),
                              (8, "an eighth"), (16, "a sixteenth")):
        if abs(share - 1.0 / denominator) < 0.01:
            return name
    return "%d%%" % round(share * 100)


def _self_targeting(entry):
    """True for a status move that does nothing to the other side."""
    if entry.get("power"):
        return False
    if str(entry.get("category", "")).lower() != "status":
        return False
    types = entry.get("effect_type")
    types = types if isinstance(types, list) else [types]
    return bool(types) and all(str(t) in SELF_EFFECTS for t in types)


def _stat_phrase(effect, detail):
    """"lowers the target's Sp. Def by 2", from a 9-slot modifier list."""
    if not isinstance(detail, (list, tuple)) or not detail:
        return ""
    if not all(isinstance(v, int) for v in detail):
        return ""
    whose = ("the user's" if "self" in str(effect) or "user" in str(effect)
             else "the target's")
    # Group the stats that move by the same amount in the same direction, so a
    # five-stat buff reads as one sentence. Repeating "and raises the user's X
    # by 1" five times was accurate and unreadable -- Unbreakable Will ran to
    # 170 characters saying one thing.
    groups = {}
    for index, step in enumerate(detail[:len(STAGE_NAMES)]):
        if step:
            groups.setdefault(step, []).append(STAGE_NAMES[index])
    if not groups:
        return ""
    parts = []
    for step in sorted(groups, key=lambda value: (-value, value)):
        names = groups[step]
        listed = (names[0] if len(names) == 1
                  else "%s and %s" % (", ".join(names[:-1]), names[-1]))
        parts.append("%s %s %s by %d"
                     % ("raises" if step > 0 else "lowers", whose, listed,
                        abs(step)))
    return "It " + " and ".join(parts) + "."


def _named_phrase(effect, detail):
    """"Applies Flinch to the target." from a function called Flinch."""
    if not isinstance(detail, str) or not detail:
        return ""
    name = _spaced(detail)
    effect = str(effect)
    # a few effect types read badly as "applies X to the target"
    if effect == "weather_effect":
        return "Sets the weather to %s." % name
    if effect == "apply_entry_hazard":
        return "Lays %s on the target's side." % name
    if effect == "self_team_buff":
        return "Sets %s on the user's side." % name
    if effect == "target_non_volatile":
        # "Can leave the target paralysis" was not English
        return "Can leave the target %s." % STATUS_WORDS.get(
            name, "with %s" % name.lower())
    if "self" in effect or "user" in effect:
        return "Applies %s to the user." % name
    return "Applies %s to the target." % name
