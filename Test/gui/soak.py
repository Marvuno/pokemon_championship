"""A long, thorough run: whole careers end to end, every window opened, every
button in them pressed, and the game's own rules checked while it plays.

playthrough.py answers prompts and watches for exceptions and stray windows.
This goes further in three ways:

  * it plays a career through to its end, leaderboard and rating swing
    included. One process is one career on purpose -- "Play Again" starts a
    detached process so the finished run's module globals cannot leak into
    the next one -- so several careers means running this several times,
    which `--repeat` in the runner below does;
  * it opens every window the player can open and presses every button
    inside, which is the only way to find a screen that raises when it is
    opened at the wrong moment;
  * it checks the game's own invariants on every tick -- team sizes, HP
    inside bounds, ratings above zero, a team shown before it was scouted --
    so a logic flaw is caught where it happens rather than read out of a
    transcript afterwards.

    python Test/gui/soak.py <root> <out> [ignored] [seconds]

Nothing reaches a desktop and nothing plays a sound: offscreen Qt, and
POKEMON_MUTE for the audio.
"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

ROOT, OUT = sys.argv[1], sys.argv[2]
CAREERS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
SECONDS = int(sys.argv[4]) if len(sys.argv) > 4 else 540
sys.path.insert(0, ROOT)
os.chdir(ROOT)

sys.path.insert(0, OUT)
import saveguard                                              # noqa: E402
saveguard.install(ROOT, OUT, tag="soak")

from PySide6.QtCore import QTimer                             # noqa: E402
from PySide6.QtWidgets import QApplication       # noqa: E402

from GUI import prompt_parser as P                            # noqa: E402
from GUI_qt.main_window import MainWindow, BATTLE_PHASES      # noqa: E402

app = QApplication.instance() or QApplication([])

errors = []
problems = {}


def note(what, detail):
    """Record a rule the game broke, once per distinct kind."""
    problems.setdefault(what, detail)


def excepthook(*exc):
    errors.append("".join(traceback.format_exception(*exc)))


sys.excepthook = excepthook

w = MainWindow(ROOT)
w.show()
_orig_error = w._show_error
w._show_error = lambda payload: (errors.append("EV_ERROR: %s" % payload),
                                 _orig_error(payload))

ALLOWED_WINDOWS = {
    "MainWindow", "RosterDialog", "OpponentInfoDialog", "SettingsDialog",
    "HistoryDialog", "CareerDialog", "StandingsDialog", "StoryDialog",
    "CreditsDialog", "CompareDialog", "ArtLightbox", "PokedexDialog",
    "QMenu", "QToolTip", "QComboBoxPrivateContainer",
}

#: buttons a player presses on purpose, and a crash-hunting sweep must not:
#: they end the run, throw away data, or answer a prompt the harness is about
#: to answer itself.
DANGEROUS = ("quit", "exit", "delete", "erase", "new game", "save and",
             "restart", "abandon", "give up", "confirm selection",
             "keep all", "proceed", "continue",
             # "Play Again" starts a real detached game process -- a sweep
             # pressing it would leave stray games running on the machine
             "play again")

state = {"n": 0, "idle": 0, "careers": 0, "battles": set(), "swept": {},
         "buttons": 0, "strays": {}, "seq": [], "done": False,
         "opened": set(), "sweeps": 0}


def check_strays():
    for widget in app.topLevelWidgets():
        if not widget.isVisible():
            continue
        name = type(widget).__name__
        if name in ALLOWED_WINDOWS:
            continue
        mark = "%s(%r) %dx%d" % (name, widget.windowTitle(),
                                 widget.width(), widget.height())
        state["strays"].setdefault(mark, (state["n"],
                                          (w.game_state or {}).get("phase")))


def check_rules():
    """The game's own invariants, sampled on every tick."""
    game = w.game_state or {}

    for side in ("player_roster", "opponent_roster"):
        roster = game.get(side) or []
        if len(roster) > 6:
            note("%s larger than six" % side, "%d entries" % len(roster))
        for mon in roster:
            hp, most = mon.get("hp"), mon.get("max_hp")
            if hp is None or not most:
                continue
            if hp < 0:
                note("HP below zero", "%s at %s" % (mon.get("name"), hp))
            if hp > most:
                note("HP above maximum",
                     "%s at %s of %s" % (mon.get("name"), hp, most))

    for who in ("player", "opponent"):
        mon = game.get(who) or {}
        hp, most = mon.get("hp"), mon.get("max_hp")
        if hp is not None and most:
            if hp < 0:
                note("active HP below zero", "%s at %s" % (who, hp))
            if hp > most:
                note("active HP above maximum",
                     "%s at %s of %s" % (who, hp, most))

    rating = game.get("rating")
    if isinstance(rating, (int, float)) and rating < 1:
        note("rating fell below one", str(rating))

    if game.get("phase") == "prebattle":
        if not game.get("opponent_known") and (game.get("opponent_roster")
                                               or []):
            note("opponent team shown before it was scouted",
                 "%d entries" % len(game.get("opponent_roster") or []))


