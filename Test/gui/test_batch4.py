"""The lightbox, the switch indicator, the battle-text scrub, the move-effect
wording, the opponent panel, the credits line and the Scouting rename."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel                # noqa: E402

from Scripts.Battle.battle_cycle import *                         # noqa: E402,F401,F403
from Scripts.Data.competitors import list_of_competitors          # noqa: E402
from Scripts.Data.moves import list_of_moves                      # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                  # noqa: E402
import Scripts.Game.before_battle as BEFORE                       # noqa: E402

from GUI import codex                                             # noqa: E402
from GUI import bridge as B                                       # noqa: E402
B.Bridge.start = lambda self: None
from GUI_qt import main_window as MW                              # noqa: E402
from GUI_qt.fonts import Fonts                                    # noqa: E402
from GUI_qt.panels import ArtLightbox, CreditsDialog              # noqa: E402
from GUI_qt.pokedex import PokedexDialog                          # noqa: E402

app = QApplication.instance() or QApplication([])
fonts = Fonts()
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


def texts(widget):
    return [c.text() for c in widget.findChildren(QLabel) if c.text()]


# ------------------------------------------------------- 3. battle text
print("== battle text ==")
KEEP = ["Garchomp used Earthquake.", "Super effective!", "STAB!",
        "Marvin sent out Milotic.", "Turn 3", "The Sky is Clear. [Clear]",
        "[(0, 'Pikachu'), (1, 'Gengar')]"]
DROP = ["Status: Normal",
        "Stats Change: [0, 0, 0, 0, 0, 0, 0, 0, 0]",
        "Volatile Status: ['Grounded', 'Turn: 3']",
        "In-battle Effects: [] || Entry Hazard: [] || Protection: [0, 0]",
        "Charging: ['', '', 0] || Disabled: {}",
        "Base Stats: ['HP: 108', 'Atk: 130']",
        "|" + "█" * 20 + "| 100%", "73", "-->", "--> "]
check("narration is kept", [l for l in KEEP if B.is_state_dump(l)], [])
check("the terminal's readout is dropped",
      [l for l in DROP if not B.is_state_dump(l)], [])
check("a mixed chunk keeps only the narration",
      B.scrub_state_dumps("Garchomp used Earthquake."
                          + chr(10) + "Status: Normal"
                          + chr(10) + "Super effective!"),
      "Garchomp used Earthquake." + chr(10) + "Super effective!")
check("an all-readout chunk disappears entirely",
      B.scrub_state_dumps("Status: Normal" + chr(10) + "73"), "")
import inspect                                                     # noqa: E402
import Scripts.Battle.battle_checklist as CHECK                    # noqa: E402
check("the meaningless 'is still <status>' line is no longer printed",
      "is still {target.status}"
      not in inspect.getsource(CHECK.move_order_and_execution))

# ----------------------------------------------------- 8. the rename
print()
print("== scouting rename ==")
check("the pre-battle menu says Scout Opponent",
      [label for _, name, label in BEFORE.MENU if name == "about_opponent"],
      ["Scout Opponent"])
import Scripts.Game.start_interface as START                       # noqa: E402
check("the tutorial says it too",
      "Scout Opponent" in inspect.getsource(START.tutorial))
from GUI_qt.widgets import ScoutCard                               # noqa: E402
card = ScoutCard(fonts)
card.set_mon({"name": "Metagross", "types": ["Steel"]}, known=False)
app.processEvents()
check("the locked hover card points at Scout Opponent",
      any("Scout Opponent" in t for t in texts(card)))
check("...and no longer says About Opponent",
      not any("About Opponent" in t for t in texts(card)))

# ------------------------------------------- 4. move effect wording
print()
print("== move effects ==")
DATA = codex.build(list_of_pokemon, list_of_moves, list_of_competitors,
                   art_for=B.character_art)
by_name = {m["name"]: m for m in DATA["moves"]}


def described(name):
    return " ".join(codex.describe(by_name[name]))


check("a self-buff no longer claims it cannot be protected against",
      "cannot be protected" not in described("Swords Dance"))
check("...nor a self-heal", "cannot be protected" not in described("Recover")
      if "Recover" in by_name else True)
check("but a move aimed at the other side still says it",
      "cannot be protected" in described("Stealth Rock"))
customs = [m for m in DATA["moves"] if m["custom"]]
check("the roster has custom moves (%d)" % len(customs), bool(customs))

dex = PokedexDialog(fonts, DATA, ROOT)
dex.present("moves")
moves = dex.sections["moves"]
dex.entry.setText(customs[0]["name"])
dex._filter()
app.processEvents()
from GUI_qt.widgets import Chip                                    # noqa: E402
check("a custom move is marked as custom when you open it",
      any(c.text() == "CUSTOM" for c in moves.findChildren(Chip)))
dex.entry.setText("Earthquake")
dex._filter()
app.processEvents()
check("...and an ordinary one is not",
      not any(c.text() == "CUSTOM" for c in moves.findChildren(Chip)))

# ------------------------------------------ 5. the opponent panel
print()
print("== opponent panel ==")
people = dex.sections["opponents"]
dex.tabs.setCurrentWidget(people)
dex.entry.setText("cynthia")
dex._filter()
app.processEvents()
shown = " | ".join(texts(people))
# "ACE", not "STRATEGY" and not "how they play": the blurb is about which
# Pokemon they always bring, so the heading says so -- and the Pokemon are
# named there with their typing.
check("the blurb is headed ACE",
      "ACE" in shown.upper() and "HOW THEY PLAY" not in shown.upper())
check("...and the ace is named with its typing",
      "GARCHOMP" in shown.upper() and "GROUND" in shown.upper())
check("their write-up is on the panel now", "ABOUT THEM" in shown.upper())
entry = [e for e in DATA["opponents"] if e["nickname"] == "Expert Cynthia"][0]
check("...and it is the real description",
      entry["description"][:28] in shown)

# ---------------------------------------------- 1. click to enlarge
print()
print("== lightbox ==")
from GUI_qt.pokedex import _ClickableFrame                         # noqa: E402
frames = people.findChildren(_ClickableFrame)
check("the portrait is clickable", len(frames), 1)
check("...and says so", "full size" in frames[0].toolTip())
people.open_lightbox(frames[0].path)
app.processEvents()
box = people._lightbox
check("clicking opens the full-size view",
      box is not None and box.isVisible(), True)
check("...frameless, with no panel around it",
      bool(box.windowFlags() & MW.Qt.FramelessWindowHint), True)
check("...covering the screen",
      box.width() >= 640 and box.height() >= 480, True)
picture = box.art.pixmap()
check("...showing the picture, larger than the panel did",
      picture.height() > people.portrait, True)
box.close()
check("closing puts it away", box.isVisible(), False)
dex.close()

# --------------------------------------- 2. the switch indicator
print()
print("== switch indicator ==")
w = MW.MainWindow(ROOT)


def mon(name):
    return {"name": name, "sprite": "garchomp", "types": ["Dragon"],
            "tier": "High", "ability": ["Rough Skin"], "status": "Normal",
            "hp": 100, "max_hp": 100, "stats": [], "nominal": [100] * 6,
            "iv": [20] * 6, "base": [80] * 6, "total": 500, "total_iv": 120,
            "modifier": [0] * 9, "volatile": {}, "moveset": ["Switching"],
            "moves": {}, "disabled": {}, "charging": ["", "", 0],
            "protecting": False, "fainted": False, "active": True}


BASE = {"phase": "battle", "battle_seq": 1,
        "player_side": {"nickname": "Marvin", "strength": 415},
        "opponent_side": {"nickname": "Expert Cynthia", "strength": 346},
        "player_team": [], "opponent_team": []}


def feed():
    """The sentences only. Each entry also carries a tag label reading
    "OPPONENT  ·  SENT OUT", which would double every count."""
    return [l.text() for l in w.feed_scroll.findChildren(QLabel)
            if "sent out " in l.text() and l.text().endswith(".")]


w._apply_state(dict(BASE, player=mon("Garchomp"), opponent=mon("Metagross")))
app.processEvents()
check("the first Pokemon of a match is not called a switch", feed(), [])
check("...and nothing is flashing", w.opponent_card.border_width, 1)

w._apply_state(dict(BASE, player=mon("Garchomp"), opponent=mon("Milotic")))
app.processEvents()
check("their switch is announced by name",
      any("Expert Cynthia sent out Milotic." == t for t in feed()))
check("...and their card flashes", w.opponent_card.border_width, 3)
check("...while yours does not", w.player_card.border_width, 1)

# switch, faint, switch again inside one turn: every one of them is recorded
w._apply_state(dict(BASE, player=mon("Garchomp"), opponent=mon("Skarmory")))
app.processEvents()
w._apply_state(dict(BASE, player=mon("Garchomp"), opponent=mon("Zapdos")))
app.processEvents()
check("three switches in a turn are all recorded", len(feed()), 3)
check("...naming each one",
      sorted(t.split("sent out ")[1] for t in feed()
             if "sent out " in t),
      ["Milotic.", "Skarmory.", "Zapdos."])

w._apply_state(dict(BASE, player=mon("Milotic"), opponent=mon("Zapdos")))
app.processEvents()
check("your own switch is announced too",
      any("You sent out Milotic." == t for t in feed()))

w._apply_state(dict(BASE, phase="prebattle", player=mon("Garchomp"),
                    opponent=mon("Metagross")))
app.processEvents()
before = len(feed())
w._apply_state(dict(BASE, player=mon("Garchomp"), opponent=mon("Aggron")))
app.processEvents()
check("a new match does not announce its first Pokemon", len(feed()), before)

# ---------------------------------------------------- 6. credits
print()
print("== credits ==")
credits = CreditsDialog(fonts, ROOT, champion=False, titles=0)
app.processEvents()
check("no 'Your run has ended'",
      not any("run has ended" in t.lower() for t in texts(credits)))
check("...it just says credits",
      any(t.upper() == "CREDITS" for t in texts(credits)))
won = CreditsDialog(fonts, ROOT, champion=True, titles=4)
app.processEvents()
check("a win still reads as a win",
      any("champion" in t.lower() for t in texts(won)))

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
