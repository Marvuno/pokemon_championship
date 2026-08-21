"""Checks for this batch: the story reader, the competitor portrait, the
opponent-team gate, and the reworked scouting."""
import os
import sys

ROOT, OUT = sys.argv[1], sys.argv[2]
HEADED = os.environ.get("QT_QPA_PLATFORM") != "offscreen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel                # noqa: E402

from GUI import bridge as B                                       # noqa: E402
B.Bridge.start = lambda self: None

from GUI_qt import main_window as MW                              # noqa: E402
from GUI_qt.panels import OpponentInfoDialog, StoryDialog         # noqa: E402

app = QApplication.instance() or QApplication([])
w = MW.MainWindow(ROOT)
w.show()

failures = []


def check(label, got, want):
    if got == want:
        print("%-54s PASS" % label)
    else:
        print("%-54s FAIL got=%r want=%r" % (label, got, want))
        failures.append(label)


# ------------------------------------------------------ 1. the story reader
story = StoryDialog(w.fonts, {"backstory": "b", "tutorial": "t"}, ROOT)
story.resize(1020, 660)
story.show()
app.processEvents()
check("reader has five pages", len(story.PAGES), 5)
check("page order starts on the background",
      [p[0] for p in story.PAGES],
      ["Background.jpg", "Tutorial_1.jpg", "Tutorial_2.jpg",
       "Tutorial_3.jpg", "Tutorial_4.jpg"])
check("opens on page 1", story.counter.text(), "1 / 5")
check("Back is disabled at the start", story.back.disabled, True)
check("Next is enabled at the start", story.forward.disabled, False)
check("page 1 shows artwork, not text",
      story.page.pixmap() is not None and not story.page.pixmap().isNull(),
      True)
for expected in ("2 / 5", "3 / 5", "4 / 5", "5 / 5"):
    story.step(1)
    app.processEvents()
    if story.counter.text() != expected:
        check("paging forward reaches %s" % expected, story.counter.text(),
              expected)
        break
else:
    check("paging forward walks 1 -> 5", story.counter.text(), "5 / 5")
check("Next disabled on the last page", story.forward.disabled, True)
check("Back enabled on the last page", story.back.disabled, False)
story.step(1)
check("Next past the end does nothing", story.counter.text(), "5 / 5")
if HEADED:
    story.grab().save(os.path.join(OUT, "story_page5.png"))
for _ in range(6):
    story.step(-1)
check("Back past the start does nothing", story.counter.text(), "1 / 5")
check("every page has artwork on disk",
      all(os.path.exists(os.path.join(ROOT, "Assets", "generated", p[0]))
          for p in story.PAGES), True)
if HEADED:
    story.grab().save(os.path.join(OUT, "story_page1.png"))
story.close()

# ------------------------------------------- 2. the competitor portrait
art = B.character_art(type("C", (), {"name": "Magnus Carlsen",
                                     "nickname": "Magnus Carlsen"})())
check("character art resolves for a competitor",
      art, os.path.join("Assets", "characters", "Magnus Carlsen.jpg"))
# The resolver tries .jpg, then .png, then .jpeg, because the folder has
# always been a mix. This used to assert that "Vardy" came back as a .png,
# which stopped being true the day that portrait was re-saved as a .jpg --
# the check was pinned to one file's extension rather than to the behaviour.
# A throwaway fixture tests the behaviour and cannot go stale.
_png = os.path.join(ROOT, "Assets", "characters", "_ExtensionProbe.png")
try:
    with open(_png, "wb") as _handle:
        _handle.write(b"not really a png")
    check("a competitor whose portrait is a .png resolves too",
          B.character_art(type("C", (), {"name": "_ExtensionProbe",
                                         "nickname": "_ExtensionProbe"})()),
          os.path.join("Assets", "characters", "_ExtensionProbe.png"))
finally:
    if os.path.exists(_png):
        os.remove(_png)
check("and the fixture is cleaned up after itself",
      os.path.exists(_png), False)
check("an unknown competitor gives no path",
      B.character_art(type("C", (), {"name": "Nobody",
                                     "nickname": "Nobody"})()), "")

info = {"nickname": "Magnus Carlsen", "tier": "Elite", "art": art,
        "description": "One of the Lower Elite Four.",
        "strategy_revealed": True, "strategy": "Blunders.",
        "scouted_text": "You have sized up their entire team.",
        "scout_failed": False}
dialog = OpponentInfoDialog(info, w.fonts, ROOT)
dialog.resize(760, 560)
dialog.show()
app.processEvents()
pixmaps = [l for l in dialog.findChildren(QLabel)
           if l.pixmap() is not None and not l.pixmap().isNull()]
check("the report shows the portrait", len(pixmaps) >= 1, True)
if HEADED:
    dialog.grab().save(os.path.join(OUT, "about_opponent.png"))
dialog.close()

# ------------------------------------------- 3. the opponent-team gate
THEIRS = [{"name": "Metagross", "sprite": "metagross", "types": ["Steel"],
           "tier": "Ultra High", "ability": ["Clear Body"], "status": "Normal",
           "hp": 100, "max_hp": 100, "stats": [], "nominal": [90] * 6,
           "iv": [10] * 6, "total": 600, "total_iv": 60, "modifier": [0] * 9,
           "volatile": {}, "moveset": ["Switching"], "moves": {},
           "disabled": {}, "charging": ["", "", 0], "protecting": False,
           "fainted": False, "active": False}]

w._apply_state({"phase": "battle", "player_roster": [],
                "opponent_roster": None, "opponent_known": False})
app.processEvents()
w.roster_dialog.show_side("opponent")
app.processEvents()
texts = " | ".join(l.text() for l in w.roster_dialog.findChildren(QLabel)
                   if l.text())
check("their team is hidden by default",
      len(w.roster_dialog.rosters["opponent"]), 0)
check("...and says how to earn it", "Not scouted yet" in texts, True)
# the two teams share one list now, so their heading is present either way
check("...with both teams headed on the one rail",
      "YOUR TEAM" in texts and "OPPONENT TEAM" in texts, True)

w._apply_state({"phase": "battle", "player_roster": [],
                "opponent_roster": THEIRS, "opponent_known": True})
app.processEvents()
check("a successful scout reveals it",
      [m["name"] for m in w.roster_dialog.rosters["opponent"]], ["Metagross"])

# and it goes away again next match
w._apply_state({"phase": "battle", "player_roster": [],
                "opponent_roster": None, "opponent_known": False})
app.processEvents()
check("the next match hides it again",
      len(w.roster_dialog.rosters["opponent"]), 0)
w.roster_dialog.close()

print("\n%s" % ("ALL PASS" if not failures
                else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
