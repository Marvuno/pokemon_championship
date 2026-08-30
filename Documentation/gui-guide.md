# Pokemon Champion — Graphical Interface Guide

This is a desktop front end for the game, built with PySide6 (Qt). It runs
the existing game logic in `Scripts/` without changing any of it: same damage
rolls, same AI, same tournament structure. What changes is that you click
instead of typing numbers, and battle state that used to be scrolling text is
now HP bars, chips, and a live weather-reactive arena.

---

## Starting the game

Double-click `PLAY.bat`. It checks for Python, installs the libraries the
game needs the first time (including PySide6), then asks whether you want the
graphical interface or the classic command line. Pick 1 for graphical, 2 for
command line.

From a terminal, the same two options are:

```
python play.py       graphical interface
python main.py       classic command line
```

---

## Starting a new career

A new game walks through four things in order, and then you are at the
pre-battle screen.

**Background** — six illustrated pages, `BKGD_1`..`BKGD_6`, paged with Back
and Next. Offered only if you say you are a first-timer.

**Tutorial** — five more, `TUT_1`..`TUT_5`, straight after the background if
you asked for it. Both are readers with their own Next button, so the whole
walkthrough takes one Continue at the end rather than a keypress between
every section.

**Who you are** — one screen showing five portraits with a Male and a Female
button underneath. It opens on Male; pressing Female swaps the five pictures
where they stand, and nothing else on the screen moves. All five are shown at
once, full size, because they are alternatives to compare. Only clicking a
portrait commits and moves on. The choice is written into that save slot and
is the picture your career history shows from then on. The artwork is in
`Assets/Player`.

**Your starter** — one of three Pokemon, name and typing only.

The background and the tutorial are also on the top bar, so a returning
player can read either at any time.

---

## What the interface adds

### Move cards

Each move is a card showing its type, category, power, accuracy, and the
effectiveness the game itself calculated — SUPER, RESISTED, IMMUNE — with a
type-coloured spine. Hover a card for recoil/multi-hit detail that doesn't
fit on the card face.

A move you cannot use says why, on its own row under the stats: how many
turns it is disabled for, that a powder move does nothing to a Grass
type, that a first-turn move has missed its turn, or that the move's
own condition is not met. The name and stats stay readable, so you can
judge whether it is worth waiting for. The engine always refused these
-- but only after you had spent the turn on one. The bracketed number is its keyboard shortcut, though
clicking is the primary way to play throughout.

### Live battle state

HP bars animate down rather than jumping, with type and status chips,
stat-stage changes, protection, charging moves and disabled moves shown on
each Pokemon's card. A Pokemon at 0 HP is marked FAINTED with a red outline,
not left showing a stale number.

A non-volatile status — Poison, Burn, Sleep, Fainted — sits on its own row
directly under the typing rather than beside it, where a two-type Pokemon
pushed it to the edge of the card and it read as a third type.

Stat stages are six dots: grey for unchanged, green up, red down.

### The field strip

A small permanent readout at the top of the arena, over the battlefield
rather than taking a row from it.

Weather is always there, "Clear" included, because it is up in most battles
and worth knowing at a glance. Terrain and Room boxes appear only while there
is one — a box reading "None" all match is furniture. Only *artificial*
weather counts down; the arena's own never lifts, so putting a number on it
would be a lie.

The emblems are drawn with QPainter at device resolution, not typed as glyphs
— a glyph is at the mercy of whatever font the machine has.

Weather, terrain and rooms are three separate layers: Rain, Electric Terrain
and Trick Room can all be up at once, and only members of the same layer
replace each other.

### Weather-reactive arena

The battleground's background changes with the field's weather — rain
streaks, drifting sand haze, hail, a warm sunny glow — cross-fading between
looks rather than cutting.

### Battle feed and log

The panel on the right has two tabs. **Battle** (the default) shows a
readable, colour-coded feed of what just happened — moves, abilities, status
effects, turn dividers, weather changes — built from the same data the toast
popups over the arena use. **Log** is the game's raw narration text, for when
you want to see exactly what it said; a small count badge appears on the tab
if something lands there while you're looking at Battle.

Stat changes read as the series words them — "Altaria's Defense rose
drastically! (+3)" — with the resulting stage in brackets, and they say what
actually happened rather than what was asked for, so a Pokemon already at -6
is told its Attack won't go any lower instead of that it fell again.

A character ability announces whose it is and what it does the first time it
fires in a battle, and its name alone afterwards.

### Toasts

The same events in the Battle feed also flash briefly over the arena as they
happen, so you don't have to glance at the side panel mid-fight.

### Team trimming and keeping Pokemon

