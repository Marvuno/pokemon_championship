# Pokemon Championship — working notes

A Python Pokemon fan-game. A complete terminal game under `Scripts/`, with a
PySide6 interface wrapped around it rather than rewritten into it.

    python play.py        the windowed game (what players use)
    python main.py        the original terminal game (still works, unchanged)

## The one architectural rule

**The engine is not rewritten. The interface wraps it.**

`GUI/bridge.py` runs the terminal game's `main()` on a worker thread and
redirects the three things that made it a terminal program:

    print()     -> event queue -> the log panel
    input()     -> blocks the worker until the window supplies an answer
    os.system   -> 'cls' clears the log panel instead of a console

On top of that it installs *read-only* hooks on game functions so the window
knows what is being asked (a move, a switch, a menu) and can draw HP bars,
sprites and type-coded cards. Hooks snapshot state into plain dicts and then
call the original untouched, so battle behaviour, damage rolls and AI
decisions are identical to the terminal version.

Threading contract, and it is not negotiable:

    worker thread:  only ever touches queues and threading.Events
    GUI thread:     only ever reads plain-dict snapshots; never calls game code

The worker is blocked inside `input()` the whole time the player is deciding,
which is what makes snapshots safe to read without locking.

`patch_everywhere(name, original, replacement)` exists because `Scripts/` uses
`from x import *` throughout: rebinding a function in its home module is not
enough, every module that star-imported it holds its own reference.

## Traps that fail silently

Things that have already cost time here. Each one looked fine and wasn't.

- **`capture()` takes its copy before any filtering.** `Bridge._write` feeds
  the capture stack first, then filters. So the title screen and tutorial —
  which read through `capture()` — still show artwork that the log strips. If
  you change the log filter and expect the tutorial to change too, it won't.
- **A prompt reaches the log by a second path.** `Bridge._ask` puts the
  question there by hand so it can sit beside its own buttons. It bypasses
  `_write` entirely, so any log filtering has to be applied in both places —
  that is why `for_log()` exists. The `InputRequest` keeps the prompt exactly
  as the engine wrote it; the parser reads the option list out of it.
- **Escape is not a close event.** `QDialog` turns Escape into `reject()`,
  which hides through `done()` without ever sending `closeEvent`. Any dialog
  that answers a prompt needs *both* handlers or Escape strands the engine
  blocked in `input()`.
- **A dialog that owns a prompt must answer on close.** `_drive_reward` and
  `_drive_career` empty the action bar and hand the whole question to a
  window. If that window closes silently the engine waits forever. Every
  other screen that calls `_clear_actions()` immediately puts buttons back.
- **One implementation, one place.** `sprite_key` once existed twice and the
  two copies disagreed about 16 names (Alolan/Galarian forms, `Farfetch'd`,
  `(Blade Forme)`). It now lives only in `GUI/codex.py`.
- **`setScaledContents(True)` only behaves when the label is exactly
  sprite-sized.** Otherwise it stretches. `show_sprite` sets the label's own
  fixed size and callers centre it in a fixed container.
- **`_FittedArt` uses `QSizePolicy.Ignored`,** so layouts reserve no space for
  it and it overlaps its neighbours. Wrap it in a fixed-size container.
- **Recursive screen loops exhaust the C stack.** `main_screen()` used to
  recurse and produced access violations with no traceback. It is a loop now.
- **`battleground.verbose`** is on for AI-vs-AI simulation only. It enables
  roster debug prints that a real game never shows — do not measure the
  player's log with it on.

## Save file

Four slots, `Save/savefile1..4.json` (dict, `version: 1`). `savefile.select(n)`
chooses which one `save()` and `load()` mean, because the engine calls
`save(list_of_competitors)` with no path from several places.

Slot 1 is special: it falls back to the two pre-slots locations
(`savefile.json`, then the `savefile.dat` pickle) so a career from before
slots existed still loads, and `adopt_single_save()` **copies** it into slot 1
on first run rather than moving it. The original stays put as a backup — the
worst case of that migration is a duplicate, never a lost career.

**Any harness that plays a real game writes into the project folder.** The
engine saves with no way to redirect it. `Test/` harnesses must snapshot and
restore both save files, and a native Qt crash skips `atexit` — so the guard
has to be out-of-process. A test run's career has shadowed the real one
before.

## Getting changes into git

    python Tools/update_repo.py                       what would change
    python Tools/update_repo.py -m "message"          commit
    python Tools/update_repo.py -m "..." --push        commit and push
    python Tools/update_repo.py --remote <url>         connect the repository

Or double-click `UPDATE.bat` for the report. With no `-m` nothing is committed
and nothing is pushed, so any first run is safe.

**It refuses to commit a save file.** `.gitignore` excludes `savefile.json`,
`savefile.dat`, `Save/` and `Test/gui/_out/` (which holds the runner's parked
*copies* of the save), but a file committed *before* it was ignored stays
tracked — the one case `.gitignore` cannot fix. So `git ls-files` is checked
every run, and a tracked save stops the commit with the `git rm --cached` line
needed to fix it. Staged *deletions* are deliberately not treated as risky:
`git rm --cached` stages a removal of exactly those paths, and objecting to it
made the tool's own advice impossible to follow.

