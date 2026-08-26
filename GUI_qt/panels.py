"""
Screens the terminal only ever printed as paragraphs: your team's full
detail, what you've scouted about the opponent, your history against them,
the tournament standings, and the end-of-run credits. Each is a QDialog
rather than a main-window panel, since none of them block the game (the
underlying input() has already been answered by the time these show) --
they're reference material the player can leave open, move, or close
whenever.
"""

import os

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import (QColor, QGuiApplication, QPainter,
                           QPixmap)
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QSizePolicy, QSlider, QTabBar,
                               QTabWidget, QVBoxLayout, QWidget)

from GUI import theme as T
from GUI_qt.settings import DIFFICULTIES
from GUI_qt.sprites import DIR_OPPONENT, DIR_PLAYER, show_sprite
from GUI_qt.widgets import (ActionButton, Chip, ElidedLabel, MoveCard,
                            RoundedPanel, StatBar, clear_layout)
from GUI_qt.widgets import label as _label

def _roster_signature(roster):
    """Everything about a team that the team window actually draws.

    Compared against the last one so a state update that changed nothing
    visible costs one tuple build instead of a full rebuild of the rail and
    the detail pane -- see RosterDialog.refresh.
    """
    return tuple(
        (mon.get("name"), mon.get("total"), mon.get("total_iv"),
         bool(mon.get("benched")), mon.get("status"),
         tuple(mon.get("types") or ()), tuple(mon.get("ability") or ()),
         tuple(mon.get("nominal") or ()), tuple(mon.get("iv") or ()),
         tuple(mon.get("moveset") or ()))
        for mon in roster or ())


MOD_LABELS = ("ATK", "DEF", "SPA", "SPD", "SPE")
#: full six, in nominal_base_stats order -- HP included, unlike the old
#: readout which started at index 1 and silently dropped it
STAT_LABELS = ("HP", "ATK", "DEF", "SPA", "SPD", "SPE")


class _ClickableLabel(QLabel):
    """A real subclass, not an instance with mousePressEvent monkey-patched
    onto it. Overriding a bound method directly on a QLabel instance is a
    known-fragile pattern in PySide6/shiboken -- rebuilding the roster
    rail this way on every battle state update was producing intermittent
    native heap-corruption crashes ("free(): invalid pointer"). A proper
    subclass with a signal is the safe equivalent."""

    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()


