class Base:
    def run(self, value):
        return value


METHOD = "Base.run"


def observed_types():
    return [Base]
