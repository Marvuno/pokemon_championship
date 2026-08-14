"""
Run the existing command-line game underneath a graphical interface.

The game logic is complete and correct, so none of it is rewritten here. This
module runs main() on a worker thread and redirects the three things that made
it a terminal program:

  print()      -> event queue -> the log panel
  input()      -> blocks the worker until the GUI supplies an answer
  os.system    -> 'cls' clears the log panel instead of a console

On top of that it installs read-only hooks on a handful of game functions so the
interface knows *what* is being asked (a move, a switch, a menu) and can show
HP bars, sprites and type-coded move cards. Hooks snapshot state into plain
dicts and then call the original function untouched, so battle behaviour,
damage rolls and AI decisions are identical to the terminal version.

Threading contract
  worker thread: only ever touches queues and threading.Events
  GUI thread:    only ever reads snapshots; never calls into game code
The worker is blocked inside input() the whole time the player is deciding,
so snapshots can never be torn.
"""

import builtins
import collections
import os
import queue
import sys
import threading
import time
import traceback

from . import codex
from .ansi import strip as ansi_strip


import re

BARE_REPR_RE = re.compile(r"^\{.*\}$")
#: elo_rating()'s per-match line, e.g. "Ash Ketchum: Win [+12]"
ELO_LINE_RE = re.compile(
    r"^(?P<name>.+?):\s*(?P<result>Win|Lose)\s*\[(?P<sign>[+-])"
    r"(?P<value>\d+)\]\s*$")


def is_raw_debug_dump(text):
    """True for the engine's own unfiltered per-turn state dump.

    That print() call joins many pieces -- name, type, "Stats Change:",
    "Volatile Status:", "In-battle Effects:", "Disabled:" -- with embedded
    newlines, so it always arrives here as one chunk. Two markers unique to
    it are enough to identify it without touching the game file.
    """
    return "Stats Change:" in text and "Volatile Status:" in text


#: Lines the terminal version prints as its user interface, which this one
#: draws as widgets instead. Measured across six full battles: of 7,044 lines
#: printed, about a third were these -- the per-turn state dump, the ASCII HP
#: bar, the roster listing with raw IV and stat arrays. Every one of them is
#: already on screen properly (stat-stage chips, the condition chip, the HP
#: bar, the Field board, the team viewer), so in the log they are noise on top
#: of a nicer version of the same facts. The terminal version still gets them:
#: this is the interface deciding what it needs, not the engine losing output.
DUMP_PREFIXES = (
    "Status:",
    "Stats Change:",
    "Volatile Status:",
    "In-battle Effects:",
    "Charging:",
    "Base Stats:",
    "Moveset:",
    "Ability:",
    "ID:",
)
#: the drawn HP bar, and a line that is nothing but a number
HP_BAR_RE = re.compile(r"^[|█░\s]*\d+\s*%\s*$")
BARE_NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?$")
#: the caret the terminal prints to show it is waiting for you to type. The
#: window asks with buttons instead, so in the log it is 116 lines of nothing.
CARET_RE = re.compile(r"^-+>\s*$")


def is_state_dump(line):
    """True for one line of the terminal's own per-turn readout."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(DUMP_PREFIXES):
        return True
    return bool(HP_BAR_RE.match(stripped) or BARE_NUMBER_RE.match(stripped)
                or CARET_RE.match(stripped))


def scrub_state_dumps(text):
    """Drop the terminal readout lines, keep the narration around them."""
    if not text.strip():
        return text
    lines = text.split("\n")
    kept = [line for line in lines if not is_state_dump(line)]
    if not any(line.strip() for line in kept):
        return ""
    return "\n".join(kept)


#: a line with nothing on it but rule and block characters: the block-letter
#: title, and the ruled frame drawn around every bracket entry. Letters and
#: digits are deliberately absent from this set, so a line carrying any actual
#: text can never match it.
BOX_ONLY_RE = re.compile(
    "^[\\s=\\-_|+"
    "─━│┃┌┐└┘├┤"
    "┬┴┼"
    "═║╔╗╚╝╠╣╦╩╬"
    "▀▄█░▒▓]+$")
#: one row of a ruled table -- "| 1  | Expert Cynthia | A | 346 |" in box
#: characters. It holds real information, so it is rewritten rather than cut.
TABLE_ROW_RE = re.compile("^\\s*║.*║\\s*$")


def flatten_table_row(line):
    """A ruled row as plain columns: the cells, two spaces apart."""
    cells = [cell.strip() for cell in line.strip().strip("║").split("║")]
    return "  ".join(cell for cell in cells if cell)


def simplify_box_art(text):
    """Rewrite the terminal's drawn artwork as plain text.

    The engine draws a block-letter title and rules a frame around every
    bracket entry -- three lines per entry, two of which are pure box
    characters. That is 640 lines of frame in a five-battle run, and the log
    is a transcript to be read back or searched, not a screen. So the frames
    and the title go, and the row inside each frame is rewritten as its
    columns. Nothing that carries information is lost.

    This is the log only. capture() takes its copy before any of this runs,
    so the title screen and the tutorial still show the artwork as drawn.
    """
    out = []
    for line in text.split("\n"):
        clean = ansi_strip(line)
        if TABLE_ROW_RE.match(clean):
            flat = flatten_table_row(clean)
            if flat:
                out.append(flat)
            continue
        if clean.strip() and BOX_ONLY_RE.match(clean):
            continue
        out.append(line)
    if not any(line.strip() for line in out):
        return ""
    return "\n".join(out)


def for_log(text):
    """Everything that stands between a print() and the log panel."""
    return simplify_box_art(scrub_state_dumps(scrub_bare_reprs(text)))


def scrub_bare_reprs(text):
    """Drop stray lines that are nothing but a raw dict repr.

    Field effects and similar are already shown properly in the HUD's
    field-note strip; the one line in the engine's own turn banner that
    prints the underlying dict directly (e.g. "{'Trick Room': 0}") is a
    leftover of debug printing, not narration, so it is dropped here
    rather than reproduced verbatim in the log.

    Deliberately dict-only (curly braces), not list-shaped: several menus
    -- team selection, reordering, the "keep N Pokemon" save prompt --
    print a bare `[(0, 'Name'), (1, 'Name'), ...]` list that the prompt
    parser reads back out of the log to build its buttons. Stripping that
    would silently break those screens' buttons.
    """
    if "\n" not in text:
        return text
    lines = text.split("\n")
    kept = [l for l in lines if not BARE_REPR_RE.match(l.strip())]
    return "\n".join(kept)

#: The three questions history_screen() asks, by a fragment of each one, and
#: what the interface should do about them. The window shows all four views at
#: once, so the player never answers any of these -- "yes" to both
#: confirmations is the only path that reaches the data, and the competitor
#: number comes from clicking a name.
CAREER_PICK = "pick"                 # waiting on a click in the window
CAREER_CONFIRM = "confirm"           # answer yes to get to the data
CAREER_PROMPTS = (
    ("read the stats of a selected character", CAREER_CONFIRM),
    ("match history against individuals", CAREER_CONFIRM),
    ("choose the participant", CAREER_PICK),
)


#: choose_pokemon()'s questions, and what each one is actually offering. The
#: reward screen is driven from the compare window now, so the interface has to
#: know which of these is on the table -- "take one of theirs" and "swap one of
#: yours for one of theirs" are different offers and the buttons should not
#: pretend otherwise. Order matters: the confirmations are matched last, since
#: their wording is the least distinctive.
REWARD_TAKE = "take"          # team not full: theirs, or the organiser's
REWARD_SWAP = "swap"          # team full: one of yours for one of theirs
REWARD_PICK_THEIRS = "pick_theirs"
REWARD_PICK_MINE = "pick_mine"
REWARD_PROMPTS = (
    ("may take one pokemon from the opponent", REWARD_PICK_THEIRS),
    ("take the pokemon you want on the other team", REWARD_PICK_THEIRS),
    ("don't want on your team", REWARD_PICK_MINE),
    ("want to take from the opponent", REWARD_TAKE),
    ("want to swap", REWARD_SWAP),
)


def reward_prompt_kind(text):
    """Which of choose_pokemon()'s questions this is, or None."""
    lowered = (text or "").lower()
    for marker, kind in REWARD_PROMPTS:
        if marker in lowered:
            return kind
    return None


