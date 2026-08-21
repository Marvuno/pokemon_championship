"""
The Pokedex: one search box over three sections.

Pokemon, moves and competitors, all filtered by the same line of text (see
GUI/codex.py for the query language). Deliberately not six dropdowns -- typing
`fire spd>110` is faster than setting three combo boxes, and it scales to
questions nobody thought to add a control for.

Two things about how it is built:

  * every row is created once and shown or hidden by the filter. 239 Pokemon
    is nothing to lay out, but rebuilding a widget tree on each keystroke both
    feels slow and is the churn pattern that has produced native crashes in
    this codebase before.
  * sprites and portraits load only for the selected entry. 239 simultaneous
    QMovies would be miserable, and nobody is looking at more than one.

It needs about 1000x620 to lay out: the selection rail, the artwork and a
readable column beside it. The competitor portraits are sized from the display
so that stays true on a 1366x768 laptop as much as on a 1440p monitor -- see
portrait_box().
"""

import os

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

from GUI import codex, theme as T
from GUI_qt.panels import (ArtLightbox, _FittedArt, _eyebrow,
                           _style_tabs)
from GUI_qt.sprites import DIR_PLAYER, show_sprite
from GUI_qt.widgets import (ActionButton, Chip, ElidedLabel, RoundedPanel,
                            StatBar, TypeBlocks, clear_layout,
                            label as _label)

SECTIONS = ("Pokemon", "Moves", "Abilities", "Opponents")
#: fixed boxes for the artwork. show_sprite fits the longest edge and never
#: enlarges, and _FittedArt scales to whatever it is given, so a fixed box is
#: both a guarantee that the picture fits and the thing that stops the panel
#: beside it reflowing every time the selection changes.
SPRITE_BOX = 210
#: the competitor portraits are 1024px square illustrations with their name,
#: write-up, quote and ace Pokemon set into them, so they are worth real room
#: -- but sized from the screen rather than hard-coded, or a small display
#: would get a box bigger than the window.
PORTRAIT_MAX = 760
PORTRAIT_MIN = 300


#: the rail, the narrowest the text column beside the portrait may get, and
#: how wide the window is allowed to get on a large monitor
RAIL_WIDTH = 330
TEXT_MIN = 260
WINDOW_MAX_W = 1480


def portrait_box(screen_height=None, screen_width=None):
    """As big as the screen can take, clamped by *both* dimensions.

    Height alone was not enough: a 576px box plus the rail plus a readable
    text column gave the window a minimum size of 1354x828, which is wider
    than the 1280px display it was meant for -- the window opened bigger than
    the screen.
    """
    if not screen_height or not screen_width:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        room = screen.availableGeometry() if screen else None
        screen_height = screen_height or (room.height() if room else 800)
        screen_width = screen_width or (room.width() if room else 1280)
    # The window is at most screen - 40 in either direction. Vertically it
    # also carries the search row, the hint line, the tab bar and the close
    # row; horizontally the rail and the text column beside the picture. Both
    # have to come off, or the window's own minimum size ends up larger than
    # the display -- which put its Close button off the right-hand edge.
    # search row, tab bar, margins -- no hint line and no close row any more
    CHROME_H, CHROME_W = 150, 60
    by_height = min(int(screen_height * 0.72),
                    screen_height - 40 - CHROME_H)
    by_width = (min(WINDOW_MAX_W, screen_width - 40) - RAIL_WIDTH - TEXT_MIN
                - CHROME_W)
    return max(PORTRAIT_MIN, min(PORTRAIT_MAX, by_height, by_width))


# Deliberately *not* a module-level constant. portrait_box() reads the screen,
# and at import time there may be no QApplication yet -- so a constant computed
# here silently used the fallback dimensions instead of the real display. The
# dialog works it out when it is built and hands it to each section.
#: base_stats order
STAT_NAMES = ("HP", "ATK", "DEF", "SPA", "SPDEF", "SPE")
EXAMPLES = ("fire flying · tier:ultra · spd>130 · move:earthquake · "
            "ability:levitate · total>550 · custom:yes · -tier:boss")


def _wrapped(text, font, colour, minimum=170):
    """A word-wrapped label that is allowed to be narrow.

    QLabel's minimum width for wrapped text is generous -- for a long
    comma-separated list ("learned by" runs to forty names) it came out at over
    1200px, which became the whole window's minimum width and made the Pokedex
    open wider than the display. Wrapped text here always sits inside a scroll
    area, so it can shrink as far as it likes.
    """
    widget = _label(text, font, colour, wrap=True)
    widget.setMinimumWidth(minimum)
    widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    return widget


