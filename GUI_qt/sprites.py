"""
Sprite loading. QMovie plays animated GIFs directly, so unlike the
Tkinter build there is no frame-decoding of our own to write or maintain.
"""

import os

from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup, QRect,
                            QPropertyAnimation, QSequentialAnimationGroup,
                            QSize, Qt)
from PySide6.QtGui import QImageReader, QMovie
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

from GUI import theme as T

DIR_PLAYER, DIR_OPPONENT = "left", "right"

#: A switch is a recall and then a send-out, in that order, and has to be over
#: before the next move resolves.
RECALL_MS = 170
SEND_MS = 230
SWITCH_MS = RECALL_MS + SEND_MS
#: What a Pokemon shrinks to as it is recalled, as a fraction of its own size.
#: Not zero: it disappears while still clearly itself, which reads as being
#: drawn back rather than as a sprite that was deleted.
SWITCH_SHRINK = 0.18
#: How far it drops as it shrinks, as a fraction of its height -- just enough
#: to pull the eye down to the platform rather than leaving it hanging.
SWITCH_SETTLE = 0.12

# -- the rest of the battle's animations ---------------------------------
#
# Deliberately short. These exist to show a player the *order* things
# happened in -- two switches inside one turn, a move that landed before a
# faint -- and an engine that has already resolved the turn is waiting
# behind them. Anything long enough to admire is long enough to annoy.
#
# One general animation per category, not per move: a distinct one for
# Stealth Rock against Spikes tells the player nothing the log does not
# already say, and would be sixty of these instead of six.
ATTACK_MS = 200
#: how far an attacker leans toward its target, as a fraction of its width
ATTACK_REACH = 0.16
#: what the type chart does to that lean. A super-effective hit should look
#: like one without the player having to read the log for it, and a resisted
#: one should look like it barely connected.
#:
#: Scaled rather than given animations of their own: one attack stays one
#: beat in the queue, so telling the player more costs no extra time. A
#: harder hit also lands faster, which is most of why it reads as harder.
ATTACK_FORCE = {"super": 1.75, "neutral": 1.0, "resist": 0.55}
#: How hard the *target* is knocked about, which is the half a player
#: actually reads. Scaling the attacker's lunge alone was far too quiet.
IMPACT_MS = 220
#: how far the target is driven back, as a fraction of its own width
IMPACT_SHOVE = 0.13
#: how far its colour drops at the worst of it
IMPACT_DIM = {"super": 0.25, "neutral": 0.55, "resist": 0.8}
FAINT_MS = 340
BUFF_MS = 300
#: how much a Pokemon swells as it buffs itself
BUFF_SWELL = 0.10
VANISH_MS = 260
FLINCH_MS = 240
#: how far a flinching Pokemon is knocked sideways, as a fraction of width
FLINCH_SHAKE = 0.05
HAZARD_MS = 420
#: how many marks are scattered at the target's feet
HAZARD_MARKS = 5


