"""
Battle-screen widgets: the rounded panel every card composes from, plus
HPBar, Chip, MoveCard, CombatantCard and FeedEntry.

Design note: the PySide6 proof of concept gave each of these its own
paintEvent, which meant the same "fill a rounded rect, stroke its border"
code existed four times. Here that logic lives once, in RoundedPanel;
everything else either uses it directly (CombatantCard) or calls its
paintEvent via super() and adds only what's actually different (MoveCard's
type spine). Changing corner radius or border behaviour for every panel in
the app is a one-place edit.
"""

import math

from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation,
                            QSize,
                            QPointF, QRectF, Qt, QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics,
                           QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

from GUI import theme as T


def label(text, font, color, wrap=False, align=None, parent=None):
    """A styled QLabel. Every plain text label in the interface goes through
    here -- it is the one place the transparent-background rule lives.

    `parent` is worth passing on any screen that rebuilds itself repeatedly.
    A widget with no parent is a top-level window in Qt's eyes, and one built
    into a layout only on the next line is briefly exactly that; handing it a
    parent at construction means it is never anything but a child.
    """
    widget = QLabel(text, parent)
    widget.setFont(font)
    widget.setWordWrap(wrap)
    if align is not None:
        widget.setAlignment(align)
    widget.setStyleSheet("color: %s; background: transparent;" % color)
    return widget


def clear_layout(layout):
    """Empty a layout, nested layouts included, unparenting as it goes.

    setParent(None) before deleteLater() matters: deleteLater only schedules
    the delete for the next event-loop turn, and until then the widget is
    still a child sitting at its old coordinates but managed by no layout.
    Screens that rebuild without returning to the event loop first drew the
    new widgets over the top of the old ones.

    hide() before that, because setParent(None) makes the widget a top-level
    window and a top-level window is a *window*: one that survives to the end
    of the turn still counting as shown is a bare label sitting on the
    desktop with no frame and nothing in it. Qt usually hides on reparent by
    itself, but "usually" was worth about six little empty windows a battle,
    and hiding first costs nothing.
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())
            item.layout().deleteLater()


def shadow(widget, blur=28, dy=6, alpha=140):
    """Depth cue with no Tkinter equivalent -- used on every top-level card."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


class RoundedPanel(QFrame):
    """An antialiased rounded rect: fill, optional border. Everything else
    in this module either is one of these or paints on top of one."""

    def __init__(self, parent=None, bg=T.PANEL, border=T.LINE,
                radius=T.RADIUS_MD, border_width=1):
        super().__init__(parent)
        self.bg = QColor(bg)
        self.border = QColor(border)
        self.radius = radius
        self.border_width = border_width

    def set_style(self, bg=None, border=None, border_width=None):
        if bg is not None:
            self.bg = QColor(bg)
        if border is not None:
            self.border = QColor(border)
        if border_width is not None:
            self.border_width = border_width
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        painter.fillPath(path, QBrush(self.bg))
        if self.border_width:
            painter.setPen(QPen(self.border, self.border_width))
            painter.drawPath(path)


class WordArt(QWidget):
    """A line of text drawn as artwork: gradient fill inside a dark outline.

    A QLabel can only be a flat colour with an optional shadow behind it, and
    over a lit stadium that reads as text sitting on a photograph. This paints
    the glyphs as a path instead, which allows three things a label cannot do:
    a fill that shades from top to bottom, a stroke that separates the letters
    from whatever is behind them at every edge rather than only below, and a
    soft dark spread underneath for depth.

    Sized from its own font metrics, so a layout reserves the right room and
    the text is never clipped by the widget it is in.
    """

    def __init__(self, text="", font=None, top=None, bottom=None, edge=None,
                 tracking=0.0, parent=None):
        super().__init__(parent)
        self._text = text
        self._font = font or QFont()
        #: the fill shades from `top` down to `bottom`
        self._top = QColor(top or "#FFFFFF")
        self._bottom = QColor(bottom or "#BFD4FF")
        self._edge = QColor(edge or "#06102A")
        self._tracking = tracking
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def setText(self, text):
        if text == self._text:
            return
        self._text = text
        self.updateGeometry()
        self.update()

    def text(self):
        return self._text

    def _spaced_font(self):
        font = QFont(self._font)
        if self._tracking:
            font.setLetterSpacing(QFont.AbsoluteSpacing, self._tracking)
        return font

    def sizeHint(self):
        metrics = QFontMetrics(self._spaced_font())
        rect = metrics.boundingRect(self._text or " ")
        # room for the stroke and the spread, on every side
        return QSize(rect.width() + 26, metrics.height() + 16)

    def minimumSizeHint(self):
        return QSize(0, self.sizeHint().height())

    def paintEvent(self, event):
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        font = self._spaced_font()
        metrics = QFontMetrics(font)
        width = metrics.boundingRect(self._text).width()
        x = (self.width() - width) / 2.0
        baseline = (self.height() + metrics.capHeight()) / 2.0

        path = QPainterPath()
        path.addText(x, baseline, font, self._text)

        # a soft dark spread first, so the letters sit on the picture rather
        # than floating over it
        painter.setPen(Qt.NoPen)
        for spread, alpha in ((7.0, 40), (4.5, 70), (2.5, 110)):
            glow = QColor(self._edge)
            glow.setAlpha(alpha)
            painter.strokePath(path, QPen(glow, spread, Qt.SolidLine,
                                          Qt.RoundCap, Qt.RoundJoin))
        # then the hard outline, then the gradient inside it
        painter.strokePath(path, QPen(self._edge, 3.0, Qt.SolidLine,
                                      Qt.RoundCap, Qt.RoundJoin))
        bounds = path.boundingRect()
        fill = QLinearGradient(bounds.topLeft(), bounds.bottomLeft())
        fill.setColorAt(0.0, self._top)
        fill.setColorAt(1.0, self._bottom)
        painter.fillPath(path, QBrush(fill))


class Chip(QLabel):
    """A small pill label -- type, status, FNT. Plain QSS is enough here;
    a chip has no states or animation, so it doesn't need RoundedPanel."""

    def __init__(self, text, color, fonts, parent=None):
        super().__init__(text.upper(), parent)
        c = QColor(color)
        # a distinct QFont copy so the letter-spacing tweak below doesn't
        # mutate fonts.small, which every other widget also points at
        chip_font = QFont(fonts.small)
        chip_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.6 * fonts.scale)
        self.setFont(chip_font)
        self.setContentsMargins(8, 3, 8, 3)
        self.setStyleSheet(
            "background: rgba(%d,%d,%d,46); color: %s;"
            "border: 1px solid rgba(%d,%d,%d,120); border-radius: %dpx;"
            % (c.red(), c.green(), c.blue(), color,
               c.red(), c.green(), c.blue(), T.RADIUS_SM))


class HPBar(RoundedPanel):
    """Gradient-filled bar that eases toward its new value instead of
    snapping -- the property animation is what Tkinter's Canvas can't do."""

    def __init__(self, parent=None, height=13):
        super().__init__(parent, bg=T.HP_TRACK, border=None, radius=height / 2,
                         border_width=0)
        self._fraction = 1.0
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._anim = QPropertyAnimation(self, b"fraction", self)
        self._anim.setDuration(620)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def get_fraction(self):
        return self._fraction

    def set_fraction(self, value):
        self._fraction = max(0.0, min(1.0, float(value)))
        self.update()

    fraction = Property(float, get_fraction, set_fraction)

    def set_hp(self, hp, max_hp, animate=True):
        target = max(0.0, min(1.0, hp / max(1, max_hp)))
        if not animate:
            self.set_fraction(target)
            return
        self._anim.stop()
        self._anim.setStartValue(self._fraction)
        self._anim.setEndValue(target)
        self._anim.start()

    def paintEvent(self, event):
        super().paintEvent(event)      # the track
        if self._fraction <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        fill = QRectF(self.rect())
        fill.setWidth(fill.width() * self._fraction)
        path = QPainterPath()
        path.addRoundedRect(fill, self.radius, self.radius)

        base = QColor(T.hp_color(self._fraction))
        gradient = QLinearGradient(fill.topLeft(), fill.bottomLeft())
        gradient.setColorAt(0.0, base.lighter(122))
        gradient.setColorAt(1.0, base.darker(112))
        painter.fillPath(path, QBrush(gradient))