class _FittedArt(QLabel):
    """A picture that always fills the space the layout gives it.

    Scaling from the *dialog's* resizeEvent was not enough: the label's own
    size settles later than the dialog's, so the artwork ended up drawn to
    whatever the label measured mid-layout -- 480px inside an 825px column.
    Rescaling from the label's own resizeEvent means the two can never
    disagree.
    """

    def __init__(self, picture, parent=None):
        super().__init__(parent)
        self._picture = picture
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: transparent;")
        # the pixmap must not size the column -- the column sizes the pixmap
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(1, 1)
        self.setWordWrap(True)
        self._fit()

    def set_picture(self, picture):
        """Show a different picture, or None to fall back to setText()."""
        self._picture = picture
        if picture is None or picture.isNull():
            self._picture = None
            self.setPixmap(QPixmap())
            return
        self.setText("")
        self._fit()

    def _fit(self):
        if self._picture is None or self._picture.isNull():
            return
        if self.width() < 2 or self.height() < 2:
            return
        # Scaled to *device* pixels, then told what ratio it is drawn at.
        # Qt lays out in logical pixels, so on a 150%-scaled display a pixmap
        # scaled to the label's 680 logical px was being stretched to 1020 real
        # px by the compositor -- a third of the detail thrown away before the
        # screen ever saw it, from 1024px source art that had it to spare.
        # This is the whole reason the portraits looked soft.
        ratio = self.devicePixelRatioF()
        scaled = self._picture.scaled(self.size() * ratio, Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(ratio)
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def changeEvent(self, event):
        # dragged to a monitor with a different scale factor
        super().changeEvent(event)
        if event.type() == QEvent.DevicePixelRatioChange:
            self._fit()


class _ClickableArt(_FittedArt):
    """Artwork that opens full size when you click it.

    A real subclass for the reason _ClickableLabel gives: patching
    mousePressEvent onto a QLabel instance is what was producing intermittent
    native heap corruption.
    """

    clicked = Signal()

    def __init__(self, picture, parent=None):
        super().__init__(picture, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to see it full size")

    def mousePressEvent(self, event):
        self.clicked.emit()


def _rated(comp):
    """"Nickname [rating]" -- the same shape the matchups screen and the
    engine's own boxes use, so a name reads the same everywhere."""
    rating = comp.get("strength")
    if rating is None:
        return comp.get("nickname", "?")
    return "%s [%s]" % (comp.get("nickname", "?"), rating)


def _eyebrow(text, fonts, color=T.ACCENT, parent=None):
    return _label(text.upper(), fonts.eyebrow, color, parent=parent)


def _style_tabs(tabs, fonts):
    """Same tab treatment as the main window's Battle/Log pair, so dialogs
    don't fall back to the platform's default grey tab bar."""
    tabs.setFont(fonts.small_bold)
    tabs.setStyleSheet(
        "QTabWidget::pane { background: %s; border: 1px solid %s;"
        "border-radius: %dpx; }"
        "QTabBar::tab { background: %s; color: %s; padding: 8px 18px;"
        "margin-right: 4px; border-top-left-radius: %dpx;"
        "border-top-right-radius: %dpx; }"
        "QTabBar::tab:selected { background: %s; color: %s; }"
        % (T.PANEL, T.LINE, T.RADIUS_LG, T.PANEL_SUNK, T.TEXT_FAINT,
           T.RADIUS_SM, T.RADIUS_SM, T.PANEL, T.TEXT))
    return tabs


class RosterDialog(QDialog):
    """A team: sprite, typing, tier, ability, stats, full moveset.

    Two tabs over one detail pane -- yours and the opponent's -- because the
    end-of-battle reward asks you to trade one of yours for one of theirs,
    and until now the only readout of their side was the block of text
    choose_pokemon() prints straight into the log. Same view for both sides
    means the numbers line up when you flip between them.

    Stays open and live during a battle: refresh() is called on every state
    update, same as the arena cards.
    """

    SIDES = (("player", "Your Team"), ("opponent", "Opponent Team"))

    def __init__(self, fonts, project_root, parent=None):
        super().__init__(parent)
        self.fonts, self.root_dir = fonts, project_root
        self.rosters = {"player": [], "opponent": []}
        self.opponent_known = False
        self.side = "player"
        self.picked = {"player": 0, "opponent": 0}
        self._dirty = True
        self._signature = None        # see refresh()
        self.setWindowTitle("Teams")
        self.setStyleSheet("background: %s;" % T.BG)
        self.resize(940, 660)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(10)

        # One list, not two tabs. Both teams share the rail -- yours, then
        # theirs underneath -- because flipping a tab to compare two Pokemon
        # means holding one of them in your head. Theirs stay unclickable
        # until you have earned sight of them.

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        outer.addLayout(body, 1)

        rail = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
        rail.setFixedWidth(230)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(10, 10, 10, 10)
        # No heading over the rail: each team writes its own inside
        # _rebuild_rail, and a third one above them just said "YOUR TEAM"
        # twice.
        self.rail_list = QVBoxLayout()
        rail_layout.addLayout(self.rail_list)
        rail_layout.addStretch(1)
        body.addWidget(rail)

        detail = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
        detail_layout = QHBoxLayout(detail)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(18)

        # No sprite here. This view is a stat sheet -- typing, tier, base
        # stats, moveset -- and the picture only pushed the numbers into a
        # narrower column. The Pokemon is on screen in the arena anyway.

        right = QVBoxLayout()
        self.name = _label("\u2014", fonts.hero, T.TEXT)
        right.addWidget(self.name)
        self.chip_row = QHBoxLayout()
        right.addLayout(self.chip_row)
        self.ability = _label("", fonts.body_bold, T.TEXT_DIM)
        right.addWidget(self.ability)
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(6)
        right.addLayout(self.stats_row)
        right.addWidget(_eyebrow("moveset", fonts, T.TEXT_FAINT))
        moves_row1, moves_row2 = QHBoxLayout(), QHBoxLayout()
        self.moves_rows = [moves_row1, moves_row2]
        right.addLayout(moves_row1)
        right.addLayout(moves_row2)
        right.addStretch(1)
        detail_layout.addLayout(right, 1)
        body.addWidget(detail, 1)

        # A way out that is not the title bar. This window is opened from the
        # action bar and from the engine's "view your pokemon", and it owns no
        # prompt -- the engine has already been answered by the time it shows
        # -- so closing it is only ever closing a window.
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(ActionButton("Close", fonts, on_click=self.close))
        outer.addLayout(footer)

    # -- which side is on show ---------------------------------------------
    @property
    def roster(self):
        return self.rosters.get(self.side) or []

    @property
    def selected(self):
        return self.picked.get(self.side, 0)

    def show_side(self, side):
        """Open with one side's Pokemon selected.

        Kept as the entry point even though there are no tabs any more: the
        reward screen asks you to pick one of theirs, and "Inspect Your Team"
        asks for yours, so both still want to land somewhere specific in the
        one list.
        """
        if (self.rosters.get(side) or []):
            self.side = side
            self.picked[side] = min(self.picked.get(side, 0),
                                    max(0, len(self.rosters[side]) - 1))
        # Build first, then show -- and only once.
        #
        # This used to show() and then build, which was visibly wrong twice
        # over. show() fires showEvent, which rebuilds if dirty, and then this
        # rebuilt again: two full passes over both teams. Worse, the rows and
        # panels are constructed with no parent and only reparented when
        # addWidget runs, so with the window already on screen Qt could paint
        # between the two -- and an unparented visible widget is a top-level
        # window. That is where the flurry of little windows before the team
        # appeared came from.
        self._dirty = False
        self._rebuild_rail()
        self._show(self.selected)
        self.show()
        self.raise_()

    def refresh(self, roster, opponent_roster=None, opponent_known=True):
        """Called on every battle-state update, many times a second.

        Two guards, and both of them earn their keep. Rebuilding a full
        widget tree (chips, stat cells, move cards) at that rate is exactly
        the pattern that produced this class's one real bug so far: rapid
        widget churn on a QDialog triggered intermittent native crashes (see
        git history / PR notes).

        The old guard was "only rebuild while visible", which left the window
        the player has *open during a battle* rebuilding fifty-odd widgets
        several times a second -- for a team that had not changed. That is
        most of what made a battle feel heavy, and every one of those
        rebuilds left a drift of detached widgets behind it waiting to be
        collected. So the data is stored unconditionally, and the tree is
        rebuilt only when something it draws is actually different.
        """
        self.rosters["player"] = roster or []
        # None means "you have not earned sight of it", which is different
        # from an empty team -- keep the two apart so the tab can say so.
        self.opponent_known = bool(opponent_known)
        self.rosters["opponent"] = list(opponent_roster or []) \
            if opponent_known else []
        for side, team in self.rosters.items():
            if self.picked.get(side, 0) >= len(team):
                self.picked[side] = 0

        signature = (_roster_signature(self.rosters["player"]),
                     _roster_signature(self.rosters["opponent"]),
                     self.opponent_known)
        if signature == self._signature:
            return                     # nothing on screen would look different
        self._signature = signature

        if self.isVisible():
            self._rebuild_rail()
            self._show(self.selected)
        else:
            self._dirty = True

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_dirty", True):
            self._dirty = False
            self._rebuild_rail()
            self._show(self.selected)

    def _restyle_rail(self):
        """Re-colour the rail without rebuilding it.

        Clicking a name only moves the highlight, but this used to tear down
        and recreate all twelve rows to redraw it -- 28ms a click, which is
        enough to feel like lag when you are comparing Pokemon one after
        another. The rows remember which Pokemon they are for, so shifting the
        highlight is now a font and a colour on each.
        """
        for side, index, row in getattr(self, "_rail_rows", ()):
            chosen = (side == self.side and index == self.picked.get(side, 0))
            accent = T.PLAYER if side == "player" else T.OPPONENT
            row.setFont(self.fonts.body_bold if chosen else self.fonts.body)
            row.setStyleSheet("color: %s; background: transparent;"
                              % (accent if chosen else T.TEXT_DIM))

    def _rebuild_rail(self):
        clear_layout(self.rail_list)
        self._rail_rows = []
        for side, heading in self.SIDES:
            team = self.rosters.get(side) or []
            accent = T.PLAYER if side == "player" else T.OPPONENT
            self.rail_list.addWidget(
                _eyebrow(heading, self.fonts, accent, parent=self))

            if not team:
                if side == "opponent" and not self.opponent_known:
                    text = ("Not scouted yet — win the match, or scout them "
                            "in Scout Opponent.")
                else:
                    text = "Nothing to show."
                self.rail_list.addWidget(
                    _label(text, self.fonts.small, T.TEXT_FAINT, wrap=True,
                           parent=self))
                continue

            for index, mon in enumerate(team):
                chosen = (side == self.side
                          and index == self.picked.get(side, 0))
                colour = accent if chosen else T.TEXT_DIM
                # the total is on the rail as well as in the detail pane --
                # when you are choosing which of six to take, that one number
                # is what you scan down the list for
                text = "%d. %s  ·  %s%s" % (index + 1, mon["name"],
                                            mon.get("total") or "—",
                                            "  (benched)"
                                            if mon.get("benched") else "")
                row = _ClickableLabel(text, self)
                row.setFont(self.fonts.body_bold if chosen
                            else self.fonts.body)
                row.setStyleSheet("color: %s; background: transparent;"
                                  % colour)
                row.setCursor(Qt.PointingHandCursor)
                row.clicked.connect(
                    lambda side=side, index=index: self._select(side, index))
                self.rail_list.addWidget(row)
                self._rail_rows.append((side, index, row))

    def _select(self, side, index):
        self.side = side
        self.picked[side] = index
        self._restyle_rail()          # not a rebuild; see _restyle_rail
        self._show(index)

    def _show(self, index):
        clear_layout(self.chip_row)
        clear_layout(self.stats_row)
        for row in self.moves_rows:
            clear_layout(row)

        if not self.roster:
            self.name.setText("No Pokemon yet")
            self.ability.setText("")
            return

        mon = self.roster[index]
        # No fainted styling here at all: this is a roster reference, and
        # between rounds nothing is fainted (see snap_roster in bridge.py).
        self.name.setText(mon["name"])
        self.name.setStyleSheet("color: %s; background: transparent;" % T.TEXT)
        for type_name in mon.get("types", []):
            self.chip_row.addWidget(Chip(type_name, T.type_color(type_name),
                                         self.fonts, parent=self))
        # no tier chip here -- see the note in widgets.py CombatantCard
        # Still yours, just held back from this round's match -- and still
        # swappable, so it has to be visible here rather than quietly absent
        if mon.get("benched"):
            self.chip_row.addWidget(Chip("benched", T.TEXT_DIM, self.fonts,
                                         parent=self))
        status = mon.get("status", "Normal")
        if status not in ("Normal", "", "Fainted"):
            self.chip_row.addWidget(Chip(
                T.STATUS_SHORT.get(status, status),
                T.STATUS_COLORS.get(status, T.TEXT_DIM), self.fonts,
                parent=self))
        self.chip_row.addStretch(1)

        ability = mon.get("ability") or []
        self.ability.setText("Ability: " + ", ".join(ability) if ability else "")

        # nominal_base_stats (base + IV) -- the same figures the terminal's
        # own team view printed, and comparable on every screen. This used
        # to prefer battle_stats, which holds the doubled in-battle values
        # with *current* HP in slot 0, so one Pokemon read ~150 before a
        # battle and ~300 after one, and HP wasn't shown at all.
        stats = mon.get("nominal") or []
        ivs = mon.get("iv") or []
        for i, label in enumerate(STAT_LABELS):
            if i >= len(stats):
                break
            cell = QVBoxLayout()
            cell.setSpacing(1)
            caption = _label(label, self.fonts.small_bold, T.TEXT_FAINT,
                             parent=self)
            caption.setAlignment(Qt.AlignHCenter)
            cell.addWidget(caption)
            value = _label(str(stats[i]), self.fonts.num_big, T.TEXT,
                           parent=self)
            value.setAlignment(Qt.AlignHCenter)
            value.setMinimumWidth(58)      # room for 3 digits at any scale
            cell.addWidget(value)
            iv = _label("IV %s" % (ivs[i] if i < len(ivs) else "—"),
                       self.fonts.small, T.TEXT_FAINT, parent=self)
            iv.setAlignment(Qt.AlignHCenter)
            cell.addWidget(iv)
            self.stats_row.addLayout(cell)
        self.stats_row.addSpacing(10)
        total = mon.get("total")
        if total:
            cell = QVBoxLayout()
            cell.setSpacing(1)
            caption = _label("TOTAL", self.fonts.small_bold, T.ACCENT,
                             parent=self)
            caption.setAlignment(Qt.AlignHCenter)
            cell.addWidget(caption)
            value = _label(str(total), self.fonts.num_big, T.ACCENT,
                           parent=self)
            value.setAlignment(Qt.AlignHCenter)
            value.setMinimumWidth(64)
            cell.addWidget(value)
            iv = _label("IV %s" % mon.get("total_iv", "—"), self.fonts.small,
                       T.TEXT_FAINT, parent=self)
            iv.setAlignment(Qt.AlignHCenter)
            cell.addWidget(iv)
            self.stats_row.addLayout(cell)
        self.stats_row.addStretch(1)

        moves = mon.get("moves") or {}
        moveset = [m for m in (mon.get("moveset") or []) if m != "Switching"]
        for slot, name in enumerate(moveset[:4]):
            meta = moves.get(name) or {"name": name, "type": "Normal",
                                       "category": "Status", "power": 0,
                                       "accuracy": None, "priority": 0}
            self.moves_rows[slot // 2].addWidget(
                MoveCard(meta, "", self.fonts, parent=self))


#: smallest the About Opponent portrait column is allowed to get
ART_WIDTH = 460


class OpponentInfoDialog(QDialog):
    """A scouting report: the competitor's artwork, tier and write-up, plus
    -- if the scouting roll went your way -- their strategy and their whole
    team. The artwork and the write-up show every time; the roll is taken
    once per round by the engine and remembered, so re-opening this cannot
    turn a failure into a success."""

    def __init__(self, info, fonts, project_root=".", parent=None):
        super().__init__(parent)
        self.setWindowTitle("About %s" % info["nickname"])
        self.setStyleSheet("background: %s;" % T.BG)
        # Open big. The artwork is a full illustration with its own text
        # panels set into it, and at a modest default you spent the first
        # thing you did in here dragging the corner. Clamped to the screen so
        # it can never open larger than the desktop.
        screen = QGuiApplication.primaryScreen()
        room = screen.availableGeometry() if screen else None
        width = min(1620, room.width() - 60) if room else 1620
        height = min(1120, room.height() - 60) if room else 1120
        self.resize(max(900, width), max(620, height))

        panel = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
        outer = QVBoxLayout(self)
        # Barely any margin: the artwork is the point of this window, so it
        # gets the glass rather than a frame of background around it.
        outer.setContentsMargins(2, 2, 2, 2)
        outer.addWidget(panel)

        # Artwork down the left, report down the right. The write-up used to
        # sit above a narrow scroller with the picture squeezed beside the
        # heading; giving each its own column means the art can be big enough
        # to be worth showing and the report is not a slot four lines tall.
        columns = QHBoxLayout(panel)
        # Tight top and bottom: the artwork is square and the window is
        # landscape, so height is what limits how big it can be drawn -- every
        # pixel of vertical margin costs a pixel of picture.
        columns.setContentsMargins(6, 4, 14, 4)
        columns.setSpacing(12)

        art = info.get("art") or ""
        self._art_path = os.path.join(project_root, art) if art else ""
        self._lightbox = None
        picture = QPixmap(self._art_path) if art else None
        if picture is not None and not picture.isNull():
            self._picture = picture
            # Clickable, the same as the Pokedex's portraits: this window
            # already gives the artwork most of the glass, and it is still a
            # 1024px illustration being drawn into rather less than that.
            self.art_label = _ClickableArt(picture)
            self.art_label.clicked.connect(self.open_lightbox)
            columns.addWidget(self.art_label, 7)
        else:
            self._picture = None
            self.art_label = None

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(_eyebrow("tier %s" % info["tier"], fonts))
        right.addWidget(_label(info["nickname"], fonts.title, T.TEXT))
        # The flavour description is deliberately not repeated here -- it is
        # the same paragraph the artwork already tells you, and it pushed the
        # scouting report out of sight.

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        # Scouting is a roll -- your rating against theirs, boosted by
        # Illuminate or Pressure -- so failing is a normal outcome and is
        # said plainly rather than leaving an empty-looking report.
        if info.get("scout_failed"):
            body_layout.addWidget(_eyebrow("scouting failed", fonts,
                                          T.OPPONENT))
            body_layout.addWidget(_label(
                "You learned nothing useful this time, and this round's roll "
                "is already spent — coming back here will not change it. The "
                "chance depends on your rating against theirs; abilities like "
                "Illuminate and Pressure improve it.",
                fonts.small, T.TEXT_DIM, wrap=True))
        else:
            body_layout.addWidget(_eyebrow("scouting report", fonts, T.PLAYER))
            body_layout.addWidget(_label(
                "Their whole team is now visible in Your Team, on the "
                "Opponent Team tab.", fonts.small, T.PLAYER, wrap=True))

        if info["strategy_revealed"] and info.get("strategy"):
            body_layout.addWidget(_eyebrow("their strategy", fonts, T.VIOLET))
            body_layout.addWidget(_label(info["strategy"], fonts.small,
                                        T.TEXT, wrap=True))
        if info["scouted_text"] and not info.get("scout_failed"):
            body_layout.addWidget(_label(info["scouted_text"], fonts.small,
                                        T.TEXT_DIM, wrap=True))
        body_layout.addStretch(1)
        scroll.setWidget(body)
        right.addWidget(scroll, 1)

        # Same as the team window: a Close under the report rather than only
        # the title bar. It sits in the report column, not across the window,
        # so it never lands on top of the artwork.
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(ActionButton("Close", fonts, on_click=self.close))
        right.addLayout(footer)

        columns.addLayout(right, 3)

    # The artwork looks after its own scaling -- see _FittedArt. It fills the
    # column, upscaling past the source's 1024px if the window is bigger;
    # slightly soft beats a picture that never used more than a third of the
    # window it is the point of.

    def open_lightbox(self):
        """The picture on its own, as large as the screen allows.

        Even with most of this window given to it the artwork is sharing space
        with the report, and it is a full illustration with its own text
        panels set into it -- small print that is only really readable at
        something close to full size.
        """
        if not self._art_path:
            return False
        if self._lightbox is None:
            self._lightbox = ArtLightbox(self.window())
        return self._lightbox.show_picture(self._art_path)


class SettingsDialog(QDialog):
    """Difficulty (next-launch) and volume.

    Volume used to live in the always-visible scoreboard header, but that
    bar's natural width (title, five score columns, a toggle, a slider,
    three buttons, all in one non-wrapping row) came out to roughly 1900px --
    comfortably wider than a lot of laptop screens. Folding it in here is
    what let the header, and so the whole window, actually fit.
    """

    def __init__(self, fonts, current_difficulty, volume, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setStyleSheet("background: %s;" % T.BG)
        self.resize(460, 300)
        self.on_difficulty_change = None      # set by caller
        self.on_volume_change = None

        panel = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
        outer = QVBoxLayout(self)
        outer.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        layout.addWidget(_eyebrow("difficulty", fonts))
        layout.addWidget(_label(
            "Beginner holds every opponent to the simple battle AI, however "
            "highly rated they are.", fonts.small, T.TEXT_DIM, wrap=True))

        row = QHBoxLayout()
        for value, label, blurb in DIFFICULTIES:
            button = ActionButton(
                label, fonts, sub=blurb, accent=T.ACCENT,
                emphasis=(value == current_difficulty),
                on_click=lambda v=value: self._pick_difficulty(v))
            row.addWidget(button)
        layout.addLayout(row)

        self.difficulty_note = _label(
            "Takes effect next time you start the game.", fonts.small,
            T.TEXT_FAINT, wrap=True)
        layout.addWidget(self.difficulty_note)

        layout.addWidget(_eyebrow("sound", fonts))
        volume_row = QHBoxLayout()
        volume_row.addWidget(_label("Volume", fonts.body_bold, T.TEXT))
        volume_slider = QSlider(Qt.Horizontal)
        volume_slider.setRange(0, 100)
        volume_slider.setValue(volume)
        volume_slider.valueChanged.connect(self._pick_volume)
        volume_row.addWidget(volume_slider, 1)
        layout.addLayout(volume_row)
        layout.addStretch(1)

    def _pick_difficulty(self, value):
        if self.on_difficulty_change:
            self.on_difficulty_change(value)
        self.difficulty_note.setText(
            "Set to %s. Takes effect next time you start the game."
            % next(l for v, l, _ in DIFFICULTIES if v == value))

    def _pick_volume(self, value):
        if self.on_volume_change:
            self.on_volume_change(value)


class HistoryDialog(QDialog):
    """Your record against this opponent, and how each meeting went.

    Nothing else. It used to sit two scrolling career histories side by side,
    which is not what anyone reads seconds before a match; the main menu's
    HISTORY screen still has all of that.

    One long-lived instance that refresh() refills, like RosterDialog and
    StandingsDialog -- a fresh dialog per visit piled up hidden children on
    the window, and could not be raised back to the front on a second look.
    """

    def __init__(self, fonts, parent=None):
        super().__init__(parent)
        self.fonts = fonts
        self.setWindowTitle("Match History")
        self.setStyleSheet("background: %s;" % T.BG)
        self.resize(540, 420)

        panel = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)
        shell = QVBoxLayout(panel)
        shell.setContentsMargins(22, 18, 22, 16)
        shell.setSpacing(8)

        shell.addWidget(_eyebrow("head to head", fonts))
        names = QHBoxLayout()
        self.you = _label("You", fonts.body_bold, T.PLAYER)
        self.record = _label("0  –  0", fonts.hero, T.TEXT)
        self.them = _label("Opponent", fonts.body_bold, T.OPPONENT)
        names.addWidget(self.you)
        names.addStretch(1)
        names.addWidget(self.record)
        names.addStretch(1)
        names.addWidget(self.them)
        shell.addLayout(names)

        self.note = _label("", fonts.small, T.TEXT_DIM, wrap=True)
        shell.addWidget(self.note)

        self.caption = _eyebrow("every meeting", fonts, T.TEXT_FAINT)
        shell.addWidget(self.caption)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        self.meetings = QVBoxLayout(body)
        self.meetings.setContentsMargins(0, 0, 0, 0)
        self.meetings.setSpacing(5)
        self.scroll.setWidget(body)
        shell.addWidget(self.scroll, 1)

        close = ActionButton("Close", fonts, on_click=self.close)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        shell.addLayout(row)

    def refresh(self, info):
        info = info or {}
        wins, losses = info.get("wins", 0), info.get("losses", 0)
        played = wins + losses
        meetings = info.get("meetings") or []
        self.you.setText(info.get("you", "You"))
        self.them.setText(info.get("opponent", "Opponent"))
        self.record.setText("%d  –  %d" % (wins, losses))

        if not played:
            self.note.setText("You have never faced %s before."
                              % info.get("opponent", "them"))
        elif not meetings:
            # An older save carries the tally but no scorelines -- those are
            # only recorded from this version on.
            self.note.setText(
                "Met %d time%s. Scorelines were not recorded for these."
                % (played, "" if played == 1 else "s"))
        else:
            self.note.setText("Met %d time%s."
                              % (played, "" if played == 1 else "s"))

        clear_layout(self.meetings)
        self.caption.setVisible(bool(meetings))
        self.scroll.setVisible(bool(meetings))
        for index, pair in enumerate(meetings, start=1):
            mine, theirs = (list(pair) + [0, 0])[:2]
            # Three-way: the tournament settles a level match on rating, so an
            # equal scoreline should never be recorded -- but calling one
            # "lost" would be simply untrue.
            outcome = "won" if mine > theirs else \
                "drew" if mine == theirs else "lost"
            accent = {"won": T.PLAYER, "drew": T.TEXT_DIM,
                      "lost": T.OPPONENT}[outcome]
            row = RoundedPanel(None, bg=T.mix(T.PANEL, accent, 0.10),
                               border=accent, radius=T.RADIUS_SM)
            line = QHBoxLayout(row)
            line.setContentsMargins(11, 6, 11, 6)
            line.addWidget(_label("#%d" % index, self.fonts.small,
                                  T.TEXT_FAINT))
            line.addWidget(Chip(outcome, accent, self.fonts))
            line.addStretch(1)
            line.addWidget(_label("%d  –  %d" % (mine, theirs),
                                  self.fonts.body_bold, accent))
            self.meetings.addWidget(row)
        self.meetings.addStretch(1)

    def present(self, info):
        """Fill in and come to the front.

        raise_() and activateWindow() are the point of this method: the main
        window is borderless fullscreen, so a dialog that is merely shown
        stays behind it and the screen looks like nothing happened.
        """
        self.refresh(info)
        self.show()
        self.raise_()
        self.activateWindow()


class _RosterRow(RoundedPanel):
    """One clickable competitor in the Opponents tab."""

    clicked = Signal(int)

    def __init__(self, entry, fonts, parent=None):
        super().__init__(parent, bg=T.PANEL, border=T.LINE_SOFT,
                         radius=T.RADIUS_SM)
        self.index = entry.get("index", 0)
        self.setCursor(Qt.PointingHandCursor)
        line = QHBoxLayout(self)
        line.setContentsMargins(11, 5, 11, 5)
        line.setSpacing(7)
        line.addWidget(_label("%2d" % self.index, fonts.small, T.TEXT_FAINT))
        line.addWidget(_label(str(entry.get("nickname", "?")),
                              fonts.body_bold,
                              T.PLAYER if entry.get("is_player") else T.TEXT))
        line.addStretch(1)
        if entry.get("tier"):
            line.addWidget(_label(str(entry["tier"]), fonts.tiny,
                                  T.TEXT_FAINT))
        line.addWidget(_label("%s" % entry.get("rating", ""), fonts.small,
                              T.CYAN))

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)

    def mark(self, on):
        self.set_style(bg=T.mix(T.PANEL, T.ACCENT, 0.22) if on else T.PANEL,
                       border=T.ACCENT if on else T.LINE_SOFT,
                       border_width=2 if on else 1)


class _StatRow(RoundedPanel):
    """One stat as base + IV, with the bar scaled against the rival's total.

    Base and IV are kept apart deliberately: base is what the species is
    worth and never changes, IV is what this individual rolled. A single
    combined number hides which of the two you are actually looking at, and
    they mean completely different things when deciding a trade.
    """

    def __init__(self, name, base, iv, ceiling, better, fonts, parent=None):
        total = base + iv
        colour = (T.PLAYER if better > 0 else
                  T.OPPONENT if better < 0 else T.TEXT_DIM)
        super().__init__(parent, bg=T.PANEL_SUNK, border=T.LINE_SOFT,
                         radius=T.RADIUS_SM)
        self.fraction = min(1.0, total / float(max(1, ceiling)))
        self.colour = colour
        self.setFixedHeight(24)
        line = QHBoxLayout(self)
        line.setContentsMargins(9, 2, 9, 2)
        line.setSpacing(6)
        line.addWidget(_label(name, fonts.tiny, T.TEXT_FAINT))
        line.addStretch(1)
        line.addWidget(_label(str(base), fonts.small, T.TEXT))
        line.addWidget(_label("+%d" % iv, fonts.tiny,
                              T.CYAN if iv >= 28 else T.TEXT_FAINT))
        line.addWidget(_label(str(total), fonts.small_bold, colour))

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.fraction <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colour = QColor(self.colour)
        colour.setAlpha(52)
        painter.setBrush(colour)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(1, 1, max(2, int((self.width() - 2)
                                                * self.fraction)),
                                self.height() - 2, T.RADIUS_SM, T.RADIUS_SM)


class CompareDialog(QDialog):
    """One of yours beside one of theirs, and the reward screen's controls.

    This replaces both the old side-by-side view and the separate team viewer:
    everything the old viewer had -- base stats, IVs, ability, the full
    moveset with type and power -- is here, on both sides at once. The reward
    screen asks you to trade a Pokemon for a Pokemon, and reading one side,
    switching tab and trying to remember was never a good way to answer that.

    It also drives the screen. The engine asks yes/no and then for indexes;
    those questions are answered from here, so the player picks Pokemon by
    clicking them and presses Proceed rather than typing numbers.
    """

    #: nominal_base_stats / base_stats / iv order
    STATS = ("HP", "ATK", "DEF", "SPA", "SPDEF", "SPE")
    SIDES = (("player", "Yours", T.PLAYER), ("opponent", "Theirs", T.OPPONENT))
    #: a fixed box for the sprite. show_sprite fits the longest edge into it
    #: and never enlarges, so the panel below never moves as you click around.
    SPRITE_BOX = 190

    #: Proceed, with the index of whatever is selected on the side being asked
    #: about (-1 when the question is a plain yes/no)
    proceed = Signal(int)
    #: Not Proceed
    declined = Signal()

    def __init__(self, fonts, project_root=".", parent=None):
        super().__init__(parent)
        self.fonts = fonts
        self.root_dir = project_root
        self.rosters = {"player": [], "opponent": []}
        self.picked = {"player": 0, "opponent": 0}
        self.asking = None          # which side the engine wants an index from
        self._sized = False         # see open_for
        self._answering = False     # a question is live here; see closeEvent
        self.setWindowTitle("Compare")
        # No close button, and Escape does nothing (see keyPressEvent). This
        # window *is* the question -- the engine is blocked waiting on it and
        # the action bar behind is empty -- and its own buttons already offer
        # the way out: keeping your team, or letting the organiser pick. A
        # cross on the frame only looked like a third option that quietly
        # answered nothing. closeEvent and reject() still decline rather than
        # say nothing, because a window manager can close a window whatever
        # its flags say, and being stranded is worse than a declined swap.
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint
                            | Qt.WindowTitleHint)
        self.setStyleSheet("background: %s;" % T.BG)
        # Balanced rather than rigid: the two halves are always the same
        # width, and the window is sized once from the screen and left alone.
        # It used to grow a little every time the selection changed -- six long
        # names in the picker row, or a Pokemon with four long moves, widened
        # one half and the whole window with it. Equal columns plus a picker
        # that wraps is what keeps it even; pinning the size outright was the
        # wrong answer, since the halves could still be uneven inside it.
        screen = QGuiApplication.primaryScreen()
        room = screen.availableGeometry() if screen else None
        self.resize(min(1180, room.width() - 40) if room else 1120,
                    min(820, room.height() - 40) if room else 780)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        # Both of these wrap, and a wrapped QLabel reports the width it would
        # *like* as its minimum -- which for a two-sentence explanation was
        # several hundred pixels, and became the window's own minimum width.
        # They live in a window that is wide anyway; letting them shrink is
        # what stops them dictating how wide that is.
        self.headline = _label("", fonts.title, T.TEXT)
        self.headline.setMinimumWidth(200)
        self.headline.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        outer.addWidget(self.headline)
        self.subline = _label("", fonts.small, T.TEXT_DIM, wrap=True)
        self.subline.setMinimumWidth(220)
        self.subline.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        outer.addWidget(self.subline)

        self.columns = {}
        split = QHBoxLayout()
        split.setSpacing(12)
        for side, title, accent in self.SIDES:
            panel = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
            # identical width whatever is in them, so the window reads as two
            # even halves instead of one fat column and one thin one
            panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            panel.setMinimumWidth(330)
            box = QVBoxLayout(panel)
            box.setContentsMargins(14, 12, 14, 12)
            box.setSpacing(7)
            heading = _label(title, fonts.title, accent)
            box.addWidget(heading)
            chips = QGridLayout()
            chips.setHorizontalSpacing(4)
            chips.setVerticalSpacing(4)
            box.addLayout(chips)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            # a small minimum, so a Pokemon with four long move names cannot
            # push the window's own minimum size up
            scroll.setMinimumHeight(180)
            scroll.setStyleSheet(
                "QScrollArea { border: none; background: transparent; }")
            holder = QWidget()
            holder.setStyleSheet("background: transparent;")
            detail = QVBoxLayout(holder)
            detail.setContentsMargins(0, 0, 0, 0)
            detail.setSpacing(6)
            scroll.setWidget(holder)
            box.addWidget(scroll, 1)
            self.columns[side] = {"chips": chips, "detail": detail,
                                  "accent": accent, "heading": heading}
            split.addWidget(panel, 1)
        outer.addLayout(split, 1)

        self.note = _label("", fonts.small, T.TEXT_FAINT, wrap=True)
        self.note.setMinimumWidth(220)
        self.note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        outer.addWidget(self.note)

        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(8)
        outer.addLayout(self.buttons)

    # -- the screen the engine is asking about -----------------------------
    def open_for(self, stage, player_roster, opponent_roster, labels):
        """`stage` names the question, `labels` is what the buttons should say
        for it -- taking one of theirs and swapping are not the same offer, and
        the buttons should not pretend otherwise."""
        self.asking = stage.get("asking")
        self.rosters["player"] = list(player_roster or [])
        self.rosters["opponent"] = list(opponent_roster or [])
        for side, _, _ in self.SIDES:
            if not (0 <= self.picked.get(side, 0)
                    < len(self.rosters[side])):
                self.picked[side] = 0
            self._build_pickers(side)
        # Sized on the first open, not on every one: the halves are equal and
        # the content can no longer stretch them, so one comfortable size is
        # enough -- and because it is a resize rather than a fixed size, the
        # window can still be dragged smaller if you want it out of the way.
        if not self._sized:
            self._sized = True
            screen = QGuiApplication.primaryScreen()
            room = screen.availableGeometry() if screen else None
            self.resize(min(1180, room.width() - 40) if room else 1120,
                        min(820, room.height() - 40) if room else 780)
        self.headline.setText(stage.get("headline", "Compare"))
        self.subline.setText(stage.get("subline", ""))
        self._build_buttons(labels)
        self._draw()
        # From here until one of the buttons answers, this window is the only
        # thing on screen that can reply to the engine. See closeEvent.
        self._answering = True
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        """Closing the window is an answer, not a way out of the question.

        The reward screen empties the action bar and hands the whole question
        to this window. Dismissing it with the X or with Escape used to say
        nothing at all, which left the engine blocked inside input() with no
        control on screen able to reach it -- the game just stopped, and the
        only way out was to type into the fallback box. Closing now means the
        same as the decline button.
        """
        answering = self._answering
        self._answering = False
        super().closeEvent(event)
        if answering:
            self.declined.emit()

    def reject(self):
        """Escape does not come through closeEvent.

        QDialog turns Escape into reject(), which hides the window through
        done() -- no close event is ever sent, so handling this in closeEvent
        alone left Escape as a second way to strand the engine. Both routes
        mean the same thing, and whichever runs first clears the flag, so the
        decline is emitted exactly once.
        """
        answering = self._answering
        self._answering = False
        super().reject()
        if answering:
            self.declined.emit()

    def keyPressEvent(self, event):
        """Swallow Escape while a question is live.

        QDialog's default is to reject() on Escape, which would put the window
        away -- and the whole point of having no close button is that this
        screen is answered with its own buttons, not dismissed.
        """
        if event.key() == Qt.Key_Escape and self._answering:
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event):
        # hide() is how the buttons put the window away once they have already
        # answered, so there is nothing left to decline after one of them.
        self._answering = False
        super().hideEvent(event)

    def _build_buttons(self, labels):
        """Named for what they do, not "Proceed" and "Not Proceed".

        Three identically-labelled Proceeds in a row was the confusing part of
        this screen: nothing said which press was the one that committed. "Swap
        these two" and "Keep my team" say it outright, and there is only one of
        each.
        """
        clear_layout(self.buttons)
        self.buttons.addWidget(ActionButton(
            "Fast Comparison", self.fonts,
            sub="your weakest against their strongest",
            accent=T.CYAN, on_click=self.fast_comparison))
        self.buttons.addStretch(1)
        if labels.get("proceed"):
            self.buttons.addWidget(ActionButton(
                labels.get("verb") or "Proceed", self.fonts,
                sub=labels.get("proceed"), accent=T.PLAYER, emphasis=True,
                on_click=self._on_proceed))
        if labels.get("decline"):
            self.buttons.addWidget(ActionButton(
                "No thanks", self.fonts, sub=labels.get("decline"),
                accent=T.OPPONENT, on_click=self._on_decline))

    def _on_proceed(self):
        # the index is a courtesy for a caller that only cares about one side;
        # the window's own `picked` is the real answer, and holds both
        self.proceed.emit(self.picked.get(self.asking, -1)
                          if self.asking in self.rosters else -1)

    def _on_decline(self):
        self.declined.emit()

    def fast_comparison(self):
        """Your weakest beside their strongest.

        A beginner's question is "am I being offered an upgrade", and the
        clearest version of that is the worst thing you own against the best
        thing they own. Totals include IVs, because that is the Pokemon you
        would actually be trading.
        """
        mine = self.rosters["player"]
        theirs = self.rosters["opponent"]
        if mine:
            self.picked["player"] = min(
                range(len(mine)), key=lambda i: sum(self._total(mine[i])))
        if theirs:
            self.picked["opponent"] = max(
                range(len(theirs)), key=lambda i: sum(self._total(theirs[i])))
        self._draw()

    # -- the two columns ---------------------------------------------------
    PICKER_COLUMNS = 3

    def _build_pickers(self, side):
        """The roster as name chips, three to a row.

        A single row of six chips is as wide as the longest six names put
        together, which is what was stretching one half of the window past the
        other. Wrapping bounds it at three names however long they are.
        """
        column = self.columns[side]
        clear_layout(column["chips"])
        for index, mon in enumerate(self.rosters[side]):
            chip = _PickChip(index, mon.get("name", "?"), self.fonts,
                             column["accent"])
            chip.clicked.connect(
                lambda position, s=side: self._pick(s, position))
            column["chips"].addWidget(chip, index // self.PICKER_COLUMNS,
                                      index % self.PICKER_COLUMNS)

    def _pick(self, side, index):
        self.picked[side] = index
        self._draw()

    def _iter_chips(self, side):
        layout = self.columns[side]["chips"]
        for position in range(layout.count()):
            item = layout.itemAt(position)
            widget = item.widget() if item else None
            if isinstance(widget, _PickChip):
                yield widget

    def _base(self, mon):
        values = list(mon.get("base") or [])
        if values:
            return [int(v) for v in values[:6]] + [0] * (6 - len(values[:6]))
        # an older snapshot without base: nominal is base + iv
        nominal = self._total(mon)
        iv = self._iv(mon)
        return [max(0, n - v) for n, v in zip(nominal, iv)]

    def _iv(self, mon):
        values = list(mon.get("iv") or [])
        return [int(v) for v in values[:6]] + [0] * (6 - len(values[:6]))

    def _total(self, mon):
        values = list(mon.get("nominal") or mon.get("stats") or [])
        if values:
            return [int(v) for v in values[:6]] + [0] * (6 - len(values[:6]))
        return [b + v for b, v in zip(self._base(mon), self._iv(mon))]

    def _draw(self):
        chosen = {}
        for side, _, _ in self.SIDES:
            roster = self.rosters[side]
            index = self.picked.get(side, 0)
            chosen[side] = roster[index] if 0 <= index < len(roster) else None

        mine, theirs = chosen["player"], chosen["opponent"]
        my_total = self._total(mine) if mine else [0] * 6
        their_total = self._total(theirs) if theirs else [0] * 6
        # scaled to the better of the two per stat, so the longer bar wins
        ceilings = [max(a, b, 1) for a, b in zip(my_total, their_total)]

        for side, title, accent in self.SIDES:
            mon = chosen[side]
            own = my_total if side == "player" else their_total
            other = their_total if side == "player" else my_total
            marker = ""
            if self.asking in (side, "both"):
                marker = "  ← selected"
            self.columns[side]["heading"].setText(title + marker)
            self._draw_side(side, mon, own, other, ceilings, accent)

        if mine and theirs:
            ahead = sum(1 for a, b in zip(my_total, their_total) if a > b)
            behind = sum(1 for a, b in zip(my_total, their_total) if b > a)
            summary = ("%s leads on %d of 6 stats; %s on %d.  Totals include "
                       "IVs." % (mine.get("name", "yours"), ahead,
                                 theirs.get("name", "theirs"), behind))
            # spell out the actual trade, so the button press is never a guess
            if self.asking == "both":
                summary = ("Swapping would give up %s and take %s.  "
                           % (mine.get("name", "?"), theirs.get("name", "?"))
                           + summary)
            elif self.asking == "opponent":
                summary = ("Taking %s.  " % theirs.get("name", "?")) + summary
            self.note.setText(summary)
        else:
            self.note.setText("")

        for side, _, _ in self.SIDES:
            for chip in self._iter_chips(side):
                chip.mark(chip.index == self.picked.get(side))

    def _draw_side(self, side, mon, own, other, ceilings, accent):
        detail = self.columns[side]["detail"]
        clear_layout(detail)
        if mon is None:
            detail.addWidget(_label("Nothing on this side.", self.fonts.body,
                                    T.TEXT_FAINT))
            detail.addStretch(1)
            return

        head = QHBoxLayout()
        head.addWidget(_label(mon.get("name", "?"), self.fonts.hero, T.TEXT))
        head.addStretch(1)
        # no tier chip on the compare screen either
        detail.addLayout(head)

        chips = QHBoxLayout()
        chips.setSpacing(4)
        for type_name in mon.get("types") or []:
            chips.addWidget(Chip(type_name, T.type_color(type_name),
                                 self.fonts))
        chips.addStretch(1)
        detail.addLayout(chips)

        # A fixed box with the sprite centred in it, so the stats below do not
        # shuffle up and down as the selection moves between a tall Pokemon and
        # a flat one -- and so the sprite is never stretched to fill the column.
        box = QWidget()
        box.setFixedHeight(self.SPRITE_BOX)
        box.setStyleSheet("background: transparent;")
        holder = QVBoxLayout(box)
        holder.setContentsMargins(0, 0, 0, 0)
        sprite = QLabel()
        sprite.setAlignment(Qt.AlignCenter)
        show_sprite(sprite, mon.get("sprite", ""),
                    DIR_PLAYER if side == "player" else DIR_OPPONENT,
                    self.root_dir, target=self.SPRITE_BOX)
        holder.addWidget(sprite, 0, Qt.AlignCenter)
        detail.addWidget(box)

        detail.addWidget(_label(
            "Ability: %s" % (", ".join(mon.get("ability") or []) or "—"),
            self.fonts.small, T.TEXT_DIM, wrap=True))

        base, iv = self._base(mon), self._iv(mon)
        totals = sum(own)
        other_total = sum(other)
        caption = QHBoxLayout()
        caption.addWidget(_eyebrow("base + iv = stat", self.fonts,
                                   T.TEXT_FAINT))
        caption.addStretch(1)
        caption.addWidget(_label(
            "total %d%s" % (totals, "" if not other_total else
                            "  (%+d)" % (totals - other_total)),
            self.fonts.body_bold,
            T.PLAYER if totals > other_total else
            T.OPPONENT if totals < other_total else T.TEXT_DIM))
        detail.addLayout(caption)

        for position, name in enumerate(self.STATS):
            mine_value = own[position] if len(own) > position else 0
            rival = other[position] if len(other) > position else 0
            detail.addWidget(_StatRow(
                name, base[position], iv[position], ceilings[position],
                (mine_value > rival) - (mine_value < rival), self.fonts))
        detail.addWidget(_label("IV total %d / 186" % sum(iv),
                                self.fonts.tiny, T.TEXT_FAINT))

        moves = [m for m in (mon.get("moveset") or []) if m != "Switching"]
        if moves:
            detail.addWidget(_eyebrow("moveset", self.fonts, T.TEXT_FAINT))
            known = mon.get("moves") or {}
            for move_name in moves:
                detail.addWidget(self._move_row(move_name,
                                                known.get(move_name)))
        detail.addStretch(1)

    def _move_row(self, move_name, move):
        """Type, category and power -- what the team viewer used to show."""
        move = move or {}
        colour = T.type_color(move.get("type", "Normal"))
        row = RoundedPanel(None, bg=T.mix(T.PANEL_SUNK, colour, 0.14),
                           border=colour, radius=T.RADIUS_SM)
        line = QHBoxLayout(row)
        line.setContentsMargins(9, 3, 9, 3)
        line.setSpacing(7)
        name = _label(move_name, self.fonts.small_bold, T.TEXT)
        name.setMinimumWidth(1)          # may shrink; the meta must stay whole
        line.addWidget(name)
        line.addStretch(1)
        if move:
            # Type, category and power -- and nothing else. The full form
            # ("Ground · PHY · PWR 100 · ACC 100%") forced the column wider
            # than its own scroll viewport, which clipped the right-hand end of
            # every stat row above it. Accuracy is the least interesting of the
            # four and is the one that goes.
            bits = [move.get("type", ""),
                    T.CATEGORY_GLYPH.get(move.get("category"), "STA")]
            if move.get("power"):
                bits.append("%d" % move["power"])
            line.addWidget(_label(" · ".join(b for b in bits if b),
                                  self.fonts.tiny, T.TEXT_DIM))
        return row


