Pokemon Championship v1.2.9

Shop
- expanded Shop to now include permanent upgrades

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.2.8

Custom Play
- NEW MODE Metronome, where players battle against AI using 6 Gamblers, who only have metronome
- renamed gamemode Custom Play into 1VS1

Gameplay
- opponent character abilities could now be copied / taken upon victory, but the chance depends on rating, and is not always guaranteed
- Auto Run will never attempt to copy character abilities
- added Shop and Coins, where coins are earned depending on Kill Score. Coins could be used in Shop, which allows re-rolling Pokemon IV and swapping Pokemon at the same tier
- added simple animation during battle, such as attacking moves, status moves, switching and fainted animations
- removed Settings, where players no longer could adjust difficulty or adjust volume in the game

Miscellaneous
- fine-tuned the game for risk control, and improve efficiency
- trim captions that are redundant, resulting in cleaner interface

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.2.7

Custom Play
- NEW MODE Custom Play, where players could pick any competitor and battle them

AI
- reworked the intelligent AI with enhanced decision-making; previous AI features a conditional scoring model and current AI uses turns as common currency in measuring move priority and score
- opponent tiers now matter again - they are all using the same AI, but they have information asymmetry that affects their decision-making

Rebalancing
- NERF CHARACTER ABILITY Curse of Forest: flinch chance 20% -> 10%
- NERF CHARACTER Alton: Psyduck IV 60 -> 50
- NERF CHARACTER ABILITY Outliers: damage band 0.8x-1.5x -> 0.8x-1.4x
- several characters' rating and ranking have been re-adjusted due to the AI changes, and their ability changes

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.2.6

Pokemon & Characters
- added new characters: Cristalla, Fae, Sterling, Libelle, Petra
- removed characters: Bondrewd, Bruno, Vardy, Bugsy, Monkey King
- NEW CHARACTER ABILITY Groundwork: the battle begins with Stealth Rock already scattered on the opponent's side of the field
- NEW CHARACTER ABILITY Reflection: her pokemon always has the higher base stats except HP among the pokemon on the field
- NEW CHARACTER ABILITY Pixelate: starts with misty terrain, all normal-type moves become fairy-type moves, and her normal and fairy moves hit 1.2x harder
- NEW CHARACTER ABILITY Cross Court: attacks choose the lower of Defense or Special Defense
- NEW CHARACTER ABILITY Field Study: attacks grow 8% stronger for each different pokemon she has seen on the field, up to 40%. Two of the same species count once
- NEW CHARACTER ABILITY Memento: when one of his pokemon faints, the opposing pokemon loses 2 stages of Attack and 2 stages of Special Attack
- NEW CHARACTER ABILITY Outliers: his attacks deal anywhere from 0.7x to 1.35x their damage, at random
- NEW CHARACTER ABILITY Quantum Roll: 3 of the 18 types cannot reach her pokemon for a turn, and the next turn's three are announced a turn ahead. Attacking moves only, from turn 2, and never every attack at once

Rebalancing
- REPLACED ABILITY Solanum: Telekinesis -> Quantum Roll
- REPLACED ABILITY Kurtosis: Outlier -> Outliers
- REBALANCED ABILITY Serene Grace: any secondary effect her moves carry now lands 80% of the time outright, instead of merely being twice as likely
- REBALANCED ABILITY Outliers: damage band widened from 0.7x-1.35x to 0.8x-1.5x, so the swing still cuts both ways but the average now favours him
- REMOVED unused character abilities: Outlier, Glacial Pace, Abdicate, Inheritance, Telekinesis, Mad Scientist, Experienced, Buggy
- REPLACED ABILITY Rudolf: Ruthless, which he shared with Gin -> Memento

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.2.5

