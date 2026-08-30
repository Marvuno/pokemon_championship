# Pokemon Championship — reference

Three things in one place: what the roster adds up to, what this game changes
from the series it borrows from, and what the numbers and letters in
`Data/*.csv` mean.

## The roster

|  |  |
|---|---|
| Pokemon | 261, of which 39 are this game's own |
| Moves | 397, of which 45 are this game's own |
| Competitors | 69, plus the player |

| Pokemon tier | | Competitor tier | |
|---|---|---|---|
| Very Low | 21 | Low | 16 |
| Low | 49 | Intermediate | 21 |
| Medium | 70 | Advanced | 23 |
| High | 80 | Elite | 8 |
| Very High | 28 | Champion | 1 |
| Ultra High | 6 | | |
| Boss / Secret | 7 | | |

Typing is spread evenly enough that no type is rare: Water 36 at the top,
Fighting 19 at the bottom, and one Typeless (Gambler).

The per-Pokemon and per-move breakdown is generated rather than kept here,
because it goes stale the moment the roster moves:

```
python Test/stats.py            the roster, counted every way
python Test/ai_simulation.py    per-Pokemon win rates
```

## Game changes

What this game changes from the series it borrows from.

### Pokemon

1. Several custom pokemon are added, including:
- Snowchild ['Normal', 'Ice']
- Kuroseh ['Fighting', 'Fairy']
- Twinktwin ['Bug', 'Fairy']
- Gyutaro ['Poison', 'Ghost']
- Harshock ['Rock', 'Ghost']
- Landozer ['Fighting', 'Ground']
- Apoptoxitic ['Poison', 'Flying']
- Emmount ['Ground', 'Rock']
- Krusadian Flygon ['Bug', 'Dragon']
- Galveon ['Steel']
- Nightdaunter ['Ghost']
- Gyokko ['Water', 'Psychic']
- Boneknight ['Steel', 'Ghost']
- Scorchrome ['Fire', 'Ground']
- Charmorin ['Normal', 'Fairy']
- Hantengu ['Electric', 'Flying']
- Psyvinstry ['Grass', 'Ice', 'Psychic']
- Fieritre ['Fire', 'Grass']
- Fairyflame ['Fire', 'Fairy']
- Tanjiro ['Water', 'Fire']
- Vindaxe ['Rock']
- Akaza ['Fighting']
- Chesiquen ['Ground', 'Flying']
- Krusadian Salamence ['Ground', 'Dragon']
- Dreadigo ['Dark', 'Fairy']
- Pianotic ['Normal', 'Ghost']
- Douma ['Ice']
- Faker-Greninja ['Water', 'Dark']
- Kogoshaka ['Dark', 'Psychic']
- Kokushibo ['Dark', 'Dragon']
- Poseidon ['Water', 'Electric']
- Memoraider ['Dark', 'Ghost']
- Armadragdon ['Dragon', 'Flying', 'Steel']
- Gambler ['Typeless']
- Brambleblood ['Poison', 'Dark']
- Maruka ['Fairy']
- Ygadr ['Ice', 'Dragon']
- Voltamelon ['Grass', 'Electric']
- Sworphin ['Water']

2. Some existing pokemon are tweaked, including:
- Alolan Exeggutor: ability changes to Long Reach
- Duraludon: ability changes to Sand Force
- Dedenne: ability changes to Static

### Moves
1. Some moves are nerfed, including:
- Recover: heal 50% -> 30%
- Slack Off: heal 50% -> 30%
- Bug Bite: no berry-eating effect

2. Some moves are buffed, including:
- Dark Void: sleep 50% -> 70%
- Team Effects (e.g. Light Screen, Reflect, Aurora Veil and Tailwind) lasts for 6 turns (by default)
- Field and Weather Effects (e.g. Rain Dance, Trick Room etc.) lasts for 6 turns (by default)
- Techno Blast: now interchange type between normal and water (since this game has no items)
- Water Shuriken: 15 power -> 20 power
- Rock Climb: Normal type -> Rock type
- Disable: can now disable multiple moves
- Glaciate: 65 power -> 80 power
- Explosive moves (Explosion, Self-Destruct, Mind Blown etc.) will no longer deduct HP when target Pokemon is in Semi-Invulnerable mode

