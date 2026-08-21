import os

# Before `import pygame`, not after: pygame reads this while it is being
# imported, so setting it on the next line left the banner already printed --
# and with the interface installed, print() is the game log, so "Hello from
# the pygame community" was going into the player's battle transcript.
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"


def _muted():
    """Is this a run that must not make a sound?

    Two ways in. `POKEMON_MUTE=1` is the explicit one. The other is
    `QT_QPA_PLATFORM=offscreen`, which every test harness here already sets
    to keep windows off the screen -- a harness plays real games, real games
    play battle music, and a test run is exactly when nobody wants the
    machine to start singing. Tying the two together means a suite is silent
    because it is a suite, with nothing to remember per harness.
    """
    if os.environ.get("POKEMON_MUTE", "").strip() not in ("", "0", "false"):
        return True
    return os.environ.get("QT_QPA_PLATFORM", "") == "offscreen"


MUTED = _muted()

if MUTED:
    # Tell SDL before pygame loads. The dummy driver is a real audio device
    # as far as pygame is concerned -- load() and play() still work, so
    # nothing below needs a second code path -- it just goes nowhere. Setting
    # this rather than skipping mixer.init() keeps the muted run on the same
    # path as a real one, which is the point of testing it.
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                                    # noqa: E402

# Only the mixer. `pygame.init()` starts every subsystem pygame has --
# display, font, joystick -- and this module plays audio and nothing else.
# The display one is the reason to care rather than a tidiness point: it
# brings up SDL's video stack, which is a window system's worth of machinery
# for a game that draws through Qt, and SDL owns any window it decides it
# needs. Measured on this machine: pygame.init() spends ~150ms on subsystems
# nothing here uses, on the worker thread, before the title screen appears.
try:
    pygame.mixer.init()
except pygame.error:
    # No audio device at all -- a locked-down machine, or a dummy driver that
    # would not start. Silence is a fine outcome; a crash on the way to the
    # title screen is not.
    MUTED = True

if not MUTED:
    pygame.mixer.music.set_volume(0.5)


def music(*, audio, loop):
    if MUTED:
        return
    pygame.mixer.music.load(audio)
    pygame.mixer.music.play(-1) if loop else pygame.mixer.music.play()


#: decoded effects, kept by path. There are only a handful of them and they are
#: played over and over -- a confirm beep on every button press.
_sounds = {}


def sound(*, audio):
    """Play a sound effect, decoding each file at most once.

    pygame.mixer.Sound(path) reads and decodes the whole file, which measured
    at 2ms a call -- on the interface thread, for a beep that plays on every
    confirmation. Everything else worth optimising in the interface came in at
    a few microseconds; this was the one real cost. Cached by path, and a file
    that will not load is remembered as unplayable rather than retried on every
    press.
    """
    if MUTED:
        return
    effect = _sounds.get(audio, False)
    if effect is False:
        try:
            effect = pygame.mixer.Sound(audio)
        except Exception:
            effect = None
        _sounds[audio] = effect
    if effect is not None:
        effect.play()