def clickables(widget):
    """Everything inside this widget a player can press.

    Two false starts worth recording, because both reported a clean sweep
    over nothing:

    * `findChildren(QPushButton)` found almost nothing. The game's own
      controls are `ActionButton(RoundedPanel)`, `Chip(QLabel)` and
      `_ClickableLabel(QLabel)` -- none of them buttons as Qt counts them.
    * duck-typing on a callable `.click()` was not much better: a QLabel
      subclass that handles `mousePressEvent` has no `click()` to call. It
      has to be *clicked*, with a real mouse event.

    So: anything that is a Qt button, or exposes a `clicked` signal, or
    overrides mouse handling to act like a control.
    """
    from PySide6.QtWidgets import QAbstractButton, QWidget
    out = []
    for child in widget.findChildren(QWidget):
        if not child.isVisible() or not child.isEnabled():
            continue
        if isinstance(child, QAbstractButton) or hasattr(child, "clicked"):
            out.append(child)
        elif type(child).__name__ in ("ActionButton", "Chip", "_PickChip",
                                      "_ClickableLabel", "_ClickableArt",
                                      "_RosterRow", "_StatRow", "MoveCard",
                                      "CombatantCard", "ScoutCard"):
            out.append(child)
    return out


def press(widget):
    """Press it the way a mouse would, whatever kind of widget it is."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    if callable(getattr(widget, "click", None)):
        widget.click()
        return
    QTest.mouseClick(widget, Qt.LeftButton)


def label_of(widget):
    """What the control says.

    `ActionButton` is the game's own button and is not a QLabel, so it has
    no `text()` -- it carries a `title` attribute for exactly this. Without
    it the DANGEROUS list below matched none of the game's real buttons.
    """
    title = getattr(widget, "title", None)
    if isinstance(title, str):
        return title
    text = getattr(widget, "text", None)
    return (text() if callable(text) else "") or type(widget).__name__


def open_settings_without_blocking():
    """The settings window, built exactly as the game builds it, shown
    non-modally so the harness keeps ticking."""
    from GUI_qt.panels import SettingsDialog
    from GUI_qt import settings as settings_mod
    dialog = SettingsDialog(w.fonts, w.difficulty, w.volume, w)
    dialog.on_difficulty_change = settings_mod.set_difficulty
    dialog.on_volume_change = w._set_volume
    dialog.show()


def sweep_windows():
    """Open each window the player can open, press what is inside, close it.

    Run only at a prompt, so the engine is waiting and nothing is mid-turn.
    """
    state["sweeps"] += 1
    openers = [
        ("roster-player", lambda: w.roster_dialog.show_side("player")),
        ("roster-opponent", lambda: w.roster_dialog.show_side("opponent")),
        ("standings", w._open_standings),
        # _open_settings ends in dialog.exec(), which is modal -- it spins its
        # own event loop and does not come back until the dialog closes, so
        # calling it from this timer wedged the whole harness. The dialog is
        # built and shown the same way, without the blocking call.
        ("settings", open_settings_without_blocking),
        ("history", w.history_dialog.show),
        ("career", w.career_dialog.show),
        ("story", w._open_story),
        ("credits", w._open_credits),
        ("pokedex", w._open_pokedex),
    ]
    for name, open_it in openers:
        try:
            open_it()
        except Exception:
            errors.append("opening %s:\n%s" % (name, traceback.format_exc()))
            continue
        state["opened"].add(name)
        # a freshly shown dialog has not laid itself out yet, so its children
        # are not visible and a sweep over them finds nothing at all
        app.processEvents()
        pressed = 0
        for widget in app.topLevelWidgets():
            if (not widget.isVisible()
                    or type(widget).__name__ == "MainWindow"):
                continue
            for button in clickables(widget):
                label = label_of(button).strip().lower()
                if any(bad in label for bad in DANGEROUS):
                    continue
                try:
                    press(button)
                    pressed += 1
                    app.processEvents()
                except Exception:
                    errors.append("clicking %r (%s) in %s:\n%s"
                                  % (label, type(button).__name__, name,
                                     traceback.format_exc()))
        state["buttons"] += pressed
        state["swept"][name] = state["swept"].get(name, 0) + pressed
        for widget in app.topLevelWidgets():
            if (widget.isVisible()
                    and type(widget).__name__ != "MainWindow"):
                try:
                    widget.close()
                except Exception:
                    errors.append("closing %s:\n%s"
                                  % (name, traceback.format_exc()))
        check_strays()


def answer_for(prompt, request):
    question = ((prompt.question or "") + " " + (request.prompt or "")).lower()
    if prompt.mode == P.MODE_TEXT:
        return "Soak%d" % state["careers"] if "name" in question else "1"
    if prompt.mode == P.MODE_CONTINUE:
        return ""
    if prompt.mode == P.MODE_CONFIRM:
        return "Y"
    if request.kind == "reward":
        return "0"
    if not prompt.choices:
        return ""
    for choice in prompt.choices:
        if "new game" in (choice.label or "").lower():
            state["careers"] += 1
            return choice.value
    unwanted = ("quit", "exit", "back", "cancel")
    good = [c for c in prompt.choices
            if not any(bad in (c.label or "").lower() for bad in unwanted)]
    pool = good or prompt.choices
    return pool[state["n"] % len(pool)].value


def tick():
    state["n"] += 1
    check_strays()
    check_rules()

    if (w.game_state or {}).get("phase") in BATTLE_PHASES:
        state["battles"].add((w.game_state or {}).get("battle_seq"))

    if w._gated:
        if hasattr(w, "_end_result_gate"):
            w._end_result_gate()
        return

    request = w.request
    if request is None:
        state["idle"] += 1
        if state["idle"] > 600:
            return finish("idle")
        return
    state["idle"] = 0

    if state.get("pending") is not request:
        state["pending"] = request
        return

    # sweep once the game is actually running, then periodically
    if (not state["swept"] and state["battles"]) or state["n"] % 900 == 0:
        return sweep_windows()

    if request.kind == "reward" and w.compare_dialog is not None:
        try:
            w.compare_dialog._on_proceed()
        except Exception:
            errors.append(traceback.format_exc())
        return
    if request.kind == "team_keep":
        for button in clickables(w):
            if label_of(button) in ("Keep All", "Confirm selection"):
                press(button)
                return

    try:
        prompt = w.memory.parse(request.prompt, request.recent)
        value = answer_for(prompt, request)
        state["seq"].append(
            "%s[%s] %r -> %r" % (request.kind, prompt.mode,
                                 (prompt.question or request.prompt
                                  or "")[:60], value))
        w._answer(value)
    except Exception:
        errors.append(traceback.format_exc())
        return finish("exception")

    if state["careers"] > CAREERS:
        return finish("played %d careers" % CAREERS)


def finish(why):
    if state["done"]:
        return
    state["done"] = True
    report = [
        "stopped: %s after %d ticks" % (why, state["n"]),
        "careers started : %d" % state["careers"],
        "battles seen    : %d" % len({b for b in state["battles"]
                                      if b is not None}),
        "window sweeps   : %d" % state["sweeps"],
        "windows opened  : %s" % ", ".join(sorted(state["opened"])),
        "buttons pressed : %d" % state["buttons"],
        "  per window    : %s" % state["swept"],
        "stray windows   : %d" % len(state["strays"]),
        "rule breaks     : %d" % len(problems),
        "exceptions      : %d" % len(errors),
    ]
    for what, detail in problems.items():
        report.append("   BROKE: %s -- %s" % (what, detail))
    for mark, (n, phase) in state["strays"].items():
        report.append("   STRAY: %s at tick %d, phase %s" % (mark, n, phase))
    text = "\n".join(report + ["", "-- last prompts --"] + state["seq"][-40:]
                     + ["", "-- exceptions --"] + errors)
    with open(os.path.join(OUT, "soak.txt"), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    print("\n".join(report), flush=True)

    trouble = []
    if errors:
        trouble.append("%d exception(s)" % len(errors))
    if state["strays"]:
        trouble.append("%d stray window(s)" % len(state["strays"]))
    if problems:
        trouble.append("%d broken rule(s)" % len(problems))
    if not {b for b in state["battles"] if b is not None}:
        trouble.append("no battles reached")
    if state["sweeps"] < 1:
        trouble.append("never swept the windows")
    if len(state["opened"]) < 9:
        trouble.append("only %d of 9 windows opened" % len(state["opened"]))
    global FAILED
    FAILED = bool(trouble)
    print("", flush=True)
    print("ALL PASS" if not trouble else "FAILURES: " + ", ".join(trouble),
          flush=True)
    for entry in errors[:4]:
        print(entry, flush=True)
    app.quit()


FAILED = False
timer = QTimer()
timer.timeout.connect(tick)
timer.start(10)
QTimer.singleShot(SECONDS * 1000, lambda: finish("wall clock"))
app.exec()
sys.exit(1 if FAILED else 0)
