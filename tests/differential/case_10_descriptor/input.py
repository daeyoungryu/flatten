class Descriptor:
    def __get__(self, obj, owner):
        return lambda: "descriptor"


class Base:
    run = Descriptor()


METHOD = "Base.run"


def observed_types():
    return [Base]
