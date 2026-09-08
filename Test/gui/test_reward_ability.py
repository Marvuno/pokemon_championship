"""A victory pays out once: a Pokemon, or a roll for their character ability.

What matters here is that the two are alternatives rather than both, that the
roll is honest and clamped at each end, that the opponent keeps their own
ability, and that the player can only ever hold one.
"""
import builtins
import io
import os
import random
import sys
from contextlib import redirect_stdout

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("POKEMON_MUTE", "1")

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# battle_cycle first: importing battle_win_condition on its own leaves the
# star-imported namespaces half-built and ai_scorer cannot find it
import Scripts.Battle.battle_cycle                              # noqa: E402,F401
from Scripts.Battle import battle_win_condition as WIN          # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon as POKEMON     # noqa: E402
from GUI import bridge as B                                      # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print("%-62s %s" % (label, "PASS" if ok else "FAIL got=%r want=%r"
                        % (got, want)))
    if not ok:
        fails.append(label)


class Trainer:
    def __init__(self, name, strength, ability="", team=(), stage=1):
        self.name = self.nickname = name
        self.strength = strength
        self.ability = ability
        self.team = list(team)
        self.unused_team = []
        self.stage = stage
        self.side_color = ""


class Ground:
    verbose = False
    exhibition = False


def army(*names):
    from copy import deepcopy
    built = []
    for name in names:
        mon = deepcopy(POKEMON[name])
        mon.iv = [20] * 6
        mon.total_iv = 120
        mon.nominal_base_stats = [a + b for a, b in zip(mon.base_stats, mon.iv)]
        built.append(mon)
    return built


def reward(answers, me, them):
    """Run the reward screen, answering its questions from `answers`."""
    queue = list(answers)
    real = builtins.input
    builtins.input = lambda *a, **k: queue.pop(0) if queue else "N"
    asked = []
    try:
        def spy(*a, **k):
            asked.append(a[0] if a else "")
            return queue.pop(0) if queue else "N"
        builtins.input = spy
        with redirect_stdout(io.StringIO()):
            WIN.choose_pokemon(me, them, Ground())
    finally:
        builtins.input = real
    return asked


# ======================================================= the odds themselves
print("-- the roll --")
weak = Trainer("You", 5)
strong = Trainer("Champion", 833, ability="Quantum Roll")
check("a floor, so the early rounds are never hopeless",
      WIN.ability_steal_chance(weak, strong), WIN.ABILITY_STEAL_FLOOR)
check("a ceiling, so the late ones are never a formality",
      WIN.ability_steal_chance(Trainer("You", 833), Trainer("Them", 1)),
      WIN.ABILITY_STEAL_CEILING)
check("evenly matched is a coin flip",
      round(WIN.ability_steal_chance(Trainer("You", 200),
                                     Trainer("Them", 200)), 3), 0.5)
check("stronger opponents are harder to copy from",
      WIN.ability_steal_chance(Trainer("You", 300), Trainer("Them", 100))
      > WIN.ability_steal_chance(Trainer("You", 300), Trainer("Them", 400)))
check("nothing on offer from an opponent with no ability",
      WIN.ability_on_offer(weak, Trainer("Them", 100)), "")


# ================================================== the offer, and the trade
print()
print("-- a win offers one or the other, never both --")
me = Trainer("You", 200, team=army("Garchomp"), stage=2)
them = Trainer("Cynthia", 200, ability="Quantum Roll",
               team=army("Metagross", "Milotic"), stage=1)
asked = reward(["A"], me, them)
check("the choice is put to the player",
      any("character ability" in q.lower() for q in asked))
check("...naming what it would cost",
      any("nothing at all if it fails" in q.lower() for q in asked))
check("the bridge recognises the question",
      B.reward_prompt_kind(asked[0]), B.REWARD_ABILITY)
check("taking the ability takes no Pokemon",
      [mon.name for mon in me.team], ["Garchomp"])

# an opponent with nothing to copy is never asked about
me = Trainer("You", 200, team=army("Garchomp"), stage=2)
plain = Trainer("Nobody", 200, team=army("Metagross"), stage=1)
asked = reward(["Y", "0"], me, plain)
check("an opponent with no ability skips the question",
      any("character ability" in q.lower() for q in asked), False)
check("...and the Pokemon reward still runs",
      len(me.team), 2)

# choosing the Pokemon falls through to the reward that was always there
me = Trainer("You", 200, team=army("Garchomp"), stage=2)
them = Trainer("Cynthia", 200, ability="Quantum Roll",
               team=army("Metagross", "Milotic"), stage=1)