When a round asks you to pick exactly how many Pokemon to leave behind, or
lets you choose which to keep between rounds, that's a proper multi-select
screen — tap to toggle, a running count, one Confirm — not the game's real
one-at-a-time prompt loop repeated on screen.

### Your Team, Scout Opponent, Match History

**Your Team** (top bar) opens a separate window with stats, ability and full
moveset for every Pokemon on your team, kept live during battle. The
opponent's side stays hidden until you have earned it — by winning the round,
or by a successful scout.

The pre-battle menu also has **Career History** — the same window the title
screen's HISTORY option opens, so during a run you can look up the champion
roll or any competitor's record. "Check History" beside it is the narrower
thing: your own record against the competitor you are about to face.

Choosing **Scout Opponent** or **Check History** from the in-game menu opens a
window rather than printing paragraphs into the log: Scout Opponent as the
competitor's artwork with the scouting report beside it, Check History as your
record against them plus the scoreline of every previous meeting.

### Career History (the title screen's HISTORY option)

One window, six tabs, all of it there when it opens:

| tab | what it holds |
|---|---|
| Opponents | every competitor, clickable, with tier and rating |
| Champions | who won each championship |
| Records | everyone who has ever won a title: titles, runs entered, overall win rate, and how often a run ends in one |
| Career | the one you picked: portrait, titles, W/L, win rate |
| Tournaments | every championship they entered and where they came |
| Head to Head | their record against everybody, hardest opponent first |

The window opens as wide as the display allows, up to 1560, because the
tables inside are wide: a Head to Head row is a name, a rating and a
full record. It is a resize rather than a fixed size, so it can still
be dragged smaller.

Click a name and the last three tabs fill in. Everything scrolls vertically —
nothing is ever laid out wide enough to need a sideways drag. You are never
asked to confirm anything: the interface answers the engine's own questions,
and closing the window returns you to the title screen.

Your own Career tab shows the portrait you chose at the start of that career.
It is stored per save slot, so two careers in two slots show two different
trainers.

Head to Head is ordered by the opponent's rating rather than by how often they
were played. A competitor who has never played says so on all three of the
owned tabs, rather than leaving the last one's record on screen.

### Auto Run (the title screen)

Pick a save slot and a number of runs, up to 100, and the game plays them
through on its own — every screen, every prompt, a real save — then hands the
title screen back. It exists to exercise the game the way a player does, for
as long as it takes to see something go wrong, and to fill out a career's
history without sitting through it.

What it does when it has to decide something:

| screen | what it answers |
|---|---|
| pre-battle menu | Battle, never the information screens |
| more Pokemon than the round allows | benches the weakest on base stats plus IVs, and only draws lots between Pokemon that genuinely tie |
| the first move of a battle | switches auto battle on, then plays |
| a forced switch | the first Pokemon still standing |
| winning a round | trades only if the loser's best beats the worst on your books, and never for a Pokemon the team already has |
| any "press any key" | a bare Enter |

It never answers the title screen itself, so a finished run gives you the
controls back rather than starting another one.

Battle and menu music are silenced for the duration, so a run of fifty
careers does not play twenty minutes of battle themes at you. There is no
sound when it finishes — the log says so instead, and the title screen coming
back is the visible sign.

Runs are saved and rated exactly as if you had played them, so a career's
history, ratings and titles all count.

### Pokedex (top bar, any time)

One search box over three sections: Pokemon, Moves and Opponents. It is
reference material only — it reads a snapshot and touches no game state — so
it is available from the title screen, the pre-battle menu and mid-battle
alike.

The search takes one line of text rather than a screen of dropdowns. Bare
words match a name, a type or an ability; anything else is `key:value` or
`stat>number`, and a leading `-` excludes:

```
fire flying              both types
tier:ultra               by tier
spd>130                  by stat (spd is Speed, spdef the other one)
move:earthquake          learns it
ability:levitate
total>550 custom:yes
water -tier:boss
cat:special pwr>110      on the Moves tab
rating>300               on the Opponents tab
```

An unknown key matches nothing rather than everything, so a typo shows an
empty list instead of the whole roster.

In the list on the left a Pokemon's typing is shown as small colour blocks
rather than words. Hovering one names them. Long names elide rather than
pushing the blocks out of sight.

A Pokemon shows its sprite, typing, tier, abilities, base stats as bars
filled to where each one sits across the whole roster, and its full move pool.
A move shows type, category, power, accuracy, PP, priority, what it actually
does in plain English, and everyone who learns it — and is marked CUSTOM if it
is one of this game's own.

An opponent reads as four sections in order: **About Them**, **Quote**,
**Ace** (the name with its typing) and **Character Ability**. The ability's
wording comes from that competitor's own `Strategy` cell in
`Data/competitors.csv` — there is no second copy of it in code to drift.

