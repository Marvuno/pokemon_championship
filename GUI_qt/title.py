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
from PySide6.QtWidgets import (QGraphicsDropShadowEffect,
                               QHBoxLayout, QVBoxLayout, QWidget)

from GUI import theme as T
from GUI_qt.widgets import ActionButton, WordArt, label

#: phase -> the line under the title
PHASE_HEADLINES = {
    "menu": "",
    "prebattle": "Next Match",
    "manage": "Team Management",
    "leaderboard": "Final Standings",
}

# No hint lines any more. "Scout your opponent, check the head-to-head, or go
# straight into battle" sat under a menu whose buttons already said Scout
# Opponent, Check History and Battle -- it restated them at greater length.


class TitleView(QWidget):
    """Wallpaper, game title, where-you-are line, and the reference buttons."""

    def __init__(self, fonts, project_root, parent=None, on_story=None,
                on_credits=None, on_standings=None, on_team=None):
        super().__init__(parent)
        self._pixmap = QPixmap(os.path.join(
            project_root, "Assets", "generated", "title_wallpaper.png"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 18, 26, 16)
        layout.setSpacing(4)
        centre = Qt.AlignCenter

        # The game's name goes along the top, small; the pairing takes the
        # middle of the screen, which is where the eye lands and where the
        # thing you are about to do belongs. They were the other way round --
        # the name occupying the centre at hero size while the matchup, the
        # only part that changes, was a line at the very top edge.

        # The matchup, built as artwork rather than a line of text: a small
        # gold round marker, your name, a large VS, then theirs. One label at
        # hero size said the same words but read as a caption laid over a
        # photograph -- stacking the parts gives each its own weight, and the
        # outlined gradient lettering (see WordArt) separates from the stadium
        # at every edge instead of relying on the backdrop being dark.
        # Which championship this is, as a banner across the top -- deep blue
        # into violet so it reads as the frame around the fight rather than
        # part of it, and wide tracking because a short line at the top edge
        # wants to span rather than huddle.
        self.meet_art = WordArt("", fonts.title, top="#DCE8FF",
                                bottom="#8AA6E8", tracking=5.0)
        self.round_art = WordArt("", fonts.small_bold, top="#FFE9A8",
                                 bottom="#F0B93C", tracking=3.4)
        self.you_art = WordArt("", fonts.title, top="#FFFFFF",
                               bottom="#A8D8FF")
        self.versus_art = WordArt("", fonts.hero, top="#FFF3C4",
                                  bottom="#E8912F", tracking=6.0)
        self.foe_art = WordArt("", fonts.title, top="#FFFFFF",
                               bottom="#FFB3AE")
        layout.addWidget(self.meet_art)
        layout.addStretch(3)
        for art in (self.round_art, self.you_art, self.versus_art,
                    self.foe_art):
            layout.addWidget(art)

        # The game's name, big, for when there is no matchup to show -- the
        # title screen. Hidden the moment a round is on.
        self.game_name = label("POKEMON CHAMPIONSHIP", fonts.hero, T.TEXT,
                               align=centre)
        halo = QGraphicsDropShadowEffect(self.game_name)
        halo.setBlurRadius(18)
        halo.setOffset(0, 3)
        halo.setColor(QColor(0, 0, 0, 235))
        self.game_name.setGraphicsEffect(halo)
        layout.addWidget(self.game_name)
        layout.addStretch(2)

        # The reference screens, offered right here. They were only reachable
        # from the header strip, which is easy to miss and reads as chrome.
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        # Story and Credits, and only those. Standings and Your Team mean
        # nothing before a run has started -- there are no matchups and no
        # team yet -- so offering them here was offering two dead ends. They
        # live in the header during a game, where they have something to show.
        for text, accent, handler in (("Story", T.ACCENT, on_story),
                                      ("Credits", T.TEXT_DIM, on_credits)):
            if handler is None:
                continue
            button = ActionButton(text, fonts, accent=accent,
                                  on_click=handler)
            button.setMinimumWidth(190)
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)
        # Bottom right, small: a credit, not a headline.
        layout.addWidget(label("Game Developer: Marvin Hui", fonts.small,
                               T.TEXT_DIM,
                               align=Qt.AlignRight | Qt.AlignBottom))

    def set_context(self, phase, state):
        stage = (state or {}).get("stage")
        you = (state or {}).get("player_side") or {}
        opponent = (state or {}).get("opponent_side") or {}
        matchup = phase == "prebattle" and bool(you) and bool(opponent)

        run = (state or {}).get("championship_run")
        if matchup:
            self.meet_art.setText("POKEMON CHAMPIONSHIP #%s" % run
                                  if run else "POKEMON CHAMPIONSHIP")
            self.round_art.setText("ROUND %s" % stage if stage else "")
            self.you_art.setText(str(you.get("nickname", "You")))
            self.versus_art.setText("VS")
            self.foe_art.setText(str(opponent.get("nickname", "Opponent")))
        else:
            for art in (self.meet_art, self.round_art, self.you_art,
                        self.versus_art, self.foe_art):
                art.setText("")

        # One or the other, never both: the matchup replaces the game's name
        # rather than being stacked under it.
        for art in (self.meet_art, self.round_art, self.you_art,
                    self.versus_art, self.foe_art):
            art.setVisible(matchup)
        self.game_name.setVisible(not matchup)

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
            veil.setColorAt(0.0, QColor(8, 20, 52, 50))
            veil.setColorAt(0.45, QColor(8, 20, 52, 84))
            veil.setColorAt(1.0, QColor(8, 20, 52, 140))
            painter.fillRect(rect, veil)
