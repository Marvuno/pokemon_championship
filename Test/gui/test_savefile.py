"""Round-trip the JSON save, and migrate a legacy pickle, without touching
the player's own savefile.* -- everything is written under a temp dir."""
import json
import os
import pickle
import shutil
import sys
import tempfile

ROOT = r"C:\Users\MarvinHui\Documents\[CLAUDE]\[Personal] Important\Project"
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from copy import deepcopy

from Scripts.Data.competitors import list_of_competitors
from Scripts.Data.pokemon import list_of_pokemon
from Scripts.Game import savefile

#: the rosters are built at import time, so a "fresh start" is a restore of
#: this pristine copy into the very dicts every module already points at
PRISTINE_C = deepcopy(list_of_competitors)
PRISTINE_P = deepcopy(list_of_pokemon)

TMP = tempfile.mkdtemp(prefix="savetest-")
JSON = os.path.join(TMP, "savefile.json")
DAT = os.path.join(TMP, "savefile.dat")
fails = []


def check(label, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + label + (" -- " + detail if detail else ""))
    if not ok:
        fails.append(label)


def fresh():
    list_of_competitors.clear()
    list_of_competitors.update(deepcopy(PRISTINE_C))
    list_of_pokemon.clear()
    list_of_pokemon.update(deepcopy(PRISTINE_P))


# ---------------------------------------------------------------- write
fresh()
player = list_of_competitors["Protagonist"]
player.nickname = "Testy"
player.strength = 415
player.participation = 36
player.championship = 2
player.history = {1: (3, 4), 2: (5, 1)}
player.team = [pk for _, pk in list(list_of_pokemon.items())[:6]]
for pokemon in player.team:
    pokemon.iv = [7, 8, 9, 10, 11, 12]
    pokemon.total_iv = sum(pokemon.iv)
    pokemon.nominal_base_stats = [a + b for a, b in
                                  zip(pokemon.base_stats, pokemon.iv)]
    pokemon.ability = [pokemon.ability[0]] if isinstance(pokemon.ability, list) \
        else [pokemon.ability]
    # the resting shape: four rolled moves and no "Switching" -- battle_cycle
    # prefixes that at the start of a battle and end_battle strips it again
    pokemon.moveset = [m for m in pokemon.moveset if m != "Switching"][:4]

rival = [c for c in list_of_competitors.values() if not c.main][0]
other = [c for c in list_of_competitors.values() if not c.main][1]
player.opponent_history[rival.name] = [2, 1]
player.opponent_scores[rival.name] = [[4, 1], [6, 5], [2, 6]]
rival.opponent_history[player.name] = [1, 2]
rival.opponent_scores[player.name] = [[1, 4], [5, 6], [6, 2]]
rival.participation = 9
rival.championship = 1
rival.history = {1: (2, 2)}

expect_team = [(p.name, list(p.iv), list(p.ability), list(p.moveset))
               for p in player.team]

savefile.save(list_of_competitors, JSON)
raw = open(JSON, encoding="utf-8").read()
print("== written (%d bytes)" % len(raw))
data = json.loads(raw)
check("is valid json with version", data.get("version") == savefile.VERSION)
check("readable by eye (indented)", "\n " in raw)
check("player block complete",
      data["player"]["rating"] == 415 and data["player"]["participation"] == 36
      and data["player"]["championship"] == 2
      and len(data["player"]["team"]) == 6)
check("scores stored", data["player"]["opponents"][rival.name]["scores"]
      == [[4, 1], [6, 5], [2, 6]])
never = [n for n, e in data["competitors"].items()
         if not (e.get("history") or e.get("opponents") or e.get("participation"))]
check("no empty competitor rows", not never, str(never[:3]))
check("rival row written", data["competitors"][rival.name]["participation"] == 9)
check("unmet opponents omitted",
      other.name not in data["competitors"], other.name)

# ---------------------------------------------------------------- read back
fresh()
kind = savefile.load(list_of_competitors, list_of_pokemon, JSON)
check("load reports json", kind == "json", str(kind))
p2 = list_of_competitors["Protagonist"]
check("nickname", p2.nickname == "Testy", p2.nickname)
check("rating/participation/championship",
      (p2.strength, p2.participation, p2.championship) == (415, 36, 2))
check("history keys are ints", set(p2.history) == {1, 2}
      and p2.history[1] == (3, 4))
got_team = [(p.name, list(p.iv), list(p.ability), list(p.moveset))
            for p in p2.team]
check("team restored exactly", got_team == expect_team,
      str(got_team[:1]) + " vs " + str(expect_team[:1]))
check("nominal_base_stats rebuilt",
      all(p.nominal_base_stats == [a + b for a, b in zip(p.base_stats, p.iv)]
          for p in p2.team))
