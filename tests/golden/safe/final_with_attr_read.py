from flatten.finals import final


@final
class Box:
    def __init__(self, value):
        self.value = value

    def read(self):
        return self.value


def main():
    box = Box(3)
    return box.read()
