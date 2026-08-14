"""The reworked in-game Check History: head-to-head and the scoreline of
every meeting, and nothing else. Also checks the bridge publishes that shape
from the engine's own attributes."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel, QScrollArea  # noqa: E402

from GUI_qt.fonts import Fonts                                   # noqa: E402
from GUI_qt.panels import HistoryDialog                          # noqa: E402

app = QApplication.instance() or QApplication([])
fonts = Fonts()
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


def texts(dialog):
    return [w.text() for w in dialog.findChildren(QLabel) if w.text()]


#: one long-lived dialog now, refilled per look -- so is the real one
DIALOG = HistoryDialog(fonts)


def show(info):
    DIALOG.present(info)
    app.processEvents()
    return DIALOG


# ------------------------------------------------------------- a real record
INFO = {"you": "Marvin", "opponent": "Goblin", "wins": 2, "losses": 1,
        "meetings": [[4, 1], [6, 5], [2, 6]]}
d = show(INFO)
joined = " | ".join(texts(d))
check("both names shown", "Marvin" in joined and "Goblin" in joined)
check("the head-to-head record is shown", "2  –  1" in joined)
check("says how many meetings", "Met 3 times." in joined)
check("every scoreline is shown",
      all(s in joined for s in ("4  –  1", "6  –  5", "2  –  6")))
check("each meeting is numbered", all("#%d" % n in joined for n in (1, 2, 3)))
check("wins and losses are labelled",
      sorted(t for t in texts(d) if t in ("WON", "LOST")),
      ["LOST", "WON", "WON"])
check("the meetings list scrolls rather than clipping",
      d.scroll.isVisible())
check("no career journey is shown",
      not any(w in joined.lower() for w in ("journey", "round 1", "stage")))
check("no detailed-history offer", "detail" not in joined.lower())
d.close()

# --------------------------------------------------------- never faced them
d = show({"you": "Marvin", "opponent": "Rudolf", "wins": 0, "losses": 0,
          "meetings": []})
joined = " | ".join(texts(d))
check("a stranger is stated plainly",
      "You have never faced Rudolf before." in joined)
check("shown as 0 - 0", "0  –  0" in joined)
check("no meetings list at all", not d.scroll.isVisible())
d.close()

# -------------------------------------- an old save: a tally but no scores
d = show({"you": "Marvin", "opponent": "Goblin", "wins": 3, "losses": 2,
          "meetings": []})
joined = " | ".join(texts(d))
check("the tally still shows", "3  –  2" in joined)
check("and says the scorelines were not kept",
      "Scorelines were not recorded" in joined)
check("...and still says how many times", "Met 5 times" in joined)
check("no empty meetings list", not d.scroll.isVisible())
d.close()

# ------------------------------------- a payload missing everything optional
d = show({})
check("an empty payload does not crash", True)
check("...and falls back to placeholder names",
      "You" in " ".join(texts(d)))
d.close()

# ------------------------------------------------- what the bridge publishes
from GUI.bridge import Bridge                                    # noqa: E402
import Scripts.Game.before_battle as before                      # noqa: E402
from Scripts.Data.competitors import list_of_competitors         # noqa: E402

bridge = Bridge(ROOT)
published = {}
bridge.publish = lambda **kw: published.update(kw)

me = list_of_competitors["Protagonist"]
foe = [c for c in list_of_competitors.values() if not c.main][0]
me.nickname = "Marvin"
me.opponent_history[foe.name] = [2, 1]
me.opponent_scores[foe.name] = [[4, 1], [6, 5], [2, 6]]

import GUI.bridge as B                                           # noqa: E402
original = before.check_history
seen = []
before.check_history = lambda *a, **k: seen.append(a)
B.install_hooks(bridge, __import__("main"))
hook = before.check_history
hook(me, foe)
before.check_history = original

check("the hook published a payload", bool(published.get("history_info")))
payload = published.get("history_info") or {}
check("wins and losses come from opponent_history",
      (payload.get("wins"), payload.get("losses")), (2, 1))
check("the meetings come from opponent_scores",
      payload.get("meetings"), [[4, 1], [6, 5], [2, 6]])
check("both nicknames are published",
      (payload.get("you"), payload.get("opponent")), ("Marvin", foe.nickname))
check("nothing else is in the payload", sorted(payload),
      ["losses", "meetings", "opponent", "wins", "you"])
check("the engine's own function still ran", len(seen), 1)

# and the dialog renders exactly what the bridge sent
d = show(payload)
joined = " | ".join(texts(d))
check("the dialog renders the published payload",
      "2  –  1" in joined and "6  –  5" in joined)
d.close()

# an opponent with no record at all, straight through the bridge
published.clear()
stranger = [c for c in list_of_competitors.values() if not c.main][1]
hook = before.check_history if before.check_history is not original else hook
hook(me, stranger)
payload = published.get("history_info") or {}
check("a stranger publishes a clean 0-0",
      (payload.get("wins"), payload.get("losses"), payload.get("meetings")),
      (0, 0, []))

print("\n" + ("ALL PASS" if not fails else "%d FAILURES: %s"
                                           % (len(fails), fails)))
sys.exit(1 if fails else 0)