class _ClickableFrame(QWidget):
    """The portrait's box. Clicking it opens the full-size view."""

    def __init__(self, path, section, parent=None):
        super().__init__(parent)
        self.path, self.section = path, section
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to see it full size")

    def mousePressEvent(self, event):
        self.section.open_lightbox(self.path)


class _Row(RoundedPanel):
    """A clickable line in the results list."""

    clicked = Signal(int)

    def __init__(self, index, entry, kind, fonts, parent=None):
        super().__init__(parent, bg=T.PANEL, border=T.LINE_SOFT,
                         radius=T.RADIUS_SM)
        self.index = index
        self.setCursor(Qt.PointingHandCursor)
        line = QHBoxLayout(self)
        line.setContentsMargins(10, 4, 10, 4)
        line.setSpacing(6)
        if kind == "moves":
            line.addWidget(ElidedLabel(entry["name"], fonts.small_bold,
                                       T.TEXT), 1)
            line.addWidget(TypeBlocks([entry["type"]]), 0)
        elif kind == "abilities":
            line.addWidget(ElidedLabel(entry["name"], fonts.small_bold,
                                       T.TEXT), 1)
            # how many Pokemon have it, so the list reads as "common or rare"
            # at a glance
            line.addWidget(_label(str(len(entry.get("pokemon") or [])),
                                  fonts.small, T.CYAN), 0)
        elif kind == "opponents":
            line.addWidget(ElidedLabel(entry["nickname"], fonts.small_bold,
                                       T.TEXT), 1)
            line.addWidget(_label(str(entry["rating"]), fonts.small, T.CYAN),
                           0)
        else:
            # typing as colour blocks, not words: two chips reading "STEEL
            # DRAGON" took most of the row and left the longer names with
            # nowhere to go. Two swatches say the same thing in a fifth of the
            # width, and three stack just as well.
            # eliding, so one very long name cannot push the type blocks out
            # past the rail's edge
            line.addWidget(ElidedLabel(entry["name"], fonts.small_bold,
                                       T.TEXT), 1)
            line.addWidget(TypeBlocks(entry["types"]), 0)
        self.setToolTip(entry.get("name") or entry.get("nickname", ""))

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)

    def mark(self, on):
        self.set_style(bg=T.mix(T.PANEL, T.ACCENT, 0.22) if on else T.PANEL,
                       border=T.ACCENT if on else T.LINE_SOFT,
                       border_width=2 if on else 1)