def career_prompt_kind(text):
    """Which of history_screen()'s questions this is, or None."""
    lowered = (text or "").lower()
    for marker, kind in CAREER_PROMPTS:
        if marker in lowered:
            return kind
    return None


# ---------------------------------------------------------------------------
# events pushed to the GUI (single queue, so ordering is preserved)
# ---------------------------------------------------------------------------
EV_TEXT = "text"      # payload: str, possibly containing ANSI escapes
EV_CLEAR = "clear"    # payload: None
EV_STATE = "state"    # payload: dict snapshot of the battle / menu
EV_INPUT = "input"    # payload: InputRequest
EV_DONE = "done"      # payload: 'quit' | 'restart' | 'finished'
EV_ERROR = "error"    # payload: traceback string
EV_BANNER = "banner"  # payload: dict(kind, text, side)


class Shutdown(BaseException):
    """Raised inside the worker to unwind it when the window closes.

    Derives from BaseException so the game's `except Exception` and
    contextlib.suppress(ValueError, ...) blocks cannot swallow it.
    """


class InputRequest:
    """One pending question. The worker waits on `event` for `value`."""

    __slots__ = ("prompt", "kind", "event", "value", "recent")

    def __init__(self, prompt, kind):
        self.prompt = prompt
        self.kind = kind          # 'move' | 'switch' | 'generic'
        self.event = threading.Event()
        self.value = ""
        self.recent = ""          # everything printed since the last answer

    def answer(self, value):
        self.value = "" if value is None else str(value)
        self.event.set()


def _g(obj, name, default=None):
    """Attribute read that tolerates the game deleting attributes on save."""
    try:
        value = getattr(obj, name)
    except Exception:
        return default
    return default if value is None else value


class Bridge:
    """Owns the worker thread, the event queue and the I/O redirection."""

    def __init__(self, project_root, difficulty="normal"):
        self.root = project_root
        #: "normal" | "beginner" -- read by install_hooks, once
        self.difficulty = difficulty
        self.events = queue.Queue()
        self.pending = None          # InputRequest awaiting an answer
        self.recent_output = []      # printed lines since the last answer
        self.next_input_kind = "generic"
        self.state = {}              # latest snapshot (GUI-thread readable)
        self.before_input = None     # set by install_hooks; see _ask()
        self.ctx = {}                # set by install_hooks; the live battle
        self.stopping = False
        self.thread = None
        self._real_print = builtins.print
        self._real_input = builtins.input
        self._real_system = os.system
        self._lock = threading.Lock()
        self._capture_stack = []      # list of lists; see capture()
        self._quiet = 0               # >0: capture text but don't log it
        self.banners = []             # rolling list of recent banner events

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        self._install_io()
        self.thread = threading.Thread(target=self._run, name="game",
                                       daemon=True)
        self.thread.start()

    def stop(self):
        """Ask the worker to unwind. Safe to call more than once."""
        self.stopping = True
        pending = self.pending
        if pending is not None:
            pending.answer("")
            pending.event.set()

    def _run(self):
        os.chdir(self.root)
        if self.root not in sys.path:
            sys.path.insert(0, self.root)
        try:
            import main as game_main          # loads every game module
            install_hooks(self, game_main)
            game_main.main()
            self.emit(EV_DONE, "finished")
        except Shutdown:
            pass
        except SystemExit:
            self.emit(EV_DONE, "quit")
        except _RestartRequest:
            self.emit(EV_DONE, "restart")
        except BaseException:
            self.emit(EV_ERROR, traceback.format_exc())

    # -- event plumbing ----------------------------------------------------
    def emit(self, kind, payload=None):
        self.events.put((kind, payload))

    def _install_io(self):
        bridge = self

        def gui_print(*args, sep=" ", end="\n", file=None, flush=False):
            if file is not None and file not in (sys.stdout, sys.stderr):
                return bridge._real_print(*args, sep=sep, end=end, file=file,
                                          flush=flush)
            text = sep.join(str(a) for a in args) + end
            bridge._write(text)

        def gui_input(prompt=""):
            return bridge._ask(str(prompt))

        def gui_system(command):
            cmd = str(command).strip().lower()
            if cmd in ("cls", "clear"):
                bridge.emit(EV_CLEAR)
                with bridge._lock:
                    bridge.recent_output = []
                return 0
            return bridge._real_system(command)

        builtins.print = gui_print
        builtins.input = gui_input
        os.system = gui_system

    def restore_io(self):
        builtins.print = self._real_print
        builtins.input = self._real_input
        os.system = self._real_system

    def _write(self, text):
        if self.stopping:
            raise Shutdown()
        # Feed any active capture() calls first -- these exist regardless of
        # whether the text also reaches the visible log.
        for buf in self._capture_stack:
            buf.append(text)
        if self._quiet:
            # read the text without it appearing anywhere: used to lift the
            # backstory and tutorial out of the engine at startup so the
            # title screen can show them on demand
            return
        if is_raw_debug_dump(text):
            # The engine's own per-turn "Stats Change: [...] Volatile
            # Status: [...]" dump duplicates, in raw Python-repr form,
            # information the interface already renders as HUD widgets
            # (stat badges, condition chips, the HP bar itself). Forwarding
            # it to the log would just be noise on top of a nicer version
            # of the same facts, so it stops here.
            return
        text = for_log(text)
        if not text.strip():
            return
        with self._lock:
            self.recent_output.append(text)
            if len(self.recent_output) > 400:
                del self.recent_output[:200]
        self.emit(EV_TEXT, text)

    def capture(self, fn, *a, **kw):
        """Call fn, returning (result, everything it printed).

        Nested captures all see the same text -- an outer capture (e.g. one
        whole move resolving) still gets the full transcript even though an
        inner capture (e.g. the ability that triggered mid-move) also grabs
        its own slice for a separate banner.
        """
        buf = []
        self._capture_stack.append(buf)
        try:
            result = fn(*a, **kw)
        finally:
            self._capture_stack.pop()
        return result, "".join(buf)

    def capture_quiet(self, fn, *a, **kw):
        """capture(), but the text never reaches the log panel."""
        self._quiet += 1
        try:
            return self.capture(fn, *a, **kw)
        finally:
            self._quiet -= 1

    def emit_banner(self, kind, text, side=None, **extra):
        clean = ansi_strip(text).strip()
        if not clean:
            return
        event = {"kind": kind, "text": clean, "side": side, "ts": time.time()}
        event.update(extra)
        self.banners.append(event)
        del self.banners[:-40]
        self.emit(EV_BANNER, event)

    def _ask(self, prompt):
        """Called on the worker thread; blocks until the GUI answers."""
        if self.stopping:
            raise Shutdown()
        # Re-snapshot before every question. The hooks publish state when a
        # game function is entered, but several of them ask more than once --
        # select_move loops on an invalid or non-move answer -- and the
        # interface was left rendering the state from before the previous
        # answer. Toggling auto battle was the visible casualty: the engine
        # flipped it and asked again, but the button still read "off", so it
        # looked like the click had done nothing at all.
        if self.before_input is not None:
            try:
                self.before_input()
            except Exception:
                pass
        if prompt:
            # The question goes to the log by hand here rather than through
            # _write, so it has to be scrubbed by hand too -- otherwise the
            # terminal's "--> " caret rides along on the end of every prompt
            # and the log fills up with a marker asking you to type at a
            # window that answers with buttons. The request itself keeps the
            # prompt exactly as the engine wrote it: the parser reads the
            # option list out of it, so it must not be touched.
            shown = for_log(prompt)
            if shown.strip():
                self.emit(EV_TEXT, shown)
        request = InputRequest(prompt, self.next_input_kind)
        with self._lock:
            request.recent = "".join(self.recent_output)
        self.pending = request
        self.emit(EV_INPUT, request)
        request.event.wait()
        self.pending = None
        with self._lock:
            self.recent_output = []
        if self.stopping:
            raise Shutdown()
        return request.value

    # -- snapshots ---------------------------------------------------------
    def publish(self, **fields):
        """Merge fields into the shared snapshot and notify the GUI."""
        self.state.update(fields)
        self.emit(EV_STATE, dict(self.state))

    def set_auto_battle(self, on):
        """Turn auto battle on or off from the interface.

        The engine only ever sets this flag -- answering 100 at move select
        switches it on and nothing switches it off, because once the AI is
        picking moves the player is never asked again. Writing the flag
        directly is the only way back: it is a plain bool on the battleground
        the worker reads once per turn, so there is nothing to tear.
        """
        battleground = (self.ctx or {}).get("battleground")
        if battleground is None:
            return False
        battleground.auto_battle = bool(on)
        field = snap_field(battleground)
        self.publish(field=field)
        return True

    def set_volume(self, value):
        try:
            import pygame
            pygame.mixer.music.set_volume(max(0.0, min(1.0, value)))
        except Exception:
            pass


