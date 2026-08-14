"""
The battle arena's background: a gradient plus drifting particles that
change with the field's weather, cross-fading between looks instead of
cutting so a weather change reads as an event rather than a glitch.

One state machine, not five: each weather is a WeatherLook (two gradient
stops, a particle style, a density); switching weather blends the old
look's colours into the new one's over ~900ms while the particle system
swaps generators. Adding a weather the game doesn't have yet -- Trick
Room's purple grid, say -- means adding one WeatherLook, not a new widget.
"""

import os
import random

from PySide6.QtCore import QPoint, QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from GUI import theme as T


class WeatherLook:
    __slots__ = ("top", "bottom", "particle", "density", "speed", "art")

    def __init__(self, top, bottom, particle=None, density=0, speed=1.0,
                 art=None):
        self.top, self.bottom = QColor(top), QColor(bottom)
        self.particle = particle    # "streak" | "drift" | "haze" | None
        self.density = density
        self.speed = speed
        # painted artwork for this weather, in Assets/generated. The gradient
        # is still built above and is what gets used if the file is missing.
        self.art = art


LOOKS = {
    "Clear":     WeatherLook("#0E1626", "#152037", art="clear.jpg"),
    "Sunny":     WeatherLook("#2E2110", "#402C14", particle="glow",
                             density=8, speed=0.4, art="sunny.jpg"),
    "Rain":      WeatherLook("#0A1420", "#122536", particle="streak",
                             density=70, speed=2.8, art="rain.jpg"),
    "Sandstorm": WeatherLook("#2A2011", "#3A2C18", particle="haze",
                             density=55, speed=1.3, art="sandstorm.jpg"),
    "Hail":      WeatherLook("#111E2A", "#1B2E3E", particle="drift",
                             density=50, speed=0.8, art="hail.jpg"),
}

#: Where the two platforms sit in the artwork, as fractions of it: the point
#: a Pokemon's feet should land on. All five backgrounds are the same
#: composition -- a near platform low and left, a far one higher and right --
#: so one pair of anchors serves them all. Mapped through the same cover/crop
#: as the picture itself (see platform_point), so they follow the art at any
#: window size rather than assuming the arena's aspect ratio.
PLATFORMS = {
    "player":   (0.325, 0.855),
    "opponent": (0.715, 0.660),
}
#: a flat tint painted over the whole arena for weather that should feel
#: like it's filling the air, not just decorating it (sand haze, e.g.)
HAZE_TINT = {"Sandstorm": QColor(200, 150, 60, 26)}
DEFAULT_LOOK = LOOKS["Clear"]


class _Particle:
    __slots__ = ("x", "y", "size", "speed", "drift", "alpha")

    def randomize(self, rng, style):
        self.x = rng.uniform(-0.15, 1.0)
        self.y = rng.uniform(-0.15, 1.0)
        self.drift = rng.uniform(-0.15, 0.15)
        if style == "streak":            # rain: thin, fast, uniform-ish
            self.size = rng.uniform(10, 22)
            self.speed = rng.uniform(0.85, 1.2)
            self.alpha = rng.randint(90, 170)
        elif style == "haze":            # sandstorm: big, soft, drifting
            self.size = rng.uniform(2.5, 6.5)
            self.speed = rng.uniform(0.5, 1.3)
            self.alpha = rng.randint(50, 110)
        elif style == "drift":           # hail: small, gentle zigzag
            self.size = rng.uniform(2.0, 4.0)
            self.speed = rng.uniform(0.5, 1.1)
            self.alpha = rng.randint(90, 170)
        else:                            # sun: static shimmer points
            self.size = rng.uniform(1.5, 3.0)
            self.speed = 0.0
            self.alpha = rng.randint(30, 90)


