"""Feed synthetic prompts straight into a MainWindow and inspect what it
renders: the reward screen, Keep All, the champion fold, and the tabbed
team viewer. The bridge's game thread is stubbed, so nothing runs the game
or touches savefile.dat.
"""
import os
import sys
import threading

ROOT, OUT = sys.argv[1], sys.argv[2]
HEADED = os.environ.get("QT_QPA_PLATFORM") != "offscreen"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtWidgets import QApplication, QLabel     # noqa: E402

from GUI import bridge as B                            # noqa: E402
B.Bridge.start = lambda self: None

from GUI_qt import main_window as MW                   # noqa: E402
from GUI_qt.widgets import ActionButton                # noqa: E402

app = QApplication.instance() or QApplication([])
w = MW.MainWindow(ROOT)
w.show()

failures = []


def check(label, got, want):
    if got == want:
        print("%-52s PASS" % label)
    else:
        print("%-52s FAIL got=%r want=%r" % (label, got, want))
        failures.append(label)


def buttons():
    """Every ActionButton currently in the action area, by label."""
    found = {}
    for b in w.actions_body.findChildren(ActionButton):
        for lab in b.findChildren(QLabel):
            text = (lab.text() or "").strip()
            if text:
                found.setdefault(text, b)
                break
    return found


def click(label):
    found = buttons()
    assert label in found, "no %r button; have %s" % (label,
                                                      sorted(found))
    found[label].on_click()


class Req:
    """Stands in for bridge.InputRequest."""

    def __init__(self, prompt, kind="generic", recent=""):
        self.prompt, self.kind, self.recent = prompt, kind, recent
        self.value = None
        self.event = threading.Event()

    def answer(self, value):
        self.value = value
        self.event.set()


def mon(name, tier, total, types, moves):
    return {"name": name, "sprite": name.lower().replace(" ", "-"),
            "types": types, "tier": tier, "ability": ["Levitate"],
            "status": "Normal", "hp": 100, "max_hp": 100, "stats": [],
            "nominal": [90, 80, 70, 110, 95, 60], "iv": [10] * 6,
            "total": total, "total_iv": 60, "modifier": [0] * 9,
            "volatile": {}, "moveset": ["Switching"] + moves,
            "moves": {m: B.snap_move(m) for m in moves}, "disabled": {},
            "charging": ["", "", 0], "protecting": False, "fainted": False,
            "active": False}


MINE = [mon("Pikachu", "Low", 320, ["Electric"], ["Thunderbolt", "Volt Switch"]),
        mon("Gengar", "High", 500, ["Ghost", "Poison"], ["Shadow Ball"]),
        mon("Snorlax", "Medium", 540, ["Normal"], ["Body Slam", "Rest"]),
        mon("Onix", "Very Low", 385, ["Rock", "Ground"], ["Earthquake"]),
        mon("Mawile", "Medium", 380, ["Steel", "Fairy"], ["Play Rough"]),
        mon("Psyduck", "Very Low", 320, ["Water"], ["Surf"])]
THEIRS = [mon("Metagross", "Ultra High", 600, ["Steel", "Psychic"],
              ["Meteor Mash", "Bullet Punch"]),
          mon("Milotic", "Very High", 540, ["Water"], ["Scald", "Recover"]),
          mon("Skarmory", "High", 465, ["Steel", "Flying"], ["Brave Bird"]),
          mon("Blissey", "Boss", 540, ["Normal"], ["Soft-Boiled"]),
          mon("Tyranitar", "Ultra High", 600, ["Rock", "Dark"], ["Crunch"]),
          mon("Zapdos", "Very High", 580, ["Electric", "Flying"], ["Thunder"])]

w._apply_state({"phase": "manage", "player_roster": MINE,
                "opponent_roster": THEIRS, "opponent_known": True})

