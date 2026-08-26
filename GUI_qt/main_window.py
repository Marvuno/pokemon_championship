"""
The main window: scoreboard, arena, tabbed battle feed/log, action bar.

Every input() the game asks arrives here as an EV_INPUT event, gets
classified by prompt_parser, and is rendered as something clickable --
move cards, a switch-in grid, a multi-select for team trimming, or a
generic button list, depending on what's being asked.

A QTimer on a 20ms tick drains bridge.events (EV_TEXT, EV_STATE,
EV_INPUT, EV_DONE, EV_ERROR, EV_BANNER) and dispatches each to the
matching handler below. bridge.py itself is untouched by any of this --
it doesn't know or care what's consuming its queue.
"""

import os
import queue
import re
import sys

from PySide6.QtCore import QEvent, QProcess, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QScrollArea, QStackedWidget,
                               QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from GUI import ansi, bridge as B, prompt_parser as P, theme as T
from GUI_qt import settings
from GUI_qt.arena import ArenaBackdrop
from GUI_qt.fonts import Fonts
from GUI_qt.panels import (AppearanceDialog, CareerDialog, CompareDialog,
                           CreditsDialog,
                           HistoryDialog, OpponentInfoDialog, RosterDialog,
                           SettingsDialog, StandingsDialog, StoryDialog)
from GUI_qt.pokedex import PokedexDialog
from GUI_qt.sprites import (DIR_OPPONENT, DIR_PLAYER, animate_switch,
                            current_frame, show_sprite, stop_switch)
from GUI_qt.title import TitleView
from GUI_qt import widgets as W
from GUI_qt.widgets import (AbilityFlare, ActionButton, CombatantCard,
                            FeedEntry, MoveCard, ResultOverlay, RoundedPanel,
                            ScoutCard, TurnDivider, clear_layout, shadow)
from GUI_qt.widgets import label as _label

#: the only phases where the arena (HP bars, sprites) means anything --
#: every other phase gets the title/lobby backdrop instead of a stale
#: battle board
BATTLE_PHASES = ("battle", "result")

# "Ice Hammer (Ice) [Super Effective]" -> name / type / effectiveness
MOVE_LABEL_RE = re.compile(
    r"^(?P<name>.+?)(?:\s*\((?P<type>[A-Za-z]+)\))?(?:\s*\[(?P<effect>.*)\])?$")