Pokemon & Characters
- added new characters: Lillie, Yor Forger, Elowen
- added new character abilities: Aurora Borealis, Assassination, Sylvan Sprout
- NEW STATUS Sylvan Seed: the seed the Sylvan Sprout character ability plants. Leech Seed at half strength -- 1/16 of max HP a turn drained from the target and healed to the seeder, against Leech Seed's 1/8 -- because Sylvan Sprout plants one on every opponent that switches in, for free, where the move spends a turn each time
- a Sylvan Seed follows Leech Seed's rules: Grass types are immune and it does not stack, and it is shed when the seeded Pokemon switches out

Bugfixes
- MOVE Leech Seed now no longer took on a Grass type
- MOVE Throat Chop could crash the battle outright: it read the target's previous move by name, and a Pokemon that has not taken a turn yet has no move there. It needed the target to own a sound move that Throat Chop had already disabled, which is why it looked random
- AI threw priority moves at a target immune to them every turn: Queenly Majesty and Dazzling only refused the move on a real turn, and a real turn is not when the AI plans
- AI would buff its stats and then switch out the next turn, throwing away the boost it had just spent a turn on: switching resets stat stages and the switch maths priced that at nothing

Rebalancing
- the Pokemon a rating draws is reworked: the ladder now matters from 0 to 500 and everybody at 500 or above draws alike. Rating 5 draws mostly Low, rating 500 mostly Very High with some Ultra High and a little High
- ADJUSTED MOVE Adrenaline: no longer raise enemy pokemon attack, special attack or speed, instead increase own attack by 1 stage, special attack by 1 stage and speed by 2 stages, and also badly poison on itself
- Auraia's ace pokemon is now Jirachi instead of Alolan Ninetales
- Some characters' tier and ratings have been adjusted for game balancing purpose
- Some pokemon's tier has been adjusted for game balancing purpose

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.2.4

Auto Run
- added Auto Run to the start menu, where game plays on its own; Auto Run can be run up to 100 runs each time - it does not freeze the screen while the careers are played behind the title screen

Interface
- moves that really deal 2x or 4x are now highlighted as Super Effective on the move cards
- description added to weather, terrain and room when hovered
- the Field tab now lists the terrain and its countdown
- career history has added a new Records section
- now uses Fredoka or Nunito as fonts

Ratings
- the champion's crown and medal are now decided by the rating of the opponents they beat, not by opponent score: 👑 for beating over 36% of the field's rating, 🥇 at 15% or under. Everybody in the field counts, the player included
- competitors' ratings now move a little with their form per run, within 30% of their original rating
- an Upset now requires to be a higher class *and* a lower rating

AI
- smart AI and dumb AI no longer applies by rating, but by difficulty; normal difficulty uses smart AI, and beginner difficulty uses dumb AI
- now using blended model in calculating move choice for smart AI

Bugfixes
- Revavroom is now Steel/Poison
- CHARACTER ABILITY Synchronize: now works from the moment a Pokemon switches in, rather than from the turn after
- CHARACTER ABILITY Wizardry: the extra move could go to the opponent instead of Mivy, and could fire without a move being played
- AI would stop attacking and repeat a buff move at maxed stats against a Pokemon it could not reach (e.g. mid Phantom Force)
- the first turn of a battle did nothing and the action started on turn 2
- Pokemon previously could be shown as fainted on turn 1 of a new battle
- Sparking Cascade, Light Speed and Brain Wave could re-lay their opening terrain on a mid-battle switch

Coding & Organization
- documentation.md is now the one reference
- a crash now writes crash_report.txt beside the game, with the last 40 lines of battle log
- added Test/crash_hunt.py and Test/duel_hunt.py to hunt crashes across many battles
- the career music is read from Assets/music, so adding start7.mp3 is all it takes to add a track
- removed unused files and documentation

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.2.3

Interface
- Will now show moves that are disabled and reason for disabling
- Career history window's width is expanded

Pokemon & Characters
- added new Pokemon: Kartana, Archeops, Overqwil, Fezandipiti, Mega Scizor, Delphox, Goodra, Heatran, Jirachi, Steelix, Tangrowth, Volcanion
- added new abilities: Toxic Chain
- added new moves: Barb Barrage, Snipe Shot, Roost, Steam Eruption, Magma Storm
- added new characters: Samantha, Beatrice, Velvet, The Trio, Vex, Serena
- added new character abilities: Anger Point, Tension Release, Wizardry, Overloaded, Synchronize, Torment
- removed characters: AL

