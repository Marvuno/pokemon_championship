"""Click a spread of real competitors in the HISTORY window, engine and all.

Replaces test_history_screen.py, which drove the screen the old way -- Y/N
prompts and a typed number -- and asserted on log text that is deliberately
quiet now. What matters here is unchanged: a competitor who has never played
must report that rather than crash the game (it used to raise
ZeroDivisionError computing a win rate over zero matches).
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
saveguard.install(ROOT, OUT, tag="career-engine")

from PySide6.QtCore import QTimer                              # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel             # noqa: E402

from GUI_qt.main_window import MainWindow                      # noqa: E402

app = QApplication.instance() or QApplication([])
errors, fails = [], []
sys.excepthook = lambda *e: errors.append("".join(
    traceback.format_exception(*e)))

w = MainWindow(ROOT)
w.show()
_orig_error = w._show_error
w._show_error = lambda p: (errors.append("EV_ERROR: %s" % p), _orig_error(p))

st = {"n": 0, "step": 0, "queue": [], "seen": [], "done": False, "log": [],
      "settle": 0}


def texts(title):
    d = w.career_dialog
    for index in range(d.tabs.count()):
        if d.tabs.tabText(index) == title:
            return " | ".join(c.text() for c in
                              d.tabs.widget(index).findChildren(QLabel)
                              if c.text())
    return ""


def tick():
    st["n"] += 1
    if st["n"] > 2500:
        return finish("step cap")
    app.processEvents()
    d = w.career_dialog

    if st["step"] == 0:
        # Getting to HISTORY takes two answers now -- the menu, then which of
        # the four save slots. Read the choices rather than hardcoding numbers:
        # this used to answer "3" and silently stopped working the moment
        # OPTIONS was removed from the menu and everything below it shifted up.
        if d.isVisible():
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

    if st["step"] == 1:
        if d.isVisible() and d._rows:
            roster = (w.game_state or {}).get("career_roster") or []
            # a spread across the field: the player, the very top and bottom
            # of the ratings, and a handful in between
            numbers = sorted(entry["index"] for entry in roster)
            step = max(1, len(numbers) // 6)
            st["queue"] = numbers[::step][:6]
            # ...and make sure at least one competitor with an empty record is
            # in the sample. On a save this deep nearly everybody has played,
            # so leaving it to chance skipped the case that used to crash.
            # The loaded records are in this process already, on the module
            # the worker thread imported -- read-only, which is safe.
            from Scripts.Data.competitors import list_of_competitors
            for entry in roster:
                comp = list_of_competitors.get(entry["name"])
                history = getattr(comp, "opponent_history", None) or {}
                if comp is not None and not any(sum(v[:2]) for v in
                                                history.values()):
                    if entry["index"] not in st["queue"]:
                        st["queue"].append(entry["index"])
                    st["expect_unplayed"] = entry["nickname"]
                    break
            st["step"] = 2
        return

    if st["step"] == 2:
        if not st["queue"]:
            st["step"] = 4
            return
        st["current"] = st["queue"].pop(0)
        st["before"] = (w.game_state or {}).get("career_report")
        d._on_pick(st["current"])
        st["step"], st["settle"] = 3, 0
        return

    if st["step"] == 3:
        st["settle"] += 1
        report = (w.game_state or {}).get("career_report")
        if report is not None and report is not st.get("before"):
            app.processEvents()
            st["seen"].append({
                "index": st["current"],
                "nickname": report.get("nickname"),
                "rate": report.get("win_rate"),
                "career": texts("Career"),
                "runs": texts("Tournaments"),
                "records": texts("Head to Head"),
            })
            st["step"] = 2
        elif st["settle"] > 250:
            st["seen"].append({"index": st["current"], "nickname": None})
            st["step"] = 2
        return

    if st["step"] == 4:
        d.close()
        st["step"], st["settle"] = 5, 0
        return
    if st["step"] == 5:
        st["settle"] += 1
        if st["settle"] > 40:
            return finish("clicked them all")
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
    seen = st["seen"]

    check("every competitor clicked reported back",
          [e for e in seen if e.get("nickname") is None], [])
    check("a spread of them was covered", len(seen) >= 6, True)

    played = [e for e in seen if e.get("rate") is not None]
    unplayed = [e for e in seen if e.get("rate") is None
                and e.get("nickname")]
    check("some had a record (%d of %d)" % (len(played), len(seen)),
          bool(played))
    for entry in played:
        check("  %s: career filled" % entry["nickname"],
              "%" in entry["career"])
        check("  %s: head to head filled" % entry["nickname"],
              " W  " in entry["records"])
    # Someone drawn into the bracket for the first time has played nobody --
    # the case that used to raise ZeroDivisionError on the win rate.
    if unplayed:
        for entry in unplayed:
            check("  %s: says there is no history" % entry["nickname"],
                  "no match history on record" in entry["career"])
            check("  %s: no stale table left behind" % entry["nickname"],
                  " W  " not in entry["records"])
    # Whether the save *has* an unplayed competitor is a property of the save,
    # not of the code -- after enough runs everyone has a record. So this is
    # reported, not asserted; the "no history" rendering itself is covered
    # deterministically by test_career_nohistory.
    if not unplayed:
        st["log"].append("%-58s %s"
                         % ("(this save has a record for every competitor)",
                            "SKIP"))
    check("no errors", len(errors), 0)

    lines = ["stopped: %s after %d ticks" % (why, st["n"]), ""]
    lines += st["log"]
    lines += ["", "clicked: %r" % [(e["index"], e.get("nickname"),
                                    e.get("rate")) for e in seen]]
    lines += errors[:2]
    with open(os.path.join(OUT, "career_engine.txt"), "w",
              encoding="utf-8") as fh:
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
QTimer.singleShot(180000, lambda: finish("wall clock"))
app.exec()
sys.exit(1 if fails else 0)
