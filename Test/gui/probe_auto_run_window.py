"""Drive the real window through an Auto Run and answer nothing.

`test_auto_run.py` checks the engine side: the scripted replies carry a
career to its end. This checks the half that lives in the window, which the
engine test cannot see -- the knockout gate and the RUN COMPLETE screen are
Qt, not `input()`, so `auto_run`'s answering of prompts never reaches them.
Both stopped an unattended run dead, once per battle and once per career.

The harness deliberately presses nothing. Anything still waiting for a click
shows up as the run going idle.

    python Test/gui/probe_auto_run_window.py <root> <out> [runs]
"""
import io
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else ".")
RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 2
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Plays real games and the engine saves into the project folder.
sys.path.insert(0, os.path.join(ROOT, "Test", "gui"))
import saveguard                                              # noqa: E402
saveguard.install(ROOT, OUT, tag="auto_run_window")

from PySide6.QtCore import QTimer                             # noqa: E402
from PySide6.QtWidgets import QApplication                    # noqa: E402

from GUI import prompt_parser as P                            # noqa: E402
from GUI_qt.main_window import MainWindow                     # noqa: E402
from Scripts.Game import auto_run                             # noqa: E402

app = QApplication.instance() or QApplication([])
errors = []
sys.excepthook = lambda *e: errors.append("".join(traceback.format_exception(*e)))

# Count anything that would actually reach the mixer while a run is on.
from Scripts.Art import music as _music
_plays = []
_real_music, _real_sound = _music.music, _music.sound
# MUTED is forced on by QT_QPA_PLATFORM=offscreen, so testing it here would
# pass no matter what. The question is whether _SILENCED -- the runtime flag
# Auto Run sets -- is on for every sound the run asks for. Anything recorded
# below would have been audible in a real, unmuted game.
def _spy_music(*, audio, loop):
    if auto_run.state.active and not _music._SILENCED:
        _plays.append("music %s" % os.path.basename(str(audio)))
    return _real_music(audio=audio, loop=loop)
def _spy_sound(*, audio, **kw):
    # **kw so a later keyword cannot turn this into a TypeError that the
    # caller quietly swallows -- which would leave this probe reporting a
    # clean run over a broken one.
    if auto_run.state.active and not _music._SILENCED:
        _plays.append("sound %s" % os.path.basename(str(audio)))
    return _real_sound(audio=audio, **kw)
_music.music, _music.sound = _spy_music, _spy_sound

import main as _main
import Scripts.Game.start_interface as _si
trace = []
_real_career = _main.play_career
def _spy_career():
    from Scripts.Game.game_system import GameSystem as _GS
    trace.append("play_career in (GameSystem.stage=%s, player.stage=%s)"
                 % (_GS.stage, getattr(_si.list_of_competitors["Protagonist"], "stage", "?")))
    out = _real_career()
    trace.append("play_career out (GameSystem.stage=%s)" % _GS.stage)
    state["careers"] = state.get("careers", 0) + 1
    return out
_main.play_career = _spy_career
_real_draw = _si.draw_bracket
def _spy_draw():
    trace.append("draw_bracket")
    return _real_draw()
_main.draw_bracket = _spy_draw
_si.draw_bracket = _spy_draw

_real_stop = auto_run.stop
def _traced_stop():
    import traceback as _tb
    auto_run.state.stops = getattr(auto_run.state, "stops", [])
    auto_run.state.stops.append("".join(_tb.format_stack()[-4:-1])[-300:])
    return _real_stop()
auto_run.stop = _traced_stop

w = MainWindow(ROOT)
# count how often the window is told anything at all, per career
_calls = {}
_real_apply = w._apply_state
def _spy_apply(st):
    _calls[auto_run.state.done] = _calls.get(auto_run.state.done, 0) + 1
    return _real_apply(st)