Competitor portraits are sized from the display, so they are as large as the
window can hold on a 1440p monitor and still fit a 1366x768 laptop. Clicking
a portrait opens it full size on a dimmed screen; a click anywhere puts it
away.

What it deliberately does **not** show: which competitor brings which Pokemon,
in either direction. That is what Scout Opponent's scouting roll is for, so it
is not in the snapshot at all and no query can reach it.

### Compare (the reward screen)

Winning a round opens this by itself — there is no yes/no to answer first. One
of yours sits beside one of theirs with name chips at the top of each column
to switch which pair you are looking at, and each shows typing, tier, sprite,
ability, every stat as base + IV = stat, the IV total, and the full moveset.

Each stat bar is scaled to the better of the two, so the longer bar is the
better Pokemon at that stat, and the totals are green or red by which side
wins.

One press does the whole thing. Underneath, the engine asks three questions in
a row — yes/no, then which of yours, then which of theirs — and as three
identically-labelled Proceed buttons that was genuinely confusing. Both sides
are selectable on the one screen instead, and the single press answers all
three.

| | |
|---|---|
| Fast Comparison | your weakest against their strongest |
| Swap these two | give up the one on the left, take the one on the right ("Take it" when nothing has to be given up) |
| No thanks | keep your team as it is — or let the organiser hand you a random one |

Changing your mind works at any point: declining clears the choice, so any
question the engine asks afterwards is answered with its go-back sentinel
rather than a stale selection.

Shutting the window counts as declining. This screen empties the action bar
and takes the whole question on itself, so a dismissal that said nothing would
leave the engine blocked inside `input()` with no control on screen able to
reach it. It needs catching in two places: the X arrives as a close event, but
Escape never does, because QDialog turns Escape into `reject()`.

If your team is not yet full the round is a straight pick with nothing given
up, and the window says so. Proceeding closes the window and goes straight on
to the next matchup.

### When the other side switches

The moment the Pokemon on the field changes, that side's status card flashes
its own colour for a second and a line goes into the turn feed naming who came
in — "Expert Cynthia sent out Milotic." Your own switches are announced the
same way. The first Pokemon of a match is not a switch and is not announced.

### What is no longer printed

The engine was written for a terminal, and printed its whole working state
after every turn — status, stat stages, volatile conditions, entry hazards,
charging counters, base stats, a drawn HP bar, and the caret it used to show
it wanted you to type. All of that is on screen as an actual widget now, so it
is filtered out of the log on the way through the bridge. With the drawn
artwork going the same way, that is about half of everything the engine prints
during a run. The narration — who used what, what was effective, what fainted
— is untouched. The terminal build still prints the lot.

The drawn artwork goes too. The engine rules a frame around every bracket
entry — three lines per entry, two of them pure box characters. The log is a
transcript to be read back and searched, not a screen, so the frames are
dropped and the row inside each is rewritten as its columns:

```
╔════╦══════════════════╦═══╦═════╗
║ 1  ║ Expert Cynthia   ║ A ║ 346 ║   becomes   1  Expert Cynthia  A  346
╚════╩══════════════════╩═══╩═════╝
```

Nothing that carries information is lost — only the ruling around it. The test
for a droppable line is that it contains no letters and no digits at all.

This is the log alone. `capture()` takes its copy at the top of `_write`,
before any filtering, so the title screen and the story readers still show the
artwork as drawn.

### Hovering a Pokemon in battle

Hover either sprite, or one of the little balls on a status card, and a small
panel appears with that Pokemon's four moves (colour-coded by type, with
category and power) and its six IVs, each shown over the stat it produced. A
31 is picked out in cyan.

Your own side always shows. Theirs shows only once you have earned it. The
balls are the only way to reach their *bench* mid-battle, which is most of
what a successful scout buys you.

### The top bar

From the left: the scoreboard (round, turn, both scores), then

```
Credits  Background  Tutorial  Settings  Pokedex  Standings  Your Team  –  ✕
```

Standings and Your Team are hidden until there is a game to look at — before a
run starts there are no matchups and no team, so offering them was offering
two dead ends. The rest are reference material and are there throughout.

The window is borderless, so it supplies its own minimise (`–`) and close
(`✕`), in the order a title bar would put them. Escape also closes.

### Settings

Difficulty — Normal, where every opponent plays the full scoring AI, or
Beginner, where every opponent plays the simple attacking one — taking effect
the next time you start the game. Music volume is on the same panel.

This is the only thing that decides which AI you face. Opponents used to play
simply or cleverly according to their own rating, so the weakest sixteen
always played simply whatever the setting said; the early rounds of a career
put up a real fight now.

The window is borderless fullscreen; there is no windowed mode and no size
option, so the arena and the sprites are laid out once against the screen you
actually have.

### Credits