class _Section(QWidget):
    """One tab: a filtered list on the left, the selected entry on the right."""

    def __init__(self, kind, data, fonts, project_root, parent=None,
                 portrait=None):
        super().__init__(parent)
        self.kind, self.fonts = kind, fonts
        self.root_dir = project_root
        self.portrait = portrait or portrait_box()
        self.entries = list(data.get(kind) or [])
        self.percentiles = (data.get("percentiles") or {})
        self.query = ""
        self.selected = None
        self.rows = []
        self._lightbox = None       # built on first use; see open_lightbox

        body = QHBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        rail = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
        # Wide enough for the longest name in the game beside its type
        # blocks -- "Aegislash (Shield Forme)" and "Krusadian Salamence" were
        # being squeezed until the words ran out of room.
        rail.setFixedWidth(RAIL_WIDTH)
        rail_box = QVBoxLayout(rail)
        rail_box.setContentsMargins(10, 10, 10, 10)
        rail_box.setSpacing(6)
        self.count = _eyebrow("%d results" % len(self.entries), fonts,
                              T.TEXT_FAINT)
        rail_box.addWidget(self.count)
        self.rail_scroll = QScrollArea()
        self.rail_scroll.setWidgetResizable(True)
        self.rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rail_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        self.rail_list = QVBoxLayout(holder)
        self.rail_list.setContentsMargins(0, 0, 0, 0)
        self.rail_list.setSpacing(4)
        for index, entry in enumerate(self.entries):
            row = _Row(index, entry, kind, fonts)
            row.clicked.connect(self.select)
            self.rows.append(row)
            self.rail_list.addWidget(row)
        self.rail_list.addStretch(1)
        self.rail_scroll.setWidget(holder)
        rail_box.addWidget(self.rail_scroll, 1)
        body.addWidget(rail)

        pane = RoundedPanel(self, bg=T.PANEL, radius=T.RADIUS_LG)
        pane_box = QVBoxLayout(pane)
        pane_box.setContentsMargins(14, 10, 14, 10)
        pane_box.setSpacing(6)
        self.detail = QVBoxLayout()
        self.detail.setSpacing(8)
        pane_box.addLayout(self.detail, 1)
        body.addWidget(pane, 1)

        if self.entries:
            self.select(0)

    # -- filtering ---------------------------------------------------------
    def apply(self, query):
        self.query = query
        matches = codex.search(query, self.entries, self.kind)
        keep = {id(entry) for entry in matches}
        first = None
        for index, entry in enumerate(self.entries):
            shown = id(entry) in keep
            self.rows[index].setVisible(shown)
            if shown and first is None:
                first = index
        self.count.setText("%d result%s" % (len(matches),
                                            "" if len(matches) == 1 else "s"))
        if first is not None and (self.selected is None
                                  or not self.rows[self.selected].isVisible()):
            self.select(first)
        elif first is None:
            self.show_nothing()

    def show_nothing(self):
        self.selected = None
        clear_layout(self.detail)
        self.detail.addWidget(_label("Nothing matches that.", self.fonts.body,
                                     T.TEXT_FAINT))
        self.detail.addWidget(_wrapped("Try: %s" % EXAMPLES,
                                       self.fonts.small, T.TEXT_DIM))
        self.detail.addStretch(1)

    # -- the detail pane ---------------------------------------------------
    def select(self, index):
        if not (0 <= index < len(self.entries)):
            return
        for position, row in enumerate(self.rows):
            row.mark(position == index)
        self.selected = index
        clear_layout(self.detail)
        entry = self.entries[index]
        if self.kind == "moves":
            self._show_move(entry)
        elif self.kind == "abilities":
            self._show_ability(entry)
        elif self.kind == "opponents":
            self._show_opponent(entry)
        else:
            self._show_pokemon(entry)

    def open_lightbox(self, path):
        """Show one picture full screen, dimmed background, click to dismiss."""
        if self._lightbox is None:
            self._lightbox = ArtLightbox(self.window())
        self._lightbox.show_picture(path)

    def _chips(self, entry):
        row = QHBoxLayout()
        row.setSpacing(5)
        for type_name in entry.get("types") or []:
            row.addWidget(Chip(type_name, T.type_color(type_name), self.fonts))
        if entry.get("tier"):
            row.addWidget(Chip(entry["tier"], T.TEXT_FAINT, self.fonts))
        if entry.get("custom"):
            row.addWidget(Chip("custom", T.CYAN, self.fonts))
        row.addStretch(1)
        return row

    def _show_pokemon(self, entry):
        head = QHBoxLayout()
        head.addWidget(ElidedLabel(entry["name"], self.fonts.hero, T.TEXT),
                       1)
        head.addWidget(_label("total %d" % entry["total"],
                              self.fonts.body_bold, T.TEXT_DIM))
        self.detail.addLayout(head)
        self.detail.addLayout(self._chips(entry))

        split = QHBoxLayout()
        split.setSpacing(14)
        # A *fixed* box, not a minimum. Sprites range from 196x30 (Stunfisk)
        # to tall and narrow, and letting the label take its own size meant the
        # stats beside it jumped left and right as you clicked down the list.
        # show_sprite fits the longest edge into SPRITE_BOX and never enlarges,
        # so whatever goes in here fits inside it.
        # a fixed box with the sprite centred in it. show_sprite gives the
        # label its own exact size, so the box is what keeps the panel beside
        # it from moving as the selection changes.
        box = QWidget()
        box.setFixedSize(SPRITE_BOX, SPRITE_BOX)
        box.setStyleSheet("background: transparent;")
        holder = QVBoxLayout(box)
        holder.setContentsMargins(0, 0, 0, 0)
        sprite = QLabel()
        sprite.setAlignment(Qt.AlignCenter)
        # loaded here and only here -- one movie at a time, not 239
        show_sprite(sprite, entry["sprite"], DIR_PLAYER, self.root_dir,
                    target=SPRITE_BOX)
        holder.addWidget(sprite, 0, Qt.AlignCenter)
        split.addWidget(box, 0, Qt.AlignTop)

        column = QVBoxLayout()
        column.setSpacing(4)
        column.addWidget(_eyebrow("base stats", self.fonts, T.TEXT_FAINT))
        columns = self.percentiles.get("stats") or []
        for position, name in enumerate(STAT_NAMES):
            stats = entry.get("stats") or []
            value = stats[position] if len(stats) > position else 0
            spread = columns[position] if len(columns) > position else []
            column.addWidget(StatBar(name, value,
                                     codex.percentile(spread, value),
                                     self.fonts))
        column.addStretch(1)
        split.addLayout(column, 1)
        self.detail.addLayout(split)

        self.detail.addWidget(_wrapped(
            "Ability: %s" % (", ".join(entry.get("abilities") or []) or "—"),
            self.fonts.small, T.TEXT_DIM))
        self.detail.addWidget(_eyebrow("move pool (%d)"
                                       % len(entry.get("moveset") or []),
                                       self.fonts, T.TEXT_FAINT))
        pool = QScrollArea()
        pool.setWidgetResizable(True)
        pool.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pool.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        grid = QVBoxLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        for move_name in entry.get("moveset") or []:
            grid.addWidget(self._move_line(move_name))
        grid.addStretch(1)
        pool.setWidget(holder)
        self.detail.addWidget(pool, 1)

    def _move_line(self, move_name, move=None):
        move = move or (self.lookup_move(move_name) or {})
        colour = T.type_color(move.get("type", "Normal"))
        row = RoundedPanel(None, bg=T.mix(T.PANEL_SUNK, colour, 0.14),
                           border=colour, radius=T.RADIUS_SM)
        line = QHBoxLayout(row)
        line.setContentsMargins(9, 4, 9, 4)
        line.setSpacing(8)
        line.addWidget(_label(move_name, self.fonts.small_bold, T.TEXT))
        line.addStretch(1)
        if move:
            bits = [T.CATEGORY_GLYPH.get(move.get("category"), "STA")]
            if move.get("power"):
                bits.append("PWR %d" % move["power"])
            accuracy = move.get("accuracy")
            bits.append("ACC %d%%" % round(accuracy * 100) if accuracy
                        else "ACC —")
            line.addWidget(_label("  ·  ".join(bits), self.fonts.tiny,
                                  T.TEXT_DIM))
        return row

    #: set by PokedexDialog so a Pokemon's move pool can show real move data
    lookup_move = staticmethod(lambda name: None)

    def _show_ability(self, entry):
        """One Pokemon ability, and every Pokemon that has it.

        No written description: the behaviour only exists as code in
        abilities.py, so inventing prose here would create a second account of
        one ability that could silently disagree with the first.

        Character abilities are not in this section at all -- see
        codex._abilities. Which competitor has which is what Scout Opponent is
        for.
        """
        head = QHBoxLayout()
        head.addWidget(ElidedLabel(entry["name"], self.fonts.hero, T.TEXT), 1)
        self.detail.addLayout(head)

        # One line from Scripts/Data/ability_text.py. Absent for anything not
        # described there, rather than a placeholder.
        text = str(entry.get("text") or "").strip()
        if text:
            self.detail.addWidget(_wrapped(text, self.fonts.body, T.TEXT_DIM))

        holders = entry.get("pokemon") or []
        self.detail.addWidget(_eyebrow("POKEMON WITH IT (%d)" % len(holders),
                                       self.fonts))
        if holders:
            self.detail.addWidget(_wrapped(", ".join(holders),
                                           self.fonts.small, T.TEXT_DIM))
        else:
            self.detail.addWidget(_label("No Pokemon has this yet.",
                                         self.fonts.small, T.TEXT_FAINT))
        self.detail.addStretch(1)

    def _show_move(self, entry):
        head = QHBoxLayout()
        head.addWidget(ElidedLabel(entry["name"], self.fonts.hero, T.TEXT),
                       1)
        head.addWidget(Chip(entry["type"], T.type_color(entry["type"]),
                            self.fonts))
        head.addWidget(Chip(entry["category"], T.TEXT_FAINT, self.fonts))
        if entry.get("custom"):
            head.addWidget(Chip("custom", T.CYAN, self.fonts))
        self.detail.addLayout(head)

        accuracy = entry.get("accuracy")
        tiles = QHBoxLayout()
        tiles.setSpacing(6)
        for caption, value in (("power", entry["power"] or "—"),
                               ("accuracy", "always" if accuracy is None
                                else "%d%%" % round(accuracy * 100)),

                               ("priority", "%+d" % entry["priority"]
                                if entry["priority"] else "—")):
            panel = RoundedPanel(None, bg=T.PANEL_SUNK, border=T.LINE_SOFT,
                                 radius=T.RADIUS_SM)
            inner = QVBoxLayout(panel)
            inner.setContentsMargins(12, 5, 12, 5)
            inner.setSpacing(0)
            inner.addWidget(_label(caption, self.fonts.tiny, T.TEXT_FAINT))
            inner.addWidget(_label(str(value), self.fonts.title, T.TEXT))
            tiles.addWidget(panel)
        tiles.addStretch(1)
        self.detail.addLayout(tiles)

        self.detail.addWidget(_eyebrow("effect", self.fonts, T.TEXT_FAINT))
        lines = codex.describe(entry)
        if not lines:
            lines = ["Straight damage, with no additional effect."]
        for text in lines:
            self.detail.addWidget(_wrapped("•  " + text, self.fonts.small,
                                           T.TEXT))

        learned = entry.get("learned_by") or []
        self.detail.addWidget(_eyebrow("learned by (%d)" % len(learned),
                                       self.fonts, T.TEXT_FAINT))
        self.detail.addWidget(_wrapped(", ".join(learned) or "Nobody in the "
                                       "roster learns this.",
                                       self.fonts.small, T.TEXT_DIM))
        self.detail.addStretch(1)

    def _show_opponent(self, entry):
        head = QHBoxLayout()
        head.addWidget(ElidedLabel(entry["nickname"], self.fonts.hero,
                                   T.TEXT), 1)
        if entry.get("tier"):
            head.addWidget(Chip(entry["tier"], T.TEXT_FAINT, self.fonts))
        head.addWidget(Chip("rated %d" % entry["rating"], T.CYAN, self.fonts))
        self.detail.addLayout(head)

        split = QHBoxLayout()
        split.setSpacing(14)
        art = entry.get("art")
        picture = os.path.join(self.root_dir, art) if art else None
        if picture and os.path.exists(picture):
            # _FittedArt, so this gets the same device-pixel scaling the
            # About Opponent window does -- these are 1024px illustrations
            # _FittedArt carries a QSizePolicy of Ignored in both directions --
            # that is what lets the column size the picture instead of the
            # other way round -- so a layout will not reserve space for it and
            # the text column was being laid out straight over the top of it.
            # A plain container with a normal policy reserves the box; the art
            # fills it.
            frame = _ClickableFrame(picture, self)
            # Fixed *height*, capped width. A fixed square made the window's
            # own minimum size wider than the display it was meant for; a
            # capped width can give room back when there is not enough, and
            # because the height never changes nothing reflows vertically as
            # the selection moves. _FittedArt keeps the aspect ratio either
            # way, so a slightly wide frame just letterboxes.
            frame.setFixedHeight(self.portrait)
            frame.setMaximumWidth(self.portrait)
            frame.setMinimumWidth(PORTRAIT_MIN)
            frame.setStyleSheet("background: transparent;")
            inner = QVBoxLayout(frame)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.addWidget(_FittedArt(QPixmap(picture)))
            split.addWidget(frame, 6, Qt.AlignTop)
        # Four sections, always in this order: who they are, what they say,
        # what they bring, what they change. Every heading is the accent gold
        # -- they are the only thing giving this column structure, and at
        # eyebrow size in TEXT_FAINT they were quieter than the body text
        # they introduced.
        column = QVBoxLayout()
        column.setSpacing(6)

        if entry.get("description"):
            column.addWidget(_eyebrow("about them", self.fonts, T.ACCENT))
            # codex flows these into one paragraph first: the CSV cell holds
            # hard line breaks wherever the spreadsheet wrapped, which is not
            # where a sentence ends, and a wrapped label then re-wraps inside
            # each fragment into ragged two-word lines.
            column.addWidget(_wrapped(entry["description"], self.fonts.small,
                                      T.TEXT))

        if entry.get("quote"):
            column.addWidget(_eyebrow("quote", self.fonts, T.ACCENT))
            column.addWidget(_wrapped('"%s"' % entry["quote"],
                                      self.fonts.small, T.TEXT_DIM))

        # The Pokemon and its typing, and nothing else. The Strategy blurb
        # used to follow in grey, which repeated the same Pokemon's name in
        # prose and said "(Custom)" -- whether a Pokemon was hand-built is
        # not a fact about the Pokemon, and it read as a tier.
        if entry.get("aces"):
            column.addWidget(_eyebrow("ace", self.fonts, T.ACCENT))
            for ace in entry["aces"]:
                row = QHBoxLayout()
                row.setSpacing(4)
                row.addWidget(_label(ace["name"], self.fonts.body_bold,
                                     T.TEXT))
                for type_name in ace["types"]:
                    row.addWidget(Chip(type_name, T.type_color(type_name),
                                       self.fonts))
                row.addStretch(1)
                column.addLayout(row)

        if entry.get("ability"):
            column.addWidget(_eyebrow("character ability", self.fonts,
                                      T.ACCENT))
            column.addWidget(_label(entry["ability"], self.fonts.body_bold,
                                    T.TEXT))
            # naming it says nothing on its own: the effect is the reason a
            # player looked it up
            if entry.get("ability_effect"):
                column.addWidget(_wrapped(entry["ability_effect"],
                                          self.fonts.small, T.TEXT_DIM))
        column.addStretch(1)
        wrap = QScrollArea()
        wrap.setWidgetResizable(True)
        wrap.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # an explicit minimum, and a policy that lets it shrink to it: word
        # wrapped labels otherwise report the width they would *like* and drag
        # the whole window wider than the display
        wrap.setMinimumWidth(TEXT_MIN)
        wrap.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        wrap.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        holder.setLayout(column)
        wrap.setWidget(holder)
        split.addWidget(wrap, 5)
        self.detail.addLayout(split, 1)