class MoveCard(RoundedPanel):
    """One selectable move: type spine, name, metadata, effectiveness badge."""

    def __init__(self, move, hotkey, fonts, effectiveness=None, parent=None,
                on_click=None):
        super().__init__(parent, bg=T.PANEL_RAISED, border=T.LINE_SOFT,
                         radius=T.RADIUS_MD)
        self.move = move
        self.on_click = on_click
        self._type_color = QColor(T.type_color(move["type"]))
        self._hover = False
        self.setCursor(Qt.PointingHandCursor if on_click else Qt.ArrowCursor)
        self.setMinimumHeight(44)
        self.setToolTip(self._tooltip_text(move))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 10, 4)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name = QLabel(move["name"])
        name.setFont(fonts.body_bold)
        name.setStyleSheet("color: %s; background: transparent;" % T.TEXT)
        text_col.addWidget(name)

        bits = [move["type"], T.CATEGORY_GLYPH.get(move.get("category"), "STA")]
        if move.get("power"):
            bits.append("PWR %d" % move["power"])
        acc = move.get("accuracy")
        bits.append("ACC %d%%" % round(acc * 100) if acc else "ACC \u2014")
        if move.get("priority"):
            bits.append("PRI %+d" % move["priority"])
        meta = QLabel("  \u00b7  ".join(bits))
        meta.setFont(fonts.small)
        meta.setStyleSheet("color: %s; background: transparent;" % T.TEXT_FAINT)
        text_col.addWidget(meta)
        layout.addLayout(text_col, 1)

        right = QVBoxLayout()
        right.setSpacing(2)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if effectiveness:
            color = {"SUPER": T.PLAYER, "RESISTED": T.TEXT_FAINT,
                     "IMMUNE": T.OPPONENT}.get(effectiveness, T.TEXT_DIM)
            badge = QLabel(effectiveness)
            badge.setFont(fonts.small_bold)
            badge.setStyleSheet("color: %s; background: transparent;" % color)
            right.addWidget(badge, alignment=Qt.AlignRight)
        key = QLabel("[%s]" % hotkey if hotkey else "")
        key.setFont(fonts.small)
        key.setStyleSheet("color: %s; background: transparent;" % T.TEXT_FAINT)
        right.addWidget(key, alignment=Qt.AlignRight)
        layout.addLayout(right)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def _tooltip_text(self, move):
        """Detail that doesn't fit on the card face but is worth a hover --
        recoil and multi-hit range are the two that most affect a real
        decision (a 409-damage hit that also costs you a third of your
        own HP is not the same choice as a free one)."""
        bits = []
        if move.get("recoil"):
            bits.append("Recoil: %d%% of damage dealt" % round(
                move["recoil"] * 100))
        lo, hi = move.get("multi") or (0, 1)
        if hi and hi != 1 and (lo, hi) != (0, 1):
            bits.append("Hits %d-%d times" % (lo or 1, hi))
        return "\n".join(bits)

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if self.on_click:
            self.on_click()

    def paintEvent(self, event):
        self.bg = QColor(T.mix(T.PANEL_RAISED, self._type_color.name(), 0.16)
                         if self._hover else T.PANEL_RAISED)
        self.border = self._type_color if self._hover else QColor(T.LINE_SOFT)
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        spine = QRectF(0, 8, 4.5, max(0, self.height() - 16))
        path = QPainterPath()
        path.addRoundedRect(spine, 2.2, 2.2)
        gradient = QLinearGradient(spine.topLeft(), spine.bottomLeft())
        gradient.setColorAt(0.0, self._type_color.lighter(130))
        gradient.setColorAt(1.0, self._type_color.darker(120))
        painter.fillPath(path, QBrush(gradient))


class ActionButton(RoundedPanel):
    """A generic clickable action: title, optional sub-label, optional
    hotkey badge. Used for everything in the action bar that isn't a
    MoveCard -- confirm/deny, menu choices, switch-in candidates."""

    def __init__(self, title, fonts, sub=None, accent=T.CYAN, emphasis=False,
                parent=None, hotkey=None, disabled=False, on_click=None):
        base_bg = T.mix(T.PANEL_RAISED, accent, 0.14) if emphasis else T.PANEL_RAISED
        base_border = accent if emphasis else T.LINE_SOFT
        super().__init__(parent, bg=base_bg, border=base_border,
                         radius=T.RADIUS_MD)
        self._base_bg, self._accent = base_bg, QColor(accent)
        #: what it says. Kept as an attribute because the title was
        #: otherwise readable only by digging out the child QLabel -- which
        #: meant nothing could tell "Play Again" from "Close", and
        #: Test/gui/soak.py's list of buttons a crash-sweep must not press
        #: silently matched none of them.
        self.title = title
        self.disabled = disabled
        self._handler = on_click        # kept, so set_enabled can restore it
        self.on_click = None if disabled else on_click
        self._hover = False
        self._labels = []
        self.setCursor(Qt.ArrowCursor if disabled else Qt.PointingHandCursor)
        self.setMinimumHeight(44 if sub else 38)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 5, 13, 5)
        layout.setSpacing(1)

        head = QHBoxLayout()
        name = QLabel(title)
        name.setFont(fonts.body_bold)
        name.setStyleSheet("color: %s; background: transparent;"
                           % (T.TEXT_FAINT if disabled else T.TEXT))
        self._labels.append(name)
        head.addWidget(name)
        head.addStretch(1)
        if hotkey:
            key = QLabel("[%s]" % hotkey)
            key.setFont(fonts.small)
            key.setStyleSheet("color: %s; background: transparent;"
                             % T.TEXT_FAINT)
            head.addWidget(key)
        layout.addLayout(head)

        if sub:
            sub_label = QLabel(sub)
            sub_label.setFont(fonts.small)
            sub_label.setWordWrap(True)
            sub_label.setStyleSheet("color: %s; background: transparent;"
                                    % T.TEXT_FAINT)
            layout.addWidget(sub_label)

    def set_enabled(self, on):
        """Grey out or restore the button in place.

        Rebuilding the widget to change this would lose its position in the
        layout, which matters where a button is toggled rather than
        re-rendered -- the story reader's Back and Next at the first and last
        page, for instance.
        """
        on = bool(on)
        if on == (not self.disabled):
            return
        self.disabled = not on
        self.on_click = self._handler if on else None
        self.setCursor(Qt.PointingHandCursor if on else Qt.ArrowCursor)
        for label in self._labels:
            label.setStyleSheet("color: %s; background: transparent;"
                                % (T.TEXT if on else T.TEXT_FAINT))
        self._hover = False
        self.update()

    def enterEvent(self, event):
        self._hover = not self.disabled
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if self.on_click:
            self.on_click()

    def paintEvent(self, event):
        self.bg = QColor(T.mix(self._base_bg, self._accent.name(), 0.14)
                         if self._hover else self._base_bg)
        super().paintEvent(event)


