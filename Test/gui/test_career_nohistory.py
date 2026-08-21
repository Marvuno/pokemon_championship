"""A competitor with nothing on record must not inherit the last one's.

The engine skips the head-to-head table entirely for someone who has never
played -- competitor_report() returns False and individual_records() is never
called -- so nothing arrives to overwrite the previous competitor's tabs.
This is the case the window has to clear for itself.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel                # noqa: E402

from GUI_qt.fonts import Fonts                                    # noqa: E402
from GUI_qt.panels import CareerDialog                            # noqa: E402

app = QApplication.instance() or QApplication([])
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


d = CareerDialog(Fonts(), ROOT)


def tab(title):
    for index in range(d.tabs.count()):
        if d.tabs.tabText(index) == title:
            return " | ".join(c.text() for c in
                              d.tabs.widget(index).findChildren(QLabel)
                              if c.text())
    return ""


VETERAN = {
    "nickname": "Expert Cynthia", "tier": "Elite", "rating": 346,
    "participation": 22, "championship": 3, "wins": 74, "losses": 51,
    "win_rate": 59.2,
    "runs": [{"run": n, "rank": r, "champion": "Marvin"} for n, r in
             enumerate([1, 4, 12], start=1)],
    "most_played": [{"nickname": "Marvin", "wins": 5, "losses": 6,
                     "rating": 415}],
    "art": "",
}
RECORDS = {"nickname": "Expert Cynthia",
           "rows": [{"nickname": "Champion Marvin", "wins": 1, "losses": 8,
                     "rating": 750, "win_rate": 11},
                    {"nickname": "Goblin", "wins": 9, "losses": 0,
                     "rating": 1, "win_rate": 100}]}
NEWCOMER = {"nickname": "Rudolf", "tier": "Advanced", "rating": 118,
            "participation": 0, "championship": 0, "wins": 0, "losses": 0,
            "win_rate": None, "runs": [], "most_played": [], "art": ""}

# ---------------------------------------------------- a full career first
d.show_report(VETERAN)
d.show_records(RECORDS)
app.processEvents()
check("the veteran's career is shown", "59.2%" in tab("Career"))
check("...their runs", "RANK 1" in tab("Tournaments"))
check("...and their head to head", "Champion Marvin" in tab("Head to Head"))
check("head to head is rating-ordered (hardest first)",
      tab("Head to Head").index("Champion Marvin")
      < tab("Head to Head").index("Goblin"))
check("...and shows the ratings it sorted by", "[750]" in tab("Head to Head"))

# -------------------------------------- now somebody who has never played
d.show_report(NEWCOMER)
app.processEvents()
career, runs, records = tab("Career"), tab("Tournaments"), tab("Head to Head")

check("the newcomer's name is shown", "Rudolf" in career)
check("the career says there is no history",
      "no match history on record for Rudolf" in career)
check("...and shows a dash for the win rate", "—" in career)
check("the tournaments tab says they have entered none",
      "not entered a championship" in runs)
check("the head to head tab says so too",
      "no match history on record for Rudolf" in records)

check("none of the veteran's numbers survived in Career",
      not any(bit in career for bit in ("59.2", "74", "51", "Cynthia")))
check("...nor in Tournaments",
      not any(bit in runs for bit in ("RANK 1", "rank 4", "BEST FINISH")))
check("...nor in Head to Head",
      not any(bit in records for bit in ("Champion Marvin", "Goblin",
                                        "[750]")))

# ------------------------------------------- and back to a real one again
d.show_report(VETERAN)
d.show_records(RECORDS)
app.processEvents()
check("a real career fills back in", "59.2%" in tab("Career"))
check("...and the newcomer's notes are gone",
      "Rudolf" not in tab("Career") + tab("Tournaments") + tab("Head to Head"))

# --------------------------------------------------- an empty payload too
try:
    d.show_report({})
    d.show_records({})
    d.show_runs([], "nobody")
    d.show_champions([])
    d.show_roster([])
    app.processEvents()
    check("empty payloads do not crash", True)
except Exception as error:
    check("empty payloads do not crash", False, repr(error))

print("\n" + ("ALL PASS" if not fails else "%d FAILURES: %s"
                                           % (len(fails), fails)))
sys.exit(1 if fails else 0)
