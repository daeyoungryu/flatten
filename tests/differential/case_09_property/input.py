class Base:
    @property
    def run(self):
        return lambda: "base"


METHOD = "Base.run"


def observed_types():
    return [Base]
