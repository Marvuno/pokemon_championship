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


def animate_switch(label, still, place):
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
    host = label.parentWidget()
    if host is None or not label.height():
        return None
    home = label.geometry()
    drop = max(1, int(home.height() * SWITCH_SETTLE))
    small = _shrunk(home, SWITCH_SHRINK, drop)
    coming = current_frame(label)
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
