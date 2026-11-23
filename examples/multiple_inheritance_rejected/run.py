from flatten.closure import ClosureChecker
from flatten.planner import RewritePlanner


class Left:
    def run(self):
        return "left"


class Right:
    def run(self):
        return "right"


class Both(Left, Right):
    pass


def main() -> None:
    verdict = ClosureChecker().check("Left.run", [Both])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]
    print(decision.reason_code)


if __name__ == "__main__":
    main()
