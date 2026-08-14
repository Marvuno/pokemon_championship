"""Does picking Check History in a real run actually open a window?

Drives Continue -> the pre-battle menu -> option 4, then reports which
dialogs exist and whether they are visible.
"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import atexit                                                # noqa: E402
import shutil                                                # noqa: E402

# --- keep the live save out of harm's way ----------------------------------
# This harness plays real games, and the engine saves into the project folder
# with no way to redirect it. See saveguard.py: it snapshots both save files
# before Qt starts and puts them back on the way out, whatever happens.
sys.path.insert(0, OUT)
import saveguard                                              # noqa: E402
saveguard.install(ROOT, OUT, tag=os.path.splitext(
    os.path.basename(__file__))[0])

from PySide6.QtCore import QTimer                             # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog           # noqa: E402

from GUI import prompt_parser as P                            # noqa: E402
from GUI_qt.main_window import MainWindow                     # noqa: E402
from GUI_qt.panels import HistoryDialog, OpponentInfoDialog   # noqa: E402

app = QApplication.instance() or QApplication([])
errors = []
sys.excepthook = lambda *e: errors.append("".join(
    traceback.format_exception(*e)))

w = MainWindow(ROOT)
w.show()
_orig_error = w._show_error
w._show_error = lambda p: (errors.append("EV_ERROR: %s" % p), _orig_error(p))

st = {"n": 0, "idle": 0, "seq": [], "done": False, "menus": 0,
      "snapshots": []}


def snapshot(tag):
    rows = []
    for d in w.findChildren(QDialog):
        rows.append("%s visible=%s size=%dx%d pos=%d,%d"
                    % (type(d).__name__, d.isVisible(),
                       d.width(), d.height(), d.x(), d.y()))
    st["snapshots"].append("%s: %s" % (tag, rows or "no dialogs"))


def answer_for(prompt, request):
    said = ((prompt.question or "") + " " + (request.prompt or "")).lower()
    if "your option" in said:
        return "1"                                  # CONTINUE
    if "what do you want to do" in said:
        st["menus"] += 1
        if st["menus"] == 1:
            return "3"                              # About Opponent
        if st["menus"] == 2:
            snapshot("after About Opponent")
            return "4"                              # Check History
        snapshot("after Check History")
        return "0"
    if prompt.mode == P.MODE_CONTINUE:
        return ""
    if prompt.mode == P.MODE_CONFIRM:
        return "N"
    return "0"


def tick():
    st["n"] += 1
    if st["n"] > 600:
        return finish("step cap")
    req = w.request
    if req is None:
        st["idle"] += 1
        if st["idle"] > 200:
            return finish("idle")
        return
    st["idle"] = 0
    try:
        prompt = w.memory.parse(req.prompt, req.recent)
        value = answer_for(prompt, req)
        st["seq"].append("%r -> %r" % ((prompt.question or req.prompt)[:50],
                                       value))
        w._answer(value)
    except Exception:
        errors.append(traceback.format_exc())
        return finish("exception")
    if st["menus"] >= 3:
        return finish("walked the menu")


def finish(why):
    if st["done"]:
        return
    st["done"] = True
    app.processEvents()
    snapshot("at the end")
    histories = w.findChildren(HistoryDialog)
    abouts = w.findChildren(OpponentInfoDialog)
    report = [
        "stopped: %s after %d ticks" % (why, st["n"]),
        "menus visited:            %d" % st["menus"],
        "HistoryDialog created:    %d" % len(histories),
        "HistoryDialog visible:    %s" % [d.isVisible() for d in histories],
        "OpponentInfoDialog made:  %d" % len(abouts),
        "OpponentInfoDialog vis:   %s" % [d.isVisible() for d in abouts],
        "history_info in state:    %s"
        % bool((w.game_state or {}).get("history_info")),
        "payload:                  %s" % ((w.game_state or {})
                                          .get("history_info")),
        "errors: %d" % len(errors),
    ] + errors[:2] + [""] + st["snapshots"] + ["", "-- prompts --"] + st["seq"]
    with open(os.path.join(OUT, "history_window.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
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
