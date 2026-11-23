class A:
    def run(self, value: int) -> int:
        return value + 1


class B:
    def run(self, value: int) -> int:
        return value + 2


def main(flag: bool = False) -> int:
    worker = B() if flag else A()
    return worker.run(2)


if __name__ == "__main__":
    print(main())