class _PickChip(Chip):
    """A clickable name chip, for choosing which Pokemon a column shows."""

    clicked = Signal(int)

    #: longest name shown on a chip; the rest is an ellipsis with the full
    #: name on hover. Six chips of full-length names is what was stretching
    #: one half of the window wider than the other.
    MAX_CHARS = 13

    def __init__(self, index, text, fonts, accent, parent=None):
        shown = text if len(text) <= self.MAX_CHARS             else text[:self.MAX_CHARS - 1] + "…"
        super().__init__(shown, T.TEXT_FAINT, fonts, parent)
        self.index = index
        self.accent = accent
        self.setToolTip(text)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)

    def mark(self, on):
        colour = self.accent if on else T.TEXT_FAINT
        c = QColor(colour)
        self.setStyleSheet(
            "background: rgba(%d,%d,%d,%d); color: %s;"
            "border: 1px solid rgba(%d,%d,%d,%d); border-radius: %dpx;"
            % (c.red(), c.green(), c.blue(), 70 if on else 40, colour,
               c.red(), c.green(), c.blue(), 190 if on else 110, T.RADIUS_SM))


class CareerDialog(QDialog):
    """The main menu's HISTORY screen, as one window you click around in.

    Four tabs, all present the moment it opens: who to look at, the roll of
    champions, the chosen competitor's career, and their record against
    everybody. Picking a name in the first tab fills the last two.

    The engine still drives this underneath -- it asks "read the stats? (Y)",
    then for a number, then "match history? (Y)" -- but the interface answers
    the two yes/no questions itself and takes the number from a click, so the
    player never sees a prompt. Closing the window answers 0 and returns to
    the title screen. See CAREER_PROMPTS in GUI/bridge.py.
    """

    #: how wide this window is allowed to get. The tables inside are the
    #: reason it is generous: a Head to Head row is a name, a rating and a
    #: full record, and there are five tabs of them.
    WIDEST = 1560

    #: rank -> colour, for the championship-history chips
    PODIUM = {1: T.ACCENT, 2: T.TEXT, 3: T.TEXT}
    TABS = ("Opponents", "Champions", "Career", "Tournaments",
            "Head to Head")
    #: the three that belong to whichever competitor is being shown, and have
    #: to be cleared together when that changes -- a competitor with nothing
    #: on record publishes no table at all, and leaving the last one's up
    #: would attribute their record to somebody who has never played
    OWNED_TABS = ("Career", "Tournaments", "Head to Head")

    #: emitted with the competitor's number when a name is clicked
    picked = Signal(int)
    #: emitted when the player closes the window
    dismissed = Signal()

    def __init__(self, fonts, project_root=".", parent=None):
        super().__init__(parent)
        self.fonts = fonts
        self.root_dir = project_root
        self._rows = {}
        self._current = None
        self.setWindowTitle("Career History")
        self.setStyleSheet("background: %s;" % T.BG)
        screen = QGuiApplication.primaryScreen()
        room = screen.availableGeometry() if screen else None
        # As wide as the display allows, up to WIDEST. The old cap was 1180,
        # which was not enough for the tables this window holds: Head to Head
        # is a competitor's name, their rating and a full win/loss record on
        # one row, and Tournaments is a row per championship ever held. Both
        # were being elided or wrapped on a display with plenty of room to
        # spare. It is still a resize rather than a fixed size, so it can be
        # dragged smaller.
        self.resize(min(self.WIDEST, room.width() - 60) if room else 1180,
                    min(880, room.height() - 60) if room else 760)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        self.tabs = _style_tabs(QTabWidget(self), fonts)
        outer.addWidget(self.tabs, 1)
        self.bodies = {title: self._add_tab(title) for title in self.TABS}

        row = QHBoxLayout()
        self.hint = _label("Pick a name to see their career.", fonts.small,
                           T.TEXT_FAINT)
        row.addWidget(self.hint)
        row.addStretch(1)
        row.addWidget(ActionButton("Close", fonts, on_click=self.close))
        outer.addLayout(row)

    def _add_tab(self, title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Vertical only, everywhere. Every row here is a full-width band, so
        # a horizontal bar can only ever mean something has been laid out too
        # wide -- and dragging one sideways to read a list is miserable.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)
        scroll.setWidget(body)
        self.tabs.addTab(scroll, title)
        return layout

    def _select(self, title):
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return

    def present(self, title=None):
        """Come to the front. raise_/activateWindow because the window behind
        this one is borderless fullscreen -- a dialog that is merely shown
        stays behind it and nothing appears to happen."""
        if title:
            self._select(title)
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.dismissed.emit()

    # -- tab 1: who to look at --------------------------------------------
    def show_roster(self, roster):
        """The clickable list. Rebuilt only when the roster itself changes --
        it is published once per pass of the engine's loop, and rebuilding
        fifty-six rows on each pass would throw away the scroll position.

        "Changes" has to mean everything a row *draws*, not just how many rows
        there are. The signature was the index list alone, and every career has
        the same competitors at the same indices -- so opening HISTORY on a
        second save found the signature unchanged, returned early, and left the
        first career's rail on screen: its ratings beside every name, and its
        player's nickname sitting in the list for the rest of the session.
        Clicking a name still worked, because that sends the index and the
        engine reads the right competitor, which is exactly why the reports
        looked correct while the list did not.
        """
        entries = list(roster or [])
        signature = [(entry.get("index"), entry.get("nickname"),
                      entry.get("tier"), entry.get("rating"),
                      entry.get("is_player")) for entry in entries]
        if signature == getattr(self, "_roster_signature", None):
            return
        self._roster_signature = signature
        body = self.bodies["Opponents"]
        clear_layout(body)
        self._rows = {}
        body.addWidget(_eyebrow("pick a competitor", self.fonts))
        for entry in entries:
            row = _RosterRow(entry, self.fonts)
            row.clicked.connect(self._on_pick)
            self._rows[row.index] = row
            body.addWidget(row)
        body.addStretch(1)

    def _on_pick(self, index):
        for number, row in self._rows.items():
            row.mark(number == index)
        self._current = index
        self.picked.emit(index)

    # -- tab 2: who won each championship ---------------------------------
    #: how wide each name on a run path gets. Fixed, so the arrows line up
    #: down the column however long the nicknames are -- a path is read across
    #: *and* compared down, and ragged spacing defeats the second.
    PATH_NAME_WIDTH = 120
    #: the gutter around each arrow. Name, gap, arrow, gap, name -- without
    #: it a name that fills its slot runs straight into the arrow beside it.
    PATH_ARROW_WIDTH = 18
    PATH_GAP = 8
    #: the run number ahead of a path, and the rank beside it on the
    #: Tournaments tab. Fixed for the same reason the name slots are: the
    #: path has to start at the same x on every row or the columns it is
    #: meant to be compared down are no longer columns.
    RUN_TAG_WIDTH = 34
    RANK_WIDTH = 96

    def _path_row(self, steps, colour=None, stretch=True):
        """A run path as "A -> B -> C", each name in a fixed-width slot.

        `steps` is [(name, won)] -- `won` True for green, False for red, or
        None to leave every name in `colour`. The arrows are their own labels
        so they sit between the slots rather than inside them, which is what
        keeps the columns aligned.

        The slot pitch (name + gap + arrow + gap) is deliberately what it was
        before the gap existed, so the gutter is bought out of the name rather
        than added to the row: these rows already sit in a scroller with no
        horizontal bar, and a wider row would push its own tail out of sight.

        `stretch=False` leaves the slack unclaimed for whatever the caller
        puts after the path -- see `_tail_label`.
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(self.PATH_GAP)
        for position, (name, won) in enumerate(steps):
            if position:
                arrow = _label("→", self.fonts.small, T.TEXT_FAINT)
                arrow.setAlignment(Qt.AlignCenter)
                arrow.setFixedWidth(self.PATH_ARROW_WIDTH)
                row.addWidget(arrow)
            if won is None:
                shade = colour or T.TEXT_DIM
            else:
                shade = T.PLAYER if won else T.OPPONENT
            cell = ElidedLabel(str(name), self.fonts.small, shade)
            cell.setFixedWidth(self.PATH_NAME_WIDTH)
            # setFixedWidth is not enough on its own here. ElidedLabel is
            # horizontally Ignored by default -- that is the whole point of it
            # in the Pokedex rail, where a long name must not widen the row --
            # and an Ignored widget reports a width of 0 to the layout. The
            # layout then advanced by the arrow alone, so every name after the
            # first was drawn on top of the one before it: six names stacked
            # in the space of one. Fixed makes the slot it is drawn at the
            # slot the layout reserves.
            cell.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            row.addWidget(cell)
        if stretch:
            row.addStretch(1)
        return row

    def _tail_label(self, text, font, colour):
        """The last thing on a path row, sized from what the path left over.

        A plain label demands its full width, and six rounds of path plus a
        run's winner is wider than the window -- with no horizontal scrollbar
        in these tabs (see `_add_tab`) the overrun is simply unreachable, so
        the tail was cut off rather than shortened. This is the one elastic
        item in the row: ElidedLabel is horizontally Ignored, which both
        expands into the slack and elides when the slack is small, so the
        names keep their fixed slots and the tail gives way instead.
        """
        label = ElidedLabel(str(text), font, colour)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return label

    def show_champions(self, champions):
        body = self.bodies["Champions"]
        clear_layout(body)
        body.addWidget(_eyebrow("CHAMPION OF EACH CHAMPIONSHIP", self.fonts))
        if not champions:
            body.addWidget(_label("No championship has been completed yet.",
                                  self.fonts.body, T.TEXT_FAINT, wrap=True))
        for entry in champions or []:
            row = RoundedPanel(None, bg=T.PANEL, border=T.LINE_SOFT,
                               radius=T.RADIUS_SM)
            line = QHBoxLayout(row)
            line.setContentsMargins(12, 6, 12, 6)
            line.setSpacing(8)
            tag = _label("#%d" % entry.get("run", 0), self.fonts.small,
                         T.TEXT_FAINT)
            tag.setFixedWidth(self.RUN_TAG_WIDTH)
            line.addWidget(tag)
            # Who they got through, on the same line rather than a second one.
            # It says what the title was worth, and it is there for whoever
            # enjoys reading it -- but a row per champion reads as a list, and
            # two rows per champion read as a wall.
            beaten = entry.get("beaten") or []
            if beaten:
                line.addLayout(self._path_row(
                    [(name, None) for name in beaten], T.TEXT_FAINT,
                    stretch=False))
            # No stretch either way: the champion's name is the elastic item
            # here, and a stretch beside it would take the whole row and
            # leave it nothing to be drawn in. See _tail_label.
            line.addWidget(self._tail_label(entry.get("champion", "—"),
                                            self.fonts.body_bold, T.ACCENT))
            body.addWidget(row)
        body.addStretch(1)

    # -- tab 3: one competitor's career -----------------------------------
    def _tile(self, caption, value, colour=None):
        panel = RoundedPanel(None, bg=T.PANEL_SUNK, border=T.LINE_SOFT,
                             radius=T.RADIUS_SM)
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(12, 6, 12, 6)
        inner.setSpacing(0)
        inner.addWidget(_label(caption, self.fonts.tiny, T.TEXT_FAINT))
        inner.addWidget(_label(str(value), self.fonts.title,
                               colour or T.TEXT))
        return panel

    def show_report(self, info):
        info = info or {}
        for title in self.OWNED_TABS:
            clear_layout(self.bodies[title])
        body = self.bodies["Career"]
        self.hint.setText("Showing %s. Pick another name any time."
                          % info.get("nickname", "them"))

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(_label(info.get("nickname", "—"), self.fonts.hero,
                              T.PLAYER if info.get("is_player") else T.TEXT))
        if info.get("tier"):
            head.addWidget(Chip(info["tier"], T.TEXT_FAINT, self.fonts))
        if info.get("rating"):
            head.addWidget(Chip("rated %d" % info["rating"], T.CYAN,
                                self.fonts))
        head.addStretch(1)
        body.addLayout(head)

        # Art on the left, numbers on the right, and the art gets the larger
        # share. These portraits are not just a picture: each one is a full
        # 1024px illustration with the competitor's name, write-up, quote and
        # ace Pokemon set into it. That is why the write-up is not repeated as
        # text beside it -- it is already there, and every pixel the column
        # gives back makes it more readable.
        split = QHBoxLayout()
        split.setSpacing(14)
        art = info.get("art")
        picture = os.path.join(self.root_dir, art) if art else None
        if picture and os.path.exists(picture):
            portrait = _FittedArt(QPixmap(picture))
            portrait.setMinimumSize(340, 340)
            split.addWidget(portrait, 7)
        column = QVBoxLayout()
        column.setSpacing(7)
        split.addLayout(column, 5)
        body.addLayout(split, 1)

        rate = info.get("win_rate")
        tiles = QHBoxLayout()
        tiles.setSpacing(6)
        tiles.addWidget(self._tile("ENTERED", info.get("participation", 0)))
        tiles.addWidget(self._tile("TITLES", info.get("championship", 0),
                                   T.ACCENT if info.get("championship")
                                   else None))
        tiles.addWidget(self._tile("WON", info.get("wins", 0), T.PLAYER))
        tiles.addWidget(self._tile("LOST", info.get("losses", 0), T.OPPONENT))
        tiles.addWidget(self._tile("WIN RATE", "—" if rate is None
                                   else "%.1f%%" % rate))
        tiles.addStretch(1)
        column.addLayout(tiles)

        who = info.get("nickname", "them")
        # The write-up belongs here as much as on the opponent panel -- the
        # player's own career tab used to be a portrait and five numbers.
        blurb = str(info.get("description") or "").strip()
        if blurb:
            column.addWidget(_eyebrow("ABOUT", self.fonts, T.TEXT_FAINT))
            column.addWidget(_label(blurb, self.fonts.small, T.TEXT_DIM,
                                    wrap=True))
        self.show_runs(info.get("runs") or [], who)

        if rate is None:
            nothing = ("There is no match history on record for %s yet."
                       % who)
            column.addWidget(_label(nothing, self.fonts.body, T.TEXT_FAINT,
                                    wrap=True))
            column.addStretch(1)
            # Say so on the other two as well. individual_records() never runs
            # for someone with no record, so nothing would arrive to fill them
            # and an empty tab reads as a bug rather than as "never played".
            self.bodies["Head to Head"].addWidget(
                _label(nothing, self.fonts.body, T.TEXT_FAINT, wrap=True))
            self.bodies["Head to Head"].addStretch(1)
            return

        played = info.get("most_played") or []
        if played:
            column.addWidget(_eyebrow("MOST PLAYED AGAINST", self.fonts,
                                      T.TEXT_FAINT))
            for entry in played:
                column.addWidget(self._record_row(entry))
        column.addStretch(1)
        # A placeholder until individual_records() lands a moment later, so
        # the tab is never blank while the engine catches up.
        self.bodies["Head to Head"].addWidget(
            _label("Loading %s's record…" % who, self.fonts.small,
                   T.TEXT_FAINT))
        self.bodies["Head to Head"].addStretch(1)

    # -- tab 4: every championship they entered ---------------------------
    def show_runs(self, runs, who):
        """One row per championship entered, best finish called out.

        A row each, scrolling down -- this was a strip of chips scrolling
        sideways, and thirty-six of them meant dragging a horizontal bar to
        read your own career.
        """
        body = self.bodies["Tournaments"]
        clear_layout(body)
        if not runs:
            body.addWidget(_label(
                "%s has not entered a championship yet." % who,
                self.fonts.body, T.TEXT_FAINT, wrap=True))
            body.addStretch(1)
            return
        ranks = [entry.get("rank") for entry in runs
                 if isinstance(entry.get("rank"), int)]
        head = QHBoxLayout()
        head.addWidget(_eyebrow("EVERY CHAMPIONSHIP", self.fonts))
        head.addStretch(1)
        if ranks:
            head.addWidget(_label("BEST FINISH: RANK %d  ·  %d ENTERED"
                                  % (min(ranks), len(runs)),
                                  self.fonts.small, T.TEXT_DIM))
        body.addLayout(head)
        for entry in runs:
            rank = entry.get("rank")
            # `entered` is absent on older payloads, so fall back to "there is
            # a rank" rather than calling every run an absence
            entered = entry.get("entered", rank is not None)
            colour = self.PODIUM.get(rank, T.TEXT_FAINT)
            row = RoundedPanel(None, bg=T.mix(T.PANEL, colour, 0.10)
                               if rank == 1 else T.PANEL,
                               border=colour if rank == 1 else T.LINE_SOFT,
                               radius=T.RADIUS_SM)
            line = QHBoxLayout(row)
            line.setContentsMargins(12, 5, 12, 5)
            tag = _label("#%d" % entry.get("run", 0), self.fonts.small,
                         T.TEXT_FAINT)
            tag.setFixedWidth(self.RUN_TAG_WIDTH)
            line.addWidget(tag)
            if entered:
                place = _label("RANK %s" % ("—" if rank is None else rank),
                               self.fonts.body_bold, colour)
                place.setFixedWidth(self.RANK_WIDTH)
                line.addWidget(place)
            else:
                # A run they sat out. Said plainly and dimly, so the row is
                # still there to be counted but does not read as a result.
                line.addWidget(_label("NO PARTICIPATION", self.fonts.small,
                                      T.TEXT_FAINT))
            # Their own way through the bracket, in the same fixed-width
            # arrow format the champion roll uses -- green for a match won,
            # red for the one that ended the run. Read across for the path,
            # down for how far they tended to get.
            path = entry.get("path") or []
            champion = entry.get("champion")
            if path:
                line.addSpacing(12)
                line.addLayout(self._path_row(
                    [(name, won) for name, won in path],
                    stretch=not champion))
            elif not champion:
                # Only when nothing follows -- a stretch beside the tail
                # label would swallow the width the label needs.
                line.addStretch(1)
            if champion:
                line.addWidget(self._tail_label(
                    "Champion: %s" % champion, self.fonts.small, T.TEXT_DIM))
            body.addWidget(row)
        body.addStretch(1)

    # -- tab 5: their record against everybody ----------------------------
    def _record_row(self, entry):
        wins, losses = entry.get("wins", 0), entry.get("losses", 0)
        played = wins + losses
        accent = T.PLAYER if wins > losses else \
            T.OPPONENT if losses > wins else T.TEXT_DIM
        row = RoundedPanel(None, bg=T.PANEL, border=T.LINE_SOFT,
                           radius=T.RADIUS_SM)
        line = QHBoxLayout(row)
        line.setContentsMargins(12, 5, 12, 5)
        line.setSpacing(8)
        line.addWidget(_label(str(entry.get("nickname", "—")),
                              self.fonts.body_bold, T.TEXT))
        # the rating this row is sorted by, so the order on screen is legible
        if entry.get("rating"):
            line.addWidget(_label("[%d]" % entry["rating"], self.fonts.small,
                                  T.CYAN))
        line.addStretch(1)
        # Fixed widths, right-aligned, so the record and the percentage sit in
        # the same place on every row. They used to be laid out one after the
        # other, so "12 W 3 L" pushed the percentage further right than
        # "0 W 0 L" did and no two rows lined up -- which matters now that
        # every opponent gets a row whether they have been played or not.
        record = _label("%d W   %d L" % (wins, losses), self.fonts.small,
                        T.TEXT_DIM if played else T.TEXT_FAINT)
        record.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        record.setFixedWidth(92)
        line.addWidget(record)
        rate = entry.get("win_rate")
        if rate is None and played:
            rate = round(100.0 * wins / played)
        # Never faced: no percentage at all rather than a 0% that would read as
        # "played and lost every time".
        percent = _label("" if not played else "%d%%" % (rate or 0),
                         self.fonts.body_bold, accent)
        percent.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        percent.setFixedWidth(52)
        line.addWidget(percent)
        return row

    def show_records(self, info):
        info = info or {}
        body = self.bodies["Head to Head"]
        clear_layout(body)
        rows = info.get("rows") or []
        head = QHBoxLayout()
        head.addWidget(_eyebrow("%s against every competitor"
                                % info.get("nickname", ""), self.fonts))
        head.addStretch(1)
        head.addWidget(_label("hardest opponent first", self.fonts.small,
                              T.TEXT_FAINT))
        body.addLayout(head)
        if not rows:
            body.addWidget(_label("They have not played anybody yet.",
                                  self.fonts.body, T.TEXT_FAINT, wrap=True))
        for entry in rows:
            body.addWidget(self._record_row(entry))
        body.addStretch(1)


class StandingsDialog(QDialog):
    """Round matchups, the tournament leaderboard, and this run's own
    win/loss journey -- three views the bridge already snapshots
    (round_begin, scoreboard, elo_rating) with nowhere to render before.

    Same rebuild-only-while-visible discipline as RosterDialog: refresh()
    lands constantly during play, but this dialog is hidden almost all of
    that time, and churning its widget tree at that rate while hidden is
    exactly the pattern that produced RosterDialog's native-crash bug.
    """

    def __init__(self, fonts, parent=None):
        super().__init__(parent)
        self.fonts = fonts
        self._data = {"bracket": None, "leaderboard": None, "journey": None,
                      "champion": False, "rating": None,
                      "rating_change": None, "rating_before": None,
                      "round_results": None}
        self._dirty = True
        self._signature = None        # see refresh()
        self.setWindowTitle("Standings")
        self.setStyleSheet("background: %s;" % T.BG)
        # wide enough for a full matchup row (two names with rating and
        # crown, plus the scoreline) and for all eight tabs -- Matchups, the
        # five rounds, Leaderboard, Your Journey -- without arrows
        self.resize(980, 620)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        self.tabs = _style_tabs(QTabWidget(self), fonts)
        outer.addWidget(self.tabs)

        # Matchups first, then one tab per round as they are played, then the
        # two end-of-run views. The rounds used to be stacked into Matchups
        # together, which by the final round meant scrolling through eighty
        # scorelines to find the one you wanted.
        self._round_bodies = {}
        self.matchups_body = self._add_tab("Matchups")
        self.leaderboard_body = self._add_tab("Leaderboard")
        self.journey_body = self._add_tab("Your Journey")

    def _sync_round_tabs(self, rounds):
        """Add a tab per completed round, in order, before Leaderboard."""
        wanted = sorted(r.get("round") for r in rounds
                        if r.get("round") is not None)
        if list(self._round_bodies) == wanted:
            return
        # rebuild the tab bar so the rounds always sit in the right place
        current = self.tabs.tabText(self.tabs.currentIndex())
        while self.tabs.count():
            self.tabs.removeTab(0)
        self._round_bodies = {}
        self.tabs.addTab(self._matchups_scroll, "Matchups")
        for number in wanted:
            self._round_bodies[number] = self._add_tab("Round %s" % number)
        self.tabs.addTab(self._leaderboard_scroll, "Leaderboard")
        self.tabs.addTab(self._journey_scroll, "Your Journey")
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == current:
                self.tabs.setCurrentIndex(index)
                break

    def select(self, title):
        """Focus a tab by name, so callers don't depend on tab order."""
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return True
        return False

    def _add_tab(self, title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        scroll.setWidget(body)
        self.tabs.addTab(scroll, title)
        # keep the scroller so the tab bar can be rebuilt without losing it
        attr = {"Matchups": "_matchups_scroll",
                "Leaderboard": "_leaderboard_scroll",
                "Your Journey": "_journey_scroll"}.get(title)
        if attr:
            setattr(self, attr, scroll)
        return layout

    def refresh(self, bracket, leaderboard, journey, champion,
               rating=None, rating_change=None, rating_before=None,
               round_results=None):
        """Store the new standings; rebuild only if they are new.

        Same guard, and the same reason, as RosterDialog.refresh -- but this
        window is the more expensive of the two to get wrong. A rebuild here
        re-renders the matchups, a tab per round played, a fifty-eight row
        leaderboard and the journey, and it was doing all of that on every
        battle-state update for as long as the window was open.
        """
        self._data.update(bracket=bracket, leaderboard=leaderboard,
                          journey=journey, champion=bool(champion),
                          rating=rating, rating_change=rating_change,
                          rating_before=rating_before,
                          round_results=round_results)

        # The bridge publishes fresh snapshots, so identity says nothing about
        # whether the contents moved -- it has to be compared by value. These
        # are plain dicts and lists all the way down (see the snap_* functions
        # in GUI/bridge.py), so repr is a faithful comparison, and even at
        # fifty-eight rows it is thousands of times cheaper than the rebuild
        # it is deciding against.
        try:
            signature = repr(self._data)
        except Exception:
            signature = None          # unreprable: fall back to rebuilding
        if signature is not None and signature == self._signature:
            return
        self._signature = signature

        if self.isVisible():
            self._rebuild()
        else:
            self._dirty = True

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_dirty", True):
            self._dirty = False
            self._rebuild()

    def _rebuild(self):
        d = self._data
        rounds = [r for r in (d.get("round_results") or []) if r.get("pairs")]
        self._sync_round_tabs(rounds)
        self._render_matchups(d.get("bracket"))
        for entry in rounds:
            body = self._round_bodies.get(entry.get("round"))
            if body is None:
                continue
            self._clear(body)
            # No caption here. _render_results opens with its own heading and
            # its own one-line explanation, and this was a second copy of that
            # explanation printed *above* the heading -- a loose sentence
            # floating over the tab with nothing to attach it to, on every
            # round tab, from the moment a round's matches were all played.
            self._render_results(entry, body)
            body.addStretch(1)
        if d["leaderboard"]:
            self._render_leaderboard(d["leaderboard"], d["champion"])
        else:
            self._placeholder(self.leaderboard_body,
                              "The tournament hasn't concluded yet.")
        if d["journey"]:
            self._render_journey(d["journey"])
        else:
            self._placeholder(self.journey_body, "No matches played yet.")

    def _clear(self, layout):
        """The shared one. This used to be a private copy that only called
        deleteLater(), leaving the old widgets parented and drawn at their old
        coordinates until the next event-loop turn -- the exact over-draw
        clear_layout was written to prevent, and the same detached-widget
        window problem it now hides against."""
        clear_layout(layout)

    def _placeholder(self, layout, text):
        self._clear(layout)
        layout.addWidget(_label(text, self.fonts.body, T.TEXT_FAINT,
                                wrap=True))
        layout.addStretch(1)

    def _render_matchups(self, bracket):
        """Just this round's pairings; results live in their own tabs."""
        layout = self.matchups_body
        self._clear(layout)
        if bracket:
            self._render_bracket(bracket, layout)
        else:
            layout.addWidget(_label("No round in progress yet.",
                                    self.fonts.body, T.TEXT_FAINT, wrap=True))
        layout.addStretch(1)

    def _render_results(self, last_round, layout):
        """Every scoreline from one round.

        round_end() announces all sixteen, but only as boxed ASCII in the
        log, so the rest of the field's results were effectively invisible --
        and gone entirely once the next round printed over them.
        """
        layout.addWidget(_eyebrow(
            "round %s results" % last_round.get("round", "?"), self.fonts,
            T.PLAYER))
        layout.addWidget(_label(
            "Winner on the left, rating in brackets · scoreline is Pokemon "
            "knocked out", self.fonts.small, T.TEXT_FAINT, wrap=True))
        for pair in last_round["pairs"]:
            if len(pair) < 2:
                continue
            winner, loser = pair[0], pair[1]
            involves_you = winner.get("is_player") or loser.get("is_player")
            row = RoundedPanel(
                None, bg=T.mix(T.PANEL, T.PLAYER, 0.10) if involves_you
                else T.PANEL,
                border=T.PLAYER if involves_you else T.LINE_SOFT,
                radius=T.RADIUS_SM)
            line = QHBoxLayout(row)
            line.setContentsMargins(12, 7, 12, 7)
            line.setSpacing(8)

            # an upset gets its own badge rather than "!!" tacked onto the
            # name -- two exclamation marks after a nickname are easy to read
            # straight past, which defeats the point of flagging it
            # An upset is worth flagging when it is someone else's, or when
            # it is yours. It is not worth rubbing in when the upset *is* you
            # being beaten by a lower-tier competitor.
            if winner.get("upset") and not loser.get("is_player"):
                line.addWidget(Chip("UPSET", T.ACCENT, self.fonts))
            else:
                spacer = _label("", self.fonts.small, T.TEXT_FAINT)
                spacer.setFixedWidth(58)
                line.addWidget(spacer)
            won = _label(_rated(winner), self.fonts.small_bold,
                         T.PLAYER if winner.get("is_player") else T.TEXT)
            won.setFixedWidth(190)
            line.addWidget(won)
            score = _label("%s  –  %s" % (
                "?" if winner.get("score") is None else winner["score"],
                "?" if loser.get("score") is None else loser["score"]),
                self.fonts.body_bold, T.ACCENT)
            score.setFixedWidth(78)
            line.addWidget(score)
            lost = _label(_rated(loser), self.fonts.small,
                          T.OPPONENT if loser.get("is_player") else T.TEXT_DIM)
            lost.setFixedWidth(200)
            line.addWidget(lost)
            line.addStretch(1)
            layout.addWidget(row)

    def _render_bracket(self, bracket, layout):
        layout.addWidget(_eyebrow(
            "round %s matchups" % bracket.get("round", "?"), self.fonts))
        layout.addWidget(_label(
            "Rating in brackets · W = rounds won so far · pts = tie-break "
            "score", self.fonts.small, T.TEXT_FAINT, wrap=True))
        for pair in bracket.get("pairs", []):
            row = RoundedPanel(None, bg=T.PANEL, border=T.LINE_SOFT,
                               radius=T.RADIUS_MD)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 10, 14, 10)
            row_layout.setSpacing(10)
            for i, comp in enumerate(pair):
                if i > 0:
                    row_layout.addWidget(_label("vs", self.fonts.small,
                                                T.TEXT_FAINT))
                accent = T.PLAYER if comp.get("is_player") else T.TEXT
                crown = (" |%d|" % comp["championship"]
                        if comp.get("championship") else "")
                cell = QVBoxLayout()
                cell.setSpacing(1)
                cell.addWidget(_label(
                    "%s [%d]%s" % (comp["nickname"], comp["strength"], crown),
                    self.fonts.body_bold, accent))
                cell.addWidget(_label(
                    "%dW  ·  %+d pts" % (comp.get("wins", 0),
                                         comp.get("score", 0)),
                    self.fonts.small, T.TEXT_DIM))
                row_layout.addLayout(cell)
            row_layout.addStretch(1)
            layout.addWidget(row)

    def _render_leaderboard(self, rows, champion):
        layout = self.leaderboard_body
        self._clear(layout)
        if champion:
            layout.addWidget(_eyebrow("world champion!", self.fonts,
                                      T.ACCENT))
        # Ranked by Points, then Opponent Score, then Kill Score -- the
        # columns are laid out in that same order so the ordering is legible
        # rather than something you have to take on trust.
        columns = (("#", 30, "rank"), ("Name", 200, "nickname"),
                  ("Rating", 66, "strength"), ("Points", 60, "stage"),
                  ("Opp. Score", 88, "opponent_score"),
                  ("Kill Score", 84, "score"))
        header = QHBoxLayout()
        for title, width, _ in columns:
            label = _label(title, self.fonts.small_bold, T.TEXT_FAINT)
            label.setFixedWidth(width)
            header.addWidget(label)
        layout.addLayout(header)
        for row in rows:
            line = QHBoxLayout()
            accent = T.PLAYER if row.get("is_player") else T.TEXT
            font = (self.fonts.small_bold if row.get("is_player")
                   else self.fonts.small)
            for _, width, key in columns:
                label = _label(str(row.get(key, "")), font, accent)
                label.setFixedWidth(width)
                line.addWidget(label)
            layout.addLayout(line)
        layout.addStretch(1)

    def _render_journey(self, journey):
        layout = self.journey_body
        self._clear(layout)

        # What the run actually cost or earned you. elo_rating() applies this
        # and printed it into the log, where it scrolled past.
        change = self._data.get("rating_change")
        rating = self._data.get("rating")
        if change is not None:
            colour = T.PLAYER if change > 0 else (
                T.OPPONENT if change < 0 else T.TEXT_DIM)
            layout.addWidget(_eyebrow("rating this run", self.fonts,
                                      T.TEXT_FAINT))
            row = QHBoxLayout()
            row.addWidget(_label("%+d" % change, self.fonts.num_big, colour))
            detail = "now %d" % rating if rating is not None else ""
            if self._data.get("rating_before") is not None:
                detail = "%d → %d" % (self._data["rating_before"], rating)
            row.addWidget(_label(detail, self.fonts.small, T.TEXT_DIM))
            row.addStretch(1)
            layout.addLayout(row)
            layout.addWidget(_eyebrow("matches", self.fonts, T.TEXT_FAINT))
        elif rating is not None:
            layout.addWidget(_label("Rating: %d" % rating,
                                    self.fonts.body_bold, T.TEXT))

        for entry in journey:
            row = QHBoxLayout()
            won = entry.get("won")
            verdict = _label("WIN" if won else "LOSS", self.fonts.small_bold,
                             T.PLAYER if won else T.OPPONENT)
            verdict.setFixedWidth(46)
            row.addWidget(verdict)
            name = _label("%s [%d]" % (entry["nickname"], entry["strength"]),
                          self.fonts.small, T.TEXT_DIM)
            name.setFixedWidth(210)
            row.addWidget(name)
            # what that particular match was worth
            change = entry.get("rating_change")
            if change is not None:
                colour = T.PLAYER if change > 0 else (
                    T.OPPONENT if change < 0 else T.TEXT_DIM)
                row.addWidget(_label("%+d" % change, self.fonts.small_bold,
                                     colour))
            row.addStretch(1)
            layout.addLayout(row)
        layout.addStretch(1)


class StoryDialog(QDialog):
    """A page-by-page reader for the illustrated pages in Assets/generated.

    Two readers rather than one. The background and the tutorial are
    different things -- one is why you are here, the other is how to play --
    and binding them into a single five-page sequence meant a returning
    player who wanted a rules reminder had to page past the lore to reach it.
    They are separate buttons in the header now, and this class is the reader
    both of them use. Pass `pages`.

    Each page is a finished illustration with its own text set into it, so
    this is a reader and not a text panel: no scrolling, because a page is
    meant to be taken in whole. The captured terminal text is kept as a
    fallback for a page whose artwork is missing.

    `on_finish` makes it a *guided* reader, which is how a new player meets
    it: reaching the end (or closing) calls it exactly once, and the flow
    behind it moves on to whatever comes next. Without it the reader is just
    reference material you can open and shut at will.
    """

    #: filename in Assets/generated, page title, and which captured lore to
    #: fall back on -- in the order they are meant to be read
    BACKGROUND_PAGES = (
        ("BKGD_1.jpg", "Background — The Region", "backstory"),
        ("BKGD_2.jpg", "Background — The Championship", "backstory"),
        ("BKGD_3.jpg", "Background — The Prize", "backstory"),
        ("BKGD_4.jpg", "Background — The Favourites", "backstory"),
        ("BKGD_5.jpg", "Background — The Elite Eight", "backstory"),
        ("BKGD_6.jpg", "Background — Your Wildcard", "backstory"),
    )
    TUTORIAL_PAGES = (
        ("TUT_1.jpg", "Tutorial #1 — Receiving Pokemon", "tutorial"),
        ("TUT_2.jpg", "Tutorial #2 — Before Battle", "tutorial"),
        ("TUT_3.jpg", "Tutorial #3 — In Battle", "tutorial"),
        ("TUT_4.jpg", "Tutorial #4 — End Game", "tutorial"),
        ("TUT_5.jpg", "Tutorial #5 — Your Career", "tutorial"),
    )
    #: kept so a caller that passes nothing still gets something to read
    PAGES = BACKGROUND_PAGES

    def __init__(self, fonts, lore, project_root=".", parent=None,
                 pages=None, title="Story & Guide", on_finish=None):
        super().__init__(parent)
        self.fonts, self.lore = fonts, lore or {}
        self.root_dir = project_root
        self.PAGES = tuple(pages) if pages else self.BACKGROUND_PAGES
        self.on_finish = on_finish
        self._finished = False
        self.index = 0
        self.setWindowTitle(title)
        self.setStyleSheet("background: %s;" % T.BG)
        # Borderless, filling the screen. Each page is a finished illustration
        # with its own text set into it at 1376x768 -- shown in a modest
        # window that text is too small to read, which defeats the point of
        # having art instead of paragraphs. Escape and the Close button both
        # get you out, since there is no title bar.
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        else:
            self.resize(1280, 800)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        self.heading = _label("", fonts.title, T.TEXT)
        outer.addWidget(self.heading)

        # Same self-fitting label the opponent artwork uses: a QLabel holding
        # a pixmap otherwise reports that pixmap as the size it wants, and
        # ends up sizing the window instead of being sized by it.
        self.page = _FittedArt(None)
        outer.addWidget(self.page, 1)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.back = ActionButton("Back", fonts, sub="previous page",
                                 accent=T.TEXT_DIM,
                                 on_click=lambda: self.step(-1))
        self.forward = ActionButton("Next", fonts, sub="next page",
                                    accent=T.ACCENT, emphasis=True,
                                    on_click=lambda: self.step(1))
        row.addWidget(self.back)
        self.counter = _label("", fonts.small_bold, T.TEXT_FAINT)
        row.addWidget(self.counter)
        row.addStretch(1)
        row.addWidget(ActionButton("Close", fonts, sub="or press Escape",
                                   accent=T.TEXT_DIM, on_click=self.finish))
        row.addWidget(self.forward)
        outer.addLayout(row)

        self._show_page()

    # -- navigation --------------------------------------------------------
    def step(self, delta):
        """Page. Past the last page is 'done', when there is somewhere to go.

        In guided mode Next on the final page reads Continue and finishes,
        so a new player never has to find the Close button to get on with
        the game -- they just keep pressing the same button.
        """
        if delta > 0 and self.index >= len(self.PAGES) - 1:
            if self.on_finish is not None:
                self.finish()
            return
        self.index = max(0, min(len(self.PAGES) - 1, self.index + delta))
        self._show_page()

    def present(self):
        """Show it, including for the second and later time.

        `_finished` is a latch so a reader cannot report twice on the way
        out. Reopening the same instance has to clear it, or `finish()`
        short-circuits and **the Close button does nothing** -- which is
        exactly what happened to the Background reader on the top bar from
        its second open onwards, and left a window nothing could shut.
        """
        self._finished = False
        self.show()
        self.raise_()
        self.activateWindow()

    def finish(self):
        """Close, and let whatever is driving the flow know. Once only.

        Every way out lands here -- the button, Escape, the window manager --
        because the engine is blocked on a keypress behind this window and a
        reader that closed without saying so would strand it. Same trap as
        the swap window (see CLAUDE.md).
        """
        if self._finished:
            return
        self._finished = True
        callback, self.on_finish = self.on_finish, None
        self.close()
        if callback is not None:
            callback()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.finish()

    def reject(self):
        # Escape routes here without ever raising closeEvent -- see the traps
        # in CLAUDE.md.
        super().reject()
        self.finish()

    def keyPressEvent(self, event):
        """Arrow keys and page keys too -- it is a reader."""
        if event.key() == Qt.Key_Escape:
            self.finish()
        elif event.key() in (Qt.Key_Left, Qt.Key_PageUp, Qt.Key_Backspace):
            self.step(-1)
        elif event.key() in (Qt.Key_Right, Qt.Key_PageDown, Qt.Key_Space):
            self.step(1)
        else:
            super().keyPressEvent(event)

    def _show_page(self):
        filename, title, fallback = self.PAGES[self.index]
        self.heading.setText(title)
        self.counter.setText("%d / %d" % (self.index + 1, len(self.PAGES)))
        # Disabled rather than hidden at the ends, so the row does not jump
        # around as you page through. In guided mode the last page's Next
        # becomes Continue instead of going dead, because there *is*
        # somewhere further to go.
        self.back.set_enabled(self.index > 0)
        last = self.index >= len(self.PAGES) - 1
        if last and self.on_finish is not None:
            self.forward.set_title("Continue")
            self.forward.set_enabled(True)
        else:
            self.forward.set_title("Next")
            self.forward.set_enabled(not last)

        path = os.path.join(self.root_dir, "Assets", "generated", filename)
        picture = QPixmap(path) if os.path.exists(path) else None
        if picture is not None and not picture.isNull():
            self.page.set_picture(picture)
            return
        # no artwork: fall back to whatever bridge.py captured
        self.page.set_picture(None)
        text = (self.lore.get(fallback) or "").strip()
        self.page.setText(text or "This page could not be read from the "
                                  "game files.")
        self.page.setFont(self.fonts.small)
        self.page.setStyleSheet("color: %s; background: transparent;"
                                % T.TEXT_DIM)
        self.page.setAlignment(Qt.AlignTop | Qt.AlignLeft)

    # The page looks after its own scaling -- see _FittedArt.


class AppearanceDialog(QDialog):
    """Who you are: one screen, five portraits, and a Male/Female switch.

    The engine asks this as two numbered questions (`choose_appearance` in
    start_interface.py) because a terminal can only ask one thing at a time.
    The window does not: it opens straight onto the five male portraits with
    both gender buttons underneath, and switching gender swaps the pictures
    where they stand.

    **Nothing moves when you switch.** The five frames are built once at a
    fixed size and only their pixmaps change, so the row cannot re-flow, and
    the gender buttons are built once and only re-styled -- a rebuilt layout
    would jump, and the two arrangements are identical anyway. That is the
    whole reason `set_portraits` swaps pictures instead of `clear_layout` and
    a fresh row.

    Underneath, switching gender answers the engine's portrait question with
    its go-back sentinel and re-answers the gender question with the new
    choice; the loop is invisible because this window never closes during it.
    Only clicking a portrait ends the screen.
    """

    #: portraits are 848x1264, so a hair under 2:3
    ASPECT = 1264.0 / 848.0
    #: room for the heading and the gender row. The portraits carry no
    #: caption -- a picture you are choosing between five of does not need
    #: to be told it is "Male 3", and the filename is not part of the game.
    CHROME = 240

    def __init__(self, fonts, project_root=".", parent=None):
        super().__init__(parent)
        self.fonts = fonts
        self.root_dir = project_root
        self._answer = None
        self._on_gender = None
        self._locked = False        # set once a portrait is taken
        self._slots = []            # the five (frame, art, caption) columns
        self._gender_buttons = {}
        self._active = 0            # which gender's portraits are showing
        self.setWindowTitle("Your Trainer")
        self.setStyleSheet("background: %s;" % T.BG)
        # Frameless and filling the screen, like the story readers: these are
        # large illustrations and a modest window wastes them.
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        else:
            self.resize(1280, 800)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.SIDE_MARGIN, 20,
                                 self.SIDE_MARGIN, 16)
        outer.setSpacing(10)

        self.heading = _label("Choose your appearance", fonts.title, T.TEXT,
                              align=Qt.AlignCenter)
        outer.addWidget(self.heading)
        self.subheading = _label(
            "Click a portrait to choose it. This is stamped on the save and "
            "shown in your career history.", fonts.small, T.TEXT_DIM,
            align=Qt.AlignCenter)
        outer.addWidget(self.subheading)

        self.body = QHBoxLayout()
        self.body.setSpacing(self.COLUMN_GAP)
        self.body.setContentsMargins(0, 0, 0, 0)
        holder = QWidget(self)
        holder.setLayout(self.body)
        outer.addWidget(holder, 1)

        self.footer = QHBoxLayout()
        self.footer.setSpacing(12)
        foot = QWidget(self)
        foot.setLayout(self.footer)
        outer.addWidget(foot)

    # -- layout ------------------------------------------------------------
    #: outer margins, the gap between columns, and what a column's own layout
    #: adds around its picture. That last one is the easy one to forget: a
    #: QVBoxLayout defaults to a 9px margin on every side, so five columns
    #: quietly claimed 90px the width calculation knew nothing about -- and
    #: the fifth portrait ran off the edge. The column layouts are flattened
    #: to zero below, so this only has to cover the two real gaps.
    SIDE_MARGIN = 24
    COLUMN_GAP = 16
    #: slack left over after the five boxes, so the row has visible air at
    #: both ends instead of sitting flush against them. Without it the
    #: arithmetic comes out exact and a single pixel of rounding clips the
    #: last portrait -- which is how this was noticed.
    ROW_SLACK = 48

    def _sizes(self, count):
        """One portrait's box: as tall as the window allows, then as wide."""
        count = max(1, count)
        tall = max(240, self.height() - self.CHROME)
        wide = max(120, int(tall / self.ASPECT))
        room = (self.width() - 2 * self.SIDE_MARGIN - self.ROW_SLACK
                - self.COLUMN_GAP * (count - 1)) // count
        if wide > room:
            wide, tall = max(80, room), int(max(80, room) * self.ASPECT)
        return wide, tall

    def _apply_sizes(self):
        """Re-fit the row to the window it is actually in.

        The boxes are a fixed size so the row cannot re-flow when the gender
        changes -- but "fixed" has to mean fixed to the *current* window.
        They were measured once at build time, before the dialog had been
        shown and while it still had its constructor geometry, so on a
        display bigger than that guess every portrait came out too small and
        the row sat off-centre. Measuring again on show and on resize costs
        nothing and cannot shift anything, because a gender switch changes
        neither.
        """
        if not self._slots:
            return
        wide, tall = self._sizes(len(self._slots))
        for art in self._slots:
            frame = art.parentWidget()
            if frame is not None:
                frame.setFixedSize(wide, tall)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_sizes()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_sizes()

    def _build_slots(self, count):
        """The five columns, once. Fixed size, so nothing can re-flow."""
        clear_layout(self.body)
        self._slots = []
        wide, tall = self._sizes(count)
        self.body.addStretch(1)
        for index in range(count):
            column = QVBoxLayout()
            column.setSpacing(6)
            column.setContentsMargins(0, 0, 0, 0)
            art = _ClickableArt(None)
            art.clicked.connect(lambda i=index: self._take(i))
            # _FittedArt is QSizePolicy.Ignored, so a layout reserves no space
            # for it and it draws over its neighbours. It has to sit in a
            # fixed-size container -- see the traps in CLAUDE.md. That
            # container is also what keeps the row from moving when the
            # pictures are swapped.
            frame = QWidget(self)
            frame.setFixedSize(wide, tall)
            inner = QVBoxLayout(frame)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.addWidget(art)
            column.addWidget(frame, 0, Qt.AlignHCenter)
            wrap = QWidget(self)
            wrap.setLayout(column)
            self.body.addWidget(wrap, 0, Qt.AlignVCenter)
            self._slots.append(art)
        self.body.addStretch(1)

    def _build_genders(self, genders, active):
        """The two buttons, once. Re-styled on a switch, never rebuilt."""
        clear_layout(self.footer)
        self._gender_buttons = {}
        self.footer.addStretch(1)
        for index, name in enumerate(genders):
            button = ActionButton(
                name, self.fonts,
                accent=T.ACCENT if index == active else T.TEXT_DIM,
                emphasis=(index == active),
                on_click=lambda i=index: self._switch(i))
            button.setMinimumWidth(190)
            button.setMinimumHeight(54)
            self.footer.addWidget(button)
            self._gender_buttons[index] = button
        self.footer.addStretch(1)

    def _mark_active(self, active):
        """Which gender is showing, without rebuilding either button."""
        for index, button in self._gender_buttons.items():
            button.set_accent(T.ACCENT if index == active else T.TEXT_DIM,
                              emphasis=(index == active))

    # -- the question ------------------------------------------------------
    def ask_portrait(self, genders, active, keys, answer, on_gender):
        """Show `keys` as pictures. Called again on every gender switch.

        The second and later calls only swap pixmaps and captions -- see the
        class docstring. `on_gender(index)` is how the window asks for the
        other set; `answer(index)` is a portrait being taken.
        """
        self._answer, self._on_gender = answer, on_gender
        self._active = active
        if len(self._slots) != len(keys):
            self._build_slots(len(keys))
        if set(self._gender_buttons) != set(range(len(genders))):
            self._build_genders(genders, active)
        else:
            self._mark_active(active)
        self.set_portraits(keys)
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def set_portraits(self, keys):
        """Swap the five pictures. No captions: the portrait is the choice."""
        for art, key in zip(self._slots, keys):
            path = os.path.join(self.root_dir, "Assets", "Player",
                                "%s.jpg" % key)
            picture = QPixmap(path) if os.path.exists(path) else None
            if picture is not None and not picture.isNull():
                art.set_picture(picture)
                art.setToolTip("Choose this trainer")
            else:
                # the only case a name is shown, and only because there is
                # nothing else to show
                art.set_picture(None)
                art.setText("(artwork missing)")
                art.setToolTip("Choose this trainer")
                art.setAlignment(Qt.AlignCenter)

    # -- plumbing ----------------------------------------------------------
    def _switch(self, index):
        """A gender button. The one already showing is not a change.

        Guarded here rather than only in the caller because this window is
        what knows which set is on screen -- and reporting a press of the
        active button would send the engine round its go-back loop to arrive
        at exactly the same five portraits.
        """
        handler = self._on_gender
        if handler is None or self._locked or index == self._active:
            return
        handler(index)

    def _take(self, index):
        """A portrait was clicked. That ends it."""
        if self._locked:
            return
        self._locked = True
        answer, self._answer = self._answer, None
        self.close()
        if answer is not None:
            answer(str(index))

    def keyPressEvent(self, event):
        # Escape does *not* dismiss this. The engine loops on the question
        # until it gets a valid answer, so walking away would leave the
        # player looking at an empty action bar with the worker blocked in
        # input() -- the swap-window trap in CLAUDE.md. There is no "no
        # thanks" answer to give it, so the only way past is to choose.
        if event.key() == Qt.Key_Escape:
            return
        super().keyPressEvent(event)

    # No closeEvent override, and that is deliberate. The first cut had one
    # that called event.ignore() until a portrait was taken, on the same
    # reasoning as Escape above -- and **a dialog that refuses to close
    # blocks QApplication.quit() outright**: app.exec() never returns and the
    # process hangs until something kills it. It cost a 30-minute harness
    # timeout to find, because the run itself finished normally and wrote its
    # report first; only the shutdown hung.
    #
    # Nothing is lost by accepting. The window is frameless, so it has no
    # close button, and Escape is swallowed above -- a player has no way to
    # close it. The only things that can are the window manager and
    # application shutdown, and in both cases refusing is worse than
    # allowing.


