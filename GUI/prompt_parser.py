"""
Read a terminal prompt and work out what the player is being asked.

The game asks for input in about twenty places, each with its own phrasing and
its own way of listing options -- numbered lines, pipe-separated menus, boxed
menus, Python tuple lists, and sentinel values buried in a sentence ("Enter 9
when you are done"). Rather than edit twenty call sites, this module reads the
prompt plus whatever was printed just before it and derives the choices, so
every prompt in the game becomes buttons without touching game logic.

parse() returns a Prompt describing the input mode and the available choices.
"""

import re

from . import ansi

MODE_CONTINUE = "continue"   # any key -> one button
MODE_CONFIRM = "confirm"     # yes / no
MODE_CHOICES = "choices"     # numbered options
MODE_TEXT = "text"           # free text (player name)

# a numbered option on its own line or pipe-separated segment: "3: Fire Blast"
RE_NUMBERED = re.compile(r"^\s*(\d{1,3})\s*[:.]\s*(.+?)\s*$")
# boxed menu row: "| 0 NEW GAME |"
RE_BOXED = re.compile(r"\|\s*(\d{1,3})\s+([A-Z][A-Z0-9 /'\-]*?)\s*\|")
# python tuple list printed straight into a prompt: "[(0, 'Pikachu'), ...]"
#
# The quote is captured and back-referenced so the closing one has to match
# the opening one, and the name itself may contain the *other* quote. That is
# not a nicety: Python's repr switches to double quotes for a string holding
# an apostrophe, so a team list prints as
#
#     [(0, 'Pikachu'), (1, "Farfetch'd")]
#
# and a character class that ended at either quote stopped inside the name,
# failed to find the ")" after it, and dropped the entry. Farfetch'd and
# Sirfetch'd were missing from the switch-order and keep-team screens --
# silently, since the rest of the list parsed fine.
RE_TUPLE = re.compile(r"""\(\s*(\d{1,3})\s*,\s*(['"])(.*?)\2\s*\)""")
# sentinel described in a sentence: "Enter 9 when you are done"
RE_SENTINEL = re.compile(
    r"(?:enter|input|press|type)\s+['\"]?(\d{1,3})['\"]?\s+"
    r"(?:when|if|to|and|for)\s+([^.,;:!\n]{2,60})", re.I)
# trailing form: "10 to keep the whole team"
RE_SENTINEL_2 = re.compile(r"\b(\d{1,3})\s+to\s+([^.,;:!\n]{2,60})", re.I)

RE_ANY_KEY = re.compile(r"(?:press|enter|hit)\s+any\s+key|any\s+key\s+to\s+"
                        r"(?:proceed|continue)", re.I)
RE_YES = re.compile(r"(?:enter|press|input|type)\s+['\"]?Y['\"]?(?:\b|$)", re.I)
# the other way a yes/no question gets asked: a bare "Y/N" in it. The
# confirm branch below requires that nothing numbered was found, so a
# real menu that happens to mention Y/N is still a menu.
RE_YES_NO = re.compile(r"\bY\s*/\s*N\b", re.I)
RE_NAME = re.compile(r"what\s+is\s+your\s+name", re.I)

# Move-select prints this; it is a toggle rather than a move.
AUTO_BATTLE_VALUE = "100"


class Choice:
    """One clickable option."""

    __slots__ = ("value", "label", "kind")

    def __init__(self, value, label, kind="option"):
        self.value = str(value)
        self.label = _tidy(label)
        self.kind = kind          # option | sentinel | toggle

    def __repr__(self):
        return "Choice(%s, %r, %s)" % (self.value, self.label, self.kind)


class Prompt:
    """The parsed question, ready for the action bar to render."""

    def __init__(self, raw, mode, choices=None, question=""):
        self.raw = raw
        self.mode = mode
        self.choices = choices or []
        self.question = question

    def choice_for(self, value):
        for c in self.choices:
            if c.value == str(value):
                return c
        return None

    def __repr__(self):
        return "Prompt(%s, %d choices)" % (self.mode, len(self.choices))


def _tidy(label):
    label = ansi.strip(str(label)).strip()
    label = re.sub(r"\s+", " ", label)
    label = label.strip(" -\u2013>|")
    # Titles from boxed menus arrive shouting; ease them back.
    if label.isupper() and len(label) > 3:
        label = label.title()
    # Sentinels are lifted out of the middle of a sentence ("...or 9 to go
    # back"), so they arrive lowercase and read as sloppy on a button.
    if label[:1].islower():
        label = label[0].upper() + label[1:]
    return label