class MainWindow(QWidget):
    #: Everything that is neither the arena nor the action list: outer
    #: margins, scoreboard, body gaps, and the action bar's own header and
    #: question line. Measured, not guessed.
    CHROME_HEIGHT = 200

    #: The smallest window the layout fits in. The vertical stack's own
    #: minimum comes out at 1169x757, so these are that with a little air.
    MIN_WIDTH, MIN_HEIGHT = 1180, 768

    def __init__(self, project_root):
        super().__init__()
        self.root = project_root
        self.window_size = self._resolve_window_size()
        self.fonts = Fonts()
        self.difficulty = settings.get_difficulty()
        self.volume = 50            # session-only
        self.memory = P.PromptMemory()
        self.request = None
        self.game_state = {}
        self.hotkeys = {}
        self._last_turn = None
        self._last_weather = None
        self._last_opponent_info = None
        self._last_history_info = None
        self._about_dialog = None
        self._scout_token = None       # what the hover card is currently showing
        self.pokedex_dialog = None     # built on first use; see _open_pokedex
        self.compare_dialog = None     # built on first use; see _drive_reward
        self._skip_next_continue = False   # see _drive_reward
        #: what the player chose on the compare screen, so the engine's two
        #: follow-up index questions can be answered without asking again
        self._reward_plan = None
        #: who was last on the field per side, for spotting a switch
        self._active_seen = {}
        self.credits_dialog = None     # built on first use; see _open_credits
        #: set when a run finishes, so the credits note knows if you won
        self._credits_state = {}
        self._last_career = {}         # per-view payloads of the HISTORY screen
        self._career_shown = False     # window raised for this visit
        self._last_bracket = None
        self._last_view_pokemon_ping = None
        self._last_story_ping = None
        self._last_tutorial_ping = None
        self._last_result_seq = None
        self._last_reward_seq = None
        self._last_battle_seq = None
        self._last_auto_battle = False
        self._last_leaderboard = None
        self._fainted_seen = {"player": set(), "opponent": set()}
        self._gated = False          # holding the screen on a battle result
        self._placed_once = False    # borderless: moved to the screen origin
        self._pending_answers = []
        self._pending_kind = None    # which screen queued those answers
        self._trim_state = {"signature": None}
        self._keep_state = {"signature": None}
        self.roster_dialog = RosterDialog(self.fonts, project_root, self)
        self.standings_dialog = StandingsDialog(self.fonts, self)
        self.history_dialog = HistoryDialog(self.fonts, self)
        self.career_dialog = CareerDialog(self.fonts, project_root, self)
        self.career_dialog.picked.connect(self._career_pick)
        self.career_dialog.dismissed.connect(self._career_closed)
        self.lore = {}               # filled in by bridge.py at startup
        self.story_dialog = None       # Background reader
        self.tutorial_dialog = None    # Tutorial reader
        self.appearance_dialog = None  # built on first use
        #: which gender's portraits are showing. The engine's gender
        #: question is answered from this and never drawn -- see
        #: _drive_appearance. 0 is the first it offers, so Male.
        self._appearance_gender = 0
        self._appearance_genders = ["Male", "Female"]
        self._appearance_back = "9"
        #: set while the first-run walkthrough is being read, so the
        #: tutorial reader follows the background one by itself
        self._guided = False
        #: the tutorial ping arrived while the background was open
        self._guided_tutorial = False

        self.setWindowTitle("Pokemon Champion")
        self.setObjectName("root")
        self.setStyleSheet("#root { background: %s; } "
                           "QLabel { background: transparent; }" % T.BG)
        # Borderless full screen, always. Fixed rather than resizable so
        # every layout below can assume a size that never changes -- that is
        # what stops the arena and sprites being re-fitted mid-battle.
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setFixedSize(*self.window_size)
        # Split once, here. The action list gets a fixed share and the arena
        # takes the rest -- fitting the action list to its content instead
        # made the arena, the platform anchors and both sprites jump every
        # time the buttons changed.
        height = self.window_size[1]
        self.actions_height = int(height * 0.225)
        self.arena_height = height - self.CHROME_HEIGHT - self.actions_height

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)
        outer.addWidget(self._build_scoreboard())
        outer.addLayout(self._build_body(), 1)
        outer.addWidget(self._build_action_bar())
        self._sync_stage_view(None)   # title screen until the game says otherwise

        self.bridge = B.Bridge(project_root, difficulty=self.difficulty)
        self.bridge.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pump)
        self._timer.start(20)

    def _resolve_window_size(self):
        """The size to build the whole layout to: the screen's own.

        Floored at the smallest the layout actually fits in rather than
        trusted blindly, so a tiny or misreported desktop cannot produce a
        window the panels do not fit inside.
        """
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return (self.MIN_WIDTH, self.MIN_HEIGHT)
        size = screen.geometry()
        return (max(self.MIN_WIDTH, size.width()),
                max(self.MIN_HEIGHT, size.height()))

    def showEvent(self, event):
        super().showEvent(event)
        # Sit at the screen origin. Done on show rather than in __init__
        # because the window manager can otherwise place it itself.
        if not self._placed_once:
            self._placed_once = True
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                self.move(screen.geometry().topLeft())

    # ------------------------------------------------------------ scoreboard
    def _build_scoreboard(self):
        bar = RoundedPanel(self, bg=T.PANEL_SUNK, border=T.LINE_SOFT,
                           radius=T.RADIUS_LG)
        bar.setMinimumHeight(60)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(14)

        def two_line(top_text, top_font, top_color, bottom_text, bottom_font,
                    bottom_color):
            col = QVBoxLayout()
            col.setSpacing(3)
            col.addWidget(_label(top_text, top_font, top_color))
            bottom = _label(bottom_text, bottom_font, bottom_color)
            col.addWidget(bottom)
            return col, bottom

        # No separate title label here -- the OS window title bar already
        # says "Pokemon Champion"; repeating it as a full-size label cost
        # ~380px of width for something already visible above the window.

        self.score_values = {}
        # No WEATHER here: the field strip over the arena shows it, with an
        # emblem and a countdown, so a second copy in the header was saying
        # the same thing worse and taking width from the buttons.
        for key, caption, color in (
                ("round", "ROUND", T.TEXT), ("turn", "TURN", T.TEXT),
                ("you", "YOU", T.PLAYER),
                ("opponent", "OPPONENT", T.OPPONENT)):
            col, value = two_line(caption, self.fonts.eyebrow, T.TEXT_FAINT,
                                  "\u2014", self.fonts.body_bold, color)
            self.score_values[key] = value
            layout.addLayout(col)

        layout.addStretch(1)

        # Named, not pictured. Icons were tried and reverted: at 22px the
        # shapes carry less than the word does, and the row is read once and
        # then known by position anyway.
        #
        # Background and Tutorial are separate on purpose: they used to be
        # one five-page reader, so a player wanting a rules reminder had to
        # page past the story to reach it. Credits is not here at all -- it
        # is what you read before or after a run, so it lives on the title
        # screen with New Game and Continue.
        for caption, accent, handler in (
                ("Background", T.ACCENT, self._open_background),
                ("Tutorial", T.ACCENT, self._open_tutorial),
                ("Settings", T.TEXT_DIM, self._open_settings)):
            layout.addWidget(ActionButton(caption, self.fonts, accent=accent,
                                          on_click=handler),
                             alignment=Qt.AlignVCenter)
        # In the top bar rather than on a menu, so it is reachable from the
        # title screen, from the pre-battle menu and mid-battle alike. It is
        # pure reference material -- it reads a snapshot and touches no game
        # state -- so there is no reason to gate it behind a prompt.
        layout.addWidget(ActionButton(
            "Pokedex", self.fonts, accent=T.CYAN,
            on_click=self._open_pokedex), alignment=Qt.AlignVCenter)
        # These two have nothing to show before a run starts -- no matchups,
        # no team -- so they are hidden at the title screen and appear once
        # there is a game to look at. See _apply_state.
        self.standings_button = ActionButton(
            "Standings", self.fonts, accent=T.VIOLET,
            on_click=self._open_standings)
        self.team_button = ActionButton(
            "Your Team", self.fonts, accent=T.CYAN,
            on_click=lambda: self.roster_dialog.show_side("player"))
        for button in (self.standings_button, self.team_button):
            button.setVisible(False)
            layout.addWidget(button, alignment=Qt.AlignVCenter)
        # No title bar, so the window has to supply its own minimise and
        # close. Both sit at the top right, in the order a title bar would
        # put them. Escape also closes (see keyPressEvent).
        layout.addWidget(ActionButton(
            "–", self.fonts, accent=T.TEXT_DIM,
            on_click=self.showMinimized), alignment=Qt.AlignVCenter)
        layout.addWidget(ActionButton(
            "✕", self.fonts, accent=T.OPPONENT,
            on_click=self.close), alignment=Qt.AlignVCenter)
        return bar

    def _set_volume(self, value):
        self.volume = value
        self.bridge.set_volume(value / 100)

    def _open_settings(self):
        dialog = SettingsDialog(self.fonts, self.difficulty, self.volume,
                                self)
        dialog.on_difficulty_change = settings.set_difficulty
        dialog.on_volume_change = self._set_volume
        dialog.exec()

    def _open_credits(self):
        """The closing note and Documentation/credits.md, on request.

        It used to open itself the moment a run ended, over the top of the
        final standings. Whether you won is remembered from that moment so the
        note still reads correctly whenever you come to it.
        """
        state = self._credits_state or {}
        if self.credits_dialog is None:
            self.credits_dialog = CreditsDialog(
                self.fonts, self.root, champion=bool(state.get("champion")),
                titles=state.get("titles", 0), parent=self)
        self.credits_dialog.show()
        self.credits_dialog.raise_()
        self.credits_dialog.activateWindow()

    def _open_pokedex(self):
        """Built on first use: 239 Pokemon, 381 moves and 56 competitors is a
        lot of widgets to lay out for a window that may never be opened."""
        data = (self.game_state or {}).get("codex")
        if not data:
            return self._feed_add("status", "The Pokedex is still loading.")
        if self.pokedex_dialog is None:
            self.pokedex_dialog = PokedexDialog(self.fonts, data, self.root,
                                               self)
        self.pokedex_dialog.present()

    def _reader(self, attribute, pages, title, on_finish=None):
        """Build (or rebuild) one of the two page readers and show it.

        Rebuilt whenever it is opened guided, because `on_finish` belongs to
        this particular run through the flow and a reader left over from a
        previous open would carry the old one.
        """
        existing = getattr(self, attribute, None)
        if existing is None or on_finish is not None:
            existing = StoryDialog(self.fonts, self.lore, self.root, self,
                                   pages=pages, title=title,
                                   on_finish=on_finish)
            setattr(self, attribute, existing)
        existing.present()
        return existing

    def _open_background(self, on_finish=None):
        return self._reader("story_dialog", StoryDialog.BACKGROUND_PAGES,
                            "Background", on_finish)

    def _open_tutorial(self, on_finish=None):
        return self._reader("tutorial_dialog", StoryDialog.TUTORIAL_PAGES,
                            "Tutorial", on_finish)

    def _finished_background(self):
        """End of the background pages during a first run.

        The engine has already run tutorial() by now -- both are swallowed
        and pinged, one after the other -- so the tutorial ping may have
        arrived while the background reader was still open. Chain to it here
        rather than letting it open on top of the page being read.
        """
        if self._guided_tutorial:
            self._guided_tutorial = False
            self._open_tutorial(on_finish=self._finished_walkthrough)
        else:
            self._finished_walkthrough()

    def _finished_walkthrough(self):
        """Both readers done. The engine is on its single Continue."""
        self._guided = False

    def _open_story(self):
        """Alias for the Background reader.

        "Story" was one five-page reader holding the background and the
        tutorial together. It is two readers now, and Background is what
        "story" always meant; this is kept so existing callers do not have
        to know that.
        """
        return self._open_background()

    def _open_standings(self):
        self.standings_dialog.show()
        self.standings_dialog.raise_()

    # ----------------------------------------------------------------- body
    def _build_body(self):
        row = QHBoxLayout()
        row.setSpacing(12)

        self.arena = ArenaBackdrop(self, project_root=self.root)
        shadow(self.arena, blur=34, dy=8, alpha=110)
        grid = QGridLayout(self.arena)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        # Opposite corners: the opponent's readout top-left, yours
        # bottom-right, the way a Pokemon battle screen reads. They fit there
        # now because the cards are much smaller than they were -- when they
        # were full-size the bottom-right one collided with the backdrop's
        # far platform, which is why they briefly both sat along the top.
        self.opponent_card = CombatantCard("opponent", self.fonts, self.arena)
        grid.addWidget(self.opponent_card, 0, 0, Qt.AlignTop | Qt.AlignLeft)

        # The two sprites are placed by hand rather than given grid cells.
        # The backdrop art puts its platforms where the composition wants
        # them -- near and left, far and right -- not on quarter lines, so
        # the only way to stand a Pokemon *on* one is to ask the backdrop
        # where it is (see _place_sprites and ArenaBackdrop.platform_point).
        # They are still children of the arena, so they scroll and clip with
        # it and stay under the result overlay.
        self.opponent_sprite = QLabel(self.arena)
        self.opponent_sprite.setAlignment(Qt.AlignCenter)
        self.player_sprite = QLabel(self.arena)
        self.player_sprite.setAlignment(Qt.AlignCenter)
        for label_widget in (self.opponent_sprite, self.player_sprite):
            label_widget.setAttribute(Qt.WA_Hover, True)
            label_widget.installEventFilter(self)

        self.player_card = CombatantCard("player", self.fonts, self.arena)
        grid.addWidget(self.player_card, 1, 1,
                       Qt.AlignBottom | Qt.AlignRight)

        # Hover a sprite, or one of the pips on a card, to see that Pokemon's
        # moves and IVs. The pips are the only way to reach the *bench* during
        # a battle, which is most of what a successful scout buys you.
        self.scout_card = ScoutCard(self.fonts, self)
        self.scout_card.hide()
        self.opponent_card.pips.hovered.connect(
            lambda index: self._hover_pip("opponent", index))
        self.player_card.pips.hovered.connect(
            lambda index: self._hover_pip("player", index))

        # Weather, terrain and rooms, permanently on screen. Top-centre of
        # the arena, between the opponent's card (top-left) and their ability
        # flare (top-right), so it costs the battle view no height at all --
        # which is the whole point. The Field tab still holds the per-side
        # detail; this is only the three field-wide layers, which the real
        # games keep in separate slots and which can all be up at once.
        self.field_strip = W.FieldStrip(self.fonts, self.arena)
        grid.addWidget(self.field_strip, 0, 0, 1, 2,
                       Qt.AlignTop | Qt.AlignHCenter)

        # Centred across the whole grid rather than positioned by hand, so
        # it tracks the arena's geometry automatically instead of needing a
        # correct size at the one moment the gate opens (which it doesn't
        # reliably have). Added last, and raised on show, so it sits above
        # the cards it overlaps.
        self.result_overlay = ResultOverlay(self.fonts, self.arena)
        grid.addWidget(self.result_overlay, 0, 0, 2, 2, Qt.AlignCenter)
        self.result_overlay.hide()

        # One flare per side, each sitting in that side's half of the field
        # so it's obvious whose character ability just fired.
        self.flares = {
            "opponent": AbilityFlare("opponent", self.fonts, self.arena),
            "player": AbilityFlare("player", self.fonts, self.arena),
        }
        grid.addWidget(self.flares["opponent"], 0, 1,
                       Qt.AlignRight | Qt.AlignTop)
        grid.addWidget(self.flares["player"], 1, 0,
                       Qt.AlignLeft | Qt.AlignBottom)

        # Two interchangeable backdrops in the same slot: the arena while a
        # match is live, the title/lobby view for everything else.
        self.title_view = TitleView(self.fonts, self.root, self)
        self.stage_views = QStackedWidget(self)
        self.stage_views.addWidget(self.title_view)   # index 0
        self.stage_views.addWidget(self.arena)        # index 1

        # The field readout used to be a strip of chips under the arena.
        # It now lives in its own tab (see _build_log), which has room to
        # name each effect, say what it does and count it down -- and the
        # arena gets the height the strip was using.
        self.stage_views.setFixedHeight(self.arena_height)

        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self.stage_views, 1)

        # The arena is the thing worth looking at, so it takes the larger
        # share; the log only needs enough width for its entries to wrap
        # sensibly, which it still has at this split.
        row.addLayout(left, 9)
        row.addWidget(self._build_log(), 4)
        return row

    #: Sprite height as a fraction of the arena's, per side. The near
    #: platform in the backdrop art is much bigger than the far one, so the
    #: Pokemon standing on it should be too -- that difference is the only
    #: thing selling the depth of the composition.
    SPRITE_SCALE = {"player": 0.46, "opponent": 0.34}
    #: clear air to leave between a sprite's head and the HP cards above it
    SPRITE_GAP = 8

    def _sprite_target(self, which):
        """A fraction of the arena, capped by the headroom above that side's
        platform. Only the card actually in the way counts -- yours stands
        low and left, so the opponent's top-left card limits it; theirs
        stands mid-right with nothing above it."""
        arena_height = max(120, self.arena.height())
        wish = int(arena_height * self.SPRITE_SCALE[which])
        feet = self.arena.platform_point(which).y()
        # sizeHint, not geometry: the card's laid-out rect is 0 until Qt has
        # run the layout, so reading geometry gave a different answer on the
        # first state update than on every one after it -- and the sprite
        # moved between them.
        ceiling = (self.opponent_card.sizeHint().height() + 10
                   if which == "player" else 0)
        room = feet - ceiling - self.SPRITE_GAP
        return max(56, min(wish, room)) if room > 56 else max(56, wish)

    def _place_sprites(self):
        """Stand each Pokemon on its platform, feet on the anchor -- so a
        tall one and a short one share the same ground."""
        for which, label in (("player", self.player_sprite),
                             ("opponent", self.opponent_sprite)):
            size = getattr(label, "_sprite_size", None)
            if size is None:
                continue
            label.resize(size)
            point = self.arena.platform_point(which)
            # keep the whole sprite inside the arena, whatever the art says
            left = min(max(0, point.x() - size.width() // 2),
                       max(0, self.arena.width() - size.width()))
            top = min(max(0, point.y() - size.height()),
                      max(0, self.arena.height() - size.height()))
            label.move(left, top)
            # Mid-switch the two stand-in ghosts are doing the acting and the
            # live sprite is hidden, so it must not be shown again here. State
            # updates arrive many times a second and every one of them lands
            # in this function, which is why the animation cannot simply hide
            # the label and trust it to stay hidden.
            if getattr(label, "_switch_busy", False):
                label.hide()
            else:
                label.show()
        # under the result plate, over the backdrop and the cards' shadows
        self.player_sprite.raise_()
        self.opponent_sprite.raise_()
        if self.result_overlay.isVisible():
            self.result_overlay.raise_()

    # -- the hover readout ------------------------------------------------
    def eventFilter(self, watched, event):
        """Sprite hover. QLabel has no hover signal, and subclassing it just
        for two events would mean two more classes; WA_Hover plus this is the
        whole mechanism."""
        kind = event.type()
        if kind == QEvent.HoverEnter or kind == QEvent.HoverMove:
            side = ("player" if watched is self.player_sprite
                    else "opponent" if watched is self.opponent_sprite
                    else None)
            if side is not None:
                self._show_scout(side, self._active_index(side))
                return False
        elif kind == QEvent.HoverLeave and watched in (self.player_sprite,
                                                      self.opponent_sprite):
            self.scout_card.hide()
        return super().eventFilter(watched, event)

    def _hover_pip(self, side, index):
        if index < 0:
            self.scout_card.hide()
        else:
            self._show_scout(side, index)

    def _active_index(self, side):
        """Which team slot the Pokemon currently out belongs to.

        Matched by name because the snapshot has no slot number, and a team
        cannot hold two of the same Pokemon (the reward screen replaces
        rather than duplicates), so the name is unambiguous.
        """
        active = (self.game_state or {}).get(
            "player" if side == "player" else "opponent") or {}
        team = (self.game_state or {}).get(
            "player_team" if side == "player" else "opponent_team") or []
        for index, member in enumerate(team):
            if member.get("name") == active.get("name"):
                return index
        return 0

    def _scout_entry(self, side, index):
        """Full detail for one team slot, or None if there is none to show.

        Falls back to the active Pokemon's own snapshot, which carries the
        same fields: the rosters are only published between prompts, so on the
        very first hover of a battle the roster list can still be a round
        behind while the active snapshot is current.
        """
        state = self.game_state or {}
        roster = state.get("player_roster" if side == "player"
                           else "opponent_roster") or []
        if 0 <= index < len(roster):
            return roster[index]
        active = state.get("player" if side == "player" else "opponent")
        if active and index == self._active_index(side):
            return active
        return None

    def _show_scout(self, side, index):
        state = self.game_state or {}
        if state.get("phase") not in BATTLE_PHASES:
            return self.scout_card.hide()
        # Their side is information you have to earn -- winning the round or
        # scouting in About Opponent. Yours is always yours.
        known = side == "player" or bool(state.get("opponent_known"))
        team = state.get("player_team" if side == "player"
                         else "opponent_team") or []
        entry = self._scout_entry(side, index)
        if entry is None:
            # Not scouted and not the one on the field: there is nothing to
            # name, so say nothing rather than pop up an empty card.
            if not known and 0 <= index < len(team):
                entry = team[index]
            else:
                return self.scout_card.hide()
        # HoverMove lands on every pixel of movement; rebuilding four move
        # rows and six stat cells that often is felt as lag, so the card is
        # only refilled when it would actually say something different.
        # The token has to carry everything the card draws, not just which
        # Pokemon it is. It used to be (side, index, known, name) -- so once a
        # card had been shown for a Pokemon, a stat stage or a condition
        # changing did not refresh it, and hovering the same Pokemon again
        # showed the stages it had the first time. That is the "stat changes
        # sometimes do not show" bug: the data had moved on and the token had
        # not.
        token = (side, index, known, entry.get("name"),
                 tuple(entry.get("modifier") or ()),
                 tuple(sorted((name, value) for name, value
                              in (entry.get("volatile") or {}).items()
                              if value)),
                 entry.get("status"), entry.get("hp"))
        if token != self._scout_token:
            self._scout_token = token
            self.scout_card.set_mon(entry, known=known, side=side)
        self.scout_card.show_at(QCursor.pos(), self._scout_bounds())

    def _scout_bounds(self):
        top_left = self.mapToGlobal(self.rect().topLeft())
        return QRect(top_left, self.size())

    def _sync_stage_view(self, phase):
        in_battle = phase in BATTLE_PHASES
        self.stage_views.setCurrentIndex(1 if in_battle else 0)
        # Standings and Your Team appear once there is a run to look at. At the
        # title screen there is no bracket and no team, so both would open on
        # nothing.
        started = phase not in (None, "", "menu")
        for button in (getattr(self, "standings_button", None),
                       getattr(self, "team_button", None)):
            if button is not None:
                button.setVisible(started)
        if not in_battle:
            self.result_overlay.hide()
            self.scout_card.hide()
            self.title_view.set_context(phase, self.game_state)

    def _build_log(self):
        """The right-hand panel: a friendly 'Battle' feed by default, with
        the raw ANSI transcript one tab away for debugging.

        Both tabs read the same underlying events -- EV_BANNER already
        gives us a curated per-move/per-ability transcript (see bridge.py's
        capture() hooks), so the Battle tab is just a permanent version of
        the same toast that flashes over the arena; nothing new had to be
        taught to the game side to get this.
        """
        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet(
            "QTabWidget::pane { background: %s; border: 1px solid %s;"
            "border-radius: %dpx; }"
            # snug padding: three tabs have to fit a column that is now
            # narrower than it used to be, and a scrolling tab bar looks
            # broken
            "QTabBar::tab { background: %s; color: %s; padding: 8px 11px;"
            "margin-right: 3px; border-top-left-radius: %dpx;"
            "border-top-right-radius: %dpx; }"
            "QTabBar::tab:selected { background: %s; color: %s; }"
            % (T.PANEL, T.LINE, T.RADIUS_LG, T.PANEL_SUNK, T.TEXT_FAINT,
               T.RADIUS_SM, T.RADIUS_SM, T.PANEL, T.TEXT))
        self.tabs.setFont(self.fonts.small_bold)

        self.feed_scroll = QScrollArea()
        self.feed_scroll.setWidgetResizable(True)
        # Without this the entries keep their preferred single-line width,
        # push the viewport wider and get a horizontal scrollbar instead of
        # wrapping. Denying horizontal scroll is what forces the word-wrap
        # in each entry's body to actually apply to the panel's width.
        self.feed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.feed_scroll.setStyleSheet("QScrollArea { border: none;"
                                       "background: transparent; }")
        feed_body = QWidget()
        feed_body.setStyleSheet("background: transparent;")
        self.feed_layout = QVBoxLayout(feed_body)
        self.feed_layout.setContentsMargins(10, 10, 10, 10)
        self.feed_layout.setSpacing(6)
        self.feed_layout.addStretch(1)   # keeps entries pinned to the top
        self.feed_scroll.setWidget(feed_body)
        self.tabs.addTab(self.feed_scroll, "Battle")

        # What is on the field right now, one row per effect, each counting
        # itself down and vanishing when it ends. This is the whole readout
        # -- there is no strip under the arena any more, and no log of
        # arrivals and departures either, because a board you can read at a
        # glance answers "is Reflect still up" better than either.
        self.field_scroll = QScrollArea()
        self.field_scroll.setWidgetResizable(True)
        self.field_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.field_scroll.setStyleSheet("QScrollArea { border: none;"
                                        "background: transparent; }")
        self.field_board = W.FieldBoard(self.fonts)
        self.field_scroll.setWidget(self.field_board)
        self._field_tab = self.tabs.count()
        self.tabs.addTab(self.field_scroll, "Field")

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(self.fonts.log)
        self.log.setStyleSheet(
            "QTextEdit { background: %s; color: %s; border: none; }"
            % (T.PANEL_SUNK, T.TEXT_DIM))
        self.tabs.addTab(self.log, "Log")
        self._log_tab = self.tabs.count() - 1

        self._log_unread = 0
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Auto-follow the newest entry. Doing this with a singleShot right
        # after inserting doesn't reliably work: the scrollbar's maximum
        # hasn't grown to include the new row yet, so it scrolls to the old
        # bottom and stalls one entry behind. Reacting to rangeChanged --
        # which fires once the new row is actually accounted for -- is what
        # makes it land on the newest line every time. Follow is dropped if
        # the player scrolls up to read back, and resumes when they return
        # to the bottom.
        self._feed_follow = True
        feed_bar = self.feed_scroll.verticalScrollBar()
        feed_bar.rangeChanged.connect(self._feed_range_changed)
        feed_bar.valueChanged.connect(self._feed_value_changed)
        return self.tabs

    def _feed_range_changed(self, _minimum, maximum):
        if self._feed_follow:
            self.feed_scroll.verticalScrollBar().setValue(maximum)

    def _feed_value_changed(self, value):
        bar = self.feed_scroll.verticalScrollBar()
        self._feed_follow = value >= bar.maximum() - 4

    def _on_tab_changed(self, index):
        if index == self._log_tab:
            self._log_unread = 0
            self.tabs.setTabText(self._log_tab, "Log")

    def _feed_add(self, kind, text, actor="", side=None):
        entry = FeedEntry(kind, text, self.fonts, actor=actor, side=side)
        self.feed_layout.insertWidget(self.feed_layout.count() - 1, entry)

    def _feed_divider(self, turn):
        divider = TurnDivider(turn, self.fonts)
        self.feed_layout.insertWidget(self.feed_layout.count() - 1, divider)

    # ------------------------------------------------------------ action bar
    def _build_action_bar(self):
        bar = RoundedPanel(self, bg=T.PANEL, border=T.LINE, radius=T.RADIUS_LG)
        shadow(bar, blur=26, dy=-4, alpha=100)
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(18, 10, 18, 10)
        outer.setSpacing(8)

        # The "type a value" escape hatch shares the header row rather than
        # owning one of its own: as a separate row it cost ~36px of height
        # that the buttons below genuinely need, for a control that is a
        # fallback and not an expected step.
        head = QHBoxLayout()
        self.prompt_tag = _label("", self.fonts.eyebrow, T.ACCENT)
        head.addWidget(self.prompt_tag)
        head.addStretch(1)
        # Credits sits in this bar rather than the header. It is what you
        # read before or after a run, so it does not belong among the six
        # things you reach *during* one -- but it does need to be reachable
        # without leaving whatever screen you are on, which is why it is
        # here and not on the title screen. This row is the action bar's
        # permanent furniture: it survives _clear_actions, so the button is
        # there whatever the game happens to be asking.
        head.addWidget(ActionButton("Credits", self.fonts,
                                    accent=T.TEXT_DIM,
                                    on_click=self._open_credits),
                       alignment=Qt.AlignVCenter)
        self.fallback_entry = QLineEdit()
        self.fallback_entry.setFont(self.fonts.small)
        self.fallback_entry.setFixedWidth(150)
        self.fallback_entry.setPlaceholderText("or type a value")
        self.fallback_entry.setStyleSheet(
            "QLineEdit { background: %s; color: %s; border: 1px solid %s;"
            "border-radius: %dpx; padding: 3px 8px; }"
            % (T.PANEL_SUNK, T.TEXT_DIM, T.LINE, T.RADIUS_SM))
        self.fallback_entry.returnPressed.connect(self._submit_fallback)
        head.addWidget(self.fallback_entry)
        outer.addLayout(head)

        self.question = _label("Waiting for the game to start\u2026",
                               self.fonts.lead, T.TEXT)
        outer.addWidget(self.question)

        # One fixed height for every screen. Whatever does not fit scrolls;
        # see the note in __init__ for why this is not fitted to content.
        self.actions_scroll = QScrollArea()
        self.actions_scroll.setWidgetResizable(True)
        self.actions_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")
        self.actions_body = QWidget()
        self.actions_body.setStyleSheet("background: transparent;")
        self.actions = QVBoxLayout(self.actions_body)
        self.actions.setContentsMargins(0, 0, 0, 0)
        # Deliberately no setAlignment(AlignTop) here. It keeps rows at their
        # preferred size in *both* directions, so a wide extras row (Switch
        # Pokemon + Auto battle, each with a sub-line) stopped being held to
        # the viewport width and ran off the side of the screen. The trailing
        # stretch added in _fit_actions is what pins content to the top.
        self.actions_scroll.setWidget(self.actions_body)
        self.actions_scroll.setFixedHeight(self.actions_height)
        outer.addWidget(self.actions_scroll)

        return bar

    def _fit_actions(self):
        """Settle a freshly built screen inside the fixed action area.

        The area no longer resizes to its content -- that is what kept the
        arena moving -- so instead the content is pinned to the top of it.
        Without this a two-button Confirm stretched its buttons to 250px
        tall to fill the space.
        """
        if self.actions.count() and not self.actions.itemAt(
                self.actions.count() - 1).spacerItem():
            self.actions.addStretch(1)

    # ------------------------------------------------------------- the pump
    def _pump(self):
        handled = 0
        while handled < 300:
            if self._gated:
                # Holding on a battle result: leave everything still queued
                # where it is, so the next prompt can't overwrite the screen
                # the player is being shown.
                break
            try:
                kind, payload = self.bridge.events.get_nowait()
            except queue.Empty:
                break
            handled += 1
            if kind == B.EV_TEXT:
                self._append_log(payload)
            elif kind == B.EV_CLEAR:
                self.log.clear()
            elif kind == B.EV_STATE:
                self._apply_state(payload)
            elif kind == B.EV_INPUT:
                self._show_request(payload)
            elif kind == B.EV_DONE:
                self._show_done(payload)
            elif kind == B.EV_ERROR:
                self._show_error(payload)
            elif kind == B.EV_BANNER:
                self._show_banner(payload)

    def _append_log(self, text):
        self.log.append(ansi.strip(text).rstrip())
        if self.tabs.currentIndex() != self._log_tab:
            self._log_unread += 1
            self.tabs.setTabText(self._log_tab,
                                 "Log (%d)" % self._log_unread)

    # ------------------------------------------------------------- state
    def _apply_state(self, state):
        self.game_state = state
        field = state.get("field") or {}
        you = state.get("player_side") or {}
        opp = state.get("opponent_side") or {}

        score = self.score_values
        score["round"].setText(str(state.get("stage", "\u2014")))
        score["turn"].setText(str(field.get("turn", "\u2014")))
        score["you"].setText("%s [%d]" % (you["nickname"], you["strength"])
                             if you else "\u2014")
        score["opponent"].setText("%s [%d]" % (opp["nickname"], opp["strength"])
                                  if opp else "\u2014")

        self.arena.set_weather(field.get("weather", "Clear"))

        # A new match starts with a clean battle log -- last round's blow by
        # blow isn't useful once the round is over, and it made the feed
        # impossible to read as "what is happening right now".
        battle_seq = state.get("battle_seq")
        if battle_seq is not None and battle_seq != self._last_battle_seq:
            self._last_battle_seq = battle_seq
            self._clear_feed()
            # A new match: same slot number, different Pokemon. Forget what
            # the hover card was showing so it cannot be reused stale.
            self._scout_token = None
            self.scout_card.hide()

        self._track_feed_worthy_changes(field, state.get("phase"))
        self._track_knockouts(state)
        self._sync_field(state)
        # Outside a live battle nothing is fainted, whatever the snapshot
        # still says: the engine leaves last round's zeroed HP on record
        # until the next battle rebuilds it (see snap_team in bridge.py).
        in_battle = state.get("phase") in BATTLE_PHASES
        self.player_card.set_team(self._condition(state.get("player_team"),
                                                 in_battle))
        self.opponent_card.set_team(self._condition(state.get("opponent_team"),
                                                   in_battle))

        if "player_roster" in state:
            self.roster_dialog.refresh(
                state["player_roster"], state.get("opponent_roster"),
                opponent_known=bool(state.get("opponent_known")))

        lore = state.get("lore")
        if lore and lore is not self.lore:
            self.lore = lore
            self.story_dialog = None      # rebuilt on next open, with the text
            self.tutorial_dialog = None

        # a new player: the engine's walkthrough now opens the reader
        # A new player is walked through both readers in order. The engine
        # runs backstory() then tutorial() back to back, so both pings can
        # land before either reader is closed -- `_guided_tutorial` remembers
        # that the second one is owed rather than opening it over the first.
        ping = state.get("show_tutorial")
        if ping is not None and ping != getattr(self, "_last_tutorial_ping",
                                                None):
            self._last_tutorial_ping = ping
            if self._guided:
                self._guided_tutorial = True   # chained after the background
            else:
                self._open_tutorial()
        ping = state.get("show_story")
        if ping is not None and ping != getattr(self, "_last_story_ping", None):
            self._last_story_ping = ping
            self._guided = True
            self._open_background(on_finish=self._finished_background)

        info = state.get("opponent_info")
        if info is not None and info is not self._last_opponent_info:
            self._last_opponent_info = info
            # Rebuilt each time (it is keyed to one competitor's artwork), so
            # the previous one is dropped rather than left as a hidden child
            # of the window. raise_/activateWindow because the window behind
            # it is borderless fullscreen.
            if self._about_dialog is not None:
                self._about_dialog.close()
                self._about_dialog.deleteLater()
            self._about_dialog = OpponentInfoDialog(info, self.fonts,
                                                   self.root, self)
            self._about_dialog.show()
            self._about_dialog.raise_()
            self._about_dialog.activateWindow()

        history = state.get("history_info")
        if history is not None and history is not self._last_history_info:
            self._last_history_info = history
            self.history_dialog.present(history)

        # The main menu's HISTORY screen. Four views, filled in as the engine
        # publishes them; the window is what the player interacts with, and
        # _drive_career answers the engine's own prompts.
        for key, show in (
                ("career_roster", self.career_dialog.show_roster),
                ("career_champions", self.career_dialog.show_champions),
                ("career_report", self.career_dialog.show_report),
                ("career_records", self.career_dialog.show_records)):
            payload = state.get(key)
            if payload is None or payload is self._last_career.get(key):
                continue
            self._last_career[key] = payload
            show(payload)
        # Opened on the roster, so the first thing on screen is the list of
        # names to click. Champions is one tab away rather than in the way.
        if state.get("career_open") and not self._career_shown:
            self._career_shown = True
            self.career_dialog.present("Opponents")
        elif not state.get("career_open"):
            self._career_shown = False

        ping = state.get("view_pokemon_requested")
        if ping is not None and ping != self._last_view_pokemon_ping:
            self._last_view_pokemon_ping = ping
            self.roster_dialog.show_side("player")

        if ("bracket" in state or "leaderboard" in state
                or "journey" in state or "round_results" in state):
            self.standings_dialog.refresh(
                state.get("bracket"), state.get("leaderboard"),
                state.get("journey"), state.get("champion"),
                rating=state.get("rating"),
                rating_change=state.get("rating_change"),
                rating_before=state.get("rating_before"),
                round_results=state.get("round_results"))

        # A new round's matchups used to open this window by itself. It is
        # already up to date the moment round_begin publishes -- five
        # unprompted windows a run is worse than a button, so the Standings
        # button is the way in. If it is already open, move it to the new
        # round's matchups rather than leaving last round's tab showing.
        bracket = state.get("bracket")
        if bracket is not None and bracket is not self._last_bracket:
            self._last_bracket = bracket
            if self.standings_dialog.isVisible():
                self.standings_dialog.select("Matchups")

        # End of the tournament: the engine computes the final table and the
        # rating changes and prints them into the log, where they scroll
        # past. Surface the real standings screen instead.
        leaderboard = state.get("leaderboard")
        if leaderboard is not None and leaderboard is not self._last_leaderboard:
            self._last_leaderboard = leaderboard
            self.standings_dialog.select("Leaderboard")
            self.standings_dialog.show()
            self.standings_dialog.raise_()

        self._sync_stage_view(state.get("phase"))

        # Who changed has to be worked out before the sprites are replaced --
        # the animation needs a picture of the Pokemon that left, and
        # show_sprite is about to overwrite it. Saying so has to wait until
        # after the cards are filled; see _announce_switches.
        switches = self._detect_switches(state)
        stills = {side: current_frame(self.player_sprite if side == "player"
                                     else self.opponent_sprite)
                  for side in switches}

        # Cards first, so the knockout is already on screen underneath the
        # result plate before the gate below stops the pump.
        player, opponent = state.get("player"), state.get("opponent")
        if player:
            self.player_card.set_mon(player)
            show_sprite(self.player_sprite, player.get("sprite", ""),
                       DIR_PLAYER, self.root,
                       target=self._sprite_target("player"))
        if opponent:
            self.opponent_card.set_mon(opponent)
            show_sprite(self.opponent_sprite, opponent.get("sprite", ""),
                       DIR_OPPONENT, self.root,
                       target=self._sprite_target("opponent"))
        if player or opponent:
            self._place_sprites()
        # After the cards are filled, not before: set_mon writes the card's
        # border itself, so a flash raised earlier in this same update was
        # painted over before it could be seen.
        self._announce_switches(state, switches, stills)

        reward = state.get("reward")
        if reward is not None and reward.get("seq") != self._last_reward_seq:
            self._last_reward_seq = reward.get("seq")
            self._announce_reward(reward)

        result = state.get("battle_result")
        if result is not None and result.get("seq") != self._last_result_seq:
            self._last_result_seq = result.get("seq")
            self._begin_result_gate(result)

    def _announce_reward(self, reward):
        """Say what the battle actually earned you, when it happens.

        The engine grants the end-of-battle Pokemon and only mentions it in
        the raw log (and for two of the four ways it can happen, not at all),
        so the only reliable way to find out used to be opening your team.
        """
        gained = reward.get("gained") or []
        lost = reward.get("lost") or []
        for name in gained:
            self._feed_add("reward", "%s joined your team." % name)
        for name in lost:
            self._feed_add("loss", "%s left your team." % name)
        if gained:
            self.question.setText(
                "You received %s." % ", ".join(gained)
                if not lost else
                "You traded %s for %s." % (", ".join(lost), ", ".join(gained)))

    # ---------------------------------------------------------- result gate
    def _begin_result_gate(self, result):
        """Hold on the knockout until the player acknowledges it.

        bridge.py snapshots this the instant before the engine resolves the
        end of a battle, which is the only moment the fainted state exists
        -- the engine then asks for the reward pick and resets every
        status back to "Normal" without ever returning control. So the
        order the player sees is: last Pokemon shown FAINTED, victory
        declared, click, then the reward pick.
        """
        won = bool(result.get("won"))
        self._gated = True
        self._timer.stop()

        self.result_overlay.show_result(
            won, "%s has no Pokemon left." % result.get("opponent", "Your opponent")
            if won else "You have no Pokemon left.")

        self.hotkeys = {}
        self._clear_actions()
        self.prompt_tag.setText("VICTORY" if won else "DEFEAT")
        self.question.setText(
            "You won the match." if won else "You lost the match.")
        self.actions.addWidget(ActionButton(
            "Continue", self.fonts,
            accent=T.PLAYER if won else T.OPPONENT, emphasis=True,
            on_click=self._end_result_gate))
        self.hotkeys["\r"] = self._end_result_gate
        self._fit_actions()

    def _end_result_gate(self):
        if not self._gated:
            return
        self._gated = False
        self.result_overlay.hide()
        self.question.setText("…")
        self._clear_actions()
        self._timer.start(20)

    # ------------------------------------------------------- feed bookkeeping
    def _clear_feed(self):
        while self.feed_layout.count() > 1:      # keep the trailing stretch
            item = self.feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.log.clear()
        self._log_unread = 0
        self.tabs.setTabText(self._log_tab, "Log")
        self.field_board.reset()
        self.tabs.setTabText(self._field_tab, "Field")
        self._feed_follow = True
        self._last_turn = None
        self._last_weather = None
        self._last_auto_battle = False   # per-match, like the engine's flag
        self._fainted_seen = {"player": set(), "opponent": set()}

    def _condition(self, team, in_battle):
        """Team pips, with fainted suppressed while no match is running."""
        team = team or []
        if in_battle:
            return team
        return [dict(member, fainted=False,
                     hp=member.get("max_hp", member.get("hp", 1)))
                for member in team]

    def _sync_field(self, state):
        """Point the Field board at the current state and badge the tab.

        No log of arrivals and departures: the board itself is the answer,
        and the count on the tab means you can see there are three things
        up without leaving the battle feed. Outside a live match the field
        is by definition clear.
        """
        if state.get("phase") not in BATTLE_PHASES:
            self.field_board.reset()
            self.field_strip.reset()
        else:
            self.field_board.set_state(state.get("player_side"),
                                       state.get("opponent_side"),
                                       state.get("field"))
            self.field_strip.set_state(state.get("field"))
        active = self.field_board.active
        self.tabs.setTabText(self._field_tab,
                             "Field  %d" % active if active else "Field")

    def _detect_switches(self, state):
        """Which sides have a different Pokemon out than they did last time.

        Separate from announcing it because the two halves have to happen on
        opposite sides of the sprite update: the outgoing Pokemon has to be
        photographed before show_sprite replaces it, while the card's flash
        has to be raised after set_mon or it is painted over. Returns the
        sides that changed, and records what is out now.
        """
        if state.get("phase") not in BATTLE_PHASES:
            if self._active_seen:
                # leaving a match with a switch still playing: the arena is
                # about to be reused, so don't leave a ghost standing in it
                stop_switch(self.player_sprite)
                stop_switch(self.opponent_sprite)
            self._active_seen = {}
            return []
        changed = []
        for side in ("player", "opponent"):
            name = (state.get(side) or {}).get("name")
            if not name:
                continue
            before = self._active_seen.get(side)
            self._active_seen[side] = name
            if before is None or before == name:
                continue                     # first sight, or no change
            changed.append(side)
        return changed

    def _announce_switches(self, state, switches, stills):
        """Call out each Pokemon as it comes in, and play the switch.

        A switch was only ever visible by reading the log -- and an opponent
        who switched in, fainted and switched again inside one turn left the
        card showing a third Pokemon with nothing to say the first two had
        been and gone. The feed entry is the record, the card's flash catches
        the eye, and the sprites act it out.

        Auto battle gets the feed line and the flash but not the animation:
        it is the mode for watching the match play itself quickly, and a
        quarter of a second per switch spent on something the player did not
        ask for is exactly what that mode is trying to avoid.
        """
        if not switches:
            return
        auto = bool((state.get("field") or {}).get("auto_battle"))
        for side in switches:
            card = (self.player_card if side == "player"
                    else self.opponent_card)
            label = (self.player_sprite if side == "player"
                     else self.opponent_sprite)
            name = (state.get(side) or {}).get("name")
            who = "You" if side == "player" else (state.get("opponent_side")
                                                  or {}).get("nickname",
                                                             "Opponent")
            self._feed_add("switch", "%s sent out %s." % (who, name),
                           actor=name, side=side)
            card.flash_switch()
            if not auto:
                animate_switch(label, stills.get(side), self._place_sprites)

    def _track_knockouts(self, state):
        """Call out each Pokemon as it goes down.

        Knowing you actually finished something off was previously only
        inferable from a damage number in a wall of move text, so every
        newly fainted Pokemon on either side now gets its own clearly
        marked entry in the battle log.

        Only while a match is actually running. Between rounds the engine
        still has last round's zeroed HP on record (end_battle clears status
        but not battle_stats), which had this re-announcing the previous
        round's knockouts into the new round's fresh log.
        """
        if state.get("phase") not in BATTLE_PHASES:
            return
        for side, key in (("player", "player_team"),
                          ("opponent", "opponent_team")):
            for member in state.get(key) or []:
                name = member.get("name")
                if not name or not member.get("fainted"):
                    continue
                if name in self._fainted_seen[side]:
                    continue
                self._fainted_seen[side].add(name)
                self._feed_add(
                    "faint",
                    "%s fainted!" % name if side == "opponent"
                    else "Your %s fainted." % name,
                    actor=name, side=side)

    def _track_feed_worthy_changes(self, field, phase=None):
        """Turn dividers and weather-change lines, derived purely from
        state diffs rather than new game hooks -- both are already fully
        visible in the snapshot, so there's nothing bridge.py needs to
        learn to make this work.

        `phase` gates the turn divider. Only a live battle has turns, but
        this runs on every publish, and the engine keeps a turn number on
        record after the match is over -- so the moment it changed on a
        management screen a "TURN n" rule was drawn across the feed among
        the run-summary entries. That is the stray line after all the
        matchups have ended: nothing was left behind, something new was
        being added at the wrong time."""
        # Auto battle turning on is worth an explicit line: the engine only
        # mentions it in the raw log, so from the battle screen a click on
        # the toggle looked like it had done nothing.
        auto = field.get("auto_battle")
        if auto and not self._last_auto_battle:
            self._feed_add("status", "Auto battle is on — the AI will play "
                                     "the rest of this match.")
        self._last_auto_battle = bool(auto)

        turn = field.get("turn")
        weather = field.get("weather")
        if (turn is not None and turn != self._last_turn
                and phase in BATTLE_PHASES):
            self._feed_divider(turn)
            self._last_turn = turn
        if (weather is not None and self._last_weather is not None
                and weather != self._last_weather):
            self._feed_add("status", "The weather turned to %s." % weather)
        if weather is not None:
            self._last_weather = weather

    # ------------------------------------------------------------- requests
    def _clear_actions(self):
        clear_layout(self.actions)

    def _show_request(self, request):
        self.request = request
        if self._pending_answers:
            # Only feed queued picks back to the screen that queued them. If
            # the engine has moved on to a different question it stopped
            # asking early, and the rest of the queue is stale -- sending it
            # anyway answers a prompt the player never saw.
            if request.kind == self._pending_kind:
                self._drain_pending()
                return
            self._pending_answers = []
        if request.kind == "career" and self._drive_career(request):
            return
        if request.kind == "appearance" and self._drive_appearance(request):
            return
        if request.kind == "reward" and self._drive_reward(request):
            return
        # off the reward screen: the choice is made, so the window goes away by
        # itself rather than being dismissed by hand
        if (self.compare_dialog is not None
                and self.compare_dialog.isVisible()):
            self.compare_dialog.hide()
        # ...and end_battle's "Press any key to continue" straight afterwards
        # is a keypress between finishing the swap and the next matchup that
        # exists only because the terminal version needed it
        if self._skip_next_continue:
            self._skip_next_continue = False
            prompt = self.memory.parse(request.prompt, request.recent)
            if prompt.mode == P.MODE_CONTINUE:
                self._answer("")
                return
        self.hotkeys = {}
        self._clear_actions()
        prompt = self.memory.parse(request.prompt, request.recent)
        self.question.setText(prompt.question or "Your move")
        self.fallback_entry.setVisible(prompt.mode != P.MODE_TEXT)

        if prompt.mode == P.MODE_CONTINUE:
            if self._fold_champion_fanfare(request):
                return
            self._render_continue()
        elif prompt.mode == P.MODE_CONFIRM:
            self._render_confirm()
        elif request.kind == "team_trim":
            self._render_team_multiselect(prompt, request, exact=True)
        elif request.kind == "team_keep":
            self._render_team_multiselect(prompt, request, exact=False)
        elif prompt.mode == P.MODE_CHOICES and request.kind == "move":
            self._render_moves(prompt)
        elif prompt.mode == P.MODE_CHOICES and request.kind == "switch":
            self._render_switch(prompt)
        elif prompt.mode == P.MODE_CHOICES:
            self._render_choices(prompt)
        else:
            self._render_text()
        self._fit_actions()

    # -- the reward screen drives itself ----------------------------------
    #: What each question is offering, and what the buttons should say for it.
    #: The wording matters: declining the take offer does not mean "nothing
    #: happens", it means the organiser hands you a random Pokemon instead.
    REWARD_STAGES = {
        B.REWARD_TAKE: {
            "headline": "You won — take one of theirs?",
            "subline": "Your team is not full, so nothing has to be given up. "
                       "This round is a straight pick: no swapping. Click a "
                       "name on the right, then Take it.",
            "asking": "opponent",
            "proceed": "add the one on the right",
            "decline": "let the organiser pick",
            "verb": "Take it",
        },
        B.REWARD_SWAP: {
            "headline": "You won — swap one of yours for one of theirs?",
            "subline": "Your team is full, so taking one of theirs means "
                       "giving one of yours up. Click a name on each side, "
                       "then Swap these two.",
            "asking": "both",
            "proceed": "left one out, right one in",
            "decline": "keep my team as it is",
            "verb": "Swap these two",
        },
    }

    def _drive_reward(self, request):
        """Answer the post-battle reward questions from the compare window.

        The engine asks this as three questions in a row -- yes/no, then an
        index, then another index -- which as three identical Proceed buttons
        was genuinely confusing: it was never clear which of them committed the
        swap. Both sides are selectable on the one screen instead, and the
        single Swap these two press answers all three. The two index questions
        that follow are filled in from what was selected, so they never reach
        the player at all.
        """
        kind = B.reward_prompt_kind(request.prompt)
        if kind is None:
            return False                        # not one of the four
        state = self.game_state or {}

        # An index question, with a plan already made: answer it and stay out
        # of the way. Backing out (below) clears the plan, so a request with no
        # plan means the player changed their mind and the sequence unwinds.
        if kind in (B.REWARD_PICK_MINE, B.REWARD_PICK_THEIRS):
            plan = self._reward_plan
            if plan is None:
                self._answer("9")               # the engine's "go back"
                return True
            wanted = plan["mine"] if kind == B.REWARD_PICK_MINE                 else plan["theirs"]
            self._answer(str(self._clamp_pick(request, wanted)))
            return True

        stage = self.REWARD_STAGES[kind]
        if self.compare_dialog is None:
            self.compare_dialog = CompareDialog(self.fonts, self.root, self)
            self.compare_dialog.proceed.connect(self._reward_proceed)
            self.compare_dialog.declined.connect(self._reward_declined)
        self._clear_actions()
        self.question.setText(stage["headline"])
        self.compare_dialog.open_for(stage, state.get("player_roster"),
                                     state.get("opponent_roster"),
                                     {"proceed": stage["proceed"],
                                      "decline": stage["decline"],
                                      "verb": stage["verb"]})
        return True

    def _clamp_pick(self, request, wanted):
        """Keep an index inside the list the engine is actually offering.

        The compare window is filled from the published roster, and the list in
        the prompt is the one the engine will index -- usually the same, but
        they can differ (a round is fought with fewer Pokemon than you own).
        An out-of-range answer makes ask_index re-ask, which from the outside
        looks like the swap question coming back a second time. The prompt
        carries its own list, so it is the authority.
        """
        try:
            prompt = self.memory.parse(request.prompt, request.recent)
            offered = [int(choice.value) for choice in prompt.choices
                       if str(choice.value).isdigit()]
        except Exception:
            offered = []
        # 9 is the engine's go-back sentinel, not a slot
        offered = [value for value in offered if value != 9]
        if not offered or wanted in offered:
            return wanted
        return min(offered, key=lambda value: abs(value - wanted))

    def _reward_proceed(self, _index):
        """One press. Whatever is selected on each side is the whole answer."""
        if self.request is None or self.request.kind != "reward":
            return
        picked = self.compare_dialog.picked
        self._reward_plan = {"mine": picked.get("player", 0),
                             "theirs": picked.get("opponent", 0)}
        self._answer("Y")
        # the swap is settled; the keypress the engine asks for afterwards is
        # a step between finishing it and seeing the next matchup
        self._skip_next_continue = True
        self.compare_dialog.hide()

    def _reward_declined(self):
        """Backing out, at any point. Clearing the plan is what makes a
        change of mind stick: any index question the engine asks afterwards is
        answered with its go-back sentinel rather than a stale selection."""
        if self.request is None or self.request.kind != "reward":
            return
        self._reward_plan = None
        kind = B.reward_prompt_kind(self.request.prompt)
        self._answer("9" if kind in (B.REWARD_PICK_THEIRS,
                                     B.REWARD_PICK_MINE) else "N")
        self._skip_next_continue = True
        self.compare_dialog.hide()

    #: main.py's tournament-win fanfare, printed just before it asks to
    #: continue: the congratulations line, the career title count, and the
    #: whole of Documentation/credits.md.
    CHAMPION_RE = re.compile(r"won the Pokemon World Championship", re.I)
    TITLES_RE = re.compile(r"obtained\s+(\d+)\s+World Champion Title", re.I)

    def _fold_champion_fanfare(self, request):
        """True if this Continue was the tournament-win one -- in which case
        it has already been answered.

        Winning is the one place the game asks to continue twice in a row:
        end_battle() asks once, then main.py prints the fanfare and asks
        again. In a terminal you read the fanfare in between; in a window it
        goes to the Log tab, so the second press looked like a Continue that
        did nothing. The celebration goes in the feed where it can be seen
        (and the credits get their own window at the end of the run), and
        the prompt answers itself, leaving one press.
        """
        said = "%s\n%s" % (request.prompt or "", request.recent or "")
        if not self.CHAMPION_RE.search(said):
            return False
        found = self.TITLES_RE.search(said)
        titles = int(found.group(1)) if found else 0
        self._feed_add("reward", "World Champion! You have won the Pokemon "
                       "World Championship.%s"
                       % ("  That is title number %d." % titles if titles
                          else ""))
        self.tabs.setCurrentIndex(0)
        self._answer("")
        return True

    def _drain_pending(self):
        """Send the next queued answer without touching the screen -- this
        is what makes a multi-pick confirm feel like one action instead of
        the engine's real one-index-at-a-time loop."""
        value = self._pending_answers.pop(0)
        if not self._pending_answers:
            # That was the last one, so this trim/keep screen is finished with.
            # Forget what was picked on it: the state is keyed by the roster's
            # labels, and two rounds in a row can present the *same* labels --
            # same team, same order. When that happened the previous round's
            # `committed` survived into the new screen, so `remaining` started
            # at zero and the screen opened with picks already made and no way
            # to choose or confirm. That is the between-round wedge.
            for state in (self._trim_state, self._keep_state):
                state.clear()
        request, self.request = self.request, None
        request.answer(value)

    def _answer(self, value):
        request, self.request = self.request, None
        if request is None:
            return
        # "View your pokemon" mid-switch (the engine's option 8) only ever
        # printed a block of text into the log, which is the one place the
        # player is not supposed to have to read. The answer still goes to the
        # engine -- it expects to be asked again afterwards -- but the team
        # window opens alongside it, so this option shows the same view as
        # Your Team rather than its own worse one.
        if request.kind == "switch" and str(value).strip() == "8":
            self.roster_dialog.show_side("player")
        self._clear_actions()
        self.question.setText("\u2026")
        request.answer(value)

    # -- who you are drives itself ----------------------------------------
    def _drive_appearance(self, request):
        """Answer choose_appearance() from the portrait window.

        The engine asks two questions -- a gender, then a portrait -- because
        a terminal can only ask one thing at a time. The player is shown one
        screen: the five portraits, with both gender buttons under them.

        So the gender question is never drawn. It is answered from
        `_appearance_gender`, which starts at 0 (Male) and only changes when
        the player presses the other button on the portrait screen. Pressing
        it answers the portrait question with its go-back sentinel, which
        sends the engine round its own loop to the gender question, which is
        answered again from here -- and the portrait question comes back with
        the other five. The window stays open throughout, so none of that
        round trip is visible.

        Returning False would render the question as a row of buttons reading
        "Male 1".."Male 5", which is what this exists to avoid -- so an
        unrecognised prompt inside the flow falls through to the normal bar
        rather than being swallowed.
        """
        kind = B.appearance_prompt_kind(request.prompt)
        if kind is None:
            return False
        prompt = self.memory.parse(request.prompt, request.recent)
        picks = [c for c in prompt.choices if c.kind == "option"]

        if kind == B.APPEARANCE_GENDER:
            # Read the names off the question rather than keeping a second
            # copy of APPEARANCE_GENDERS here, then answer without drawing
            # anything. Clamped, so a roster with one gender cannot ask for
            # an option that is not on offer.
            if picks:
                self._appearance_genders = [c.label for c in picks]
                self._appearance_gender = min(self._appearance_gender,
                                              len(picks) - 1)
            self._answer(str(self._appearance_gender))
            return True

        if self.appearance_dialog is None:
            self.appearance_dialog = AppearanceDialog(self.fonts, self.root,
                                                      self)
        self._clear_actions()
        self.question.setText("Choose your trainer")
        keys, back = self._split_portraits(picks)
        if back is not None:
            self._appearance_back = back
        self.appearance_dialog.ask_portrait(
            self._appearance_genders, self._appearance_gender, keys,
            self._answer, self._switch_appearance_gender)
        return True

    @staticmethod
    def _split_portraits(picks):
        """(the portraits, the go-back value) out of one numbered list.

        The engine has to print "9: Choose a different gender instead" as
        another numbered line -- a terminal has nowhere else to put it -- so
        the parser reads it as an ordinary choice and it arrived here as a
        sixth portrait with no artwork behind it.

        Told apart by *position*, not by wording: the engine accepts a
        portrait only when `0 <= answer < len(offered)`, so the portraits are
        exactly the contiguous run from zero and anything past the first gap
        is a sentinel. Matching on the label would break the moment the
        sentence is reworded.
        """
        numbered = []
        for choice in picks:
            try:
                numbered.append((int(choice.value), choice.label))
            except (TypeError, ValueError):
                continue
        numbered.sort()
        keys, back = [], None
        for value, label in numbered:
            if back is None and value == len(keys):
                keys.append(label)
            elif back is None:
                back = str(value)
        return keys, back

    def _switch_appearance_gender(self, index):
        """The other gender button. Sends the engine back round its loop."""
        if index == self._appearance_gender or self.request is None:
            return
        self._appearance_gender = index
        self._answer(self._appearance_back)

    # -- the HISTORY screen drives itself ---------------------------------
    def _drive_career(self, request):
        """Answer the HISTORY screen's own prompts, so the player never sees
        them. True when this request has been dealt with.

        The engine walks that screen as three questions -- "read the stats?",
        a competitor number, "match history?" -- which as buttons meant
        clicking Y, then a number out of fifty-six, then Y again, for every
        single competitor you wanted to look at. All four views are in the
        window at once instead, and the only real decision left (which name)
        is a click on it.
        """
        kind = B.career_prompt_kind(request.prompt)
        if kind is None:
            return False                       # not one of the three; render it
        # Closed the window: unwind the screen rather than sit on a prompt
        # nobody can see. "N" ends the loop, "0" returns to the title screen.
        if not self.career_dialog.isVisible():
            self._answer("0" if kind == B.CAREER_PICK else "N")
            return True
        if kind == B.CAREER_CONFIRM:
            self._answer("Y")
            return True
        # waiting on a click -- keep the request pending, say so, draw nothing
        self._clear_actions()
        self.question.setText("Career History is open")
        self.career_dialog.present()
        return True

    def _career_pick(self, index):
        """A name was clicked. Only meaningful while the engine is asking."""
        if self.request is not None and self.request.kind == "career":
            self._answer(str(index))

    def _career_closed(self):
        """Window shut: answer whatever is pending so the engine unwinds."""
        if self.request is not None and self.request.kind == "career":
            kind = B.career_prompt_kind(self.request.prompt)
            self._answer("0" if kind == B.CAREER_PICK else "N")

    def _auto_battle_off(self):
        """Hand control back to the player mid-match."""
        if not self.bridge.set_auto_battle(False):
            return
        self._feed_add("status", "Auto battle off — you are picking the "
                                 "moves again.")
        # Mirror the flag locally before re-rendering. set_auto_battle
        # publishes a new snapshot, but that arrives as an event on the next
        # pump tick -- so re-rendering straight away read the *old* state and
        # drew the button as still ON. It took a second click to look off,
        # which read as the first one not working.
        field = dict(self.game_state.get("field") or {})
        field["auto_battle"] = False
        self.game_state["field"] = field
        if self.request is not None:
            self._show_request(self.request)   # re-render with the new label

    def _submit_fallback(self):
        value = self.fallback_entry.text().strip()
        self.fallback_entry.clear()
        if value:
            self._answer(value)

    # -- generic renderers ---------------------------------------------------
    def _render_continue(self):
        self.prompt_tag.setText("CONTINUE")
        button = ActionButton("Continue", self.fonts,
                              accent=T.ACCENT, emphasis=True,
                              on_click=lambda: self._answer(""))
        self.actions.addWidget(button)
        # No auto-advance. A Continue prompt is deliberate: it is what holds
        # the knockout, the reward and the round result on screen long enough
        # to read, so skipping them automatically defeated their purpose.
        self.hotkeys["\r"] = lambda: self._answer("")

    def _render_confirm(self):
        self.prompt_tag.setText("CONFIRM")
        row = QHBoxLayout()
        row.addWidget(ActionButton("Yes", self.fonts, accent=T.PLAYER,
                                   emphasis=True,
                                   on_click=lambda: self._answer("Y")))
        row.addWidget(ActionButton("No", self.fonts, accent=T.TEXT_DIM,
                                   on_click=lambda: self._answer("N")))
        row.addStretch(1)
        self.actions.addLayout(row)
        self.hotkeys["y"] = lambda: self._answer("Y")
        self.hotkeys["n"] = lambda: self._answer("N")
        self.hotkeys["\r"] = lambda: self._answer("Y")

    def _render_choices(self, prompt):
        self.prompt_tag.setText("CHOOSE")
        grid = QGridLayout()
        columns = 4 if len(prompt.choices) > 6 else 3
        for index, choice in enumerate(prompt.choices):
            accent = T.ACCENT if choice.kind == "sentinel" else T.CYAN
            answer = (lambda value=choice.value:
                      lambda: self._answer(value))()
            button = ActionButton(
                choice.label, self.fonts, accent=accent,
                emphasis=(index == 0 and choice.kind == "option"),
                on_click=answer)
            grid.addWidget(button, index // columns, index % columns)
            if len(choice.value) == 1:
                self.hotkeys[choice.value] = answer
        self.actions.addLayout(grid)
        # Enter is deliberately not bound. No menu entry ends the run any more
        # -- QUIT is gone from the title screen and Quit Game from the
        # pre-battle menu, both replaced by the window's own close button --
        # but a stray keypress firing whichever button happens to be first is
        # still not something any screen wants.

    def _render_text(self):
        self.prompt_tag.setText("TYPE")
        row = QHBoxLayout()
        entry = QLineEdit()
        entry.setFont(self.fonts.body)
        entry.setStyleSheet(
            "QLineEdit { background: %s; color: %s; border: 1px solid %s;"
            "border-radius: %dpx; padding: 8px; }"
            % (T.PANEL_SUNK, T.TEXT, T.ACCENT, T.RADIUS_SM))
        entry.setMinimumWidth(260)
        entry.returnPressed.connect(lambda: self._answer(entry.text().strip()))
        row.addWidget(entry)
        row.addWidget(ActionButton(
            "Confirm", self.fonts, accent=T.ACCENT, emphasis=True,
            on_click=lambda: self._answer(entry.text().strip())))
        row.addStretch(1)
        self.actions.addLayout(row)
        entry.setFocus()

    # -- battle-specific renderers --------------------------------------------
    def _effects_from(self, prompt):
        out = {}
        for choice in prompt.choices:
            match = MOVE_LABEL_RE.match(choice.label)
            if match:
                out[choice.value] = (match.group("effect") or "").strip()
        return out

    def _render_moves(self, prompt):
        self.prompt_tag.setText("SELECT A MOVE")
        player = self.game_state.get("player") or {}
        moveset = player.get("moveset") or []
        metas = player.get("moves") or {}
        disabled = player.get("disabled") or {}
        # name -> why it cannot be used. `disabled` is the turn counter and
        # only covers one of the four reasons; this covers all of them and
        # carries the wording. See blocked_moves in GUI/bridge.py.
        blocked = player.get("blocked") or {}
        effects = self._effects_from(prompt)

        grid = QGridLayout()
        placed = 0
        for index, name in enumerate(moveset):
            if name == "Switching":
                continue
            meta = metas.get(name) or B.snap_move(name)
            why = blocked.get(name)
            is_disabled = bool(why) or name in disabled
            card = MoveCard(
                meta, str(index), self.fonts,
                effectiveness=effects.get(str(index), "") or None,
                unusable=why or ("Disabled" if is_disabled else None),
                on_click=(None if is_disabled
                         else (lambda v=str(index): self._answer(v))))
            if is_disabled:
                card.setEnabled(False)
                card.setCursor(Qt.ArrowCursor)
                card.setToolTip(why or "This move cannot be used right now")
            grid.addWidget(card, placed // 2, placed % 2)
            if not is_disabled:
                self.hotkeys[str(index)] = \
                    lambda v=str(index): self._answer(v)
            placed += 1

        if placed == 0:
            self._render_choices(prompt)
            return
        self.actions.addLayout(grid)

        extras = QHBoxLayout()
        if prompt.choice_for("0"):
            extras.addWidget(ActionButton(
                "Switch Pokemon", self.fonts, accent=T.CYAN,
                on_click=lambda: self._answer("0")))
            self.hotkeys["0"] = lambda: self._answer("0")
        auto_choice = prompt.choice_for(P.AUTO_BATTLE_VALUE)
        if auto_choice:
            on = bool((self.game_state.get("field") or {}).get("auto_battle"))
            # It switches both ways now. On is the engine's own answer (100);
            # off has no engine answer at all -- nothing in the game turns the
            # flag back down -- so the bridge writes it directly.
            extras.addWidget(ActionButton(
                "Auto battle: ON" if on else "Auto battle: off", self.fonts,
                accent=T.ACCENT if on else T.TEXT_DIM,
                on_click=(self._auto_battle_off if on
                          else (lambda: self._answer(P.AUTO_BATTLE_VALUE)))))
        extras.addStretch(1)
        self.actions.addLayout(extras)

    def _render_switch(self, prompt):
        self.prompt_tag.setText("BRING IN")
        team = self.game_state.get("player_team") or []
        grid = QGridLayout()
        placed = 0
        for index, member in enumerate(team):
            if index == 0:
                continue                     # already in battle
            fainted = member["fainted"]
            percent = round(100 * member["hp"] / max(1, member["max_hp"]))
            sub = "fainted" if fainted else "%d/%d HP  \u00b7  %d%%" % (
                member["hp"], member["max_hp"], percent)
            types = "/".join(member["types"])
            button = ActionButton(
                member["name"], self.fonts, sub="%s  \u00b7  %s" % (types, sub),
                accent=(T.type_color(member["types"][0]) if member["types"]
                       else T.CYAN),
                disabled=fainted,
                on_click=(None if fainted
                         else (lambda v=str(index): self._answer(v))))
            # Five across: a full team leaves five on the bench, so this is
            # the one row count that fits them all beside each other. At
            # three or four columns it spilled onto a second row, which
            # together with the extras row overflowed the action area and
            # made a routine switch-in scroll.
            grid.addWidget(button, placed // 5, placed % 5)
            if not fainted:
                self.hotkeys[str(index)] = \
                    lambda v=str(index): self._answer(v)
            placed += 1

        if placed == 0:
            self._render_choices(prompt)
            return
        self.actions.addLayout(grid)

        extras = QHBoxLayout()
        # No sub-captions. "Inspect your team" and "Back to battle" say what
        # they do; a second line under each restated it, and one of them
        # ("print full stats to the log") had not been true since that option
        # started opening the team window.
        for value, label in (("8", "Inspect your team"),
                             ("9", "Back to battle")):
            if prompt.choice_for(value):
                extras.addWidget(ActionButton(
                    label, self.fonts, accent=T.TEXT_DIM,
                    on_click=lambda v=value: self._answer(v)))
                self.hotkeys[value] = lambda v=value: self._answer(v)
        extras.addStretch(1)
        self.actions.addLayout(extras)

    # -- multi-select team screens -------------------------------------------
    # team_selection ("trim to fit this round's limit") and the save-game
    # keep-flow both ask the engine's real one-index-at-a-time loop; this
    # renders them as one screen with a running count and a single Confirm,
    # queuing the individual answers via _pending_answers/_drain_pending so
    # the back-and-forth is invisible.
    def _extract_int(self, text, pattern):
        match = re.search(pattern, text or "")
        return int(match.group(1)) if match else None

    def _render_team_multiselect(self, prompt, request, exact):
        state = self._trim_state if exact else self._keep_state
        signature = tuple(c.label for c in prompt.choices)
        if state.get("signature") != signature:
            # Search the prompt as well as what came before it. The limit is
            # stated in the question itself ("keep at most 6 Pokemon"), and
            # the prompt text never reaches the recent-output buffer -- so
            # this always fell through to counting the buttons instead, and
            # the sentinels (Enter 9 / Enter 10) counted as Pokemon. That is
            # where "you can keep 7" came from with a team of six.
            said = "%s\n%s" % (request.prompt or "", request.recent or "")
            if exact:
                target = self._extract_int(
                    said, r"Select (\d+) Pokemon you DO NOT need") or 1
            else:
                target = self._extract_int(said, r"keep at most (\d+) Pokemon")
                if target is None:
                    # last resort: real Pokemon only, never the sentinels
                    target = len([c for c in prompt.choices
                                  if c.kind == "option"])
            # Clamp against what the engine is *offering on this screen*, not
            # against `player_roster`.
            #
            # player_roster is a separate snapshot and it lags: during a round
            # with a 4v4 or 5v5 limit the Pokemon you benched live in
            # `unused_team`, so the published roster holds four or five while
            # the team is six. end_battle folds them home, but nothing
            # republishes the roster between that and save_game -- so the
            # clamp quietly turned the engine's "keep at most 6" into 5, and
            # a Pokemon you owned could not be kept. That is the "sometimes
            # you can only select 5" bug.
            #
            # The option list cannot lag: it *is* this prompt. Clamping to it
            # still stops the other direction -- "you can keep 7" when the
            # sentinels were counted as Pokemon.
            offered = len([c for c in prompt.choices if c.kind == "option"])
            if offered:
                target = min(target, offered)
            state.clear()
            state.update(signature=signature, target=target, committed=set(),
                        checked=set())

        team = self.game_state.get("player_roster") or []
        remaining = state["target"] - len(state["committed"])

        if exact:
            self.prompt_tag.setText("TRIM YOUR TEAM")
            self.question.setText(
                "Choose %d Pokemon you don't need this round "
                "(%d selected)" % (state["target"], len(state["checked"])))
        else:
            self.prompt_tag.setText("KEEP YOUR TEAM")
            self.question.setText(
                "Choose up to %d Pokemon to keep for next time "
                "(%d selected)" % (state["target"], len(state["checked"])))

        # Pokemon only. The parser reads "enter 9 when you are done" out of
        # the prompt as a choice too, which put a stray "you are done" tile
        # in among the team; the Confirm button below is how you finish.
        # Indexes come from each choice's own value rather than its position,
        # so filtering can't shift what gets sent to the engine.
        grid = QGridLayout()
        picks = [c for c in prompt.choices if c.kind == "option"]
        for slot, choice in enumerate(picks):
            try:
                index = int(choice.value)
            except (TypeError, ValueError):
                continue
            mon = team[index] if index < len(team) else {}
            checked = index in state["checked"]
            committed = index in state["committed"]
            label = mon.get("name", choice.label)
            sub = "kept already" if committed else (
                "selected" if checked else "/".join(mon.get("types", [])))
            button = ActionButton(
                label, self.fonts, sub=sub,
                accent=(T.ACCENT if checked else
                       (T.TEXT_FAINT if committed else T.CYAN)),
                emphasis=checked, disabled=committed,
                on_click=(None if committed else
                         (lambda i=index: self._toggle_team_pick(
                             state, i, exact, remaining))))
            grid.addWidget(button, slot // 3, slot % 3)
        self.actions.addLayout(grid)

        extras = QHBoxLayout()
        can_confirm = (len(state["checked"]) == remaining if exact
                      else True)
        extras.addWidget(ActionButton(
            "Confirm selection", self.fonts, accent=T.ACCENT,
            emphasis=can_confirm, disabled=not can_confirm,
            on_click=lambda: self._confirm_team_multiselect(state, exact)))
        # Keeping everyone is the common case at the end of a run, and
        # clicking six tiles to say so is busywork. It selects rather than
        # submits -- every tile lights up so you can see what you are about
        # to keep, and Confirm is still the only thing that commits.
        if not exact:
            picks = [c for c in prompt.choices if c.kind == "option"]
            all_indexes = set()
            for choice in picks:
                try:
                    all_indexes.add(int(choice.value))
                except (TypeError, ValueError):
                    continue
            everything = all_indexes - state["committed"]
            already_all = bool(everything) and state["checked"] == everything
            extras.addWidget(ActionButton(
                "Clear selection" if already_all else "Keep All", self.fonts,
                accent=T.PLAYER, disabled=not everything,
                on_click=lambda: self._select_all_team_picks(
                    state, set() if already_all else everything)))
        extras.addStretch(1)
        self.actions.addLayout(extras)

    def _select_all_team_picks(self, state, indexes):
        state["checked"] = set(indexes)
        self._show_request(self.request)   # cheap re-render, ~6 Pokemon max

    def _toggle_team_pick(self, state, index, exact, remaining):
        if index in state["checked"]:
            state["checked"].remove(index)
        elif not exact or len(state["checked"]) < remaining:
            state["checked"].add(index)
        self._show_request(self.request)   # cheap re-render, ~6 Pokemon max

    def _confirm_team_multiselect(self, state, exact):
        picks = sorted(state["checked"])
        state["committed"].update(picks)
        state["checked"].clear()
        self._pending_answers = [str(i) for i in picks]
        self._pending_kind = "team_trim" if exact else "team_keep"
        # The "I am done" sentinel, but only when the engine will still be
        # asking. save_game() stops as soon as its limit is reached, so a
        # sentinel queued behind a full six is never read there -- it gets
        # handed to whatever asks next instead, which silently swallowed the
        # final "press any key to confirm the results".
        if not exact and len(state["committed"]) < state["target"]:
            self._pending_answers.append("9")
        self._drain_pending()

    # ---------------------------------------------------------------- banners
    def _show_banner(self, event):
        # The Battle feed tab (right of the arena) already shows every one
        # of these permanently; a second floating toast over the arena
        # itself for the same text was pure duplication. `side` is what
        # makes the feed readable as a back-and-forth -- your moves and the
        # opponent's are colour-coded and labelled rather than interleaved
        # anonymously.
        text = ansi.strip(event["text"]).strip()
        if not text:
            return
        kind, side = event["kind"], event.get("side")
        actor = event.get("actor", "")
        # A character ability that fired mid-move already has its text
        # inside that move's entry, so it gets the on-field callout only --
        # no duplicate line in the log.
        if not (kind == "character" and event.get("nested")):
            self._feed_add(kind, text, actor=actor, side=side)
        # Character abilities also get an on-field callout -- they have no
        # move name or animation of their own, so the log alone left them
        # looking like unexplained swings mid-battle.
        if kind == "character":
            flare = self.flares.get(side)
            if flare is not None:
                flare.flare(actor, text)

    # --------------------------------------------------------------- endings
    def _show_done(self, payload):
        """Final standings, then the credits."""
        champion = bool(self.game_state.get("champion"))
        # The standings already opened by themselves the moment the final
        # table was computed, at the end of the last round. Opening them a
        # second time here -- after the credits -- just made the player
        # dismiss the same window twice. It stays one click away on the
        # Standings button if they want another look.
        titles = 0
        for row in (self.game_state.get("leaderboard") or []):
            if row.get("is_player"):
                titles = row.get("championship", 0) or 0
                break

        # Deliberately not opened here. Finishing a run and being handed a
        # window to dismiss before you can look at anything else is worse than
        # a button -- the Credits button in the top bar is there whenever you
        # want them, and it knows whether you won.
        self._credits_state = {"champion": champion, "titles": titles}

        self.prompt_tag.setText("RUN COMPLETE")
        self.question.setText("Tournament complete. Your progress is saved.")
        self._clear_actions()
        self.hotkeys = {}
        self._offer_replay()
        self._fit_actions()

    def _offer_replay(self):
        """Play again without having to close the window and start over.

        The engine restarted itself with os.execl, which replaces the whole
        process -- fine for a terminal, but it would take the window with it.
        A fresh process plus closing this one is the same thing done safely,
        and it guarantees a clean slate: the game keeps its state in module
        globals (GameSystem, the competitor table), so reusing this process
        would carry the finished run's data into the new one.
        """
        row = QHBoxLayout()
        row.addWidget(ActionButton(
            "Play Again", self.fonts,
            accent=T.PLAYER, emphasis=True, on_click=self._relaunch))
        row.addWidget(ActionButton(
            "Close", self.fonts,
            accent=T.TEXT_DIM, on_click=self.close))
        row.addStretch(1)
        self.actions.addLayout(row)
        self.hotkeys["\r"] = self._relaunch

    def _relaunch(self):
        script = os.path.join(self.root, "play.py")
        started = QProcess.startDetached(sys.executable, [script], self.root)
        if not started:
            QMessageBox.warning(
                self, "Pokemon Champion",
                "Could not start a new game automatically. Please run "
                "PLAY.bat again.")
            return
        self.close()

    def _show_error(self, payload):
        QMessageBox.critical(self, "Pokemon Champion", str(payload))
        # the run is over either way -- don't leave the window as a dead end
        self.prompt_tag.setText("RUN ENDED")
        self.question.setText("Something went wrong and the run stopped.")
        self._clear_actions()
        self.hotkeys = {}
        self._offer_replay()
        self._fit_actions()

    # --------------------------------------------------------------- input
    def keyPressEvent(self, event):
        if self.fallback_entry.hasFocus():
            return super().keyPressEvent(event)
        # Borderless has no title bar and no window buttons, so Escape has to
        # be a way out -- confirmed, because it is also easy to hit by
        # accident mid-battle.
        if event.key() == Qt.Key_Escape:
            if QMessageBox.question(
                    self, "Pokemon Champion",
                    "Close the game? Progress since your last save will be "
                    "lost.") == QMessageBox.Yes:
                self.close()
            return
        text = event.text().lower()
        handler = self.hotkeys.get(text)
        if handler is None and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            handler = self.hotkeys.get("\r")
        if handler:
            handler()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.bridge.stop()
        self.bridge.restore_io()
        super().closeEvent(event)
