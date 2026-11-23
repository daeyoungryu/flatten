class Base:
    def run(self) -> str:
        return "base"


class Observed(Base):
    def run(self) -> str:
        return "observed"


class Unobserved(Base):
    def run(self) -> str:
        return "unobserved"


def main() -> str:
    worker = Observed()
    return worker.run()


if __name__ == "__main__":
    print(main())