def show_sprite(label, key, side, project_root, zoom=2, target=None):
    """Point `label` (a QLabel) at the animated GIF for `key`/`side`.

    Falls back to the Pokemon's name as plain text if the asset is
    missing, rather than leaving a blank box.

    Two things matter here that didn't in the first pass: skip rebuilding
    anything if the sprite hasn't actually changed (refresh() call sites
    run on every battle-state update, many times a second, but the active
    Pokemon's sprite is usually the same frame to frame), and explicitly
    stop() the previous QMovie before dropping the reference to it. QMovie
    runs its own internal timer; replacing label._movie lets Python garbage
    collect the old QMovie while that timer could still be mid-callback,
    which is a use-after-free -- it surfaced as intermittent native
    crashes ("free(): invalid pointer") when refresh() ran rapidly.
    """
    cache_key = (key, side, zoom, target)
    if getattr(label, "_sprite_key", None) == cache_key:
        return getattr(label, "_sprite_size", None)
    label._sprite_key = cache_key

    old_movie = getattr(label, "_movie", None)
    if old_movie is not None:
        old_movie.stop()
        label._movie = None

    path = os.path.join(project_root, "Assets", "pokemon", side,
                        "%s-%s.gif" % (key, side))
    if not key or not os.path.exists(path):
        # no picture: drop the fixed size and the stretching, so the name can
        # lay out as ordinary text
        label.setScaledContents(False)
        label.setMinimumSize(0, 0)
        label.setMaximumSize(16777215, 16777215)
        label.setMovie(None)
        label.setText(key or "")
        label.setStyleSheet("color: %s; background: transparent;"
                            % T.TEXT_FAINT)
        label._sprite_size = None
        return None

    # Measure the file, not the movie. This used to jumpToFrame(0) to read
    # the native size and only then call setScaledSize -- but with CacheAll
    # frame 0 was already decoded and cached at 1x, and changing the scaled
    # size afterwards doesn't invalidate it. Every time the animation looped
    # back to frame 0 the sprite flashed at native size for one frame, on
    # every sprite in the game (it just shows up more on shorter loops).
    # Reading the size with QImageReader means the scale is set before
    # anything is decoded, so all frames are cached at the same size.
    size = QImageReader(path).size()
    movie = QMovie(path, parent=label)   # parented: Qt owns its lifetime
    movie.setCacheMode(QMovie.CacheAll)
    scaled = None
    if size.isValid() and size.width() and size.height():
        if target:
            # Fit a target x target box on the longest edge, and never
            # enlarge. Scaling by height alone blew a wide, flat Pokemon
            # (Stunfisk, 196x30) up 6.4x and 1260px across; smooth
            # enlargement is also the one thing that turns pixel art to mush,
            # and the assets are pre-scaled past the box already
            # (Test/sharpen_sprites.py), so clamping costs almost nothing.
            factor = min(1.0, float(target)
                         / max(size.width(), size.height()))
            scaled = QSize(max(1, round(size.width() * factor)),
                           max(1, round(size.height() * factor)))
        else:
            scaled = size * zoom
        # Decode at *device* resolution, lay out at logical. QMovie has no
        # setDevicePixelRatio -- it regenerates a pixmap per frame -- so the
        # frames are scaled to 1.5x and the label is told to fit its contents
        # to its (logical) rect. QLabel paints onto a device-resolution
        # backing store, so a 322px frame drawn into a 215pt box lands 1:1 on
        # the screen instead of a 215px frame being stretched to 322 by the
        # compositor. Same detail loss the portraits had, same fix.
        ratio = label.devicePixelRatioF()
        device = QSize(max(1, round(scaled.width() * ratio)),
                      max(1, round(scaled.height() * ratio)))
        movie.setScaledSize(device)
    # setScaledContents maps the device-sized frames back into the label's
    # logical rect -- which is only 1:1 if the label is exactly `scaled`. In
    # the arena _place_sprites resizes it to that, but anywhere the label is
    # bigger (the Pokedex, the compare screen) the frames were stretched to
    # fill it, which is how a 190px box ended up showing a 370px-wide, badly
    # distorted Pokemon. So the label is *given* that size here, and callers
    # centre it inside whatever fixed box they want.
    if scaled is not None:
        label.setFixedSize(scaled)
        label.setScaledContents(True)
    label.setMovie(movie)
    movie.start()
    label._movie = movie   # keep a reference alive; QLabel doesn't own it
    label._sprite_size = scaled
    return scaled


# --------------------------------------------------------------- switching
def current_frame(label):
    """A still of whatever `label` is showing, or None if it is showing text.

    Taken from the movie rather than with grab(), which renders the widget
    onto an opaque pixmap and would give the sprite a black box behind it.
    """
    movie = getattr(label, "_movie", None)
    if movie is None:
        return None
    frame = movie.currentPixmap()
    return frame if not frame.isNull() else None


def _ghost(host, picture, rect):
    """A throwaway label showing `picture`, free to be scaled and faded.

    The live sprite cannot do either. It carries a running QMovie whose frames
    were decoded once at exactly one size (see show_sprite), so resizing it
    mid-animation would soften the pixel art for as long as the animation ran,
    and a graphics effect on a playing movie is asking for trouble. A still
    picture in a label of its own has neither problem.
    """
    ghost = QLabel(host)
    #: marks it as this animation's own throwaway. A harness checking that
    #: none were left behind used to look for "any label in the arena with a
    #: pixmap", which counted anything else that legitimately lives there --
    #: the field strip's emblems, for instance.
    ghost.is_switch_ghost = True
    ghost.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    ghost.setScaledContents(True)
    ghost.setPixmap(picture)
    ghost.setStyleSheet("background: transparent;")
    ghost.setGeometry(rect)
    ghost.show()
    return ghost


