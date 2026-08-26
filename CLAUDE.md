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

## Adding a move

Edit `Data/moves.csv`. One row, no Python.

`Scripts/Data/moves.py` is the whole move layer: the `Move` class, the
encoding rules, and the loader. It was 1,425 lines of hand-written constructor
calls and is 292 of class and reader. There is no separate loader module --
one was tried and it bought nothing: it was imported by three files, had no
circular-import reason to exist, and forced `load(Move)` to take the class as
an argument purely to hop the gap. Its *encoder* half did belong elsewhere and
lives in `Tools/moves_to_csv.py`, because the game only ever reads the table
and the only thing that writes it is that tool.

`Scripts/Data/move_text.py` is not move data and does not belong in the CSV.
It is 28 hand-written descriptions for the Pokedex, and it exists for the
mechanics that live in *code* rather than in data -- Brine doubling against a
hurt target, Metronome picking at random, Guillotine's roll. `GUI/codex.py`
generates a description from the row for the other 359 moves, which is why
that generated text can never go stale. Only add an entry when the generated
line is missing or misleading.

Thirty-one of the thirty-five columns are ordinary. `special_effect` is not -- it
holds twelve different shapes across the 387 moves, including *function
references* -- so it has four rules:

    |   one effect per entry, paired by position with `effect_type`.
        368 of 387 moves never need it.
    @   one of the 24 status functions in moves_status_condition_apply.py:
        `@Burn`, `@Confused`. The registry is built by introspecting that
        module, so it cannot fall out of step with it.
    ,   an array: `0,0,0,0,-2,0,0,0,0` is a stat-stage change. **A trailing
        comma marks a one-entry array** -- `Grass,` is `['Grass']` where bare
        `Grass` is the string. Forest's Curse is the only move that needs
        this, and it needs it badly: the handler iterates the value, so the
        string would add five types called G, r, a, s and s.
    ~   None, which three moves mean on purpose.

    Flamethrower     target_non_volatile                 @Burn
    Acid Spray       opponent_modifier                   0,0,0,0,-2,0,0,0,0
    Reign of Terror  opponent_modifier|target_volatile   0,0,0,0,0,-1,0,-1,0|@Frighten
    Defog            opponent_modifier|clear_entry_hazard   0,0,0,0,0,0,-1,0,0|~
    Haze             reset_target_modifier|reset_user_modifier   |

### The three rule columns

`power_when`, `weather_when` and `fails_unless`. These are the answer to "why
is some of a move in the spreadsheet and some of it in Python", for the part
of the answer that was never a good reason.

A *computation* has to be code: Metronome picks a move at random, Counter
reads the target's last hit, Electro Ball divides two speeds. No cell holds a
formula. But most of what was in code was not a computation at all -- it was a
**condition**, and a condition is a name. "Brine hits twice as hard below half
HP" was an `elif move.name == "Brine"` in a chain of twelve; the other three
moves in that chain had exactly the same shape. Twenty-two such branches are
gone, and the table says it instead:

    power_when     Brine          target_below_half
                   Venoshock      target_poisoned
                   Facade         user_statused
    weather_when   Thunder        Sunny:half_accuracy|Rain:always_hits
                   Solar Beam     Sunny:no_charge|Rain:half_power
    fails_unless   Dream Eater    target_asleep
                   Gigaton Hammer not_used_last_turn

`|` separates one weather's entry from the next; `:` separates the weather
from what it does. `power_when` doubles by default and takes `condition*1.5`
if a move ever wants something else.

The vocabulary is **closed and checked at load**. The names each column may
use live in `Scripts/Battle/move_rules.py` -- one small function each, in a
table -- and a row naming something that is not there is an error at startup
giving the move, the column, and every name that would have worked:

    Data/moves.csv:88 move 'Scald Burst': no power condition called
    'target_burnt'. The ones there are: target_below_half, target_poisoned,
    target_statused, user_statused

That is the whole point of a closed vocabulary over a free-text cell. Before,
a typo in a hardcoded branch was silent: the move simply never did the thing,
and nothing said so.

So: **a move reusing an existing condition is one cell and no Python.** A move
needing a genuinely new condition is one function and one dictionary entry in
`move_rules.py`, next to its siblings, and every later move gets it for free.
Same bargain as `effect_type`, which has always been a name in a cell
dispatched to a handler.

### The `remarks` column

28 of the 387 moves have behaviour written in code as well as in the table --
Metronome picks a random move, Counter reads what the target just did. The
`remarks` column says so, in the row, so the person editing the spreadsheet
finds out there rather than by surprise:

    Flamethrower    (blank -- the table says all of it)
    Metronome       in code: picks a random other move (battle_initialization.py:68)
    Earthquake      in code: could be data: double power on a target underground (...)

It was 40 before the three rule columns; those twelve now say it in a cell.

It is **generated, not typed**. `Tools/move_code_scan.py` reads the engine for
anything of the shape `something.name == "Fire Blast"`, and
`test_engine_integrity` fails when the column and the code disagree. Adding a
new `if move.name == ...` therefore breaks a test until it is written down --
checked by adding one and watching three checks go red.

It is a column but **not a constructor field**: `FIELDS` drives what `Move()`
is given, `COLUMNS` drives the CSV, and `decode_row` drops the remark. It is a
note, and the engine never reads it.

The wording matters. A remark saying **"could be data"** means the only reason
it is in code is that nobody has given it a column yet -- 7 of the 28 say
this, and they are what is left to work through if the table is ever to be the
whole truth. They are all one idea: the moves that reach a target mid-Fly,
mid-Dig or mid-Dive. The other 21 are computations, and no cell can hold a
formula.

A bad row is a load-time error naming the file, the line, the move and the
problem -- an unknown `@Name`, a mismatch between the two effect columns, a
non-numeric power, a duplicate name, or a row with data and no name (which
would otherwise be dropped in silence). `python Tools/moves_to_csv.py --check`
validates the table without touching it.

That tool also did the conversion: it wrote the CSV *out of* the old literal
and compared all 387 moves field for field, status effects by function
identity, so nothing was transcribed by hand. The fingerprint then confirmed
40 battles play identically.

## How the game speaks

`Scripts/Art/narrator.py`. Every line the battle engine says goes through
`say(text, kind, **facts)`. There were 262 bare `print()` calls; 130 of the
ones in Scripts/Battle are `narrator.say` now, and the 19 left are the
per-turn state dump, which is debug output rather than speech.

Two things this buys.

**One place decides how the game reads.** "The move failed." was written out
as five separate string literals, and two more sites said "The move failed!"
with an exclamation mark instead. They are one constant now
(`narrator.MOVE_FAILED`), so the wording and the styling are a single edit.
Those two odd sites never fire in the 40 fingerprint battles -- which is
worth knowing on its own: the fingerprint could not have caught a change to
them either way.

