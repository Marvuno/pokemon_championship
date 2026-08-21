"""Play a whole run in one slot; do the other slots survive it?

The report is that after finishing a career in slot 2 and choosing Play
Again, the other slots' histories cannot be reached. The engine's slot
handling round-trips correctly and the interface re-opens its career window
correctly, so this checks the remaining possibility: that finishing a run
damages the files the other careers live in.

Runs in a sandbox with its own Save/, so the player's real careers are never
touched. Prints what each slot looked like before and after.

    python Test/gui/probe_slot_survival.py <root> <out>
"""
import builtins
import hashlib
import io
import json
import os
import shutil
import sys
import traceback

ROOT, OUT = sys.argv[1], sys.argv[2]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

_say = builtins.print          # the bridge is about to replace print()

# -- the real root, with the project's own guard ---------------------------
# A sandbox needs Assets (311MB) or the game will not start at all, so this
# runs where the game lives and leans on saveguard, which snapshots every save
# by hash before Qt starts and puts exactly that back on the way out. The
# before/after comparison below is taken *during* the run, ahead of that
# restore, so the evidence survives the protection.
sys.path.insert(0, OUT)
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import saveguard                                                 # noqa: E402
saveguard.install(ROOT, OUT, tag="probe_slot_survival")

SAVE_DIR = os.path.join(ROOT, "Save")


def snapshot():
    out = {}
    for slot in (1, 2, 3, 4):
        path = os.path.join(SAVE_DIR, "savefile%d.json" % slot)
        if not os.path.exists(path):
            out[slot] = None
            continue
        raw = open(path, "rb").read()
        try:
            player = (json.loads(raw.decode("utf-8")) or {}).get("player") or {}
            out[slot] = {"nickname": player.get("nickname"),
                         "runs": player.get("participation"),
                         "bytes": len(raw),
                         "sha": hashlib.sha256(raw).hexdigest()[:12]}
        except Exception as exc:                                # noqa: BLE001
            out[slot] = {"UNREADABLE": repr(exc), "bytes": len(raw)}
    return out


before = snapshot()
_say("slots before the run:")
for slot, info in sorted(before.items()):
    _say("   %d: %s" % (slot, info))

TARGET_SLOT = "2" if before.get(2) else "1"
_say("")
_say("playing a whole career in slot %s ..." % TARGET_SLOT)

sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer                                # noqa: E402
from PySide6.QtWidgets import QApplication                       # noqa: E402

from GUI import prompt_parser as P                               # noqa: E402
from GUI_qt.main_window import MainWindow                        # noqa: E402

app = QApplication.instance() or QApplication([])
errors = []
sys.excepthook = lambda *e: errors.append("".join(
    traceback.format_exception(*e)))

window = MainWindow(ROOT)
window.show()
_orig_error = window._show_error
window._show_error = lambda payload: errors.append("EV_ERROR: %s" % payload)

state = {"n": 0, "idle": 0, "done": False, "slot_asked": 0, "finished": False,
         "seq": []}


def answer_for(prompt, request):
    said = ((prompt.question or "") + " " + (request.prompt or "")).lower()
    if "which save slot" in said:
        state["slot_asked"] += 1
        return TARGET_SLOT
    if prompt.mode == P.MODE_TEXT:
        return "SlotProbe" if "name" in said else "1"
    if prompt.mode == P.MODE_CONTINUE:
        if "confirm the results" in said:
            state["finished"] = True
        return ""
    if prompt.mode == P.MODE_CONFIRM:
        return "N" if "first-timer" in said else "Y"
    if request.kind == "reward":
        return "0"
    choices = prompt.choices
    if not choices:
        return ""
    # CONTINUE the existing career in that slot rather than starting new
    for choice in choices:
        if "continue" in (choice.label or "").lower():
            return choice.value
    bad = ("quit", "exit", "back", "cancel")
    good = [c for c in choices
            if not any(b in (c.label or "").lower() for b in bad)]
    pool = good or choices
    return pool[state["n"] % len(pool)].value


def tick():
    state["n"] += 1
    if state["n"] > 6000:
        return finish("step cap")
    if state["finished"]:
        return finish("run completed")
    if window._gated:
        return
    request = window.request
    if request is None:
        state["idle"] += 1
        if state["idle"] > 600:
            return finish("idle")
        return
    state["idle"] = 0
    if request.kind == "reward" and window.compare_dialog is not None:
        import GUI.bridge as B
        if B.reward_prompt_kind(request.prompt) is not None:
            window.compare_dialog._on_proceed()
            return
    if request.kind == "team_keep":
        for widget in window.findChildren(object):
            if (hasattr(widget, "text") and callable(getattr(widget, "click", None))
                    and widget.isVisible() and widget.text() == "Keep All"):
                widget.click()
                return
    try:
        prompt = window.memory.parse(request.prompt, request.recent)
        value = answer_for(prompt, request)
        state["seq"].append("%s -> %r" % ((request.prompt or "")[:48], value))
        window._answer(value)
    except Exception:                                           # noqa: BLE001
        errors.append(traceback.format_exc())
        return finish("exception")


def finish(why):
    if state["done"]:
        return
    state["done"] = True
    timer.stop()
    after = snapshot()
    _say("stopped: %s after %d ticks (slot question asked %d time(s))"
         % (why, state["n"], state["slot_asked"]))
    _say("")
    _say("slots after the run:")
    changed = []
    for slot in sorted(after):
        mark = ""
        if before.get(slot) != after.get(slot):
            mark = "   <<< CHANGED"
            if slot != int(TARGET_SLOT):
                changed.append(slot)
        _say("   %d: %s%s" % (slot, after.get(slot), mark))
    _say("")
    if changed:
        _say("PROBLEM: finishing a run in slot %s also changed slot(s) %s"
             % (TARGET_SLOT, changed))
    else:
        _say("the other slots are byte-for-byte unchanged")
    _say("errors: %d" % len(errors))
    for entry in errors[:2]:
        _say(entry)
    with open(os.path.join(OUT, "slot_survival.txt"), "w",
              encoding="utf-8") as out:
        out.write("\n".join(state["seq"][-80:]) + "\n")
    QTimer.singleShot(0, app.quit)


timer = QTimer()
timer.timeout.connect(tick)
timer.start(15)   # the engine needs seconds to import; 1ms idled out
QTimer.singleShot(240000, lambda: finish("wall clock"))
app.exec()
