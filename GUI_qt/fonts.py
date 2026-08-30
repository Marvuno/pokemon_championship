"""
Resolves GUI/theme.py's font stacks into real QFonts, once, at one scale.

Everything a widget needs is a named attribute here (fonts.body,
fonts.eyebrow, ...) so widget code never picks a family or a point size
itself -- that's what kept the Tkinter POC's paintEvents short, and it's
also the whole mechanism behind the UI-scale setting: change `scale` here
and every widget in the app resizes, because they all read from this one
object instead of hard-coding numbers.
"""

import os

from PySide6.QtGui import QFont, QFontDatabase

from GUI import theme as T

#: the four sizes exposed in Settings (see GUI_qt/settings.py, Phase 5)
SCALE_STEPS = {"90%": 0.9, "100%": 1.0, "115%": 1.15, "130%": 1.3}


#: Where a font the game ships with lives. Fredoka and Nunito are not on any
#: machine by default -- they are Google fonts, both under the SIL Open Font
#: License, which is what makes it fine to carry them here -- so without this
#: naming them in a stack would silently fall through to the next entry and
#: nothing would change.
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))), "Assets", "fonts")

_loaded = False


def load_bundled():
    """Register every font file in Assets/fonts with Qt. Idempotent.

    Called before any Fonts() is built. A file that will not load is skipped
    rather than raised on: a missing typeface should cost the game its look,
    never its start.
    """
    global _loaded
    if _loaded:
        return
    _loaded = True
    if not os.path.isdir(FONT_DIR):
        return
    for name in sorted(os.listdir(FONT_DIR)):
        if name.lower().endswith((".ttf", ".otf")):
            try:
                QFontDatabase.addApplicationFont(os.path.join(FONT_DIR, name))
            except Exception:
                pass


def _pick_installed(stack):
    load_bundled()
    installed = {f.lower() for f in QFontDatabase.families()}
    return next((name for name in stack if name.lower() in installed),
               stack[-1])


class Fonts:
    def __init__(self, scale=1.0):
        self.scale = scale
        display = _pick_installed(T.FONT_STACKS["display"])
        ui = _pick_installed(T.FONT_STACKS["ui"])
        mono = _pick_installed(T.FONT_STACKS["mono"])

        def make(family, size, weight=QFont.Normal, spacing=0.0):
            f = QFont(family)
            f.setPointSizeF(size * scale)
            f.setWeight(weight)
            if spacing:
                f.setLetterSpacing(QFont.AbsoluteSpacing, spacing * scale)
            return f

        # Fredoka Medium, Nunito SemiBold: both are real faces in the files
        # bundled under Assets/fonts, so Qt picks the drawn weight rather
        # than thickening a lighter one itself. Asking for a weight a family
        # does not have is where synthesised bold comes from, and it always
        # looks muddy next to the real thing.
        self.hero        = make(display, T.SZ_HERO, QFont.Medium)
        self.title       = make(display, T.SZ_TITLE, QFont.Medium)
        self.lead        = make(display, T.SZ_LEAD, QFont.Medium)
        self.eyebrow     = make(ui, T.SZ_EYEBROW, QFont.Bold, spacing=1.3)
        self.body        = make(ui, T.SZ_BODY, QFont.DemiBold)
        self.body_bold   = make(ui, T.SZ_BODY, QFont.Bold)
        self.tiny        = make(ui, T.SZ_TINY, QFont.DemiBold)
        self.small       = make(ui, T.SZ_SMALL, QFont.DemiBold)
        self.small_bold  = make(ui, T.SZ_SMALL, QFont.Bold)
        self.log         = make(mono, T.SZ_SMALL)
        self.num         = make(mono, T.SZ_SMALL, QFont.DemiBold)
        self.num_big     = make(mono, T.SZ_LEAD, QFont.DemiBold)