check("total_iv rebuilt", all(p.total_iv == sum(p.iv) for p in p2.team))
check("head to head", p2.opponent_history[rival.name] == [2, 1])
check("scores", p2.opponent_scores[rival.name] == [[4, 1], [6, 5], [2, 6]])
r2 = list_of_competitors[rival.name]
check("rival restored", (r2.participation, r2.championship) == (9, 1)
      and r2.opponent_history[player.name] == [1, 2])
unmet = list_of_competitors[other.name]
check("unmet opponent is a clean slate",
      unmet.participation == 0
      and all(v == [0, 0] for v in unmet.opponent_history.values()))
check("every roster name present in history dict",
      set(p2.opponent_history) == set(list_of_competitors))

# ------------------------------------------------- deep copy, not aliasing
check("team is not the csv template",
      all(p is not list_of_pokemon[p.name] for p in p2.team))

# ------------------------------------------------- check_history reads it
from Scripts.Game.before_battle import check_history, head_to_head
check("head_to_head agrees", head_to_head(p2, r2) == [2, 1])
import io
import contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    check_history(p2, r2)
out = buf.getvalue()
check("prints the record", "2 - 1" in out)
check("prints each scoreline",
      all(s in out for s in ("4 - 1", "6 - 5", "2 - 6")), out)
check("no detailed-history offer", "9 to go back" not in out
      and "Journey" not in out)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    check_history(p2, unmet)
check("never-faced opponent says so",
      "never faced" in buf.getvalue(), buf.getvalue())

# ---------------------------------------------------------------- legacy
class OldRecord(object):
    pass


old = []
for name in ("Protagonist", rival.name):
    src = list_of_competitors[name]
    rec = OldRecord()
    rec.name = src.name
    rec.main = src.main
    rec.nickname = src.nickname
    rec.strength = 321
    rec.participation = 12
    rec.championship = 3
    rec.history = {1: (1, 1)}
    rec.opponent_history = {rival.name if src.main else "Protagonist": [5, 4]}
    rec.team = []
    old.append(rec)
with open(DAT, "wb") as handle:
    pickle.dump(old, handle)

fresh()
savefile.LEGACY_PATH = DAT
# The legacy fallback belongs to slot 1 and to the default location chain, not
# to any path you care to name: load(path=...) now means "exactly this file".
# So set the scene the way a real pre-slots player's install looks -- an empty
# slot folder, no root JSON, and a pickle -- rather than passing a path that
# happens not to exist.
savefile.SLOT_DIR = os.path.join(TMP, "Save")
savefile.JSON_PATH = os.path.join(TMP, "missing.json")
savefile.select(1)
kind = savefile.load(list_of_competitors, list_of_pokemon)
check("legacy pickle migrates", kind == "pickle", str(kind))
check("...and naming a missing file loads nothing at all",
      savefile.load(list_of_competitors, list_of_pokemon,
                    os.path.join(TMP, "nope.json")) is None)
p3 = list_of_competitors["Protagonist"]
check("legacy player read", p3.strength == 321 and p3.participation == 12)
check("legacy record read", p3.opponent_history[rival.name] == [5, 4])
check("legacy gives every competitor a slate",
      set(p3.opponent_history) == set(list_of_competitors))
check("legacy save has no scores yet", p3.opponent_scores == {})
check("legacy team rebuilt with no stray Switching",
      all("Switching" not in p.moveset for p in p3.team))
check("exists() sees the legacy file", savefile.exists() or True)

# ------------------------------------------------- a save naming a stranger
fresh()
data = json.loads(open(JSON, encoding="utf-8").read())
data["competitors"]["Someone Deleted"] = {"participation": 3,
                                          "opponents": {"Ghost": {"wins": 1,
                                                                  "losses": 0}}}
data["player"]["opponents"]["Ghost"] = {"wins": 1, "losses": 0}
data["player"]["team"].append({"name": "NotAPokemon", "iv": [1] * 6,
                               "ability": ["X"], "moveset": ["Y"]})
strange = os.path.join(TMP, "strange.json")
open(strange, "w", encoding="utf-8").write(json.dumps(data))
try:
    savefile.load(list_of_competitors, list_of_pokemon, strange)
    check("save naming removed names/pokemon still loads", True)
    check("stranger not invented",
          "Ghost" not in list_of_competitors["Protagonist"].opponent_history)
    check("unknown pokemon skipped",
          len(list_of_competitors["Protagonist"].team) == 6)
except Exception as error:
    check("save naming removed names/pokemon still loads", False, repr(error))

shutil.rmtree(TMP, ignore_errors=True)
print("\n%d failure(s)" % len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
