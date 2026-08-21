"""The permanent weather / terrain / room boxes on the battle screen.

Three separate layers, because that is how the real games work: Rain and
Electric Terrain and Trick Room can all be up at once, and only members of
the same layer cancel each other.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

from PySide6.QtWidgets import QApplication                          # noqa: E402

app = QApplication.instance() or QApplication([])

from GUI import theme as T                                         # noqa: E402
from GUI_qt import widgets as W                                     # noqa: E402
from GUI_qt.fonts import Fonts                                      # noqa: E402

FAILURES = []


def check(what, got, want=True):
    ok = got == want
    print("%-58s %s%s" % (what, "PASS" if ok else "FAIL",
                          "" if ok else " got=%r want=%r" % (got, want)))
    if not ok:
        FAILURES.append(what)


strip = W.FieldStrip(Fonts())
strip.show()


def shown(key):
    return strip.chips[key].value.text()


print("-- what is on the field --")
strip.set_state({"weather": "Clear", "field": {}})
check("clear weather is still shown, not hidden", shown("weather"), "Clear")
# Weather is the exception: it is up in most battles, and "no weather" is
# worth knowing. A Room or a Terrain box reading None all battle is
# furniture, and this strip sits over the arena.
check("an empty room slot shows no box at all",
      strip.chips["room"].isHidden())
check("nor does an absent terrain", strip.chips["terrain"].isHidden())

strip.set_state({"weather": "Rain", "weather_artificial": True,
                 "weather_turns": 4, "field": {"Trick Room": 3}})
check("conjured weather counts itself down", shown("weather"), "Rain  4")
check("a room appears when one goes up", strip.chips["room"].isHidden(),
      False)
check("...naming itself and counting down", shown("room"), "Trick Room  3")
strip.set_state({"weather": "Rain", "weather_artificial": True,
                 "weather_turns": 4, "field": {}})
check("...and goes away when it lapses", strip.chips["room"].isHidden())

strip.set_state({"weather": "Sandstorm", "weather_artificial": False,
                 "weather_turns": 5})
check("the arena's own weather shows no countdown -- it never lifts",
      shown("weather"), "Sandstorm")

print()
print("-- the terrain box arrives with terrain --")
strip.set_state({"weather": "Clear"})
check("hidden while the engine reports no terrain",
      strip.chips["terrain"].isHidden())
strip.set_state({"weather": "Clear", "terrain": "Electric",
                 "terrain_turns": 5})
check("appears the moment it does", strip.chips["terrain"].isHidden(), False)
check("...naming it", shown("terrain"), "Electric  5")
strip.set_state({"weather": "Clear"})
check("and goes away again", strip.chips["terrain"].isHidden())

print()
print("-- the layers are independent --")
strip.set_state({"weather": "Rain", "weather_artificial": True,
                 "weather_turns": 2, "terrain": "Electric",
                 "terrain_turns": 5, "field": {"Trick Room": 4}})
check("weather, terrain and a room can all be up at once",
      [shown("weather"), shown("terrain"), shown("room")],
      ["Rain  2", "Electric  5", "Trick Room  4"])

print()
print("-- drawing --")
check("every weather the engine can set has an emblem",
      sorted(w for w in ("Clear", "Sunny", "Rain", "Sandstorm", "Hail")
             if w not in W.FIELD_ART), [])
check("so does every terrain the real games have",
      sorted(t for t in ("Electric", "Grassy", "Misty", "Psychic")
             if t not in W.FIELD_ART), [])
blank = [name for name in W.FIELD_ART
         if W.field_emblem(W.FIELD_ART[name][0], T.TEXT, 22).isNull()]
check("and every emblem actually paints something", blank, [])

# a no-op when nothing changed: this runs on every state publish
strip.set_state({"weather": "Rain", "weather_artificial": True,
                 "weather_turns": 2, "terrain": "Electric",
                 "terrain_turns": 5, "field": {"Trick Room": 4}})
before = strip.chips["weather"]._shown
strip.set_state({"weather": "Rain", "weather_artificial": True,
                 "weather_turns": 2, "terrain": "Electric",
                 "terrain_turns": 5, "field": {"Trick Room": 4}})
check("repeating the same state redraws nothing",
      strip.chips["weather"]._shown, before)

print()
print("-- the window's own controls --")
check("ActionButton reports what it says",
      W.ActionButton("Play Again", Fonts()).title, "Play Again")

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