**Facts travel with the line.** This is the part that removed a real
fragility. `elo_rating()` worked out each match's rating change, printed it
as "Nickname: Win [+12]", and GUI/bridge.py ran `ELO_LINE_RE` over the
printed text to get the number back -- with a fall-back to print order for
when two competitors share a nickname. The engine says the number now:

    narrator.say(f"{nickname}: {result} [{sign}{amount}]", "result",
                 nickname=..., won=..., rating_change=...)

and the bridge listens. `ELO_LINE_RE` is deleted. Retuning the wording can no
longer break the interface.

`KINDS` is the closed list a line may be tagged with -- `faint`, `heal`,
`fail`, `switch`, `weather` and so on. A kind earns its place by being
something an interface would plausibly present differently, which is what
makes styling by kind possible instead of matching on ANSI escapes or on the
English. Only lines whose wording is unambiguous carry one today; the rest
are `plain`, deliberately, because a *wrong* kind would misinform whatever
styles by it.

`test_narrator` fails if anything in Scripts/Battle prints speech directly
again, or uses a kind that is not declared.

### Stat changes and character abilities

Two things the player was barely told about.

**A stat change printed its own data structure.** `Pikachu | Attack -1 |
Speed -1` was the raw contents of `applied_modifier`. `narrator.stat_change`
takes the stage list either side of the change and says what happened:

    Altaria's Defense rose drastically! (+3)
    Kingler's Speed rose sharply! (+2)
    Pikachu's Attack won't go any lower!

The last line is the part that was wrong rather than merely terse. The old
code reported what was *asked for*, not what happened, so a Pokemon already
at -6 was told its Attack fell again. Over 40 battles that happens 33 times.
The wording is the series' own -- fell / harshly fell / severely fell -- and
the resulting stage is in brackets, because "rose sharply" twice in a row
otherwise leaves the player counting.

**Abilities changed stats in total silence.** 36 sites applied a stat change
with nothing said at all: Intimidate dropped the opponent's Attack and the
log did not mention it. They all announce now. It comes to about 19 stat
lines a battle, and the transcript grew by only 12 a battle because the old
terse dumps went away.

**A non-volatile status has its own row.** Poison, Burn, Sleep and Fainted
sat on the typing row, where a two-type Pokemon pushed the status chip to the
edge of a 300px card and it read as a third type rather than as something
wrong. It is a row of its own directly under the typing now, and Fainted is
spelled out rather than abbreviated to FNT.

**A character ability said what it was, not whose or what it did.**
`Character Ability: Procrastination` in a battle where both competitors have
one does not say who just changed the rules. Now:

    * Jason's character ability: Procrastination -- priority is reversed
    * Jason's character ability: Procrastination

The explanation the first time it fires in a battle, the name alone after
that -- Trashy fires on every Poison attack, and repeating the sentence each
turn would bury the rest of the log. `battleground` is rebuilt per battle so
the "already explained" set resets itself.

`CHARACTER_ABILITY_EFFECT` in character_abilities.py holds all 52
descriptions. They were **already written down** as comments on the bodies,
where only somebody reading the source would ever see them. The trainer's own
`ability` field supplies the display name rather than title-casing the
function name, which turned `curse_of_forest` into "Curse Of Forest".

**Anything that announces has to know whether it is real.** The first cut of
this leaked: the AI scores its candidate moves by running the real ability
code against a copy, on the same phases a real turn uses, so thirteen
stat-changing abilities fire while nothing is happening. Measured at **6 of
54 announcements over six battles** -- the log telling the player "Defense
rose!" about a move the opponent never used. `stat_change` takes the
battleground and says nothing when `reality` is False, the same test
`notice()` has always made. `test_stat_reporting` walks the AST of all three
files and fails if any `stat_change` call is missing it.

`test_stat_reporting` covers both, including that every ability a competitor
holds has a description and that nothing is described that nobody holds.

None of this changed what a battle *does*: all 40 fingerprint battles have
identical scores and turn counts, and all 40 transcripts differ. That pairing
is the signature to look for after a presentation change -- and the reason
`fingerprint.json` keeps a `score` and `turns` alongside the transcript hash.

### A bug this turned up

`elo_rating()` read each match's win or loss with
`me.opponent.index(opponent)` -- three times per iteration. `.index()`
returns the *first* match, so meeting the same competitor twice in one run
would have scored the second meeting with the first meeting's result. It
reads by position now, and `test_narrator` plays a doubled opponent to prove
each meeting is scored separately.

## Adding an ability

Write the function in `Scripts/Battle/ability_effects.py`, add one line to the
registry at the bottom naming the phase it fires on. Nothing else in the
codebase needs to know it exists.

`Scripts/Data/abilities.py` used to be 1,064 lines, of which about 950 were
153 ability bodies nested inside `UseAbility` as closures -- redefined on
every call, and that function runs about 95,000 times over forty battles.
They were nested because they read six names out of the enclosing scope
instead of taking arguments. `AbilityCall` carries those six, so they are
module-level functions now and `abilities.py` is a 170-line dispatcher.

    old   12,891 firings x 153 closures = 1,972,323 function objects
    new   12,891 AbilityCall objects

The nine phases, since `abilityphase=7` says nothing on its own:

    1  switching in                 6  after dealing damage
    2  using a move                 7  after taking damage
    3  being targeted by a move     8  end of turn
    4  dealing damage               9  switching out

`REGISTRY` is the single source: the phase map is derived from it rather than
written out, and `abilities.problems()` reports a malformed entry, a phase
that does not exist, or an effect that is not callable.

### Abilities that do nothing

Two kinds, and the difference matters.

**Deliberate** -- Illuminate and Pressure act outside battle (scouting), and
Magic Guard is implemented in `hp_decreasing_modifier`. Their bodies are
`pass` with a comment saying where the real behaviour is. This is fine.

**Not deliberate** -- `KNOWN_INERT` in abilities.py. An ability a Pokemon
actually holds that has *no* registry entry does nothing at all, and nothing
used to say so: the debug read-out carried a bare
`usage.update({'Surge Surfer': 0})` line, which stopped it raising KeyError
without recording why. Surge Surfer doubles Speed on Electric Terrain and
this game has no terrain, so **Alolan Raichu, which holds it and nothing
else, plays with no ability at all** -- while `ability_text.py` tells the
player it doubles Speed. It is declared now, with the reason, and a new one
is a test failure rather than a silent gap.

### Why there is no abilities.csv

The moves table works because moves *repeat*: four moves double their power
on the same condition, six care about the same weathers. Abilities do not.
Blanking every literal and clustering the 153 bodies by shape gives **121
one-of-a-kind shapes**; only about 32 abilities share a shape, and those in
pairs. A CSV would need roughly 120 bespoke vocabularies, which is code with
extra steps and a worse place to read it.

What was worth doing instead: seven groups had **byte-identical** bodies. Six
are now one function with several registry entries pointing at it
(`_softens_super_effective` is Solid Rock and Filter, `_wakes_up_immediately`
is Insomnia, Vital Spirit and Sweet Veil). Before, fixing one of a pair would
silently miss the other. `test_ability_registry` fails if two effect
functions ever have identical bodies again.