# --------------------------------------------------------- 1. reward screen
# One screen, one press. The engine asks yes/no and then two index questions;
# the window answers all three from what is selected in it.
req = Req("Input Y if you want to swap, and N otherwise. ", kind="reward")
w._show_request(req)
app.processEvents()
d = w.compare_dialog
check("no Y/N buttons on the reward screen any more",
      [b for b in buttons() if b in ("Yes", "No")], [])
check("the compare window opened by itself", d is not None and d.isVisible(),
      True)
labels = [c.text() for c in d.findChildren(QLabel) if c.text()]
check("the button says what it does, not 'Proceed'",
      "Swap these two" in labels, True)
check("...and so does the way out", "No thanks" in labels, True)
check("no ambiguous Proceed button at all", "Proceed" in labels, False)
check("both columns are marked as selected",
      ("selected" in d.columns["player"]["heading"].text()
       and "selected" in d.columns["opponent"]["heading"].text()), True)
check("the note spells out the actual trade",
      "Swapping would give up" in d.note.text(), True)
check("a full team is told its team is full",
      "full" in d.subline.text().lower(), True)

# one press answers the yes/no *and* remembers both picks
d._pick("player", 2)
d._pick("opponent", 4)
d._on_proceed()
check("one press answers the confirmation", req.value, "Y")
check("...and records both sides",
      w._reward_plan, {"mine": 2, "theirs": 4})
check("...and puts the window away", d.isVisible(), False)

# the two index questions that follow never reach the player. Their prompts
# list all six slots, as the engine's do for a full team.
SIX_MINE = "[%s]" % ", ".join("(%d, %r)" % (i, m["name"])
                              for i, m in enumerate(MINE))
SIX_THEIRS = "[%s]" % ", ".join("(%d, %r)" % (i, m["name"])
                                for i, m in enumerate(THEIRS))
mine_q = Req("Choose the pokemon you don't want on your team, or 9 to go back:"
             + chr(10) + SIX_MINE + chr(10) + "--> ", kind="reward")
w._show_request(mine_q)
app.processEvents()
check("the 'which of yours' question answers itself", mine_q.value, "2")
check("...with no buttons shown for it", buttons(), {})
theirs_q = Req("Take the pokemon you want on the other team, or 9 to go back:"
               + chr(10) + SIX_THEIRS + chr(10) + "--> ", kind="reward")
w._show_request(theirs_q)
app.processEvents()
check("the 'which of theirs' question answers itself", theirs_q.value, "4")

# ...and an index the engine is not actually offering is pulled back into
# range rather than sent, which would make it ask the same question again
w._reward_plan = {"mine": 5, "theirs": 5}
narrow = Req("Take the pokemon you want on the other team, or 9 to go back:"
             + chr(10) + "[(0, 'Metagross'), (1, 'Milotic')]" + chr(10)
             + "--> ", kind="reward")
w._show_request(narrow)
app.processEvents()
check("an out-of-range pick is clamped to what is offered", narrow.value, "1")
w._reward_plan = {"mine": 2, "theirs": 4}

# changing your mind at the last minute unwinds the whole sequence
req = Req("Input Y if you want to swap, and N otherwise. ", kind="reward")
w._show_request(req)
app.processEvents()
w.compare_dialog._on_decline()
check("No thanks declines the swap", req.value, "N")
check("...and forgets any earlier plan", w._reward_plan, None)
stray = Req("Choose the pokemon you don't want on your team, or 9 to go back:",
            kind="reward")
w._show_request(stray)
app.processEvents()
check("...so a stale index question goes back instead of choosing",
      stray.value, "9")

# the take offer, where declining means the organiser picks for you
req = Req("Input Y if you want to take from the opponent, and N to get a "
          "random pokemon from the organizer. ", kind="reward")
w._show_request(req)
app.processEvents()
labels = [c.text() for c in w.compare_dialog.findChildren(QLabel) if c.text()]
check("the take offer says Take it", "Take it" in labels, True)
check("...and taking says nothing of yours goes",
      "given up" in w.compare_dialog.subline.text().lower(), True)
