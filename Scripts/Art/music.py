import os
import random
import re

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


#: Silence decided *after* import, which `MUTED` cannot be: it is read from
#: the environment before pygame loads, and Auto Run is chosen from the start
#: menu long after that. Kept separate rather than reassigning MUTED so the
#: two reasons for silence stay distinguishable -- one is how the process was
#: started, the other is what the player asked for.
_SILENCED = False


def silence(on=True):
    """Turn all sound off (or back on) for the rest of this session.

    Stopping matters as much as the flag. `_SILENCED` only makes *future*
    calls return early -- whatever was already streaming when it was set
    keeps going, and the title theme loops, so an Auto Run started from the
    menu would have played over the whole run. Both the music stream and the
    effect channels are stopped, and not only when `MUTED` is off: stopping
    a stream that is already silent costs nothing and removes a case to
    reason about.
    """
    global _SILENCED
    _SILENCED = bool(on)
    if not _SILENCED:
        return
    for stop in (lambda: pygame.mixer.music.stop(), lambda: pygame.mixer.stop()):
        try:
            stop()
        except Exception:
            pass


#: Where the music lives, relative to the project root.
MUSIC_DIR = os.path.join("Assets", "music")

#: What a career track is called: start1.mp3, start2.mp3, and so on.
#: Numbered strictly, so an unrelated "startup_chime.mp3" is not picked up.
START_PATTERN = re.compile(r"^start(\d+)\.mp3$", re.IGNORECASE)

#: Played when there is no numbered track to play.
START_FALLBACK = "intro.mp3"

#: Its own generator, like GUI/wallpaper.py and GUI_qt/arena.py. Choosing the
#: menu track must not draw from the game's stream: a seed is what replays a
#: battle, and a draw here would shift everything after it.
_start_random = random.Random()


def start_tracks(directory=None):
    """Every numbered career track, in numeric order.

    Read off the disk rather than listed in code, so adding start7.mp3 to
    Assets/music is the whole job -- no edit here and no entry anywhere else.
    Sorted by the number rather than by name, or start10 would sort between
    start1 and start2.
    """
    directory = MUSIC_DIR if directory is None else directory
    found = []
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    for name in names:
        match = START_PATTERN.match(name)
        if match:
            found.append((int(match.group(1)), os.path.join(directory, name)))
    return [path for _, path in sorted(found)]


def start_track(directory=None):
    """One career track at random, or the fallback when there are none.

    main.py picked with `random.randint(1, 6)`, so the range was written down
    in code and a seventh file would simply never have been played. Reading
    the folder means adding start7.mp3 to Assets/music is the whole job.
    """
    tracks = start_tracks(directory)
    if not tracks:
        return os.path.join(MUSIC_DIR if directory is None else directory,
                            START_FALLBACK)
    return _start_random.choice(tracks)


def music(*, audio, loop):
    if MUTED or _SILENCED:
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
    if MUTED or _SILENCED:
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