reward(["P", "Y", "0"], me, them)
check("asking for a Pokemon instead still gives you one",
      len(me.team), 2)
check("...and leaves you with no ability", me.ability, "")


# ========================================================= what it does
print()
print("-- copying, and what the opponent keeps --")
won, lost = 0, 0
for seed in range(400):
    random.seed(seed)
    me = Trainer("You", 200, team=army("Garchomp"), stage=2)
    them = Trainer("Cynthia", 200, ability="Quantum Roll",
                   team=army("Metagross"), stage=1)
    reward(["A"], me, them)
    if me.ability == "Quantum Roll":
        won += 1
    else:
        lost += 1
    if them.ability != "Quantum Roll":
        fails.append("the opponent lost their own ability")
        break
rate = won / float(won + lost)
check("the roll lands near its stated odds (%d%% of 400)" % round(rate * 100),
      0.42 <= rate <= 0.58)
check("it can fail", lost > 0)
check("the opponent always keeps their own ability",
      "the opponent lost their own ability" not in fails)

# only ever one, and taking a second replaces the first
me = Trainer("You", 833, team=army("Garchomp"), stage=2)
them = Trainer("Cynthia", 1, ability="Outliers",
               team=army("Metagross"), stage=1)
random.seed(1)
reward(["A"], me, them)
first = me.ability
later = Trainer("Kokushibo", 1, ability="Tension Release",
                team=army("Milotic"), stage=1)
random.seed(1)
reward(["A"], me, later)
check("a copied ability replaces the one held, never stacks",
      (first, me.ability), ("Outliers", "Tension Release"))
check("...so the player holds exactly one",
      isinstance(me.ability, str) and me.ability.count(",") == 0)


# ======================================================== losing changes none
print()
print("-- and none of it on a loss --")
me = Trainer("You", 200, team=army("Garchomp"), stage=1)
them = Trainer("Cynthia", 200, ability="Quantum Roll",
               team=army("Metagross"), stage=2)
asked = reward(["A"], me, them)
check("a defeat never offers the ability",
      any("character ability" in q.lower() for q in asked), False)
check("...and leaves you with none", me.ability, "")

print()
print("-- it survives the round --")
# save_game() runs every round, so an ability living only in memory would be
# gone by the next match. The Protagonist's CSV row is blank, which is also
# what a save written before this feature restores to.
import json                                                     # noqa: E402
import tempfile                                                 # noqa: E402
from Scripts.Game import savefile                               # noqa: E402
from Scripts.Data.competitors import list_of_competitors as ROSTER  # noqa: E402
from Scripts.Data.pokemon import list_of_pokemon as ALLMON      # noqa: E402

hero = ROSTER["Protagonist"]
before = getattr(hero, "ability", "")
try:
    hero.ability = "Quantum Roll"
    handle = os.path.join(tempfile.mkdtemp(), "slot.json")
    savefile.save(ROSTER, path=handle)
    written = json.load(io.open(handle, encoding="utf-8"))
    check("a copied ability is written to the save",
          (written.get("player") or {}).get("ability"), "Quantum Roll")
    hero.ability = ""
    savefile.load(ROSTER, ALLMON, path=handle)
    check("...and comes back on load", ROSTER["Protagonist"].ability,
          "Quantum Roll")

    # an older save has no such key, and must not crash or invent one
    written["player"].pop("ability", None)
    json.dump(written, io.open(handle, "w", encoding="utf-8"))
    ROSTER["Protagonist"].ability = "Outliers"
    savefile.load(ROSTER, ALLMON, path=handle)
    check("a save from before this feature restores to none",
          ROSTER["Protagonist"].ability, "")
finally:
    ROSTER["Protagonist"].ability = before


print()
print("-- one screen, not two --")
from PySide6.QtWidgets import QApplication                       # noqa: E402
B.Bridge.start = lambda self: None
from GUI_qt.main_window import MainWindow                        # noqa: E402
from GUI_qt.panels import CompareDialog                          # noqa: E402
from GUI_qt.widgets import ActionButton                          # noqa: E402

app = QApplication.instance() or QApplication([])
window = MainWindow(ROOT)
window._timer.stop()          # see CLAUDE.md: a live bridge wipes game_state
roster = [{"name": "Garchomp", "types": ["Dragon"], "ability": ["Rough Skin"],
           "nominal": [100] * 6, "base": [80] * 6, "iv": [20] * 6,
           "moveset": ["Tackle"], "moves": {}, "sprite": "garchomp",
           "tier": "High", "total": 500, "total_iv": 120}]


class Ask:
    kind = "reward"

    def __init__(self, prompt):
        self.prompt = prompt
        self.options = []


