class DynamicBase:
    def __setattr__(self, name: str, value: object) -> None:
        object.__setattr__(self, name, value)

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

    def run(self, expression: str) -> object:
        import math

        return eval(expression) + math.sqrt(4)


class Worker(DynamicBase):
    pass


def main() -> object:
    worker = Worker()
    return worker.run("1")


if __name__ == "__main__":
    print(main())
