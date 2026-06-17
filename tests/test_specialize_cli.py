import importlib.util
import json
import subprocess
import sys
import textwrap


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_expand_prints_target_method_source(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text(
        textwrap.dedent(
            """
            class Service:
                def run(self, value):
                    return value + 1
            """
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "expand",
            str(source),
            "--target",
            "Service.run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "def run(self, value):" in result.stdout
    assert "return value + 1" in result.stdout


def test_specialize_emits_executable_python_with_constant_entry_args(tmp_path):
    source = tmp_path / "sample.py"
    args_json = tmp_path / "args.json"
    out = tmp_path / "specialized.py"
    source.write_text(
        textwrap.dedent(
            """
            class Dog:
                def __init__(self, name):
                    self.name = name

                def speak(self, count):
                    return (self.name + "!") * count

            class Service:
                def run(self, obj, count=1):
                    return obj.speak(count)

            def main(name, count=1):
                service = Service()
                obj = Dog(name)
                return service.run(obj, count=count)
            """
        ),
        encoding="utf-8",
    )
    args_json.write_text(
        json.dumps({"args": ["choco"], "kwargs": {"count": 3}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "specialize",
            str(source),
            "--entry",
            "sample:main",
            "--target",
            "Service.run",
            "--args-json",
            str(args_json),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert "def specialized():" in text
    assert 'return main("choco", count=3)' in text

    original = _load(source, "sample_original")
    generated = _load(out, "sample_specialized")
    assert generated.specialized() == original.main("choco", count=3)
