"""The Pokedex's Abilities section, and the move wording fixes that went
with it."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel                # noqa: E402

from GUI import bridge as B                                       # noqa: E402
B.Bridge.start = lambda self: None
from GUI import codex                                             # noqa: E402
from GUI_qt.fonts import Fonts                                    # noqa: E402
from GUI_qt.pokedex import PokedexDialog, SECTIONS                 # noqa: E402
from Scripts.Data.competitors import list_of_competitors           # noqa: E402
from Scripts.Data.moves import list_of_moves                       # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon                   # noqa: E402

app = QApplication.instance() or QApplication([])
fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-58s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


DATA = codex.build(list_of_pokemon, list_of_moves, list_of_competitors,
                   art_for=B.character_art)
ABILITIES = DATA["abilities"]

# ------------------------------------------------------------- the data
check("abilities are in the snapshot", bool(ABILITIES))
by_name = {entry["name"]: entry for entry in ABILITIES}
check("a Pokemon ability lists who has it",
      by_name["Levitate"]["kind"] == "pokemon"
      and len(by_name["Levitate"]["pokemon"]) > 5)
check("a new Pokemon ability is there",
      by_name["Supreme Overload"]["pokemon"], ["Kingambit"])
# Character abilities are deliberately absent: which competitor has which is
# what Scout Opponent gates, and listing them here would give it away free.
check("character abilities are not listed",
      [name for name in ("Frighten", "Procrastination", "Naive", "Trashy")
       if name in by_name], [])
check("...so every entry is a Pokemon ability",
      sorted({entry["kind"] for entry in ABILITIES}), ["pokemon"])
check("...and none carries a trainer list",
      [entry["name"] for entry in ABILITIES if entry.get("trainers")], [])
check("the player's own ability slot is not a listed ability",
      "Protagonist" not in by_name)
check("nothing unassigned pads the list",
      [name for name, entry in by_name.items()
       if not entry["pokemon"] and not entry["trainers"]], [])

# ------------------------------------------------------------ searching
for query, expect in (("levitate", "Levitate"),
                      ("kingambit", "Supreme Overload"),
                      ("baxcalibur", "Thermal Exchange")):
    hits = codex.search(query, ABILITIES, "abilities")
    check("searching %-11s finds %s" % (query, expect),
          [h["name"] for h in hits], [expect])

# ------------------------------------------------------------ the panel
check("Abilities is a section", "Abilities" in SECTIONS)
dex = PokedexDialog(Fonts(), DATA, ROOT)
check("...and a tab",
      [dex.tabs.tabText(i) for i in range(dex.tabs.count())],
      ["Pokemon", "Moves", "Abilities", "Opponents"])
dex.present("abilities")
app.processEvents()
section = dex.sections["abilities"]


def panel_text(query):
    dex.entry.setText(query)
    dex._filter()
    for _ in range(5):
        app.processEvents()
    return " | ".join(w.text() for w in section.detail.parentWidget()
                      .findChildren(QLabel) if w.text())


shown = panel_text("Supreme Overload")
check("opening one names it", "Supreme Overload" in shown)
check("...and lists the Pokemon", "Kingambit" in shown)
dex.close()

# ------------------------------------------------- move wording fixes
moves = {entry["name"]: entry for entry in DATA["moves"]}


def described(name):
    return " ".join(codex.describe(moves[name]))


check("a move that spends HP says so, not that it recovers it",
      "gives up a quarter" in described("Unbreakable Will"))
check("...and never claims to recover",
      "recovers" not in described("Unbreakable Will"))
check("Belly Drum spends half", "gives up half" in described("Belly Drum"))
check("a real draining move still drains",
      "Drains HP" in described("Drain Punch"))
check("PP is not mentioned in any description",
      [name for name in moves if " PP" in described(name)], [])
# the five-stat buff used to run to one sentence per stat
check("stats that move together are grouped",
      "Attack, Defence, Sp. Atk, Sp. Def and Speed by 1"
      in described("Unbreakable Will"))
check("...and a single stat still reads plainly",
      "raises the user's Attack by 2" in described("Swords Dance"))
check("a self-buff still does not claim protection cannot stop it",
      "cannot be protected" not in described("Swords Dance"))

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