def _question_text(prompt):
    """The human part of the prompt, minus option lists and arrow cruft."""
    lines = [l.strip() for l in prompt.splitlines()]
    keep = []
    for line in lines:
        if not line or line in ("-->", "->"):
            continue
        # Drop any line that is purely an option list, whether it is one
        # option per line or a pipe-separated menu -- the buttons already
        # show them, so repeating them in the question is noise.
        segments = [seg.strip() for seg in line.split("||") if seg.strip()]
        if segments and all(RE_NUMBERED.match(seg) for seg in segments):
            continue
        keep.append(line)
    text = " ".join(keep)
    text = re.sub(r"\s*\[\(.*?\)\]\s*", " ", text)      # drop tuple lists
    text = re.sub(r"\s*-->\s*$", "", text)
    # A trailing "Y/N" is instructions for a terminal. Beside a Yes and a No
    # button it is noise, and the buttons say it better.
    text = re.sub(r"\s*\bY\s*/\s*N\b\s*[.:!]?\s*$", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tail_block(recent, max_lines=80, gap_tolerance=2):
    """The last run of option-ish lines printed before the prompt.

    Scanning backwards and stopping after a couple of consecutive plain lines
    keeps an old menu from leaking into the current question.
    """
    lines = recent.splitlines()[-max_lines:]
    block, gap, found = [], 0, False
    for line in reversed(lines):
        plain = line.strip()
        looks_optionish = bool(
            RE_NUMBERED.match(plain) or RE_BOXED.search(plain)
            or RE_TUPLE.search(plain))
        if looks_optionish:
            block.append(line)
            found = True
            gap = 0
        else:
            if found:
                gap += 1
                if gap > gap_tolerance:
                    break
            block.append(line)
    return "\n".join(reversed(block))


def _collect(text, into, seen):
    """Run every option pattern over text, appending new choices in place."""
    for line in text.splitlines():
        for segment in line.split("||"):
            m = RE_NUMBERED.match(segment)
            if m:
                _add(into, seen, m.group(1), m.group(2))
    for m in RE_BOXED.finditer(text):
        _add(into, seen, m.group(1), m.group(2))
    for m in RE_TUPLE.finditer(text):
        _add(into, seen, m.group(1), m.group(3))   # 2 is the quote itself


def _add(into, seen, value, label, kind="option"):
    value = str(int(value))
    if value in seen:
        return
    label = _tidy(label)
    if not label:
        return
    seen.add(value)
    into.append(Choice(value, label, kind))


def parse(prompt, recent_output=""):
    """Classify a prompt and extract its choices."""
    raw = prompt
    prompt = ansi.strip(prompt)
    recent = ansi.strip(recent_output)
    question = _question_text(prompt)

    if RE_ANY_KEY.search(prompt):
        return Prompt(raw, MODE_CONTINUE, question=question or "Continue")

    choices, seen = [], set()
    _collect(prompt, choices, seen)

    # Options printed before the prompt, but only if they are numbered
    # *differently* from the ones the prompt lists itself. A single question
    # never gives two things the same number, so an overlap means the block on
    # screen belongs to a different screen -- and topping the prompt's own
    # list up from it is how scouting produced a ghost button. About Opponent
    # prints the opponent's team as `0:`..`5:`; the pre-battle menu then asks
    # its question listing `0:`..`4:` inline. Five of the six were already
    # claimed, so the sixth Pokemon arrived as an extra option -- and clicking
    # it answered `5` to a menu with no option 5, which printed a complaint
    # and redrew the bar. A button that vanished and did nothing.
    #
    # A gap rule cannot separate these: only two plain lines sit between that
    # list and the prompt, fewer than the switch window has on a good day.
    # Disjointness can. The switch window lists `8:` and `9:` inline and gets
    # its Pokemon (`0:`..`5:`) from the block above it, which is exactly the
    # case this keeps working.
    nearby, nearby_seen = [], set()
    _collect(_tail_block(recent), nearby, nearby_seen)
    if not (nearby_seen & seen):
        for choice in nearby:
            _add(choices, seen, choice.value, choice.label, choice.kind)

    # sentinels are described in prose, so they come last and never overwrite
    # a real option with the same number
    for rx in (RE_SENTINEL, RE_SENTINEL_2):
        for m in rx.finditer(prompt):
            _add(choices, seen, m.group(1), m.group(2), kind="sentinel")

    if (RE_YES.search(prompt) or RE_YES_NO.search(prompt)) and not choices:
        return Prompt(raw, MODE_CONFIRM, question=question)

    if choices:
        choices.sort(key=lambda c: int(c.value))
        for c in choices:
            if c.value == AUTO_BATTLE_VALUE:
                c.kind = "toggle"
        return Prompt(raw, MODE_CHOICES, choices, question)

    if RE_NAME.search(prompt):
        return Prompt(raw, MODE_TEXT, question=question)

    return Prompt(raw, MODE_TEXT, question=question)


class PromptMemory:
    """parse() plus a memory of what each prompt looked like last time.

    When the player enters something the game rejects, it loops and calls
    input() again *without* reprinting the option list. Parsing that second
    prompt in isolation would find no options and fall back to a text box.
    Caching by exact prompt text restores the buttons, and because prompt
    strings are distinctive ("What is the move for Rampardos?") one prompt can
    never inherit another's options.
    """

    def __init__(self, limit=64):
        self._cache = {}
        self._order = []
        self._limit = limit

    def parse(self, prompt, recent_output=""):
        result = parse(prompt, recent_output)
        key = ansi.strip(prompt)
        if result.choices:
            if key not in self._cache:
                self._order.append(key)
                if len(self._order) > self._limit:
                    self._cache.pop(self._order.pop(0), None)
            self._cache[key] = result.choices
        elif result.mode == MODE_TEXT and key in self._cache:
            return Prompt(prompt, MODE_CHOICES, self._cache[key],
                          result.question)
        return result
