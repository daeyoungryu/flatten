class Base:
    def run(self):
        return "base"


class Child(Base):
    def run(self):
        return super().run()


METHOD = "Base.run"


def observed_types():
    return [Child]
