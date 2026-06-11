class Base:
    def run(self):
        raise ValueError("base")


METHOD = "Base.run"


def observed_types():
    return [Base]
