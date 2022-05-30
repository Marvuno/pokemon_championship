class EntryBox:
    def __init__(self, id=" ", name=" ", score=" ", stage=" "):
        self.id = str(id)
        self.name = name
        self.score = str(score)
        self.stage = str(stage)
        self.structure = structure(self.id, self.name, self.score, self.stage)


def structure(id, name, stage, score):
    box = f'╔====╦{"=" * 32}╦===╦===╗\n' \
          f'║ {id + " " * (3 - len(id))}║ {name + " " * (31 - len(name))}║ {stage} ║ {score} ║\n' \
          f'╚====╩{"=" * 32}╩===╩===╝'
    return box

