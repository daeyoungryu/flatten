class Base:
    def run(self):
        return "base"


def hacked(self):
    return "hacked"


Base.run = hacked

METHOD = "Base.run"


def observed_types():
    return [Base]
