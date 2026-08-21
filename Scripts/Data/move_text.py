"""Hand-written descriptions for moves the generated text cannot explain.

GUI/codex.py builds a description for every move out of its own data -- type,
power, stat changes, added effects, flags. That covers most of the roster, and
it can never go stale, because it is reading the move itself.

What it cannot see is a mechanic that lives in code rather than in data: Brine
doubling against a hurt target, Metronome picking at random, Guillotine's
one-hit knockout roll. Those are listed here, and anything named here is shown
*instead of* the generated lines.

So: only add an entry when the generated text is missing or misleading. A plain
attack needs nothing -- its type, power and accuracy already say everything,
and an entry that merely restates them is one more thing to keep in step.
"""

#: move name -> the whole description. Overrides the generated one.
MOVE_TEXT = {
    # -- power that depends on the target ---------------------------------
    "Brine": "Hits twice as hard when the target is below half HP.",
    "Hex": "Hits twice as hard when the target has a status condition.",
    "Venoshock": "Hits twice as hard when the target is poisoned.",
    "Facade": "Hits twice as hard while the user has a status condition.",
    "Payback": "Hits twice as hard when the user moves second.",

    # -- moves that do something other than damage ------------------------
    "Acupressure": "Sharply raises one of the user's stats, chosen at random.",
    "Clear Smog": "Removes every stat change from the target.",
    "Metronome": "Becomes a different move, chosen at random.",
    "Psyshock": "A special move, but weighed against the target's Defence.",
    "Splash": "Does nothing whatsoever.",
    "Swift": "Never misses.",
    "Techno Blast": "Its type follows whichever drive the user holds.",

    # -- the ones added for this game --------------------------------------
    "Gigaton Hammer": "Cannot be used twice in a row.",
    "Kowtow Cleave": "Never misses.",
    "Guillotine": "A one-hit knockout, but it only lands three times in ten.",
    "Bitter Blade": "The user recovers half the damage it deals.",
    "Lumina Crash": "Sharply lowers the target's Sp. Def.",

    # -- custom moves whose behaviour is not visible in their data ---------
    "Annihilation": "Enormous power and nothing held back.",
    "Depraved Shriek": "Strikes before the target can act.",
    "Enragement": "Hits back harder the more the user has taken.",
    "First Strike": "A quick opening blow.",
    "Time Pressure": "Wears the target down as the turns run on.",
    "Total Concentration": "The user focuses utterly -- and cannot flee.",
    "History Rewritten": "Disables the target's move, clears its stat changes "
                         "and leaves it confused.",
    "Empyrean Glory": "Raises the user's defences, clears the team's status "
                      "conditions and changes the weather.",
    "3-Hand Trick": "Three quick strikes from an unexpected angle.",
    "Lotus Petal": "A light, clean hit.",
    "Nichirin Sword": "A blade that cuts with the sun's own heat.",
}