class CreditsDialog(QDialog):
    """End of run: the closing note plus Documentation/credits.md.

    The engine does print the credits, but only into the scrolling log
    where they arrive as an undifferentiated wall of text mixed in with
    battle output -- and only in the one case where the player actually
    wins the whole thing. This shows them at the end of any completed run.
    """

    def __init__(self, fonts, project_root, champion=False, titles=0,
                parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pokemon Champion — Credits")
        self.setStyleSheet("background: %s;" % T.BG)
        self.resize(600, 560)

        panel = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
        outer = QVBoxLayout(self)
        outer.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(8)

        if champion:
            layout.addWidget(_eyebrow("world champion", fonts, T.ACCENT))
            layout.addWidget(_label("You won the Pokemon World Championship!",
                                    fonts.title, T.TEXT, wrap=True))
            if titles:
                layout.addWidget(_label(
                    "%d World Champion title(s) in your career." % titles,
                    fonts.body, T.TEXT_DIM, wrap=True))
        else:
            # No "Your run has ended." -- these open from a button now, which
            # may well be mid-run, and it was stating the obvious even when
            # they opened themselves.
            layout.addWidget(_eyebrow("credits", fonts))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(_label(self._credits_text(project_root),
                                    fonts.small, T.TEXT_DIM, wrap=True))
        body_layout.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

    def _credits_text(self, project_root):
        path = os.path.join(project_root, "Documentation", "credits.md")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read().rstrip()
        except OSError:
            return "Credits file could not be read."


class ArtLightbox(QDialog):
    """One picture, as big as the screen will allow, on a dimmed backdrop.

    The competitor portraits carry their write-up, quote and ace Pokemon as
    text baked into the illustration, so "big enough to read" is a real
    requirement and the Pokedex's column can only ever be part of the screen.
    Clicking the artwork opens it here instead: no panel, no chrome, just the
    image centred on a translucent black ground. A click anywhere, or Escape,
    puts it away.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        self.art = _FittedArt(QPixmap())
        layout.addWidget(self.art)

    def show_picture(self, path):
        picture = QPixmap(path)
        if picture.isNull():
            return False
        self.art.set_picture(picture)
        self.show()
        self.raise_()
        self.activateWindow()
        return True

    def paintEvent(self, event):
        # the dimmed ground the picture sits on; the window itself is
        # translucent, so this is the only thing painting a background
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 214))

    def mousePressEvent(self, event):
        self.close()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Space, Qt.Key_Return):
            return self.close()
        super().keyPressEvent(event)