Rebalancing
- REMOVE CHARACTER ABILITY Monkey: Monkey King now has no character ability
- REWORK CHARACTER ABILITY Light Speed: no longer grants +1 Spd or the Electric type; the battle now starts on Electric Terrain and the Pokemon are immune to Ground-type damage
- ADJUST CHARACTER ABILITY Primordial: every 10 turns, brings the rain back if anything cleared it; Pokemon move 1.5x faster while it is raining instead of 2x
- ADJUST CHARACTER ABILITY Moody: 15% swing -> 10% swing, and the chances go from 15%/25% to 10%/20%
- NERF CHARACTER ABILITY Killer Instinct: 20% chance -> 10% chance
- NERF CHARACTER ABILITY Blunders: damage no longer takes type effectiveness into effect
- NERF CHARACTER ABILITY Plot Armor: still 3 lives, but revives to half HP rather than a full bar
- NERF CHARACTER ABILITY Gargantuan: 25% chance -> 15% chance
- BUFF CHARACTER ABILITY Old Legends: will reduce a random stat except crit ratio for target Pokemon when switched in
- BUFF CHARACTER ABILITY Serene Grace: doubled secondary effect at any point, but capped at 80% except for moves where secondary effect is 80% or above by default
- BUFF CHARACTER ABILITY Blood Magic: drains 33% instead of 20% of the damage actually dealt
- BUFF CHARACTER ABILITY Infiltration: entry hazards no longer affect own Pokemon
- BUFF CHARACTER ABILITY Overloaded: 10% chance -> 20% chance
- BUFF CHARACTER ABILITY Brain Wave: Psychic move damage +30% -> +50%
- BUFF CHARACTER ABILITY Tenebrous: now covers Ghost-type moves as well as Dark-type

- NERF MOVE History Rewritten: no longer disable moves
- NERF MOVE Regin of Terror: Power 90 -> 80, no longer reduce speed and accuracy by 1 stage
- NERF MOVE Draconic Blade: Power 75 -> 70
- BUFF MOVE Bodhisattva: Power 60 -> 80

- NERF STATUS CONDITION Frighten: damage dealt reduced by 1/2 -> damage dealt reduced by 1/3

- ADJUST CHARACTER Mivy Wenceslas: character ability Infiltration -> Wizardry
- ADJUST CHARACTER Emperor Marvuno: replace Scizor with Cloyster
- ADJUST CHARACTER Champion Marvin: replace Cloyster with Mega Scizor

Coding & Organization
- Align coding logic for implementation of character abilities

Miscellaneous
- amended character ability name of Berserker
- changed the quote of Rum
- removed Flame Charge for Genesect
- adjusted ratings and rankings of competitors
- adjusted tiers of certain Pokemon

Bugfixes
- Farfetch'd will now be shown in the list of Pokemon switching and Pokemon retention list
- Semi-invulnerable moves e.g. Fly will now be effected by drowsy effect and fail
- Damaging moves will no longer deal zero damage, and opponent reaching zero HP will no longer revive in normal circumstances
- U-Turn will now switch out Pokemon when against target Pokemon with illusion
- Bodhisattva now properly deals super effective damage to Flying type, instead of 0 damage
- Ruthless divided by the holder's current HP, which is zero the moment it faints, so a Pokemon knocked out by recoil or a hazard crashed the battle

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.2.0 - v1.2.2 (Graphics Update)

Graphics Update (Highlights)
- revamped text-based interface into graphic-based application with Claude and Leonardo.ai
- re-characterized characters due to legal issues: Adolf Hitler -> Rudolf; Voldemort -> Devoltorm
- pokedex to record all characters, moves, abilities and pokemon
- career history enhanced to show match-up result from start to end during the battle, and all past battle history / record in History section
- added graphics for tutorial, and background story

