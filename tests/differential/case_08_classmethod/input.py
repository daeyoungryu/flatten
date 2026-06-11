class Base:
    @classmethod
    def run(cls):
        return cls.__name__


METHOD = "Base.run"


def observed_types():
    return [Base]
