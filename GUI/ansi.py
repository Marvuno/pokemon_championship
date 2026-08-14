"""
Turn the game's ANSI-coloured terminal output into styled segments.

The game narrates battles with \\33[..m escapes (green for your side, red for
the enemy, violet for special events). That colour carries real meaning, so the
log panel keeps it rather than stripping it.
"""

import re

ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")
ANSI_STRIP_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip(text):
    """Plain text with all escapes removed -- used for parsing prompts."""
    return ANSI_STRIP_RE.sub("", text)


class Style:
    """Immutable-ish text style, hashable so it can key a lookup table."""

    __slots__ = ("fg", "bold", "italic", "underline")

    def __init__(self, fg=None, bold=False, italic=False, underline=False):
        self.fg = fg
        self.bold = bold
        self.italic = italic
        self.underline = underline

    def key(self):
        return (self.fg or "-", self.bold, self.italic, self.underline)

    def copy(self):
        return Style(self.fg, self.bold, self.italic, self.underline)

    def apply(self, codes):
        """Apply a list of SGR integer codes, returning a new Style."""
        out = self.copy()
        for code in codes:
            if code == 0:
                out = Style()
            elif code == 1:
                out.bold = True
            elif code == 3:
                out.italic = True
            elif code == 4:
                out.underline = True
            elif code == 22:
                out.bold = False
            elif code == 23:
                out.italic = False
            elif code == 24:
                out.underline = False
            elif code == 39:
                out.fg = None
            elif 30 <= code <= 37 or 90 <= code <= 97:
                out.fg = code
            # background codes (40-47/100-107) are ignored on purpose: the
            # game only uses them incidentally and inverted blocks would
            # fight the panel design.
        return out


def segments(text, style=None):
    """Split text into [(chunk, Style), ...], carrying style across calls.

    Returns (list_of_segments, trailing_style) so a streaming log can keep
    the colour state between writes -- the game frequently prints a colour
    code and its reset in separate print() calls.
    """
    cur = style.copy() if style else Style()
    out = []
    pos = 0
    for m in ANSI_RE.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], cur))
        raw = m.group(1)
        if raw == "":
            codes = [0]
        else:
            codes = []
            for part in raw.split(";"):
                if part.isdigit():
                    codes.append(int(part))
        cur = cur.apply(codes)
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], cur))
    return out, cur
