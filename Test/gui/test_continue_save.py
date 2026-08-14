"""Load the real save through the real main menu (Continue), then walk the
pre-battle menu including Check History against whoever we are drawn against.

The save is parked before Qt starts and restored on the way out.
"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import atexit                                              # noqa: E402
import shutil                                              # noqa: E402

# --- keep the live save out of harm's way ----------------------------------
# This harness plays real games, and the engine saves into the project folder
# with no way to redirect it. See saveguard.py: it snapshots both save files
# before Qt starts and puts them back on the way out, whatever happens.
sys.path.insert(0, OUT)
import saveguard                                              # noqa: E402
saveguard.install(ROOT, OUT, tag=os.path.splitext(
    os.path.basename(__file__))[0])

from PySide6.QtCore import QTimer                           # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

from GUI import prompt_parser as P                          # noqa: E402
from GUI_qt.main_window import MainWindow                   # noqa: E402

app = QApplication.instance() or QApplication([])
errors = []
sys.excepthook = lambda *e: errors.append("".join(
    traceback.format_exception(*e)))

w = MainWindow(ROOT)
w.show()
_orig_error = w._show_error
w._show_error = lambda payload: (errors.append("EV_ERROR: %s" % payload),
                                 _orig_error(payload))

st = {"n": 0, "idle": 0, "seq": [], "done": False, "history": 0,
      "menus": 0, "loaded": False}


def answer_for(prompt, request):
    said = ((prompt.question or "") + " " + (request.prompt or "")).lower()
    if prompt.mode == P.MODE_TEXT:
        return "1"
    if prompt.mode == P.MODE_CONTINUE:
        return ""
    if prompt.mode == P.MODE_CONFIRM:
        return "Y"
    # the main menu: Continue, not New Game
    for c in prompt.choices:
        if "continue" in (c.label or "").lower():
            st["loaded"] = True
            return c.value
    if "what do you want to do" in said:
        st["menus"] += 1
        # About Opponent, Check History, Check History again, then battle
        order = ["3", "4", "4", "1", "0"]
        return order[min(st["menus"] - 1, len(order) - 1)]
    if "wanna know the pokemon championship history" in said:
        return "Y"
    pool = [c for c in prompt.choices
            if "quit" not in (c.label or "").lower()] or prompt.choices
    return pool[st["n"] % len(pool)].value


def tick():
    st["n"] += 1
    if st["n"] > 1200:
        return finish("step cap")
    if w._gated:
        w._end_result_gate()
        return
    req = w.request
    if req is None:
        st["idle"] += 1
        if st["idle"] > 300:
            return finish("idle")
        return
    st["idle"] = 0
    try:
        prompt = w.memory.parse(req.prompt, req.recent)
        value = answer_for(prompt, req)
        st["seq"].append("%s[%s] %r -> %r" % (
            req.kind, prompt.mode,
            (prompt.question or req.prompt or "")[:64], value))
        w._answer(value)
    except Exception:
        errors.append(traceback.format_exc())
        return finish("exception")
    # did the history dialog get data?
    if w.game_state.get("history_info"):
        st["history"] = 1
    if st["menus"] >= 5 and st["history"]:
        return finish("walked the menu")


def finish(why):
    if st["done"]:
        return
    st["done"] = True
    # The bridge redirects builtins.print into its own event queue, so
    # anything printed here would be swallowed -- write to a file instead.
    report = [
        "stopped: %s after %d ticks" % (why, st["n"]),
        "picked Continue:      %s" % st["loaded"],
        "pre-battle menus hit: %d" % st["menus"],
        "history_info arrived: %s" % bool(st["history"]),
        "errors:               %d" % len(errors),
    ]
    report += errors[:2]
    report += ["", "-- prompts --"] + ["  " + l for l in st["seq"][:30]]
    with open(os.path.join(OUT, "continue.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
    # Stop the game thread and let it unwind BEFORE the atexit restore fires.
    # Otherwise the worker can still be inside save_game() when the save is
    # put back, and its write lands afterwards -- which is how the player's
    # save crept forward a run at a time despite the guard.
    try:
        w.bridge.stop()
        if w.bridge.thread is not None:
            w.bridge.thread.join(timeout=5)
    except Exception:
        pass
    app.quit()


t = QTimer()
t.timeout.connect(tick)
t.start(15)
QTimer.singleShot(120000, lambda: finish("wall clock"))
app.exec()