## Testing

    python Test/run_tests.py                 every suite
    python Test/run_tests.py pokedex swap    only matching suites
    python Test/run_tests.py --list

Suites live in `Test/gui/`; see `Test/gui/README.txt`. Headless always:
`QT_QPA_PLATFORM=offscreen`. Note the offscreen "screen" is 800x800 square,
not a real display, so anything that sizes itself from the screen behaves
differently there.

Run tests in the background and offscreen — the owner works on this machine
and a window taking over the screen interrupts them.

The runner runs each suite as a **subprocess** on purpose. `saveguard.py`
restores on `atexit`, which covers a clean exit or an exception, but a PySide6
access violation kills the interpreter outright and `atexit` never runs. A
separate process means the runner can put every save back however the child
died. It guards all six save paths, slots included — a harness starting a new
game picks a slot like anyone else. "save file put back" in the output is the
guard working, not a failure.

## What was done in this conversation

Verified by 25 headless suites plus a scripted five-battle playthrough.

**Engine fixes**
- Protean/Libero changed type *before* the Pokemon moved. `compare_speed`
  called the pre-turn adjustment for both sides before either move executed,
  so a priority attack was worked out against the new type instead of the one
  the Pokemon was still wearing. Ability phase 2 moved out into
  `on_move_used()`, fired as each Pokemon takes its turn.
- Removed `"{target} is still {status}."` — it reported the status of the
  Pokemon that had just been *attacked*, and said nothing when Normal.
- `result_announcement` returned None; `'Razor Shell'` keyed a Move named
  `"RazorShell"`; `ai_move_score` was fixed at 5 slots and raised IndexError
  on shorter movesets.
- The AI carried its own byte-identical copies of three of the engine's
  damage helpers, so correcting a formula in `damage_calculation.py` would
  have left the AI deciding by the old one with nothing failing. It now
  shares `check_attack_power`, `check_defense_strength` and
  `check_if_weather_affect_moves` (verified equivalent over 45,888
  attack/defence and 1,910 weather cases). The five helpers still defined
  inside `estimated_damage_calculation` differ for a real reason: the
  estimate has to be silent and deterministic where the engine's version
  rolls dice and prints. `check_estimated_STAB` differs from `check_STAB`
  by exactly one line — `print("STAB!")` — so separating calculation from
  narration would collapse three more of them.

**Interface**
- Career HISTORY as one interactive window, five tabs, no Continue prompts.
- Searchable Pokedex (Pokemon / Moves / Opponents) with a one-line query
  language; `GUI/codex.py` holds the data and query, no Qt.
- Compare replaces the reward screen's three identical Proceed buttons with
  one press; absorbed the old team viewer.
- Hover cards for Pokemon in battle; artwork click-to-enlarge lightbox;
  opponent-switch indicator (card flash + a named line in the feed).
- DPR-correct sprites and artwork throughout.
- Save moved to JSON; Quit/withdraw removed; "About Opponent" renamed
  "Scout Opponent"; "How They Play" renamed "Strategy".

**The log is now a plain-text transcript**
State dumps, the ASCII HP bar, bare numbers, the `--> ` caret, the
block-letter title and the ruled bracket frames are all filtered on the way
to the log. Ruled rows are rewritten as columns rather than dropped, so no
information is lost. Roughly half of what the engine prints is filtered. The
terminal build still prints everything; nothing was removed from the engine
except the one status line above.

**The swap window could strand the game**
Closing it said nothing to the engine, which sat blocked in `input()` with an
empty action bar. Both the X and Escape now decline. See the traps above.

**Switching Pokemon is animated** as a recall and then a send-out: each side's
sprite shrinks towards the middle of its own base and the replacement grows out
of the same spot, overshooting full size slightly so it lands. Two throwaway
ghost labels do the acting because the live sprite carries a QMovie whose
frames were decoded at exactly one size — scaling it would soften the pixel art
— so it is hidden for the duration and handed back at the end. `_place_sprites`
honours `_switch_busy` to keep it hidden, since state updates land there many
times a second. Auto battle gets the feed line and card flash but no animation.

**The start menu is NEW GAME / CONTINUE / HISTORY.** OPTIONS only ever printed
"feature not available yet" (Settings is the real thing, reachable any time)
and QUIT is what the window's close button is for. The swap window has no close
button either, and swallows Escape while a question is live — its own buttons
are the way out. `closeEvent`/`reject()` still decline rather than say nothing,
because a window manager can close a window whatever its flags say.

## Open

- An intermittent access violation on the worker thread during
  garbage-collection under harness load. Realistic play is clean (20/20 runs,
  4/4 playthroughs). One attempted fix made it worse and was reverted.
- `savefile.dat` is no longer in the project root though `savefile.py` says it
  stays as a backup. Harmless — never read while the JSON exists.
