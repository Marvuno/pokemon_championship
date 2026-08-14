import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = sys.argv[1]; sys.path.insert(0, ROOT); os.chdir(ROOT)
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from GUI import bridge as B
B.Bridge.start = lambda self: None
from GUI_qt import sprites as S
from GUI_qt.main_window import MainWindow
app = QApplication.instance() or QApplication([])


def mon(n):
    return {"name": n, "sprite": "garchomp", "types": ["Dragon"], "tier": "High",
            "ability": ["Rough Skin"], "status": "Normal", "hp": 100, "max_hp": 100,
            "stats": [100]*6, "nominal": [100]*6, "iv": [20]*6, "base": [80]*6,
            "total": 500, "total_iv": 120, "modifier": [0]*9, "volatile": {},
            "moveset": ["Tackle"], "moves": {}, "disabled": {},
            "charging": ["", "", 0], "protecting": False, "fainted": False,
            "active": True, "index": 0}


def st(p, o):
    return {"phase": "battle", "battle_seq": 1,
            "player_side": {"nickname": "M", "strength": 400},
            "opponent_side": {"nickname": "C", "strength": 300},
            "player_team": [], "opponent_team": [],
            "field": {"turn": 1, "weather": "Clear", "auto_battle": False},
            "player": mon(p), "opponent": mon(o)}


w = MainWindow(ROOT); w.show(); w.resize(1280, 800); app.processEvents()
w._apply_state(st("Garchomp", "Metagross")); app.processEvents()
full = w.opponent_sprite.width()
w._apply_state(st("Garchomp", "Milotic")); app.processEvents()


def settle(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


out, inn = [], []
for _ in range(14):
    settle(35)
    g = getattr(w.opponent_sprite, "_switch_ghost", None)
    i = getattr(w.opponent_sprite, "_switch_ghost_in", None)
    out.append(g.width() if g is not None else None)
    inn.append(i.width() if i is not None else None)
print("full size:      %d" % full)
print("recall ghost:   %s" % out)
print("send-out ghost: %s" % inn)
vals = [v for v in inn if v]
print()
print("send-out grew:  %s  (%d -> %d)" % (len(set(vals)) > 2, vals[0], max(vals)))
print("overshot full:  %s  (peak %d vs %d)"
      % (max(vals) > full, max(vals), full))
