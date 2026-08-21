"""One line of the tournament bracket.

This used to draw a ruled box in box-drawing characters, three lines per entry,
for a console to print. The window builds the standings itself from these
values, and the log filter was throwing the drawing away again at the other end
(GUI/bridge.py, simplify_box_art) -- 640 lines of frame in a five-battle run.

The class stays because it is how the result of every pairing reaches the
interface: GUI/bridge.py wraps EntryBox to record (id, name, score, stage) as
the boxes are built, which is where the round results and the standings screen
come from. Only the picture is gone.
"""


class EntryBox:
    def __init__(self, id=" ", name=" ", score=" ", stage=" "):
        self.id = str(id)
        self.name = name
        self.score = str(score)
        self.stage = str(stage)
        #: kept so anything that reads it still finds a string
        self.structure = ""
