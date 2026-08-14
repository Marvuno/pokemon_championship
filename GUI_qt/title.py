"""
The out-of-battle backdrop.

The arena (HP bars, sprites, type chips) only means anything while a match is
actually being fought, but it used to be the single permanent view -- so the
main menu, the pre-battle options, the team screens and the final standings
were all shown against a stale battle board holding whatever Pokemon happened
to be out last. This is the other view.

The wallpaper (Assets/generated/title_wallpaper.png) is finished artwork --
stadium, banners, confetti, light and all -- so this draws nothing over it
beyond a veil to keep the text legible. It used to paint its own waving
flags, drifting motes and a breathing rule, which suited the earlier, plainer
backdrop but only fought this one -- which is also why there is no
reduced-motion switch any more: nothing on this screen moves. The panel offers
the reference screens (story, standings, your team) directly rather than
making the player hunt for them in the header.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from GUI import theme as T
from GUI_qt.widgets import ActionButton, label

#: phase -> the line under the title
PHASE_HEADLINES = {
    "menu": "Main Menu",
    "prebattle": "Next Match",
    "manage": "Team Management",
    "leaderboard": "Final Standings",
}

PHASE_HINTS = {
    "menu": "Choose an option below to begin — or read up on the world first.",
    "prebattle": "Scout your opponent, check the head-to-head, or go straight "
                 "into battle.",
    "manage": "Pick the Pokemon you want to take forward.",
    "leaderboard": "The tournament is over — see how everyone finished.",
}


class TitleView(QWidget):
    """Wallpaper, game title, where-you-are line, and the reference buttons."""

    def __init__(self, fonts, project_root, parent=None, on_story=None,
                on_standings=None, on_team=None):
        super().__init__(parent)
        self._pixmap = QPixmap(os.path.join(
            project_root, "Assets", "generated", "title_wallpaper.png"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 22)
        layout.setSpacing(4)
        layout.addStretch(3)
        centre = Qt.AlignCenter
        layout.addWidget(label("WORLD CHAMPIONSHIP", fonts.eyebrow, T.ACCENT,
                               align=centre))
        layout.addWidget(label("POKEMON CHAMPION", fonts.hero, T.TEXT,
                               align=centre))
        self.headline = label("", fonts.title, T.CYAN, align=centre)
        layout.addWidget(self.headline)
        self.hint = label("", fonts.body, T.TEXT_DIM, wrap=True, align=centre)
        layout.addWidget(self.hint)
        layout.addStretch(2)

        # The reference screens, offered right here. They were only reachable
        # from the header strip, which is easy to miss and reads as chrome.
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        for text, sub, accent, handler in (
                ("Story & Guide", "world · how to play", T.ACCENT,
                 on_story),
                ("Standings", "matchups · leaderboard", T.VIOLET,
                 on_standings),
                ("Your Team", "your Pokemon", T.CYAN, on_team)):
            if handler is None:
                continue
            button = ActionButton(text, fonts, sub=sub, accent=accent,
                                  on_click=handler)
            button.setMinimumWidth(190)
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

    def set_context(self, phase, state):
        headline = PHASE_HEADLINES.get(phase, "Pokemon Championship")
        hint = PHASE_HINTS.get(phase, "")

        stage = (state or {}).get("stage")
        you = (state or {}).get("player_side") or {}
        opponent = (state or {}).get("opponent_side") or {}
        if phase == "prebattle" and you and opponent:
            headline = "Round %s — %s vs %s" % (
                stage, you.get("nickname", "You"),
                opponent.get("nickname", "Opponent"))
        elif phase not in PHASE_HEADLINES and stage:
            headline = "Round %s" % stage

        self.headline.setText(headline)
        self.hint.setText(hint)

    # -- painting ---------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        if self._pixmap.isNull():
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            gradient.setColorAt(0.0, QColor("#2E63C8"))
            gradient.setColorAt(1.0, QColor(T.BG))
            painter.fillRect(rect, gradient)
        else:
            # cover, not stretch: fill and centre-crop, so the artwork keeps
            # its proportions at any window size
            scaled = self._pixmap.scaled(rect.size(),
                                         Qt.KeepAspectRatioByExpanding,
                                         Qt.SmoothTransformation)
            x = (scaled.width() - rect.width()) // 2
            y = (scaled.height() - rect.height()) // 2
            painter.drawPixmap(rect, scaled,
                               scaled.rect().adjusted(x, y, -x, -y))
            # A light veil, not a blackout. The old backdrop was dim enough
            # to need heavy dimming on top; this one is a lit stadium, so it
            # only needs enough to keep the title legible -- and the shade
            # deepens toward the bottom, where the text and buttons sit.
            veil = QLinearGradient(0.0, 0.0, 0.0, float(rect.height()))
            veil.setColorAt(0.0, QColor(8, 20, 52, 70))
            veil.setColorAt(0.45, QColor(8, 20, 52, 120))
            veil.setColorAt(1.0, QColor(8, 20, 52, 190))
            painter.fillRect(rect, veil)
