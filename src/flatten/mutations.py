"""Source-level mutation generation for false-positive safety checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MutationCase:
    kind: str
    description: str
    source: str


def generate_mutations(source: str) -> list[MutationCase]:
    """Generate conservative dispatch-risk mutations for a source fixture.

    The harness intentionally produces simple, source-level variants. They are
    not meant to be exhaustive; they are regression probes for classes of
    mutations that must not be silently rewritten.
    """
    base = source.rstrip() + "\n\n"
    return [
        MutationCase(
            "new-subclass",
            "add a previously unobserved subclass",
            base + "class MutatedWorker(Worker):\n    pass\n",
        ),
        MutationCase(
            "dispatch-target",
            "add a subclass with a new dispatch implementation",
            base
            + "class MutatedWorker(Worker):\n"
            + "    def run(self, value):\n"
            + "        return value + 100\n",
        ),
        MutationCase(
            "monkey-patch",
            "replace the method through class attribute assignment",
            base + "Worker.run = lambda self, value: value + 100\n",
        ),
        MutationCase(
            "runtime-registration",
            "add an init-subclass registration hook and registered subclass",
            base
            + "REGISTRY = []\n"
            + "class RegistryBase:\n"
            + "    def __init_subclass__(cls):\n"
            + "        REGISTRY.append(cls)\n"
            + "class RegisteredWorker(RegistryBase, Worker):\n"
            + "    pass\n",
        ),
        MutationCase(
            "setattr-change",
            "replace the method through setattr",
            base + "setattr(Worker, 'run', lambda self, value: value + 100)\n",
        ),
    ]
