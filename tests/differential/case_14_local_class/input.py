def make_class():
    class Local:
        def run(self):
            return "local"

    return Local


Local = make_class()
METHOD = "Local.run"


def observed_types():
    return [Local]
