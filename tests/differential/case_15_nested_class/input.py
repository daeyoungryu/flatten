class Outer:
    class Nested:
        def run(self):
            return "nested"


METHOD = "Nested.run"


def observed_types():
    return [Outer.Nested]
