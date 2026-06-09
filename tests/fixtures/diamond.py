"""5단계 다이아몬드 상속 테스트 픽스처.

A (최상위)
├── B
│   └── D
└── C
    └── D (다이아몬드 — D는 B와 C 모두 상속)
        └── E (최하위)
"""


class A:
    def process(self, x: int) -> str:
        return f"A:{x}"


class B(A):
    def process(self, x: int) -> str:
        return f"B:{x}"


class C(A):
    def process(self, x: int) -> str:
        return f"C:{x}"


class D(B, C):
    def process(self, x: int) -> str:
        return f"D:{x}"


class E(D):
    def process(self, x: int) -> str:
        return f"E:{x}"


def make_all() -> list[A]:
    return [A(), B(), C(), D(), E()]