On the top bar, not thrown up automatically. They used to open themselves the
moment a run ended, over the top of the final standings. Whether you won, and
how many titles you hold, is remembered from that moment so the closing note
still reads correctly whenever you come to it.

### Fallback text entry

Every screen has a small "or type a value" field in the action bar. It's
deliberately understated — buttons are the primary way to play — but it stays
available as an escape hatch.

---

## Requirements

Python 3.8 or newer. PySide6 (Qt for Python) for the graphical interface.
pygame and openpyxl are already required by the game.

`PLAY.bat` installs all of these for you. Manually:

```
pip install -r requirements.txt
```

---

## How it is wired up (for anyone touching the code)

```
GUI/                toolkit-agnostic pieces, usable by any front end:
  bridge.py           runs main() on a worker thread, redirects its I/O,
                      and hooks a handful of game functions to know what
                      is being asked and what just happened
  prompt_parser.py    turns terminal prompts into structured choices
  ansi.py             ANSI escape parsing for the raw log
  theme.py            palette, type colours, status maps, size scale
  codex.py            the Pokedex's data and its query language -- no Qt,
                      so the search is testable on its own. sprite_key
                      lives here: it is the one implementation

GUI_qt/             the Qt rendering layer
  main_window.py      the window: scoreboard, arena, tabbed feed/log,
                      action bar, every prompt renderer
  widgets.py          RoundedPanel base, HPBar, Chip, MoveCard,
                      CombatantCard, Banner, FieldBoard, FieldStrip,
                      ScoutCard, ActionButton
  panels.py           RosterDialog, OpponentInfoDialog, HistoryDialog,
                      CareerDialog, CompareDialog, StandingsDialog,
                      StoryDialog, AppearanceDialog, SettingsDialog,
                      CreditsDialog
  pokedex.py          the Pokedex window (three sections, one search box)
  arena.py            the weather-reactive battleground backdrop
  sprites.py          sprite loading via QMovie
  fonts.py            resolves theme.py's font stacks into QFonts
  settings.py         persistent settings via QSettings (difficulty)
```

Three redirections make a terminal program clickable: `print()` appends to the
log/feed, `input()` blocks the game's worker thread until a button is clicked,
and `os.system('cls')` clears the log. On top of that, `bridge.py` wraps a
number of game functions — `battle_setup`, `select_move`,
`switching_criteria`, `check_win_or_lose`, `move_order_and_execution`,
`UseAbility`, `team_selection`, `save_game`, `about_opponent`,
`check_history`, `choose_appearance`, `round_begin`, `scoreboard`,
`elo_rating` and others — so the interface knows what screen to show and when.
Every wrapper calls the original unchanged.

A few prompts are answered by a window rather than by the button bar. Those
are tagged with a *kind* — `career`, `reward`, `appearance` — and the window
answers the engine directly. Any such window must answer on close, by every
route including Escape, or the worker is left blocked in `input()`.

Two small behaviour changes exist, both to keep the game running rather than
to change how it plays: a missing audio file or device can no longer end a
run, and `restart()` signals the interface to relaunch cleanly instead of
calling `os.execl` over the running process.

### Artwork and scaling

Artwork is scaled to *device* pixels and stamped with the ratio (`_FittedArt`
in `panels.py`), and the animated sprites decode at device resolution too
(`show_sprite` in `sprites.py` — QMovie has no `setDevicePixelRatio`, so the
frames are scaled up and the label fits them back into its logical rect).

Two rules follow, both learned the hard way:

- `show_sprite` gives its label the sprite's own size, because scaled contents
  in a label bigger than the sprite stretches it. Callers wanting a stable box
  put the label inside a fixed-size container and centre it.
- `_FittedArt` carries a `QSizePolicy` of `Ignored` so the layout sizes the
  picture rather than the reverse — which also means a layout reserves no room
  for it. It needs the same container treatment, or the widget beside it is
  laid out straight over the top.

Qt lays out in logical pixels, so on a 150%-scaled display a portrait fitted
to a 680px label was being stretched to 1020 real pixels by the compositor. It
was that, not the source resolution, that made portraits look soft.

If the game itself raises an exception, the interface shows it in a dialog
with a copy button instead of closing silently.

### The save

Four slots, `Save/savefile1..4.json`, written by `Scripts/Game/savefile.py`.
Each holds the facts that need to outlive a run — your rating, participation,
titles, the portrait you chose, the Pokemon you kept and what was rolled for
them, and everyone's records — and rebuilds the rest from `Data/pokemon.csv`
and `Data/competitors.csv` on load, so a save is safe to open and edit by
hand.

Slot 1 also falls back to the two pre-slots locations (`savefile.json`, then
the `savefile.dat` pickle) so a career from before slots existed still loads.
The original is copied rather than moved, so it stays as a backup.
