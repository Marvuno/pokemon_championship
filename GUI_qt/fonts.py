"""
Resolves GUI/theme.py's font stacks into real QFonts, once, at one scale.

Everything a widget needs is a named attribute here (fonts.body,
fonts.eyebrow, ...) so widget code never picks a family or a point size
itself -- that's what kept the Tkinter POC's paintEvents short, and it's
also the whole mechanism behind the UI-scale setting: change `scale` here
and every widget in the app resizes, because they all read from this one
object instead of hard-coding numbers.
"""

from PySide6.QtGui import QFont, QFontDatabase

from GUI import theme as T

#: the four sizes exposed in Settings (see GUI_qt/settings.py, Phase 5)
SCALE_STEPS = {"90%": 0.9, "100%": 1.0, "115%": 1.15, "130%": 1.3}


def _pick_installed(stack):
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

        self.hero        = make(display, T.SZ_HERO, QFont.Bold)
        self.title       = make(display, T.SZ_TITLE, QFont.Bold)
        self.lead        = make(display, T.SZ_LEAD, QFont.DemiBold)
        self.eyebrow     = make(ui, T.SZ_EYEBROW, QFont.Bold, spacing=1.3)
        self.body        = make(ui, T.SZ_BODY)
        self.body_bold   = make(ui, T.SZ_BODY, QFont.DemiBold)
        self.tiny        = make(ui, T.SZ_TINY)
        self.small       = make(ui, T.SZ_SMALL)
        self.small_bold  = make(ui, T.SZ_SMALL, QFont.DemiBold)
        self.log         = make(mono, T.SZ_SMALL)
        self.num         = make(mono, T.SZ_SMALL, QFont.DemiBold)
        self.num_big     = make(mono, T.SZ_LEAD, QFont.DemiBold)