class TeamPips(QWidget):
    """One ball per team member: how many Pokemon that side has left, and
    what shape they're in -- green healthy, amber hurt, grey fainted.

    The engine only ever printed this as prose buried in the log, so the
    single most basic question in a match ("how many do they have left?")
    had no answer on screen.
    """

    PIP_D = 11          # ball diameter
    PIP_GAP = 5

    #: which team member the pointer is over, or -1 when it leaves. Drives
    #: the ScoutCard: the pips are the only place the *bench* is reachable
    #: during a battle, which is exactly what scouting buys you.
    hovered = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._team = []
        self._over = -1
        self.setFixedHeight(self.PIP_D + 2)
        # No setToolTip: hovering a pip raises the ScoutCard, and a platform
        # tooltip fading in on top of it is exactly the mismatched-styling
        # problem the card exists to avoid.
        self.setMouseTracking(True)

    def set_team(self, team):
        self._team = list(team or [])
        count = max(1, len(self._team))
        self.setFixedWidth(count * self.PIP_D + (count - 1) * self.PIP_GAP + 2)
        self.update()

    def pip_at(self, x):
        """Index of the pip under `x`, or -1. Includes the gap after each
        ball, so there is no dead strip between them to fall into."""
        step = self.PIP_D + self.PIP_GAP
        index = int((x - 1) // step)
        return index if 0 <= index < len(self._team) else -1

    def mouseMoveEvent(self, event):
        index = self.pip_at(event.position().x())
        if index != self._over:
            self._over = index
            self.hovered.emit(index)

    def leaveEvent(self, event):
        if self._over != -1:
            self._over = -1
            self.hovered.emit(-1)

    def _colour(self, member):
        if member.get("fainted"):
            return QColor(T.TEXT_FAINT)
        max_hp = max(1, member.get("max_hp") or 1)
        if (member.get("hp") or 0) / max_hp <= 0.5:
            return QColor(T.ACCENT)
        return QColor(T.PLAYER)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        x = 1
        for member in self._team:
            colour = self._colour(member)
            painter.setBrush(QBrush(colour))
            painter.setPen(QPen(colour.darker(160), 1))
            painter.drawEllipse(x, 1, self.PIP_D, self.PIP_D)
            x += self.PIP_D + self.PIP_GAP


#: index into pokemon.modifier -> short label. 0 is HP, which is a real number
#: rather than a stage. Shared by the status card and the hover card.
STAGE_LABELS = ((1, "ATK"), (2, "DEF"), (3, "SPA"), (4, "SPD"),
                (5, "SPE"), (6, "EVA"), (7, "ACC"), (8, "CRIT"))


#: volatile_status key -> what to call it on screen. The engine's names are
#: internal ("Frighten", "TotalConcentration"); these are what a player would
#: say. Shared by the status card and the hover card, which name the same
#: conditions and must not drift apart.
CONDITION_LABELS = {
    "Confused": "CONFUSED", "Frighten": "FRIGHTENED",
    "Flinch": "FLINCHED", "Curse": "CURSED",
    "DestinyBond": "DESTINY BOND", "PerishSong": "PERISH SONG",
    "Torment": "TORMENTED", "Binding": "BOUND", "Trapped": "TRAPPED",
    "LeechSeed": "SEEDED", "Ingrain": "ROOTED", "AquaRing": "AQUA RING",
    "Octolock": "OCTOLOCKED", "TotalConcentration": "FOCUSED",
    "Yawn": "DROWSY", "FlashFire": "FLASH FIRE", "TakeAim": "TAKING AIM",
}
#: bookkeeping the engine keeps on everything -- never worth showing
CONDITION_NOISE = ("Turn", "Grounded", "NonVolatile")


def live_conditions(volatile):
    """The conditions actually in force, as display names."""
    return [CONDITION_LABELS.get(name, name)
            for name, value in sorted((volatile or {}).items())
            if value and name not in CONDITION_NOISE]


class StageDots(QWidget):
    """One stat's stage as six dots rather than a signed number.

    Six, because six is the range: a stage cannot pass +6 or -6. Grey for a
    stage that is not there, and as many coloured dots as stages actually
    moved -- green upwards, red downwards. "+2" and "-1" are a number to read
    and compare; two green dots against a row of grey is a shape, and the
    whole row of stats can be taken in at a glance without reading anything.
    """

    DOT = 7
    GAP = 3
    MAX = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stage = 0
        self.setFixedSize(self.MAX * self.DOT + (self.MAX - 1) * self.GAP,
                          self.DOT + 2)
        self.setStyleSheet("background: transparent;")

    def set_stage(self, stage):
        stage = max(-self.MAX, min(self.MAX, int(stage or 0)))
        if stage != self._stage:
            self._stage = stage
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        lit = abs(self._stage)
        on = QColor(T.PLAYER if self._stage > 0 else T.OPPONENT)
        off = QColor(T.LINE)
        x = 0
        for index in range(self.MAX):
            painter.setBrush(on if index < lit else off)
            painter.drawEllipse(x, 1, self.DOT, self.DOT)
            x += self.DOT + self.GAP


class CombatantCard(RoundedPanel):
    """One side's status card: name, HP, typing, ability, stat stages."""

    #: index into pokemon.modifier -> short label. 0 is HP, which is shown
    #: as a real number instead, and stages only exist for the rest.

    def __init__(self, side, fonts, parent=None):
        super().__init__(parent, bg=T.PANEL, border=T.LINE, radius=T.RADIUS_LG)
        self.side, self.fonts = side, fonts
        shadow(self)

        # Compact on purpose. This card is a readout, not the subject of the
        # screen -- every pixel it gives back goes to the battlefield behind
        # it, and at these sizes it still reads at a glance.
        self.setMaximumWidth(300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        head = QHBoxLayout()
        head.setSpacing(6)
        accent = T.PLAYER if side == "player" else T.OPPONENT
        eyebrow = QLabel("YOU" if side == "player" else "OPPONENT")
        eyebrow.setFont(fonts.eyebrow)
        eyebrow.setStyleSheet("color: %s; background: transparent;" % accent)
        head.addWidget(eyebrow)
        self.pips = TeamPips(self)
        head.addWidget(self.pips)
        head.addStretch(1)
        self.hp_text = QLabel("\u2014")
        self.hp_text.setFont(fonts.small)
        self.hp_text.setStyleSheet("color: %s; background: transparent;"
                                   % T.TEXT_DIM)
        head.addWidget(self.hp_text)
        layout.addLayout(head)

        self.name = QLabel("\u2014")
        self.name.setFont(fonts.title)
        self.name.setStyleSheet("color: %s; background: transparent;" % T.TEXT)
        layout.addWidget(self.name)

        self.chips = QHBoxLayout()
        self.chips.setSpacing(4)
        self.chips.setAlignment(Qt.AlignLeft)
        layout.addLayout(self.chips)

        # The non-volatile status -- Poison, Burn, Sleep, and Fainted -- on
        # its own row directly under the typing. It shared the typing row
        # before, where a two-type Pokemon pushed it to the edge of a 300px
        # card and it read as a third type rather than as something wrong.
        self.status_row = QHBoxLayout()
        self.status_row.setSpacing(4)
        self.status_row.setAlignment(Qt.AlignLeft)
        layout.addLayout(self.status_row)

        self.bar = HPBar(self, height=9)
        layout.addWidget(self.bar)

        self.ability = QLabel("")
        self.ability.setFont(fonts.tiny)
        self.ability.setStyleSheet("color: %s; background: transparent;"
                                   % T.TEXT_DIM)
        layout.addWidget(self.ability)

        # Confused, Bound, Seeded and the rest, on their own row. They used
        # to be in the hover card only, which meant the one class of thing
        # you have to react to *this turn* was the one thing you had to go
        # hunting for with the mouse. Stat stages stay in the hover card:
        # they are a number you weigh, not a warning.
        self.conditions = QHBoxLayout()
        self.conditions.setSpacing(4)
        self.conditions.setAlignment(Qt.AlignLeft)
        layout.addLayout(self.conditions)

        # one timer, reused: a switch-in flash that ends itself
        self._switch_timer = QTimer(self)
        self._switch_timer.setSingleShot(True)
        self._switch_timer.timeout.connect(self._end_flash)

    def flash_switch(self):
        """A brief accent pulse on the card, for a Pokemon coming in.

        Two seconds of a coloured border is enough to catch the eye without
        being something to wait for -- and unlike a banner it cannot be missed
        by looking at the wrong part of the screen, because it is on the card
        whose name just changed.
        """
        accent = T.PLAYER if self.side == "player" else T.OPPONENT
        self.set_style(border=accent, border_width=3)
        self._switch_timer.start(1400)

    def _end_flash(self):
        self.set_style(border=T.LINE, border_width=1)

    def set_mon(self, mon, animate=True):
        fainted = mon.get("fainted") or mon["hp"] <= 0
        self.name.setText(mon["name"])
        self.name.setStyleSheet("color: %s; background: transparent;"
                                % (T.TEXT_FAINT if fainted else T.TEXT))
        self.hp_text.setText("FAINTED" if fainted
                             else "%d / %d" % (mon["hp"], mon["max_hp"]))
        self.hp_text.setStyleSheet("color: %s; background: transparent;"
                                   % (T.OPPONENT if fainted else T.TEXT_DIM))
        self.set_style(border=T.OPPONENT if fainted else T.LINE,
                       border_width=2 if fainted else 1)
        self.bar.set_hp(0 if fainted else mon["hp"], mon["max_hp"], animate)

        # Rebuild the chips only when they would actually differ. set_mon runs
        # on every state update -- many times a second -- and the typing,
        # status and fainted flag almost never change between two of them, so
        # tearing down and recreating the row each time was the single biggest
        # source of widget churn in the interface (4,214 QLabel constructions
        # over five battles). The signature is exactly what the row is drawn
        # from, so if it matches, the row on screen is already correct.
        status = mon.get("status", "Normal")
        conditions = tuple(live_conditions(mon.get("volatile") or {}))
        chip_state = (tuple(mon.get("types") or ()), status, fainted,
                      conditions)
        if chip_state != getattr(self, "_chip_state", None):
            self._chip_state = chip_state
            self._rebuild_chips(mon, status, fainted)
            self._rebuild_conditions(conditions)

        self._set_ability(mon)

    def _rebuild_chips(self, mon, status, fainted):
        # clear_layout, not a takeAt/deleteLater loop of its own: deleteLater
        # alone leaves the old chip parented to this card until the next
        # event-loop turn, so it is still a child at its old coordinates. This
        # card is re-set on every state update, and the chips were piling up
        # (80 of them after 40 renders) and drawing over each other.
        # clear_layout unparents first, which is exactly the bug it was
        # written for.
        clear_layout(self.chips)
        for type_name in mon.get("types", []):
            self.chips.addWidget(Chip(type_name, T.type_color(type_name),
                                      self.fonts))
        # a row of its own, under the typing
        clear_layout(self.status_row)
        if fainted:
            self.status_row.addWidget(Chip("FAINTED", T.OPPONENT, self.fonts))
        elif status not in ("Normal", "", "Fainted"):
            self.status_row.addWidget(
                Chip(T.STATUS_SHORT.get(status, status),
                     T.STATUS_COLORS.get(status, T.TEXT_DIM), self.fonts))

    #: how many condition chips fit on a 300px card before they start
    #: squeezing each other unreadably. The rest become a "+N".
    CONDITION_ROOM = 3

    def _rebuild_conditions(self, conditions):
        """The volatile conditions in force, as chips.

        clear_layout for the same reason `_rebuild_chips` uses it: this runs
        on a state change and deleteLater alone would leave the old chips
        parented here, drawing at their old coordinates until the next
        event-loop turn.
        """
        clear_layout(self.conditions)
        shown = conditions[:self.CONDITION_ROOM]
        for name in shown:
            self.conditions.addWidget(Chip(name, T.VIOLET, self.fonts))
        extra = len(conditions) - len(shown)
        if extra > 0:
            more = Chip("+%d" % extra, T.VIOLET, self.fonts)
            more.setToolTip(", ".join(conditions))
            self.conditions.addWidget(more)

    def _set_ability(self, mon):
        # The opponent's ability is hidden information, and printing it broke
        # Illusion outright: a disguised Zoroark keeps ability ["Illusion"]
        # while wearing another Pokemon's name and typing, so the card
        # announced the trick before it could ever work. You learn an
        # opponent's ability by watching it trigger (it shows up in the
        # battle log) or by scouting them before the match.
        if self.side == "player":
            ability = mon.get("ability") or []
            self.ability.setText(
                "Ability: " + ", ".join(ability) if ability else "")
        else:
            self.ability.setText("Ability: ???")

    def set_team(self, team):
        """How many Pokemon this side has left, and their condition."""
        self.pips.set_team(team)

    # Stat stages and temporary conditions are not on this card any more.
    # Eight stats and a handful of conditions at once turned a compact readout
    # into a wall, and none of it was actionable at a glance. The card now
    # carries only what changes how you must play right now -- typing, HP, and
    # a serious status condition (asleep, paralysed, poisoned, burned, frozen).
    # Everything temporary lives in the hover card, which is opened on purpose
    # and has room to spell it out. See ScoutCard._add_stages.


EVENT_ACCENTS = {"move": T.ACCENT, "ability": T.VIOLET, "status": T.CYAN,
                 "faint": T.OPPONENT, "character": T.CYAN,
                 "reward": T.PLAYER, "loss": T.TEXT_DIM,
                 "switch": T.VIOLET}
EVENT_LABELS = {"move": "MOVE", "ability": "ABILITY", "status": "EFFECT",
                "faint": "KNOCKED OUT", "character": "CHARACTER ABILITY",
                "reward": "JOINED YOUR TEAM", "loss": "LEFT YOUR TEAM",
                "switch": "SENT OUT"}
#: whose turn produced the event -- colouring by side is what makes the
#: feed readable as a back-and-forth ("you did X, they did Y") instead of
#: an undifferentiated wall of move text
SIDE_ACCENTS = {"player": T.PLAYER, "opponent": T.OPPONENT}
SIDE_LABELS = {"player": "YOU", "opponent": "OPPONENT"}


def event_accent(kind, side=None):
    # These keep their own colour regardless of side: they're the events
    # that must never blend into the surrounding move text.
    if kind in ("faint", "character", "reward", "loss"):
        return EVENT_ACCENTS[kind]
    return SIDE_ACCENTS.get(side) or EVENT_ACCENTS.get(kind, T.TEXT_DIM)


def _build_event_body(container, kind, text, fonts, actor="", side=None):
    """The tag/actor header plus wrapped text every event card shows."""
    accent = event_accent(kind, side)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(13, 8, 13, 10)
    layout.setSpacing(3)

    head = QHBoxLayout()
    tag_text = EVENT_LABELS.get(kind, "EVENT")
    if side in SIDE_LABELS:
        tag_text = "%s  ·  %s" % (SIDE_LABELS[side], tag_text)
    tag = QLabel(tag_text)
    tag.setFont(fonts.eyebrow)
    tag.setStyleSheet("color: %s; background: transparent;" % accent)
    head.addWidget(tag)
    head.addStretch(1)
    if actor:
        who = QLabel(actor)
        who.setFont(fonts.small)
        who.setStyleSheet("color: %s; background: transparent;" % T.TEXT_FAINT)
        head.addWidget(who)
    layout.addLayout(head)

    body = QLabel(text)
    body.setWordWrap(True)
    body.setFont(fonts.small)
    body.setStyleSheet("color: %s; background: transparent;" % T.TEXT)
    layout.addWidget(body)
    return accent


class FeedEntry(RoundedPanel):
    """One permanent row in the Battle tab's scrollback."""

    def __init__(self, kind, text, fonts, actor="", side=None, parent=None):
        accent = event_accent(kind, side)
        super().__init__(parent, bg=T.mix(T.PANEL, accent, 0.08),
                         border=T.LINE_SOFT, radius=T.RADIUS_SM,
                         border_width=1)
        _build_event_body(self, kind, text, fonts, actor, side)


class TurnDivider(QWidget):
    """A slim 'Turn N' rule between one turn's events and the next."""

    def __init__(self, turn, fonts, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 10, 4, 4)
        layout.setSpacing(10)
        layout.addWidget(_line(T.LINE_SOFT), 1)
        label = QLabel("TURN %s" % turn)
        label.setFont(fonts.eyebrow)
        label.setStyleSheet("color: %s; background: transparent;"
                            % T.TEXT_FAINT)
        layout.addWidget(label)
        layout.addWidget(_line(T.LINE_SOFT), 1)


def _line(color):
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("background: %s; max-height: 1px; border: none;"
                       % color)
    return line


#: screen names for the things that sit on the field, and the colour each
#: one keeps wherever it appears
EFFECT_STYLE = {
    "Reflect": ("REFLECT", T.CYAN),
    "Light Screen": ("LIGHT SCREEN", T.ACCENT),
    "Aurora Veil": ("AURORA VEIL", T.VIOLET),
    "Tailwind": ("TAILWIND", T.PLAYER),
    "Trick Room": ("TRICK ROOM", T.VIOLET),
    "Stealth Rock": ("STEALTH ROCK", T.OPPONENT),
    "Spikes": ("SPIKES", T.OPPONENT),
    "Toxic Spikes": ("TOXIC SPIKES", T.OPPONENT),
    "Sticky Web": ("STICKY WEB", T.OPPONENT),
}

#: what each one actually does, since the game never says
EFFECT_NOTE = {
    "Reflect": "halves physical damage",
    "Light Screen": "halves special damage",
    "Aurora Veil": "halves damage of both kinds",
    "Tailwind": "doubles Speed",
    "Trick Room": "slower Pokemon move first",
    "Stealth Rock": "chips each Pokemon switching in",
    "Spikes": "hurts grounded Pokemon switching in",
    "Toxic Spikes": "poisons grounded Pokemon switching in",
    "Sticky Web": "lowers Speed of grounded Pokemon switching in",
}


class FieldBoard(QWidget):
    """A live board of what is on the field, not a log of what happened.

    Everything here is state the engine already keeps -- screens and Tailwind
    as turn counters, hazards as layer counts, Trick Room and artificial
    weather on their own timers -- and none of it narrates itself. An
    append-only log of arrivals and departures read as noise: by turn six you
    were scrolling to find out whether Reflect was still up. So each effect
    gets one row that stays put and counts itself down, and disappears the
    moment it is gone. set_state() is a no-op unless something changed, so
    this can be called on every state update.
    """

    def __init__(self, fonts, parent=None):
        super().__init__(parent)
        self.fonts = fonts
        self._signature = None
        self.active = 0
        self.setStyleSheet("background: transparent;")
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(10, 10, 10, 10)
        self._column.setSpacing(6)
        self._column.addStretch(1)

    # -- building blocks ---------------------------------------------------
    def _clear(self):
        while self._column.count():
            item = self._column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _caption(self, text, colour):
        label = QLabel(text.upper())
        font = QFont(self.fonts.eyebrow)
        label.setFont(font)
        label.setStyleSheet("color: %s; background: transparent;" % colour)
        self._column.addWidget(label)

    def _row(self, name, note, count, unit, colour, tooltip=""):
        panel = RoundedPanel(self, bg=T.mix(T.PANEL, colour, 0.12),
                             border=colour, radius=T.RADIUS_SM)
        # Word wrap is deliberately off on both labels. A wrapping label's
        # minimum height is one line, so inside a widgetResizable QScrollArea
        # the whole column would compress to the viewport instead of
        # scrolling -- a busy field then had its bottom rows unreachable.
        # Fixed-height rows give the column an honest minimum, which is what
        # makes the scrollbar appear. The long-form description moves to the
        # tooltip rather than costing a wrapped line.
        panel.setToolTip(tooltip or note)
        line = QHBoxLayout(panel)
        line.setContentsMargins(11, 6, 11, 6)
        line.setSpacing(10)

        text = QVBoxLayout()
        text.setSpacing(1)
        title = QLabel(name)
        title.setFont(self.fonts.body_bold)
        title.setStyleSheet("color: %s; background: transparent;" % T.TEXT)
        text.addWidget(title)
        if note:
            caption = QLabel(note)
            caption.setFont(self.fonts.small)
            caption.setStyleSheet("color: %s; background: transparent;"
                                  % T.TEXT_DIM)
            caption.setWordWrap(False)
            text.addWidget(caption)
        line.addLayout(text, 1)

        tally = QVBoxLayout()
        tally.setSpacing(0)
        tally.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value = QLabel("—" if count is None else str(count))
        value.setFont(self.fonts.num_big)
        value.setStyleSheet("color: %s; background: transparent;" % colour)
        value.setAlignment(Qt.AlignRight)
        tally.addWidget(value)
        suffix = QLabel(unit)
        suffix.setFont(self.fonts.small)
        suffix.setStyleSheet("color: %s; background: transparent;"
                             % T.TEXT_FAINT)
        suffix.setAlignment(Qt.AlignRight)
        tally.addWidget(suffix)
        line.addLayout(tally)

        self._column.addWidget(panel)

    # -- state -------------------------------------------------------------
    def _entries(self, you, opponent, field):
        """(section, name, note, count, unit) for everything currently up.

        Which side a thing sits on is also who put it there: a screen
        protects the side that set it, while a hazard is laid on the side
        that has to walk into it -- so the same dictionary means "you cast
        this" for buffs and "they cast this" for hazards.
        """
        mine = you.get("nickname") or "You"
        theirs = opponent.get("nickname") or "The opponent"
        out = []
        for section, source, unit, caster in (
                ("your side", you.get("buffs"), "turns left", "you set it"),
                ("your side", you.get("hazards"), "layers",
                 "%s set it" % theirs),
                ("opponent's side", opponent.get("buffs"), "turns left",
                 "%s set it" % theirs),
                ("opponent's side", opponent.get("hazards"), "layers",
                 "you set it")):
            for name, count in sorted((source or {}).items()):
                if not count:
                    continue
                out.append((section, name, caster, int(count), unit,
                            EFFECT_NOTE.get(name, "")))
        for name, count in sorted((field.get("field") or {}).items()):
            if count:
                out.append(("the battlefield", name, "in effect", int(count),
                            "turns left", EFFECT_NOTE.get(name, "")))
        weather = field.get("weather")
        if weather and weather != "Clear":
            turns = field.get("weather_turns")
            artificial = field.get("weather_artificial")
            out.append(("the battlefield", weather,
                        "conjured" if artificial else "this arena's own",
                        turns, "turns left" if turns is not None else "lasting",
                        "weather set by a move or an ability, so it will pass"
                        if artificial
                        else "the arena's natural weather -- it never lifts"))
        return out

    def set_state(self, you, opponent, field):
        you, opponent, field = you or {}, opponent or {}, field or {}
        entries = self._entries(you, opponent, field)
        signature = tuple(entries)
        if signature == self._signature:
            return
        self._signature = signature
        self.active = len(entries)
        self._clear()
        if not entries:
            empty = QLabel("Nothing on the field.")
            empty.setFont(self.fonts.body)
            empty.setStyleSheet("color: %s; background: transparent;"
                                % T.TEXT_FAINT)
            self._column.addWidget(empty)
            self._column.addStretch(1)
            return
        section = None
        for where, name, note, count, unit, tooltip in entries:
            if where != section:
                section = where
                self._caption(
                    where,
                    T.PLAYER if where == "your side"
                    else T.OPPONENT if where == "opponent's side"
                    else T.VIOLET)
            _, colour = EFFECT_STYLE.get(name, (name, T.CYAN))
            self._row(name, note, count, unit, colour, tooltip)
        self._column.addStretch(1)

    def reset(self):
        """Wipe the board -- a new matchup starts on a clear field."""
        self._signature = None
        self.active = 0
        self.set_state({}, {}, {})


#: one field layer -> (caption, colour). The real games keep weather,
#: terrain and rooms in *separate* slots -- Rain and Electric Terrain and
#: Trick Room can all be up at once, and only members of the same layer
#: cancel each other. So this is three boxes, never one.
FIELD_LAYERS = (
    ("weather", "WEATHER", T.CYAN),
    ("terrain", "TERRAIN", T.PLAYER),
    ("room", "ROOM", T.VIOLET),
)

#: what each condition's emblem is drawn as, and in what colour. Drawn
#: rather than typed: `theme.WEATHER_GLYPH` held ☀/☂/❄ for this job and was
#: never used by anything, and a glyph is at the mercy of whether the font
#: on the machine happens to carry it.
FIELD_ART = {
    "Clear": ("clear", T.TEXT_FAINT),
    "Sunny": ("sun", T.ACCENT),
    "Rain": ("rain", T.CYAN),
    "Sandstorm": ("sand", "#C9A227"),
    "Hail": ("hail", "#9FD8FF"),
    "Snow": ("hail", "#9FD8FF"),
    "Electric": ("bolt", T.ACCENT),
    "Grassy": ("grass", T.PLAYER),
    "Misty": ("mist", "#F0A8FF"),
    "Psychic": ("psychic", T.VIOLET),
    "Trick Room": ("room", T.VIOLET),
    "Magic Room": ("room", T.VIOLET),
    "Wonder Room": ("room", T.VIOLET),
    "None": ("none", T.TEXT_FAINT),
}


def field_emblem(shape, colour, size, ratio=1.0):
    """A small painted emblem for one field condition.

    Device-pixel-ratio aware the same way the sprites are: painted at
    size*ratio and told its ratio, so it is crisp on a scaled display
    instead of being blown up by the label.
    """
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    ink = QColor(colour)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.scale(ratio, ratio)
    mid = size / 2.0
    thin = QPen(ink, max(1.4, size * 0.09), Qt.SolidLine, Qt.RoundCap,
                Qt.RoundJoin)

    if shape == "sun":
        painter.setPen(Qt.NoPen)
        painter.setBrush(ink)
        painter.drawEllipse(QRectF(mid - size * 0.19, mid - size * 0.19,
                                   size * 0.38, size * 0.38))
        painter.setPen(thin)
        for step in range(8):
            angle = math.radians(step * 45)
            inner, outer = size * 0.28, size * 0.44
            painter.drawLine(
                QPointF(mid + math.cos(angle) * inner,
                        mid + math.sin(angle) * inner),
                QPointF(mid + math.cos(angle) * outer,
                        mid + math.sin(angle) * outer))
    elif shape == "clear":
        painter.setPen(thin)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(mid - size * 0.28, mid - size * 0.28,
                                   size * 0.56, size * 0.56))
    elif shape == "rain":
        painter.setPen(thin)
        painter.setBrush(Qt.NoBrush)
        cloud = QRectF(size * 0.16, size * 0.20, size * 0.68, size * 0.36)
        painter.drawArc(cloud, 0, 180 * 16)
        painter.drawLine(QPointF(size * 0.16, size * 0.38),
                         QPointF(size * 0.84, size * 0.38))
        for offset in (0.30, 0.50, 0.70):
            painter.drawLine(QPointF(size * offset, size * 0.54),
                             QPointF(size * (offset - 0.06), size * 0.80))
    elif shape == "sand":
        painter.setPen(thin)
        for row, length in ((0.32, 0.62), (0.50, 0.74), (0.68, 0.54)):
            painter.drawLine(QPointF(size * (0.5 - length / 2), size * row),
                             QPointF(size * (0.5 + length / 2), size * row))
    elif shape == "hail":
        painter.setPen(thin)
        for step in range(3):
            angle = math.radians(step * 60)
            reach = size * 0.34
            painter.drawLine(
                QPointF(mid - math.cos(angle) * reach,
                        mid - math.sin(angle) * reach),
                QPointF(mid + math.cos(angle) * reach,
                        mid + math.sin(angle) * reach))
    elif shape == "bolt":
        painter.setPen(Qt.NoPen)
        painter.setBrush(ink)
        painter.drawPolygon(QPolygonF([
            QPointF(size * 0.56, size * 0.12), QPointF(size * 0.30, size * 0.54),
            QPointF(size * 0.47, size * 0.54), QPointF(size * 0.41, size * 0.88),
            QPointF(size * 0.70, size * 0.44), QPointF(size * 0.52, size * 0.44),
        ]))
    elif shape == "grass":
        painter.setPen(thin)
        painter.setBrush(Qt.NoBrush)
        for base, tip in ((0.30, 0.18), (0.50, 0.10), (0.70, 0.22)):
            path = QPainterPath(QPointF(size * base, size * 0.84))
            path.quadTo(QPointF(size * (base + 0.06), size * 0.50),
                        QPointF(size * (base + tip * 0.3), size * tip))
            painter.drawPath(path)
    elif shape == "mist":
        painter.setPen(thin)
        for row, length in ((0.36, 0.56), (0.52, 0.70), (0.68, 0.48)):
            path = QPainterPath(QPointF(size * (0.5 - length / 2), size * row))
            path.quadTo(QPointF(size * 0.5, size * (row - 0.12)),
                        QPointF(size * (0.5 + length / 2), size * row))
            painter.drawPath(path)
    elif shape == "psychic":
        painter.setPen(thin)
        painter.setBrush(Qt.NoBrush)
        for reach in (0.16, 0.28, 0.40):
            painter.drawArc(QRectF(mid - size * reach, mid - size * reach,
                                    size * reach * 2, size * reach * 2),
                            30 * 16, 280 * 16)
    elif shape == "room":
        painter.setPen(thin)
        painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(QPolygonF([
            QPointF(size * 0.28, size * 0.20), QPointF(size * 0.72, size * 0.20),
            QPointF(size * 0.36, size * 0.80), QPointF(size * 0.64, size * 0.80),
        ]))
    else:                                  # "none", and anything unnamed
        painter.setPen(thin)
        painter.drawLine(QPointF(size * 0.32, mid), QPointF(size * 0.68, mid))
    painter.end()
    return pixmap


class FieldChip(RoundedPanel):
    """One field layer, as an emblem, a caption and what is up right now."""

    ICON = 22

    def __init__(self, caption, colour, fonts, parent=None):
        super().__init__(parent, bg=T.mix(T.PANEL_SUNK, colour, 0.10),
                         border=T.LINE_SOFT, radius=T.RADIUS_SM)
        self.fonts = fonts
        self.accent = colour
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 5, 10, 5)
        row.setSpacing(8)

        self.emblem = QLabel(self)
        self.emblem.setFixedSize(self.ICON, self.ICON)
        self.emblem.setAlignment(Qt.AlignCenter)
        row.addWidget(self.emblem)

        text = QVBoxLayout()
        text.setSpacing(0)
        self.caption = QLabel(caption, self)
        self.caption.setFont(fonts.eyebrow)
        self.caption.setStyleSheet("color: %s; background: transparent;"
                                   % T.TEXT_FAINT)
        text.addWidget(self.caption)
        self.value = QLabel("—", self)
        self.value.setFont(fonts.body_bold)
        self.value.setStyleSheet("color: %s; background: transparent;"
                                 % T.TEXT)
        text.addWidget(self.value)
        row.addLayout(text)
        self._shown = None

    def show_condition(self, name, turns=None):
        """Name the condition, draw its emblem, and count it down if it will
        pass. A no-op when nothing has changed -- this is called on every
        state publish, several times a second."""
        signature = (name, turns)
        if signature == self._shown:
            return
        self._shown = signature
        shape, colour = FIELD_ART.get(name, ("none", self.accent))
        self.emblem.setPixmap(field_emblem(
            shape, colour, self.ICON, self.emblem.devicePixelRatioF()))
        self.value.setText(name if turns in (None, 0)
                           else "%s  %d" % (name, turns))
        self.value.setStyleSheet(
            "color: %s; background: transparent;"
            % (T.TEXT_FAINT if name == "None" else T.TEXT))
        self.setToolTip(FIELD_TIP.get(name, name))


