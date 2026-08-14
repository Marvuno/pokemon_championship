"""Render the arena on every weather with a Pokemon on each platform, so the
placement can actually be looked at."""
import os
import sys

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication                   # noqa: E402

from GUI import bridge as B                                  # noqa: E402
B.Bridge.start = lambda self: None

from GUI_qt.main_window import MainWindow                     # noqa: E402
from GUI_qt.widgets import ActionButton, MoveCard             # noqa: E402
from GUI import theme as T                                    # noqa: E402
from PySide6.QtWidgets import QGridLayout, QHBoxLayout        # noqa: E402

app = QApplication.instance() or QApplication([])
w = MainWindow(ROOT)
w.show()


def mon(name, key, hp=100):
    return {"name": name, "sprite": key, "types": ["Normal"], "tier": "High",
            "ability": ["Levitate"], "status": "Normal", "hp": hp,
            "max_hp": 100, "stats": [], "nominal": [90] * 6, "iv": [10] * 6,
            "total": 500, "total_iv": 60, "modifier": [0] * 9, "volatile": {},
            "moveset": ["Switching"], "moves": {}, "disabled": {},
            "charging": ["", "", 0], "protecting": False, "fainted": False,
            "active": True}


PAIRS = [("Clear", "akaza", "charizard"),
         ("Rain", "poseidon", "milotic"),
         ("Sunny", "scorchrome", "torkoal"),
         ("Sandstorm", "landozer", "tyranitar"),
         ("Hail", "snowchild", "abomasnow")]

for weather, mine, theirs in PAIRS:
    w._apply_state({
        "phase": "battle",
        "player": mon("Yours", mine),
        "opponent": mon("Theirs", theirs),
        "player_side": {"nickname": "Marvin", "strength": 421, "buffs": {},
                        "hazards": {}},
        "opponent_side": {"nickname": "Rival", "strength": 300, "buffs": {},
                          "hazards": {}},
        "field": {"turn": 3, "weather": weather, "field": {}},
    })
    for _ in range(6):
        app.processEvents()
    w.grab().save(os.path.join(OUT, "weather_%s.png" % weather.lower()))

# a real move screen, so the arena is the height it actually has in battle
MOVES = [{"name": "Thunderbolt", "type": "Electric", "category": "Special",
          "power": 90, "accuracy": 1.0, "priority": 0}] * 4
grid = QGridLayout()
for i, m in enumerate(MOVES):
    grid.addWidget(MoveCard(m, str(i), w.fonts, on_click=lambda: None),
                   i // 2, i % 2)
w.actions.addLayout(grid)
extras = QHBoxLayout()
extras.addWidget(ActionButton("Switch Pokemon", w.fonts, sub="give up the turn",
                              accent=T.CYAN, on_click=lambda: None))
w.actions.addLayout(extras)
w._apply_actions_fit()
for _ in range(8):
    app.processEvents()
w._place_sprites()
app.processEvents()
w.grab().save(os.path.join(OUT, "weather_inbattle.png"))

def overlap(a, b):
    r = a.geometry().intersected(b.geometry())
    return r.width() * r.height()

lines = ["arena %dx%d" % (w.arena.width(), w.arena.height())]
for which, label in (("player", w.player_sprite),
                     ("opponent", w.opponent_sprite)):
    point = w.arena.platform_point(which)
    lines.append("%-9s anchor=(%d,%d)  sprite=%dx%d at (%d,%d) bottom=%d"
                 % (which, point.x(), point.y(),
                    label.width(), label.height(), label.x(), label.y(),
                    label.y() + label.height()))
lines.append("art placed (w,h,offx,offy): %s" % (w.arena._placed,))
lines.append("")
lines.append("overlap player sprite vs player card:   %d px2"
             % overlap(w.player_sprite, w.player_card))
lines.append("overlap player sprite vs opponent card: %d px2"
             % overlap(w.player_sprite, w.opponent_card))
lines.append("overlap opp sprite vs player card:      %d px2"
             % overlap(w.opponent_sprite, w.player_card))
lines.append("overlap opp sprite vs opponent card:    %d px2"
             % overlap(w.opponent_sprite, w.opponent_card))
lines.append("sprites overlap each other:             %d px2"
             % overlap(w.player_sprite, w.opponent_sprite))
for nm, lb in (("player", w.player_sprite), ("opponent", w.opponent_sprite)):
    g = lb.geometry()
    inside = (g.left() >= 0 and g.top() >= 0
              and g.right() <= w.arena.width()
              and g.bottom() <= w.arena.height())
    lines.append("%-9s inside the arena: %s  (%s)" % (nm, inside, g.getRect()))
with open(os.path.join(OUT, "weather.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
