from flatten.finals import final


@final
class Worker:
    def run(self, value):
        print("value", value)
        return value + 1


def main():
    return Worker().run(2)


if __name__ == "__main__":
    raise SystemExit(main())