#: what a condition does, for the tooltip. The strip itself stays terse.
FIELD_TIP = {
    "Clear": "No weather. Nothing is boosting or blunting anything.",
    "Sunny": "Fire moves hit harder, Water moves weaker. Solar Beam needs no "
             "charge; Thunder and Hurricane become unreliable.",
    "Rain": "Water moves hit harder, Fire moves weaker. Thunder and Hurricane "
            "cannot miss; Solar Beam is halved.",
    "Sandstorm": "Chips away at anything not Rock, Ground or Steel.",
    "Hail": "Chips away at anything not Ice. Blizzard cannot miss.",
    "Snow": "Chips away at anything not Ice. Blizzard cannot miss.",
    "Trick Room": "The slower Pokemon moves first.",
    "None": "Nothing on this layer.",
}


class FieldStrip(QWidget):
    """Weather, terrain and rooms, always on screen, never in the way.

    The field readout used to be a strip of chips *under* the arena, which
    was moved into its own tab to give the arena back the height -- see
    FieldBoard. This is the third answer: the three permanent layers sit
    inside the arena as an overlay, so they cost the battle view no height
    at all, while the tab keeps the per-side detail (screens, hazards, who
    set what, turn counts).

    Only Weather is always shown, "None" included, because "there is no
    weather" is information a player wants at a glance -- and weather is on
    the field in most battles. Terrain and Room appear only while there is
    one: a box reading "None" for the whole battle is furniture, and this
    strip sits over the arena where every pixel is the battlefield.
    """

    def __init__(self, fonts, parent=None):
        super().__init__(parent)
        self.fonts = fonts
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.chips = {}
        for key, caption, colour in FIELD_LAYERS:
            chip = FieldChip(caption, colour, fonts, self)
            self.chips[key] = chip
            row.addWidget(chip)
        for key in ("terrain", "room"):
            self.chips[key].setVisible(False)
        self._signature = None

    def set_state(self, field):
        field = field or {}
        weather = str(field.get("weather") or "Clear")
        turns = field.get("weather_turns")
        # the arena's own weather never lifts, so counting it down would be a
        # lie -- weather_artificial is what says which kind this is
        if not field.get("weather_artificial"):
            turns = None

        rooms = {name: count
                 for name, count in (field.get("field") or {}).items()
                 if count and "Room" in name}
        room, room_turns = (sorted(rooms)[0], rooms[sorted(rooms)[0]]) \
            if rooms else ("None", None)

        terrain = field.get("terrain")
        terrain_turns = field.get("terrain_turns")

        signature = (weather, turns, room, room_turns, terrain, terrain_turns)
        if signature == self._signature:
            return
        self._signature = signature
        self.chips["weather"].show_condition(weather, turns)
        self.chips["room"].setVisible(room != "None")
        if room != "None":
            self.chips["room"].show_condition(room, room_turns)
        self.chips["terrain"].setVisible(terrain is not None)
        if terrain is not None:
            self.chips["terrain"].show_condition(str(terrain), terrain_turns)

    def reset(self):
        self._signature = None
        self.set_state({})


