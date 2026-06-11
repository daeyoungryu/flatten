class Base:
    def __getattr__(self, name):
        raise AttributeError(name)

    def run(self):
        return 1


METHOD = "Base.run"


def observed_types():
    return [Base]