class _RestartRequest(BaseException):
    """Replaces the game's os.execl-based restart with a clean signal."""


# ---------------------------------------------------------------------------
# snapshotting game objects into plain dicts
# ---------------------------------------------------------------------------
STAT_NAMES = ("HP", "Atk", "Def", "SpA", "SpDef", "Speed")
MOD_NAMES = ("HP", "Atk", "Def", "SpA", "SpDef", "Speed", "Evasion",
             "Accuracy", "Crit")


#: one implementation, in GUI/codex.py -- see the note there about the second
#: copy that got sixteen names wrong
sprite_key = codex.sprite_key


def character_art(competitor):
    """Path to a competitor's portrait, relative to the project root.

    Assets/characters is named by competitor, mostly .jpg with a couple of
    .png -- so the extension has to be looked for rather than assumed.
    Returns "" when there is no artwork, which the interface reads as "just
    show the write-up".
    """
    name = str(_g(competitor, "name", "") or _g(competitor, "nickname", ""))
    for candidate in (name, str(_g(competitor, "nickname", ""))):
        if not candidate:
            continue
        for extension in (".jpg", ".png", ".jpeg"):
            relative = os.path.join("Assets", "characters",
                                    candidate + extension)
            if os.path.exists(relative):
                return relative
    return ""


def snap_move(name):
    """Move metadata for a move card, read from the game's own move table."""
    try:
        from Scripts.Data.moves import list_of_moves
        move = list_of_moves[name]
    except Exception:
        return {"name": name, "type": "Normal", "category": "Status",
                "power": 0, "accuracy": None, "priority": 0}
    accuracy = _g(move, "accuracy", 1)
    try:
        accuracy = None if accuracy is None or accuracy > 1 else float(accuracy)
    except Exception:
        accuracy = None
    return {
        "name": _g(move, "name", name),
        "type": _g(move, "type", "Normal"),
        "category": _g(move, "attack_type", "Status"),
        "power": _g(move, "power", 0) or 0,
        "accuracy": accuracy,
        "priority": _g(move, "priority", 0) or 0,
        "multi": list(_g(move, "multi", [0, 1]) or [0, 1]),
        "recoil": _g(move, "recoil", 0) or 0,
    }


def snap_pokemon(mon, active=False):
    if mon is None:
        return None
    stats = _g(mon, "battle_stats", None)
    has_stats = isinstance(stats, (list, tuple)) and len(stats) > 0
    max_hp = _g(mon, "hp", 0) or 0
    if has_stats:
        current = stats[0]
    else:
        # battle_setup() hasn't run for this Pokemon yet this round (it's
        # the one place that fills in both hp and battle_stats together),
        # so there's no real HP reading -- report full/healthy rather than
        # the 0 a missing snapshot would otherwise give, which read as
        # "fainted" for a team that has never even been in a battle.
        current = max_hp or 1
    if not max_hp:
        max_hp = current or 1
    volatile = _g(mon, "volatile_status", {}) or {}
    modifier = list(_g(mon, "modifier", [0] * 9) or [0] * 9)
    moveset = list(_g(mon, "moveset", []) or [])
    disabled = dict(_g(mon, "disabled_moves", {}) or {})
    charging = list(_g(mon, "charging", ["", "", 0]) or ["", "", 0])
    fainted = str(_g(mon, "status", "")) == "Fainted" or (
        has_stats and int(current) <= 0)
    return {
        "name": str(_g(mon, "name", "?")),
        "sprite": sprite_key(_g(mon, "name", "") or
                             _g(mon, "default_name", "")),
        "types": list(_g(mon, "type", []) or []),
        # the Pokemon's own rarity band from Data/pokemon.csv -- what the
        # organiser's reward pool is drawn from, and the quickest read on
        # whether one of the opponent's is worth taking
        "tier": str(_g(mon, "tier", "") or ""),
        "ability": list(_g(mon, "ability", []) or []),
        "status": str(_g(mon, "status", "Normal")),
        "hp": max(0, int(current)),
        "max_hp": max(1, int(max_hp)),
        "stats": list(stats) if isinstance(stats, (list, tuple)) else [],
        # base and nominal both: the Pokedex and the compare screen want to
        # show what the species is worth separately from what this individual
        # rolled, and nominal is base + iv
        "base": list(_g(mon, "base_stats", []) or []),
        "nominal": list(_g(mon, "nominal_base_stats", []) or []),
        "iv": list(_g(mon, "iv", []) or []) if isinstance(
            _g(mon, "iv", []), (list, tuple)) else [],
        "total": _g(mon, "total_stats", 0) or 0,
        "total_iv": _g(mon, "total_iv", 0) or 0,
        "modifier": modifier,
        "volatile": {k: v for k, v in volatile.items() if v},
        "moveset": moveset,
        "moves": {m: snap_move(m) for m in moveset if m != "Switching"},
        "disabled": {k: v for k, v in disabled.items() if v > 0},
        "charging": charging,
        "protecting": bool((_g(mon, "protection", [0, 0]) or [0, 0])[0]),
        "fainted": fainted,
        "active": active,
    }


def snap_roster(team):
    """Full detail for every team member, for the standalone team viewer.

    Deliberately strips the in-battle condition. end_battle() resets each
    pokemon.status back to "Normal" but leaves battle_stats[0] sitting at
    whatever it ended on -- so a Pokemon that was knocked out keeps 0 HP on
    record until the next battle_setup() rebuilds its stats. The team
    viewer is a roster reference, not a live battle readout, so reporting
    that as "fainted" was wrong: between rounds nothing is fainted, and
    the number shown had no bearing on the next match.
    """
    out = []
    for mon in (team or []):
        snap = snap_pokemon(mon)
        if snap is None:
            continue
        snap["fainted"] = False
        if snap.get("status") == "Fainted":
            snap["status"] = "Normal"
        out.append(snap)
    return out


