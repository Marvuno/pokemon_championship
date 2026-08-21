"""
Terminal colour codes, kept only as names.

The game is a windowed application now: every one of these was an ANSI escape
meant for a console, and the interface strips escapes out of everything it is
handed before showing it (see GUI/ansi.py -- `strip` is the only thing anything
imports from it). So the codes were being generated and thrown away.

They are empty strings rather than deleted outright because they appear inside
around a hundred f-strings across the engine. Emptying them removes the colour
without touching a single one of those call sites, which is a change that
cannot break a format string; deleting the names would mean editing all of them
for no visible difference.
"""

CEND = ''
CBOLD = ''
CITALIC = ''
CURL = ''
CBLINK = ''
CBLINK2 = ''
CSELECTED = ''
CBLACK = ''
CRED = ''
CGREEN = ''
CYELLOW = ''
CBLUE = ''
CVIOLET = ''
CBEIGE = ''
CWHITE = ''
CGREY = ''
CBLACKBG = ''
CREDBG = ''
CGREENBG = ''
CYELLOWBG = ''
CBLUEBG = ''
CVIOLETBG = ''
CBEIGEBG = ''
CWHITEBG = ''
CRED2 = ''
CGREEN2 = ''
CYELLOW2 = ''
CBLUE2 = ''
CVIOLET2 = ''
CBEIGE2 = ''
CWHITE2 = ''
CGREYBG = ''
CREDBG2 = ''
CGREENBG2 = ''
CYELLOWBG2 = ''
CBLUEBG2 = ''
CVIOLETBG2 = ''
CBEIGEBG2 = ''
CWHITEBG2 = ''
