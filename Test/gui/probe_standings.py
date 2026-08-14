"""Render the standings dialog with synthetic data to check the ratings now
show on both the matchups and the per-round results."""
import os
import sys

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel        # noqa: E402

from GUI_qt.fonts import Fonts                            # noqa: E402
from GUI_qt.panels import StandingsDialog                 # noqa: E402

app = QApplication.instance() or QApplication([])
fonts = Fonts()
d = StandingsDialog(fonts)

NAMES = [("Marvin", 421, True), ("Champion Marvin", 750, False),
         ("Mivy Wenceslas", 200, False), ("Elias Ainsworth", 232, False),
         ("Magnus Carlsen", 288, False), ("Reaper Conan", 321, False),
         ("Aphelios", 40, False), ("Big Bryan", 37, False)]

bracket = {"round": 3, "pairs": [
    [{"nickname": n, "strength": s, "color": "", "championship": 0,
      "wins": 2, "score": 3, "is_player": p}
     for n, s, p in NAMES[i:i + 2]] for i in (0, 2, 4, 6)]}

results = [{"round": 3, "pairs": [
    [{"nickname": NAMES[i][0], "strength": NAMES[i][1], "points": 2,
      "score": 6, "is_player": NAMES[i][2], "upset": i == 2},
     {"nickname": NAMES[i + 1][0], "strength": NAMES[i + 1][1], "points": 1,
      "score": 4, "is_player": NAMES[i + 1][2], "upset": False}]
    for i in (0, 2, 4, 6)]}]

leaderboard = [{"nickname": n, "strength": s, "stage": 3, "opponent_score": 12,
                "score": 5, "championship": 1 if "Champion" in n else 0,
                "is_player": p, "rank": i + 1}
               for i, (n, s, p) in enumerate(NAMES)]

d.refresh(bracket, leaderboard, [], False, rating=421, rating_change=18,
          rating_before=403, round_results=results)
d.resize(980, 620)
d.show()
app.processEvents()

for title in ("Matchups", "Round 3", "Leaderboard"):
    d.select(title)
    app.processEvents()
    d.grab().save(os.path.join(OUT, "standings_%s.png"
                               % title.replace(" ", "").lower()))
    texts = [l.text() for l in d.findChildren(QLabel) if l.isVisible()
             and l.text()]
    rated = [t for t in texts if "[" in t and "]" in t]
    print("%-12s labels with a rating: %s" % (title, rated[:6]))