class AbilityFlare(RoundedPanel):
    """A brief on-field callout when a trainer's character ability fires.

    Character abilities are the one thing in a match that belongs to the
    trainer rather than a Pokemon, and they fire without any of the usual
    cues -- no move name, no HP change of their own. On the field there was
    nothing at all to see, so they read as unexplained swings. This shows
    who triggered what, on their side of the arena, then fades out.
    """

    def __init__(self, side, fonts, parent=None):
        accent = T.PLAYER if side == "player" else T.OPPONENT
        super().__init__(parent, bg=T.mix(T.PANEL, T.CYAN, 0.30),
                         border=T.CYAN, radius=T.RADIUS_SM, border_width=2)
        shadow(self, blur=20, dy=4, alpha=150)
        self.setMaximumWidth(260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 6, 11, 7)
        layout.setSpacing(1)

        self.tag = QLabel("CHARACTER ABILITY", self)
        self.tag.setFont(fonts.eyebrow)
        self.tag.setStyleSheet("color: %s; background: transparent;" % T.CYAN)
        layout.addWidget(self.tag)

        self.who = QLabel("", self)
        self.who.setFont(fonts.small_bold)
        self.who.setStyleSheet("color: %s; background: transparent;" % accent)
        layout.addWidget(self.who)

        self.body = QLabel("", self)
        self.body.setFont(fonts.small)
        self.body.setWordWrap(True)
        self.body.setStyleSheet("color: %s; background: transparent;" % T.TEXT)
        layout.addWidget(self.body)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self.hide()

    def flare(self, actor, text, lifetime_ms=4200):
        self.who.setText(actor or "")
        self.who.setVisible(bool(actor))
        # first sentence only: the full transcript is in the battle log, and
        # this needs to stay small enough not to cover the field
        first = text.strip().split("\n")[0].strip()
        self.body.setText(first[:150])
        self.show()
        self.raise_()
        self._hide_timer.start(lifetime_ms)


