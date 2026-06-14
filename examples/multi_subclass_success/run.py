from flatten.closure import ClosureChecker
from flatten.finals import final
from flatten.planner import RewritePlanner


class Base:
    @final
    def run(self):
        return "base"


class A(Base):
    pass


class B(Base):
    pass


def main() -> None:
    verdict = ClosureChecker().check("Base.run", [A, B])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]
    print(decision.reason_code)


if __name__ == "__main__":
    