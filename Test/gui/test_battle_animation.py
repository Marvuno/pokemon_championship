"""The battle animations: one per category, played in order, live play only.

Seven things happen on a field and each gets a general animation rather than
a per-move one -- an attack, a switch, a knockout, a buff, a semi-invulnerable
move, a hazard going down, and a debuff landing. What this checks is that the
right one is chosen from the move's own data, that it plays on the right side,
that they queue rather than cutting each other short, and that none of it
happens when nobody is watching.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel                # noqa: E402

from GUI import bridge as B                                        # noqa: E402
B.Bridge.start = lambda self: None
from GUI.bridge import hit_shape, move_shape                       # noqa: E402
from GUI_qt import sprites as S                                    # noqa: E402
from GUI_qt.main_window import MainWindow                          # noqa: E402
from Scripts.Data.moves import list_of_moves as MOVES              # noqa: E402
from Scripts.Game import auto_run                                  # noqa: E402

app = QApplication.instance() or QApplication([])
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-62s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


# ===================================================== the move's own shape
print("-- which animation a move asks for --")
shapes = {}
for name, move in MOVES.items():
    shapes.setdefault(move_shape(move), []).append(name)

check("every move is classified", None not in shapes)
for name, want in (("Earthquake", "attack"), ("Shadow Ball", "attack"),
                   ("Swords Dance", "buff"), ("Recover", "buff"),
                   ("Toxic", "harm"), ("Thunder Wave", "harm"),
                   ("Fly", "vanish"), ("Dig", "vanish"),
                   ("Stealth Rock", "hazard"), ("Toxic Spikes", "hazard")):
    if name in MOVES:
        check("  %-14s -> %s" % (name, want), move_shape(MOVES[name]), want)

# all four hazards, not just the two spot-checked above
check("all four entry hazards are hazards",
      sorted(shapes.get("hazard", [])),
      ["Spikes", "Stealth Rock", "Sticky Web", "Toxic Spikes"])
# a move object is what this reads; anything else must decline rather than guess
check("the switching pseudo-move asks for nothing",
      move_shape("Switching"), None)
check("...and so does nothing at all", move_shape(None), None)


# ============================================================== the window
def mon(name, fainted=False, sprite="garchomp"):
    return {"name": name, "sprite": sprite, "types": ["Dragon"],
            "tier": "High", "ability": ["Rough Skin"], "status": "Normal",
            "hp": 0 if fainted else 100, "max_hp": 100, "stats": [100] * 6,
            "nominal": [100] * 6, "iv": [20] * 6, "base": [80] * 6,
            "total": 500, "total_iv": 120, "modifier": [0] * 9,
            "volatile": {}, "moveset": ["Tackle"], "moves": {},
            "disabled": {}, "charging": ["", "", 0], "protecting": False,
            "fainted": fainted, "active": True, "index": 0}


def state(player, opponent, auto=False, phase="battle", teams=None,
          down=()):
    """`down` names the sides whose *active* Pokemon is fainted.

    snap_pokemon marks the one on the field as well as the team entry, so a
    fixture that only faints the team member is not what the window is ever
    handed in a real battle.
    """
    mine, theirs = (teams or ([], []))
    return {"phase": phase, "battle_seq": 1,
            "player_side": {"nickname": "Marvin", "strength": 415},
            "opponent_side": {"nickname": "Expert Cynthia", "strength": 346},
            "player_team": mine, "opponent_team": theirs,
            "field": {"turn": 1, "weather": "Clear", "auto_battle": auto},
            "player": mon(player, fainted="player" in down),
            "opponent": mon(opponent, fainted="opponent" in down)}


w = MainWindow(ROOT)
w.show()
w.resize(1280, 800)
app.processEvents()
w._apply_state(state("Garchomp", "Metagross"))
app.processEvents()


def banner(kind, side, actor, shape=None, text=None, hit=None):
    event = {"kind": kind, "side": side, "actor": actor,
             "text": text or "%s did something." % actor}
    if shape is not None:
        event["shape"] = shape
    if hit is not None:
        event["hit"] = hit
    w._show_banner(event)
    app.processEvents()


def quiet():
    """Put the stage back: nothing playing, nothing queued."""
    for label in (w.player_sprite, w.opponent_sprite):
        S.stop_switch(label)
        S.stop_fx(label)
    w._fx_clear()
    w._place_sprites()
    app.processEvents()


def playing(side):
    label = w.player_sprite if side == "player" else w.opponent_sprite
    return getattr(label, "_fx_anim", None) is not None


print()
print("-- how hard the hit landed --")


class Hit:
    def __init__(self, damage, multiplier, crit=False):
        self.damage = damage
        self.type_effectiveness = multiplier
        self.critical_hit = crit


for label, made, want in (
        ("4x", Hit(50, 4), "super"),
        ("2x", Hit(50, 2), "super"),
        ("1x", Hit(50, 1), "neutral"),
        ("0.5x", Hit(50, 0.5), "resist"),
        ("a crit at 1x", Hit(50, 1, True), "super"),
        # A Move is shared by everybody and keeps its effectiveness between
        # uses, so a move that *missed* still carries the last multiplier it
        # was calculated against. Damage dealt is what proves it is fresh.
        ("a miss with a stale 4x on it", Hit(0, 4), None),
        ("an immunity", Hit(0, 0), None),
        ("a status move", Hit(0, None), None)):
    check("  %-28s -> %s" % (label, want), hit_shape(made), want)
check("  a bare string reports nothing", hit_shape("Switching"), None)

# and it reaches the picture
quiet()
soft = S.animate_attack(w.player_sprite, "player", w._place_sprites,
                        force=S.ATTACK_FORCE["resist"])
soft_reach = soft.animationAt(0).endValue().x() if soft else None
soft_span = soft.duration() if soft else None
quiet()
hard = S.animate_attack(w.player_sprite, "player", w._place_sprites,
                        force=S.ATTACK_FORCE["super"])
hard_reach = hard.animationAt(0).endValue().x() if hard else None
hard_span = hard.duration() if hard else None
quiet()
check("a super-effective hit reaches further than a resisted one",
      hard_reach is not None and soft_reach is not None
      and hard_reach > soft_reach)
check("...and gets there quicker",
      hard_span is not None and soft_span is not None
      and hard_span < soft_span)


print()
print("-- each one plays, and on the right side --")
for shape, side, expect in (("attack", "player", "player"),
                            ("attack", "opponent", "opponent"),
                            ("buff", "player", "player"),
                            ("vanish", "player", "player"),
                            # a debuff lands on the one it was aimed at
                            ("harm", "player", "opponent"),
                            ("harm", "opponent", "player")):
    quiet()
    banner("move", side, "Garchomp", shape=shape)
    other = "opponent" if expect == "player" else "player"
    check("%-7s used by %-8s plays on %s" % (shape, side, expect),
          playing(expect))
    check("  ...and not on the other side", playing(other), False)

quiet()
banner("move", "player", "Garchomp", shape="attack")
check("an attack leaves a ghost to act with",
      isinstance(getattr(w.player_sprite, "_fx_ghost", None), QLabel))
check("...marked as a throwaway",
      getattr(w.player_sprite._fx_ghost, "is_switch_ghost", False))
check("...with the live sprite hidden while it runs",
      not w.player_sprite.isVisible())

# a hazard is laid on the ground, so it has no sprite and marks its own
quiet()
banner("move", "player", "Garchomp", shape="hazard")
marks = getattr(w.arena, "_hz_marks", None) or []
check("a hazard scatters marks on the ground", len(marks), S.HAZARD_MARKS)
check("...and none of them is a sprite animation", playing("opponent"), False)
S.stop_hazard(w.arena)
check("...cleared on demand", len(getattr(w.arena, "_hz_marks", None) or []), 0)


print()
print("-- a knockout is animated on the side that lost it --")
quiet()
w._apply_state(state("Garchomp", "Metagross",
                     teams=([mon("Garchomp")],
                            [mon("Metagross", fainted=True)]),
                     down=("opponent",)))
app.processEvents()
quiet()
banner("faint", None, "Metagross", text="Metagross fainted!")
check("their knockout plays on their side", playing("opponent"))
check("...not on yours", playing("player"), False)
check("the side is found from the team even with none given",
      w._side_of_name("Metagross"), "opponent")
check("...and an unknown name finds nobody", w._side_of_name("Nobody"), None)


print()
print("-- a knockout stays down, and is never recalled --")
from PySide6.QtCore import QEventLoop, QTimer                      # noqa: E402


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


quiet()
# the teams matter: a knockout is reported with a name and no side, and the
# side is looked up in them (see _side_of_name)
w._apply_state(state("Garchomp", "Metagross",
                     teams=([mon("Garchomp")],
                            [mon("Metagross", fainted=True)]),
                     down=("opponent",)))
app.processEvents()
banner("faint", None, "Metagross", text="Metagross fainted!")
check("the knockout is queued against a side", playing("opponent"))
wait(S.FAINT_MS + 250)
# The bug this covers: the faint faded the sprite out and then handed the
# stage straight back, so the Pokemon reappeared whole and at full colour,
# still standing on its platform.
check("after fainting the sprite is not shown again",
      w.opponent_sprite.isVisible(), False)
check("...it is held down rather than merely mid-animation",
      getattr(w.opponent_sprite, "_fx_hold", False))
check("...and nothing is still playing", playing("opponent"), False)

# ...and the replacement does not withdraw the corpse first
w._apply_state(state("Garchomp", "Milotic",
                     teams=([mon("Garchomp")],
                            [mon("Metagross", fainted=True), mon("Milotic")])))
app.processEvents()
check("the replacement plays", w.opponent_sprite._switch_anim is not None)
check("...with no recall for the one that fainted",
      getattr(w.opponent_sprite, "_switch_ghost", None), None)
check("...only a send-out for the one arriving",
      isinstance(getattr(w.opponent_sprite, "_switch_ghost_in", None), QLabel))
check("...and it is shorter than a switch between two live Pokemon",
      w.opponent_sprite._switch_anim.duration() < S.SWITCH_MS)
wait(S.SWITCH_MS + 250)
check("...leaving the hold released", getattr(w.opponent_sprite,
                                              "_fx_hold", False), False)
check("...and the new Pokemon on the field",
      w.opponent_sprite.isVisible())

# a switch between two Pokemon that are both still standing keeps its recall
quiet()
w._apply_state(state("Garchomp", "Skarmory"))
app.processEvents()
w._apply_state(state("Garchomp", "Zapdos"))
app.processEvents()
check("an ordinary switch still recalls the one leaving",
      isinstance(getattr(w.opponent_sprite, "_switch_ghost", None), QLabel))


print()
print("-- a living Pokemon is never left hidden --")
# The fault this covers: a knockout is announced during the move, before the
# publish that marks anybody fainted. Attributing it by name alone could pick
# the side that had *not* fainted, hold its sprite down, and never release it
# -- the Pokemon vanished for the rest of the match.
quiet()
both = ([mon("Garchomp")], [mon("Garchomp", fainted=True)])
w._apply_state(state("Garchomp", "Garchomp", teams=both))
app.processEvents()
check("with the same species on both sides, the one on the field is meant",
      w._side_of_name("Garchomp"), "opponent")

quiet()
w._apply_state(state("Garchomp", "Metagross",
                     teams=([mon("Garchomp")], [mon("Metagross")])))
app.processEvents()
check("a name on neither field nor fainted list resolves to nobody",
      w._side_of_name("Milotic"), None)
banner("faint", None, "Milotic", text="Milotic fainted!")
check("...so nothing is animated for it",
      playing("player") or playing("opponent"), False)
check("...and neither sprite is held",
      (getattr(w.player_sprite, "_fx_hold", False),
       getattr(w.opponent_sprite, "_fx_hold", False)), (False, False))

# the backstop: whatever set a hold, a living Pokemon takes the field back
quiet()
w.player_sprite._fx_hold = True
w._place_sprites()
app.processEvents()
check("a hold does hide the sprite", w.player_sprite.isVisible(), False)
w._apply_state(state("Garchomp", "Metagross",
                     teams=([mon("Garchomp")], [mon("Metagross")])))
app.processEvents()
check("...but the next publish gives a living Pokemon the field back",
      getattr(w.player_sprite, "_fx_hold", False), False)
check("...and shows it", w.player_sprite.isVisible())

# a knockout whose replacement is already out must not hide the newcomer
quiet()
w._apply_state(state("Garchomp", "Metagross",
                     teams=([mon("Garchomp")],
                            [mon("Milotic", fainted=True),
                             mon("Metagross")])))
app.processEvents()
w._fx_enqueue("faint", "opponent")
wait(S.FAINT_MS + 250)
check("a late knockout does not hold down the Pokemon that replaced it",
      getattr(w.opponent_sprite, "_fx_hold", False), False)
check("...which stays on the field", w.opponent_sprite.isVisible())


print()
print("-- the target wears the hit --")
quiet()
banner("move", "player", "Garchomp", shape="attack", hit="super")
check("an attack plays on the user", playing("player"))
check("...and on the target too, at the same time", playing("opponent"))
soft_ghost = getattr(w.opponent_sprite, "_fx_ghost", None)
check("...with a ghost to knock about", isinstance(soft_ghost, QLabel))

# a whiff must look like a whiff
quiet()
banner("move", "player", "Garchomp", shape="attack", hit=None)
check("a hit that did nothing does not strike the target",
      playing("opponent"), False)
check("...though the user still swings", playing("player"))

# harder matchups drive the target further
quiet()
weak = S.animate_impact(w.opponent_sprite, "player", w._place_sprites,
                        hit="resist")
weak_x = weak.animationAt(0).animationAt(0).endValue().x() if weak else None
quiet()
strong = S.animate_impact(w.opponent_sprite, "player", w._place_sprites,
                          hit="super")
strong_x = (strong.animationAt(0).animationAt(0).endValue().x()
            if strong else None)
quiet()
check("a super-effective hit drives the target further than a resisted one",
      strong_x is not None and weak_x is not None and strong_x > weak_x)
check("...and nothing is played for a hit that never landed",
      S.animate_impact(w.opponent_sprite, "player", w._place_sprites,
                       hit=None), None)


print()
print("-- a knockout draws the Pokemon that fainted --")
# The fault: these play out of a queue, and by the time a knockout reached
# the front the replacement was often already on the label -- so the
# newcomer slumped and the one that actually fainted was never drawn.
quiet()
w._apply_state(state("Garchomp", "Metagross",
                     teams=([mon("Garchomp")], [mon("Metagross")])))
app.processEvents()
taken = w._frame_of("opponent")
check("a picture of the one standing there can be taken", taken is not None)
# now the replacement arrives, and only then does the knockout play
w._apply_state(state("Garchomp", "Milotic",
                     teams=([mon("Garchomp")],
                            [mon("Metagross", fainted=True),
                             mon("Milotic")])))
app.processEvents()
quiet()
played = S.animate_faint(w.opponent_sprite, w._place_sprites, still=taken,
                         hold=False)
check("the knockout plays with the picture it was handed",
      played is not None)
check("...rather than whoever is standing there now",
      isinstance(getattr(w.opponent_sprite, "_fx_ghost", None), QLabel))
quiet()


print()
print("-- and never across a change of identity --")
# Illusion wears a team-mate's face and drops it the moment a hit lands, so
# the sprite becomes a different Pokemon inside a turn. A ghost of the
# disguise moving about while the real one appears underneath is what made
# that ability unreadable.
# Built by hand: the identity that matters is the *sprite*, and the `mon`
# helper gives both sides the same one. And quiet() after the state, because
# a state change queues a switch -- which holds the timer, so the banner
# below would only queue and never play.
disguised = dict(state("Garchomp", "Metagross"))
disguised["opponent"] = mon("Metagross", sprite="metagross")
revealed = dict(state("Garchomp", "Metagross"))
revealed["opponent"] = mon("Zoroark", sprite="zoroark")

quiet()
w._apply_state(disguised)
app.processEvents()
quiet()
banner("move", "opponent", "Metagross", shape="attack", hit="neutral")
check("an effect is playing", playing("opponent"))
w._apply_state(revealed)                      # the disguise breaks
app.processEvents()
check("...and is dropped when its Pokemon becomes another",
      playing("opponent"), False)
check("...leaving the real sprite on the field",
      w.opponent_sprite.isVisible())

# ...and an effect is *not* dropped when the sprite is unchanged
quiet()
w._apply_state(disguised)
app.processEvents()
quiet()
banner("move", "opponent", "Metagross", shape="attack", hit="neutral")
w._apply_state(disguised)
app.processEvents()
check("an effect survives a publish that changes nothing",
      playing("opponent"))
quiet()


print()
print("-- they queue instead of cutting each other short --")
quiet()
banner("move", "player", "Garchomp", shape="attack")
check("the first plays at once", playing("player"))
first = w.player_sprite._fx_ghost
banner("move", "player", "Garchomp", shape="buff")
banner("move", "player", "Garchomp", shape="vanish")
check("...the next two wait their turn", len(w._fx_queue), 2)
check("...and the first is still the one on screen",
      w.player_sprite._fx_ghost is first)

# the queue cannot grow without bound: the engine has resolved the turn and
# is waiting behind these
quiet()
banner("move", "player", "Garchomp", shape="attack")
for _ in range(40):
    banner("move", "player", "Garchomp", shape="buff")
check("a backlog is capped rather than followed for ever",
      len(w._fx_queue) <= w.FX_QUEUE_MAX)


print()
print("-- nobody watching, nothing played --")
quiet()
w._apply_state(state("Garchomp", "Metagross", auto=True))
app.processEvents()
quiet()
banner("move", "player", "Garchomp", shape="attack")
check("auto battle does not animate", playing("player"), False)
check("...and queues nothing", len(w._fx_queue), 0)

w._apply_state(state("Garchomp", "Metagross"))
app.processEvents()
quiet()
auto_run.state.active = True
try:
    banner("move", "player", "Garchomp", shape="attack")
    check("an unattended run does not animate", playing("player"), False)
    check("...and queues nothing", len(w._fx_queue), 0)
finally:
    auto_run.state.active = False

quiet()
banner("move", "player", "Garchomp", shape="attack")
check("and it animates again once a person is back", playing("player"))


print()
print("-- it finishes by itself and leaves nothing behind --")
from PySide6.QtCore import QEventLoop, QTimer                      # noqa: E402


def settle(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


quiet()
banner("move", "player", "Garchomp", shape="attack")
widths = []
for _ in range(8):
    settle(30)
    ghost = getattr(w.player_sprite, "_fx_ghost", None)
    widths.append(ghost.x() if ghost is not None else -1)
check("something actually moves while it runs (%s)" % widths,
      len(set(widths)) > 2)
settle(S.ATTACK_MS + 300)
check("it finishes on its own", playing("player"), False)
check("...releasing its ghost",
      getattr(w.player_sprite, "_fx_ghost", None), None)
check("...and showing the live sprite again", w.player_sprite.isVisible())
check("...at full size",
      w.player_sprite.size(), w.player_sprite._sprite_size)

# a whole turn's worth, drained by the timer alone
quiet()
for shape in ("attack", "harm", "buff", "vanish"):
    banner("move", "player", "Garchomp", shape=shape)
settle(S.ATTACK_MS + S.FLINCH_MS + S.BUFF_MS + S.VANISH_MS + 900)
check("a turn's queue drains without help", len(w._fx_queue), 0)
check("...leaving nothing playing",
      playing("player") or playing("opponent"), False)
leftovers = [g for g in w.arena.findChildren(QLabel)
             if getattr(g, "is_switch_ghost", False)]
check("...and no ghosts in the arena (%d)" % len(leftovers),
      len(leftovers), 0)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