def _shrunk(rect, factor, drop):
    """`rect` scaled about the middle of its own base.

    Anchoring at the base is what makes this read as a recall: the Pokemon
    collapses towards the spot it was standing on, rather than towards the
    middle of the air it happened to occupy.
    """
    width = max(2, int(rect.width() * factor))
    height = max(2, int(rect.height() * factor))
    return QRect(rect.x() + (rect.width() - width) // 2,
                 rect.y() + rect.height() - height + drop,
                 width, height)


def stop_switch(label):
    """Abandon a switch still playing on `label`, and tidy up after it.

    Switches can arrive faster than they animate -- a Pokemon can come in,
    faint and be replaced inside one turn -- so starting one has to be able
    to cut the last one short rather than leave two running on the same
    label and ghosts that never get collected.
    """
    animation = getattr(label, "_switch_anim", None)
    if animation is not None:
        label._switch_anim = None
        animation.stop()
    for name in ("_switch_ghost", "_switch_ghost_in"):
        ghost = getattr(label, name, None)
        if ghost is not None:
            setattr(label, name, None)
            ghost.setGraphicsEffect(None)   # drop the effect before the widget
            ghost.deleteLater()
    label._switch_busy = False


def animate_switch(label, still, place, coming=None):
    """Recall the Pokemon that left, then send the new one out.

    `label` is already showing the new sprite and has already been placed;
    `still` is a picture of the old one, taken before the swap.

    The two halves run in sequence rather than together, because that is the
    order the thing actually happens in: one is drawn back, then the other
    comes out. Each is a still picture shrinking towards -- or growing out of
    -- the middle of its own base, so both collapse to and rise from the spot
    on the platform the Pokemon was standing on. Scaling about the base is
    what separates this from a sprite sliding around: it reads as a recall,
    which is the idiom the game already trades in.

    The live sprite is hidden for the duration and handed back at the end,
    full size and pixel-exact, because its frames were decoded at one size
    and scaling it would go soft. `_place_sprites` honours `_switch_busy` to
    keep it hidden, so a state update landing mid-switch cannot reveal it
    early -- and there is no gap at the handover, since the last frame of the
    grow-in is the same rectangle the live sprite reappears in.
    """
    stop_switch(label)
    # Whatever is arriving takes the stage back from a knockout that was
    # holding it empty. Released before `place()` runs below, or the live
    # sprite would stay hidden after the send-out finished.
    release_hold(label)
    host = label.parentWidget()
    if host is None or not label.height():
        place()
        return None
    home = label.geometry()
    drop = max(1, int(home.height() * SWITCH_SETTLE))
    small = _shrunk(home, SWITCH_SHRINK, drop)
    # `coming` is normally read off the label, which is already showing the
    # new sprite -- but a caller replaying this later must pass the picture
    # it took at the time, or it will send out whoever is standing there now.
    coming = current_frame(label) if coming is None else coming
    if still is None and coming is None:
        return None

    whole = QSequentialAnimationGroup(label)

    # -- the one being recalled: collapse to the platform and wink out
    if still is not None:
        going = _ghost(host, still, home)
        fading = QGraphicsOpacityEffect(going)
        going.setGraphicsEffect(fading)
        recall = QParallelAnimationGroup(whole)
        shrink = QPropertyAnimation(going, b"geometry", recall)
        shrink.setDuration(RECALL_MS)
        shrink.setStartValue(home)
        shrink.setEndValue(small)
        shrink.setEasingCurve(QEasingCurve.InCubic)
        dim = QPropertyAnimation(fading, b"opacity", recall)
        dim.setDuration(RECALL_MS)
        dim.setStartValue(1.0)
        dim.setEndValue(0.0)
        # fade later than it shrinks, so it is still visibly itself on the way
        dim.setEasingCurve(QEasingCurve.InQuart)
        recall.addAnimation(shrink)
        recall.addAnimation(dim)
        whole.addAnimation(recall)
        label._switch_ghost = going

    # -- the one being sent out: grow out of the same spot, and settle
    if coming is not None:
        arriving = _ghost(host, coming, small)
        rising = QGraphicsOpacityEffect(arriving)
        arriving.setGraphicsEffect(rising)
        send = QParallelAnimationGroup(whole)
        grow = QPropertyAnimation(arriving, b"geometry", send)
        grow.setDuration(SEND_MS)
        grow.setStartValue(small)
        grow.setEndValue(home)
        # a little past full size and back: the overshoot is what makes it
        # land rather than simply stop
        grow.setEasingCurve(QEasingCurve.OutBack)
        lift = QPropertyAnimation(rising, b"opacity", send)
        lift.setDuration(min(SEND_MS, 120))
        lift.setStartValue(0.0)
        lift.setEndValue(1.0)
        send.addAnimation(grow)
        send.addAnimation(lift)
        whole.addAnimation(send)
        label._switch_ghost_in = arriving

    def done():
        # stop_switch clears _switch_busy, and place() puts the live sprite
        # back. Both happen before Qt paints again, so the handover from the
        # last grown frame to the real thing is not visible.
        stop_switch(label)
        place()

    whole.finished.connect(done)
    label._switch_anim = whole
    label._switch_busy = True
    place()                      # hides the live sprite while the ghosts run
    whole.start()
    return whole


