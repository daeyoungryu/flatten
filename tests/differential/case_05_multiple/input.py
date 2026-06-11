class Left:
    def run(self):
        return "left"


class Right:
    def run(self):
        return "right"


class Both(Left, Right):
    pass


METHOD = "Left.run"


def observed_types():
    return [Both]