class ResultOverlay(RoundedPanel):
    """The VICTORY / DEFEAT plate shown over the arena at the end of a match.

    The engine resolves a battle ending, the reward pick and the state
    reset in one uninterrupted call, so without something deliberately
    holding the screen here the knockout is never actually seen -- the
    fainted Pokemon is already back to "Normal" by the time the next
    prompt renders. This is that hold, and it's dismissed by a real click
    rather than a timer so it can't be missed on a slow frame.

    Deliberately a centred plate rather than a full-arena scrim: the point
    of the pause is to show the knocked-out Pokemon, so the combatant
    cards (and their FAINTED state) have to stay legible next to it.
    """

    def __init__(self, fonts, parent=None):
        super().__init__(parent, bg=T.PANEL, border=T.LINE,
                         radius=T.RADIUS_LG, border_width=2)
        shadow(self, blur=30, dy=6, alpha=170)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 16, 34, 18)
        layout.setSpacing(2)

        self.headline = QLabel("", self)
        self.headline.setFont(fonts.hero)
        self.headline.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.headline)

        self.detail = QLabel("", self)
        self.detail.setFont(fonts.body_bold)
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setStyleSheet("color: %s; background: transparent;"
                                  % T.TEXT)
        layout.addWidget(self.detail)

    def show_result(self, won, detail):
        accent = T.PLAYER if won else T.OPPONENT
        self.set_style(bg=T.mix(T.PANEL, accent, 0.22), border=accent)
        self.headline.setText("VICTORY" if won else "DEFEAT")
        self.headline.setStyleSheet("color: %s; background: transparent;"
                                    % accent)
        self.detail.setText(detail)
        self.show()
        self.raise_()