# ======================================================================
# The other six animations.
#
# `stop_switch` above owns the switch's own slots. These use a separate set
# (`_fx_*`) so a switch and, say, a faint arriving together cannot tear down
# each other's ghosts -- and so `test_switch_anim`, which reaches for the
# switch slots by name, keeps meaning what it meant.
# ======================================================================


def release_hold(label):
    """Let the live sprite be shown again after a knockout held it down."""
    label._fx_hold = False


def stop_fx(label):
    """Abandon any effect animation on `label` and tidy up after it.

    Deliberately leaves `_fx_hold` alone: a knockout's hold outlives the
    animation that set it, and is released when something is sent out.

    Same contract as stop_switch: events can arrive faster than they play,
    so starting one has to be able to cut the last one short rather than
    leave two running on one label with ghosts nothing will collect.
    """
    animation = getattr(label, "_fx_anim", None)
    if animation is not None:
        label._fx_anim = None
        animation.stop()
    ghost = getattr(label, "_fx_ghost", None)
    if ghost is not None:
        label._fx_ghost = None
        ghost.setGraphicsEffect(None)    # drop the effect before the widget
        ghost.deleteLater()
    label._fx_busy = False


def _fx_begin(label, still=None):
    """A ghost standing exactly where the live sprite is, with it hidden.

    Returns (host, home, ghost, fade), or None when there is nothing to act
    with: no parent, no laid-out geometry yet, or no decoded frame (a
    Pokemon whose art is missing shows as text and has no picture to move).

    `still` overrides what is drawn. Anything replayed out of a queue has to
    pass the picture it took at the time, or it acts with whoever happens to
    be standing there when it finally runs.
    """
    stop_fx(label)
    host = label.parentWidget()
    frame = still if still is not None else current_frame(label)
    if host is None or not label.height() or frame is None:
        return None
    home = label.geometry()
    ghost = _ghost(host, frame, home)
    fade = QGraphicsOpacityEffect(ghost)
    ghost.setGraphicsEffect(fade)
    label._fx_ghost = ghost
    return host, home, ghost, fade


def _fx_run(label, place, whole, hold=False):
    """Hand `whole` the stage: hide the live sprite, play, then give it back.

    Unless `hold` -- a knockout keeps the stage empty afterwards rather than
    handing it back to a Pokemon that is no longer standing.
    """
    def done():
        # stop_fx clears _fx_busy and place() shows the live sprite again,
        # both before Qt paints, so the handover is not visible.
        if hold:
            label._fx_hold = True
        stop_fx(label)
        place()

    whole.finished.connect(done)
    label._fx_anim = whole
    label._fx_busy = True
    place()                      # hides the live sprite while the ghost runs
    whole.start()
    return whole