Game Mechanics
- now allows player to keep all Pokemon regardless of win/loss record for the run
- now allows player to view opponent team statistics when given the opportunity to swap upon victory
- now allows player to view opponent team, stat changes, non-volatile condition, weather, terrain, rooms all in battle interface
- added Fast Comparison for recommending swap based on base stats
- added Options to tweak game difficulty and volume
- added Starter Pokemon for new player to select
- revised rating table and mechanics for Pokemon distribution based on ratings, with simpler algorithm, and improved fairness between players and AI
- now allows up to 4 save slots
- added Terrain (same as original Pokemon series)

Pokemon & Characters
- added new Pokemon: Amoonguss, Slowbro, Glimmora, Baxcalibur, Kingambit, Tinkaton, Espathra, Ceruledge, Revavroom
- added new abilities: Toxic Debris, Thermal Exchange, Supreme Overload, Filter
- added new moves: Gigaton Hammer, Kowtow Cleave, Guillotine, Bitter Blade, Lumina Crash, Electric Terrain, Grassy Terrain, Misty Terrain, Psychic Terrain, Synthesis
- added new characters: Jason, Evonne, Celeste, Auraia, Ophelia, Coco, Alton, AL
- added new character abilities: Procrastination, Frighten, Celestial, Serene Grace, Lamplighter, Spark Cascade, Calibration
- some Pokemon's moves changed to add Terrain moves
- added splash art and gender for player to choose, and revised description of main character

Rebalancing
- NERF CHARACTER ABILITY Divine Power: 1.5x -> 1.25x
- REVISED CHARACTER ABILITY Desert Wind (Dulunga): now brews up sandstorm when a Ground type pokemon on either side is on the field
- revised ratings and tier of some characters: some characters have been moved up and down the ladder after rebalancing

Coding & Organization
- coding mainly powered by Claude Code Opus 5.0, including GUI graphical interface and some game mechanics changes
- backtesting added for rebalancing characters
- moves now integrated into csv instead of Python file
- custom team now integrated into competitors directly

Bugfixes
- Pudding's character ability Naive never trap both Pokemon
- Protean and Libero now work as intended

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.1.1 (bugfix)

In-Game Changes
Character Abilities
Buff: Musical, Last Stand, Curse of Forest, Silhouette, Old Legends
Nerf: Fireworks, Nimble

Abilities
Changed: Instrumental

Moves
Buff: Adrenaline

Pokemon
Buff: Kogoshaka

*********************************************************************************

Changed
- reduced frequency of pop-up message from Monkey and Charm character ability
- updated ratings and team order for some characters
- now display total win, lose and win rate for each character at History

Fixed
- pokemon get Grounded status if applicable once they are switched in
- entry hazard will work as usual now
- provide some ratings protection for player
- pokemon with Illusion ability now switches with fake name
- pokemon will no longer suffer from crash damage upon game ended
- pokemon in-game turn will now display when switched in
- disabled moves now disappear when reaching turn 0
- pokemon now faints when reaching < 0HP when using switching moves (e.g. U-Turn and Rough Skin)
- AI now considers move priority in its algorithm when considering best attacking move
- ground type moves no longer hit levitating pokemon
- grounding move should now ground pokemon
- sleeping turns appropriately adjusted and displayed
- weather-effect moves will no longer overlap
- weather-effect moves will now work again when the weather reverted back
- rearranged text order
- fixed some minor issues

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.1.0 (Official Release)

In-Game Changes
Character Abilities
- Buff: Mad Scientist, Brain Wave, Tenebrous, Heavy Blow, Sucking
- Nerf: Ruthless, Gargantuan, Musical, Moody

Added
- added description for trainers' ace and character ability
- mechanism for player to reveal trainer's ace and ability
- obtained 3D sprites for all non-custom pokemon (except Spectrier)
- added two pieces of music for start

