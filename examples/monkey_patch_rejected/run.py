from flatten.closure import ClosureChecker
from flatten.planner import RewritePlanner


class Target:
    def run(self):
        return "original"


def replacement(self):
    return "patched"


Target.run = replacement


def main() -> None:
    verdict = ClosureChecker().check("Target.run", [Target])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]
    print(decision.reason_code)


if __name__ == "__main__":
    main()