class ScoutCard(RoundedPanel):
    """The hover readout for one Pokemon: its four moves and its six IVs.

    A frameless top-level panel rather than a tooltip. A tooltip is plain
    text on the platform's yellow -- it cannot show a type-coloured move
    spine or grade an IV, and next to the rest of the battle screen it looks
    like a different program. This is the same RoundedPanel every card is
    built from, so it reads as part of the game.

    It never takes focus (WA_ShowWithoutActivating) and never accepts the
    mouse (WA_TransparentForMouseEvents), so it cannot steal a click, and it
    cannot land under the pointer and trigger its own leaveEvent -- which is
    what makes a popup flicker on and off as you move.
    """

    #: nominal_base_stats / iv order
    STATS = ("HP", "ATK", "DEF", "SPA", "SPD", "SPE")
    MAX_IV = 31
    WIDTH = 268

    def __init__(self, fonts, parent=None):
        super().__init__(parent, bg=T.PANEL_RAISED, border=T.ACCENT,
                         radius=T.RADIUS_MD, border_width=2)
        self.fonts = fonts
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint
                            | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedWidth(self.WIDTH)
        # deliberately no shadow(): a QGraphicsDropShadowEffect on a
        # top-level widget is drawn inside that widget's own rect, so on a
        # frameless popup it clips into a dark band along the edges

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 9, 11, 10)
        layout.setSpacing(6)

        self.name = label("", fonts.body_bold, T.TEXT)
        layout.addWidget(self.name)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(4)
        self.chips.setAlignment(Qt.AlignLeft)
        layout.addLayout(self.chips)
        self.ability = label("", fonts.tiny, T.TEXT_DIM, wrap=True)
        layout.addWidget(self.ability)

        self.body = QVBoxLayout()
        self.body.setSpacing(5)
        layout.addLayout(self.body)

    # -- IV colour: a 31 is worth spotting at a glance --------------------
    def _iv_colour(self, value):
        if value >= self.MAX_IV:
            return T.CYAN                    # a perfect roll, worth spotting
        if value >= 24:
            return T.PLAYER
        if value >= 14:
            return T.ACCENT
        return T.TEXT_FAINT

    def _iv_row(self, ivs, nominal, total):
        row = QHBoxLayout()
        row.setSpacing(3)
        for index, name in enumerate(self.STATS):
            value = ivs[index] if index < len(ivs) else 0
            cell = RoundedPanel(None, bg=T.PANEL_SUNK,
                                border=T.LINE_SOFT, radius=T.RADIUS_SM)
            inner = QVBoxLayout(cell)
            inner.setContentsMargins(2, 2, 2, 2)
            inner.setSpacing(0)
            inner.addWidget(label(name, self.fonts.tiny, T.TEXT_FAINT,
                                  align=Qt.AlignCenter))
            inner.addWidget(label(str(value), self.fonts.small_bold,
                                  self._iv_colour(value),
                                  align=Qt.AlignCenter))
            # the stat the IV actually produced, which is the number that
            # decides the trade -- the IV alone means nothing without it
            if index < len(nominal):
                inner.addWidget(label(str(nominal[index]), self.fonts.tiny,
                                      T.TEXT_DIM, align=Qt.AlignCenter))
            row.addWidget(cell)
        wrap = QVBoxLayout()
        wrap.setSpacing(2)
        wrap.addWidget(label("IVS  (total %d / 186)" % total,
                             self.fonts.tiny, T.TEXT_FAINT))
        wrap.addLayout(row)
        return wrap

    def _move_row(self, move_name, move):
        colour = T.type_color((move or {}).get("type", "Normal"))
        row = RoundedPanel(None, bg=T.mix(T.PANEL_SUNK, colour, 0.16),
                           border=colour, radius=T.RADIUS_SM)
        line = QHBoxLayout(row)
        line.setContentsMargins(8, 3, 8, 3)
        line.setSpacing(6)
        line.addWidget(label(move_name, self.fonts.small_bold, T.TEXT))
        line.addStretch(1)
        if move:
            bits = [T.CATEGORY_GLYPH.get(move.get("category"), "STA")]
            if move.get("power"):
                bits.append(str(move["power"]))
            line.addWidget(label(" · ".join(bits), self.fonts.tiny,
                                 T.TEXT_DIM))
        return row

    def _add_stages(self, modifier):
        """Every stat, always, with its stage as six dots.

        Every stat rather than only the moved ones: a row that appears and
        disappears cannot be read by position, so finding out whether Speed
        had dropped meant reading labels. The full list is always in the same
        order, and an untouched stat is simply six grey dots.
        """
        self.body.addWidget(label("STAT STAGES", self.fonts.tiny,
                                  T.TEXT_FAINT))
        for index, name in STAGE_LABELS:
            stage = modifier[index] if index < len(modifier) else 0
            line = QHBoxLayout()
            line.setSpacing(6)
            line.addWidget(label(name, self.fonts.tiny,
                                 T.TEXT_DIM if stage else T.TEXT_FAINT))
            line.addStretch(1)
            dots = StageDots(self)
            dots.set_stage(stage)
            line.addWidget(dots)
            self.body.addLayout(line)

    def set_mon(self, mon, known=True, side="opponent"):
        """Fill in from a bridge snapshot. `known` false shows the locked
        note instead of the numbers -- the whole point of scouting is that
        this is information you have to earn."""
        clear_layout(self.chips)
        clear_layout(self.body)
        accent = T.PLAYER if side == "player" else T.OPPONENT
        self.set_style(border=accent)
        self.name.setText(mon.get("name", "?"))
        for type_name in mon.get("types") or []:
            self.chips.addWidget(Chip(type_name, T.type_color(type_name),
                                      self.fonts))
        # A Pokemon's tier is deliberately not shown outside the Pokedex.
        # It is a roster-balancing label, and next to a Pokemon on the field it
        # only invited "why am I being given a Low one" -- the stats and the
        # typing are what a player can actually act on.

        # What is being done to this Pokemon right now is not secret. You can
        # see a Swords Dance land and hear that it is confused, so hiding the
        # stat stages and conditions behind a scouting roll only meant reading
        # them back out of the battle log. Scouting gates what you could not
        # otherwise know -- the moveset and the IVs -- and nothing else.
        # Conditions are not listed here any more: Confused, Bound and the
        # rest are on the status card that is always on screen, which is
        # where a thing you need to react to this turn belongs. This panel
        # has to be hovered for, so it keeps what you go looking for --
        # the stat stages, the moveset and the IVs.
        self._add_stages(mon.get("modifier") or [])

        if not known:
            self.ability.setText("")
            self.body.addWidget(label(
                # Still names Scout Opponent. The other helper captions went
                # because they restated a button label; this one says how to
                # change the state you are looking at, which nothing else does.
                "Not scouted -- use Scout Opponent to reveal "
                "their moves and IVs.",
                self.fonts.tiny, T.TEXT_DIM, wrap=True))
            self.adjustSize()
            return

        ability = ", ".join(mon.get("ability") or []) or "—"
        self.ability.setText("Ability: %s" % ability)
        moves = mon.get("moves") or {}
        names = [m for m in (mon.get("moveset") or []) if m != "Switching"]
        if names:
            self.body.addWidget(label("MOVES", self.fonts.tiny, T.TEXT_FAINT))
            for move_name in names:
                self.body.addWidget(self._move_row(move_name,
                                                   moves.get(move_name)))
        self.body.addLayout(self._iv_row(mon.get("iv") or [],
                                         mon.get("nominal") or [],
                                         mon.get("total_iv") or 0))
        self.adjustSize()

    def show_at(self, global_point, bounds=None):
        """Place near the pointer, kept inside `bounds` (a global QRect)."""
        self.adjustSize()
        x, y = global_point.x() + 16, global_point.y() + 14
        if bounds is not None:
            x = min(x, bounds.right() - self.width() - 6)
            x = max(x, bounds.left() + 6)
            if y + self.height() > bounds.bottom() - 6:
                y = global_point.y() - self.height() - 12
            y = max(y, bounds.top() + 6)
        self.move(x, y)
        self.show()
        self.raise_()


