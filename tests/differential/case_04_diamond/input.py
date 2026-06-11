class Top:
    def run(self):
        return "top"


class Left(Top):
    pass


class Right(Top):
    pass


class Bottom(Left, Right):
    pass


METHOD = "Top.run"


def observed_types():
    return [Bottom]