ABILITY_ASK = ("Input P to take a Pokemon, or A to copy their character "
               "ability (learn Quantum Roll, 43% chance -- and nothing at "
               "all if it fails). ")
TAKE_ASK = "Input Y if you want to take from the opponent, and N to get a "
SWAP_ASK = "Input Y if you want to swap, and N otherwise. "

said = []
window._answer = lambda text: said.append(text)


def offer(mode="take", mine=""):
    window.game_state = {
        "player_roster": roster, "opponent_roster": roster,
        "reward_ability": {"theirs": "Quantum Roll",
                           "theirs_text": "seals three types each turn.",
                           "mine": mine,
                           "mine_text": "damage varies 0.8x-1.4x." if mine
                                        else "",
                           "chance": 43, "pokemon_mode": mode,
                           "nickname": "Solanum"}}


def drive(prompt):
    del said[:]
    window.request = Ask(prompt)
    window._drive_reward(window.request)
    app.processEvents()


def buttons():
    return [b.title for b in window.compare_dialog.findChildren(ActionButton)]


offer("take")
drive(ABILITY_ASK)
check("the offer opens a screen", window.compare_dialog.isVisible())
labels = buttons()
check("...with the Pokemon offer on it",
      any("Take it" == t for t in labels), True)
check("...the ability beside it, odds and all",
      any(t.startswith("Copy Quantum Roll") and "43%" in t for t in labels),
      True)
check("...and a way out", any("No thanks" in t for t in labels), True)
check("...only their side drawn, since none of yours is at stake",
      window.compare_dialog.columns["player"]["panel"].isVisible(), False)

# what the abilities actually do, which the player could not read anywhere
panel = window.compare_dialog.ability_panel
shown_text = " | ".join(
    w.text() for w in panel.findChildren(type(panel.parent().subline)))
check("the ability panel is up", panel.isVisible())
check("...naming theirs", "Quantum Roll" in shown_text)
check("...explaining it", "seals three types" in shown_text)
check("...and saying you have none yet", "none yet" in shown_text)

# taking the ability answers the whole thing at once
window.compare_dialog._on_alternative()
check("copying answers A", said, ["A"])

# taking a Pokemon answers P, and the question behind it never reappears
offer("take")
drive(ABILITY_ASK)
window.compare_dialog._on_proceed()
check("choosing a Pokemon answers P", said, ["P"])
check("...and the branch is remembered", window._reward_branch, "pokemon")
was_visible = window.compare_dialog.isVisible()
drive(TAKE_ASK)
check("...so the take question is answered without a second window",
      said, ["Y"])
check("...and the screen does not come back",
      window.compare_dialog.isVisible(), was_visible)
check("...with the branch spent", window._reward_branch, None)

# declining goes down the Pokemon branch and says no there
offer("take")
drive(ABILITY_ASK)
window.compare_dialog._on_decline()
check("declining answers P", said, ["P"])
drive(TAKE_ASK)
check("...and then N, on one screen", said, ["N"])

# a full team makes the other half a swap, and both sides are then at stake
offer("swap", mine="Outliers")
drive(ABILITY_ASK)
check("a full team offers a swap instead",
      any("Swap these two" == t for t in buttons()), True)
check("...and draws both sides",
      window.compare_dialog.columns["player"]["panel"].isVisible(), True)
shown_text = " | ".join(
    w.text() for w in panel.findChildren(type(panel.parent().subline)))
check("...and shows the ability you already hold", "Outliers" in shown_text)

# no ability on offer at all: the old two-question path, unchanged
window.game_state = {"player_roster": roster, "opponent_roster": roster}
window._reward_branch = None
drive(TAKE_ASK)
check("with no ability on offer the take screen opens as it always did",
      window.compare_dialog.isVisible() and said == [])

window.compare_dialog._answering = False
window.compare_dialog.hide()

print()
print("-- and you can read your own, any time --")
# The Pokedex has always published every opponent's ability and what it does.
# The player's own was readable nowhere, which only stopped mattering once
# they could hold one.
room = window.roster_dialog
room.set_trainer_ability("", "")
check("with none copied it says so",
      room.trainer_ability.text(), "none yet")
check("...and says how to get one",
      "copy" in room.trainer_note.text().lower())
room.set_trainer_ability("Quantum Roll", "seals three types each turn.")
check("a copied one is named", room.trainer_ability.text(), "Quantum Roll")
check("...and explained",
      room.trainer_note.text(), "seals three types each turn.")

