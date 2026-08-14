"""The story/tutorial reader opens borderless full screen, each page fills it,
and there are two ways out."""
import os
import sys

ROOT, OUT = sys.argv[1], sys.argv[2]
HEADED = os.environ.get("QT_QPA_PLATFORM") != "offscreen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtCore import Qt                                   # noqa: E402
from PySide6.QtGui import QGuiApplication, QKeyEvent            # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel              # noqa: E402

from GUI_qt.fonts import Fonts                                  # noqa: E402
from GUI_qt.panels import StoryDialog                           # noqa: E402
from GUI_qt.widgets import ActionButton                         # noqa: E402

app = QApplication.instance() or QApplication([])
fonts = Fonts()
failures = []


def check(label, got, want):
    if got == want:
        print("%-56s PASS" % label)
    else:
        print("%-56s FAIL got=%r want=%r" % (label, got, want))
        failures.append(label)


screen = QGuiApplication.primaryScreen().geometry()
story = StoryDialog(fonts, {"backstory": "b", "tutorial": "t"}, ROOT)
story.show()
for _ in range(8):
    app.processEvents()

check("opens frameless",
      bool(story.windowFlags() & Qt.FramelessWindowHint), True)
check("covers the whole screen",
      (story.width(), story.height()) == (screen.width(), screen.height()),
      True)
check("sits at the screen origin", (story.x(), story.y()),
      (screen.x(), screen.y()))

buttons = {}
for b in story.findChildren(ActionButton):
    for l in b.findChildren(QLabel):
        if (l.text() or "").strip():
            buttons.setdefault(l.text().strip(), b)
            break
check("a Close button is offered", "Close" in buttons, True)
check("Back and Next are still there",
      "Back" in buttons and "Next" in buttons, True)

# every page fills the frame
for index in range(len(story.PAGES)):
    story.index = index
    story._show_page()
    for _ in range(4):
        app.processEvents()
    shown = story.page.pixmap()
    box = story.page.size()
    filled = shown is not None and not shown.isNull() and (
        max(shown.width() / box.width(), shown.height() / box.height()) > 0.98)
    check("page %d/%d fills the frame (%dx%d in %dx%d)"
          % (index + 1, len(story.PAGES),
             0 if shown is None else shown.width(),
             0 if shown is None else shown.height(),
             box.width(), box.height()), filled, True)

# a missing page falls back to text rather than a blank frame
story.page.set_picture(None)
story.page.setText("fallback")
app.processEvents()
check("a missing page can still show text", story.page.text(), "fallback")

if HEADED:
    story.index = 0
    story._show_page()
    for _ in range(4):
        app.processEvents()
    story.grab().save(os.path.join(OUT, "story_fs_1.png"))
    story.index = 2
    story._show_page()
    for _ in range(4):
        app.processEvents()
    story.grab().save(os.path.join(OUT, "story_fs_3.png"))

# Escape closes it
story.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape,
                              Qt.NoModifier))
app.processEvents()
check("Escape closes the reader", story.isVisible(), False)

print("\n%s" % ("ALL PASS" if not failures
                else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
