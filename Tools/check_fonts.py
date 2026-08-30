"""Which typefaces the game will actually use, and why.

A font stack falls through silently: name a family that is not installed and
the next one is used with nothing said. This prints what each role resolves
to, so "I dropped the files in, did it work" has an answer.

    python Tools/check_fonts.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
# no window, and no sound, for a script that only reads the font database
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

from PySide6.QtWidgets import QApplication                        # noqa: E402

app = QApplication.instance() or QApplication([])

from GUI import theme as T                                        # noqa: E402
from GUI_qt.fonts import FONT_DIR, Fonts, _pick_installed         # noqa: E402

print("bundled fonts in %s" % os.path.relpath(FONT_DIR, ROOT))
files = (sorted(name for name in os.listdir(FONT_DIR)
                if name.lower().endswith((".ttf", ".otf")))
         if os.path.isdir(FONT_DIR) else [])
for name in files:
    print("   %s" % name)
if not files:
    print("   (none -- the stacks below will fall through to what Windows has)")

print()
print("what each role resolves to")
for role in ("display", "ui", "mono"):
    stack = T.FONT_STACKS[role]
    chosen = _pick_installed(stack)
    mark = "" if chosen == stack[0] else "   <- wanted %r" % stack[0]
    print("   %-8s %-26s%s" % (role, chosen, mark))

print()
print("the sizes every widget reads")
fonts = Fonts()
for name in ("hero", "title", "lead", "eyebrow", "body", "body_bold",
             "small", "tiny", "log", "num_big"):
    font = getattr(fonts, name)
    print("   %-10s %-24s %5.1fpt  weight %d"
          % (name, font.family(), font.pointSizeF(), font.weight()))

# Under QT_QPA_PLATFORM=offscreen Qt reports a nearly empty font database, so
# everything falls through to the last entry in each stack. That is the test
# environment, not what a player sees -- run this from a normal terminal to
# get the real answer.
print()
print("note: run without QT_QPA_PLATFORM=offscreen for the real answer -- "
      "the headless platform reports almost no fonts.")
