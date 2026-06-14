from flatten.finals import final


@final
class Worker:
    def run(self) -> int:
        raise ValueError("same failure")


def main() -> int:
    worker = Worker()
    return worker.run()


if __name__ == "__main__":
    print(