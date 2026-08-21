"""Headless playthrough: start a new game and answer every prompt, watching
for exceptions, clipped screens and Field-log / feed-flush behaviour.

Answers are chosen from the parsed prompt, so this follows the real game
flow rather than blind-clicking buttons.
"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT, OUT, NAME = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# --- keep the live save out of harm's way ----------------------------------
# This harness plays real games, and the engine saves into the project folder
# with no way to redirect it. See saveguard.py: it snapshots both save files
# before Qt starts and puts them back on the way out, whatever happens.
sys.path.insert(0, OUT)
import saveguard                                              # noqa: E402
saveguard.install(ROOT, OUT, tag=os.path.splitext(
    os.path.basename(__file__))[0])

from PySide6.QtCore import QTimer                       # noqa: E402
from PySide6.QtWidgets import QApplication              # noqa: E402

from GUI import prompt_parser as P                      # noqa: E402
from GUI_qt.main_window import MainWindow, BATTLE_PHASES  # noqa: E402

app = QApplication.instance() or QApplication([])

errors = []


def excepthook(*exc):
    errors.append("".join(traceback.format_exception(*exc)))


sys.excepthook = excepthook

w = MainWindow(ROOT)
w.show()
# the bridge swallows worker-thread tracebacks into an EV_ERROR event; without
# this a crash in the engine just looks like the harness going idle
_orig_error = w._show_error
w._show_error = lambda payload: (errors.append("EV_ERROR: %s" % payload),
                                 _orig_error(payload))

state = {"n": 0, "idle": 0, "clipped": [], "seq": [], "done": False,
         "battles": set(), "flushes": 0, "field_entries": 0, "shots": 0,
         "kinds": {}, "keepall": 0, "champ": 0, "compare": 0,
         "strays": {}}
_orig_fold = w._fold_champion_fanfare
def _spy_fold(request):
    out = _orig_fold(request)
    if out:
        state["champ"] += 1
        state["seq"].append("CHAMPION FANFARE FOLDED")
    return out
w._fold_champion_fanfare = _spy_fold
_orig_side = w.roster_dialog.show_side
def _spy_side(side):
    state["compare"] += 1
    state["seq"].append("COMPARE opened on %s" % side)
    return _orig_side(side)
w.roster_dialog.show_side = _spy_side
_orig_clear_feed = w._clear_feed


def _spy_clear_feed():
    state["flushes"] += 1
    return _orig_clear_feed()


w._clear_feed = _spy_clear_feed
# every line the log *would* have received, before and after the scrub, so the
# real player path can be measured rather than the simulation's debug output
LOG_SEEN, LOG_RAW = [], []
import GUI.bridge as _BR
_orig_write = w.bridge._write


def _spy_write(text):
    from GUI.ansi import strip as _strip
    for line in _strip(text).split(chr(10)):
        if line.strip():
            LOG_RAW.append(line.strip())
    return _orig_write(text)


w.bridge._write = _spy_write
_orig_log = w._append_log


def _spy_log(text):
    from GUI.ansi import strip as _strip
    for line in _strip(text).split(chr(10)):
        if line.strip():
            LOG_SEEN.append(line.strip())
    return _orig_log(text)


w._append_log = _spy_log
# the Field tab is a live board now, not a log -- record how many effects it
# is showing whenever that changes, instead of hooking a per-entry appender
_orig_set_state = w.field_board.set_state


def _spy_set_state(you, opponent, field):
    before = w.field_board._signature
    _orig_set_state(you, opponent, field)
    if w.field_board._signature != before and w.field_board.active:
        state["field_entries"] += 1
        state["seq"].append(
            "FIELD BOARD (%d): %s" % (w.field_board.active,
                                      w.tabs.tabText(w._field_tab)))


w.field_board.set_state = _spy_set_state


def answer_for(prompt, request):
    q = (prompt.question or "") + " " + (request.prompt or "")
    ql = q.lower()
    if prompt.mode == P.MODE_TEXT:
        if "name" in ql:
            return NAME
        return "1"
    if prompt.mode == P.MODE_CONTINUE:
        return ""
    if prompt.mode == P.MODE_CONFIRM:
        return "Y"
    if request.kind == "reward":
        # take/swap the opponent's first Pokemon, and give up our own first
        return "0"
    values = [c.value for c in prompt.choices]
    if not values:
        return ""
    # main menu: take New Game
    for c in prompt.choices:
        if "new game" in (c.label or "").lower():
            return c.value
    # never quit / save-and-exit out of the run
    bad = ("quit", "exit", "back", "cancel")
    good = [c for c in prompt.choices
            if not any(b in (c.label or "").lower() for b in bad)]
    pool = good or prompt.choices
    # rotate so battles don't loop on one move forever
    return pool[state["n"] % len(pool)].value


#: the windows the game is *meant* to be able to put on screen. Anything else
#: that turns up as a visible top-level widget is a stray -- a widget built
#: with no parent and shown before it was ever added to a layout is a window
#: in its own right, which is where the "flurry of little windows" before the
#: team screen came from. Class names rather than the classes themselves so
#: this list stays readable and does not need the imports.
ALLOWED_WINDOWS = {
    "MainWindow", "RosterDialog", "OpponentInfoDialog", "SettingsDialog",
    "HistoryDialog", "CareerDialog", "StandingsDialog", "StoryDialog",
    "CreditsDialog", "CompareDialog", "ArtLightbox", "PokedexDialog",
    "QMenu", "QToolTip", "QComboBoxPrivateContainer",
}


def check_strays():
    """Visible top-level widgets that are not one of the real windows.

    Qt makes any visible widget without a parent a window of its own, so this
    is what a stray pop-up looks like from the inside, on any platform --
    including offscreen, where nothing reaches a real desktop to be seen.
    """
    for widget in app.topLevelWidgets():
        if not widget.isVisible():
            continue
        name = type(widget).__name__
        if name in ALLOWED_WINDOWS:
            continue
        mark = "%s(%r) %dx%d" % (name, widget.windowTitle(),
                                 widget.width(), widget.height())
        if mark not in state["strays"]:
            state["strays"][mark] = (state["n"],
                                     (w.game_state or {}).get("phase"))


def check_clip(tag):
    hint = w.actions_body.sizeHint().height()
    have = w.actions_scroll.height()
    if hint > have + 1:
        state["clipped"].append("%s: needs %d has %d" % (tag, hint, have))


def tick():
    state["n"] += 1
    check_strays()
    if state["n"] > 4000:
        return finish("step cap")

    phase = (w.game_state or {}).get("phase")
    if phase in BATTLE_PHASES:
        state["battles"].add((w.game_state or {}).get("battle_seq"))
        if state["shots"] < 1 and (w.game_state or {}).get("player"):
            state["shots"] += 1
            w.grab().save(os.path.join(OUT, "live_battle.png"))

    if w._gated:
        w._end_result_gate() if hasattr(w, "_end_result_gate") else None
        return

    req = w.request
    if req is None:
        state["idle"] += 1
        if state["idle"] > 400:
            return finish("idle")
        return
    state["idle"] = 0
    # entitlement to see their team, sampled at every prompt
    known = bool(w.game_state.get("opponent_known"))
    seen = len(w.game_state.get("opponent_roster") or [])
    phase = (w.game_state or {}).get("phase")
    if phase == "prebattle":
        state.setdefault("prebattle_known", []).append((known, seen))
    if req.kind == "reward":
        state["won_known"] = True
        roster = w.game_state.get("player_roster") or []
        state["seq"].append(
            "ROSTER at reward: %d entries, benched=%s"
            % (len(roster), [m["name"] for m in roster if m.get("benched")]))
        state["rewards"] = state.get("rewards", 0) + 1
        state["opened"] = (w.compare_dialog is not None
                           and w.compare_dialog.isVisible())
        # the reward screen is driven from the compare window: press its
        # buttons rather than looking for a button grid that is not there
        import GUI.bridge as _B
        kind = _B.reward_prompt_kind(req.prompt)
        if kind is not None and w.compare_dialog is not None:
            state.setdefault("reward_kinds", []).append(kind)
            state.setdefault("reward_log", []).append(
                (kind, (req.prompt or "")[:46]))
            state["seq"].append("REWARD %s -> compare window open=%s"
                                % (kind, state["opened"]))
            state.setdefault("compare_sizes", set()).add(
                (w.compare_dialog.width(), w.compare_dialog.height()))
            state.setdefault("halves", set()).add(tuple(
                w.compare_dialog.columns[s]["heading"].parentWidget().width()
                for s in ("player", "opponent")))
            w.compare_dialog.fast_comparison()
            state["compare_sizes"].add((w.compare_dialog.width(),
                                        w.compare_dialog.height()))
            w.compare_dialog._on_proceed()
            state.setdefault("presses", []).append(kind)
            state.setdefault("plans", []).append(
                (kind, dict(w._reward_plan or {}),
                 len(w.game_state.get("player_roster") or []),
                 len(w.game_state.get("opponent_roster") or [])))
            return
    if req.kind == "team_keep":
        labels = [b.text() for b in w.findChildren(object)
                  if hasattr(b, "text") and callable(getattr(b, "click", None))
                  and b.isVisible()]
        for b in w.findChildren(object):
            if (hasattr(b, "text") and callable(getattr(b, "click", None))
                    and b.isVisible() and b.text() == "Keep All"):
                state["keepall"] += 1
                state["seq"].append("KEEP ALL clicked")
                b.click()
                return
        for b in w.findChildren(object):
            if (hasattr(b, "text") and callable(getattr(b, "click", None))
                    and b.isVisible() and b.text() == "Confirm selection"
                    and b.isEnabled()):
                state["seq"].append("CONFIRM clicked (labels=%s)" % labels)
                b.click()
                return
    # _fit_actions defers its measurement by one event-loop turn, so give
    # the screen a tick to settle before judging whether it is clipped
    if state.get("pending") is not req:
        state["pending"] = req
        return
    try:
        prompt = w.memory.parse(req.prompt, req.recent)
        check_clip("%s/%s" % (req.kind, prompt.mode))
        value = answer_for(prompt, req)
        state["seq"].append("%s[%s] %r -> %r"
                            % (req.kind, prompt.mode,
                               (prompt.question or req.prompt or "")[:70],
                               value))
        w._answer(value)
    except Exception:
        errors.append(traceback.format_exc())
        return finish("exception")


def finish(why):
    if state["done"]:
        return
    state["done"] = True
    report = [
        "stopped: %s after %d ticks" % (why, state["n"]),
        "battles seen:   %d" % len({b for b in state["battles"]
                                    if b is not None}),
        "feed flushes:   %d" % state["flushes"],
        "field entries:  %d" % state["field_entries"],
        "clipped screens: %d" % len(state["clipped"]),
        "stray windows:  %d" % len(state["strays"]),
        "prompt kinds:   %s" % state["kinds"],
        "keep-all uses:  %d" % state["keepall"],
        "champ folds:    %d" % state["champ"],
        "compare opens:  %d" % state["compare"],
        "pre-battle samples (known, roster size): %s"
        % sorted(set(state.get("prebattle_known") or [])),
        "a reward screen happened: %s" % bool(state.get("won_known")),
        "reward prompts: %d" % state.get("rewards", 0),
        "compare auto-opened at reward: %s" % state.get("opened"),
        "reward questions seen: %s" % sorted(set(state.get("reward_kinds")
                                                or [])),
        "every reward prompt in order: %s" % (state.get("reward_log") or []),
        "compare window sizes seen: %s" % sorted(state.get("compare_sizes")
                                                or []),
        "column widths seen: %s" % sorted(state.get("halves") or []),
        "presses the player had to make: %s" % (state.get("presses") or []),
        "plans + roster sizes: %s" % (state.get("plans") or []),
        "round_results ratings: %s" % [
            [(c.get("nickname"), c.get("strength")) for c in pair]
            for r in (w.game_state.get("round_results") or [])[:1]
            for pair in r.get("pairs", [])[:2]],
    ]
    report += ["  " + c for c in state["clipped"][:20]]
    report += ["  stray window %s at tick %d, phase %s" % (mark, n, phase)
               for mark, (n, phase) in state["strays"].items()]
    # just report it -- saveguard moves anything this run created into OUT as
    # CREATED-playthrough-*.savefile.json, so it can still be inspected
    made = os.path.join(ROOT, "savefile.json")
    report.append("wrote savefile.json: %s"
                  % ("%d bytes" % os.path.getsize(made)
                     if os.path.exists(made) else "no"))
    import collections as _c
    import re as _re
    shape = lambda l: _re.sub(r"\d+", "N", l)
    report += ["", "log lines the engine offered: %d" % len(LOG_RAW),
               "log lines actually shown:     %d" % len(LOG_SEEN),
               "most common shown:"]
    report += ["    %-4d %s" % (n, t[:70]) for t, n
               in _c.Counter(shape(l) for l in LOG_SEEN).most_common(12)]
    report += ["most common filtered out:"]
    shown = _c.Counter(shape(l) for l in LOG_SEEN)
    offered = _c.Counter(shape(l) for l in LOG_RAW)
    gone = {t: n - shown.get(t, 0) for t, n in offered.items()
            if n > shown.get(t, 0)}
    report += ["    %-4d %s" % (n, t[:70]) for t, n
               in sorted(gone.items(), key=lambda kv: -kv[1])[:10]]
    report += ["errors: %d" % len(errors)]
    report += errors[:3]
    report += ["", "-- last 60 prompts --"] + state["seq"][-120:]
    text = "\n".join(report)
    with open(os.path.join(OUT, "playthrough.txt"), "w",
              encoding="utf-8") as f:
        f.write(text + "\n")
    print("\n".join(report[:18]), flush=True)
    # A verdict of its own. This used to print the report and nothing else, so
    # whether a whole tournament had gone through cleanly was left to whoever
    # read it -- and a runner looking for a summary line matched a stray "ok"
    # buried in the report by luck rather than by design.
    global FAILED
    trouble = []
    if errors:
        trouble.append("%d exception(s)" % len(errors))
    if state["clipped"]:
        trouble.append("%d clipped screen(s)" % len(state["clipped"]))
    if state["strays"]:
        trouble.append("%d stray window(s)" % len(state["strays"]))
    if not {b for b in state["battles"] if b is not None}:
        trouble.append("no battles were reached")
    FAILED = bool(trouble)
    print("", flush=True)
    print("ALL PASS" if not trouble else "FAILURES: " + ", ".join(trouble),
          flush=True)
    for entry in errors[:2]:
        print(entry, flush=True)
    app.quit()


FAILED = False

t = QTimer()
t.timeout.connect(tick)
t.start(15)
QTimer.singleShot(180000, lambda: finish("wall clock"))
app.exec()
sys.exit(1 if FAILED else 0)
