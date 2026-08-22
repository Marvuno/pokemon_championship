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


# ------------------------------------------------------ 1. the two readers
# Background and Tutorial used to be one five-page reader. They are two now,
# because wanting a rules reminder should not mean paging past the lore --
# so what this checks is that each is a complete reader in its own right.
story = StoryDialog(w.fonts, {"backstory": "b", "tutorial": "t"}, ROOT,
                    pages=StoryDialog.BACKGROUND_PAGES)
story.resize(1020, 660)
story.show()
app.processEvents()
check("the background reader has six pages", len(story.PAGES), 6)
check("...all of them BKGD art",
      [p[0] for p in story.PAGES],
      ["BKGD_%d.jpg" % n for n in range(1, 7)])
check("the tutorial reader has five",
      len(StoryDialog.TUTORIAL_PAGES), 5)
check("...all of them TUT art",
      [p[0] for p in StoryDialog.TUTORIAL_PAGES],
      ["TUT_%d.jpg" % n for n in range(1, 6)])
check("opens on page 1", story.counter.text(), "1 / 6")
check("Back is disabled at the start", story.back.disabled, True)
check("Next is enabled at the start", story.forward.disabled, False)
check("page 1 shows artwork, not text",
      story.page.pixmap() is not None and not story.page.pixmap().isNull(),
      True)
for expected in ("2 / 6", "3 / 6", "4 / 6", "5 / 6", "6 / 6"):
    story.step(1)
    app.processEvents()
    if story.counter.text() != expected:
        check("paging forward reaches %s" % expected, story.counter.text(),
              expected)
        break
else:
    check("paging forward walks 1 -> 6", story.counter.text(), "6 / 6")
check("Next disabled on the last page, unguided", story.forward.disabled,
      True)
check("Back enabled on the last page", story.back.disabled, False)
story.step(1)
check("Next past the end does nothing", story.counter.text(), "6 / 6")
if HEADED:
    story.grab().save(os.path.join(OUT, "story_page6.png"))
for _ in range(8):
    story.step(-1)
check("Back past the start does nothing", story.counter.text(), "1 / 6")

# Guided: a new player is walked through, and the last page's Next becomes
# the way on rather than going dead. Every way out has to report, because
# the engine is blocked on a keypress behind it.
for exit_name, leave in (("Continue on the last page",
                          lambda d: d.step(1)),
                         ("the Close button", lambda d: d.finish()),
                         ("closing the window", lambda d: d.close())):
    done = []
    guided = StoryDialog(w.fonts, {}, ROOT,
                         pages=StoryDialog.TUTORIAL_PAGES,
                         on_finish=lambda: done.append(1))
    guided.show()
    app.processEvents()
    for _ in range(len(guided.PAGES) - 1):
        guided.step(1)
    check("guided: last page offers Continue", guided.forward.title,
          "Continue")
    leave(guided)
    app.processEvents()
    check("guided: %s reports exactly once" % exit_name, done, [1])
    leave(guided)                       # and never twice
    check("guided: %s does not report twice" % exit_name, done, [1])

check("every page has artwork on disk",
      all(os.path.exists(os.path.join(ROOT, "Assets", "generated", p[0]))
          for p in StoryDialog.BACKGROUND_PAGES
          + StoryDialog.TUTORIAL_PAGES), True)

# ---------------------------------------------------- 1b. who you are
# One screen: five portraits with both gender buttons under them. The engine
# still asks two questions; the window never draws the first one.
from GUI_qt.panels import AppearanceDialog                          # noqa: E402

picker = AppearanceDialog(w.fonts, ROOT)
chosen, switched = [], []
MALE = ["Male %d" % n for n in range(1, 6)]
FEMALE = ["Female %d" % n for n in range(1, 6)]

picker.ask_portrait(["Male", "Female"], 0, MALE, chosen.append,
                    switched.append)
app.processEvents()
check("it opens straight onto the portraits", picker.heading.text(),
      "Choose your appearance")
check("all five are shown at once", len(picker._slots), 5)
check("both gender buttons are there", len(picker._gender_buttons), 2)

# the one thing this screen must not do is move when the gender changes
def geometry():
    return [art.parentWidget().geometry().getRect()
            for art in picker._slots]

before = geometry()
pictures_before = [art.pixmap().cacheKey() if art.pixmap() else None
                   for art in picker._slots]
picker._switch(1)
check("pressing the other gender asks for it", switched, [1])
picker.ask_portrait(["Male", "Female"], 1, FEMALE, chosen.append,
                    switched.append)
app.processEvents()
check("nothing moves when the gender changes", geometry(), before)
check("...but the portraits do change",
      [art.pixmap().cacheKey() if art.pixmap() else None
       for art in picker._slots] != pictures_before, True)
# and no name is written under any of them -- the picture is the choice
check("the portraits are unlabelled",
      [art.text() for art in picker._slots], [""] * 5)
check("pressing the gender already showing does nothing",
      (picker._switch(1), switched)[1], [1])
check("nothing is committed by switching", chosen, [])

picker._take(3)
check("clicking a portrait answers with its index", chosen, ["3"])
check("...and there is no going back after it", picker._locked, True)
picker._switch(0)
check("...not even the gender buttons", switched, [1])
check("every portrait exists on disk",
      all(os.path.exists(os.path.join(ROOT, "Assets", "Player",
                                      "%s %d.jpg" % (g, n)))
          for g in ("Male", "Female") for n in range(1, 6)), True)
picker.close()

# --- no dialog may refuse to close ----------------------------------------
# A closeEvent that calls event.ignore() blocks QApplication.quit(): the
# event loop never returns and the process hangs. AppearanceDialog had one,
# to stop the player walking away from a question the engine loops on, and it
# hung the playthrough harness for thirty minutes -- the run finished and
# wrote its report, and only the shutdown stuck. Escape is the right place to
# refuse; closeEvent never is.
import GUI_qt.panels as PANELS                                      # noqa: E402
from PySide6.QtWidgets import QDialog                               # noqa: E402

stubborn = []
for _name in dir(PANELS):
    _cls = getattr(PANELS, _name)
    if not (isinstance(_cls, type) and issubclass(_cls, QDialog)):
        continue
    _own = _cls.__dict__.get("closeEvent")
    import inspect                                                  # noqa: E402
    # only ones written in Python here -- a class that inherits Qt's own
    # closeEvent has a C++ method_descriptor, which has no source to read
    if not inspect.isfunction(_own):
        continue
    _src = inspect.getsource(_own)
    _code = chr(10).join(l.split("#", 1)[0] for l in _src.splitlines())
    if "ignore()" in _code:
        stubborn.append(_name)
check("no dialog refuses to close", stubborn, [])
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
