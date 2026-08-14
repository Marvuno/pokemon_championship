"""
Visual language for Pokemon Champion.

Design direction: "championship broadcast overlay". This is not a GameBoy
tribute -- the game underneath is a 32-player bracket with elo ratings,
hazards, weather and stat telemetry, so the interface is styled like the
on-screen graphics of a competitive match telecast: dark stadium navy,
hairline panels, a live scoreboard strip, and type-coded action cards.

Everything visual is defined here so it can be retuned in one place.
"""

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
# A near-neutral dark ground, so the colour in the interface comes from its
# *content* -- type chips, HP, both sides' greens and reds, the feed, the
# flags. Saturating the furniture itself as well (everything cobalt) made the
# screen louder without making it more colourful: one hue everywhere reads as
# monochrome no matter how bright it is.
BG            = "#0E1420"   # charcoal navy, the room the match happens in
PANEL         = "#19202E"   # slate panel
PANEL_RAISED  = "#232C3D"   # cards sitting on a panel
PANEL_SUNK    = "#111725"   # log well, inputs
LINE          = "#38455C"   # quiet border; colour goes on what you interact
LINE_SOFT     = "#252E3E"

TEXT          = "#F4F7FC"
TEXT_DIM      = "#AFBDD2"
TEXT_FAINT    = "#7A8798"

PLAYER        = "#3FD66B"   # your side
PLAYER_DEEP   = "#177A38"
OPPONENT      = "#FF3B3B"   # Poke Ball red, the enemy side
OPPONENT_DEEP = "#96130F"
ACCENT        = "#FFCB05"   # the franchise's own gold: the thing you click
ACCENT_DEEP   = "#A97F00"
VIOLET        = "#B569FF"
CYAN          = "#2FC3FF"

HP_GOOD       = "#3FD66B"   # the in-game HP bar's own three states
HP_WARN       = "#FFCB05"
HP_CRIT       = "#FF3B3B"
HP_TRACK      = "#141B29"

# --------------------------------------------------------------------------
# ANSI -> screen. The game narrates in terminal colours; keep the meaning.
# --------------------------------------------------------------------------
ANSI_COLORS = {
    30: "#6C86BC", 31: "#F0574F", 32: "#4ECB77", 33: "#F0C33C",
    34: "#7FA6FF", 35: "#BE86EC", 36: "#4FC9EE", 37: "#DDE8FF",
    90: TEXT_FAINT,
    91: OPPONENT, 92: PLAYER, 93: ACCENT, 94: "#7FA6FF",
    95: VIOLET, 96: CYAN, 97: "#FFFFFF",
}

# --------------------------------------------------------------------------
# type identity -- the single most useful colour cue in the whole interface
# --------------------------------------------------------------------------
# The series' canonical type colours, lifted a little in value so each one
# still reads against the cobalt panels (the official Normal, Dark and Rock
# are muddy browns that disappear on a dark ground).
TYPE_COLORS = {
    "Normal": "#C6C6A7", "Fire": "#FF9741", "Water": "#6390F0",
    "Electric": "#F7D02C", "Grass": "#7AC74C", "Ice": "#96D9D6",
    "Fighting": "#E0483F", "Poison": "#C452C2", "Ground": "#E2BF65",
    "Flying": "#A98FF3", "Psychic": "#F95587", "Bug": "#BBD030",
    "Rock": "#CDB94E", "Ghost": "#9575C9", "Dragon": "#8155FC",
    "Dark": "#A08776", "Steel": "#B7B7CE", "Fairy": "#F0A2C6",
}

CATEGORY_GLYPH = {"Physical": "PHY", "Special": "SPC", "Status": "STA"}

WEATHER_GLYPH = {
    "Clear": "\u25CB", "Rain": "\u2614", "Sunny": "\u2600",
    "Sandstorm": "\u25A6", "Hail": "\u2744",
}

STATUS_COLORS = {
    "Normal": TEXT_FAINT, "Poison": "#C452C2", "BadPoison": "#9B32B0",
    "Paralysis": "#F7D02C", "Burn": "#FF9741", "Sleep": "#A98FF3",
    "Freeze": "#96D9D6", "Fainted": "#6B82AE",
}
STATUS_SHORT = {
    "Poison": "PSN", "BadPoison": "TOX", "Paralysis": "PAR",
    "Burn": "BRN", "Sleep": "SLP", "Freeze": "FRZ", "Fainted": "FNT",
}

# --------------------------------------------------------------------------
# typography
# --------------------------------------------------------------------------
# Preference chains -- resolved against installed families at startup so the
# app looks intentional on Windows, macOS and Linux without shipping fonts.
FONT_STACKS = {
    "display": ["Bahnschrift SemiBold Condensed", "Bahnschrift Condensed",
                "Oswald", "Archivo Narrow", "Segoe UI Semibold",
                "Helvetica Neue", "DejaVu Sans", "Helvetica"],
    "ui":      ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter",
                "DejaVu Sans", "Helvetica"],
    "mono":    ["Cascadia Mono", "Consolas", "SF Mono", "Menlo",
                "JetBrains Mono", "DejaVu Sans Mono", "Courier New"],
}

# point sizes -- bumped up from the Tk-era scale, which read as too small;
# everything here is also multiplied by the user's UI-scale setting
# (see GUI_qt/fonts.py), so retuning readability again means editing one
# number here rather than hunting through widget code.
SZ_EYEBROW = 9
#: the in-battle numbers (HP, stat stages) -- a readout, not prose, and it
#: was competing with the Pokemon's name for attention
SZ_TINY    = 10
SZ_SMALL   = 11.5
SZ_BODY    = 13
SZ_LEAD    = 17
SZ_TITLE   = 22
SZ_HERO    = 30

PAD = 10          # base spacing unit
RADIUS_SM = 8     # chips, small controls
RADIUS_MD = 12    # cards
RADIUS_LG = 16    # panels (arena, action bar, dialogs)


def hp_color(fraction):
    if fraction <= 0.20:
        return HP_CRIT
    if fraction <= 0.50:
        return HP_WARN
    return HP_GOOD


def type_color(name):
    return TYPE_COLORS.get(name, TEXT_DIM)


#: Data/pokemon.csv's rarity bands, cool-to-hot so a glance at a chip reads
#: as "how good is this one" without having to know the ordering.
TIER_COLORS = {
    "Very Low":   TEXT_FAINT,
    "Low":        TEXT_DIM,
    "Medium":     CYAN,
    "High":       PLAYER,
    "Very High":  ACCENT,
    "Ultra High": VIOLET,
    "Boss":       OPPONENT,
    "Secret":     OPPONENT,
}


def tier_color(name):
    return TIER_COLORS.get(name, TEXT_DIM)


def mix(hex_a, hex_b, t):
    """Blend two hex colours; t=0 gives a, t=1 gives b."""
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    c = [round(x + (y - x) * t) for x, y in zip(a, b)]
    return "#%02X%02X%02X" % tuple(c)
