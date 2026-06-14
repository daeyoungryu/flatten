from flatten.closure import ClosureChecker
from flatten.finals import final
from flatten.planner import RewritePlanner


class Worker:
    @final
    def run(self):
        return "ok"


def main() -> None:
    verdict = ClosureChecker().check("Worker.run", [Worker])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]
    print(decision.reason_code)


if __name__ == "__main__":
    