Changed
- distinguish between Protagonist object and name (by adding nickname for every trainer)
- updated lore for tutorial and backstory while removed rules
- rearranged interaction between Aegislash and Stance Change ability
- organized files and folders
- retweaked strength of each competitors
- player now starts at strength 5
- organized all files into respective folders
- organized text output

Fixed
- custom team Pokemon now properly aligns with designated trainers
- slightly amended obvious error in character ability
- ability that triggers when switched in now functions for player when both pokemon are fainted (e.g. intimidate)
- corrected name of Venusaur

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.0.8 (Character Ability Update)

In-Game Changes
Moves
- Nerf: Draconic Blade, Empyrean Glory, Soul Harvest, History Rewritten, Glissando
- Change: Crow Dance -> Adrenaline (different move effect), Depraved Shriek (after_hand -> before_hand, power 120 -> 100)
- Buff: Cannibalism

Abilities
- Nerf: Divine Aegis

Pokemon
- Nerf: Scizor (reverted to original base stats)

Added
- new batch of both original and custom Pokemon is added, with some additional new moves and abilities
- added comprehensive stats, including win rate, for AI simulation
- now able to loop through each opponent in AI simulation
- added Character Ability for AI participants (!!)

Changed
- converted weather to str/dict instead of class
- ratings adjustment and Pokemon tier adjustment based on data analysis
- pokemon team alternation for characters
- text color adjustment
- actual gameplay readability update

Fixed
- 3-hit moves (e.g. 3-hand trick & triple axel) now multiplies power when hit
- AI now appropriately addresses ability Disguise (mimikyu)
- perish song is now properly functioning, with perish count included
- AI will no longer switch itself in
- attempt to reach >6 critical hit will no long result in error
- ability Illusion now changes type before calculating move damage
- ability-induced changes will now be factored before calculating speed and move order
- obtaining random pokemon when beating Champion-level participant will no longer cause error
- disabling moves will now fail when previous move of the target pokemon is "Switching"
- smart AI using useless first-turn-priority move (e.g. fake out)
- interchangable type moves should use the best typing now
- countering move won't induce error if target has not used any move before
- fixed ability Moody affecting the same stats (now distinct)
- AI now properly addresses speed adjustment due to abilities

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.0.7 (AI Update)

AI
- added new additional effects for smart AI to evaluate
- added a new comprehensive scoring system for smart AI
- added basic description for the AI
- redevelop smart AI to be less willing to switch and more willing to attack, especially at desperate moment
- smart AI will no longer spam self-modifying moves
- smart AI now forbids entering into switching loop
- smart AI will look upon special conditions for some moves (e.g. dream eater, sucker punch, destiny bond etc.)
- smart AI will now consider before using health-deducting moves (e.g. explosion and belly drum)
- updated AI switching mechanism
- smart AI will attempt to predict moves

In-Game Changes
- Nerf: Bodhisattva, Battle Axe, Glissando, Eerie Rhythm
- Buff: Glaciate, Gambit

Added
- added a proper and appropriately dumb auto-battle AI (worse than dumb AI)
- added favorite opponent
- added tutorial for beginners
- added "keep all" function for player when crowned Champion
- new tiebreak (opponent score) has been added to reflect on overall performance of the participant
- special symbol to highlight high-valued Champion and low-valued Champion based on opponent score
- display opponent Pokemon stats upon victory (convenient for choosing)
- display player Pokemon stats for swapping
- display total Pokemon stats for easier comparison
- added sudden death to shorten game time
- now displays no. of world champion of the participant (and bold them)
- new batch of original Pokemon, with some new moves and abilities

Changed
- added custom function for ability Illuminate
- amended wordings on Ash Ketchum's description
- adjusted elo rating formula to be more vigorous
- volatile status in battle now displays only when necessary (cleaner interface)
- formula where participants receive Pokemon of different tiers based on ratings is now harsher
- updated multi-strike metrics
- added number of pokemon based on tier for AI simulation

