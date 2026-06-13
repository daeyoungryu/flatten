from flatten.finals import final


class Base:
    @final
    def run(self):
        return "base"


class Child(Base):
    pass


METHOD = "Base.run"


def observed_types():
    return [Child]