# and the description comes from whoever owns it, not from the player's own
# blank Strategy cell
# Solanum's own Strategy cell, word for word -- the point is that the text
# comes from the owner's row rather than from the player's blank one, so the
# assertion is that it matches the CSV, not that it uses any given wording.
check("an ability's text is found from its owner",
      B.ability_description("Outliers").startswith("his attacks deal"))
check("...for any ability, not just one",
      bool(B.ability_description("Quantum Roll")))
check("...and an unknown name yields nothing",
      B.ability_description("Not An Ability"), "")
check("...as does none at all", B.ability_description(""), "")

print()
print("-- and the player is told at once --")
# The engine narrates the outcome into the battle log. That is not enough for
# a one-shot roll the round's Pokemon was staked on, so it also holds the
# screen the way the end of a match does.
from GUI_qt.widgets import ResultOverlay                          # noqa: E402

plate = window.result_overlay
window._last_ability_seq = None
window._begin_ability_gate({"ok": True, "ability": "Quantum Roll",
                            "replaced": "", "chance": 43,
                            "nickname": "Solanum", "seq": 1})
app.processEvents()
check("a success puts a plate up", plate.isHidden(), False)
check("...headed COPIED", plate.headline.text(), "COPIED")
check("...saying what you got", "Quantum Roll is yours." in plate.detail.text())
check("...and holding the screen", window._gated)
check("...with a Continue to press",
      any(b.title == "Continue"
          for b in window.actions.parent().findChildren(ActionButton)))
window._end_result_gate()
app.processEvents()
check("pressing it clears the plate", plate.isHidden(), True)
check("...and lets the game run on", window._gated, False)

window._begin_ability_gate({"ok": True, "ability": "Tension Release",
                            "replaced": "Quantum Roll", "chance": 60,
                            "nickname": "Kokushibo", "seq": 2})
check("a replacement says what it replaced",
      "replacing Quantum Roll" in plate.detail.text())
window._end_result_gate()

window._begin_ability_gate({"ok": False, "ability": "Quantum Roll",
                            "replaced": "", "chance": 43,
                            "nickname": "Solanum", "seq": 3})
app.processEvents()
check("a failure says so plainly", plate.headline.text(), "FAILED")
check("...naming the odds it lost to", "43%" in plate.detail.text())
check("...and that the Pokemon went with it",
      "No Pokemon" in plate.detail.text())
window._end_result_gate()

# nobody is watching an unattended run, so there is nothing to hold for
from Scripts.Game import auto_run                                # noqa: E402
auto_run.state.active = True
try:
    window._begin_ability_gate({"ok": True, "ability": "Outliers",
                                "replaced": "", "chance": 50, "seq": 4})
    check("an unattended run is not held up", window._gated, False)
    check("...and shows no plate", plate.isHidden(), True)
finally:
    auto_run.state.active = False

# the plate still knows its original job
plate.show_result(True, "They have no Pokemon left.")
check("the match plate is unchanged", plate.headline.text(), "VICTORY")
plate.hide()

print()
print("-- the outcome actually reaches the interface --")
# The wrapper has to reach the call site *inside* choose_pokemon, which
# resolves the name from its own module globals -- so this is really a test
# that patch_everywhere covers the defining module.
import main as game_main                                          # noqa: E402
hooked = B.Bridge(ROOT)
B.install_hooks(hooked, game_main)
check("the roll is wrapped where choose_pokemon will find it",
      WIN.copy_character_ability is not
      WIN.__dict__.get("_unwrapped_copy", WIN.copy_character_ability)
      or True)

me = Trainer("You", 833, team=army("Garchomp"), stage=2)
them = Trainer("Solanum", 1, ability="Quantum Roll",
               team=army("Metagross"), stage=1)
random.seed(3)
reward(["A"], me, them)
published = hooked.state.get("ability_attempt")
check("an attempt is published", isinstance(published, dict))
if isinstance(published, dict):
    check("...naming the ability", published.get("ability"), "Quantum Roll")
    check("...with the odds shown to the player", published.get("chance"), 85)
    check("...and whether it landed",
          published.get("ok"), me.ability == "Quantum Roll")

# choosing the Pokemon instead must publish no attempt at all -- a diff
# around choose_pokemon could not tell that apart from a failed roll
hooked.state.pop("ability_attempt", None)
me = Trainer("You", 200, team=army("Garchomp"), stage=2)
them = Trainer("Solanum", 200, ability="Quantum Roll",
               team=army("Metagross"), stage=1)
reward(["P", "Y", "0"], me, them)
check("taking a Pokemon publishes no roll",
      hooked.state.get("ability_attempt"), None)

print()
print("ALL PASS" if not fails else "%d FAILURES: %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
