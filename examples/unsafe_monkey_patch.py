class Worker:
    def run(self) -> str:
        return "original"


def patched(self) -> str:
    return "patched"


Worker.run = patched


def main() -> str:
    worker = Worker()
    return worker.run()


if __name__ == "__main__":
    print(main())
