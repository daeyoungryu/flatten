from typing import final


@final
class Worker:
    def run(self, value: int) -> int:
        return value + 1


def main() -> int:
    worker = Worker()
    return worker.run(2)


if __name__ == "__main__":
    print(main())