3. Some custom moves are added, including:
- Cold Touch (Ice): 30 power, physical, priority move, 30% flinch
- Wail (Ghost): 90 special power, 50% to lower SpDef and Acc. by 1 stage
- Corrosive Water (Water): 80 power, special, 90% accuracy, 20% poison, super-effective against grass and fairy type
- Adrenaline (Dark): status, increase ATK and SpA by 2 stages, DEF and SpDef by 1 stage, decrease Spd by 2 stages, while increasing target pokemon ATK, SpA and Spd by 1 stage
- Depraved Shriek (Dark): 100 power, special, duo-type with psychic, double power when move first
- Double Sickle (Ghost): 50 power, physical, double hit, drain 15% hp and 20% to poison for each hit
- Fish Needle (Water): 90 power, special, 30% badly poison
- Enragement (Flying): 70 power, non-contact physical, power depends on number of pokemon fainted in user team (power range between 0 - 350)
- Annihilation (Fighting): 240 power, physical, charging move, 25% recoil
- Crystalline Clone (Ice): status, increase SpA and Evasion between 2 - 5 stages at 50% accuracy, depends on MultiHit formula (e.g. biased on around 2 - 3 stages)
- Bodhisattva (Ground): 80 power, contact special, -2 priority, super-effective against flying type, increase SpDef by 1 stage
- Lotus Petal (Grass): 60 power, special, priority move
- Unbreakable Will (Fighting): status, increase ATK, DEF, SpA, SpDef, Spd by 1 stage, deduct 25% HP
- Moon Slash (Dark): 80 power, physical, drain 25% HP
- Dragon Crescent (Dragon): 80 power, physical, increased crit ratio, 20% flinch
- First Strike (Steel): 60 power, physical, priority move
- Total Concentration (Normal): status, increase ATK and SpA by 1 stage at the end of each turn
- Nichirin Sword (Water): 90 power, physical, will determine the highest type effectiveness between water and fire type against target, and change move type
- Tidal Surge (Water): 90 power, special, 30% confuse
- Thunderous Trident (Electric): 120 power, special, 30% flinch, Guarantee accuracy in rain
- Cryokinesis (Psychic): 80 power, special, duo-type with ice, 10% freeze
- Cling (Fairy): 35 power, physical, binding move
- Charming Tap (Fairy), 60 power, physical, lower target ATK by 1 stage
- Sparkling Punch (Fairy): 80 power, physical, 30% flinch
- Sweet Dreams (Fairy): status, bypass protection and accuracy, 70% sleep
- Revenant Charge (Ghost): 100 power, physical, 50% lower target DEF by 1 stage
- Battle Axe (Rock): 65 power, physical, drain 25% HP
- Thunderclap (Electric): 80 power, physical, 20% paralysis
- Chaotic Shockwave (Electric): 80 power, physical, 30% flinch, sound-based move, can breakthrough protection
- History Rewritten (Normal): status, reset opponent stat stages and confuse
- Soul Harvest (Dark): 40 power, special, +1 priority move, binding, drain 30% dmg
- Reign of Terror (Ghost): 80 power, special, 30% frighten
- Empyrean Glory (Flying): status, buff user DEF and SpDef by 1 stage, heal team status condition problem, clear weather
- Draconic Blade (Dragon): 70 power, physical, 30% frighten
- Ground Slam (Ground): 100 power, non-contact physical, 50% confuse
- Glissando (Flying): 70 power, special, sound-based, 30% flinch
- Eerie Rhythm (Ghost): 70 power, special, sound-based, 10% reduce target SpDef by 1 stage, 10% confuse
- 3-Hand Trick (Fairy): 20 power, special, double power for each successive hit
- Cannibalism (Dark): 80 power, physical, drain 50% HP, if directly cause faint drain another 50% HP
- Time Pressure (Ground): 40 power, special, the higher the relative speed the higher the dmg (ref: electro ball)
- Gambit (Normal): status, increase SpDef, SpA and Spd by 1 stage, can only use at the first turn
- Twin Shadows (Normal): status, increase Evasion by 2 stages
- Faerie Fire (Fire): 70 power, special, 2x against Dragon, 50% lower SpA by 1 stage
- Fluid Spray (Grass): 50 power, special, reduce target Def and SpDef by 1 stage
- Boulder Smash (Rock): 100 power, physical, 70% accuracy, 50% confuse

### Abilities
1. Some custom abilities are added, including:
- Poisonous Blow: badly poison opponent when user at 30% hp or below (including fainted)
- Improvise: increase speed and evasion by one stage when directly cause target to faint
- Compass Needle: always guarantee accuracy
- Dead Calm: negate weather buff/nerf to moves
- Scorch: burn target grounded pokemon
- Goredrinker: user recovers ~33% damage as HP for damaging moves when below 50% HP
- Formation: buff user Rock-type move damage by 30%
- Landlord: buff user Ground-type move damage by 30%
- Divine Power: if not super-effective against target, move damage * 1.5
- Divine Aegis: if not super-effective against user, move damage * 0.75 (Ignored by Mold Breaker)
- Instrumental: halved damage to sound-based moves, sound-based moves against target buff move damage by 30%, take 50% more damage from fire and water types attack
- Strong Roots: start with Ingrain

