"""
Persistent settings via Qt's own QSettings -- no custom file format, no
manual JSON read/write/migration code to maintain. One value:

  difficulty      applied at next launch. It decides which battle AI every
                  opponent uses, and that choice is wired in once when the
                  bridge installs its hooks (see GUI/bridge.py) -- swapping
                  it mid-run would change the opponent's brain halfway
                  through a match.

Three settings used to live here and are gone:

  window size     the game is borderless full screen now, always. A fixed
                  windowed size was either wider than the desktop or not the
                  whole of it, and neither was what anyone wanted.
  reduced motion  the backdrop animation is cheap and the arena no longer
                  moves anything else, so there was nothing worth switching
                  off.
  auto-advance    skipping Continue prompts hid the very screens they exist
                  to hold -- the knockout, the reward, the round result.
"""

from PySide6.QtCore import QSettings

_settings = QSettings("PokemonChampion", "GUI")

NORMAL, BEGINNER = "normal", "beginner"
#: (value, label, blurb) per option, default first
DIFFICULTIES = (
    (NORMAL, "Normal", "opponents play to their rating"),
    (BEGINNER, "Beginner", "every opponent plays simply"),
)


def get_difficulty():
    value = str(_settings.value("difficulty", NORMAL))
    return value if value in (NORMAL, BEGINNER) else NORMAL


def set_difficulty(value):
    _settings.setValue("difficulty",
                       value if value in (NORMAL, BEGINNER) else NORMAL)
