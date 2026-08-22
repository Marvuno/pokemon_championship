# Encoding reference

What the numbers and letters in `Data/*.csv` and the engine's own arrays
mean. Positions are zero-based throughout.

## Typing

| | | | | | |
|---|---|---|---|---|---|
| 0 Normal | 1 Fire | 2 Water | 3 Electric | 4 Grass | 5 Ice |
| 6 Fighting | 7 Poison | 8 Ground | 9 Flying | 10 Psychic | 11 Bug |
| 12 Rock | 13 Ghost | 14 Dragon | 15 Dark | 16 Steel | 17 Fairy |

## Move type

`0 Physical | 1 Special | 2 Status`

## Modifier

Stat stages, the nine-slot array `[0]`..`[8]`:

`0 HP | 1 Attack | 2 Defense | 3 SpA | 4 SpDef | 5 Speed | 6 Evasion |
7 Accuracy | 8 Crit`

Stages run -6..+6 and are clamped. `modifierChart` rows are `_StageRow`,
which does the clamping: 0..+6 are the first seven entries, -1..-6 are read
off the end by negative indexing.

## Status condition

`0 Normal | 1 Poison | 2 BadPoison | 3 Paralysis | 4 Burn | 5 Sleep |
6 Freeze | 7 Fainted`

Fainted lives in the same field as the rest. Anything that clears "status"
has to exclude it or it revives the dead.

## Battle stats

`0 Attack | 1 Defense | 2 SpA | 3 SpDef | 4 Speed`

## Entry hazard

`0 Stealth Rock | 1 Spikes | 2 Toxic Spikes | 3 Sticky Web`

## Multi-strike move

`[0]` `0 Fixed | 1 Variable | 2 Triple Hit`
`[1]` maximum number of strikes

## Move flags

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

## Protective moves

`0 None | 1 Protect | 2 King's Shield | 3 Baneful Bunker`

## Move effect types

The `effect_type` column. One name, or several separated by `|`, paired by
position with `special_effect`.

| | | |
|---|---|---|
| no_effect | target_non_volatile | target_volatile |
| user_volatile | opponent_modifier | self_modifier |
| self_heal | hp_draining | weather_effect |
| weather_heal | field_effect | terrain |
| self_team_buff | remove_team_buff | team_status_heal |
| apply_entry_hazard | clear_entry_hazard | charging |
| switching | reset_user_modifier | reset_target_modifier |
| user_protection | countering | retaliation |
| hp_split | before_hand | after_hand |
| modifier_dependent | target_disable | swap_barrier |
| add_target_type | cursing | ohko |

`terrain` and `weather_heal` are the newest: the four terrain-laying moves,
and Synthesis, whose heal depends on the sky.

## The three rule columns

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

## Ability phases

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

`REGISTRY` at the bottom of `Scripts/Battle/ability_effects.py` is the single
source; the phase map is derived from it.

## Field layers

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

## The Poke columns in competitors.csv

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

## Competitor tiers

`Low`, `Intermediate`, `Advanced`, `Elite`, `Champion`, plus `Protagonist`
for the player's own row, which is a marker and not a rung.

Ratings are the numbers in `Strength` and on screen. `SMART_AI_RATING` (50)
is read on that scale: at or above it a competitor uses the planning AI
against a human player, below it the damage-first one.

## Pokemon tiers

`Very Low`, `Low`, `Medium`, `High`, `Very High`, `Ultra High` — weakest
first. A competitor's rating becomes a position on this ladder and their team
is drawn around it; see `Scripts/Data/tiers.py`, which is the single answer
for a competitor's own team, the player's, a win reward and a consolation.