Fixed
- multi-strike moves now function according to the formula properly
- when fast-moving pokemon affects any battle stats, slow-moving pokemon's moves does not account for such change immediately
- skill link not activated before multi-strike calculation
- rough skin will no longer attack target that does no damage to user (including charging move)
- countering moves now function as intended when opponent missed the move (instead of error)
- obtained pokemon upon defeat now distributes IV according to player strength/ratings
- aegislash will now change name and reset base stats after battle
- zoroark illusion will no longer revert its typing when it is not hit or revealed
- zoroark illusion now partially misleads AI (when considering its typing only)
- recursion error in AI simulation is now non-existent due to sudden death

Known Bugs
- if there is only 1 Pokemon left and all its moves are disabled, there will be error

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.0.6 (Character Update)

Added
- added new characters
- added incremental age for player
- added sign (!!!) to indicate player loss and upset
- added confirmation message for ongoing moves (e.g. frenzy and charging moves)
- added signature pokemon for each character
- added a few Pokemon

Changed
- updated existing characters' ratings and quotes
- tuned down some custom Pokemon moves (mostly Armadragdon & Memoraider)
- tuned down some custom Pokemon abilities (mostly Armadragdon & Memoraider)
- re-written elo rating formula
- increase no. of elite per round (3-5 --> 4-6)
- readability update (text color, spacing and individual rating change)

Fixed
- fixed duplicated/ongoing literal "Fainted" status
- Illusion ability now considers the correct typing for damage calculation
- recoil damage now guarantees 1 damage to user
- Aegislash now switches to blade forme only before it executes its attacking move
- Pokemon affected by Mummy ability will now revert back when switched out
- Poison type and Steel type Pokemon now does not get affected by poison due to toxic spikes
- Ground type move now does not work on target with Levitate ability
- frenzy moves (e.g. outrage, raging fury etc.) now reset counter when being interrupted (e.g. fairy type Pokemon)
- countering moves (e.g. mirror coat & counter) now properly function
- AI now uses first-turn priority moves (e.g. Fake Out) only at the first turn
- status condition interrupt now won't inflict crash damage
- charging moves and semi-invulnerable moves will now execute for the first turn regardless of accuracy

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.0.5 (Pokemon Update)

Added
- added new batch of Pokemon, and the respective necessary moves and abilities

Changed
- updated credits
- updated moveset of some existing Pokemon

Fixed
- unused pokemon's moveset now does not get erased
- dumb AI won't switch pokemon when activating auto battle
- Keen Eye ability now properly functions

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.0.4 (Lore Update)

Changed
- updated descriptions and quotes for some characters
- replaced the Lower Elite Four

Fixed
- fixed gamesystem giving duplicated pokemon when continue game (not accounting for pokemon object previously)
- fixed 6 pokemon cannot swap bug
- hurricane confused bug
- fixed sticky web fails to slow pokemon
- now also change type for Zoroark illusion

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.0.3 (Team Update)

Added
- added team selection feature when player has more Pokemon than the round requires
- as of above, World Champ can now keep full team, high achievers (4PTS) can keep 4 Pokemon, otherwise can keep 3 Pokemon (BUFF)

Fixed
- fixed levitate & ungrounded bug

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.0.2 (User-Friendly Update)

Added
- added Auto Battle feature (automating battle with Dumb AI upon player's wish)

Changed
- formula for receiveing pokemon according to strength is changed
- divided custom pokemon to several tiers, removed custom tier and added Boss tier (cannot be obtained)
- updated text colors for readability
- tuned down Goredrinker ability

Fixed
- fixed incorrect win rate
- fixed incorrect IV distribution
- smart AI is now compatible with multiple move effects

---------------------------------------------------------------------------------------------------------------------------------------------------------

Pokemon Championship v1.0.1 (Game System Update)

Added
- added comprehensive match history available at home screen
- now restart the game when ended
- added proper team for World Champion Marvin

Changed
- replaced with royalty-free music (partially)
- organized csv file

Fixed
- duplicated Pokemon upon selection
- bug involving History and New Game (due to recursion)
- AI simulation issue