class ArenaBackdrop(QWidget):
    """Sits behind the combatant cards and sprites; siblings just need
    `raise_()` after their own construction to stay on top of it."""

    def __init__(self, parent=None, fps=30, project_root=None):
        super().__init__(parent)
        self._root = project_root
        self._art = {}          # filename -> QPixmap (or None if missing)
        self._placed = None     # last cover/crop, for platform_point
        self._look = DEFAULT_LOOK
        self._blend_from = DEFAULT_LOOK
        self._blend_t = 1.0          # 1.0 == fully settled on self._look
        self._particles = []
        self._rng = random.Random(7)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000 // fps)
        self._respawn(LOOKS["Clear"].density)

    def set_weather(self, name):
        look = LOOKS.get(name, DEFAULT_LOOK)
        if look is self._look:
            return
        self._blend_from, self._look, self._blend_t = self._look, look, 0.0
        self._respawn(look.density)

    def _respawn(self, count):
        style = self._look.particle
        particles = []
        for _ in range(count):
            p = _Particle()
            p.randomize(self._rng, style)
            particles.append(p)
        self._particles = particles

    def _tick(self):
        if self._blend_t < 1.0:
            self._blend_t = min(1.0, self._blend_t + 1.0 / 27)   # ~900ms
        if self._look.particle:
            self._advance_particles()
        self.update()

    def _advance_particles(self):
        style, speed = self._look.particle, self._look.speed
        for p in self._particles:
            if style == "streak":                  # rain: fast, straight down
                p.y += 0.05 * speed * p.speed
                p.x += 0.01 * speed * p.speed        # slight wind lean
            elif style == "drift":                  # hail: gentle zigzag fall
                p.y += 0.014 * speed * p.speed
                p.x += p.drift * 0.012
            elif style == "haze":                    # sandstorm: sidelong
                p.x += 0.022 * speed * p.speed
                p.y += p.drift * 0.004
            elif style == "glow":                    # sun: near-static shimmer
                p.alpha = 30 + int(60 * abs(
                    ((p.y * 97 + p.x * 53) % 1.0) - 0.5) * 2)
            if p.x > 1.05 or p.y > 1.05:
                p.randomize(self._rng, style)
                if style == "streak":
                    p.y = -0.05
                elif style == "haze":
                    p.x = -0.05

    # -- the painted backdrop ---------------------------------------------
    def _pixmap(self, look):
        """The artwork for a look, loaded once. None when there is no file."""
        name = getattr(look, "art", None)
        if not name or not self._root:
            return None
        if name not in self._art:
            path = os.path.join(self._root, "Assets", "generated", name)
            pixmap = QPixmap(path) if os.path.exists(path) else None
            self._art[name] = pixmap if pixmap and not pixmap.isNull() else None
        return self._art[name]

    def _draw_art(self, painter, rect, pixmap, opacity=1.0):
        """Cover and centre-crop, so the art keeps its proportions."""
        scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding,
                               Qt.SmoothTransformation)
        x = (scaled.width() - self.width()) // 2
        y = (scaled.height() - self.height()) // 2
        painter.setOpacity(opacity)
        painter.drawPixmap(self.rect(), scaled,
                           scaled.rect().adjusted(x, y, -x, -y))
        painter.setOpacity(1.0)
        return (scaled.width(), scaled.height(), x, y)

    def platform_point(self, which):
        """Where a Pokemon's feet belong, in this widget's coordinates.

        Worked out from the pixmap and widget sizes directly rather than read
        back from the last paintEvent. Depending on paint state meant the
        answer changed the first time the arena drew itself -- so the Pokemon
        were placed once against a fallback and then jumped when the real
        mapping became available. This is the same cover/crop arithmetic,
        just available before anything has been drawn.
        """
        fx, fy = PLATFORMS.get(which, (0.5, 0.75))
        pixmap = self._pixmap(self._look)
        width, height = max(1, self.width()), max(1, self.height())
        if pixmap is None or pixmap.isNull():
            return QPoint(int(width * fx), int(height * fy))
        scale = max(width / float(pixmap.width()),
                    height / float(pixmap.height()))
        art_w, art_h = pixmap.width() * scale, pixmap.height() * scale
        off_x, off_y = (art_w - width) / 2.0, (art_h - height) / 2.0
        return QPoint(int(art_w * fx - off_x), int(art_h * fy - off_y))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect())

        top = self._blend(self._blend_from.top, self._look.top)
        bottom = self._blend(self._blend_from.bottom, self._look.bottom)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bottom)
        painter.fillRect(rect, gradient)

        # The gradient stays underneath: it is what shows through while one
        # weather cross-fades into the next, and what you get if a file is
        # missing. Painting the outgoing art first and the incoming one over
        # it at the blend factor keeps a weather change a dissolve rather
        # than a cut, which is the whole point of the blend machinery.
        outgoing = self._pixmap(self._blend_from)
        incoming = self._pixmap(self._look)
        placed = None
        if outgoing is not None and self._blend_t < 1.0:
            placed = self._draw_art(painter, rect, outgoing)
        if incoming is not None:
            placed = self._draw_art(painter, rect, incoming,
                                    opacity=self._blend_t)
        self._placed = placed
        if placed:
            # a light veil so the HP cards and sprites stay readable over
            # artwork that is much brighter than the old flat gradient
            painter.fillRect(self.rect(), QColor(6, 14, 32, 46))

        if not self._look.particle:
            return
        self._paint_particles(painter, rect)

        tint = HAZE_TINT.get(self._name_of(self._look))
        if tint:
            painter.fillRect(rect, tint)

    def _name_of(self, look):
        return next((n for n, l in LOOKS.items() if l is look), None)

    def _blend(self, a, b):
        t = self._blend_t
        return QColor(int(a.red() + (b.red() - a.red()) * t),
                      int(a.green() + (b.green() - a.green()) * t),
                      int(a.blue() + (b.blue() - a.blue()) * t))

    def _paint_particles(self, painter, rect):
        style = self._look.particle
        w, h = rect.width(), rect.height()
        painter.setPen(Qt.NoPen)
        for p in self._particles:
            x, y = p.x * w, p.y * h
            if style == "streak":
                color = QColor("#BFE3F2"); color.setAlpha(p.alpha)
                painter.setBrush(color)
                painter.drawRect(QRectF(x, y, 1.6, p.size))
            elif style == "haze":
                color = QColor(T.ACCENT); color.setAlpha(p.alpha)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(x, y), p.size, p.size * 0.5)
            elif style == "drift":
                color = QColor("#E7F6FA"); color.setAlpha(p.alpha)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(x, y), p.size, p.size)
            else:   # glow
                color = QColor(T.ACCENT); color.setAlpha(p.alpha)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(x, y), p.size, p.size)
