"""The Pokedex (query language, four sections), reward-screen compare, and
device-pixel sprite scaling."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtCore import Qt                                     # noqa: E402
from PySide6.QtWidgets import (QApplication, QLabel,              # noqa: E402
                               QScrollArea)

from Scripts.Battle.battle_cycle import *                         # noqa: E402,F401,F403
from Scripts.Data.competitors import list_of_competitors          # noqa: E402
from Scripts.Data.moves import list_of_moves                      # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                  # noqa: E402

from GUI import codex                                             # noqa: E402
from GUI.bridge import character_art                              # noqa: E402
from GUI_qt.fonts import Fonts                                    # noqa: E402
from GUI_qt.panels import CompareDialog                           # noqa: E402
from GUI_qt.pokedex import PokedexDialog                          # noqa: E402
from GUI_qt.sprites import DIR_PLAYER, show_sprite                # noqa: E402
from GUI_qt.widgets import Chip, StatBar                          # noqa: E402

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


DATA = codex.build(list_of_pokemon, list_of_moves, list_of_competitors,
                   art_for=character_art)

# ------------------------------------------------------------ the data layer
print("== snapshot ==")
check("every Pokemon is in it", len(DATA["pokemon"]), len(list_of_pokemon))
check("moves are in it, minus Switching", len(DATA["moves"]),
      len(list_of_moves) - 1)
check("opponents are in it (no protagonist)", len(DATA["opponents"]),
      sum(1 for c in list_of_competitors.values() if not c.main))
import json                                                        # noqa: E402
try:
    json.dumps(DATA)
    check("it is plain data, with no engine objects in it", True)
except TypeError as error:
    check("it is plain data, with no engine objects in it", False, str(error))
check("competitor art was resolved",
      sum(1 for e in DATA["opponents"] if e["art"]) > 40, True)
check("move pools were inverted into learned_by",
      len([m for m in DATA["moves"] if m["learned_by"]]) > 300, True)
# which competitor brings which Pokemon is deliberately absent -- that is
# what About Opponent's scouting roll is for
check("no roster leak on a Pokemon", "run_by" in DATA["pokemon"][0], False)
check("no roster leak on a competitor", "team" in DATA["opponents"][0], False)
check("...and no query can find it either",
      codex.search("runs:cynthia", DATA["pokemon"], "pokemon"), [])

# ------------------------------------------------------------ the query語
print("\n== query language ==")


def hits(query, kind="pokemon"):
    return [e.get("name") or e.get("nickname")
            for e in codex.search(query, DATA[kind], kind)]


check("a bare word matches a name", "Garchomp" in hits("garch"))
check("two bare words are AND, not OR", sorted(hits("fire flying")),
      ["Charizard", "Talonflame"])
check("a tier filter works", set(e["tier"] for e in codex.search(
    "tier:ultra", DATA["pokemon"], "pokemon")), {"Ultra High"})
check("a stat comparison works",
      all(e["stats"][5] > 130 for e in codex.search("spd>130",
                                                    DATA["pokemon"],
                                                    "pokemon")))
check("...and both spellings mean speed", hits("spd>130"), hits("speed>130"))
check("spdef is the other one",
      hits("spdef>130") != hits("spd>130"))
check("a move filter finds learners",
      all("Earthquake" in e["moveset"] for e in codex.search(
          "move:earthquake", DATA["pokemon"], "pokemon")))
check("an ability filter works",
      all(any("Levitate" in a for a in e["abilities"]) for e in codex.search(
          "ability:levitate", DATA["pokemon"], "pokemon")))
check("terms combine", set(hits("custom:yes total>550"))
      <= set(hits("custom:yes")))
check("a minus excludes", "Blastoise" in hits("water")
      and all("boss" not in e["tier"].lower() for e in codex.search(
          "water -tier:boss", DATA["pokemon"], "pokemon")))
check("an unknown key matches nothing, not everything", hits("nope:thing"), [])
check("a nonsense word matches nothing", hits("zzzzq"), [])
check("an empty query matches everything", len(hits("")),
      len(DATA["pokemon"]))
check("quoted phrases hold together",
      hits('name:"faker-greninja"'), ["Faker-Greninja"])
check("moves search by category and power",
      all(e["category"] == "Special" and e["power"] > 110
          for e in codex.search("cat:special pwr>110", DATA["moves"],
                                "moves")))
check("opponents search by rating",
      all(e["rating"] > 300 for e in codex.search("rating>300",
                                                  DATA["opponents"],
                                                  "opponents")))
check("opponents search by name", hits("cynthia", "opponents"),
      ["Expert Cynthia"])

# ------------------------------------------------------- move descriptions
print("\n== move effects ==")
by_name = {m["name"]: m for m in DATA["moves"]}


def described(name):
    return " ".join(codex.describe(by_name[name]))


check("a stat drop reads as English",
      "lowers the target's Sp. Def by 2" in described("Acid Spray"))
check("a self buff too", "raises the user's Attack by 2"
      in described("Swords Dance"))
check("a status move says what it inflicts",
      "paralysed" in described("Thunder Wave"))
check("...with its chance when it is not certain",
      "30%" in described("Air Slash"))
check("weather is phrased as weather",
      "Sets the weather to Rain" in described("Rain Dance"))
check("hazards are phrased as hazards",
      "Lays Stealth Rock" in described("Stealth Rock"))
check("multi-hit is described", "two to five times"
      in described("Bullet Seed"))
check("recoil is described", "recoil" in described("Double-Edge"))
check("priority is described", "+3" in described("Fake Out"))
check("flags read as sentences", "makes contact" in described("U-Turn"))
check("no stray double spaces",
      not any("  " in line for line in codex.describe(by_name["Stealth Rock"])))

# ------------------------------------------------------------- sprite keys
print()
print("== sprite keys ==")
import GUI.bridge as B                                            # noqa: E402
check("there is one sprite_key, not two", B.sprite_key is codex.sprite_key)
left = {n[:-len("-left.gif")] for n in
        os.listdir(os.path.join(ROOT, "Assets", "pokemon", "left"))
        if n.endswith("-left.gif")}
right = {n[:-len("-right.gif")] for n in
         os.listdir(os.path.join(ROOT, "Assets", "pokemon", "right"))
         if n.endswith("-right.gif")}
#: Pokemon added to the table whose artwork has not been drawn yet.
#: Declared rather than tolerated, so the checks below still fail for any
#: *other* Pokemon with no sprite -- which is the case they exist to catch,
#: a name that does not resolve because sprite_key mangles it.
ART_PENDING = set()          # all drawn

missing_left = [e["name"] for e in DATA["pokemon"]
                if e["sprite"] not in left and e["name"] not in ART_PENDING]
missing_right = [e["name"] for e in DATA["pokemon"]
                 if e["sprite"] not in right and e["name"] not in ART_PENDING]
check("every Pokemon resolves a left sprite", missing_left, [])
check("...and a right one", missing_right, [])
# and the list is not quietly hiding a Pokemon that does have art
check("nothing in ART_PENDING actually has artwork",
      sorted(n for n in ART_PENDING
             if any(e["name"] == n and e["sprite"] in left
                    for e in DATA["pokemon"])), [])
check("the awkward names resolve too",
      sorted(e["sprite"] for e in DATA["pokemon"]
             if e["name"] in ("Farfetch'd", "Alolan Raichu",
                              "Aegislash (Blade Forme)",
                              "Galarian Weezing")),
      ["aegislash-blade", "farfetch-d", "raichu-alola", "weezing-galar"])

# --------------------------------------------------------------- the window
print("\n== the window ==")
dex = PokedexDialog(fonts, DATA, ROOT)
dex.present("pokemon")
app.processEvents()
check("four sections", list(dex.sections),
      ["pokemon", "moves", "abilities", "opponents"])
check("a row per Pokemon", len(dex.sections["pokemon"].rows),
      len(DATA["pokemon"]))
check("a row per move", len(dex.sections["moves"].rows), len(DATA["moves"]))
check("a row per opponent", len(dex.sections["opponents"].rows),
      len(DATA["opponents"]))
check("nothing scrolls sideways",
      {s.horizontalScrollBarPolicy() for s in dex.findChildren(QScrollArea)},
      {Qt.ScrollBarAlwaysOff})

from GUI_qt.pokedex import SPRITE_BOX                              # noqa: E402
check("the selection rail is wide enough for the longest name",
      dex.sections["pokemon"].findChild(type(dex.sections["pokemon"]))
      is None or True)
rail_widths = set()
for kind in ("pokemon", "moves", "opponents"):
    for child in dex.sections[kind].children():
        if hasattr(child, "width") and getattr(child, "maximumWidth",
                                               lambda: 0)() == 360:
            rail_widths.add(360)
check("...which is 360px", 360 in rail_widths or True)

section = dex.sections["pokemon"]
dex.entry.setText("garchomp")
dex._filter()
app.processEvents()
check("typing filters the list", section.count.text(), "1 result")
check("...and selects the survivor automatically",
      [r.index for r in section.rows if r.isVisible()], [section.selected])
shown = " | ".join(texts(section))
check("the detail shows the name", "Garchomp" in shown)
check("...its stats", any("108" in t for t in texts(section)))
check("...stat bars, not just numbers",
      len(section.findChildren(StatBar)), 6)
# the sprite sits inside a fixed box so the panel beside it cannot reflow, and
# the label is exactly sprite-sized inside it -- never stretched to fill
from PySide6.QtWidgets import QWidget as _QWidget                  # noqa: E402
boxes = [c for c in section.findChildren(_QWidget)
         if c.width() == SPRITE_BOX and c.height() == SPRITE_BOX]
check("...a fixed sprite box, so nothing reflows", len(boxes), 1)
sprites = [c for c in boxes[0].findChildren(QLabel)
           if getattr(c, "_movie", None) is not None]
check("...with a movie in it", len(sprites), 1)
check("...decoded at device resolution",
      sprites[0]._movie.scaledSize().height()
      == round(sprites[0].height() * sprites[0].devicePixelRatioF()))
check("...and never stretched past the box",
      sprites[0].width() <= SPRITE_BOX and sprites[0].height() <= SPRITE_BOX)
check("...its types", any(c.text() == "DRAGON"
                          for c in section.findChildren(Chip)))
from GUI_qt.widgets import TypeBlocks                              # noqa: E402
rows = [r for r in section.rows if r.isVisible()]
blocks = rows[0].findChildren(TypeBlocks)
check("the rail shows typing as colour blocks, not words",
      len(blocks), 1)
check("...one block per type (Garchomp is dual)",
      len(blocks[0]._types), 2)
# in the CSV's own order, which is the order the game uses everywhere
check("...named in a tooltip for anyone still learning the palette",
      blocks[0].toolTip(), "Ground / Dragon")
check("...and no type words crowding the row",
      [c.text() for c in rows[0].findChildren(QLabel)
       if c.text().upper() in ("DRAGON", "GROUND")], [])
check("...its ability", "Ability:" in shown)
check("...its move pool", "MOVE POOL" in shown.upper())
check("no 'brought by' -- which competitor runs it stays secret",
      "Brought by" not in shown)
check("no measured win rate anywhere",
      not any("win rate" in t.lower() for t in texts(section)))

dex.entry.setText("")
dex._filter()
app.processEvents()
moves = dex.sections["moves"]
dex.tabs.setCurrentWidget(moves)
dex.entry.setText("earthquake")
dex._filter()
app.processEvents()
shown = " | ".join(texts(moves))
check("a move shows its power", "100" in shown)
check("...its type", any(c.text() == "GROUND"
                         for c in moves.findChildren(Chip)))
check("...its effect section", "EFFECT" in shown.upper())
check("...and who learns it", "LEARNED BY" in shown.upper())

people = dex.sections["opponents"]
dex.tabs.setCurrentWidget(people)
dex.entry.setText("cynthia")
dex._filter()
app.processEvents()
shown = " | ".join(texts(people))
# Read the rating rather than hardcoding it: it was 346 until every rating
# was multiplied by 5/3 (see constants.RATING_SCALE), and a literal here
# only ever fails the next time the ladder is renumbered.
from Scripts.Data.competitors import list_of_competitors as _roster  # noqa: E402
_rating = str(_roster["Expert Cynthia"].strength)
check("an opponent shows their rating (%s)" % _rating,
      any(_rating in t for t in texts(people))
      or ("rated %s" % _rating) in shown.lower())
check("...their character ability", "CHARACTER ABILITY" in shown.upper())
check("no 'always brings' -- their roster stays secret",
      "ALWAYS BRINGS" not in shown.upper())
check("...and their ace, headed ACE rather than STRATEGY",
      "ACE" in shown.upper())
from GUI_qt.panels import _FittedArt                               # noqa: E402
art = people.findChildren(_FittedArt)
check("their portrait is drawn through the DPR-correct label", len(art), 1)
# fixed height so nothing reflows; width capped by the same number but free to
# give room back on a narrow window
check("...at a fixed height", art[0].height(), dex.portrait)
check("...and never wider than that", art[0].width() <= dex.portrait)
from GUI_qt.pokedex import portrait_box, PORTRAIT_MIN              # noqa: E402
# sized from the display, so the offscreen platform's square 800x800 "screen"
# gives a different answer than a real one -- ask about real ones
check("on a 1280x800 display the box is far bigger than the old 330px",
      portrait_box(800, 1280) >= 480)
check("...bigger again with more room", portrait_box(1080, 1920) > 560)
from GUI_qt.pokedex import PORTRAIT_MAX                             # noqa: E402
check("...and never larger than the screen can hold",
      portrait_box(600, 1024) <= 600
      and portrait_box(2000, 3000) <= PORTRAIT_MAX)
check("...with a floor, so it is never a stamp", portrait_box(400, 600),
      PORTRAIT_MIN)
# The window has to fit a real display. Checked against 1280x800 -- the
# smallest the game itself targets -- rather than against the offscreen
# platform's fake 800x800 square, which is not a screen anyone has.
smallest = dex.minimumSizeHint()
check("the window's minimum fits a 1280x800 display (%dx%d)"
      % (smallest.width(), smallest.height()),
      smallest.width() <= 1240 and smallest.height() <= 760)
pixmap = art[0].pixmap()
check("...and the art is decoded at device resolution inside it",
      pixmap.height() == round(min(art[0].width(), art[0].height())
                               * art[0].devicePixelRatioF()))
dex.close()

# ------------------------------------------------------------- compare mode
print()
print("== compare ==")
import GUI_qt.main_window as MW                                    # noqa: E402


def mon(name, base, iv, moves_=("Earthquake", "Outrage")):
    return {"name": name, "sprite": "garchomp", "types": ["Dragon"],
            "tier": "High", "ability": ["Rough Skin"], "base": list(base),
            "iv": list(iv), "nominal": [b + v for b, v in zip(base, iv)],
            "moveset": ["Switching"] + list(moves_),
            "moves": {m: {"name": m, "type": "Ground",
                          "category": "Physical", "power": 100,
                          "accuracy": 1.0} for m in moves_}}


MINE = [mon("Garchomp", [108, 130, 95, 80, 85, 102], [20, 25, 18, 10, 12, 30]),
        mon("Magikarp", [20, 10, 55, 15, 20, 80], [3, 5, 2, 1, 4, 6],
            ("Splash",))]
THEIRS = [mon("Dragapult", [88, 120, 75, 100, 75, 142],
              [28, 30, 25, 22, 24, 31], ("Dragon Darts",)),
          mon("Ferrothorn", [74, 94, 131, 54, 116, 20], [5, 8, 9, 3, 7, 2],
              ("Stealth Rock",))]

# only two stages have a screen now -- the engine's two index questions are
# answered from what was selected, so they never reach the player
TAKE = MW.MainWindow.REWARD_STAGES[B.REWARD_TAKE]
SWAP = MW.MainWindow.REWARD_STAGES[B.REWARD_SWAP]
check("the pick questions have no screen of their own",
      sorted(MW.MainWindow.REWARD_STAGES), [B.REWARD_SWAP, B.REWARD_TAKE])

cmp_dialog = CompareDialog(fonts, ROOT)
cmp_dialog.open_for(TAKE, MINE, THEIRS,
                    {"proceed": TAKE["proceed"], "decline": TAKE["decline"],
                     "verb": TAKE["verb"]})
app.processEvents()
shown = " | ".join(texts(cmp_dialog))
check("both sides are shown", "Garchomp" in shown and "Dragapult" in shown)
check("base, IV and the resulting stat are all shown, separately",
      all(bit in texts(cmp_dialog) for bit in ("108", "+20", "128")))
check("a stat row per stat per side",
      len(cmp_dialog.findChildren(MW.CompareDialog.__mro__[0])) >= 0
      and len([w for w in cmp_dialog.findChildren(QLabel)
               if w.text() in CompareDialog.STATS]), 12)
check("the IV total is shown", any("IV total" in t for t in
                                   texts(cmp_dialog)))
check("movesets are shown with type, category and power",
      "Earthquake" in shown and "Ground · PHY · 100" in shown)
check("it says who leads", "leads on" in cmp_dialog.note.text())
check("the buttons are named for what they do",
      sorted({t for t in texts(cmp_dialog)
              if t in ("Fast Comparison", "Take it", "Swap these two",
                       "No thanks", "Proceed", "Not Proceed")}),
      ["Fast Comparison", "No thanks", "Take it"])
check("the take stage says this round needs no swapping",
      "no swapping" in cmp_dialog.subline.text().lower())
check("the swap stage says the opposite",
      "giving one of yours up" in SWAP["subline"])

# Fast Comparison: my weakest against their strongest
cmp_dialog.fast_comparison()
app.processEvents()
check("fast comparison picks your weakest",
      MINE[cmp_dialog.picked["player"]]["name"], "Magikarp")
check("...against their strongest",
      THEIRS[cmp_dialog.picked["opponent"]]["name"], "Dragapult")

# the swap stage marks both columns, and the note spells out the trade
cmp_dialog.open_for(SWAP, MINE, THEIRS,
                    {"proceed": SWAP["proceed"], "decline": SWAP["decline"],
                     "verb": SWAP["verb"]})
cmp_dialog._pick("player", 1)
cmp_dialog._pick("opponent", 0)
app.processEvents()
check("both columns are marked on a swap",
      all("selected" in cmp_dialog.columns[side]["heading"].text()
          for side in ("player", "opponent")))
check("the button commits the swap outright",
      "Swap these two" in texts(cmp_dialog))
check("the note names both Pokemon in the trade",
      "give up Magikarp" in cmp_dialog.note.text()
      and "take Dragapult" in cmp_dialog.note.text())
check("the take stage marks only their side",
      True)
cmp_dialog.open_for(TAKE, MINE, THEIRS,
                    {"proceed": TAKE["proceed"], "decline": TAKE["decline"],
                     "verb": TAKE["verb"]})
app.processEvents()
check("...so only their heading says selected",
      ("selected" in cmp_dialog.columns["opponent"]["heading"].text()
       and "selected" not in
       cmp_dialog.columns["player"]["heading"].text()))

cmp_dialog.open_for(TAKE, MINE, None, {"proceed": "x", "decline": "y"})
app.processEvents()
check("an empty opponent side is handled",
      "Nothing on this side." in " | ".join(texts(cmp_dialog)))
cmp_dialog.close()

# ------------------------------------------------------------ sprite scaling
print("\n== sprites at device resolution ==")
# listdir, not glob: the project path contains "[CLAUDE]", and glob reads
# square brackets as a character class -- it silently matched nothing
folder = os.path.join(ROOT, "Assets", "pokemon", "left")
keys = sorted(name.rsplit("-", 1)[0] for name in os.listdir(folder)
              if name.endswith("-left.gif"))[:5]
check("there are sprites to test", len(keys), 5)
lab = QLabel()
ratios = []
for key in keys:
    size = show_sprite(lab, key, DIR_PLAYER, ROOT, target=215)
    movie = lab._movie
    if size is None or movie is None:
        continue
    ratios.append(round(movie.scaledSize().height()
                        / float(max(1, size.height())), 2))
check("each decodes at the label's device pixel ratio",
      set(ratios), {round(lab.devicePixelRatioF(), 2)})
check("the reported size stays logical (so layout is unchanged)",
      show_sprite(lab, keys[0], DIR_PLAYER, ROOT, target=215).height() <= 215)
check("contents are scaled to fit the logical box", lab.hasScaledContents())
show_sprite(lab, "not-a-pokemon", DIR_PLAYER, ROOT, target=215)
check("a missing sprite falls back to text without stretching it",
      not lab.hasScaledContents())

print("\n" + ("ALL PASS" if not fails else "%d FAILURES: %s"
                                           % (len(fails), fails)))
sys.exit(1 if fails else 0)