w._apply_state = _spy_apply
# is the engine still publishing, or has the window stopped listening?
_pub = {}
_real_publish = w.bridge.publish
def _spy_publish(**kw):
    if "phase" in kw or "player" in kw or "field" in kw:
        _pub[auto_run.state.done] = _pub.get(auto_run.state.done, 0) + 1
    return _real_publish(**kw)
w.bridge.publish = _spy_publish
_drain = {}
_real_drain = w._drain_events if hasattr(w, "_drain_events") else None
w.show()
_orig_error = w._show_error
w._show_error = lambda payload: (errors.append("EV_ERROR: %s" % payload),
                                 _orig_error(payload))

state = {"n": 0, "idle": 0, "gates": 0, "careers": 0, "last": None,
         "menu_answers": 0, "done": False, "why": "", "started": False,
         "before": None}

import hashlib
from Scripts.Data.competitors import list_of_competitors as _C
from Scripts.Game import savefile as _sf


def career_facts():
    me = _C["Protagonist"]
    slot = getattr(_sf, "_slot", None) or getattr(_sf, "slot", None) or 1
    path = os.path.join(ROOT, "Save", "savefile%s.json" % slot)
    try:
        digest = hashlib.sha1(io.open(path, "rb").read()).hexdigest()[:12]
    except Exception:
        digest = "(missing)"
    return dict(slot=slot, save=digest,
                participation=getattr(me, "participation", None),
                history=len(getattr(me, "history", {}) or {}),
                rating=me.strength)

_gate_events = []
_orig_end = w._end_result_gate
def _spy_end():
    _gate_events.append("END   gated=%s unattended=%s done=%d"
                        % (w._gated, auto_run.unattended(), auto_run.state.done))
    return _orig_end()
w._end_result_gate = _spy_end
_orig_gate = w._begin_result_gate


def spy_gate(result):
    state["gates"] += 1
    _gate_events.append("BEGIN unattended=%s done=%d"
                        % (auto_run.unattended(), auto_run.state.done))
    state.setdefault("gate_log", []).append(
        "gate %d: active=%s settling=%s" % (state["gates"],
                                            auto_run.state.active,
                                            auto_run.state.settling))
    return _orig_gate(result)


w._begin_result_gate = spy_gate


def finish(why):
    if state["done"]:
        return
    state["done"] = True
    state["why"] = why
    timer.stop()
    app.quit()


def tick():
    state["n"] += 1
    if auto_run.state.active:
        # How far behind the window is. During an unattended run the worker
        # never blocks on input, so without a yield it holds the GIL and the
        # queue climbs into the thousands while the screen sits frozen.
        state.setdefault("lag", set()).add(
            "career %d: gated=%s pump=%s queued=%d"
            % (auto_run.state.done + 1, w._gated, w._timer.isActive(),
               w.bridge.events.qsize()))
    # the finish line: the ordinary end-of-run screen, reached with nobody
    # having pressed anything since the slot was chosen
    if state["started"] and not auto_run.state.active and state.get("careers"):
        if state["careers"] < RUNS:
            return finish("stopped after only %d of %d careers"
                          % (state["careers"], RUNS))
    if state["n"] > 40000:
        return finish("step cap")

    req = w.request
    if req is not None and (req.prompt or "") != state["last"]:
        state["last"] = req.prompt or ""
        state.setdefault("seen", []).append(state["last"][:70])
    if req is None:
        # nothing being asked. Idle is only a problem once the run has begun.
        state["idle"] += 1
        if auto_run.state.active and state["idle"] > 400:
            return finish("STALLED: %d ticks with nothing asked and no auto "
                          "answer (gates seen: %d)" % (state["idle"],
                                                       state["gates"]))
        return
    state["idle"] = 0

    prompt = P.parse(req.prompt, getattr(req, "recent", "") or "")

    # The only things this harness ever answers are the three questions that
    # *start* an Auto Run -- the menu, the slot, and how many runs. Everything
    # after that has to come from auto_run itself, which is the point.
    if not auto_run.state.active:
        text = req.prompt or ""
        if "Your Option" in text:
            state["menu_answers"] += 1
            if state["menu_answers"] > 1:
                return finish("back at the menu after %d careers"
                              % state.get("careers", 0))
            return w._answer("3")                       # AUTO RUN
        if "save slot" in text.lower():
            used = [c.value for c in prompt.choices if c.value != "0"]
            if not used:
                return finish("no used save slot to auto-run")
            state["started"] = True
            answer = w._answer(used[0])
            state["before"] = career_facts()
            return answer
        if "How many runs to simulate" in text:
            return w._answer(str(RUNS))
        return finish("unexpected question before the run began: %r" % text[:70])

    # Auto Run is live: nothing here answers anything.
    return finish("a prompt reached the window during an Auto Run: %r"
                  % (req.prompt or "")[:70])