def _step(host, target, rect, ms, curve=None):
    """One geometry leg, as its own animation."""
    leg = QPropertyAnimation(target, b"geometry", host)
    leg.setDuration(ms)
    leg.setEndValue(rect)
    if curve is not None:
        leg.setEasingCurve(curve)
    return leg


def animate_attack(label, side, place, force=1.0):
    """Lean hard toward the target, then recover.

    The lunge is the whole idiom: it says *this* Pokemon acted, and which
    way it was facing when it did. Out fast and back slower, because the
    recovery is not the part worth watching.

    `force` is how hard it landed -- see ATTACK_FORCE. It scales the reach
    and shortens the whole thing, so a super-effective hit snaps and a
    resisted one barely leaves the platform.
    """
    started = _fx_begin(label)
    if started is None:
        return None
    _host, home, ghost, _fade = started
    force = max(0.2, float(force))
    reach = max(6, int(home.width() * ATTACK_REACH * force))
    # the player's Pokemon stands at the left and swings right; the
    # opponent's stands at the right and swings left
    if side != "player":
        reach = -reach
    out = QRect(home)
    out.translate(reach, -max(2, int(home.height() * 0.05)))

    # a harder hit is quicker as well as further; a weak one drags a little
    span = max(90, int(ATTACK_MS / max(0.5, force ** 0.5)))
    whole = QSequentialAnimationGroup(label)
    forth = _step(whole, ghost, out, span // 2, QEasingCurve.OutQuad)
    forth.setStartValue(home)
    back = _step(whole, ghost, home, span - span // 2,
                 QEasingCurve.InOutQuad)
    back.setStartValue(out)
    whole.addAnimation(forth)
    whole.addAnimation(back)
    return _fx_run(label, place, whole)


def animate_faint(label, place, still=None, hold=True):
    """Go down: slump to the platform and fade out, and stay down.

    Anchored at the base like a recall, so it collapses onto the spot it
    was standing on rather than sinking through it.

    `still` is the Pokemon that went down, pictured when the knockout was
    *queued*. It has to be handed in: these play out of a queue, and by the
    time a knockout reaches the front the replacement is often already on
    the label -- so reading the picture here drew the newcomer slumping and
    never showed the one that actually fainted.

    `hold` is what separates this from every other effect here. The others
    borrow the stage and hand it back; a knockout has nothing to hand back
    to, because the Pokemon is gone. Without it the sprite faded out and was
    then shown again, whole and at full colour, still standing on its
    platform -- which is not what fainting looks like. The hold is released
    by whoever is sent out next (see animate_switch).
    """
    started = _fx_begin(label, still)
    if started is None:
        if hold:
            # nothing to animate -- art missing, or no geometry yet -- but it
            # must still not be left standing there
            label._fx_hold = True
            place()
        return None
    _host, home, ghost, fade = started
    floor = _shrunk(home, 0.62, max(2, int(home.height() * 0.30)))

    whole = QParallelAnimationGroup(label)
    slump = _step(whole, ghost, floor, FAINT_MS, QEasingCurve.InQuad)
    slump.setStartValue(home)
    out = QPropertyAnimation(fade, b"opacity", whole)
    out.setDuration(FAINT_MS)
    out.setStartValue(1.0)
    out.setEndValue(0.0)
    # fades late, so it is still recognisably itself most of the way down
    out.setEasingCurve(QEasingCurve.InQuart)
    whole.addAnimation(slump)
    whole.addAnimation(out)
    return _fx_run(label, place, whole, hold=hold)


def animate_buff(label, place):
    """Swell and rise, then settle -- something went up.

    Read against animate_flinch, which is the same idea inverted: this one
    grows and lifts, that one is knocked about. A player should be able to
    tell good news from bad without reading either.
    """
    started = _fx_begin(label)
    if started is None:
        return None
    _host, home, ghost, _fade = started
    grown = QRect(home)
    grown.setWidth(int(home.width() * (1.0 + BUFF_SWELL)))
    grown.setHeight(int(home.height() * (1.0 + BUFF_SWELL)))
    # keep its feet on the platform and its middle over the same spot
    grown.moveCenter(home.center())
    grown.moveBottom(home.bottom() - max(2, int(home.height() * 0.06)))

    whole = QSequentialAnimationGroup(label)
    up = _step(whole, ghost, grown, BUFF_MS // 2, QEasingCurve.OutBack)
    up.setStartValue(home)
    down = _step(whole, ghost, home, BUFF_MS - BUFF_MS // 2,
                 QEasingCurve.InOutQuad)
    down.setStartValue(grown)
    whole.addAnimation(up)
    whole.addAnimation(down)
    return _fx_run(label, place, whole)


def animate_vanish(label, place):
    """Wink out of reach -- Fly, Dig, Dive, Bounce, Phantom Force.

    Shrinks about its own middle rather than its base: it is leaving the
    field altogether, not being drawn back to the platform, and the two
    should not read the same.
    """
    started = _fx_begin(label)
    if started is None:
        return None
    _host, home, ghost, fade = started
    gone = QRect(home)
    gone.setWidth(max(2, int(home.width() * 0.30)))
    gone.setHeight(max(2, int(home.height() * 0.30)))
    gone.moveCenter(home.center())

    whole = QParallelAnimationGroup(label)
    shrink = _step(whole, ghost, gone, VANISH_MS, QEasingCurve.InCubic)
    shrink.setStartValue(home)
    out = QPropertyAnimation(fade, b"opacity", whole)
    out.setDuration(VANISH_MS)
    out.setStartValue(1.0)
    out.setEndValue(0.0)
    out.setEasingCurve(QEasingCurve.InQuad)
    whole.addAnimation(shrink)
    whole.addAnimation(out)
    return _fx_run(label, place, whole)


def animate_flinch(label, place):
    """Take it badly: knocked side to side, and dimmed.

    This plays on whoever the status move was *aimed at*, which is what
    separates it from animate_attack -- that one is the user leaning in,
    this one is the target wearing it.
    """
    started = _fx_begin(label)
    if started is None:
        return None
    _host, home, ghost, fade = started
    shove = max(3, int(home.width() * FLINCH_SHAKE))
    left, right = QRect(home), QRect(home)
    left.translate(-shove, 0)
    right.translate(shove, 0)

    shake = QSequentialAnimationGroup(label)
    leg = FLINCH_MS // 4
    previous = home
    for rect in (right, left, right, home):
        step = _step(shake, ghost, rect, leg, QEasingCurve.OutQuad)
        step.setStartValue(previous)
        shake.addAnimation(step)
        previous = rect

    whole = QParallelAnimationGroup(label)
    dim = QSequentialAnimationGroup(whole)
    down = QPropertyAnimation(fade, b"opacity", dim)
    down.setDuration(FLINCH_MS // 2)
    down.setStartValue(1.0)
    down.setEndValue(0.55)
    up = QPropertyAnimation(fade, b"opacity", dim)
    up.setDuration(FLINCH_MS - FLINCH_MS // 2)
    up.setStartValue(0.55)
    up.setEndValue(1.0)
    dim.addAnimation(down)
    dim.addAnimation(up)
    whole.addAnimation(shake)
    whole.addAnimation(dim)
    return _fx_run(label, place, whole)


def stop_hazard(host):
    """Clear a hazard scatter still playing over `host`."""
    animation = getattr(host, "_hz_anim", None)
    if animation is not None:
        host._hz_anim = None
        animation.stop()
    for mark in getattr(host, "_hz_marks", None) or ():
        mark.setGraphicsEffect(None)
        mark.deleteLater()
    host._hz_marks = []


def animate_hazard(host, point, width):
    """Scatter something across the ground at `point`.

    Has no sprite to work with -- a hazard is laid on the *field*, and the
    Pokemon standing there may well be about to leave -- so it draws its own
    marks and takes them away again. `point` is the platform anchor the
    sprites stand their feet on; `width` is roughly how wide that platform
    reads, which is what keeps the scatter on the ground rather than
    trailing off into the backdrop.

    One animation for all four hazards on purpose: which one it was is the
    field strip's job, and it already says so permanently.
    """
    stop_hazard(host)
    if host is None or width <= 0:
        return None
    span = max(12, int(width))
    size = max(3, span // 22)
    marks, whole = [], QParallelAnimationGroup(host)
    for index in range(HAZARD_MARKS):
        # spread evenly across the platform, with the ends pulled in a
        # little so nothing lands off the edge of it
        across = (index + 0.5) / HAZARD_MARKS - 0.5
        x = int(point.x() + across * span * 0.78) - size // 2
        settled = QRect(x, int(point.y()) - size, size, size)
        start = QRect(settled)
        start.translate(0, -max(6, span // 8))

        mark = QLabel(host)
        mark.is_switch_ghost = True      # same throwaway marker, same sweeps
        mark.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        mark.setStyleSheet("background: %s; border-radius: %dpx;"
                           % (T.ACCENT, max(1, size // 2)))
        mark.setGeometry(start)
        mark.show()
        marks.append(mark)

        fade = QGraphicsOpacityEffect(mark)
        mark.setGraphicsEffect(fade)
        # staggered, so they land as a scatter rather than a row
        lag = int(HAZARD_MS * 0.22 * (index / max(1, HAZARD_MARKS - 1)))
        drop = QSequentialAnimationGroup(whole)
        if lag:
            drop.addPause(lag)
        fall = _step(drop, mark, settled, int(HAZARD_MS * 0.45),
                     QEasingCurve.OutBounce)
        fall.setStartValue(start)
        drop.addAnimation(fall)
        whole.addAnimation(drop)

        life = QSequentialAnimationGroup(whole)
        if lag:
            life.addPause(lag)
        show = QPropertyAnimation(fade, b"opacity", life)
        show.setDuration(int(HAZARD_MS * 0.15))
        show.setStartValue(0.0)
        show.setEndValue(1.0)
        life.addAnimation(show)
        life.addPause(int(HAZARD_MS * 0.30))
        hide = QPropertyAnimation(fade, b"opacity", life)
        hide.setDuration(int(HAZARD_MS * 0.40))
        hide.setStartValue(1.0)
        hide.setEndValue(0.0)
        life.addAnimation(hide)
        whole.addAnimation(life)

    host._hz_marks = marks
    whole.finished.connect(lambda: stop_hazard(host))
    host._hz_anim = whole
    whole.start()
    return whole


def animate_impact(label, side, place, hit=None):
    """The target wearing a hit: driven back, and dimmed.

    This is the half of an attack a player actually reads. Scaling the
    attacker's lean by the type chart was measured and published correctly
    and still looked like nothing -- a fifth of a sprite's width, returning
    inside two tenths of a second, on a still that looks the same either
    way. Something happening to the *target* is what says "that hurt".

    Driven *away* from whoever hit it, so the two animations read as one
    exchange rather than two wobbles. Nothing plays for a hit that did no
    damage: `hit` is None then, and a whiff should look like a whiff.
    """
    if hit is None:
        return None
    started = _fx_begin(label)
    if started is None:
        return None
    _host, home, ghost, fade = started
    force = max(0.2, float(ATTACK_FORCE.get(hit, 1.0)))
    shove = max(3, int(home.width() * IMPACT_SHOVE * force))
    # the target is driven away from the attacker: the player stands at the
    # left, so a hit *from* the player pushes right
    if side != "player":
        shove = -shove
    knocked = QRect(home)
    knocked.translate(shove, 0)

    whole = QParallelAnimationGroup(label)
    move = QSequentialAnimationGroup(whole)
    away = _step(move, ghost, knocked, IMPACT_MS // 3, QEasingCurve.OutQuad)
    away.setStartValue(home)
    back = _step(move, ghost, home, IMPACT_MS - IMPACT_MS // 3,
                 QEasingCurve.OutBack)
    back.setStartValue(knocked)
    move.addAnimation(away)
    move.addAnimation(back)

    dim = QSequentialAnimationGroup(whole)
    down = QPropertyAnimation(fade, b"opacity", dim)
    down.setDuration(IMPACT_MS // 3)
    down.setStartValue(1.0)
    down.setEndValue(IMPACT_DIM.get(hit, 0.55))
    up = QPropertyAnimation(fade, b"opacity", dim)
    up.setDuration(IMPACT_MS - IMPACT_MS // 3)
    up.setStartValue(IMPACT_DIM.get(hit, 0.55))
    up.setEndValue(1.0)
    dim.addAnimation(down)
    dim.addAnimation(up)

    whole.addAnimation(move)
    whole.addAnimation(dim)
    return _fx_run(label, place, whole)
