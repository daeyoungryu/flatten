class Worker:
    def run(self, value: int) -> int:
        return value + 1


def left(worker: Worker) -> int:
    return worker.run(1)


def right(worker: Worker) -> int:
    return worker.run(1)


def main() -> tuple[int, int]:
    worker = Worker()
    return left(worker), right(worker)


if __name__ == "__main__":
    print(main())
