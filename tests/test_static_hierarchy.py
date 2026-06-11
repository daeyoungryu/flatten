import json
from argparse import Namespace

from flatten.cli import cmd_analyze
from flatten.static import analyze_class_hierarchy


def test_static_hierarchy_extracts_subclasses_methods_final_and_dynamic_risks():
    source = """
from typing import final

@final
class Root:
    def run(self): ...

class Child(Root):
    def run(self): ...

class Dynamic(Child):
    def __getattribute__(self, name):
        return super().__getattribute__(name)

setattr(Child, "run", lambda self: 1)
"""

    graph = analyze_class_hierarchy(source, filename="pkg/mod.py", module_name="pkg.mod")

    assert graph.classes["pkg.mod.Root"].is_final is True
    assert graph.classes["pkg.mod.Child"].bases == ("pkg.mod.Root",)
    assert graph.subclasses["pkg.mod.Root"] == {"pkg.mod.Child"}
    assert graph.method_overrides["run"] == {"pkg.mod.Root", "pkg.mod.Child"}
    assert "setattr" in graph.risk_flags
    assert "__getattribute__" in graph.classes["pkg.mod.Dynamic"].risk_flags


def test_static_hierarchy_flags_phase2_dynamic_blockers():
    source = """
class Base:
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
    def __init_subclass__(cls):
        super().__init_subclass__()
    def run(self, expression):
        return eval(expression)

class Importer:
    def run(self):
        import math
        return math.sqrt(4)
"""

    graph = analyze_class_hierarchy(source, filename="pkg/mod.py", module_name="pkg.mod")

    assert "__setattr__" in graph.classes["pkg.mod.Base"].risk_flags
    assert "__init_subclass__" in graph.classes["pkg.mod.Base"].risk_flags
    assert "dynamic-code-execution" in graph.classes["pkg.mod.Base"].risk_flags
    assert "dynamic-import" in graph.classes["pkg.mod.Importer"].risk_flags


def test_cli_analyze_reports_static_risk_reasons(tmp_path, capsys):
    source = tmp_path / "unsafe.py"
    source.write_text(
        "class Worker:\n"
        "    def run(self): return 'x'\n"
        "Worker.run = lambda self: 'patched'\n"
        "def main():\n"
        "    worker = Worker()\n"
        "    return worker.run()\n",
        encoding="utf-8",
    )

    exit_code = cmd_analyze(
        Namespace(path=source, format="json", strict=False)
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["static_analysis"]["risk_flags"] == ["class-attribute-assignment"]


def test_single_inheritance_is_not_flagged_as_multiple_inheritance():
    source = """
class Base:
    pass

class Child(Base):
    pass

class Mix(Base, object):
    pass
"""

    graph = analyze_class_hierarchy(source, filename="pkg/mod.py", module_name="pkg.mod")

    assert "multiple-inheritance" not in graph.classes["pkg.mod.Child"].risk_flags
    assert "multiple-inheritance" in graph.classes["pkg.mod.Mix"].risk_flags


def test_attribute_assignment_risk_only_tracks_attribute_targets():
    source = """
class Worker:
    pass

name = Worker
Worker.run = lambda self: 1
"""

    graph = analyze_class_hierarchy(source, filename="pkg/mod.py", module_name="pkg.mod")

    assert graph.risk_flags == {"class-attribute-assignment"}