check("...and only their column is marked",
      ("selected" in w.compare_dialog.columns["opponent"]["heading"].text()
       and "selected" not in
       w.compare_dialog.columns["player"]["heading"].text()), True)
w.compare_dialog._pick("opponent", 1)
w.compare_dialog._on_proceed()
check("one press takes it", req.value, "Y")
pick = Req("You may take one pokemon from the opponent, or 9 to go back:",
           kind="reward")
w._show_request(pick)
app.processEvents()
check("...and the follow-up uses that pick", pick.value, "1")

# the halves stay the same width whatever is in them
widths = set()
for side, index in (("player", 0), ("player", 5), ("opponent", 0),
                    ("opponent", 3)):
    probe = Req("Input Y if you want to swap, and N otherwise. ",
                kind="reward")
    w._show_request(probe)
    w.compare_dialog._pick(side, index)
    app.processEvents()
    widths.add(tuple(w.compare_dialog.columns[s]["heading"]
                     .parentWidget().width() for s in ("player", "opponent")))
    probe.answer = lambda value: None
check("both halves are always the same width",
      {left == right for left, right in widths}, {True})
check("...and that width does not drift with the selection", len(widths), 1)
w.compare_dialog.close()

# the "press any key" after a reward answers itself
cont = Req("Press any key to continue.", kind="generic")
w._show_request(cont)
app.processEvents()
check("the continue after a reward answers itself", cont.value, "")
cont2 = Req("Press any key to continue.", kind="generic")
w._show_request(cont2)
app.processEvents()
check("an ordinary continue still waits for the player", cont2.value, None)

# a benched Pokemon is still on your roster and still swappable
BENCHED = [dict(m) for m in MINE]
BENCHED[-1]["benched"] = True
w._apply_state({"phase": "manage", "player_roster": BENCHED,
                "opponent_roster": THEIRS, "opponent_known": True})
w.roster_dialog.show_side("player")
w.roster_dialog._show(5)
app.processEvents()
names = [l.text() for l in w.roster_dialog.findChildren(QLabel)]
check("benched Pokemon is listed on your side",
      any("(benched)" in t for t in names), True)
check("...and chipped in the detail pane",
      any(t == "BENCHED" for t in names), True)
check("all six roster slots offered",
      len(w.roster_dialog.roster), 6)
w.roster_dialog.hide()
if HEADED:
    w.grab().save(os.path.join(OUT, "reward_screen.png"))

# --------------------------------------------------------- 2. Keep All
w.roster_dialog.hide()
keep = Req("You can keep at most 6 Pokemon for your next run. Pick them one "
           "at a time, then enter 9 when you are done: \n"
           "[(0, 'Pikachu'), (1, 'Gengar'), (2, 'Snorlax'), (3, 'Onix'), "
           "(4, 'Mawile'), (5, 'Psyduck')]\n", kind="team_keep")
w._show_request(keep)
app.processEvents()
check("keep screen offers Keep All", "Keep All" in buttons(), True)
check("nothing selected yet", len(w._keep_state["checked"]), 0)
click("Keep All")
app.processEvents()
check("Keep All highlights all six", sorted(w._keep_state["checked"]),
      [0, 1, 2, 3, 4, 5])
check("Keep All does not submit", keep.value, None)
check("it becomes Clear selection", "Clear selection" in buttons(), True)
tiles = [b for b in w.actions_body.findChildren(ActionButton)
         if any((l.text() or "") == "selected"
                for l in b.findChildren(QLabel))]
check("every tile reads 'selected'", len(tiles), 6)
if HEADED:
    w.grab().save(os.path.join(OUT, "keep_all.png"))
click("Clear selection")
app.processEvents()
check("Clear selection empties it", len(w._keep_state["checked"]), 0)
click("Keep All")
app.processEvents()
click("Confirm selection")
check("Confirm sends the first pick", keep.value, "0")
check("the rest are queued", w._pending_answers, ["1", "2", "3", "4", "5"])
check("no stale 9 behind a full keep", "9" in w._pending_answers, False)