timer = QTimer()
timer.timeout.connect(tick)
QTimer.singleShot(200000, lambda: finish("wall clock"))
timer.start(15)
app.exec()

print("ticks=%d gates=%d menu_answers=%d" % (state["n"], state["gates"],
                                             state["menu_answers"]))
print("outcome: %s" % state["why"])
print("careers played: %d of %d" % (state.get("careers", 0), RUNS))
after = career_facts()
before = state["before"] or {}
print("did the career leave anything behind?")
for key in ("slot", "save", "participation", "history", "rating"):
    mark = "SAME" if before.get(key) == after.get(key) else "changed"
    print("   %-14s %-14s -> %-14s %s"
          % (key, before.get(key), after.get(key), mark))
print("auto_run active=%s" % auto_run.state.active)
print("prompt tag now: %r" % w.prompt_tag.text())
print("how far behind the window ran: %r" % state.get("lag"))
print("gate events:")
print("   total %d events; last 8:" % len(_gate_events))
[print("   " + e) for e in _gate_events[-8:]]
print("   final: gated=%s pump=%s queued=%d"
      % (w._gated, w._timer.isActive(), w.bridge.events.qsize()))
print("_apply_state calls per career: %r" % _calls)
print("bridge.publish calls per career: %r" % _pub)
print("sounds asked for during the run with silence OFF: %d" % len(_plays))
for p in _plays[:8]:
    print("   %s" % p)
print("gate log: %s" % state.get("gate_log"))
print("window gated=%s  event timer active=%s  request=%r"
      % (getattr(w, "_gated", "?"),
         getattr(getattr(w, "_timer", None), "isActive", lambda: "?")(),
         getattr(w.request, "prompt", None)))
import threading
print("live threads: %s" % [t.name for t in threading.enumerate()])
import sys as _s
dupes = [k for k in _s.modules if k.endswith("auto_run")]
print("auto_run module names in sys.modules: %s" % dupes)
print("same object as the window's? %s"
      % (_s.modules.get("Scripts.Game.auto_run") is auto_run))
import GUI_qt.main_window as _mw
print("window sees the same module? %s" % (_mw.auto_run is auto_run))
import Scripts.Game.start_interface as _si
print("start_interface sees the same module? %s" % (_si.auto_run is auto_run))
print("career trace:")
for t in trace[:14]:
    print("   %s" % t)
print("stop() call sites hit: %s" % getattr(auto_run.state, "stops", "not traced"))
try:
    log = [l for l in (w.log.toPlainText() or "").splitlines() if l.strip()]
    print("last 14 log lines:")
    for l in log[-14:]:
        print("   %s" % l[:96])
except Exception as err:
    print("could not read the log: %r" % err)
print("prompts seen (%d):" % len(state.get("seen", [])))
for p in state.get("seen", [])[:12]:
    print("   %r" % p)
for e in errors[:2]:
    print(e[-600:])
ok = (not errors) and state["why"].startswith("back at the menu")     and state.get("careers") == RUNS
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