def snap_team(team, active_mon=None, in_battle=True):
    """The team as a row of condition pips.

    `in_battle` matters because end_battle() puts every status back to
    "Normal" but leaves battle_stats[0] wherever it ended -- so between
    rounds a Pokemon that was knocked out still reads 0 HP until the next
    battle_setup() rebuilds its stats. Reporting that outside a live battle
    showed last round's casualties as fainted on the new round's screens,
    and had the interface announcing their knockouts all over again.
    """
    out = []
    for mon in (team or []):
        stats = _g(mon, "battle_stats", None)
        has_stats = isinstance(stats, (list, tuple)) and len(stats) > 0 \
            and in_battle
        max_hp = _g(mon, "hp", 0) or 0
        current = stats[0] if has_stats else (max_hp or 1)
        out.append({
            "name": str(_g(mon, "name", "?")),
            "sprite": sprite_key(_g(mon, "name", "")),
            "types": list(_g(mon, "type", []) or []),
            "status": str(_g(mon, "status", "Normal")),
            "hp": max(0, int(current)),
            "max_hp": max(1, int(max_hp or current or 1)),
            "fainted": in_battle and (
                str(_g(mon, "status", "")) == "Fainted"
                or (has_stats and max(0, int(current)) <= 0)),
            "active": mon is active_mon,
        })
    return out


def snap_side(participant):
    if participant is None:
        return {}
    return {
        "nickname": str(_g(participant, "nickname", "?")),
        "strength": _g(participant, "strength", 0),
        "level": str(_g(participant, "level", "")),
        "hazards": {k: v for k, v in (_g(participant, "entry_hazard", {})
                                      or {}).items() if v},
        "buffs": {k: v for k, v in (_g(participant, "in_battle_effects", {})
                                    or {}).items() if v},
    }


def snap_field(battleground):
    if battleground is None:
        return {}
    # Weather counts *up* to WEATHER_EFFECT_TURNS and only while it is
    # artificial -- the arena's own weather never expires. Publishing turns
    # remaining rather than turns elapsed keeps the countdown logic in one
    # place instead of in every consumer.
    artificial = bool(_g(battleground, "artificial_weather", False))
    elapsed = _g(battleground, "weather_turn", 0) or 0
    try:
        from Scripts.Battle.constants import WEATHER_EFFECT_TURNS as limit
    except Exception:
        limit = 6
    return {
        "turn": _g(battleground, "turn", 1),
        "weather": str(_g(battleground, "weather_effect", "Clear")),
        "weather_artificial": artificial,
        "weather_turns": (max(0, limit - int(elapsed)) if artificial
                          else None),
        "field": {k: v for k, v in (_g(battleground, "field_effect", {})
                                    or {}).items() if v},
        "sudden_death": bool(_g(battleground, "sudden_death", False)),
        "auto_battle": bool(_g(battleground, "auto_battle", False)),
    }


def game_stage():
    try:
        from Scripts.Game.game_system import GameSystem
        return _g(GameSystem, "stage", 1)
    except Exception:
        return 1


# ---------------------------------------------------------------------------
# hook installation
# ---------------------------------------------------------------------------
def patch_everywhere(name, original, replacement):
    """Rebind a function in every module that imported it.

    The game uses `from module import *` throughout, so each importing module
    holds its own reference. Patching only the defining module would miss the
    call sites. Identity-checking each attribute keeps this safe.
    """
    count = 0
    for module in list(sys.modules.values()):
        if module is None:
            continue
        try:
            if getattr(module, name, None) is original:
                setattr(module, name, replacement)
                count += 1
        except Exception:
            continue
    return count


