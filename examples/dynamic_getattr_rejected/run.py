from flatten.closure import ClosureChecker
from flatten.planner import RewritePlanner


class Dynamic:
    def __getattr__(self, name):
        raise AttributeError(name)

    def run(self):
        return 1


def main() -> None:
    verdict = ClosureChecker().check("Dynamic.run", [Dynamic])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]
    print(decision.reason_code)


if __name__ == "__main__":
    main()
