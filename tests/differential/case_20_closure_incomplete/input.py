class Base:
    def run(self):
        return "base"


class Observed(Base):
    pass


class Hidden(Base):
    pass


METHOD = "Base.run"


def observed_types():
    return [Observed]
