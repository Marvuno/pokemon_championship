"""One line each for what a Pokemon ability does.

Text only -- nothing here affects the game. The behaviour lives in
abilities.py, and this exists because that file is code: the Pokedex had no
description to show and inventing one at render time would have meant a second
account of an ability that could quietly drift from the first.

Kept deliberately short: one clause, the effect and nothing else. Where a
number appears it is the number abilities.py actually uses, not the one the
official games use, because the two do not always agree in this project.

Custom abilities -- the ones written for this game -- are marked and were
described by reading their implementation rather than any outside source.
"""

#: ability name -> one line. Anything missing simply shows no description.
ABILITY_TEXT = {
    # -- damage and stat modifiers ----------------------------------------
    "Adaptability": "Same-type moves hit harder than usual.",
    "Analytic": "Moves hit harder when moving after the target.",
    "Battle Bond": "Grows stronger after knocking a Pokemon out.",
    "Beast Boost": "Raises its best stat after a knockout.",
    "Berserk": "Raises Sp. Atk when dropped below half HP.",
    "Blaze": "Fire moves hit harder when low on HP.",
    "Torrent": "Water moves hit harder when low on HP.",
    "Competitive": "Sharply raises Sp. Atk when a stat is lowered.",
    "Defiant": "Sharply raises Attack when a stat is lowered.",
    "Download": "Raises Attack or Sp. Atk against the target's weaker defence.",
    "Grim Neigh": "Raises Sp. Atk after knocking a Pokemon out.",
    "Guts": "Attack rises while poisoned, burned or paralysed.",
    "Huge Power": "Doubles Attack.",
    "Hustle": "Physical moves hit harder but land less often.",
    "Iron Fist": "Punching moves hit harder.",
    "Justified": "Raises Attack when hit by a Dark move.",
    "Mega Launcher": "Pulse and aura moves hit harder.",
    "Moxie": "Raises Attack after knocking a Pokemon out.",
    "Overgrow": "Grass moves hit harder when low on HP.",
    "Pure Power": "Doubles Attack.",
    "Punk Rock": "Sound moves hit harder, and sound taken is halved.",
    "Reckless": "Recoil moves hit harder.",
    "Sand Force": "Rock, Ground and Steel moves hit harder in a sandstorm.",
    "Sheer Force": "Moves hit harder but lose their added effect.",
    "Skill Link": "Multi-hit moves always hit the maximum number of times.",
    "Sniper": "Critical hits do more than usual.",
    "Soul-Heart": "Raises Sp. Atk whenever any Pokemon faints.",
    "Stamina": "Raises Defence when hit.",
    "Steelworker": "Steel moves hit harder.",
    "Strong Jaw": "Biting moves hit harder.",
    "Super Luck": "Lands critical hits more often.",
    "Swarm": "Bug moves hit harder when low on HP.",
    "Technician": "Weak moves hit harder.",
    "Tinted Lens": "Doubles the damage of moves the target resists.",
    "Tough Claws": "Moves that make contact hit harder.",
    "Victory Star": "Moves land more often.",
    "Compound Eyes": "Moves land more often.",
    "No Guard": "Every move lands, from either side.",

    # -- damage taken ------------------------------------------------------
    "Battle Armor": "Cannot be struck by a critical hit.",
    "Shell Armor": "Cannot be struck by a critical hit.",
    "Filter": "Takes a quarter less from super-effective moves.",
    "Solid Rock": "Takes a quarter less from super-effective moves.",
    "Fluffy": "Halves contact damage but takes double from Fire.",
    "Heatproof": "Takes less from Fire moves.",
    "Ice Scales": "Halves the damage of special moves.",
    "Multiscale": "Takes half damage at full HP.",
    "Thick Fat": "Takes less from Fire and Ice moves.",
    "Wonder Guard": "Only super-effective moves can hurt it.",
    "Magic Guard": "Only takes damage from moves.",
    "Sturdy": "Survives a hit that would knock it out from full HP.",
    "Disguise": "A busted disguise absorbs the first hit.",

    # -- immunities and absorption ----------------------------------------
    "Bulletproof": "Immune to ball and bomb moves.",
    "Dazzling": "Blocks priority moves aimed at it.",
    "Queenly Majesty": "Blocks priority moves aimed at it.",
    "Flash Fire": "Immune to Fire, and its own Fire moves strengthen.",
    "Levitate": "Immune to Ground moves.",
    "Lightning Rod": "Draws in Electric moves and raises Sp. Atk instead.",
    "Motor Drive": "Draws in Electric moves and raises Speed instead.",
    "Storm Drain": "Draws in Water moves and raises Sp. Atk instead.",
    "Sap Sipper": "Immune to Grass, raising Attack instead.",
    "Volt Absorb": "Recovers HP from Electric moves instead of taking damage.",
    "Water Absorb": "Recovers HP from Water moves instead of taking damage.",
    "Soundproof": "Immune to sound moves.",
    "Water Bubble": "Doubles its Water moves, halves Fire taken, cannot burn.",

    # -- status ------------------------------------------------------------
    "Early Bird": "Wakes from sleep twice as fast.",
    "Hydration": "Cures its status condition in rain.",
    "Immunity": "Cannot be poisoned.",
    "Insomnia": "Cannot fall asleep.",
    "Vital Spirit": "Cannot fall asleep.",
    "Limber": "Cannot be paralysed.",
    "Natural Cure": "Cures its status condition on switching out.",
    "Shed Skin": "May shed a status condition each turn.",
    "Sweet Veil": "Cannot fall asleep.",
    "Water Veil": "Cannot be burned.",
    "Own Tempo": "Cannot be confused.",
    "Inner Focus": "Cannot be made to flinch.",
    "Synchronize": "Passes its status condition back to whoever caused it.",
    "Effect Spore": "Contact may poison, paralyse or put to sleep.",
    "Flame Body": "Contact may burn.",
    "Poison Point": "Contact may poison.",
    "Static": "Contact may paralyse.",
    "Cursed Body": "May disable the move that struck it.",
    "Mummy": "Contact replaces the attacker's ability.",
    "Bad Dreams": "Drains HP from a sleeping target each turn.",

    # -- contact and recoil ------------------------------------------------
    "Aftermath": "Hurts the attacker when knocked out by contact.",
    "Iron Barbs": "Hurts anything that touches it.",
    "Rough Skin": "Hurts anything that touches it.",
    "Rock Head": "Takes no recoil damage.",
    "Long Reach": "Its moves never make contact.",
    "Liquid Ooze": "Draining HP from it hurts the drainer instead.",

    # -- speed and weather -------------------------------------------------
    "Chlorophyll": "Doubles Speed in sunshine.",
    "Swift Swim": "Doubles Speed in rain.",
    "Slush Rush": "Doubles Speed in hail.",
    "Sand Rush": "Doubles Speed in a sandstorm.",
    "Surge Surfer": "Doubles Speed on electric terrain.",
    "Speed Boost": "Speed rises every turn.",
    "Gale Wings": "Flying moves go first at full HP.",
    "Prankster": "Status moves go first.",
    "Drizzle": "Summons rain on entering battle.",
    "Drought": "Summons sunshine on entering battle.",
    "Sand Stream": "Summons a sandstorm on entering battle.",
    "Snow Warning": "Summons hail on entering battle.",
    "Cloud Nine": "Cancels all weather effects.",
    "Sand Spit": "Summons a sandstorm when hit.",
    "Ice Body": "Recovers HP in hail and is unharmed by it.",
    "Rain Dish": "Recovers HP in rain.",
    "Sand Veil": "Harder to hit in a sandstorm.",
    "Snow Cloak": "Harder to hit in hail.",

    # -- stats protected ---------------------------------------------------
    "Clear Body": "Its stats cannot be lowered by the opponent.",
    "White Smoke": "Its stats cannot be lowered by the opponent.",
    "Hyper Cutter": "Its Attack cannot be lowered.",
    "Keen Eye": "Its accuracy cannot be lowered.",
    "Big Pecks": "Its Defence cannot be lowered.",
    "Illuminate": "Its accuracy cannot be lowered, and scouting is easier.",

    # -- typing and trickery ----------------------------------------------
    "Protean": "Changes type to match the move it uses.",
    "Libero": "Changes type to match the move it uses.",
    "Pixelate": "Normal moves become Fairy and hit harder.",
    "Refrigerate": "Normal moves become Ice and hit harder.",
    "Illusion": "Enters battle disguised as another team member.",
    "Stance Change": "Swaps between Blade and Shield forms as it acts.",
    "Trace": "Copies the opponent's ability.",
    "Mold Breaker": "Ignores abilities that would blunt its moves.",
    "Scrappy": "Can hit Ghost types with Normal and Fighting moves.",
    "Infiltrator": "Ignores the opponent's barriers.",
    "Screen Cleaner": "Removes barriers from both sides on entry.",
    "Unaware": "Ignores the opponent's stat changes.",
    "Simple": "Its own stat changes count double.",
    "Contrary": "Its stat changes work the other way round.",
    "Serene Grace": "Added effects trigger twice as often.",
    "Shield Dust": "Immune to the added effects of moves.",
    "Anticipation": "Senses a dangerous move on the other side.",
    "Intimidate": "Lowers the opponent's Attack on entering battle.",
    "Pressure": "The opponent's moves cost more to use.",
    "Arena Trap": "The opponent cannot switch out.",
    "Regenerator": "Recovers HP on switching out.",
    "Anger Point": "Maxes out Attack when struck by a critical hit.",
    "Moody": "Its stats drift up and down each turn.",
    "Defeatist": "Fights at half strength below half HP.",
    "Weak Armor": "Being hit lowers its Defence and raises its Speed.",
    "Water Compaction": "Sharply raises Defence when hit by Water.",
    "Marvel Scale": "Defence rises while it has a status condition.",

    # -- custom to this game ----------------------------------------------
    "Dead Calm": "Custom: its moves ignore the weather entirely.",
    "Divine Power": "Custom: moves that are not super effective hit 25% harder.",
    "Divine Aegis": "Custom: takes a quarter less from moves that are not "
                    "super effective.",
    "Formation": "Custom: Rock moves hit 30% harder.",
    "Landlord": "Custom: Ground moves hit 30% harder.",
    "Goredrinker": "Custom: below half HP, drains half the damage it deals.",
    "Improvise": "Custom: makes the best of whatever it is handed.",
    "Instrumental": "Custom: sound moves hit 30% harder and are halved "
                    "against it; Fire and Water hurt it more.",
    "Materialize": "Custom: brings its own conditions into being.",
    "Poisonous Blow": "Custom: its strikes carry poison.",
    "Scorch": "Custom: burns a grounded target that has no status yet.",
    "Strong Roots": "Custom: roots itself -- recovering, but unable to flee.",
    "Supreme Overload": "Custom: Attack and Sp. Atk rise 10% for each "
                        "fainted team-mate.",
    "Thermal Exchange": "Custom: Fire hits raise its Attack, and it cannot "
                        "be burned.",
}