class PokedexDialog(QDialog):
    """The window. One search box, three sections, no game state involved."""

    def __init__(self, fonts, data, project_root=".", parent=None):
        super().__init__(parent)
        self.fonts = fonts
        self.sections = {}
        self.setWindowTitle("Pokedex")
        self.setStyleSheet("background: %s;" % T.BG)
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        room = screen.availableGeometry() if screen else None
        self.resize(min(WINDOW_MAX_W, room.width() - 40) if room else 1240,
                    min(940, room.height() - 40) if room else 800)

        self.portrait = portrait_box(
            room.height() if room else None, room.width() if room else None)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.entry = QLineEdit()
        self.entry.setFont(fonts.body)
        self.entry.setPlaceholderText(
            "search  —  name, type, ability, move, tier, or a stat "
            "(fire spd>110)")
        self.entry.setStyleSheet(
            "QLineEdit { background: %s; color: %s; border: 1px solid %s;"
            "border-radius: %dpx; padding: 8px 12px; }"
            % (T.PANEL_SUNK, T.TEXT, T.ACCENT, T.RADIUS_SM))
        # debounced: filtering 381 rows per keystroke is cheap, but not
        # cheap enough to do it mid-word on every character
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self._filter)
        self.entry.textChanged.connect(lambda _: self._debounce.start())
        self.entry.returnPressed.connect(self._filter)
        top.addWidget(self.entry, 1)
        top.addWidget(ActionButton("Clear", fonts,
                                   on_click=lambda: self.entry.setText("")))
        # Close sits up here rather than on a row of its own, and the examples
        # are a tooltip on the box rather than a line under it. Between them
        # that was a hundred pixels of chrome above the artwork, which is a
        # hundred pixels the portraits can have instead.
        top.addWidget(ActionButton("Close", fonts, on_click=self.close))
        self.entry.setToolTip("Examples:" + chr(10)
                              + EXAMPLES.replace(" · ", chr(10)))
        outer.addLayout(top)

        self.tabs = _style_tabs(self._make_tabs(), fonts)
        moves_by_name = {move["name"]: move
                         for move in (data.get("moves") or [])}
        for title in SECTIONS:
            kind = title.lower()
            section = _Section(kind, data, fonts, project_root, self,
                               portrait=self.portrait)
            section.lookup_move = moves_by_name.get
            self.sections[kind] = section
            self.tabs.addTab(section, title)
        self.tabs.currentChanged.connect(lambda _: self._filter())
        outer.addWidget(self.tabs, 1)

    def _make_tabs(self):
        from PySide6.QtWidgets import QTabWidget
        return QTabWidget(self)

    def _current(self):
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, _Section) else None

    def _filter(self):
        section = self._current()
        if section is not None:
            section.apply(self.entry.text().strip())

    def present(self, section=None):
        if section and section in self.sections:
            self.tabs.setCurrentWidget(self.sections[section])
        self.show()
        self.raise_()
        self.activateWindow()
        self.entry.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            return self.close()
        super().keyPressEvent(event)