class StatBar(RoundedPanel):
    """One stat, as a bar filled to where it sits across the whole roster.

    The number alone says nothing -- "110 Speed" is meaningless without
    knowing that it beats four fifths of everything in the game, which is
    exactly what a player wants to know while building a team.
    """

    def __init__(self, name, value, fraction, fonts, parent=None,
                 colour=None):
        super().__init__(parent, bg=T.PANEL_SUNK, border=T.LINE_SOFT,
                         radius=T.RADIUS_SM)
        self.fraction = max(0.0, min(1.0, fraction))
        self.colour = colour or (T.CYAN if self.fraction >= 0.9 else
                                 T.PLAYER if self.fraction >= 0.65 else
                                 T.ACCENT if self.fraction >= 0.35
                                 else T.TEXT_FAINT)
        self.setFixedHeight(22)
        line = QHBoxLayout(self)
        line.setContentsMargins(9, 2, 9, 2)
        line.addWidget(label(name, fonts.tiny, T.TEXT_FAINT))
        line.addStretch(1)
        line.addWidget(label(str(value), fonts.small_bold, self.colour))

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.fraction <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colour = QColor(self.colour)
        colour.setAlpha(58)
        painter.setBrush(colour)
        painter.setPen(Qt.NoPen)
        width = int((self.width() - 2) * self.fraction)
        painter.drawRoundedRect(1, 1, max(2, width), self.height() - 2,
                                T.RADIUS_SM, T.RADIUS_SM)


class TypeBlocks(QWidget):
    """A Pokemon's typing as small colour blocks instead of words.

    "STEEL DRAGON" as two chips is most of a list row; the same information as
    two 14px swatches is a fifth of the width, which is what lets the name
    beside it be shown in full. Three types stack just as happily. The tooltip
    names them for anyone who has not learned the palette yet.
    """

    BLOCK_W = 13
    BLOCK_H = 15
    GAP = 3

    def __init__(self, types, parent=None):
        super().__init__(parent)
        self._types = [str(t) for t in (types or []) if t]
        count = max(1, len(self._types))
        self.setFixedSize(count * self.BLOCK_W + (count - 1) * self.GAP,
                          self.BLOCK_H)
        self.setToolTip(" / ".join(self._types))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        x = 0
        for type_name in self._types:
            colour = QColor(T.type_color(type_name))
            painter.setBrush(QBrush(colour))
            painter.setPen(QPen(colour.darker(150), 1))
            painter.drawRoundedRect(x, 0, self.BLOCK_W, self.BLOCK_H, 3, 3)
            x += self.BLOCK_W + self.GAP


class ElidedLabel(QLabel):
    """A label that shortens its own text with an ellipsis instead of forcing
    the row wider than the panel it lives in.

    A plain QLabel reports its full text as its minimum width, so one long
    name -- "Aegislash (Shield Forme)" -- made every row in the Pokedex's list
    360px wide inside a 310px rail, and the type blocks on the right-hand end
    were pushed outside the clip and simply vanished. Eliding keeps the row
    inside the panel and keeps whatever is beside it visible.
    """

    def __init__(self, text, font, color, parent=None):
        super().__init__(text, parent)
        self._full = text
        self.setFont(font)
        self.setStyleSheet("color: %s; background: transparent;" % color)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setToolTip(text)

    def setText(self, text):
        self._full = text
        self.setToolTip(text)
        super().setText(text)

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(24)          # enough for an ellipsis and a letter
        return hint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(QColor(self.palette().color(
            self.foregroundRole()))))
        painter.setFont(self.font())
        metrics = painter.fontMetrics()
        text = metrics.elidedText(self._full, Qt.ElideRight, self.width())
        painter.drawText(self.rect(), int(self.alignment()), text)