# a stale queue must not answer a different screen
after = Req("Press any key to confirm the results.", kind="generic")
w._pending_answers = ["9"]
w._pending_kind = "team_keep"
w._show_request(after)
app.processEvents()
check("stale queue dropped, not sent", after.value, None)
check("queue cleared", w._pending_answers, [])

# --------------------------------------------------------- 3. champion fold
champ = Req("\nPress any key to proceed.", kind="generic", recent=(
    "Congratulations! You have won the Pokemon World Championship!!!\n"
    "You have obtained 10 World Champion Title(s) in your career!\n\n"
    "-- credits --\n"))
w._show_request(champ)
app.processEvents()
check("champion continue answers itself", champ.value, "")
feed = [l.text() for l in w.feed_scroll.findChildren(QLabel)]
check("championship announced in the feed",
      any("World Champion" in t for t in feed), True)

plain = Req("Press any key to continue.", kind="generic", recent="Round 3:\n")
w._show_request(plain)
app.processEvents()
check("an ordinary continue still waits", plain.value, None)
check("...and renders a button", "Continue" in buttons(), True)

# ----------------------------------------------------------- 3b. credits
# The credits used to open themselves the moment a run ended, over the top of
# the final standings. They are a button now, and it still knows if you won.
from GUI_qt.panels import CreditsDialog                 # noqa: E402
w.game_state = dict(w.game_state or {}, champion=True,
                    leaderboard=[{"is_player": True, "championship": 7}])
w._show_done("finished")
app.processEvents()
check("finishing a run does not throw up the credits",
      w.findChildren(CreditsDialog), [])
check("...but it remembers whether you won",
      w._credits_state, {"champion": True, "titles": 7})
check("the top bar offers Credits",
      any(lab.text() == "Credits" for lab in w.findChildren(QLabel)), True)
w._open_credits()
app.processEvents()
check("...and the button opens them",
      w.credits_dialog is not None and w.credits_dialog.isVisible(), True)
shown = [l.text() for l in w.credits_dialog.findChildren(QLabel) if l.text()]
check("...reading as a win", any("7" in t for t in shown), True)
w.credits_dialog.close()

# --------------------------------------------------- 4. no matchup pop-up
def bracket(round_no):
    return {"round": round_no, "pairs": [
        [{"nickname": "Marvin", "strength": 421, "color": "", "wins": 1,
          "score": 2, "championship": 0, "is_player": True},
         {"nickname": "Magnus Carlsen", "strength": 288, "color": "",
          "wins": 1, "score": 1, "championship": 0, "is_player": False}]]}


def current_tab():
    tabs = w.standings_dialog.tabs
    return tabs.tabText(tabs.currentIndex())


w.standings_dialog.hide()
w._apply_state({"phase": "manage", "bracket": bracket(2)})
app.processEvents()
check("a new round does not open standings",
      w.standings_dialog.isVisible(), False)
check("...but the data is there for the button",
      (w.game_state.get("bracket") or {}).get("round"), 2)

# already open: follow the new round rather than show a stale tab
w.standings_dialog.select("Leaderboard")
w._open_standings()
app.processEvents()
w._apply_state({"phase": "manage", "bracket": bracket(3)})
app.processEvents()
check("an open window follows to the new matchups", current_tab(), "Matchups")
w.standings_dialog.hide()

# the end-of-run standings still surface by themselves
w._apply_state({"phase": "leaderboard", "leaderboard": [
    {"nickname": "Marvin", "strength": 421, "stage": 5, "opponent_score": 20,
     "score": 8, "championship": 1, "is_player": True, "rank": 1}]})
app.processEvents()
check("final standings still open themselves",
      w.standings_dialog.isVisible(), True)
check("...on the leaderboard", current_tab(), "Leaderboard")
w.standings_dialog.hide()

print("\n%s" % ("ALL PASS" if not failures
                else "%d FAILURES: %s" % (len(failures), failures)))
sys.exit(1 if failures else 0)
