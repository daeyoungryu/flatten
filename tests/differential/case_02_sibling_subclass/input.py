class Base:
    def run(self):
        return "base"


class A(Base):
    def run(self):
        return "a"


class B(Base):
    def run(self):
        return "b"


METHOD = "Base.run"


def observed_types():
    return [A]
