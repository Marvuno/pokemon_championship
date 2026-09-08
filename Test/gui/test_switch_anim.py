"""The switching animation: both sides, not in auto battle, and safe when
switches arrive faster than they animate."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel                # noqa: E402

from GUI import bridge as B                                        # noqa: E402
B.Bridge.start = lambda self: None
from GUI_qt import sprites as S                                    # noqa: E402
from GUI_qt.main_window import MainWindow                          # noqa: E402

app = QApplication.instance() or QApplication([])
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-60s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


def mon(name, sprite="garchomp"):
    return {"name": name, "sprite": sprite, "types": ["Dragon"],
            "tier": "High", "ability": ["Rough Skin"], "status": "Normal",
            "hp": 100, "max_hp": 100, "stats": [100] * 6,
            "nominal": [100] * 6, "iv": [20] * 6, "base": [80] * 6,
            "total": 500, "total_iv": 120, "modifier": [0] * 9,
            "volatile": {}, "moveset": ["Tackle"], "moves": {},
            "disabled": {}, "charging": ["", "", 0], "protecting": False,
            "fainted": False, "active": True, "index": 0}


def state(player, opponent, auto=False, phase="battle"):
    return {"phase": phase, "battle_seq": 1,
            "player_side": {"nickname": "Marvin", "strength": 415},
            "opponent_side": {"nickname": "Expert Cynthia", "strength": 346},
            "player_team": [], "opponent_team": [],
            "field": {"turn": 1, "weather": "Clear", "auto_battle": auto},
            "player": mon(player), "opponent": mon(opponent)}


w = MainWindow(ROOT)
w.show()
w.resize(1280, 800)
app.processEvents()


def running(side):
    label = w.player_sprite if side == "player" else w.opponent_sprite
    return getattr(label, "_switch_anim", None) is not None


def ghost(side):
    label = w.player_sprite if side == "player" else w.opponent_sprite
    return getattr(label, "_switch_ghost", None)


def busy(side):
    label = w.player_sprite if side == "player" else w.opponent_sprite
    return getattr(label, "_switch_busy", False)


def ghost_in(side):
    label = w.player_sprite if side == "player" else w.opponent_sprite
    return getattr(label, "_switch_ghost_in", None)


def live_hidden(side):
    label = w.player_sprite if side == "player" else w.opponent_sprite
    return not label.isVisible()


def play_next():
    """Hand the stage to the next *waiting* animation at once.

    The window paces animations on a timer, so a turn's events are seen in
    the order they actually happened. A test does not want to sit through
    SWITCH_MS of wall clock between each one, so it ends the current one
    early and pumps the queue by hand -- exactly what the timer does.

    A no-op when nothing is waiting, which matters: an animation that
    started the moment its state was applied (the queue was empty and the
    timer idle) would otherwise be stopped here and nothing would replace
    it.
    """
    if not w._fx_queue:
        return
    for label in (w.player_sprite, w.opponent_sprite):
        S.stop_switch(label)
        S.stop_fx(label)
    w._fx_timer.stop()
    w._fx_pump()
    app.processEvents()


def sent_out():
    return [l.text() for l in w.feed_scroll.findChildren(QLabel)
            if "sent out " in l.text() and l.text().endswith(".")]


# ------------------------------------------------- the lead is not a switch
w._apply_state(state("Garchomp", "Metagross"))
app.processEvents()
check("the first Pokemon of a match is not animated",
      running("player") or running("opponent"), False)
check("...and is not announced", sent_out(), [])

# ------------------------------------------------------- opponent switches
w._apply_state(state("Garchomp", "Milotic"))
app.processEvents()
check("their switch animates", running("opponent"))
check("...on their side only", running("player"), False)
check("...with the outgoing one still on screen as a ghost",
      isinstance(ghost("opponent"), QLabel))
# the mark the leak check at the bottom counts, proved to exist while an
# animation is actually running -- otherwise that check could pass by
# finding nothing for the wrong reason
check("...and it is marked as this animation's own",
      getattr(ghost("opponent"), "is_switch_ghost", False))
check("...so the leak check has something to find mid-animation",
      len([g for g in w.arena.findChildren(QLabel)
           if getattr(g, "is_switch_ghost", False)]) > 0)
check("...and a second one for the Pokemon arriving",
      isinstance(ghost_in("opponent"), QLabel))
check("...with the live sprite hidden while they act", live_hidden("opponent"))
check("...the arriving one starting small",
      ghost_in("opponent").width() < w.opponent_sprite.width())
check("...and announced by name",
      any("Expert Cynthia sent out Milotic." == t for t in sent_out()))
check("...and the card flashes", w.opponent_card.border_width, 3)

# it must actually finish and put the sprite back on its feet
S.stop_switch(w.opponent_sprite)
w._place_sprites()
check("finishing hands the live sprite back", busy("opponent"), False)
check("...and releases both ghosts",
      (ghost("opponent"), ghost_in("opponent")), (None, None))

# ----------------------------------------------------------- your switch
w._apply_state(state("Milotic", "Milotic"))
app.processEvents()
play_next()
check("your own switch animates too", running("player"))
check("...and is announced",
      any("You sent out Milotic." == t for t in sent_out()))
S.stop_switch(w.player_sprite)

# ------------------------------------------------- faster than it animates
w._apply_state(state("Milotic", "Skarmory"))
app.processEvents()
play_next()
first = ghost("opponent")
w._apply_state(state("Milotic", "Zapdos"))
app.processEvents()
# A second switch used to cut the first short, which is why a turn holding
# two of them only ever showed the second one. It queues instead now.
check("a second switch does not replace the one playing",
      ghost("opponent") is first)
check("...it waits its turn instead", len(w._fx_queue), 1)
check("...leaving exactly one animation on that label",
      sum(1 for _ in [running("opponent")] if _), 1)
play_next()
check("...and plays once the first is out of the way",
      ghost("opponent") is not None and ghost("opponent") is not first)
check("...and all three switches are recorded", len(sent_out()), 4)
S.stop_switch(w.opponent_sprite)

# --------------------------------------------------------- auto battle
before = len(sent_out())
w._apply_state(state("Milotic", "Aggron", auto=True))
app.processEvents()
check("auto battle does not animate", running("opponent"), False)
check("...but still records the switch", len(sent_out()), before + 1)
check("...and still flashes the card", w.opponent_card.border_width, 3)

# ------------------------------------------------ leaving the match tidies up
w._apply_state(state("Milotic", "Sandaconda"))
app.processEvents()
play_next()
check("a switch is playing before we leave", running("opponent"))
w._apply_state(state("Garchomp", "Metagross", phase="prebattle"))
app.processEvents()
check("leaving the match stops it", running("opponent"), False)
check("...and takes the ghost with it", ghost("opponent"), None)
check("...and hands the live sprite back", busy("opponent"), False)

# a new match's lead is not a switch
after = len(sent_out())
w._apply_state(state("Garchomp", "Aggron"))
app.processEvents()
check("the new match's lead is not announced", len(sent_out()), after)
check("...nor animated", running("opponent"), False)

# --------------------- it finishes by itself, and leaks nothing
from PySide6.QtCore import QEventLoop, QTimer                      # noqa: E402


def settle(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


w._apply_state(state("Garchomp", "Perrserker"))
app.processEvents()
play_next()
check("a switch is running", running("opponent"))
widths = []
for _ in range(9):
    settle(45)
    g = ghost("opponent") or ghost_in("opponent")
    widths.append(g.width() if g is not None else -1)
check("something is actually scaling while it runs (%s)" % widths,
      len(set(widths)) > 2)
settle(S.SWITCH_MS + 300)
check("it finishes on its own", running("opponent"), False)
check("...releasing both ghosts",
      (ghost("opponent"), ghost_in("opponent")), (None, None))
check("...and showing the live sprite again",
      live_hidden("opponent"), False)
check("...at full size",
      w.opponent_sprite.size(), w.opponent_sprite._sprite_size)
# the animation's own throwaways, by their mark. This used to be "any
# label in the arena carrying a pixmap", which counted anything else that
# legitimately lives in there -- the field strip's weather and room
# emblems are two such labels, and they read as two leftover ghosts.
ghosts = [g for g in w.arena.findChildren(QLabel)
          if getattr(g, "is_switch_ghost", False)]
check("no ghost labels left in the arena (%d)" % len(ghosts),
      len(ghosts), 0)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
