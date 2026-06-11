class Base:
    def run(self):
        yield "generator"


METHOD = "Base.run"


def observed_types():
    return [Base]