2. Some abilities are buffed, including:
- Berserk: can now activate several times when taking damage under 50% HP (previously only one time)
- Cloud Nine: now clears weather (previously suppress weather)

3. Some abilities are nerfed, including:
- Heatproof: it will no longer prevent Burn status ailment
- Battle Bond: it now only multiplies the power of Water Shuriken by 1.5
- Anticipation: it no longer detects any explosive moves
- No Guard: it no longer hits pokemon in semi-invulnerability

4. Some abilities are altered, including:
- Magic Guard: it will now prevent damage from binding move, but also disable regeneration from ingrain, leech seed and aqua ring

### Rules of this game
1. All trainers will have their character ability
2. Some trainers will have custom pokemon, which is usually stronger and own unique ability or moves
3. The AI will know the moves of the target Pokemon, but can be deceived by its typing, and not the pokemon on the Protagonist team
4. Unless otherwise specified, original pokemon's ability can be selected via its mega form or normal form (but not limited to regional form)
5. The arena rolls its own weather: 20% that there is any, then an even pick of Rain, Sunny, Sandstorm or Hail. It never lifts. Terrain is rolled the same way and at the same odds, and does lapse.
6. There is no Draw in this game. However, if both players are out of usable Pokemon, the one with lower strength is deemed the winner.

### Known bugs
1. If one team's pokemon got swept at the move selection process by entry hazard, the game will announce results
but still go on for one more turn for the opponent.
2. ability Illusion is partially useful to AI, due to Rules #3.

## Encoding reference

What the numbers and letters in `Data/*.csv` and the engine's
own arrays mean. Positions are zero-based throughout.

### Typing

| | | | | | |
|---|---|---|---|---|---|
| 0 Normal | 1 Fire | 2 Water | 3 Electric | 4 Grass | 5 Ice |
| 6 Fighting | 7 Poison | 8 Ground | 9 Flying | 10 Psychic | 11 Bug |
| 12 Rock | 13 Ghost | 14 Dragon | 15 Dark | 16 Steel | 17 Fairy |

### Move type

`0 Physical | 1 Special | 2 Status`

### Modifier

Stat stages, the nine-slot array `[0]`..`[8]`:

`0 HP | 1 Attack | 2 Defense | 3 SpA | 4 SpDef | 5 Speed | 6 Evasion |
7 Accuracy | 8 Crit`

Stages run -6..+6 and are clamped. `modifierChart` rows are `_StageRow`,
which does the clamping: 0..+6 are the first seven entries, -1..-6 are read
off the end by negative indexing.

### Status condition

`0 Normal | 1 Poison | 2 BadPoison | 3 Paralysis | 4 Burn | 5 Sleep |
6 Freeze | 7 Fainted`

Fainted lives in the same field as the rest. Anything that clears "status"
has to exclude it or it revives the dead.

### Battle stats

`0 HP | 1 Attack | 2 Defense | 3 SpA | 4 SpDef | 5 Speed`

### Entry hazard

`0 Stealth Rock | 1 Spikes | 2 Toxic Spikes | 3 Sticky Web`

### Multi-strike move

`[0]` `0 Fixed | 1 Variable | 2 Triple Hit`
`[1]` maximum number of strikes

### Move flags

| | |
|---|---|
| `a` | contact |
| `b` | cannot be protected against |
| `c` | thaws out a frozen user |
| `d` | biting (Strong Jaw) |
| `e` | punching (Iron Fist) |
| `f` | sound-based (Soundproof is immune) |
| `g` | powder-based (Grass types are immune) |
| `h` | pulse-based (Mega Launcher) |
| `i` | ball or bomb (Bulletproof resists) |
| `j` | first-turn only (Fake Out) |

### Protective moves

`0 None | 1 Protect | 2 King's Shield | 3 Baneful Bunker`

### Move effect types

The `effect_type` column. One name, or several separated by `|`, paired by
position with `special_effect`.

| | | |
|---|---|---|
| no_effect | target_non_volatile | target_volatile |
| user_volatile | opponent_modifier | self_modifier |
| self_heal | hp_draining | weather_effect |
| weather_heal | field_effect | terrain |
| self_team_buff | remove_team_buff | team_status_heal |
| apply_entry_hazard | clear_entry_hazard | switching |
| reset_user_modifier | reset_target_modifier | user_protection |
| countering | retaliation | hp_split |
| before_hand | after_hand | modifier_dependent |
| target_disable | swap_barrier | add_target_type |
| cursing | ohko | roost |