## Terrain

`Scripts/Battle/terrain.py`, and `battleground.terrain` -- **its own slot**,
deliberately not a member of `field_effect`. In the real games weather,
terrain and rooms are separate layers: Rain, Electric Terrain and Trick Room
can all be up at once and only members of the same layer replace each other.
Terrain inside `field_effect` next to Trick Room would have made those two
mutually exclusive, which is wrong.

    Electric   Electric moves x1.3; nothing on the ground can fall asleep
    Grassy     Grass moves x1.3; the ground heals 1/16 a turn; quakes halved
    Misty      no status and no confusion on the ground; Dragon moves halved
    Psychic    Psychic moves x1.3; priority moves cannot touch the ground

Five turns each, x1.3 (which is what it has been since Generation 7; it was
x1.5 when terrain was introduced).

**The one rule that makes terrain different from weather: it only reaches
Pokemon standing on it.** Weather is in the air and touches everything.
A Flying-type, a Levitate holder, or anything half-way through Fly gets none
of it -- not the boost, not the healing, not the protection. `is_grounded`
reads all four cases, including the engine's own
`volatile_status['Grounded']`, which switching sets and Levitate clears.

Where it hooks in, all five places:

- **damage** -- a factor of its own in `damage_calculation`, next to the
  weather factor rather than folded into it. The AI's estimator gets the same
  factor, because an AI scoring moves by different rules than the engine
  resolves them by is the trap recorded above for the three damage helpers.
- **status** -- Misty and Electric refuse one outright in
  `check_move_target_non_volatile_status_effect`, and Misty refuses confusion
  in the volatile one.
- **priority** -- Psychic Terrain sets `move.accuracy = 0`, which is how
  Queenly Majesty and Dazzling already say "this does not reach".
- **end of turn** -- Grassy heals, then the terrain counts down, in
  `end_of_turn` beside the field-effect tick.
- **the interface** -- `snap_field` publishes `terrain` and `terrain_turns`
  on their own, and `FieldStrip` shows the box. It appears only when the
  state carries a terrain, so it was hidden until this existed.

Terrain arrives two ways, and they last different lengths:

    a move lays it            5 turns   (Electric Terrain and its three kin)
    the battle opens on it   10 turns   (5% chance each, so 1 battle in 5)

Four moves lay it, one row each in `Data/moves.csv` with `effect_type` of
`terrain`. Setting the terrain already down **fails**, as it does in the real
games, rather than silently refreshing its five turns.