def install_hooks(bridge, game_main):
    """Wrap the game functions the interface needs to observe."""
    import Scripts.Battle.ai as battle_ai
    import Scripts.Battle.battle_checklist as checklist
    import Scripts.Battle.battle_cycle as cycle
    import Scripts.Battle.battle_win_condition as win
    import Scripts.Battle.switching as switching
    import Scripts.Game.before_battle as before
    import Scripts.Game.game_procedure as procedure
    import Scripts.Game.start_interface as start
    import Scripts.Art.music as music_mod

    # -- difficulty --------------------------------------------------------
    # Beginner holds every opponent to the simple battle AI. Rather than teach
    # battle_cycle a second rule -- it already picks between the two by
    # rating, and there are three separate call sites -- the smart routine is
    # simply replaced by the simple one everywhere. Both take
    # (battleground, protagonist, ai), so the swap is exact, and it covers the
    # AI-vs-AI simulation path as well as the player's own match. Read once,
    # here, because changing an opponent's brain mid-match would be worse
    # than making the setting take effect on relaunch.
    if bridge.difficulty == "beginner":
        patched = patch_everywhere("smart_ai_select_move",
                                   battle_ai.smart_ai_select_move,
                                   battle_ai.dumb_ai_select_move)
        bridge.publish(difficulty="beginner")
        if not patched:
            bridge.emit(EV_TEXT,
                        "Beginner difficulty could not be applied.\n")

    # -- the Pokedex -------------------------------------------------------
    # Snapshotted once, here, rather than read live: 239 Pokemon, 381 moves
    # and 56 competitors reduced to plain dicts. The interface must never hold
    # a reference into a game object, and this is data the game never changes
    # after load anyway -- so once is exactly right.
    try:
        from Scripts.Data.moves import list_of_moves
        from Scripts.Data.pokemon import list_of_pokemon
        from Scripts.Data.competitors import list_of_competitors as roster
        bridge.publish(codex=codex.build(list_of_pokemon, list_of_moves,
                                        roster, art_for=character_art))
    except Exception:
        # A Pokedex that cannot be built is not a reason to lose the run; the
        # interface simply says it is unavailable.
        bridge.publish(codex=None)

    ctx = {"protagonist": None, "competitor": None,
           "player_team": [], "opponent_team": [], "battleground": None}
    bridge.ctx = ctx

    def refresh(player=None, opponent=None, phase=None, **extra):
        resolved_phase = phase or bridge.state.get("phase", "battle")
        # Condition only means anything while a match is actually running --
        # see snap_team. Outside one, every stale 0 HP left over from the
        # last round is reported as healthy.
        in_battle = resolved_phase in ("battle", "result")
        fields = {
            "phase": resolved_phase,
            "stage": game_stage(),
            "player_side": snap_side(ctx["protagonist"]),
            "opponent_side": snap_side(ctx["competitor"]),
            "field": snap_field(ctx["battleground"]),
        }
        if player is not None:
            fields["player"] = snap_pokemon(player, active=True)
        if opponent is not None:
            fields["opponent"] = snap_pokemon(opponent, active=True)
        protagonist = ctx["protagonist"]
        competitor = ctx["competitor"]
        player_roster = _g(protagonist, "team", ctx["player_team"])
        opponent_roster = _g(competitor, "team", ctx["opponent_team"])
        fields["player_team"] = snap_team(player_roster, player,
                                         in_battle=in_battle)
        fields["opponent_team"] = snap_team(opponent_roster, opponent,
                                           in_battle=in_battle)
        # Your whole roster, benched Pokemon included and in that order --
        # the same order choose_pokemon() offers them in, so a slot number on
        # the reward screen means the same thing in the team viewer. The ones
        # held back from this round live in unused_team until end_battle()
        # folds them home (see team_selection), and leaving them out made the
        # viewer disagree with the picker about how many Pokemon you own.
        benched = list(_g(protagonist, "unused_team", []) or [])
        roster = snap_roster(list(player_roster) + benched)
        for entry in roster[len(roster) - len(benched):] if benched else []:
            entry["benched"] = True
        fields["player_roster"] = roster
        # The opponent's side in the same detail -- but only when you are
        # entitled to see it. Publishing it unconditionally meant their whole
        # team was on display from the moment a match started, which made
        # both scouting and the post-win reward pointless. Two ways to earn
        # it, and no others: win the match and be offered one of their
        # Pokemon, or succeed at the scouting roll in About Opponent.
        if bridge.state.get("opponent_known"):
            fields["opponent_roster"] = snap_roster(opponent_roster)
        else:
            fields["opponent_roster"] = None
        fields.update(extra)
        bridge.publish(**fields)

    bridge.refresh = refresh

    def refresh_before_input():
        """Keep the live battle readout current across repeated prompts.

        Deliberately as narrow as it can be -- just the battlefield flags.
        This runs before *every* question, so anything heavier is felt
        directly as sluggishness: snapshotting the active Pokemon as well
        (let alone the rosters) cost enough to slow the game to a crawl,
        and the flags are all this needs to fix -- they are what told the
        interface whether auto battle was on.
        """
        battleground = ctx.get("battleground")
        if battleground is None:
            return
        field = snap_field(battleground)
        # and only when something actually moved: an extra state event on
        # every single prompt costs the interface a full re-apply each time,
        # which was worth about a third of the game's responsiveness for
        # information that is usually unchanged.
        if field == bridge.state.get("field"):
            return
        bridge.publish(field=field)

    bridge.before_input = refresh_before_input

    def side_of(participant):
        if participant is ctx.get("protagonist"):
            return "player"
        if participant is ctx.get("competitor"):
            return "opponent"
        return None

    bridge.side_of = side_of

    # -- battle start ------------------------------------------------------
    original_setup = cycle.battle_setup

    def battle_setup(protagonist, competitor, player_team, opponent_team,
                     battleground, *a, **kw):
        ctx.update(protagonist=protagonist, competitor=competitor,
                   player_team=player_team, opponent_team=opponent_team,
                   battleground=battleground)
        # publish() merges into one long-lived snapshot, so last battle's
        # result would otherwise ride along in every state update for the
        # rest of the run; clear it as the next battle starts. battle_seq
        # marks this as a distinct match, which is what lets the interface
        # start each round with a clean battle log.
        # Whether their team may be shown is per match. A successful scout
        # last round says nothing about this one, so it resets here -- and
        # before refresh(), which reads it to decide what to publish.
        scouted = getattr(competitor, "scouted", None)
        known = bool(isinstance(scouted, tuple) and scouted[1]
                     and scouted[0] == game_stage())
        bridge.state["opponent_known"] = known
        refresh(player=player_team[0] if player_team else None,
                opponent=opponent_team[0] if opponent_team else None,
                phase="battle", battle_result=None,
                opponent_known=known,
                battle_seq=time.time())
        return original_setup(protagonist, competitor, player_team,
                              opponent_team, battleground, *a, **kw)

    patch_everywhere("battle_setup", original_setup, battle_setup)

    # -- move selection ----------------------------------------------------
    original_select = checklist.select_move

    def select_move(pokemon, target, battleground, *a, **kw):
        ctx["battleground"] = battleground
        ctx["active_player"], ctx["active_opponent"] = pokemon, target
        refresh(player=pokemon, opponent=target, phase="battle")
        bridge.next_input_kind = "move"
        try:
            return original_select(pokemon, target, battleground, *a, **kw)
        finally:
            bridge.next_input_kind = "generic"

    patch_everywhere("select_move", original_select, select_move)

    # -- switching ---------------------------------------------------------
    original_switch = switching.switching_criteria

    def switching_criteria(protagonist, competitor, user_team, opponent_team,
                           battleground, *a, **kw):
        ctx["battleground"] = battleground
        refresh(player=user_team[0] if user_team else None,
                opponent=opponent_team[0] if opponent_team else None,
                phase="battle")
        bridge.next_input_kind = "switch"
        try:
            return original_switch(protagonist, competitor, user_team,
                                   opponent_team, battleground, *a, **kw)
        finally:
            bridge.next_input_kind = "generic"

    patch_everywhere("switching_criteria", original_switch, switching_criteria)

    # -- move resolution: one banner per Pokemon acting this turn -----------
    # move_order_and_execution runs everything about one side's move --
    # the "X used Y" line, damage, status/stat effects, any ability it
    # triggers -- so capturing its whole transcript in one place gives a
    # single clean event per actor per turn instead of trying to reparse
    # fragments of the log after the fact.
    original_move_exec = checklist.move_order_and_execution

    def move_order_and_execution(user_side, target_side, user_team,
                                 target_team, user, target, battleground,
                                 move, target_move, *a, **kw):
        result, text = bridge.capture(
            original_move_exec, user_side, target_side, user_team,
            target_team, user, target, battleground, move, target_move,
            *a, **kw)
        if text.strip():
            bridge.emit_banner("move", text, side=side_of(user_side),
                               actor=_g(user, "name", ""))
        return result

    patch_everywhere("move_order_and_execution", original_move_exec,
                     move_order_and_execution)

    # -- ability triggers that happen outside of a move (switch-in, weather
    #    on entry, end-of-turn ticks) -- anything triggered mid-move is
    #    already part of that move's banner above, so this only fires for
    #    the outermost call.
    def _wrap_ability(module, func_name, kind, trainer=False):
        original = getattr(module, func_name, None)
        if original is None:
            return

        def wrapper(user_side, target_side, user, target, battleground,
                   move="", abilityphase=1, verbose=False, *a, **kw):
            nested = bool(bridge._capture_stack)
            if nested and not trainer:
                # A Pokemon ability firing mid-move is already narrated
                # inside that move's own log entry.
                return original(user_side, target_side, user, target,
                                battleground, move, abilityphase, verbose,
                                *a, **kw)
            # Character abilities are reported even when nested: most of
            # them trigger from inside move resolution (phases 3-7), so
            # skipping nested calls meant the majority never surfaced at
            # all. `nested` lets the interface show the on-field callout
            # without duplicating text the move entry already carries.
            result, text = bridge.capture(
                original, user_side, target_side, user, target, battleground,
                move, abilityphase, verbose, *a, **kw)
            if text.strip():
                # A trainer's character ability belongs to the trainer, not
                # to whichever Pokemon happens to be out, and it was
                # previously indistinguishable from a Pokemon ability in
                # the log. Tag it separately so it can be called out.
                actor = (_g(user_side, "nickname", "") if trainer
                        else _g(user, "name", ""))
                bridge.emit_banner(kind, text, side=side_of(user_side),
                                   actor=actor, nested=nested)
            return result

        patch_everywhere(func_name, original, wrapper)

    import Scripts.Data.abilities as abilities_mod
    import Scripts.Data.character_abilities as char_abilities_mod
    _wrap_ability(abilities_mod, "UseAbility", "ability")
    _wrap_ability(char_abilities_mod, "UseCharacterAbility", "character",
                  trainer=True)

    # -- last round's scorelines ------------------------------------------
    # round_end() announces every one of the 16 results, but only as boxed
    # ASCII art in the log, which scrolls away -- so there was no way to see
    # how the rest of the field did. Rather than parse the box drawing back
    # apart, this records the values as the boxes are built: each is
    # EntryBox(id, "Nick [rating]", points, pokemon_knocked_out), emitted
    # victor-then-loser for each pair.
    import Scripts.Game.single_elimination_bracket as bracket_mod

    original_entrybox = bracket_mod.EntryBox
    box_log = []
    recording = {"on": False}

    def EntryBox(id=" ", name=" ", score=" ", stage=" "):
        if recording["on"]:
            box_log.append((id, name, score, stage))
        return original_entrybox(id, name, score, stage)

    patch_everywhere("EntryBox", original_entrybox, EntryBox)

    def _as_int(value):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    original_round_end = win.round_end

    def round_end(stage, *a, **kw):
        del box_log[:]
        recording["on"] = True
        try:
            result = original_round_end(stage, *a, **kw)
        finally:
            recording["on"] = False
        try:
            you = str(_g(list_of_competitors_ref().get("Protagonist"),
                         "nickname", ""))
            pairs = []
            for i in range(0, len(box_log) - 1, 2):
                match = []
                for _, label, points, score in (box_log[i], box_log[i + 1]):
                    label = ansi_strip(str(label))
                    nickname = label.split(" [")[0].strip()
                    # round_end() formats the label as "Nickname [rating]"
                    # (plus a |titles| crown and an upset marker), so the
                    # rating is already there to be read back -- no second
                    # lookup into the competitor table, which would report
                    # whatever the rating is *now* rather than what it was
                    # for this match.
                    rating = re.search(r"\[(\d+)\]", label)
                    match.append({
                        "nickname": nickname,
                        "strength": int(rating.group(1)) if rating else None,
                        "points": _as_int(points),
                        "score": _as_int(score),
                        "is_player": nickname == you,
                        "upset": "!!" in label,
                    })
                pairs.append(match)
            if pairs:
                # every round is kept, not just the most recent one: by the
                # final round you want to be able to look back over how the
                # whole bracket played out, not only what just happened
                history = [r for r in (bridge.state.get("round_results") or [])
                           if r.get("round") != stage]
                history.append({"round": stage, "pairs": pairs})
                history.sort(key=lambda r: r.get("round") or 0)
                bridge.publish(round_results=history)
        except Exception:
            pass
        return result

    patch_everywhere("round_end", original_round_end, round_end)

    # -- round matchups: captured once per round for the bracket screen ----
    original_round_begin = procedure.round_begin

    def round_begin(*a, **kw):
        result = original_round_begin(*a, **kw)
        try:
            from Scripts.Game.game_system import GameSystem
            from Scripts.Data.competitors import list_of_competitors
            pairs = {}
            for name in GameSystem.participants:
                comp = list_of_competitors[name]
                pairs.setdefault(comp.match_id, []).append({
                    "nickname": comp.nickname,
                    "strength": comp.strength,
                    "color": _g(comp, "color", ""),
                    "championship": _g(comp, "championship", 0),
                    # rounds already won (stage counts from 1) and the
                    # running tie-break score, so a matchup screen can show
                    # how each side is actually doing
                    "wins": max(0, _g(comp, "stage", 1) - 1),
                    "score": _g(comp, "score", 0),
                    "is_player": name == "Protagonist",
                })
            bridge.publish(bracket={"round": game_stage(),
                                    "pairs": list(pairs.values())})
        except Exception:
            pass
        return result

    patch_everywhere("round_begin", original_round_begin, round_begin)

    # -- tournament end: leaderboard + opponent journey + credits ----------
    original_scoreboard = procedure.scoreboard

    def scoreboard(*a, **kw):
        result = original_scoreboard(*a, **kw)
        try:
            from Scripts.Game.game_system import GameSystem
            from Scripts.Data.competitors import list_of_competitors
            rows = []
            for name in GameSystem.participants:
                comp = list_of_competitors[name]
                rows.append({
                    "nickname": comp.nickname,
                    "strength": comp.strength,
                    "stage": _g(comp, "stage", 1) - 1,
                    "opponent_score": _g(comp, "opponent_score", 0),
                    "score": _g(comp, "score", 0),
                    "championship": _g(comp, "championship", 0),
                    "is_player": name == "Protagonist",
                })
            # rounds won first, then the opponent-strength tiebreak, then
            # Pokemon knocked out -- the order the tournament itself ranks by
            rows.sort(key=lambda r: (r["stage"], r["opponent_score"],
                                     r["score"]), reverse=True)
            for i, row in enumerate(rows):
                row["rank"] = i + 1
            champion = _g(list_of_competitors.get("Protagonist"),
                         "stage", 1) == 6
            bridge.publish(phase="leaderboard", leaderboard=rows,
                          champion=champion)
        except Exception:
            pass
        return result

    patch_everywhere("scoreboard", original_scoreboard, scoreboard)

    original_elo = procedure.elo_rating

    def elo_rating(*a, **kw):
        # elo_rating() is what applies this run's rating change, so the only
        # way to report the swing is to read the rating either side of it.
        before = None
        try:
            before = _g(list_of_competitors_ref()["Protagonist"], "strength",
                        None)
        except Exception:
            pass
        result, text = bridge.capture(original_elo, *a, **kw)
        try:
            protagonist = list_of_competitors_ref()["Protagonist"]
            # elo_rating() prints its own per-match figure as
            # "Nickname: Win [+12]". Reading those back beats recomputing the
            # formula here, which would silently drift the day the engine's
            # rating maths is retuned.
            per_match = {}
            order = []
            for line in ansi_strip(text).splitlines():
                found = ELO_LINE_RE.match(line.strip())
                if found:
                    delta = int(found.group("value"))
                    if found.group("sign") == "-":
                        delta = -delta
                    per_match.setdefault(found.group("name").strip(),
                                         []).append(delta)
                    order.append(delta)

            journey = []
            for idx, opponent in enumerate(_g(protagonist, "opponent", [])
                                           or []):
                won = protagonist.win_order[idx] == 1
                deltas = per_match.get(opponent.nickname)
                if deltas:
                    change = deltas.pop(0)
                elif idx < len(order):
                    change = order[idx]      # fall back to print order
                else:
                    change = None
                journey.append({"nickname": opponent.nickname, "won": won,
                                "strength": opponent.strength,
                                "rating_change": change})
            after = _g(protagonist, "strength", 0)
            bridge.publish(phase="leaderboard", journey=journey,
                          rating=after,
                          rating_before=before,
                          rating_change=(None if before is None
                                        else after - before))
        except Exception:
            pass
        return result

    def list_of_competitors_ref():
        from Scripts.Data.competitors import list_of_competitors
        return list_of_competitors

    patch_everywhere("elo_rating", original_elo, elo_rating)

    # -- end of battle -----------------------------------------------------
    original_check = win.check_win_or_lose

    def check_win_or_lose(protagonist, competitor, player_team, opponent_team,
                          battleground, *a, **kw):
        # This one call resolves the entire end of a battle without ever
        # handing control back: it announces the result, then choose_pokemon()
        # asks the player to pick their reward, then end_battle() resets
        # every pokemon.status to "Normal". So a snapshot taken *after* it
        # returns can never show the knockout -- the fainted flags are gone
        # and the reward prompt has already been answered. Right here,
        # before the original runs, is the only moment the final fainted
        # state exists, so that is where the result is published.
        def wiped(team):
            return bool(team) and all(
                _g(p, "status", "") == "Fainted" for p in team)

        player_wiped, opponent_wiped = wiped(player_team), wiped(opponent_team)
        if player_wiped or opponent_wiped:
            if player_wiped and opponent_wiped:
                # same tie-break the engine itself applies
                won = _g(protagonist, "strength", 0) > _g(competitor,
                                                          "strength", 0)
            else:
                won = opponent_wiped
            refresh(player=player_team[0] if player_team else None,
                   opponent=opponent_team[0] if opponent_team else None,
                   phase="result",
                   battle_result={
                       "won": bool(won),
                       "you": str(_g(protagonist, "nickname", "You")),
                       "opponent": str(_g(competitor, "nickname",
                                          "Your opponent")),
                       "seq": time.time(),
                   })
        return original_check(protagonist, competitor, player_team,
                             opponent_team, battleground, *a, **kw)

    patch_everywhere("check_win_or_lose", original_check, check_win_or_lose)

    # -- pre-battle menu ---------------------------------------------------
    original_before = before.before_battle_option

    def before_battle_option(protagonist, opponent, *a, **kw):
        ctx.update(protagonist=protagonist, competitor=opponent)
        # A new matchup, so whatever you were entitled to see about the last
        # opponent is void. This has to happen here rather than in
        # battle_setup: the pre-battle menu is where the team viewer is
        # reachable, and until this point the flag was still carrying last
        # round's win -- you could open Your Team before the match and read
        # the new opponent's side.
        scouted = getattr(opponent, "scouted", None)
        known = bool(isinstance(scouted, tuple)
                     and scouted[0] == game_stage() and scouted[1])
        bridge.state["opponent_known"] = known
        refresh(phase="prebattle", opponent_known=known)
        return original_before(protagonist, opponent, *a, **kw)

    patch_everywhere("before_battle_option", original_before,
                     before_battle_option)

    # -- the lore, lifted out once ----------------------------------------
    # backstory() and tutorial() only print (and pause for a keypress), and
    # the engine shows them exactly once, buried inside the new-game flow --
    # so a returning player could never read them again. Captured here so
    # the interface can offer them from the title screen at any time.
    def capture_lore():
        real_input = builtins.input
        builtins.input = lambda prompt="": ""      # they only pause
        try:
            _, backstory = bridge.capture_quiet(start.backstory)
            _, tutorial = bridge.capture_quiet(start.tutorial)
        finally:
            builtins.input = real_input
        bridge.publish(lore={
            "backstory": ansi_strip(backstory).strip(),
            "tutorial": ansi_strip(tutorial).strip(),
        })

    try:
        capture_lore()
    except Exception:
        pass          # never let a lore hiccup stop the game from starting

    # -- the first-timer walkthrough ---------------------------------------
    # backstory() and tutorial() are what a new player is shown, and they
    # print straight into the log where the artwork versions of the same
    # pages cannot be seen at all. Ping the interface to open its reader
    # instead, and swallow the printing -- the reader is the walkthrough now.
    for func_name in ("backstory", "tutorial"):
        original_page = getattr(start, func_name, None)
        if original_page is None:
            continue

        def make_page(original_page=original_page, func_name=func_name):
            def wrapper(*a, **kw):
                bridge.capture_quiet(original_page, *a, **kw)
                if func_name == "backstory":
                    bridge.publish(show_story=time.time())
                return None
            return wrapper

        patch_everywhere(func_name, original_page, make_page())

    # -- title screen ------------------------------------------------------
    original_main_screen = start.main_screen

    def main_screen(*a, **kw):
        bridge.publish(phase="menu", stage=game_stage())
        return original_main_screen(*a, **kw)

    patch_everywhere("main_screen", original_main_screen, main_screen)

    # -- the main menu's HISTORY screen ------------------------------------
    # Every input() inside history_screen() is tagged "career", which is the
    # interface's cue to let its own window drive the screen: it answers the
    # engine's two yes/no questions itself and takes the competitor number
    # from a click instead of a button grid. See CAREER_PROMPTS.
    original_screen = start.history_screen

    def history_screen(protagonist, *a, **kw):
        previous = bridge.next_input_kind
        bridge.next_input_kind = "career"
        try:
            return original_screen(protagonist, *a, **kw)
        finally:
            bridge.next_input_kind = previous
            bridge.publish(career_open=False)

    patch_everywhere("history_screen", original_screen, history_screen)

    original_list = start.participant_list

    def participant_list(*a, **kw):
        result, _raw = bridge.capture_quiet(original_list, *a, **kw)
        roster = list_of_competitors_ref()
        bridge.publish(career_roster=[
            {"index": number, "name": name,
             "nickname": str(_g(roster.get(name), "nickname", name)),
             "tier": str(_g(roster.get(name), "level", "") or ""),
             "rating": _g(roster.get(name), "strength", 0),
             "is_player": bool(_g(roster.get(name), "main", False))}
            for number, name in sorted((result or {}).items())],
            career_open=True)
        return result

    patch_everywhere("participant_list", original_list, participant_list)

    def nickname_of(name):
        """A competitor's display name, or the raw key if the roster has been
        renamed since the save was written."""
        comp = list_of_competitors_ref().get(name)
        return str(_g(comp, "nickname", name) if comp is not None else name)

    def describe(op):
        """Their write-up. The player's has a {} in it for the title count."""
        text = str(_g(op, "desc", "") or "")
        if _g(op, "main", False):
            try:
                return text.format(10 + len(_g(op, "history", {}) or {}))
            except (IndexError, KeyError, ValueError):
                pass          # a write-up edited to drop the placeholder
        return text


    # Three separate hooks because the engine prints it in three passes: the
    # roll of champions when you enter, one competitor's career when you pick
    # them, and their record against everybody on a second confirmation. All
    # three are captured quietly and published instead: a career is not
    # something to read as a hundred lines of scrollback.
    original_roll = start.champion_roll

    def champion_roll(protagonist, *a, **kw):
        result, _raw = bridge.capture_quiet(original_roll, protagonist,
                                           *a, **kw)
        # career_open goes up here, at the very start of the screen, not with
        # the roster below. The interface only answers this screen's prompts
        # while its window is open, and the roster is not published until the
        # first of those prompts has been answered -- so waiting for it meant
        # the window waited for the roster and the roster waited for the
        # window.
        bridge.publish(career_open=True, career_champions=[
            {"run": int(run) + 1, "champion": str(entry[0]),
             "rank": entry[1] if len(entry) > 1 else None}
            for run, entry in sorted((_g(protagonist, "history", {}) or {})
                                     .items())])
        return result

    patch_everywhere("champion_roll", original_roll, champion_roll)

    original_report = start.competitor_report

    def competitor_report(op, *a, **kw):
        result, _raw = bridge.capture_quiet(original_report, op, *a, **kw)
        wins, losses = start.career_totals(op)
        played = wins + losses
        history = _g(op, "opponent_history", {}) or {}
        # the same top five the engine calls "Favorite Opponent": most played,
        # then most beaten
        top = sorted(history.items(), key=lambda x: (x[1][0] + x[1][1],
                                                     x[1][0]), reverse=True)
        bridge.publish(career_report={
            "name": _g(op, "name", ""),
            "nickname": op.nickname,
            "tier": str(_g(op, "level", "") or ""),
            "rating": _g(op, "strength", 0),
            "is_player": bool(_g(op, "main", False)),
            "description": describe(op),
            "participation": _g(op, "participation", 0),
            "championship": _g(op, "championship", 0),
            "wins": wins,
            "losses": losses,
            "win_rate": round(100.0 * wins / played, 2) if played else None,
            # history is {run: (champion of that run, rank, score)}, so each
            # run can say who won it as well as where they came
            "runs": [{"run": int(run) + 1,
                      "rank": entry[1] if len(entry) > 1 else None,
                      "champion": str(entry[0]) if entry else ""}
                     for run, entry in sorted((_g(op, "history", {}) or {})
                                              .items())],
            "most_played": [
                {"nickname": nickname_of(name), "wins": record[0],
                 "losses": record[1]}
                for name, record in top[:5] if record[0] or record[1]],
            "art": character_art(op),
            "seq": time.time(),
        })
        return result

    patch_everywhere("competitor_report", original_report, competitor_report)

    original_individual = start.individual_records

    def individual_records(op, *a, **kw):
        result, _raw = bridge.capture_quiet(original_individual, op, *a, **kw)
        roster = list_of_competitors_ref()
        rows = []
        for name, record in (_g(op, "opponent_history", {}) or {}).items():
            if name == _g(op, "name", None):
                continue                       # nobody plays themselves
            played = record[0] + record[1]
            if not played:
                continue                       # never met: not a row worth
            rows.append({"nickname": nickname_of(name), "wins": record[0],
                         "losses": record[1],
                         "rating": _g(roster.get(name), "strength", 0),
                         "tier": str(_g(roster.get(name), "level", "") or ""),
                         "win_rate": round(100.0 * record[0] / played)})
        # By the opponent's rating, hardest first. Most-played first put the
        # people you happen to keep drawing at the top, which says more about
        # the bracket than about the record -- rating order reads as "how far
        # up the field have they actually beaten anyone".
        rows.sort(key=lambda row: (-row["rating"], row["nickname"]))
        bridge.publish(career_records={"nickname": op.nickname, "rows": rows,
                                       "seq": time.time()})
        return result

    patch_everywhere("individual_records", original_individual,
                     individual_records)

    # -- team management screens -------------------------------------------
    # team_selection and save_game both drive a repeated-prompt loop (pick
    # one Pokemon at a time until a count is satisfied) -- tagging them
    # distinctly lets the interface show a real multi-select screen instead
    # of one plain button prompt per pick, the same way "move"/"switch" get
    # their own screens.
    for func_name, module, kind in (
            ("team_selection", before, "team_trim"),
            ("save_game", procedure, "team_keep"),
            # the post-battle reward: take one off the opponent, swap one of
            # yours for one of theirs, or accept the organiser's. Tagged so
            # the interface can offer the two rosters for comparison while
            # the question is on screen.
            ("choose_pokemon", win, "reward")):
        original = getattr(module, func_name, None)
        if original is None:
            continue

        def make(original=original, kind=kind):
            def wrapper(*a, **kw):
                # refresh(), not publish(): publish merges into one long-lived
                # snapshot, so setting just the phase left the finished
                # battle's team condition sitting in state and the interface
                # drew last round's casualties on this round's screens.
                refresh(phase="manage")
                previous = bridge.next_input_kind
                bridge.next_input_kind = kind
                try:
                    return original(*a, **kw)
                finally:
                    bridge.next_input_kind = previous
            return wrapper

        patch_everywhere(func_name, original, make())

    # -- what you walked away with ----------------------------------------
    # choose_pokemon() hands out the end-of-battle reward: one taken from the
    # opponent, a random one from the organiser, a swap, or a consolation
    # Pokemon after a loss. Two of those four paths print the name and two
    # don't, and all of it lands in the raw log, so the usual way to find out
    # what you'd been given was to go and look at your team. Diffing the team
    # around the call catches every path without relying on that text.
    original_choose = win.choose_pokemon

    def choose_pokemon(protagonist, opponent, battleground, *a, **kw):
        def names(team):
            return [str(_g(mon, "name", "?")) for mon in (team or [])]

        # Won the round, so you are about to be offered one of their Pokemon
        # -- you can hardly choose one without seeing them. This is the other
        # way to earn sight of their team (see refresh).
        if _g(protagonist, "stage", 0) > _g(opponent, "stage", 0)                 and not _g(battleground, "verbose", False):
            bridge.state["opponent_known"] = True
            bridge.publish(opponent_known=True,
                           opponent_roster=snap_roster(_g(opponent, "team",
                                                          [])))
        was = names(_g(protagonist, "team", []))
        result = original_choose(protagonist, opponent, battleground, *a, **kw)
        now = names(_g(protagonist, "team", []))
        gained = list((collections.Counter(now)
                       - collections.Counter(was)).elements())
        lost = list((collections.Counter(was)
                     - collections.Counter(now)).elements())
        if gained or lost:
            bridge.publish(reward={"gained": gained, "lost": lost,
                                   "seq": time.time()})
        return result

    patch_everywhere("choose_pokemon", original_choose, choose_pokemon)

    # -- opponent info and match history: structured, not printed paragraphs
    original_about = before.about_opponent

    #: the sentence about_opponent() prints when the scouting roll fails --
    #: failing is a real game mechanic (the chance is
    #: your_rating / (your_rating + theirs), multiplied by Illuminate or
    #: Pressure if you have them), so the interface has to be able to say
    #: "you learned nothing" rather than just show an empty report.
    SCOUT_FAILED = "fail to obtain any useful information"
    #: where about_opponent()'s narration starts; everything before it is
    #: the tier/description/strategy header, which is already shown as its
    #: own fields and would otherwise appear twice.
    SCOUT_NARRATION = "Before the match begins"

    def about_opponent(protagonist, opponent, *a, **kw):
        result, raw = bridge.capture(original_about, protagonist, opponent,
                                     *a, **kw)
        # capture() collects what print() was handed, escape codes and all;
        # forwarding that verbatim is what put literal "[95m[1m" sequences
        # in the scouting report.
        text = ansi_strip(raw)
        start = text.find(SCOUT_NARRATION)
        if start != -1:
            text = text[start:]
        # about_opponent() prints the strategy at the end of a successful
        # scout, and the report shows it in its own section -- so leaving it
        # in the narration too printed the whole ability write-up twice.
        strategy = ansi_strip(str(_g(opponent, "strategy", ""))).strip()
        if strategy and strategy in text:
            text = text.replace(strategy, "").rstrip()
        # The roll is taken once per round and kept on the competitor, so
        # reading it back here is what tells the interface whether their team
        # may be shown -- and it stays consistent however many times About
        # Opponent is opened. reveal_ability is no longer consulted: the
        # strategy is part of what a successful scout buys.
        scouted = SCOUT_FAILED not in text
        # Publish the roster here too, not just the flag. refresh() is what
        # normally fills opponent_roster in, and nothing calls it between
        # scouting and the player opening Your Team -- so a successful scout
        # set the flag and still showed an empty opponent tab.
        bridge.state["opponent_known"] = scouted
        if scouted:
            bridge.publish(opponent_roster=snap_roster(_g(opponent, "team",
                                                          [])))
        bridge.publish(opponent_info={
            "nickname": opponent.nickname,
            "tier": str(_g(opponent, "level", "")),
            "description": ansi_strip(str(_g(opponent, "desc", ""))).strip(),
            "art": character_art(opponent),
            "strategy_revealed": scouted,
            "strategy": ansi_strip(str(_g(opponent, "strategy", ""))).strip(),
            "scouted_text": text.strip(),
            "scout_failed": not scouted,
            "seq": time.time(),
        }, opponent_known=scouted)
        return result

    patch_everywhere("about_opponent", original_about, about_opponent)

    original_history = before.check_history

    def check_history(protagonist, opponent, *a, **kw):
        # Just the head-to-head, matching what the engine now prints: the
        # scoreline of every previous meeting against this opponent. The two
        # trainers' whole tournament journeys used to be here too, which is
        # not what you want to read seconds before a match -- and is still
        # on the main menu's HISTORY screen.
        wins, losses = before.head_to_head(protagonist, opponent)
        scores = (_g(protagonist, "opponent_scores", {}) or {}).get(
            _g(opponent, "name", "")) or []
        bridge.publish(history_info={
            "you": protagonist.nickname,
            "opponent": opponent.nickname,
            "wins": wins,
            "losses": losses,
            "meetings": [[int(pair[0]), int(pair[1])]
                         for pair in scores if len(pair) >= 2],
        })
        # capture_quiet, not a plain call: the engine still prints the same
        # record for the terminal version, and letting that land in the log
        # made the log look like the only place it appeared. The window above
        # is the answer to the question; the log is not meant to be read
        # during play.
        result, _raw = bridge.capture_quiet(original_history, protagonist,
                                           opponent, *a, **kw)
        return result

    patch_everywhere("check_history", original_history, check_history)

    # -- "View My Pokemon" from the pre-battle menu: the terminal version
    #    just prints a paragraph per Pokemon, which in the GUI lands as
    #    unstyled text in the Log tab and looks like the button did
    #    nothing. The interface already has a proper team viewer (the
    #    "Your Team" roster dialog, fed by player_roster on every state
    #    update) -- this just pings the GUI to open that same dialog
    #    instead of teaching it a second team-detail view.
    original_view_pokemon = before.view_pokemon

    def view_pokemon(protagonist, opponent, *a, **kw):
        result = original_view_pokemon(protagonist, opponent, *a, **kw)
        bridge.publish(view_pokemon_requested=time.time())
        return result

    patch_everywhere("view_pokemon", original_view_pokemon, view_pokemon)

    # -- restart: signal the GUI instead of exec'ing over the process ------
    original_restart = procedure.restart

    def restart(*a, **kw):
        raise _RestartRequest()

    patch_everywhere("restart", original_restart, restart)

    # -- audio: never let a missing file or device kill the run -----------
    original_music, original_sound = music_mod.music, music_mod.sound

    def safe_music(*, audio, loop):
        try:
            original_music(audio=audio, loop=loop)
        except Exception:
            pass

    def safe_sound(*, audio):
        try:
            original_sound(audio=audio)
        except Exception:
            pass

    patch_everywhere("music", original_music, safe_music)
    patch_everywhere("sound", original_sound, safe_sound)
