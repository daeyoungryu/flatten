class Base:
    @staticmethod
    def run(self):
        return "base"


METHOD = "Base.run"


def observed_types():
    return [Base]
