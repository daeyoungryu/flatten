class Dynamic:
    def __getattribute__(self, name: str):
        return super().__getattribute__(name)

    def run(self) -> str:
        return "dynamic"


def main() -> str:
    worker = Dynamic()
    return worker.run()


if __name__ == "__main__":
    print(main())
