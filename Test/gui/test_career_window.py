"""The main menu's HISTORY screen: one window, four tabs, no prompts.

Drives the real thing -- title screen -> HISTORY -> click names in the window
-> close -- and checks the player is never asked a question, that all four
views fill in, and that none of it lands in the log.
"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

sys.path.insert(0, OUT)
import saveguard                                               # noqa: E402
saveguard.install(ROOT, OUT, tag="career")

from PySide6.QtCore import Qt, QTimer                          # noqa: E402
from PySide6.QtWidgets import (QApplication, QLabel,           # noqa: E402
                               QScrollArea)

from GUI_qt.main_window import MainWindow                      # noqa: E402

app = QApplication.instance() or QApplication([])
errors, fails = [], []
sys.excepthook = lambda *e: errors.append("".join(
    traceback.format_exception(*e)))

w = MainWindow(ROOT)
w.show()
_orig_error = w._show_error
w._show_error = lambda p: (errors.append("EV_ERROR: %s" % p), _orig_error(p))

logged = []
_orig_append = w._append_log
w._append_log = lambda text: (logged.append(text), _orig_append(text))[1]

#: every question the player was actually shown a control for
asked = []
_orig_show = w._show_request
def spy_show(request):
    out = _orig_show(request)
    if w.request is request and request.kind != "career":
        asked.append((request.kind, (request.prompt or "")[:60]))
    return out
w._show_request = spy_show

st = {"n": 0, "idle": 0, "step": 0, "done": False, "snap": {}, "log": []}
PLAYER, RIVAL = 1, 2
UNPLAYED = None      # filled in once the roster arrives


def texts(widget):
    return [c.text() for c in widget.findChildren(QLabel) if c.text()]


def body_of(title):
    d = w.career_dialog
    for index in range(d.tabs.count()):
        if d.tabs.tabText(index) == title:
            return d.tabs.widget(index)
    return d


def capture():
    d = w.career_dialog
    return {
        "visible": d.isVisible(),
        "tab": d.tabs.tabText(d.tabs.currentIndex()),
        "tabs": [d.tabs.tabText(i) for i in range(d.tabs.count())],
        "opponents": len(d._rows),
        "champions": " | ".join(texts(body_of("Champions"))),
        "career": " | ".join(texts(body_of("Career"))),
        "runs": " | ".join(texts(body_of("Tournaments"))),
        "records": " | ".join(texts(body_of("Head to Head"))),
        "hbars": [sc.horizontalScrollBarPolicy()
                  for sc in d.findChildren(QScrollArea)],
        "pending": None if w.request is None else w.request.kind,
    }


def tick():
    st["n"] += 1
    if st["n"] > 900:
        return finish("step cap")
    app.processEvents()
    d = w.career_dialog

    # step 0: get to HISTORY -- the menu, then which of the four save slots.
    # Both are normal menus with buttons. Read the choices rather than
    # hardcoding numbers: answering "3" stopped working the moment OPTIONS was
    # taken off the menu and everything below it shifted up.
    if st["step"] == 0:
        if w.career_dialog.isVisible():
            st["step"] = 1
            return
        if w.request is not None and w.request.kind != "career":
            prompt = w.memory.parse(w.request.prompt, w.request.recent)
            asked = ((w.request.prompt or "") + " "
                     + (prompt.question or "")).lower()
            if "slot" in asked:
                pick = next((c.value for c in prompt.choices
                             if str(c.value).isdigit() and int(c.value) > 0),
                            None)
            else:
                pick = next((c.value for c in prompt.choices
                             if "history" in (c.label or "").lower()), None)
            if pick is not None:
                w._answer(pick)
        return

    # step 1: wait for the window to open on its own
    if st["step"] == 1:
        if d.isVisible() and d._rows:
            st["snap"]["opened"] = capture()
            st["step"] = 2
        return

    # step 2: click the player, then wait for both tabs to fill
    if st["step"] == 2:
        d._on_pick(PLAYER)
        st["step"], st["settle"] = 3, 0
        return
    if st["step"] == 3:
        st["settle"] += 1
        if (w.game_state or {}).get("career_records") is not None:
            app.processEvents()
            st["snap"]["player"] = capture()
            st["step"] = 4
        elif st["settle"] > 250:
            st["snap"]["player"] = capture()
            st["step"] = 4
        return

    # step 4: a second name, with no prompt in between
    if st["step"] == 4:
        st["records_before"] = (w.game_state or {}).get("career_records")
        d._on_pick(RIVAL)
        st["step"], st["settle"] = 5, 0
        return
    if st["step"] == 5:
        st["settle"] += 1
        now = (w.game_state or {}).get("career_records")
        if now is not None and now is not st.get("records_before"):
            app.processEvents()
            st["snap"]["rival"] = capture()
            st["step"] = 6
        elif st["settle"] > 250:
            st["snap"]["rival"] = capture()
            st["step"] = 6
        return

    # step 6: close the window -- the engine must unwind by itself
    if st["step"] == 6:
        d.close()
        st["step"], st["settle"] = 7, 0
        return
    if st["step"] == 7:
        st["settle"] += 1
        if st["settle"] > 40:
            st["snap"]["closed"] = capture()
            return finish("walked the screen")
        return


def check(label, got, want=True):
    ok = got == want
    st["log"].append("%-58s %s" % (label, "PASS" if ok else
                                   "FAIL got=%r want=%r" % (got, want)))
    if not ok:
        fails.append(label)


def finish(why):
    if st["done"]:
        return
    st["done"] = True
    app.processEvents()
    opened = st["snap"].get("opened") or {}
    player = st["snap"].get("player") or {}
    rival = st["snap"].get("rival") or {}
    closed = st["snap"].get("closed") or {}
    log = chr(10).join(logged)

    check("the window opens by itself", opened.get("visible"))
    check("...on the Opponents tab", opened.get("tab"), "Opponents")
    check("...with six tabs", opened.get("tabs"),
          ["Opponents", "Champions", "Records", "Career", "Tournaments",
           "Head to Head"])
    check("...every competitor listed", (opened.get("opponents") or 0) > 50)
    check("...and the champion roll already filled",
          "#1" in opened.get("champions", ""))

    check("clicking a name fills the career",
          "win rate" in player.get("career", "").lower())
    check("...and the run list has moved off it, into Tournaments",
          "rank" not in player.get("career", "").lower())
    check("...and who they played most",
          "most played" in player.get("career", "").lower())
    check("...and fills head to head too",
          player.get("records", "").count(" W  ") > 3)

    check("the tournaments tab lists every run",
          "every championship" in player.get("runs", "").lower())
    check("...with a best finish", "BEST FINISH" in player.get("runs", ""))
    check("...and who won each one", "Champion:" in player.get("runs", ""))
    check("nothing scrolls sideways", set(player.get("hbars") or [1]),
          {Qt.ScrollBarAlwaysOff})
    check("head to head is ordered by rating, hardest first",
          "hardest opponent first" in player.get("records", ""))
    check("...and each row shows that rating",
          player.get("records", "").count("[") > 5)

    check("a second name works with no prompt in between",
          rival.get("records", "") != player.get("records", ""))
    check("...and swaps the career over",
          rival.get("career", "") != player.get("career", ""))

    # "Your Option:" is the title menu -- the prompt used to get in here, and
    # the one landed back on afterwards. Both are meant to have buttons. What
    # must never reach the player is any of the history screen's own three.
    from GUI.bridge import career_prompt_kind
    leaked = [entry for entry in asked if career_prompt_kind(entry[1])]
    check("no history-screen question ever reached the player", leaked, [])
    # The title menu, and which of the four save slots to read -- both are
    # meant to be asked, and both get buttons. Nothing else should be.
    check("...only the title menu and the slot question did",
          sorted({entry[1].strip() for entry in asked}),
          ["Which save slot?", "Your Option:"])
    check("closing the window lets the engine move on",
          closed.get("pending") in (None, "generic"))

    check("the career did not go to the log",
          "has participated the Pokemon Championship" not in log)
    check("nor the win rate line", "Win Rate:" not in log)
    check("nor the champion roll",
          "The Champion of the Pokemon Championship" not in log)
    # Match the roster's actual lines, not just "a line starting with 1: ".
    # The slot picker prints "1: Slot 1: ..." now, so the loose version was
    # tripping on a menu the player is supposed to see rather than on the
    # history screen's competitor list it was written to catch.
    roster_lines = ["%s: %s" % (entry["index"], entry["nickname"])
                    for entry in (w.game_state.get("career_roster") or [])]
    check("nor the numbered roster",
          [line for line in roster_lines if chr(10) + line in log], [])
    check("no errors", len(errors), 0)

    lines = ["stopped: %s after %d ticks (step %d)" % (why, st["n"],
                                                       st["step"]), ""]
    lines += st["log"]
    lines += ["", "questions the player saw: %r" % (asked[:6],)]
    lines += errors[:2]
    with open(os.path.join(OUT, "career.txt"), "w", encoding="utf-8") as fh:
        fh.write(chr(10).join(lines) + chr(10))
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
sys.exit(1 if fails else 0)