The second way is this game's own rather than a series mechanic -- the same
idea as the arena rolling its own weather, and rolled right beside it in
`battle_setup` with one `random.choices` so the two read alike. Four terrains
at 5% each: one battle in five opens on some ground, four in five on none.
Measured over 20,000 rolls in `test_terrain`, and over the 40 fingerprint
battles it came out at exactly 8. Longer than a move's five turns because it
is the ground the battle is fought on rather than something somebody spent a
turn on -- but unlike the arena's own *weather*, which never lifts, it does
lapse, and a move can override it (and then it runs on the move's clock).

Four Pokemon learn them, each swapping one redundant slot: **Electivire**
(Rock Climb), **Sceptile** (Endeavor), **Sylveon** (Fake Tears), **Alakazam**
(Shadow Ball). That distribution is a *design choice*, not a mechanic --
there are no Tapus in this roster, so somebody had to be picked. Change the
Poke columns freely; the mechanic does not care. It is also why the
fingerprint was deliberately re-baselined: 36 of 40 battles play differently
because four Pokemon have a different move.

Still to do if you want the full set: Steel Roller (removes terrain, fails
without one) and Defog clearing terrain, both of which `fails_unless` and the
existing `clear_entry_hazard` shape already fit.

## A competitor's designed team

`Data/competitors.csv`, columns `Poke1`..`Poke6`. A cell is either a bare
species name or a name carrying the details that make it *theirs*:

    Durant
    Grimmsnarl|iv=20|ability=Prankster|moves=Bulk Up,Foul Play,Play Rough
    Pikachu|iv=60

`|` separates the name from each detail, `=` separates a detail from its
value, `,` separates moves. Whatever a cell does not pin is rolled exactly as
a bare name always was: IVs from the competitor's tier floor, one ability
from the species list, four moves sampled from its movepool. A pinned `iv` is
used as *both ends* of the roll, which is how an IV above the usual 31 can
exist at all -- Ash's Pikachu at 60 is `randint(60, 60)`.

This replaced **`Data/custom_team.csv` and `Scripts/Data/custom_team.py`**,
both now deleted. That file was a second place a competitor's team was
written down, keyed by ID, holding exactly one Pokemon each, re-read in full
for every competitor on every round -- and only it could say anything beyond
a species name. Any of the six slots can carry detail now.

`read_ace` validates at startup, so a bad cell names the competitor, the
column and every key that would have worked instead of failing mid-battle.

### The bare `except:` that was load-bearing

`team_generation` used to resolve each entry with `list_of_pokemon[entry]`
inside a `try`, and a bare `except:` assumed anything that raised must
already be a built Pokemon -- which is how the second file's objects got
merged in. Two things hid in that:

- **It was doing real work.** `team_generation` writes its results back into
  `participant.team`, so every round after the first sees the Pokemon it
  built last time, and the player's kept team arrives the same way. The
  `except` branch is what stopped those being rebuilt from the species with
  fresh IVs and a fresh moveset every round. The three cases are explicit
  now: an `Ace`, a name, or a Pokemon already built.
- **A typo took the same branch.** `Grimmsnarrl` raised `KeyError`, was
  caught, and became a broken Pokemon. It names the Pokemon it cannot find
  now, and says which file to look in.

The refactor is **fingerprint-identical**: 40 battles, same scorelines and
same transcripts. That took keying the pre-rolled IVs by the `Ace` object
rather than by its index -- `nominal_team` is prepended to the team further
down, which shifts every index, so an index-keyed lookup missed and rolled
the ace's IVs a second time. Six extra draws moved the whole random stream.
Worth knowing for anything else that reads `participant.team` by position
across that line.

## The battle context object

`Scripts/Battle/context.py`. A `Side` is one competitor's corner -- trainer,
party, active Pokemon. A `Turn` is the battle from the acting side's point of
view: `ground`, `user`, `foe`, and `flip()` for the mirrored reading that half
the ability calls want.

It exists because the engine threads the same six things through nearly every
function in a battle. Forty-one functions take eight or more positional
arguments; the effect handlers were the clearest case -- all twenty-four took
the same nine parameters and the median one used *three*, with `target_team`
used by one of twenty-four. They take `(turn, move, special_effect)` now.

Two rules for it:

- **`Side.active` is stored, never derived.** It would be tidier to return
  `team[0]` and it would be wrong: mid-switch the engine passes the Pokemon
  that *was* out while the team list already holds the replacement, and
  several call sites re-derive `user = user_team[0]` at a specific moment
  precisely because the two differ in between.
- **Nothing here copies.** A handler writing through `turn.foe.active` writes
  to the real Pokemon, exactly as it did when that object arrived as a bare
  argument.

**Done.** Every battle function that took the cluster now takes a `Turn`:
the turn loop (`move_selection`, `compare_speed`, `move_execution`,
`end_of_turn`), `move_order_and_execution`, `move_special_effect` and its
twenty-four handlers, `damage_calculation` and its three context-taking
helpers, and both ability entry points. **41 functions took eight or more
positional arguments; 3 do, and all three are data-row constructors** --
`Move`, `Competitor` and `Pokemon`, whose signatures are the shape of a CSV
row rather than battle plumbing.

Two things to know when working on it:

- **`turn.flip()` replaced argument reordering.** Forty-two ability calls used
  to say "the other side's ability" by writing the six arguments backwards
  (`UseAbility(target_side, user_side, target, user, ...)`). They read
  `UseAbility(turn.flip(), move, abilityphase=3)`. If a call looks wrong, the
  question is which way round the turn is, and that is now one word.
- **The ability bodies were not touched.** `UseAbility` and
  `UseCharacterAbility` unpack the six names from the turn at the top, so all
  153 and 52 closures still read `user`, `target`, `move` and `battleground`
  out of the enclosing scope exactly as before. Converting the signature did
  not mean converting two hundred bodies.

`turn_of(...)` remains for anything that still has the six values loose --
`switching_criteria` and `switching_mechanism` are the main ones left, and
they are switch plumbing rather than the battle cluster.

The interface hooks the engine, so `GUI/bridge.py` wraps two of these:
`move_order_and_execution` and both ability entry points. Those wrappers take
the context too. A refactor that misses them fails the playthrough suite
rather than the fingerprint, because the fingerprint plays AI-vs-AI and never
loads the interface -- which is exactly what happened here, twice.

## A prompt gets its own buttons, and nobody else's

`prompt_parser.parse` reads the prompt *and* whatever was printed just
before it, because several screens print their list first and then ask a bare
question -- the switch window lists only `8:` and `9:` inline and gets the
party from the block above it.

The risk in that is picking up a list belonging to the previous screen, and it
happened. `about_opponent` prints the opponent's team as `0:`..`5:`; the
pre-battle menu then asks its own question listing `0:`..`4:` inline. Five of
the six numbers were already claimed, so **the sixth Pokemon arrived as an
extra button** -- and clicking it answered `5` to a menu with no option 5,
which printed a complaint and redrew the bar. A button that vanished and did
nothing, and only ever with a six-Pokemon team, which is why it looked
intermittent.

The rule is **disjointness**: a block printed earlier is used only when it is
numbered differently from what the prompt lists itself. A single question
never gives two things the same number, so an overlap means two screens. A
gap rule cannot separate these -- only two plain lines sit between that list
and the prompt, fewer than the switch window has on a good day.

`test_prompt_options` holds every real prompt shape on both sides of it.

## The engine's own rules

Three invariants, one suite: `Test/gui/test_engine_integrity.py`. Each of
them was broken, and each break was invisible from inside a single battle.

**A battle leaves the move table as it found it.** `list_of_moves` holds one
Move per move, shared by every Pokemon in every battle, and the battle writes
its per-use working state onto whatever Move it is handed -- damage,
accuracy, whether the hit was super effective, and for an interchange-type
move its very type. Almost everything copies first. `ai_switching_mechanism`
did not: scoring candidate switches passed the shared entries straight to the
damage estimator. Twelve battles left 211 of 387 moves carrying stale
effectiveness flags and had permanently retyped one move. The rest of the
damage followed from there -- a Flash Fire hit set a move's damage multiplier
to 0 *for everyone, permanently*; a move used into a Double Team dropped from
100% to 8% accuracy and stayed there; Iron Fist took Mach Punch from 40 power
to 99 in five uses. **Anything handed to `estimated_damage_calculation` or
`damage_calculation` must be a copy.**

**A seed replays a battle.** `multi_strike_move` drew from `np.random`, which
`random.seed()` does not touch, so the engine ran on two independent
generators and seeding one reproduced nothing. It uses `random.choices` now,
and numpy is no longer imported anywhere in the game. Without this no engine
change can be checked by playing the same battle before and after it, which
is the only way any of the above was found.

**An ability guard has to be able to fire.** `pokemon.ability` is a *list*.
Four guards compared it to a string -- `if pokemon.ability != 'Magic Guard'`
-- and a list never equals a string, so all four were permanently true and
the abilities behind them did nothing: Levitate (13 Pokemon, all grounded and
taking Ground moves and Spikes), Clear Body, Hyper Cutter, Magic Guard. Use
`has_ability(pokemon, "Levitate")` from `Scripts/Battle/constants.py`. The
sandstorm guard failed differently, `any(a not in pokemon.ability for a in
[...])`, which is true unless the Pokemon holds *every* listed ability.

**And a guard has to be able to *not* fire.** The same trap, one step along,
in the only two abilities that *write* to that list. Mummy and Trace each
carry a list of abilities they must leave alone -- the ones that *are* the
Pokemon rather than something it is holding -- and both wrote it as
`call.target.ability not in ('Stance Change', 'Disguise', ...)`, comparing
the whole *list* against a tuple of strings. A list is never in a tuple of
strings, so both exclusion lists were permanently satisfied and both
abilities did exactly what they exist not to do: Mummy overwrote Aegislash's
Stance Change and Mimikyu's Disguise, and Trace copied Illusion and
Imposter. They read `has_ability(call.target, *MUMMY_PROOF)` now.

Mummy then had a second fault that was not silent at all, only slow:
`call.target.ability = "Mummy"`, a bare string where every other site in the
engine holds a list. It surfaced as a **`TypeError` 4,000 battles into a
rating simulation** -- the `infiltration` character ability does
`user.ability + ['Dead Calm', 'Mold Breaker']`, and str + list raises. Before
that it was quietly wrong in a worse way: `random.choice(pokemon.ability)` in
`choose_pokemon` picks from a string *by letter*, so a mummified Pokemon
could come out of a round holding an ability called `m`.

Trace had the aliasing trap as well, both ways: it assigned the target's list
itself rather than a copy, so the two Pokemon shared one list and a character
ability appending to one wrote into the other's; and it restored from
`default_ability` by assigning it, where `switching.py` and `end_battle` both
take `list(...)` of it. Assign `list(...)`, never the list.

`test_engine_integrity` fires both abilities against each protected ability,
and walks the AST of `Scripts/Battle`, `Scripts/Data` and `Scripts/Game` to
fail on any assignment of a bare string to a Pokemon's `ability`. The fix
changed 1 of the 40 fingerprint battles -- these two abilities are held by
few Pokemon, which is why nothing noticed for so long.

Two formulas were no-ops for the same kind of reason: Adaptability was
`math.floor(1 / 1.5 * 2)`, and floor(1.333) is 1, so the ability granted
nothing; Enragement multiplied its power by the number of fainted allies,
which is zero when nobody has fainted.

`modifierChart` rows are `_StageRow`, which clamps the stage index. Stages
0..+6 are the first seven entries and -1..-6 are read off the end by negative
indexing -- elegant, and silently *backwards* one step outside that range,
where +7 used to return 0.25 instead of 4.

**State belongs to the thing it is about, and has to be reset with it.** A
second sweep found the same shape in five more places, all of them fixed and
all of them in the suite:

- `end_battle` cleared the *protagonist's* entry hazards and barriers only,
  inside the per-Pokemon loop. A competitor's Stealth Rock and Reflect
  outlived the battle that set them.
- It also set `previous_move = None`, where a Pokemon starts it as `""`. The
  counter moves guard with `if type(previous_move) is not str`, which None
  slips straight through, so a Counter on the first turn of the next battle
  raised `AttributeError`. That guard now asks whether the thing looks like a
  move rather than whether it isn't a string.
- Switching restored `type` and `ability` by *assigning the default list*,
  making the two names one list -- so `target.type += [typing]` from a move
  like Forest's Curse rewrote the typing the Pokemon was supposed to revert
  to. Restore copies, and extend with `type = type + [x]`, never `+=`.
- `check_move_heal_team_status` set every team-mate's status to "Normal", and
  Fainted lives in that same field -- so a team status heal *revived the
  dead*, on 0 HP, and stopped `check_win_or_lose` from ever seeing a wipe.
- `user_turn_in_battle_stats` filtered disabled moves with `if k > 0` where
  `k` is the move's *name*. Comparing a string to 0 raised `TypeError` on
  every turn, swallowed by the enclosing `suppress` -- which also meant
  everything after it in that block was skipped every turn.

Two more of the same family, both about what the player is told rather than
what happens: stat changes were announced only `if sum(applied_modifier) > 0`,
so every debuff landed in silence, and `("Poison" or "Steel") not in
user.type` is just `"Poison"` -- Python takes the first truthy operand -- so
Baneful Bunker poisoned Steel types.

## A turn's state, and what goes stale in it

Four bugs of one shape, found together. Each is something that was true when
a turn started and not by the time it was read.

**The next turn's active Pokemon.** `end_of_turn` built the following turn
from its own `player`/`opponent` locals, and only the *fainted*-switch loop
reassigned them. So anything else that replaced `team[0]` during the turn --
a forced switch from a character ability -- left the next turn running with
the Pokemon that had gone as its `active` while the team already held the
replacement, and **the replacement executed the move chosen for the one that
had left**: 14 moves in 60 battles. It derives both from `team[0]` now.
`Side.active` is still stored rather than derived on purpose; a turn
*boundary* is simply not the mid-switch moment that rule is about.

**A charge nobody could finish.** `check_volatile_status` blocked a move but
left `charging` standing, so a Pokemon that fell asleep half-way through Fly
stayed *semi-invulnerable* for the rest of the battle -- untouchable, and
doing nothing. Yawn into Fly was the reliable way to see it. An interrupted
two-turn move is cancelled now, as in the real games.

**An ability that fired per strike.** `UseAbility(phase=5)` sits inside the
multi-strike loop, which is right for Rough Skin and wrong for the absorbing
abilities: Water Absorb heals a quarter of maximum HP *each time*. Water
Shuriken hits up to five times, so it reported 0 damage -- correctly -- and
refilled a nearly-fainted Pokemon to full. A move the target is immune to now
stops striking.

**"Did no damage" is not "never connected".** The two were the same flag, and
the effect handlers sit behind it, so a U-turn whose damage was reduced to
nothing by an ability did not switch out and the player was left standing
there. The type chart is what decides whether a move connected at all: a real
immunity is 0x.

## The phase that runs before the order is decided

`ORDER_PHASE` (10), fired from `compare_speed` after `speed_adjustment` and
before the comparison.

Phases 1..9 all happen once a Pokemon is already taking its turn, which is
too late for an ability whose entire job is to decide *when* the turn is
taken. Measured: `compare_speed` read Barraskewda at **339** every single
turn while Swift Swim doubled it to 678 immediately afterwards, and the next
turn's stat rebuild threw that away. Swift Swim did nothing. Neither did
Prankster, Chlorophyll, Slush Rush, Gale Wings, or Jason's Procrastination --
five Pokemon abilities and a character ability, all silently inert.

They were on phase 2, which used to fire in `pre_move_adjustment` -- before
the comparison, so they worked. Phase 2 moved into `on_move_used` so Protean
and Libero would change type as their Pokemon actually moved rather than
before the turn. That was right for those two and wrong for these six, which
is why this is a phase of its own rather than phase 2 moved back.

Nothing compounds: `move_selection` rebuilds `battle_stats` from
`nominal_base_stats` at the top of every turn, so the doubling applies to one
comparison and is gone.

After the fix, the same battle: Barraskewda at **678** in the comparison, and
Marvuno's side moving first on 11 turns out of 11.

## Running a move twice

`battleground.encore_move`, read once at the end of
`move_order_and_execution` -- the only place that knows a move has finished.
**Wizardry** sets it, to a move drawn at random.

**Overloaded does not.** It is an extra *strike* (`multi[1] += 1`), inside the
move's own execution, like Double Hit. Running the whole move again was a
different thing entirely: it took a second slot in the turn, so the holder
appeared to move twice and the order came out wrong.

The engine only honours an encore once the move has actually worked, which
the ability cannot know when it fires:

    fail            missed, refused, or hit an immunity
    name Switching  swapping out is not a move to follow up
    charging set    committed to Fly or Dig rather than landing anything;
                    eligible on the turn it comes down instead

Without those it fired on misses and on switches, and the log filled with
moves nobody had chosen.

`encore_running` is not belt and braces. The repeat goes through the same
code path, so the ability fires again on the way and would queue another; a
Wizardry holder would take its turn until the recursion limit stopped it.

`NO_SECOND_HELPING` in character_abilities.py is what may not be repeated:
switching, Metronome (it would recurse), the two-turn moves (a repeat starts
a fresh charge on top of the one just committed to), and the protective moves
(already up, and in the series they fail on consecutive use).

## Saying why a move cannot be used

`blocked_moves()` in GUI/bridge.py. The engine has always refused these four
-- `move_fail_checklist_before_execution` is the list -- but only *after* the
player spent a turn on one, and the card just went grey with no explanation.
The same four are worked out ahead of the turn so the card can name the
reason: disabled and for how long, a powder move against a Grass type, a
first-turn-only move after the first turn, and the move's own `fails_unless`
condition.

The wording lives in `FAILURE_LINES` beside the conditions, so the log and
the card read from one source -- phrased as a *reason* rather than an event,
since it now has to make sense both after a wasted turn and before one.

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
- **`setFixedWidth` does not reserve space on an `Ignored` widget, and
  `ElidedLabel` is `Ignored`.** Same trap as `_FittedArt`, one level quieter:
  the widget *draws* at its fixed width, because `QWidget::setGeometry` clamps
  to its own minimum, but it reports 0 to the layout, so the layout advances
  past it by nothing. The career path rows stepped by the arrow alone and drew
  six opponent names on top of each other. `setSizePolicy(Fixed, ...)` after
  `setFixedWidth` is what makes the drawn slot and the reserved slot the same
  slot. The bare `Ignored` default is still right where a long name must not
  widen its row — the Pokedex rail, and `_tail_label`, which wants to expand
  into the slack and elide rather than push the row past the window.
- **A detached widget is a window.** `clear_layout` hides before it unparents,
  because `setParent(None)` makes a widget top-level and a top-level widget is
  a window -- a bare label on the desktop with no frame and nothing in it. Qt
  usually hides on reparent by itself; "usually" was worth about six little
  empty windows a battle. `Test/gui/playthrough.py` now counts visible
  top-level widgets that are not one of the real dialogs and fails on any,
  which is what a stray pop-up looks like from the inside on any platform --
  offscreen included, where nothing reaches a real desktop to be seen.
- **Recursive screen loops exhaust the C stack.** `main_screen()` used to
  recurse and produced access violations with no traceback. It is a loop now.
- **`battleground.verbose`** is on for AI-vs-AI simulation only. It enables
  roster debug prints that a real game never shows — do not measure the
  player's log with it on.

## The field strip, and the three field layers

`FieldStrip` in `GUI_qt/widgets.py`, sitting inside the arena at top centre.

**Only the weather box is always there**, "Clear" included, because weather
is up in most battles and "no weather" is worth knowing at a glance. The
Terrain and Room boxes appear only while there is one: a box reading "None"
for a whole battle is furniture, and this strip sits over the arena where
every pixel is the battlefield.

The header bar no longer carries a WEATHER column. The strip says the same
thing with an emblem and a countdown, and the duplicate was taking width
from the buttons.

**It is an overlay, not a row.** The field readout was once a strip of chips
*under* the arena; that was moved into its own tab precisely to give the arena
back the height (see `FieldBoard`). Putting it back as a layout row would undo
that. It is a child of the arena in grid cell (0, 0..1), aligned top-centre --
between the opponent's card at top-left and their ability flare at top-right
-- so it costs the battle view no height at all. The Field *tab* still owns
the per-side detail: screens, hazards, who set what, turn counts.

**Three boxes, never one.** In the real games weather, terrain and rooms are
*separate slots*: Rain, Electric Terrain and Trick Room can all be up at once,
and only members of the same layer cancel each other. Terrain is a third slot
alongside the other two, never a value inside either -- putting it in
`field_effect` next to Trick Room would make terrain and Trick Room mutually
exclusive, which is wrong.

The terrain box **appears on its own** the moment the published state carries
a `terrain` key. This game has no terrains yet, and a box reading "None"
forever would be furniture, so until then it stays hidden. Adding terrain to
the engine lights it up with no interface change.

The emblems are **drawn**, not typed. `theme.WEATHER_GLYPH` held ☀/☂/❄ for
exactly this job and was never used by anything -- and a glyph is at the mercy
of whether the font on the machine carries it. `field_emblem()` paints each
one with QPainter at `size * devicePixelRatio`, the same way the sprites stay
crisp.

Only the *artificial* weather counts down. The arena's own weather never
lifts, so putting a number on it would be a lie -- `weather_artificial` is
what tells the two apart.

## Minimise

The window is frameless (`Qt.FramelessWindowHint`) and fixed to the screen
size, so it has no title bar and has to supply its own controls. The top bar
carries `–` then `✕`, in the order a title bar would put them. Escape still
closes.

`ActionButton` now keeps its `title` as an attribute. It was previously
readable only by digging the child QLabel out of the widget tree, which meant
nothing could tell "Play Again" from "Close" -- and `Test/gui/soak.py`'s list
of buttons a crash-sweep must never press was silently matching none of the
game's real buttons.

## Starting a career

`choose_appearance` in `start_interface.py`, between the name and the
starter. Two numbered questions -- a gender, then one of five portraits from
`Assets/Player` -- so the terminal build works unchanged, and
`AppearanceDialog` recognises them and shows the pictures instead of five
buttons reading their filenames. Tagged `appearance`, the same mechanism
`history_screen` uses (see `APPEARANCE_PROMPTS`).

**The gender question is never drawn.** The window shows one screen -- the
five portraits, with both gender buttons under them -- and answers the gender
question from `_appearance_gender`, which starts at 0 (Male). Pressing the
other button answers the portrait question with its go-back sentinel, which
sends the engine round its own loop to the gender question, answered again
from here, and the portrait question comes back with the other five. The
window stays open throughout, so none of that round trip is visible.

**Nothing on that screen may move when the gender changes.** The five frames
are built once at a fixed size and only their pixmaps and captions change;
the gender buttons are built once and only recoloured, which is what
`ActionButton.set_accent` is for. `clear_layout` and a fresh row would work
and would also make the row jump. `test_batch` compares every widget's
geometry either side of a switch.

Only clicking a portrait ends the screen. It is written to the save and shown
in that slot's career history for good, which is why the window refuses
Escape -- the engine loops on the question, so there is no answer that means
"not yet".

The portrait reaches the career screen through `character_art()`, which is
the one place a competitor's picture is resolved. The player's is the only
one that comes from `Assets/Player` rather than `Assets/characters`, and the
only one that is per *save slot* rather than per competitor.

This replaced an age in the protagonist's description. An age is either
wrong immediately or has to be incremented on a schedule nothing in the game
tracks.

## The background and the tutorial

Two readers, not one. `StoryDialog` takes its `pages`:
`BACKGROUND_PAGES` is `BKGD_1`..`BKGD_6`, `TUTORIAL_PAGES` is
`TUT_1`..`TUT_5`. They were a single five-page sequence, so a returning
player who wanted a rules reminder had to page past the lore to reach it.

`on_finish` makes it a **guided** reader, which is how a new player meets it:
the last page's Next reads Continue, and every way out -- that button, the
Close button, Escape, the window manager -- reports exactly once. It has to,
because the engine is blocked on a keypress behind it. Same trap as the swap
window.

`bridge.py` swallows the pauses inside `backstory()` and `tutorial()` by
stubbing `builtins.input` for the duration. The tutorial pauses four times
between its sections -- reasonable for a terminal that would otherwise scroll
the text away, but here each one arrived as a Continue button stacked over a
reader the player had already paged through. One keypress for the whole
walkthrough now, at the end.

Both are pinged through state (`show_story`, `show_tutorial`) and the engine
runs them back to back, so **both pings can land before either reader is
closed**. `_guided_tutorial` remembers that the second is owed rather than
opening it over the top of the first.

## The top bar

    Credits  Background  Tutorial  Settings  Pokedex  Standings  Your Team  –  ✕

Credits and Story used to be a row of buttons on the title screen, which
meant the lore became unreachable the moment a run started. They are all
reference material -- they read a snapshot and touch no game state -- so
there is no reason for them to be somewhere you have to leave a battle to
find. Standings and Your Team are still hidden until there is a game to look
at.

`ActionButton.set_title` changes a button's caption in place, keeping
`self.title` in step -- that attribute is what tells one button from another.

## Screens that rebuild on every state update

`_apply_state` runs on every battle-state publish, several times a second,
and hands the roster to `RosterDialog.refresh` and the standings to
`StandingsDialog.refresh`. Both used to rebuild their whole widget tree
whenever they were visible -- which is precisely when the player has them
open. Both now compare a signature first and rebuild only when something
they draw is actually different. Measured over one playthrough with both
windows open: 85 roster refreshes produced 34 rebuilds, 86 standings
refreshes produced 13.

Anything else added to that path wants the same guard. The cost is not just
time: every rebuild produces a drift of detached widgets, and detached
widgets are how this project grows windows it did not ask for (below).

## No sound, and no windows, in a test run

`Scripts/Art/music.py` goes silent when `POKEMON_MUTE` is set **or** when
`QT_QPA_PLATFORM=offscreen` -- which every harness here already sets. So a
suite is silent because it is a suite, with nothing to remember per harness.
Both `music()` and `sound()` return early *and* SDL is pointed at its dummy
audio driver, because a machine playing twenty minutes of battle music
during someone's meeting is not a bug anyone wants to debug twice.

The mixer is started on its own, not through `pygame.init()`. `pygame.init()`
starts display, font and joystick as well; the display one brings up SDL's
video stack, which is a window system's worth of machinery for a game that
draws through Qt -- and SDL owns any window it decides it needs. Dropping it
took `import Scripts.Art.music` from 1950ms to 1081ms.

`PYGAME_HIDE_SUPPORT_PROMPT` has to be set *before* `import pygame`. It was
set after, so the banner still printed -- and with the interface installed,
`print()` is the game log, so "Hello from the pygame community" was landing
in the player's battle transcript.

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

### The deep sweep

    python Test/gui/soak.py <root> <out> 1 220

`Test/gui/soak.py` plays a career to its end while opening every window the
player can open and pressing everything inside, and checks the game's own
invariants on every tick -- team sizes, HP inside bounds, ratings above zero,
an opponent team shown before it was scouted. It is **not** in `run_tests`
(it is not named `test_*`): it takes minutes and is a manual sweep, not a
regression check. Three careers: 5 battles each, ~285 presses each, no
exceptions, no strays, no broken rules.

Four things it needs to do that are not obvious, each of which made it report
a clean pass over nothing:

- **`findChildren(QPushButton)` finds almost nothing.** The game's controls
  are `ActionButton(RoundedPanel)`, `Chip(QLabel)` and `_ClickableLabel`.
  None of them is a Qt button.
- **Duck-typing on `.click()` is not enough either.** A QLabel subclass that
  handles `mousePressEvent` has no `click()` to call -- it has to be clicked,
  with `QTest.mouseClick`.
- **A freshly shown dialog has not laid itself out.** Its children are not
  visible yet, so the sweep must `processEvents()` first.
- **`_open_settings` ends in `dialog.exec()`,** which is modal: it spins its
  own event loop and does not return until the dialog closes, so calling it
  from the harness timer wedges the whole run. The harness builds that dialog
  itself and `show()`s it.

And one it must not do: **never press "Play Again".** It calls
`QProcess.startDetached`, so a sweep pressing it leaves real game processes
running on the machine. One process is one career by design -- the finished
run's module globals must not reach the next one -- so several careers means
running the harness several times, not looping inside it.

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

## The game is still random

Nothing in the game seeds the random number generator, so every real game is
different -- Python seeds from the OS at startup. "Deterministic from a seed"
means only that *if* a harness fixes the seed it gets the same battle back,
which is a property every generator has and is what makes a before/after
comparison possible at all. What was broken was that fixing the seed *did
not* reproduce the battle, because a second generator (numpy's) and two
hash-ordered iterations were feeding it as well.

The two `random.Random(n)` instances in `GUI/wallpaper.py` and
`GUI_qt/arena.py` are deliberate and cosmetic -- a stable wallpaper and a
stable arena layout -- and they hold their own generator, so they take nothing
out of the game's stream.

## Changing the engine safely

    python Test/gui/fingerprint.py <root> <out>            record behaviour
    python Test/gui/fingerprint.py <root> <out> --compare  did it change?

Forty battles from a fixed seed, hashed transcript and scoreline each. Two
runs of the same engine produce the same file, so `--compare` answers "did
that change what a battle does" for any edit -- including edits meant to
change nothing. Every optimisation below was landed by recording a baseline,
making the change, and getting IDENTICAL back.

It only works because a seed replays a battle, which took three separate
fixes: numpy's generator (`multi_strike_move`), unsorted set iteration in
Metronome's move list, and `list(set(...))` in the `infiltration` character
ability -- the last one mattered because `UseAbility` walks the ability list
in order and applies each in turn, so two abilities writing the same field
resolve by their position, and set order is salted per process.

**Copying: `fast_copy`, not `deepcopy`.** `Scripts/Battle/fastcopy.py`. The AI
copies a Pokemon and a Move for every candidate move it scores, every turn,
and `copy.deepcopy`'s generic machinery cost more than these objects are
worth. Measured: a Move 35.6us -> 8.6us, a Pokemon 56.2us -> 14.3us, and a
battle **130ms -> 50ms**. Behaviour bit-identical by fingerprint.

Three things it must keep doing, each of which broke an attempt at it:

- **Keep the memo.** Two attributes pointing at one list have to still point
  at one list. The engine aliases: switching hands a Pokemon its own
  `default_type`, and `previous_move` holds a live Move.
- **Treat callables as atomic**, as deepcopy does. A Move carries a callable
  in `special_effect`; `object.__new__` on a function raises.
- **Recurse into objects.** `Pokemon.previous_move` is a Move, not a string,
  and a shallow copy shares it -- which the AI then mutates while scoring.

The atomic check is inlined into the list and dict loops rather than left to
the recursive call: almost everything in these containers is a number or a
string, and one Python call per element was most of the total cost.

**Copy once, not once per candidate.** `ai_switching_mechanism` accounted for
79% of all copying, and most of that was the *protagonist's* moveset being
copied afresh for each of six candidates -- the same moves, six times over.
They are copied once outside the candidate loop now, which is exact rather
than approximate for a specific reason: `estimated_damage_calculation` writes
three fields to the move it is handed and no more (`type`,
`super_effective`, `not_effective`), and the last two are overwritten at the
top of every call before anything reads them. Only `type` -- which an
interchange-type move rewrites -- carries over, so only `type` is put back
between candidates. 2,503 copies a battle down to 1,782, fingerprint
identical. If the estimator ever starts writing a fourth field, that reset
list has to grow with it.

## The save slots, and what has been ruled out

Reported: finish a career in slot 2, choose Play Again, and the other slots'
histories cannot be reached. Not reproduced yet. What has been checked, so
nobody checks it twice:

- **The engine's slot handling is correct.** `select(n)` + `load()` round-trips
  between careers any number of times, in any order, loading the right one
  every time. `savefile.slots()` reads the four files from disk on every call,
  so the menu cannot go stale. `adopt_single_save()` is properly guarded --
  it only copies the pre-slots save when slot 1 is *empty*.
- **The career window re-opens.** `champion_roll` publishes `career_open=True`
  at the start of every visit and `history_screen` publishes False in a
  `finally`, which clears the interface's `_career_shown` latch, so a second
  and third visit present the window again. `test_history_slots.py` covers it.
- **Finishing a run does not damage the other slots.** `probe_slot_survival.py`
  plays in one slot under saveguard and compares all four files by hash.
- **Play Again starts a fresh process** (`QProcess.startDetached`), so no
  module global from the finished run can reach the new one.

What would narrow it down: whether the slot is missing from the list, present
but showing the wrong career, or present with the window refusing to open.

## Simulations

    python Test/ai_simulation.py            per-Pokemon win rates
    python Test/ai_rating_simulation.py     what each competitor's rating is worth

The second one is new. Every competitor except the player plays every other
ten times -- 16,530 battles, about 17 minutes across 12 cores -- and each
result moves both ratings by the engine's own formula. Teams are always
rolled from the competitor's *shipped* rating, never the one they are
climbing to, or a competitor who got ahead would field better Pokemon and get
further ahead: a feedback loop measuring itself. Because of that, outcomes do
not depend on the evolving ratings at all, which is why the battles can run
in a process pool and the rating arithmetic can be replayed afterwards in
schedule order -- the same numbers a strictly sequential run would produce.
`--cache` keeps the raw results so the report can be recomputed without
replaying the battles.

It reports two ladders, and the difference between them is the finding.
Starter protection -- the `+1` that softens a loss in `elo_rating()` -- has
no equilibrium: at an even 50% win rate a competitor still gains +1 per
win/loss pair, at rating 1 and at rating 750 alike. Over 570 matches that is
about +280 of inflation on everybody. So the report also runs the formula
with the cushion off, and *that* column is the one to read as "what this
roster is worth".

Results in `Documentation/ai_rating_simulation.md`.

### What the rating simulation cannot tell you

**Both sides of an AI-vs-AI battle use the smart AI**, whatever they are
rated. `move_selection` reads `SMART_AI_RATING` only in its `else` branch --
the one where a human is playing:

    if battleground.verbose:                    # AI vs AI: both smart
    else:                                       # a human: rating decides

So no amount of that simulation says anything about the dumb AI, and
comparing its low-rated competitors against its high-rated ones compares
*teams*, not AIs. That inference was drawn from this data once, and it was
wrong; `Test/ai_head_to_head.py` exists because of it.

    python Test/ai_head_to_head.py

That harness holds everything else equal -- both sides field identical copies
of one randomly drawn team, at the same rating, with their character
abilities cleared -- so the only difference is which function picks the
moves. Every team is played twice with the sides swapped, and a smart-vs-smart
control band proves the harness itself is symmetric before any result is
read. Teams are drawn at five ratings, because the answer turns out to depend
on the team.

The answer: **overall exactly 50%**, but 42.6% with rating-20 teams and 53%
with rating-300-and-up ones. The smart AI is a liability with a weak team and
worth about three points with a good one.

Three arms, because the obvious explanation was wrong. The smart AI spends
12-15% of its turns switching against the dumb AI's 2%, so switching looked
like the cause. Removing it entirely moves the weakest band from 42.6% to
43.6% (+/- 2.3) -- **nothing**. Restricting it to the dumb AI's rule does not
help there either. Its switching is roughly break-even everywhere: the wasted
turns and the better matchups cancel.

What is left is move *ranking*, and there is a specific suspect in
`smart_ai_select_move`:

    ranked = sorted(ai_move_score,
                    key=lambda x: (-ai_move_score[x][0], -ai_move_score[x][3]))

Factor `[0]` is a small integer "priority" nudged up and down by a dozen
conditions, and it is the **primary** key -- the composite score `[3]`, which
is where damage lives, only breaks ties. So any move with a priority score
one higher wins regardless of how much more damage the alternative does. The
dumb AI sorts on damage alone. With weak Pokemon "hit it hardest" is very
nearly the optimal policy, which would explain both halves of the result: the
smart AI's extra information is worth something only once priority and
effects start to matter. Not yet tested.

Results in `Documentation/ai_head_to_head.md`.

## Open

- **Copying could stop being necessary.** `fast_copy` made the copies cheap
  (above), but the reason they exist is that scoring a move mutates it. Move
  the per-use scratch fields -- `damage`, `accuracy`, `abilitymodifier`,
  `evasion`, `super_effective`, `not_effective`, `critical_hit` -- off `Move`
  into a per-evaluation object and `Move` becomes immutable shared data that
  never needs copying at all. That would make the shared-table invariant
  structural instead of a rule to remember, and it is still the largest
  remaining win: `fast_copy` is now the top entry in the profile at roughly a
  third of a battle. It changes AI decisions, so it needs the fingerprint as
  a *deliberate* diff rather than a check, plus a rating-simulation before and
  after to confirm the AI is no weaker.
- **Surge Surfer does nothing.** Alolan Raichu holds it and there is no
  handler, so it is a no-op -- and `UseAbility`'s debug counter has
  `ability_list.update({'Surge Surfer': 0})` bolted on to stop that being
  noticed. In the real games it doubles Speed on Electric Terrain, and this
  engine has no terrains (`field_effect` holds only Trick Room), so there is
  nothing to port; it needs a design decision, not a fix. Four registered
  abilities are unused by any Pokemon: Immunity, Magma Armor, Shadow Tag,
  Water Veil.
- **The turn loop is mutual recursion.** `end_of_turn` calls back into
  `move_selection`, about five stack frames a turn. Battles run 8-39 turns
  (median 19) so the 1000-frame limit is far off, but a stalling battle would
  die by `RecursionError` rather than end -- and both simulation harnesses
  suppress it, which would silently truncate the battle rather than report.

- An intermittent access violation on the worker thread during
  garbage-collection under harness load. Realistic play is clean (20/20 runs,
  4/4 playthroughs). One attempted fix made it worse and was reverted.
- `savefile.dat` is no longer in the project root though `savefile.py` says it
  stays as a backup. Harmless — never read while the JSON exists.