`terrain`, `weather_heal` and `roost` are the newest: the four
terrain-laying moves, Synthesis (whose heal depends on the sky), and
Roost -- which heals a third *rounded up*, unlike every other heal
here, and takes the user's Flying type away until the end of the turn.

### The three rule columns

`power_when`, `weather_when` and `fails_unless` say in the table what used to
be `if move.name == ...` in the engine. The vocabularies are **closed** and
checked when the table loads: a name that is not on these lists is an error
at startup naming the move, the column and every name that would have
worked. They live in `Scripts/Battle/move_rules.py`.

**power_when** — doubles the power by default; `condition*1.5` for anything else.

`target_below_half`, `target_poisoned`, `target_statused`, `user_statused`

**weather_when** — `Weather:effect`, several separated by `|`.

`always_hits`, `half_accuracy`, `half_power`, `no_charge`

**fails_unless** — the move does nothing unless the condition holds.

`can_pay_hp_and_still_boost`, `hit_by_contact`, `not_used_last_turn`,
`target_asleep`, `target_attacks`, `user_asleep`

### Ability phases

| | |
|---|---|
| 0 | Battle initialization (character abilities only) |
| 1 | Start — beginning of battle, or switched in |
| 2 | After move select (user side) |
| 3 | After move select (target side) |
| 4 | After calculating move damage (user side) |
| 5 | After calculating move damage (target side) |
| 6 | After a successful hit and its effect (user side) |
| 7 | After a successful hit and its effect (target side) |
| 8 | End of turn |
| 9 | Switched out |
| 10 | Before the turn order is decided (`ORDER_PHASE`) |

Phase 10 is the odd one out and is there for a reason: 1..9 all happen once a
Pokemon is already taking its turn, which is too late for an ability that
decides *when* the turn is taken. Swift Swim, Chlorophyll, Slush Rush,
Prankster and Gale Wings live there, along with the character abilities that
change a move's priority or its holder's Speed -- Tension Release and
Primordial. It fires from `compare_speed`, after the speed adjustment and
before the comparison.

`REGISTRY` at the bottom of `Scripts/Battle/ability_effects.py` is the single
source; the phase map is derived from it.

### Field layers

Three separate slots, not one. Weather, a terrain and a room can all be up
at once, and only members of the same layer replace each other.

| layer | where it lives | lifts? |
|---|---|---|
| Weather | `battleground.weather_effect` | only if artificial |
| Terrain | `battleground.terrain` | yes, counts down |
| Rooms | `battleground.field_effect` | yes, counts down |

**Terrain** — `None`, `Electric`, `Grassy`, `Misty`, `Psychic`. A move lays
it for 5 turns; a battle that opens on one has it for 10 (5% chance each, so
one battle in five). Terrain reaches only what is standing on it: a Flying
type, a Levitate holder or anything mid-Fly gets none of it.

A terrain move that no Pokemon in the roster learns is listed in
`terrain.UNLEARNED` with the reason, so a deliberate gap can be told from an
editing accident. **Misty Terrain** is there now: nobody carries it, so it
happens only on the arena's own opening roll.

### The Poke columns in competitors.csv

A cell is a species name, optionally carrying the details that make it
theirs:

```
Durant
Grimmsnarl|iv=20|ability=Prankster|moves=Bulk Up,Foul Play,Play Rough
Pikachu|iv=60
```

`|` separates the name from each detail, `=` a detail from its value, `,` the
moves. Anything not pinned is rolled as a bare name always was. A pinned
`iv` is used as both ends of the roll, which is how an IV above 31 exists.

The recognised details are `iv`, `ability` and `moves` — closed, so a typo is
a load-time error naming the competitor, the cell and the valid keys.

### Competitor tiers

`Low`, `Intermediate`, `Advanced`, `Elite`, `Champion`, plus `Protagonist`
for the player's own row, which is a marker and not a rung.

Ratings are the numbers in `Strength` and on screen. They decide the calibre
of team a competitor brings and where they sit in the bracket -- not how well
they play. A competitor's rating drifts with their form after each career,
by at most 3% a run and never further than 30% from the value in
`competitors.csv`. Every opponent uses the planning AI on Normal and the damage-first
one on Beginner, whatever they are rated.

### Pokemon tiers

`Very Low`, `Low`, `Medium`, `High`, `Very High`, `Ultra High` — weakest
first. A competitor's rating becomes a position on this ladder and their team
is drawn around it; see `Scripts/Data/tiers.py`, which is the single answer
for a competitor's own team, the player's, a win reward and a consolation.
