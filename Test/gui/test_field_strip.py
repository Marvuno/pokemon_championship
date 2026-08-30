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

# This suite builds a real MainWindow to check the strip is not buried by the
# sprites, and a MainWindow starts the game on a worker thread -- which saves
# into Save/ like any other run. Without this it truncated a real career to
# zero bytes. Any suite that constructs a window needs it, not only the ones
# that obviously play a game. Must come before the game modules are imported.
sys.path.insert(0, os.path.join(ROOT, "Test", "gui"))
import saveguard                                                    # noqa: E402
saveguard.install(ROOT, os.path.join(ROOT, "Test", "gui", "_out"),
                  tag="field_strip")

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
print("-- the hover has to reach something that carries the words --")
# The Terrain box is a panel with an emblem and two labels inside it, so the
# widget actually under the pointer is one of those children. A tooltip set
# on the panel alone is not the one Qt asks for, and the hover did nothing
# for exactly that reason.
strip.set_state({"weather": "Rain", "weather_artificial": True,
                 "weather_turns": 2, "terrain": "Grassy", "terrain_turns": 4,
                 "terrain_note": "Grass moves hit harder.", "field": {}})
_chip = strip.chips["terrain"]
check("the Terrain box knows what to say", bool(_chip.note_heading))
check("...naming the terrain", "Grassy" in _chip.note_heading)
check("...and saying what it does", "hit harder" in _chip.note_body)
check("the Weather box knows too", bool(strip.chips["weather"].note_heading))
# No Qt tooltip on these boxes any more. FieldNote says the same words at
# once; leaving the tooltip on as well meant the desktop's black box arrived
# a second later on top of a card already saying it.
from PySide6.QtWidgets import QWidget as _QW                     # noqa: E402
check("and no tooltip is left to arrive late on top of the card",
      any(w.toolTip() for w in [_chip] + _chip.findChildren(_QW)), False)

# -- the overlay has to stay on top of the sprites -------------------------
# `_place_sprites` raises both sprite labels on every state publish, and
# `raise_()` puts a widget above *all* its siblings -- so the strip, which is
# a child of the same arena, ended up underneath them. A buried widget gets
# no hover, which is why the Terrain description never appeared no matter how
# the tooltip was set. Whether it was actually covered depended on the
# sprite's size and position, so it looked intermittent and never reproduced
# in a harness with no artwork loaded.
import os as _os                                                  # noqa: E402
_os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QPixmap as _QPixmap                     # noqa: E402
from PySide6.QtWidgets import QApplication as _QApp               # noqa: E402
from GUI_qt.main_window import MainWindow as _MW                  # noqa: E402
import sys as _sys                                                # noqa: E402
_ROOT = _os.path.abspath(_sys.argv[1] if len(_sys.argv) > 1 else ".")
_w = _MW(_ROOT)
_w.show()
_app = _QApp.instance()
_app.processEvents()
_state = {"phase": "battle",
          "field": {"weather": "Rain", "weather_turns": 2,
                    "weather_artificial": True, "terrain": "Grassy",
                    "terrain_turns": 4, "terrain_note": "Grass moves hit "
                    "harder.", "field": {}},
          "player": {"nickname": "You", "name": "P", "hp": 80, "max_hp": 100,
                     "types": ["Electric"], "status": "Normal",
                     "fainted": False},
          "opponent": {"nickname": "T", "name": "G", "hp": 90, "max_hp": 120,
                       "types": ["Dragon"], "status": "Normal",
                       "fainted": False}}
_w._apply_state(_state)
_app.processEvents()
for _label in (_w.player_sprite, _w.opponent_sprite):
    _pix = _QPixmap(900, 600)
    _pix.fill()
    _label.setPixmap(_pix)
    _label.setGeometry(0, 0, 900, 600)
    _label.show()
_w._apply_state(_state)
_app.processEvents()
_chip = _w.field_strip.chips["terrain"]
_under = _QApp.widgetAt(_chip.mapToGlobal(_chip.rect().center()))
check("a sprite over the whole arena does not bury the Terrain box",
      _under is _chip or (_under is not None and _chip.isAncestorOf(_under)),
      True)
check("...and the box it belongs to still knows the description",
      "hit harder" in _w.field_strip.chips["terrain"].note_body, True)

# -- and it explains itself the moment it is hovered ----------------------
# A Qt tooltip waits about a second, is styled by the desktop and vanishes on
# its own timer. The Pokemon hover card does none of that, and a box in the
# same arena should behave the same way.
from PySide6.QtCore import QEvent as _QEvent, QPoint as _QPoint  # noqa: E402
from PySide6.QtGui import QHoverEvent as _QHover                 # noqa: E402
_chip2 = _w.field_strip.chips["terrain"]
_inner = _chip2.findChildren(type(_chip2.value))[0]
check("the note card starts hidden", not _w.field_note.isVisible(), True)
_app.sendEvent(_inner, _QHover(_QEvent.HoverEnter, _QPoint(3, 3),
                               _QPoint(-1, -1)))
_app.processEvents()
check("hovering the box shows it straight away",
      _w.field_note.isVisible(), True)
check("...naming the terrain", "Grassy" in _w.field_note.heading.text(), True)
check("...and saying what it does",
      "hit harder" in _w.field_note.body.text(), True)
_app.sendEvent(_inner, _QHover(_QEvent.HoverLeave, _QPoint(-1, -1),
                               _QPoint(3, 3)))
_app.processEvents()
check("leaving hides it again", not _w.field_note.isVisible(), True)

print()
print("-- the window's own controls --")
check("ActionButton reports what it says",
      W.ActionButton("Play Again", Fonts()).title, "Play Again")

print()
print("FAILURES: %d" % len(FAILURES) if FAILURES else "ALL PASS")
raise SystemExit(1 if FAILURES else 0)
